"""Game rules for 2-6 players. No UI, no networking: the server calls Game.act()."""
import random

from .board import TILES, GROUPS, N, JAIL_POS, STATION_RENT, AIRPORT_RENT_PER_POINT, MAX_HOUSES, HOTEL
from .cards import LUCK, FORTUNE
from . import texts

MIN_PLAYERS, MAX_PLAYERS = 2, 6
START_CASH, GO_SALARY, JAIL_FINE = 15000, 750, 500
AUCTION_START, AUCTION_STEP = 100, 100         # lowest opening bid / lowest raise in an auction
AUCTION_ACTIONS = {"bid", "pass_bid", "mortgage", "sell", "leave"}     # all that is allowed while an auction runs (mortgage / sell = raise cash)
TOKEN_COLORS = ["#D32F2F", "#2536B5", "#2E7D32", "#F2BE16", "#7B1FA2", "#F57C00",      # red, blue, green, yellow, purple, orange
                "#5DE02A", "#EC6C9C", "#1A8AA0"]                                          # lime, pink, teal (extra choices)


class GameError(Exception):
    """Illegal move. `key` + `params` let every app show the message in the player's language (see texts.ERR);
    str(error) is the Hindi text, kept for old callers / tests."""

    def __init__(self, key, **params):
        self.key, self.params = key, params
        super().__init__(texts.err_text("hi", key, params, fallback=key))


