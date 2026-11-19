"""Smart, property-set-aware hints (the Hint button). Pure Python, no UI, no network, never changes the game state.

    get_hints(game_state, player) -> [ {priority, type, text, properties_involved, ...}, ... ]   (best first, at most 3)

`game_state` is the plain dict the clients already have (Game.state()); `player` is the player id (or the player dict).
Every hint is a dict with
    priority            1..7, lower = more important (see PRIORITIES below)
    type                "buy_complete" | "trade_complete" | "foothold" | "buy_target" | "block" | "build" | "transport"
    text                a short English sentence (names + colour groups), ready to show as it is
    properties_involved list of tile indexes the hint is about
    key, params         the same sentence as a translation key + values, so the app can show it in Hindi / English
                        (params: tile = one tile, X_tiles = a list of tiles, player = a player id, group, how, numbers)
    trade               None, or a ready-made offer {to, give_tiles, give_cash, get_tiles, get_cash} the app can pre-fill
                        into its Trade window ("Propose trade")

Priority order
    1 buy_complete    I own all but one land of a colour set and the last one is unowned
    2 trade_complete  I own all but one land and another player owns the last: what to offer, plus a cash top-up
    3 foothold        I own a first land of a set (targets to aim for; sets split between many players are flagged hard)
    4 buy_target      the best unowned lands: set closeness, rent vs price, how often players land there, affordability
    5 block           an opponent owns all but one land of a set and the last one is unowned: take it first
    6 build           I own a full set: build houses evenly (or redeem a mortgaged land that blocks building)
    7 transport       stations / utilities: the more of them one player owns, the more rent each pays

Rules every hint obeys: never anything the game would refuse, never a buy / offer that leaves less than MIN_BUFFER cash,
mortgaged lands still count as owned (but block building), bankrupt / left players own nothing, computer players are
treated like any other owner (their trade answers are estimated with the same value model the computer uses).
Works for groups of any size (the printed board has 3-land sets; a 2-land set simply has no "foothold" step).
"""
from .board import TILES, GROUPS, STATION_RENT, HOTEL
from .value import trade_value, BUY_CUSHION, BUILD_CUSHION
from .bot import LEVEL_CFG, DEFAULT_LEVEL

MIN_BUFFER = 1000            # cash that must stay after any buy / trade offer / redeem we suggest
SAFE_RESERVE = BUY_CUSHION   # cash that should stay after an ordinary (not set-completing) buy
BUILD_RESERVE = BUILD_CUSHION
MAX_HINTS = 3
TRADE_CASH_CAP = 1.6         # never offer more than this x the price of the land we want (same cap the computer uses)
BOT_CASH_CAP = 3.0           # a computer owner values a land that completes OUR set very highly (2.5x), so allow more
AUCTION_MIN_BID = 100

PRIORITIES = dict(buy_complete=1, trade_complete=2, foothold=3, buy_target=4, block=5, build=6, transport=7)

# How often tokens land on each set (orange / red are the strong ones: they come right after Jail, the most visited exit).
LANDING = dict(orange=1.30, red=1.25, yellow=1.10, cyan=1.00, purple=1.00, blue=0.95, brown=0.80,
               station=1.00, utility=0.70, airport=0.80)
_LAND_MAX = max(LANDING.values())

GROUP_EN = dict(blue="dark blue")                    # every other group is shown under its own key ("orange", "station" ...)
HOW_EN = dict(mortgage="mortgage", sell="sell a house on", mix="mortgage or sell houses on")

