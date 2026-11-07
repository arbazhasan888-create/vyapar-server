"""Multiplayer server. Run from project root:  uvicorn server.main:app --host 0.0.0.0 --port 8000"""
import logging
import random
import string
import time
import uuid

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException

from game.board import TILES
from game.rules import Game, GameError, MIN_PLAYERS, MAX_PLAYERS, TOKEN_COLORS
from game.texts import err_text

log = logging.getLogger("uvicorn.error")
app = FastAPI()
rooms = {}
MAX_VOICE_B64 = 600_000    # base64 chars per voice message (~12 s of 11 kHz mono WAV is ~350 KB)
MAX_VOICE_KEPT = 5         # voice messages replayed to a player who reconnects
ROOM_GRACE = 3600          # seconds a started game is kept after everybody disconnected (so players can come back)


def err(key, fatal=False, **params):
    """Error message for a client: `key` + `params` let the app show it in the player's language;
    `msg` is the Hindi text (fallback for old apps)."""
    m = dict(type="error", key=key, params=params, msg=err_text("hi", key, params, fallback=key))
    if fatal:
        m["fatal"] = True
    return m


def purge_rooms():
    now = time.time()
    for code in [c for c, r in rooms.items() if r.empty_since and now - r.empty_since > ROOM_GRACE]:
        rooms.pop(code, None)


class Room:
    def __init__(self, code, max_players):
        self.code, self.max = code, max_players
        self.members = {}      # pid -> {"name", "ws"}
        self.host = None
        self.colors = {}        # pid -> token colour chosen in the lobby (host can change anyone's)
        self.game = None
        self.chat = []          # last chat messages, replayed to players who reconnect
        self.empty_since = None
        self.last_voice = {}    # pid -> time of the last voice message (flood guard)

    def lobby(self):
        return dict(type="lobby", code=self.code, host=self.host, max=self.max,
                    players=[dict(id=k, name=v["name"], color=self.colors.get(k)) for k, v in self.members.items()])

    def start_msg(self):
        return dict(type="start", tiles=TILES, state=self.game.state())

    async def broadcast(self, msg):
        for m in self.members.values():
            if m["ws"]:
                try:
                    await m["ws"].send_json(msg)
                except Exception:
                    m["ws"] = None


@app.get("/")
def health():
    return {"ok": True, "rooms": len(rooms)}


@app.post("/create")
def create(max_players: int = 4):
    purge_rooms()
    if not MIN_PLAYERS <= max_players <= MAX_PLAYERS:
        raise HTTPException(400, f"max_players must be {MIN_PLAYERS}-{MAX_PLAYERS}")
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    while True:
        code = "".join(random.choice(alphabet) for _ in range(5))
        if code not in rooms:
            break
    rooms[code] = Room(code, max_players)
    return {"code": code}