class Game:
    def __init__(self, players, seed=None, colors=None, auction=True):
        """players: list of (player_id, name). colors: optional {player_id: "#RRGGBB"} chosen in the lobby.
        auction: False = a land that is not bought stays unowned (no auctions in this game)."""
        if not MIN_PLAYERS <= len(players) <= MAX_PLAYERS:
            raise GameError("need_players", min=MIN_PLAYERS, max=MAX_PLAYERS)
        self.rng = random.Random(seed)
        self.players = [dict(id=pid, name=name, money=START_CASH, pos=0, in_jail=False,
                             jail_turns=0, cards=0, bankrupt=False, left=False, color=(colors or {}).get(pid) or TOKEN_COLORS[i])
                        for i, (pid, name) in enumerate(players)]
        self.props = {}            # tile index -> {owner, houses, mortgaged}
        self.turn = 0
        self.phase = "roll"        # "roll" -> "act"
        self.dice = [0, 0]
        self.roll_seq = 0                      # +1 on every roll, so clients can animate even when the dice repeat
        self.doubles = 0
        self.extra = False         # unused now: doubles no longer give an extra turn (kept so saved games still load)
        self.pending_buy = None
        self.pending_draw = None               # "luck" / "fortune": the player landed there and must roll the dice for the card
        self.trade = None
        self.auction_on = bool(auction)        # room / game setting: are auctions played at all?
        self.auction = None                    # a declined property is sold to the highest bidder, see do_skip()
        self.winner = None
        self.creditor = None
        self.log = []
        self.last_card = None                  # last Luck / Fortune card drawn (shown in the board centre)
        self.events, self.event_seq = [], 0   # structured events, shown to ALL players as banners
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
        if t["type"] == "airport":
            return AIRPORT_RENT_PER_POINT * total       # `total` = the visitor's extra roll, see airport_rent()
        n = sum(1 for i in GROUPS[t["group"]] if self.owner_of(i) == owner)    # stations / utilities: own set only
        return STATION_RENT * n

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
        if k in ("property", "station", "utility", "airport"):
            s = self.props.get(idx)
            if s is None:
                self.pending_buy = idx
            elif s["owner"] != p["id"] and not s["mortgaged"] and k == "airport":
                self.pending_draw = "airport"        # the visitor must roll the dice again: total x 100 is the rent
            elif s["owner"] != p["id"] and not s["mortgaged"]:
                owner = self.get(s["owner"])
                r = self.rent(idx, sum(self.dice))
                self.pay(p, r, owner)
                self.say("rent", "rent", (p["id"], owner["id"]), name=p["id"], owner=owner["id"], tile=idx, amt=r)
        elif k == "tax":
            self.pay(p, t["amount"])
            self.say("tax", name=p["id"], amt=t["amount"])
        elif k in ("luck", "fortune"):
            self.pending_draw = k                # the player now chooses to roll the dice (do_roll_card)
            self.last_card = None                # clear the highlight of the previous card on the board centre
        elif k == "gotojail":
            self.go_to_jail(p)
        # START and JAIL (just visiting): nothing happens

    def draw(self, p, kind):
        """Luck / Fortune tile: the player's two dice are rolled once more and the total (2..12) picks the line of the
        card, exactly like the table printed on the board. Called from do_roll_card()."""
        cards = LUCK if kind == "luck" else FORTUNE
        self.dice = [self.rng.randint(1, 6), self.rng.randint(1, 6)]
        self.roll_seq += 1                                   # clients tumble the dice again for this roll
        roll = sum(self.dice)
        ci = roll - 2
        c = cards[ci]
        self.last_card = dict(deck=kind, ci=ci, roll=roll, pid=p["id"], text=c["text"], who=p["name"])   # text / who: Hindi fallback
        self.say("card", "card", (p["id"],), name=p["id"], deck=kind, ci=ci, roll=roll)
        k, v = c["kind"], c["value"]
        if k == "money":
            if v < 0:
                self.pay(p, -v)
            else:
                p["money"] += v
        elif k == "jail":
            self.go_to_jail(p)
        elif k == "jail_card":
            p["cards"] += v                      # kept until used (do_use_card) or traded
        elif k == "collect_each":
            for o in self.alive():
                if o is not p:
                    self.pay(o, v, p)
            self.creditor = None
        elif k == "collect_one":
            others = [o for o in self.alive() if o is not p]
            if others:
                self.pay(max(others, key=lambda o: o["money"]), v, p)
                self.creditor = None
        elif k == "repairs":
            per_house, per_hotel = v
            cost = 0
            for i in self.owned(p["id"]):
                n = self.props[i]["houses"]
                cost += per_hotel if n >= HOTEL else per_house * n
            if cost:
                self.pay(p, cost)
        elif k == "holiday":
            self.pay(p, v)                       # there is no Resort tile any more: the holiday is only paid for

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
        if self.auction and action not in AUCTION_ACTIONS:
            raise GameError("auction_busy")
        fn(p, **kw)

    def _my_turn(self, p):
        if self.cur() is not p:
            raise GameError("not_turn")

    def do_roll(self, p):
        self._my_turn(p)
        if self.phase != "roll":
            raise GameError("already_rolled")
        self.pending_buy = None
        self.pending_draw = None
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
        # doubles give NO extra turn (one roll per turn); a double only frees a player from jail (above)
        old = p["pos"]
        newpos = (old + total) % N
        if newpos < old:
            p["money"] += GO_SALARY
            self.say("go", name=p["id"], amt=GO_SALARY)
        p["pos"] = newpos
        self.land(p)

    def do_roll_card(self, p):
        """The player on a Luck / Fortune tile rolls the dice; the total decides the line that applies."""
        self._my_turn(p)
        kind = self.pending_draw
        if kind is None:
            raise GameError("no_card_roll")
        self.pending_draw = None
        if kind == "airport":
            return self.airport_rent(p)
        self.draw(p, kind)

    def airport_rent(self, p):
        """The player on somebody else's Airport rolls both dice again; the total x 100 is the rent. (Doubles here give
        no extra turn.) Nothing is paid if the Airport was mortgaged or changed hands in the meantime."""
        idx = p["pos"]
        s = self.props.get(idx)
        if TILES[idx]["type"] != "airport" or s is None or s["owner"] == p["id"] or s["mortgaged"]:
            return
        owner = self.get(s["owner"])
        self.dice = [self.rng.randint(1, 6), self.rng.randint(1, 6)]
        self.roll_seq += 1                                   # clients tumble the dice again for this roll
        self.say("roll", name=p["id"], d1=self.dice[0], d2=self.dice[1])
        r = self.rent(idx, sum(self.dice))
        self.pay(p, r, owner)
        self.say("rent", "rent", (p["id"], owner["id"]), name=p["id"], owner=owner["id"], tile=idx, amt=r)

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

    # ---- auction: the player on an unowned property declines to buy it (Skip, or End turn) ----
    def do_skip(self, p):
        """Decline to buy at the printed price. The property is auctioned: the other players (and the decliner) bid in
        turn, clockwise, each one raises the bid or passes. The last bidder left pays his bid and gets the property;
        if everybody passes it stays for sale. Players who cannot afford the next bid pass automatically."""
        self._my_turn(p)
        idx = self.pending_buy
        if idx is None:
            raise GameError("nothing_to_buy")
        self.pending_buy = None
        if not self.auction_on:                   # auctions are switched off for this game: the land just stays unowned
            self.say("no_buy", name=p["id"], tile=idx)
            return
        n = len(self.players)
        order = [self.players[(self.turn + k) % n]["id"] for k in range(1, n + 1)]      # decliner bids last
        order = [pid for pid in order if not self.get(pid)["bankrupt"]]
        self.auction = dict(tile=idx, bid=0, leader=None, order=order, passed=[], bidder=None)
        self.say("auction_start", "auction", (p["id"],), name=p["id"], tile=idx, price=TILES[idx]["price"])
        self._auction_next(None)

    def auction_min(self):
        """Lowest bid allowed right now."""
        a = self.auction
        return a["bid"] + AUCTION_STEP if a["bid"] else AUCTION_START

    def _auction_next(self, after):
        """Pick who bids next (the player after `after` in the bidding order); end the auction when nobody is left."""
        a = self.auction
        order, need = a["order"], self.auction_min()
        for pid in order:                                    # cannot pay the next bid: out, without being asked
            if pid not in a["passed"] and pid != a["leader"] and self.get(pid)["money"] < need:
                a["passed"].append(pid)
        active = [pid for pid in order if pid not in a["passed"] and pid != a["leader"]]
        if not active:
            return self._auction_end()
        start = 0 if after is None else order.index(after) + 1
        for k in range(len(order)):
            pid = order[(start + k) % len(order)]
            if pid in active:
                a["bidder"] = pid
                return

    def _auction_end(self):
        a, self.auction = self.auction, None
        idx = a["tile"]
        if a["leader"]:
            w = self.get(a["leader"])
            w["money"] -= a["bid"]
            self.props[idx] = dict(owner=w["id"], houses=0, mortgaged=False)
            self.say("auction_won", "buy", (w["id"],), name=w["id"], tile=idx, price=a["bid"])
        else:
            self.say("auction_none", tile=idx)

    def _bidder(self, p):
        if not self.auction:
            raise GameError("no_auction")
        if self.auction["bidder"] != p["id"]:
            raise GameError("not_bidder")
        return self.auction

    def do_bid(self, p, amount):
        a = self._bidder(p)
        if not isinstance(amount, int) or isinstance(amount, bool):
            raise GameError("bad_bid")
        low = self.auction_min()
        if amount < low:
            raise GameError("bid_low", min=low)
        if amount > p["money"]:
            raise GameError("poor")
        a["bid"], a["leader"] = amount, p["id"]
        self.say("auction_bid", name=p["id"], tile=a["tile"], amt=amount)
        self._auction_next(p["id"])

    def do_pass_bid(self, p):
        a = self._bidder(p)
        a["passed"].append(p["id"])
        self.say("auction_pass", name=p["id"])
        self._auction_next(p["id"])

    def do_end_turn(self, p):
        self._my_turn(p)
        if self.phase != "act":
            raise GameError("roll_first")
        if self.pending_draw:
            raise GameError("card_roll_first")
        if self.pending_buy is not None and self.auction_on:    # ending the turn without buying = declining: auction
            return self.do_skip(p)
        if p["money"] < 0:
            raise GameError("in_debt")
        self._advance()

    def _advance(self):
        self.pending_buy = None
        self.pending_draw = None
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
        if s["houses"] >= HOTEL:
            raise GameError("hotel_exists")
        if s["houses"] > min(g["houses"] for g in grp):
            raise GameError("build_even")
        if p["money"] < t["house_cost"]:
            raise GameError("poor")
        p["money"] -= t["house_cost"]
        # 3 houses, then the hotel (a saved game from before may still have 4 houses: that also goes to the hotel)
        s["houses"] = HOTEL if s["houses"] >= MAX_HOUSES else s["houses"] + 1
        if s["houses"] == HOTEL:
            self.say("build_hotel", "build", (p["id"],), name=p["id"], tile=tile)
        else:
            self.say("build", "build", (p["id"],), name=p["id"], tile=tile, n=s["houses"])

    def do_sell(self, p, tile):
        t, s = self._own(p, tile)
        if s["houses"] == 0:
            raise GameError("no_house")
        if s["houses"] < max(g["houses"] for g in self._group_states(t["group"])):
            raise GameError("sell_even")
        was_hotel = s["houses"] == HOTEL
        s["houses"] = MAX_HOUSES if was_hotel else s["houses"] - 1      # selling the hotel leaves 3 houses
        p["money"] += t["house_cost"] // 2
        self.say("sell_hotel" if was_hotel else "sell", "sell", (p["id"],), name=p["id"], tile=tile)

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
        if self.trade and p["id"] in (self.trade["frm"], self.trade["to"]):
            self.trade = None                                # a deal with a player who goes bankrupt is off
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

    def do_leave(self, p):
        """The player exits the running game on purpose (any time, even when it is not his turn). He is out like a
        bankrupt player, tagged `left`, but his lands go back to the bank (nobody inherits them). If only one player
        is still in, that player wins."""
        if self.trade and p["id"] in (self.trade["frm"], self.trade["to"]):
            self.trade = None
        for i in self.owned(p["id"]):
            del self.props[i]
        a = self.auction
        if a:                                                # he drops out of a running auction
            if a["leader"] == p["id"]:
                a["leader"], a["bid"] = None, 0
            if p["id"] not in a["passed"]:
                a["passed"].append(p["id"])
        p.update(bankrupt=True, left=True, money=0, cards=0)
        self.creditor = None
        self.say("left", "bankrupt", (p["id"],), name=p["id"])
        left = self.alive()
        if len(left) == 1:
            self.auction = None
            self.winner = left[0]["id"]
            self.say("win", "win", (left[0]["id"],), name=left[0]["id"])
            return
        if self.auction and a["bidder"] == p["id"]:
            self._auction_next(p["id"])
        if self.cur() is p:
            self.extra = False
            self._advance()

    # ---- trade ----
    def _check_side(self, owner, tiles, cash, cards=0):
        if cash < 0 or cash > owner["money"]:
            raise GameError("owner_poor", name=owner["name"])
        if cards < 0 or cards > owner["cards"]:
            raise GameError("trade_no_card", name=owner["name"])
        if len(set(tiles)) != len(tiles):
            raise GameError("bad_move")
        for i in tiles:
            t, s = self._own(owner, i)
            if t["type"] == "property" and any(g["houses"] for g in self._group_states(t["group"])):
                raise GameError("trade_houses")

    def do_propose_trade(self, p, to, give_tiles=(), give_cash=0, get_tiles=(), get_cash=0, give_cards=0, get_cards=0):
        other = self.get(to)
        if other is p or other["bankrupt"]:
            raise GameError("wrong_player")
        if self.trade:
            raise GameError("trade_pending")
        for v in (give_cash, get_cash, give_cards, get_cards):
            if not isinstance(v, int) or isinstance(v, bool):
                raise GameError("bad_move")
        give_tiles, get_tiles = [int(i) for i in give_tiles], [int(i) for i in get_tiles]
        if not (give_tiles or get_tiles or give_cash or get_cash or give_cards or get_cards):
            raise GameError("trade_empty")
        self._check_side(p, give_tiles, give_cash, give_cards)
        self._check_side(other, get_tiles, get_cash, get_cards)
        self.trade = dict(frm=p["id"], to=to, give_tiles=give_tiles, give_cash=give_cash, give_cards=give_cards,
                          get_tiles=get_tiles, get_cash=get_cash, get_cards=get_cards)
        self.say("trade_offer", name=p["id"], other=other["id"])

    def do_accept_trade(self, p):
        tr = self.trade
        if not tr or tr["to"] != p["id"]:
            raise GameError("no_trade_for_you")
        a = self.get(tr["frm"])
        gc, tc = tr.get("give_cards", 0), tr.get("get_cards", 0)        # saves from before cards could be traded have none
        self._check_side(a, tr["give_tiles"], tr["give_cash"], gc)
        self._check_side(p, tr["get_tiles"], tr["get_cash"], tc)
        for i in tr["give_tiles"]:
            self.props[i]["owner"] = p["id"]
        for i in tr["get_tiles"]:
            self.props[i]["owner"] = a["id"]
        a["money"] += tr["get_cash"] - tr["give_cash"]
        p["money"] += tr["give_cash"] - tr["get_cash"]
        a["cards"] += tc - gc
        p["cards"] += gc - tc
        self.trade = None
        self.say("trade_done", "trade", (a["id"], p["id"]), p1=a["id"], p2=p["id"])

    def do_reject_trade(self, p):
        tr = self.trade
        if not tr or p["id"] not in (tr["to"], tr["frm"]):
            raise GameError("no_trade")
        self.trade = None
        self.say("trade_cancel")

    # ---------- state for clients ----------
    # ---------- save / resume (computer games) ----------
    SAVE_VERSION = 2

    def to_dict(self):
        """Everything needed to continue this game later (JSON-safe), including the dice / card-shuffle generator, so a
        resumed game plays on exactly as the original would have."""
        rs = self.rng.getstate()
        return dict(v=self.SAVE_VERSION, players=self.players, props={str(k): v for k, v in self.props.items()},
                    turn=self.turn, phase=self.phase, dice=self.dice, roll_seq=self.roll_seq, doubles=self.doubles,
                    extra=self.extra, pending_buy=self.pending_buy, pending_draw=self.pending_draw, trade=self.trade, winner=self.winner,
                    auction=self.auction, auction_on=self.auction_on, creditor=self.creditor, log=self.log, last_card=self.last_card, events=self.events,
                    event_seq=self.event_seq,
                    rng=[rs[0], list(rs[1]), rs[2]])

    @classmethod
    def from_dict(cls, d):
        """Rebuild a game from to_dict() data (after a JSON round trip). Raises ValueError if the data is unusable."""
        try:
            if d.get("v") != cls.SAVE_VERSION:
                raise ValueError("unknown save version")
            g = cls.__new__(cls)
            g.players = [dict(p) for p in d["players"]]
            if not MIN_PLAYERS <= len(g.players) <= MAX_PLAYERS:
                raise ValueError("bad player count")
            g.props = {int(k): dict(v) for k, v in d["props"].items()}
            g.turn = int(d["turn"])
            if not 0 <= g.turn < len(g.players):
                raise ValueError("bad turn")
            g.phase, g.dice, g.roll_seq, g.doubles = d["phase"], list(d["dice"]), d["roll_seq"], d["doubles"]
            g.extra, g.pending_buy, g.trade, g.winner = d["extra"], d["pending_buy"], d["trade"], d["winner"]
            g.pending_draw = d.get("pending_draw")              # saves from before this rule have none
            g.auction = d.get("auction")                        # same for the auction
            g.auction_on = d.get("auction_on", True)
            g.creditor, g.log, g.last_card = d["creditor"], list(d["log"]), d["last_card"]
            g.events, g.event_seq = list(d["events"]), d["event_seq"]
            rs = d["rng"]
            g.rng = random.Random()
            g.rng.setstate((rs[0], tuple(rs[1]), rs[2]))
            return g
        except (KeyError, TypeError, AttributeError) as e:
            raise ValueError(f"bad save data: {e}")

    def state(self):
        return dict(players=self.players, props={str(k): v for k, v in self.props.items()},
                    turn=self.cur()["id"], phase=self.phase, dice=self.dice, roll_seq=self.roll_seq,
                    pending_buy=self.pending_buy, pending_draw=self.pending_draw, trade=self.trade, auction=self.auction, auction_on=self.auction_on,
                    winner=self.winner, log=self.log[-12:], events=self.events[-8:], last_card=self.last_card)