TEXT_EN = dict(
    hs_set_buy_now="Buy {name} now (₹{price})! It completes your {group} set, so you can start building.",
    hs_set_buy="Finish your {group} set ({have} of {total}): {name} (₹{price}) is the last one. You can afford it.",
    hs_set_bid="{name} is up for auction. Bid up to ₹{limit} to finish your {group} set.",
    hs_set_raise="Finish your {group} set: {name} costs ₹{price}, but you'd be left with too little cash. "
                 "Raise ₹{need} first: {how} {raise}.",
    hs_set_poor="{name} would finish your {group} set (₹{price}), but you can't safely afford it yet. Build up cash first.",
    hs_trade_both="{who} owns {name}, the last tile of your {group} set. Offer {offer} plus ₹{cash} for it.",
    hs_trade_tile="{who} owns {name}, the last tile of your {group} set. Offer {offer} for it.",
    hs_trade_cash="{who} owns {name}, the last tile of your {group} set. Offer ₹{cash} for it.",
    hs_trade_raise="{who} owns {name}, the last tile of your {group} set. A fair offer is about ₹{cash}; "
                   "raise ₹{need} first: {how} {raise}.",
    hs_foot_easy="You own {have} of {total} {group}. Aim for {targets} to build a set.",
    hs_foot_mixed="You own {have} of {total} {group}. Aim for {targets}; {who} holds another, so a trade may be needed.",
    hs_foot_hard="{group} is split among {count} players, so it's hard to complete. Don't pay extra for it.",
    hs_targets="Good lands to buy when you reach them: {targets}.",
    hs_block_now="Buy {name} now (₹{price}) to block {who}'s {group} set ({have} of {total}).",
    hs_block="Block {who}: they own {have} of {total} {group}. Grab {name} (₹{price}) before they do.",
    hs_block_bid="{who} owns {have} of {total} {group}. Win the auction for {name} (bid up to ₹{limit}) to block them.",
    hs_build="Build a house on {name} ({group}) for ₹{cost}. Keep houses even across the set.",
    hs_build_redeem="Redeem {name} ({group}) for ₹{cost}: you can't build while a land of the set is mortgaged.",
    hs_build_save="You own all of {group}. Save ₹{need} more, then build evenly (₹{cost} per house).",
    hs_transport="Pick up {name} (₹{price}): you'd own {next} of {total} {group} lands, and rent on each rises to ₹{rent}.",
)


# ----------------------------------------------------------------------------------------------------------------- helpers
def _groups_of(tiles):
    g = {}
    for i, t in enumerate(tiles):
        if t.get("group"):
            g.setdefault(t["group"], []).append(i)
    return g


def is_bot(pid):
    """Computer players have ids like 'bot1' (the same rule the app uses to name them)."""
    s = str(pid)
    return s.startswith("bot") and s[3:].isdigit()


def _name(T, i):
    return T[i].get("en") or T[i].get("name") or str(i)


def _group_en(g):
    return GROUP_EN.get(g, g)


def _label(T, i):
    return f"{_name(T, i)} ({_group_en(T[i].get('group'))})"


def _expand_en(params, T, names):
    """Fill values for TEXT_EN from a hint's params (the app does the same with its own language)."""
    kw = {}
    if "tile" in params:
        kw["name"] = _name(T, params["tile"])
        kw["group"] = _group_en(T[params["tile"]].get("group"))
    for k, v in params.items():
        if k == "tile":
            continue
        if k.endswith("_tiles"):
            kw[k[:-6]] = ", ".join(_label(T, i) for i in v)
        elif k == "player":
            kw["who"] = names.get(v, str(v))
        elif k == "group":
            kw["group"] = _group_en(v)
        elif k == "how":
            kw["how"] = HOW_EN[v]
        else:
            kw[k] = v
    return kw


class _Ctx:
    """Everything the hint rules need, read once from the state dict."""

    def __init__(self, st, me, T, G, bot_level=DEFAULT_LEVEL):
        self.st, self.me, self.T, self.G = st, me, T, G
        self.bot_level = bot_level if bot_level in LEVEL_CFG else DEFAULT_LEVEL
        self.pid, self.money = me["id"], me["money"]
        self.players = st.get("players", [])
        self.live = {p["id"]: p for p in self.players if not p.get("bankrupt") and not p.get("left")}
        self.names = {p["id"]: p.get("name", str(p["id"])) for p in self.players}
        self.props_raw = st.get("props", {})
        self.props = {int(k): v for k, v in self.props_raw.items()}
        self.my_turn = st.get("turn") == self.pid
        self.pending = st.get("pending_buy") if self.my_turn else None
        auc = st.get("auction")
        self.auction_tile = auc.get("tile") if auc else None
        self.can_trade = not st.get("trade") and not auc
        self.prop_groups = [g for g, idxs in G.items() if T[idxs[0]].get("type") == "property"]

    def owner(self, i):
        s = self.props.get(i)
        o = s.get("owner") if s else None
        return o if o in self.live else None

    def houses(self, i):
        return (self.props.get(i) or {}).get("houses") or 0

    def mortgaged(self, i):
        return bool((self.props.get(i) or {}).get("mortgaged"))

    def analyse(self, g):
        idxs = self.G[g]
        mine = [i for i in idxs if self.owner(i) == self.pid]
        free = [i for i in idxs if self.owner(i) is None]
        others = {}
        for i in idxs:
            o = self.owner(i)
            if o is not None and o != self.pid:
                others.setdefault(o, []).append(i)
        return dict(group=g, n=len(idxs), mine=mine, free=free, others=others)

    def protected_groups(self):
        """Groups the player is building (owns all but one land or more): never offered away / mortgaged."""
        out = set()
        for g, idxs in self.G.items():
            n = len(idxs)
            if n >= 2 and sum(1 for i in idxs if self.owner(i) == self.pid) >= n - 1:
                out.add(g)
        return out

    def group_has_houses(self, g):
        return any(self.houses(j) for j in self.G[g])


