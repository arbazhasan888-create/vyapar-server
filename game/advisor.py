"""Best-move advisor (the Hint button). It does not follow fixed rules: it plays the game forward.

For the player who asked it builds a list of possible moves (what the Hard computer would do, building on each land that can
take a house, redeeming a mortgaged land, paying the jail fine, buying / skipping a land, which land to mortgage when in debt ...),
copies the game, makes that move, and lets Hard computer players play every seat (also yours) for the next few rounds. That is
repeated many times with the same dice for every move (so the moves are compared fairly) and the move that leaves the player
richest compared with the others, with the fewest bankruptcies, wins.

advise(state, pid, budget) -> dict(kind, action, tile, gain, runs, ...) or None. It reads the plain state dict the clients
already have (online and computer games), and has no UI. It takes `budget` seconds at most (run it in a thread on a phone).
"""
import copy
import random
import time

from .board import TILES, GROUPS, HOTEL
from .rules import Game, GameError
from .bot import bot_step
from .value import build_options, raisable

HORIZON_ROUNDS = 10          # rounds (every player rolls once) looked ahead
MIN_RUNS = 6                 # fewer finished playouts than this: no advice from the simulation
BANKRUPT_PENALTY = 60000
WIN_BONUS = 30000


def game_from_state(st, seed=0):
    """A playable copy of the game described by a client state dict (state() of the engine)."""
    g = Game.__new__(Game)
    g.players = copy.deepcopy(st["players"])
    g.props = {int(k): dict(v) for k, v in st["props"].items()}
    g.turn = next(i for i, p in enumerate(g.players) if p["id"] == st["turn"])
    g.phase, g.dice, g.roll_seq = st["phase"], list(st.get("dice") or [0, 0]), st.get("roll_seq", 0)
    g.doubles, g.extra = 0, False
    g.pending_buy, g.pending_draw = st.get("pending_buy"), st.get("pending_draw")
    g.trade = None                                        # a deal in the air is left out of the simulation
    g.auction, g.auction_on = copy.deepcopy(st.get("auction")), st.get("auction_on", True)
    g.winner, g.creditor = st.get("winner"), None
    g.log, g.last_card, g.events, g.event_seq = [], st.get("last_card"), [], 0
    g.rng = random.Random(seed)
    g._bot_offer = {p["id"]: 10 ** 9 for p in g.players}  # nobody proposes trades inside the simulation
    return g


def _clone(g, seed):
    c = copy.deepcopy(g)
    c.rng = random.Random(seed)
    c._bot_offer = {p["id"]: 10 ** 9 for p in c.players}
    return c


def worth(g, pid):
    """Cash + lands at their price (mortgaged: half) + houses at 90% of their cost."""
    p = g.get(pid)
    if p["bankrupt"]:
        return 0.0
    v = float(p["money"])
    for i, s in g.props.items():
        if s["owner"] != pid:
            continue
        t = TILES[i]
        v += t["price"] * (0.5 if s["mortgaged"] else 1.0)
        h = s.get("houses") or 0
        if h and t["type"] == "property":
            v += 0.9 * t["house_cost"] * (4 if h >= HOTEL else h)
    return v


def score(g, pid):
    me = g.get(pid)
    if me["bankrupt"]:
        return -BANKRUPT_PENALTY
    rivals = [worth(g, o["id"]) for o in g.players if o["id"] != pid and not o["bankrupt"]]
    s = worth(g, pid) - (sum(rivals) / len(rivals) if rivals else 0.0)
    if g.winner == pid:
        s += WIN_BONUS
    return s


def _play(g, rng, rolls):
    """Let Hard computers play until `rolls` more dice rolls happened (or the game ended / got stuck)."""
    end = g.roll_seq + rolls
    for _ in range(rolls * 14 + 60):
        if g.winner or g.roll_seq >= end:
            break
        try:
            bot_step(g, rng, "hard")
        except GameError:
            break
        except Exception:
            break


def _apply(g, pid, mv):
    """Make the first move of a candidate on game copy g. Returns False if it is not allowed."""
    kind = mv["kind"]
    if kind == "natural":
        return True
    kw = {"tile": mv["tile"]} if mv.get("tile") is not None else {}
    try:
        g.act(pid, kind, **kw)
        return True
    except GameError:
        return False
    except Exception:
        return False