@app.websocket("/ws/{code}")
async def ws_endpoint(ws: WebSocket, code: str, pid: str, name: str = "खिलाड़ी"):
    await ws.accept()
    room = rooms.get(code.upper())
    log.warning(f"[vyapar] join code={code.upper()} pid={pid[:6]} name={name!r} room_found={bool(room)} rooms={list(rooms)} members={[k[:6] for k in room.members] if room else None}")
    if not room:
        await ws.send_json(err("room_not_found", fatal=True))
        await ws.close()
        return
    room.empty_since = None
    name = name.strip()[:14] or "खिलाड़ी"
    if pid in room.members:                       # reconnect keeps the seat
        old_ws = room.members[pid]["ws"]
        room.members[pid]["ws"] = ws
        if old_ws is not None:                    # same player opened a second connection: drop the stale one
            try:
                await old_ws.close()
            except Exception:
                pass
    elif room.game:
        await ws.send_json(err("game_started", fatal=True))
        await ws.close()
        return
    elif len(room.members) >= room.max:
        await ws.send_json(err("room_full", fatal=True))
        await ws.close()
        return
    else:
        room.members[pid] = dict(name=name, ws=ws)
        room.colors[pid] = next((c for c in TOKEN_COLORS if c not in room.colors.values()), TOKEN_COLORS[0])
        room.host = room.host or pid
    if room.game:
        await ws.send_json(room.start_msg())
        if room.chat:
            await ws.send_json(dict(type="chat_history", items=room.chat))
    else:
        await room.broadcast(room.lobby())

    try:
        while True:
            data = await ws.receive_json()
            kind = data.get("type")
            if kind == "start":
                if pid != room.host:
                    await ws.send_json(err("only_host_start"))
                elif len(room.members) < MIN_PLAYERS:
                    await ws.send_json(err("at_least", min=MIN_PLAYERS))
                elif not room.game:
                    room.game = Game([(k, v["name"]) for k, v in room.members.items()], colors=room.colors)
                    await room.broadcast(room.start_msg())
            elif kind == "set_color":
                target, color = data.get("pid"), data.get("color")
                if pid != room.host:                             # only the host chooses colours (for every player)
                    await ws.send_json(err("only_host_color"))
                elif room.game or target not in room.members or color not in TOKEN_COLORS:
                    pass
                else:
                    holder = next((k for k, c in room.colors.items() if c == color and k != target), None)
                    if holder:                               # colour already taken: the two players swap colours
                        room.colors[holder] = room.colors[target]
                    room.colors[target] = color
                    await room.broadcast(room.lobby())
            elif kind == "action" and room.game:
                try:
                    room.game.act(pid, data["action"], **data.get("args", {}))
                except (GameError, TypeError, KeyError) as e:
                    await ws.send_json(err(e.key, **e.params) if isinstance(e, GameError) else err("bad_move"))
                else:
                    await room.broadcast(dict(type="state", state=room.game.state()))
            elif kind == "chat":
                text = str(data.get("text", "")).strip()[:200]
                if text:
                    msg = dict(type="chat", id=pid, name=room.members[pid]["name"], text=text)
                    room.chat = (room.chat + [msg])[-50:]
                    await room.broadcast(msg)
            elif kind == "voice":
                audio = data.get("audio")
                if not isinstance(audio, str) or not audio:
                    continue
                if len(audio) > MAX_VOICE_B64:
                    await ws.send_json(err("voice_long"))
                    continue
                now = time.time()
                if now - room.last_voice.get(pid, 0) < 0.5:          # one message at a time per player
                    continue
                room.last_voice[pid] = now
                try:
                    dur = max(0.0, min(float(data.get("dur", 0)), 15.0))
                except (TypeError, ValueError):
                    dur = 0.0
                msg = dict(type="voice", id=pid, name=room.members[pid]["name"], audio=audio,
                           dur=round(dur, 1), vid=uuid.uuid4().hex)
                room.chat = (room.chat + [msg])[-50:]
                voices = [m for m in room.chat if m["type"] == "voice"]
                if len(voices) > MAX_VOICE_KEPT:                     # keep memory small: drop the oldest audio
                    drop = {id(m) for m in voices[:-MAX_VOICE_KEPT]}
                    room.chat = [m for m in room.chat if id(m) not in drop]
                await room.broadcast(msg)
    except WebSocketDisconnect:
        pass
    finally:
        log.warning(f"[vyapar] leave code={room.code} pid={pid[:6]}")
        m = room.members.get(pid)
        if m and m["ws"] is ws:
            m["ws"] = None
            if not room.game:                       # leaving the lobby frees the seat
                del room.members[pid]
                room.colors.pop(pid, None)
                if room.host == pid:
                    room.host = next(iter(room.members), None)
                await room.broadcast(room.lobby())
        if not any(v["ws"] for v in room.members.values()):
            if room.game:                           # keep a running game for a while so players can rejoin
                room.empty_since = time.time()
            else:
                rooms.pop(room.code, None)