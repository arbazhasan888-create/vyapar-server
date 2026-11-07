"""Game rules for 2-6 players. No UI, no networking: the server calls Game.act()."""
import random

from .board import TILES, GROUPS, N
from .cards import CHANCE, CHEST
from . import texts

MIN_PLAYERS, MAX_PLAYERS = 2, 6
START_CASH, GO_SALARY, JAIL_FINE, JAIL_POS = 1500, 200, 50, 10
TOKEN_COLORS = ["#E53935", "#1E88E5", "#43A047", "#FDD835", "#8E24AA", "#FB8C00"]


class GameError(Exception):
    """Illegal move. `key` + `params` let every app show the message in the player's language (see texts.ERR);
    str(error) is the Hindi text, kept for old callers / tests."""

    def __init__(self, key, **params):
        self.key, self.params = key, params
        super().__init__(texts.err_text("hi", key, params, fallback=key))


class Game:
    def __init__(self, players, seed=None, colors=None):
        """players: list of (player_id, name). colors: optional {player_id: "#RRGGBB"} chosen in the lobby."""
        if not MIN_PLAYERS <= len(players) <= MAX_PLAYERS:
            raise GameError("need_players", min=MIN_PLAYERS, max=MAX_PLAYERS)
        self.rng = random.Random(seed)
        self.players = [dict(id=pid, name=name, money=START_CASH, pos=0, in_jail=False,
                             jail_turns=0, cards=0, bankrupt=False, color=(colors or {}).get(pid) or TOKEN_COLORS[i])
                        for i, (pid, name) in enumerate(players)]
        self.props = {}            # tile index -> {owner, houses, mortgaged}
        self.turn = 0
        self.phase = "roll"        # "roll" -> "act"
        self.dice = [0, 0]
        self.roll_seq = 0                      # +1 on every roll, so clients can animate even when the dice repeat
        self.doubles = 0
        self.extra = False         # rolled doubles: same player rolls again
        self.pending_buy = None
        self.trade = None
        self.winner = None
        self.creditor = None
        self.log = []
        self.last_card = None                  # last Chance / Fortune card drawn (shown in the board centre)
        self.events, self.event_seq = [], 0   # structured events, shown to ALL players as banners
        self.chance = list(range(len(CHANCE)))
        self.chest = list(range(len(CHEST)))
        self.rng.shuffle(self.chance)
        self.rng.shuffle(self.chest)
        self.say("start", name=self.cur()["id"])

    # ---------- helpers ----------
    def say(self, key, kind=None, who=(), **params):
        """Add to the log. The entry is {k: key, p: params, text: Hindi sentence}: apps rebuild the sentence in the
        player's language from k + p (see texts.LOG); `text` is only a fallback. With `kind`, also publish an event
        every player's app shows as a banner. Player parameters hold player ids, tile parameters tile indexes."""
        names = {p["id"]: p["name"] for p in self.players}
        entry = dict(k=key, p=params)
        entry["text"] = texts.log_text("hi", entry, names)
        self.log.append(entry)
        self.log = self.log[-30:]
        if kind:
            self.event_seq += 1
            self.events.append(dict(id=self.event_seq, kind=kind, k=key, p=params, text=entry["text"], who=list(who)))
            self.events = self.events[-12:]

    def cur(self):
        return self.players[self.turn]

    def get(self, pid):
        for p in self.players:
            if p["id"] == pid:
                return p
        raise GameError("no_player")

    def alive(self):
        return [p for p in self.players if not p["bankrupt"]]

    def owner_of(self, idx):
        return self.props.get(idx, {}).get("owner")

    def owned(self, pid):
        return [i for i, s in self.props.items() if s["owner"] == pid]

    def monopoly(self, pid, group):
        return all(self.owner_of(i) == pid for i in GROUPS[group])

    def pay(self, p, amount, to=None):
        p["money"] -= amount
        if to:
            to["money"] += amount
            self.creditor = to["id"]
        else:
            self.creditor = None

    def rent(self, idx, total):
        t, s = TILES[idx], self.props[idx]
        if s["mortgaged"]:
            return 0
        owner = s["owner"]
        if t["type"] == "property":
            if s["houses"]:
                return t["rents"][s["houses"]]
            return t["rents"][0] * (2 if self.monopoly(owner, t["group"]) else 1)
        n = sum(1 for i in GROUPS[t["group"]] if self.owner_of(i) == owner)
        if t["type"] == "station":
            return 25 * 2 ** (n - 1)
        return (10 if n == 2 else 4) * total

    # ---------- movement ----------
    def go_to_jail(self, p):
        p["pos"], p["in_jail"], p["jail_turns"] = JAIL_POS, True, 0
        self.extra = False
        self.say("jail", "jail", (p["id"],), name=p["id"])

    def move_to(self, p, pos, collect=True):
        if collect and pos < p["pos"]:
            p["money"] += GO_SALARY
            self.say("go", name=p["id"], amt=GO_SALARY)
        p["pos"] = pos
        self.land(p)

    def land(self, p):
        idx = p["pos"]
        t = TILES[idx]
        self.say("arrive", name=p["id"], tile=idx)
        k = t["type"]
        if k in ("property", "station", "utility"):
            s = self.props.get(idx)
            if s is None:
                self.pending_buy = idx
            elif s["owner"] != p["id"] and not s["mortgaged"]:
                owner = self.get(s["owner"])
                r = self.rent(idx, sum(self.dice))
                self.pay(p, r, owner)
                self.say("rent", "rent", (p["id"], owner["id"]), name=p["id"], owner=owner["id"], tile=idx, amt=r)
        elif k == "tax":
            self.pay(p, t["amount"])
            self.say("tax", name=p["id"], amt=t["amount"])
        elif k in ("chance", "chest"):
            self.draw(p, k)
        elif k == "gotojail":
            self.go_to_jail(p)

    def draw(self, p, kind):
        deck, cards = (self.chance, CHANCE) if kind == "chance" else (self.chest, CHEST)
        ci = deck.pop(0)
        deck.append(ci)
        c = cards[ci]
        self.last_card = dict(deck=kind, ci=ci, pid=p["id"], text=c["text"], who=p["name"])   # text / who: Hindi fallback
        self.say("card", "card", (p["id"],), name=p["id"], deck=kind, ci=ci)
        k, v = c["kind"], c["value"]
        if k == "jail_free":
            p["cards"] += 1
        elif k == "money":
            if v < 0:
                self.pay(p, -v)
            else:
                p["money"] += v
        elif k == "move_to":
            self.move_to(p, v)
        elif k == "move_rel":
            self.move_to(p, (p["pos"] + v) % N, collect=False)
        elif k == "jail":
            self.go_to_jail(p)
        elif k == "pay_each":
            for o in self.alive():
                if o is not p:
                    self.pay(p, v, o)
        elif k == "collect_each":
            for o in self.alive():
                if o is not p:
                    self.pay(o, v, p)

    # ---------- actions ----------
    def act(self, pid, action, **kw):
        if self.winner:
            raise GameError("game_over")
        p = self.get(pid)
        if p["bankrupt"]:
            raise GameError("you_bankrupt")
        fn = getattr(self, "do_" + action, None)
        if fn is None or action.startswith("_"):
            raise GameError("bad_move")
        fn(p, **kw)

    def _my_turn(self, p):
        if self.cur() is not p:
            raise GameError("not_turn")

    def do_roll(self, p):
        self._my_turn(p)
        if self.phase != "roll":
            raise GameError("already_rolled")
        self.pending_buy = None
        self.dice = [self.rng.randint(1, 6), self.rng.randint(1, 6)]
        self.roll_seq += 1
        total, dbl = sum(self.dice), self.dice[0] == self.dice[1]
        self.say("roll", name=p["id"], d1=self.dice[0], d2=self.dice[1])
        self.phase = "act"
        self.extra = False
        if p["in_jail"]:
            if dbl:
                p["in_jail"] = False
                self.say("jail_double", name=p["id"])
            else:
                p["jail_turns"] += 1
                if p["jail_turns"] < 3:
                    return
                self.pay(p, JAIL_FINE)
                p["in_jail"] = False
                self.say("jail_auto", amt=JAIL_FINE)
        elif dbl:
            self.doubles += 1
            if self.doubles == 3:
                self.doubles = 0
                self.go_to_jail(p)
                return
            self.extra = True
        old = p["pos"]
        newpos = (old + total) % N
        if newpos < old:
            p["money"] += GO_SALARY
            self.say("go", name=p["id"], amt=GO_SALARY)
        p["pos"] = newpos
        self.land(p)

    def do_buy(self, p):
        self._my_turn(p)
        idx = self.pending_buy
        if idx is None:
            raise GameError("nothing_to_buy")
        price = TILES[idx]["price"]
        if p["money"] < price:
            raise GameError("poor")
        p["money"] -= price
        self.props[idx] = dict(owner=p["id"], houses=0, mortgaged=False)
        self.pending_buy = None
        self.say("buy", "buy", (p["id"],), name=p["id"], tile=idx, price=price)

    def do_end_turn(self, p):
        self._my_turn(p)
        if self.phase != "act":
            raise GameError("roll_first")
        if p["money"] < 0:
            raise GameError("in_debt")
        self._advance()

    def _advance(self):
        self.pending_buy = None
        p = self.cur()
        if self.extra and not p["in_jail"] and not p["bankrupt"]:
            self.extra, self.phase = False, "roll"
            self.say("again", name=p["id"])
            return
        self.extra, self.doubles, self.phase = False, 0, "roll"
        for _ in range(len(self.players)):
            self.turn = (self.turn + 1) % len(self.players)
            if not self.cur()["bankrupt"]:
                break
        self.say("turn", name=self.cur()["id"])

    def do_pay_jail(self, p):
        self._my_turn(p)
        if not p["in_jail"] or self.phase != "roll":
            raise GameError("no_fine_now")
        if p["money"] < JAIL_FINE:
            raise GameError("poor")
        self.pay(p, JAIL_FINE)
        p["in_jail"] = False
        self.say("pay_jail", name=p["id"], amt=JAIL_FINE)

    def do_use_card(self, p):
        self._my_turn(p)
        if not p["in_jail"] or self.phase != "roll" or p["cards"] < 1:
            raise GameError("card_unusable")
        p["cards"] -= 1
        p["in_jail"] = False
        self.say("use_card", name=p["id"])

    # ---- property management (allowed any time for the owner) ----
    def _own(self, p, tile):
        s = self.props.get(tile)
        if s is None or s["owner"] != p["id"]:
            raise GameError("not_yours")
        return TILES[tile], s

    def _group_states(self, group):
        return [self.props[i] for i in GROUPS[group] if i in self.props]

    def do_build(self, p, tile):
        t, s = self._own(p, tile)
        if t["type"] != "property":
            raise GameError("no_build")
        if not self.monopoly(p["id"], t["group"]):
            raise GameError("need_group")
        grp = self._group_states(t["group"])
        if any(g["mortgaged"] for g in grp):
            raise GameError("mortgaged_group")
        if s["houses"] >= 5:
            raise GameError("hotel_exists")
        if s["houses"] > min(g["houses"] for g in grp):
            raise GameError("build_even")
        if p["money"] < t["house_cost"]:
            raise GameError("poor")
        p["money"] -= t["house_cost"]
        s["houses"] += 1
        self.say("build", "build", (p["id"],), name=p["id"], tile=tile, n=s["houses"])

    def do_sell(self, p, tile):
        t, s = self._own(p, tile)
        if s["houses"] == 0:
            raise GameError("no_house")
        if s["houses"] < max(g["houses"] for g in self._group_states(t["group"])):
            raise GameError("sell_even")
        s["houses"] -= 1
        p["money"] += t["house_cost"] // 2
        self.say("sell", "sell", (p["id"],), name=p["id"], tile=tile)

    def do_mortgage(self, p, tile):
        t, s = self._own(p, tile)
        if s["mortgaged"]:
            raise GameError("already_mortgaged")
        if t["type"] == "property" and any(g["houses"] for g in self._group_states(t["group"])):
            raise GameError("sell_group_first")
        s["mortgaged"] = True
        p["money"] += t["price"] // 2
        self.say("mortgage", "mortgage", (p["id"],), name=p["id"], tile=tile)

    def do_redeem(self, p, tile):
        t, s = self._own(p, tile)
        if not s["mortgaged"]:
            raise GameError("not_mortgaged")
        cost = int(t["price"] // 2 * 1.1)
        if p["money"] < cost:
            raise GameError("poor")
        p["money"] -= cost
        s["mortgaged"] = False
        self.say("redeem", "redeem", (p["id"],), name=p["id"], tile=tile)

    def do_bankrupt(self, p):
        if p["money"] >= 0:
            raise GameError("not_in_debt")
        heir = self.get(self.creditor) if self.creditor and self.creditor != p["id"] else None
        for i in self.owned(p["id"]):
            s = self.props[i]
            if heir and not heir["bankrupt"]:
                s["owner"], s["houses"] = heir["id"], 0
            else:
                del self.props[i]
        if heir:
            heir["money"] += max(p["money"], 0)
            heir["cards"] += p["cards"]
        p.update(bankrupt=True, money=0, cards=0)
        self.say("bankrupt", "bankrupt", (p["id"],), name=p["id"])
        left = self.alive()
        if len(left) == 1:
            self.winner = left[0]["id"]
            self.say("win", "win", (left[0]["id"],), name=left[0]["id"])
            return
        if self.cur() is p:
            self._advance()

    # ---- trade ----
    def _check_side(self, owner, tiles, cash):
        if cash < 0 or cash > owner["money"]:
            raise GameError("owner_poor", name=owner["name"])
        for i in tiles:
            t, s = self._own(owner, i)
            if t["type"] == "property" and any(g["houses"] for g in self._group_states(t["group"])):
                raise GameError("trade_houses")

    def do_propose_trade(self, p, to, give_tiles=(), give_cash=0, get_tiles=(), get_cash=0):
        other = self.get(to)
        if other is p or other["bankrupt"]:
            raise GameError("wrong_player")
        if self.trade:
            raise GameError("trade_pending")
        give_tiles, get_tiles = list(give_tiles), list(get_tiles)
        self._check_side(p, give_tiles, give_cash)
        self._check_side(other, get_tiles, get_cash)
        self.trade = dict(frm=p["id"], to=to, give_tiles=give_tiles, give_cash=give_cash,
                          get_tiles=get_tiles, get_cash=get_cash)
        self.say("trade_offer", name=p["id"], other=other["id"])

    def do_accept_trade(self, p):
        tr = self.trade
        if not tr or tr["to"] != p["id"]:
            raise GameError("no_trade_for_you")
        a = self.get(tr["frm"])
        self._check_side(a, tr["give_tiles"], tr["give_cash"])
        self._check_side(p, tr["get_tiles"], tr["get_cash"])
        for i in tr["give_tiles"]:
            self.props[i]["owner"] = p["id"]
        for i in tr["get_tiles"]:
            self.props[i]["owner"] = a["id"]
        a["money"] += tr["get_cash"] - tr["give_cash"]
        p["money"] += tr["give_cash"] - tr["get_cash"]
        self.trade = None
        self.say("trade_done", "trade", (a["id"], p["id"]), p1=a["id"], p2=p["id"])

    def do_reject_trade(self, p):
        tr = self.trade
        if not tr or p["id"] not in (tr["to"], tr["frm"]):
            raise GameError("no_trade")
        self.trade = None
        self.say("trade_cancel")

    # ---------- state for clients ----------
    def state(self):
        return dict(players=self.players, props={str(k): v for k, v in self.props.items()},
                    turn=self.cur()["id"], phase=self.phase, dice=self.dice, roll_seq=self.roll_seq,
                    pending_buy=self.pending_buy, trade=self.trade, winner=self.winner,
                    log=self.log[-12:], events=self.events[-8:], last_card=self.last_card)