def candidates(g, pid):
    """Possible first moves for `pid`: dicts(kind, tile). "natural" = let the Hard computer decide."""
    me = g.get(pid)
    mine = g.cur()["id"] == pid
    c = [dict(kind="natural", tile=None)]
    props = {str(k): v for k, v in g.props.items()}
    if me["money"] < 0:                                              # in debt: which land to mortgage / which house to sell
        r = raisable(props, pid)
        seen = set()
        for it in r["items"]:
            key = (it["kind"], it["idx"])
            if key not in seen:
                seen.add(key)
                c.append(dict(kind=it["kind"], tile=it["idx"]))
        return c[:14]
    if mine and g.pending_buy is not None and not g.auction:
        c += [dict(kind="buy", tile=None), dict(kind="skip", tile=None)]
        return c
    if g.auction or (mine and g.pending_draw):
        return c
    if mine and me.get("in_jail") and g.phase == "roll":
        if me["cards"]:
            c.append(dict(kind="use_card", tile=None))
        c.append(dict(kind="pay_jail", tile=None))
        c.append(dict(kind="roll", tile=None))
    elif mine and g.phase == "act":
        c.append(dict(kind="end_turn", tile=None))
    elif mine and g.phase == "roll":
        c.append(dict(kind="roll", tile=None))
    for i, cost in build_options(props, pid)[:4]:                    # cheapest houses first
        if me["money"] - cost >= 300:
            c.append(dict(kind="build", tile=i))
    mort = sorted((i for i, s in g.props.items() if s["owner"] == pid and s["mortgaged"]), key=lambda i: -TILES[i]["price"])
    for i in mort[:3]:
        if me["money"] - int(TILES[i]["price"] // 2 * 1.1) >= 300:
            c.append(dict(kind="redeem", tile=i))
    return c


def describe_natural(g, pid):
    """What the Hard computer would do now: dict(kind, tile) by comparing a copy of the game before / after one step."""
    c = _clone(g, 1)
    before_h = {i: (s.get("houses") or 0, s["mortgaged"], s["owner"]) for i, s in c.props.items()}
    idx = c.pending_buy
    try:
        name = bot_step(c, random.Random(1), "hard")
    except Exception:
        return None
    tile = None
    if name in ("buy", "skip"):
        tile = idx
    elif name in ("build", "sell", "mortgage", "redeem"):
        for i, s in c.props.items():
            if (s.get("houses") or 0, s["mortgaged"], s["owner"]) != before_h.get(i):
                tile = i
                break
    return dict(kind=name, tile=tile)


def advise(st, pid, budget=2.0, tiles=None):
    """The best move for `pid` now, or None (nothing to say / too little time to find out)."""
    me = next((p for p in st["players"] if p["id"] == pid), None)
    if not me or me["bankrupt"] or st.get("winner"):
        return None
    base = game_from_state(st)
    cands = candidates(base, pid)
    live = []
    for mv in cands:                                                 # drop moves the engine does not allow
        t = _clone(base, 0)
        if _apply(t, pid, mv):
            live.append(mv)
    if len(live) < 2:
        return None
    n = len(base.players)
    rolls = HORIZON_ROUNDS * n
    totals = {i: [] for i in range(len(live))}
    t0 = time.time()
    run = 0
    while time.time() - t0 < budget and run < 60:
        seed = 1000 + run
        for i, mv in enumerate(live):                                # same dice for every candidate in one run
            if time.time() - t0 > budget * 1.25:
                break
            g = _clone(base, seed)
            if not _apply(g, pid, mv):
                totals[i].append(-BANKRUPT_PENALTY)
                continue
            _play(g, random.Random(seed), rolls)
            totals[i].append(score(g, pid))
            time.sleep(0.001)                                # a short breath: the screen stays smooth while it thinks
        run += 1
    runs = min(len(v) for v in totals.values())
    if runs < MIN_RUNS:
        return None
    avg = {i: sum(v[:runs]) / runs for i, v in totals.items()}
    best = max(avg, key=lambda i: avg[i] - (0 if live[i]["kind"] == "natural" else 0))
    nat = next(i for i, m in enumerate(live) if m["kind"] == "natural")
    # a different move must clearly beat the computer's own choice (more than 1 standard error of the paired difference)
    if best != nat:
        diffs = [totals[best][r] - totals[nat][r] for r in range(runs)]
        mean = sum(diffs) / runs
        sd = (sum((d - mean) ** 2 for d in diffs) / max(1, runs - 1)) ** 0.5
        if mean < sd / (runs ** 0.5) * 1.0 or mean < 150:
            best = nat
    mv = dict(live[best])
    if mv["kind"] == "natural":
        nd = describe_natural(base, pid) if base.cur()["id"] == pid else dict(kind="wait", tile=None)
        if nd:
            mv = nd
    second = sorted((v for i, v in avg.items() if i != best), reverse=True)
    return dict(kind=mv["kind"], tile=mv.get("tile"), gain=int(avg[best] - second[0]) if second else 0, runs=runs,
                tried=len(live), rounds=HORIZON_ROUNDS)