def _hint(ctx, type_, key, params, tiles, trade=None, hard=False):
    text = TEXT_EN[key].format(**_expand_en(params, ctx.T, ctx.names))
    return dict(priority=PRIORITIES[type_], type=type_, text=text, properties_involved=list(tiles), key=key,
                params=params, trade=trade, _hard=hard)


# --------------------------------------------------------------------------------------------- raising cash (legal ways only)
def _raise_plan(ctx, need):
    """Lands to mortgage / houses to sell to raise `need` cash without breaking a set the player is building.
    Returns [dict(kind "mortgage"|"sell", tile, cash)] (at most 3) or None when that is not possible."""
    T, G = ctx.T, ctx.G
    keep = ctx.protected_groups()
    src = []
    for i, s in ctx.props.items():
        if s.get("owner") != ctx.pid:
            continue
        tl, g = T[i], T[i].get("group")
        if tl.get("type") == "property" and ctx.group_has_houses(g):
            mx = max(ctx.houses(j) for j in G[g])
            if ctx.houses(i) and ctx.houses(i) == mx:               # houses are sold evenly: from the tallest land first
                src.append(dict(kind="sell", tile=i, cash=tl["house_cost"] // 2, rank=1))
            continue
        if s.get("mortgaged") or g in keep:
            continue
        src.append(dict(kind="mortgage", tile=i, cash=tl["price"] // 2, rank=0))
    for rank in (0, 1, None):                                          # prefer mortgaging free lands, then selling houses
        pool = [s for s in src if rank is None or s["rank"] == rank]
        single = sorted((s for s in pool if s["cash"] >= need), key=lambda s: s["cash"])
        if single:
            return [single[0]]
        chosen, total = [], 0
        for s in sorted(pool, key=lambda s: (-s["cash"], s["tile"])):
            chosen.append(s)
            total += s["cash"]
            if total >= need:
                if len(chosen) <= 3:
                    return chosen
                break
    return None


def _raise_params(plan):
    kinds = {s["kind"] for s in plan}
    return dict(how=kinds.pop() if len(kinds) == 1 else "mix", raise_tiles=[s["tile"] for s in plan])


# --------------------------------------------------------------------------------------------------- 1. buy to complete a set
def _buy_complete(ctx):
    out = []
    for g in ctx.prop_groups:
        a = ctx.analyse(g)
        if a["n"] < 2 or len(a["mine"]) != a["n"] - 1 or len(a["free"]) != 1:
            continue
        idx = a["free"][0]
        price = ctx.T[idx]["price"]
        base = dict(tile=idx, price=price, have=len(a["mine"]), total=a["n"])
        if ctx.auction_tile == idx:                                    # the land is being auctioned right now
            limit = (ctx.money - MIN_BUFFER) // 100 * 100
            if limit >= AUCTION_MIN_BID:
                out.append(_hint(ctx, "buy_complete", "hs_set_bid", dict(tile=idx, limit=limit), [idx]))
            continue
        if ctx.money - price >= MIN_BUFFER:
            key = "hs_set_buy_now" if ctx.pending == idx else "hs_set_buy"
            out.append(_hint(ctx, "buy_complete", key, base, [idx]))
            continue
        need = price + MIN_BUFFER - ctx.money
        plan = _raise_plan(ctx, need)
        if plan:
            out.append(_hint(ctx, "buy_complete", "hs_set_raise", dict(base, need=need, **_raise_params(plan)),
                             [idx] + [s["tile"] for s in plan]))
        else:
            out.append(_hint(ctx, "buy_complete", "hs_set_poor", base, [idx]))
    return out


# ------------------------------------------------------------------------------------------ 2. trade to complete a set
def _spare_tiles(ctx, x):
    """My lands I can offer player x: not part of a set I am building, no houses, and not the land that would hand x a
    full set. Returns [(tile, penalty)]; penalty > 0 when the land would leave x one short of a set."""
    T, G = ctx.T, ctx.G
    keep = ctx.protected_groups()
    out = []
    for i, s in ctx.props.items():
        if s.get("owner") != ctx.pid:
            continue
        g = T[i].get("group")
        if g in keep:
            continue
        if T[i].get("type") == "property" and ctx.group_has_houses(g):
            continue
        n = len(G[g])
        x_has = sum(1 for j in G[g] if ctx.owner(j) == x)
        if x_has + 1 >= n and n >= 2:                                  # would complete x's set
            continue
        penalty = T[i]["price"] * 0.5 if (n >= 3 and x_has + 1 == n - 1) else 0
        out.append((i, penalty))
    return out


def _bot_value(ctx, bot, idx, receiving):
    """What a land is worth to computer player `bot` (the same numbers game.bot uses to answer a trade offer)."""
    tl = ctx.T[idx]
    v = float(tl["price"]) * (0.6 if ctx.mortgaged(idx) else 1.0)
    if tl.get("type") == "property":
        rest = [j for j in ctx.G[tl["group"]] if j != idx]
        if receiving:
            if all(ctx.owner(j) == bot for j in rest):
                v *= 2.2
        else:
            if any(ctx.owner(j) == bot for j in rest):
                v *= 1.3
            if any(o != bot and all(ctx.owner(j) == o for j in rest) for o in ctx.live):   # the receiver gets a full set
                v *= 2.5
    return v


def _accepts(ctx, x, give_tiles, cash, target):
    """Will player x probably accept: he gets give_tiles + cash, hands over `target`?"""
    if is_bot(x):                                                      # computers: their own rule, at the top of their margin
        thr = LEVEL_CFG[ctx.bot_level]["trade"][1]
        gets = sum(_bot_value(ctx, x, i, True) for i in give_tiles) + cash
        gives = _bot_value(ctx, x, target, False)
        return gets >= gives * thr and ctx.live[x].get("money", 0) + cash >= 1000
    v = trade_value(ctx.props_raw, x, ctx.pid, get_tiles=give_tiles, get_cash=cash, give_tiles=[target])
    return bool(v) and v["level"] >= 1                                  # at least "good" for him


def _best_offer(ctx, x, target):
    """The cheapest (for me) legal offer x should accept for `target`: dict(give, cash, ok) or None.
    ok=False: nothing I can safely pay reaches a fair deal (the dict then holds the cash a fair deal needs)."""
    T = ctx.T
    cap = int(T[target]["price"] * (BOT_CASH_CAP if is_bot(x) else TRADE_CASH_CAP))
    room = max(0, ctx.money - MIN_BUFFER)
    best, fair = None, None
    for give, pen in [(None, 0)] + _spare_tiles(ctx, x):
        gt = [give] if give is not None else []
        lost = (T[give]["price"] * (0.6 if ctx.mortgaged(give) else 1.0) + pen) if give is not None else 0
        for cash in range(0, cap + 1, 100):
            if _accepts(ctx, x, gt, cash, target):
                if fair is None or cash < fair:
                    fair = cash
                if cash <= room and (best is None or cash + lost < best[0]):
                    best = (cash + lost, give, cash)
                break
    if best:
        return dict(give=best[1], cash=best[2], ok=True)
    return dict(give=None, cash=fair if fair is not None else cap, ok=False)


def _trade_complete(ctx):
    out = []
    T = ctx.T
    for g in ctx.prop_groups:
        a = ctx.analyse(g)
        if a["n"] < 2 or len(a["mine"]) != a["n"] - 1 or a["free"] or len(a["others"]) != 1:
            continue
        x, (target,) = next(iter(a["others"].items()))
        if ctx.live[x].get("money", 0) < 0:                            # the game refuses offers to a player who is in debt
            continue
        base = dict(tile=target, player=x, have=len(a["mine"]), total=a["n"])
        offer = _best_offer(ctx, x, target)
        if offer["ok"]:
            gt = [offer["give"]] if offer["give"] is not None else []
            cash = offer["cash"]
            if gt and cash:
                key, params = "hs_trade_both", dict(base, offer_tiles=gt, cash=cash)
            elif gt:
                key, params = "hs_trade_tile", dict(base, offer_tiles=gt)
            else:
                key, params = "hs_trade_cash", dict(base, cash=max(cash, 100))
                cash = params["cash"]
            trade = dict(to=x, give_tiles=gt, give_cash=cash, get_tiles=[target], get_cash=0) if ctx.can_trade else None
            out.append(_hint(ctx, "trade_complete", key, params, [target] + gt, trade))
            continue
        need = offer["cash"] + MIN_BUFFER - ctx.money                  # a fair offer is out of reach: raise cash first
        plan = _raise_plan(ctx, need) if need > 0 else None
        if plan:
            out.append(_hint(ctx, "trade_complete", "hs_trade_raise",
                             dict(base, cash=offer["cash"], need=need, **_raise_params(plan)),
                             [target] + [s["tile"] for s in plan]))
    return out


# ------------------------------------------------------------------------------------------------------------- 3. foothold
def _foothold(ctx):
    out = []
    T = ctx.T
    for g in ctx.prop_groups:
        a = ctx.analyse(g)
        k, n = len(a["mine"]), a["n"]
        if k < 1 or k >= n - 1:                                        # none yet, or already one short (rules 1 / 2)
            continue
        opp = a["others"]
        if len(opp) >= 2:                                              # split among many players: flag it as hard
            out.append(_hint(ctx, "foothold", "hs_foot_hard", dict(group=g, count=len(opp)), a["mine"] + sum(opp.values(), []),
                             hard=True))
            continue
        targets = [i for i in a["free"] if ctx.money - T[i]["price"] >= SAFE_RESERVE]
        if not targets:
            continue
        base = dict(group=g, have=k, total=n, targets_tiles=targets)
        if opp:
            (x,) = opp.keys()
            out.append(_hint(ctx, "foothold", "hs_foot_mixed", dict(base, player=x), targets + opp[x]))
        else:
            out.append(_hint(ctx, "foothold", "hs_foot_easy", base, targets))
    return out


# ------------------------------------------------------------------------------------------------------- 4. ranked buy targets
def _buy_targets(ctx, used):
    T = ctx.T
    cands = []
    for g in ctx.prop_groups:
        a = ctx.analyse(g)
        k, n = len(a["mine"]), a["n"]
        for i in a["free"]:
            price = T[i]["price"]
            if i in used or ctx.money - price < SAFE_RESERVE or i == ctx.auction_tile:
                continue
            closeness = (k + 1) / n * (0.5 if a["others"] else 1.0)    # an opponent in the set: a full set needs a trade
            rents = T[i].get("rents") or [0, 0, 0, 0]
            value = min(1.0, rents[min(3, len(rents) - 1)] / price / 3)  # rent with 3 houses vs price
            land = LANDING.get(g, 1.0) / _LAND_MAX
            afford = min(1.0, (ctx.money - price - SAFE_RESERVE) / 5000)
            cands.append((50 * closeness + 15 * value + 25 * land + 10 * afford, -price, i))
    if not cands:
        return []
    cands.sort(reverse=True)
    top = [c[2] for c in cands[:2]]
    return [_hint(ctx, "buy_target", "hs_targets", dict(targets_tiles=top), top)]


# ----------------------------------------------------------------------------------------------------------------- 5. block
def _block(ctx):
    out = []
    for g in ctx.prop_groups:
        a = ctx.analyse(g)
        if a["n"] < 2 or a["mine"] or len(a["free"]) != 1 or len(a["others"]) != 1:
            continue
        x, tiles = next(iter(a["others"].items()))
        if len(tiles) != a["n"] - 1:
            continue
        idx = a["free"][0]
        price = ctx.T[idx]["price"]
        base = dict(tile=idx, player=x, have=len(tiles), total=a["n"])
        if ctx.auction_tile == idx:
            limit = (ctx.money - MIN_BUFFER) // 100 * 100
            if limit >= AUCTION_MIN_BID:
                out.append(_hint(ctx, "block", "hs_block_bid", dict(base, limit=limit), [idx] + tiles))
            continue
        if ctx.money - price < MIN_BUFFER:                             # cannot afford it safely: no advice
            continue
        out.append(_hint(ctx, "block", "hs_block_now" if ctx.pending == idx else "hs_block", dict(base, price=price),
                         [idx] + tiles))
    return out


# ---------------------------------------------------------------------------------------------------------------- 6. build
def _build(ctx):
    out = []
    T = ctx.T
    best = None
    for g in ctx.prop_groups:
        a = ctx.analyse(g)
        if a["n"] < 2 or len(a["mine"]) != a["n"]:
            continue
        idxs = ctx.G[g]
        if any(ctx.mortgaged(i) for i in idxs):                        # a mortgaged land blocks building: redeem it first
            i = next(i for i in idxs if ctx.mortgaged(i))
            cost = int(T[i]["price"] // 2 * 1.1)
            if ctx.money - cost >= MIN_BUFFER:
                out.append(_hint(ctx, "build", "hs_build_redeem", dict(tile=i, cost=cost), [i]))
            continue
        low = min(ctx.houses(i) for i in idxs)
        if low >= HOTEL:
            continue
        i = min((i for i in idxs if ctx.houses(i) == low), key=lambda j: (T[j]["house_cost"], j))
        cost = T[i]["house_cost"]
        rank = LANDING.get(g, 1.0) * T[i]["rents"][min(3, len(T[i]["rents"]) - 1)]
        if best is None or rank > best[0]:
            best = (rank, i, cost)
    if best:
        _, i, cost = best
        if ctx.money - cost >= BUILD_RESERVE:
            out.append(_hint(ctx, "build", "hs_build", dict(tile=i, cost=cost), [i]))
        else:
            out.append(_hint(ctx, "build", "hs_build_save", dict(tile=i, cost=cost, need=cost + BUILD_RESERVE - ctx.money), [i]))
    return out


# ---------------------------------------------------------------------------------------------- 7. stations / utilities
def _transport(ctx):
    T, G = ctx.T, ctx.G
    out = []
    for g, idxs in G.items():
        if T[idxs[0]].get("type") not in ("station", "utility") or len(idxs) < 2:
            continue
        mine = [i for i in idxs if ctx.owner(i) == ctx.pid]
        free = [i for i in idxs if ctx.owner(i) is None and i != ctx.auction_tile]
        if not mine or not free:
            continue
        i = min(free, key=lambda j: (T[j]["price"], j))
        if ctx.money - T[i]["price"] < SAFE_RESERVE:
            continue
        out.append((len(mine), _hint(ctx, "transport", "hs_transport",
                                     dict(tile=i, price=T[i]["price"], next=len(mine) + 1, total=len(idxs),
                                          rent=STATION_RENT * (len(mine) + 1)), [i] + mine)))
    out.sort(key=lambda p: -p[0])                                       # the set I already own most of first
    return [h for _, h in out]


# ---------------------------------------------------------------------------------------------------------------- main API
def get_hints(game_state, player, tiles=None, groups=None, max_hints=MAX_HINTS, bot_level=DEFAULT_LEVEL):
    """Ranked smart hints for `player` (id or player dict), best first, at most `max_hints` (default 3). [] when there is
    nothing worth saying (or the player is out of the game / in debt, which the rule hints in game.value handle).
    `tiles` / `groups` default to the printed board; `bot_level` ("easy" / "normal" / "hard") is the computer level of the
    game, used to size offers to computer owners."""
    T = tiles if tiles is not None else TILES
    G = groups if groups is not None else (_groups_of(T) if tiles is not None else GROUPS)
    st = game_state or {}
    pid = player.get("id") if isinstance(player, dict) else player
    me = next((p for p in st.get("players", []) if p.get("id") == pid), None)
    if not me or me.get("bankrupt") or me.get("left") or st.get("winner") or me.get("money", 0) < 0:
        return []
    ctx = _Ctx(st, me, T, G, bot_level)
    found = []
    for rule in (_buy_complete, _trade_complete, _foothold, _block, _build, _transport):
        found += rule(ctx)
    used = {i for h in found for i in h["properties_involved"]}
    found += _buy_targets(ctx, used)
    found.sort(key=lambda h: h["priority"] + (0.5 if h["_hard"] else 0))   # stable: rule order breaks ties
    gone = {T[i].get("group") for h in found if h["type"] == "trade_complete" and h["trade"]
            for i in h["trade"]["give_tiles"]}                          # lands offered away: no "build on it" advice for them
    found = [h for h in found if not (h["type"] == "foothold" and h["params"].get("group") in gone)]
    out, seen = [], set()
    for h in found:
        k = (h["type"], h["params"].get("group") or T[h["properties_involved"][0]].get("group"))
        if k in seen:
            continue
        seen.add(k)
        h.pop("_hard", None)
        out.append(h)
        if len(out) >= max_hints:
            break
    return out


# --- "is there a BETTER move?" : drives the blinking light of the Hint button ---------------------------------------
def auction_advice(st, pid, tiles=None):
    """Auction help for player `pid` while a land is being auctioned.
    Returns None when there is no auction (or the player is out of the game), else a dict
        tile    the land being sold            limit   the most the player should bid (multiple of 100, may be 0)
        bid     the highest bid right now      over    True when the bid is already so high that raising it would be a loss
        none    True when the player's cash is too low to bid safely (limit below the lowest bid)
        reason  "set" (completes the player's set) | "block" (stops an opponent's set) | "part" | "plain"
    The limit is the printed price (x1.3 when the player already owns a land of the set), or all the cash that can be spared
    (money - MIN_BUFFER) when the land completes the player's set or blocks an opponent's. Never more than the cash that can be spared.
    Pure Python, never raises, never changes the state."""
    try:
        T = tiles if tiles is not None else TILES
        a = (st or {}).get("auction")
        me = next((p for p in (st or {}).get("players", []) if p.get("id") == pid), None)
        if not a or not me or me.get("bankrupt") or me.get("left") or st.get("winner"):
            return None
        idx = a["tile"]
        tl = T[idx]
        price = tl.get("price", 0) or 0
        live = {p["id"] for p in st.get("players", []) if not p.get("bankrupt") and not p.get("left")}
        props = {int(k): v for k, v in (st.get("props") or {}).items()}

        def owner(i):
            o = (props.get(i) or {}).get("owner")
            return o if o in live else None
        grp = tl.get("group")
        same = [i for i, x in enumerate(T) if grp and x.get("group") == grp and i != idx and x.get("type") == tl.get("type")]
        mine = [i for i in same if owner(i) == pid]
        others = {}
        for i in same:
            o = owner(i)
            if o is not None and o != pid:
                others.setdefault(o, []).append(i)
        cash_cap = max(0, (me["money"] - MIN_BUFFER) // 100 * 100)
        if same and len(mine) == len(same):
            reason, worth = "set", cash_cap
        elif same and not mine and len(others) == 1 and len(next(iter(others.values()))) == len(same):
            reason, worth = "block", cash_cap
        elif mine:
            reason, worth = "part", price * 1.3
        else:
            reason, worth = "plain", price
        limit = min(int(worth) // 100 * 100, cash_cap)
        bid = a.get("bid", 0) or 0
        return dict(tile=idx, limit=limit, bid=bid, reason=reason,
                    none=limit < AUCTION_MIN_BID, over=bool(bid and bid + 100 > limit))
    except Exception:
        return None


BLINK_TYPES = frozenset({"buy_complete", "trade_complete", "block", "build"})      # set-aware hints worth a blink
BLINK_RULES = frozenset({"hint_buy_set", "hint_buy_ok", "hint_buy_risky", "hint_jail_card", "hint_jail_pay",
                         "hint_redeem", "hint_build", "hint_debt"})   # tactical hints worth a blink (not hint_rent_ahead: the Hint window does not show it)
# (not worth a blink: roll / roll for a card / end turn / wait for your turn / auction / "cannot afford" / stuck in debt)


def better_hint_signature(st, pid, tiles=TILES, bot_level=DEFAULT_LEVEL):
    """None when the best advice is only the ordinary 'roll' / 'end turn' / 'wait'. Otherwise a hashable signature of
    the better move(s) (it changes when the advice changes, so the app can tell a NEW better move from one the player
    has already looked at). Works on the player's own turn AND on other players' turns (trades, blocks and
    builds are possible any time). Sub-millisecond: safe to call on every state update. Never raises."""
    try:
        me = next((p for p in (st or {}).get("players", []) if p.get("id") == pid), None)
        if not me or me.get("bankrupt") or me.get("left") or st.get("winner"):
            return None
        sig = []
        for h in get_hints(st, pid, tiles, bot_level=bot_level):
            if h["type"] in BLINK_TYPES:
                sig.append(("smart", h["type"], tuple(h["properties_involved"])))
        from .value import hint as rule_hint                      # local import: value.py imports nothing from here
        r = rule_hint(st, pid, tiles)
        if r and r["key"] in BLINK_RULES:
            sig.append(("rule", r["key"], r["tile"]))
        return tuple(sig) or None
    except Exception:
        return None
