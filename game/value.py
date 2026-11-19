"""Pure helpers without any UI.
 - trade_value(): how good a trade is for one player (the deal-value meter in the Trade windows).
 - raisable(): how much cash a player in debt could still raise (the rescue window before bankruptcy).
 - rent_ahead(): which lands within one roll of the player's pawn would cost a lot of rent (the hint above Roll).
All of them read the plain state dict the app already has (state["props"][str(tile)] = {owner, houses, mortgaged})."""
from .board import TILES, GROUPS, N, STATION_RENT, MAX_HOUSES, HOTEL

JAIL_CARD_VALUE = 600
WAYS = {2: 1, 3: 2, 4: 3, 5: 4, 6: 5, 7: 6, 8: 5, 9: 4, 10: 3, 11: 2, 12: 1}      # two dice: ways out of 36 to roll each total


def _owner(props, idx):
    s = props.get(str(idx))
    return s["owner"] if s else None


def _worth(props, idx, viewer, other, get_tiles, give_tiles, receiving):
    """What one land is worth to `viewer`: its price (less when mortgaged); more when receiving it completes a colour
    set for the viewer, and when giving it away breaks the viewer's own set or hands the other player a full set.
    Returns (value, completes_mine, gives_set)."""
    tl = TILES[idx]
    s = props.get(str(idx)) or {}
    v = float(tl["price"]) * (0.6 if s.get("mortgaged") else 1.0)
    completes = gives = False
    if tl["type"] == "property":
        rest = [j for j in GROUPS[tl["group"]] if j != idx]
        if receiving:
            if all(_owner(props, j) == viewer or j in get_tiles for j in rest):
                v *= 1.6
                completes = True
        else:
            if any(_owner(props, j) == viewer and j not in give_tiles for j in rest):
                v *= 1.2
            if all(_owner(props, j) == other or j in give_tiles for j in rest):
                v *= 1.5
                gives = True
    return v, completes, gives


def trade_value(props, viewer, other, get_tiles=(), get_cash=0, get_cards=0, give_tiles=(), give_cash=0, give_cards=0):
    """The deal as seen by `viewer` (get = what the viewer receives, give = what the viewer hands over).
    Returns None for an empty deal, else dict(get, give, pct, pos, level, completes, gives_set):
    pct runs from -1 (very bad) to +1 (very good), pos = 0..1 for the meter, level = 2 great, 1 good, 0 fair,
    -1 slightly bad, -2 bad."""
    get_tiles, give_tiles = set(get_tiles), set(give_tiles)
    if not (get_tiles or give_tiles or get_cash or give_cash or get_cards or give_cards):
        return None
    got = give = 0.0
    completes = gives_set = False
    for i in get_tiles:
        v, c, _ = _worth(props, i, viewer, other, get_tiles, give_tiles, True)
        got += v
        completes |= c
    for i in give_tiles:
        v, _, g = _worth(props, i, viewer, other, get_tiles, give_tiles, False)
        give += v
        gives_set |= g
    got += get_cash + JAIL_CARD_VALUE * get_cards
    give += give_cash + JAIL_CARD_VALUE * give_cards
    pct = (got - give) / max(got, give, 1.0)
    level = 2 if pct >= .30 else 1 if pct >= .10 else 0 if pct > -.10 else -1 if pct > -.30 else -2
    return dict(get=got, give=give, pct=pct, pos=max(0.0, min(1.0, (pct + 1) / 2)), level=level,
                completes=completes, gives_set=gives_set)


def _rent_if_landed(props, idx, owner):
    tl = TILES[idx]
    s = props[str(idx)]
    if s.get("mortgaged"):
        return 0
    if tl["type"] == "property":
        if s.get("houses"):
            return tl["rents"][s["houses"]]
        mono = all(_owner(props, j) == owner for j in GROUPS[tl["group"]])
        return tl["rents"][0] * (2 if mono else 1)
    if tl["type"] in ("station", "utility"):
        return STATION_RENT * sum(1 for j in GROUPS[tl["group"]] if _owner(props, j) == owner)
    return 0                                    # the Airport rent depends on a second roll: not predicted


def rent_ahead(props, pos, pid, cash, limit=2):
    """Lands 2..12 steps ahead (one roll of two dice) owned by other players with a heavy rent: at least Rs 1000 or a
    quarter of the player's cash. Returns up to `limit` dicts (idx, dist, rent, pct), the highest rent first."""
    out = []
    for dist, ways in WAYS.items():
        idx = (pos + dist) % N
        s = props.get(str(idx))
        if not s or s.get("owner") in (None, pid):
            continue
        r = _rent_if_landed(props, idx, s["owner"])
        if r >= 1000 or (r > 0 and r >= cash * 0.25):
            out.append(dict(idx=idx, dist=dist, rent=r, pct=round(ways * 100 / 36)))
    out.sort(key=lambda d: -d["rent"])
    return out[:limit]


def raisable(props, pid, tiles=TILES):
    """What `pid` could still turn into cash: every house sold (a hotel counts as 4 sales: the hotel, then 3 houses, each
    for half the house price) and every free land mortgaged (half its price). Returns dict(houses, mortgage, total,
    items): items = [dict(idx, kind "sell" | "mortgage", n houses, cash)], the biggest sums first."""
    items, sell, mort = [], 0, 0
    for k, s in props.items():
        if s.get("owner") != pid:
            continue
        idx, tl = int(k), tiles[int(k)]
        h = s.get("houses") or 0
        if h and tl.get("type") == "property":
            n = MAX_HOUSES + 1 if h >= HOTEL else h
            cash = n * (tl.get("house_cost", 0) // 2)
            sell += cash
            items.append(dict(idx=idx, kind="sell", n=n, cash=cash))
        if not s.get("mortgaged"):
            cash = tl.get("price", 0) // 2
            mort += cash
            items.append(dict(idx=idx, kind="mortgage", n=0, cash=cash))
    items.sort(key=lambda d: (-d["cash"], d["idx"]))
    return dict(houses=sell, mortgage=mort, total=sell + mort, items=items)


JAIL_FINE = 500
BUY_CUSHION = 2000          # cash that should stay after buying a land
BUILD_CUSHION = 2500        # cash that should stay after building a house
REDEEM_CASH = 6000          # redeem a mortgaged land when richer than this


def build_options(props, pid, tiles=TILES):
    """Lands `pid` can build on right now (same conditions as the game's do_build, without the cash check),
    cheapest house first: [(tile index, house cost)]."""
    out = []
    for k, s in props.items():
        i = int(k)
        tl = tiles[i]
        if s.get("owner") != pid or tl.get("type") != "property":
            continue
        grp = [props.get(str(j)) for j in GROUPS[tl["group"]]]
        if any(g is None or g.get("owner") != pid or g.get("mortgaged") for g in grp):
            continue
        h = s.get("houses") or 0
        if h >= HOTEL or h > min((g.get("houses") or 0) for g in grp):
            continue
        out.append((i, tl["house_cost"]))
    out.sort(key=lambda d: (d[1], d[0]))
    return out


def _completes(props, pid, idx, tiles):
    tl = tiles[idx]
    if tl.get("type") != "property":
        return False
    return all(j == idx or _owner(props, j) == pid for j in GROUPS[tl["group"]])


def hint(st, pid, tiles=TILES):
    """A sensible next step for player `pid`, read from the plain state dict. Returns None (nothing to say) or
    dict(key, kw, action, tile): key / kw = text key + parameters (the app translates it), action = the button the
    app can press for the player ("roll", "end_turn", "build", "redeem", "mortgage", "pay_jail", "use_card" or None),
    tile = tile index of the advice (or None)."""
    me = next((p for p in st.get("players", []) if p["id"] == pid), None)
    if not me or me.get("bankrupt") or st.get("winner"):
        return None
    props = st.get("props", {})
    money = me["money"]

    def H(key, action=None, tile=None, **kw):
        return dict(key=key, kw=kw, action=action, tile=tile)

    if money < 0:
        r = raisable(props, pid, tiles)
        if r["total"] >= -money:
            return H("hint_debt", "mortgage", debt=-money, total=r["total"])
        return H("hint_debt_lost", None, debt=-money, total=r["total"])
    if st.get("auction"):
        return H("hint_auction")
    mine = st.get("turn") == pid
    if not mine:
        return H("hint_wait", None, who=st.get("turn"))
    phase = st.get("phase")
    if st.get("pending_buy") is not None:
        idx = st["pending_buy"]
        price = tiles[idx]["price"]
        left = money - price
        if left < 0:
            return H("hint_buy_poor", None, idx, price=price)
        if _completes(props, pid, idx, tiles):
            return H("hint_buy_set", None, idx, price=price)
        if left < BUY_CUSHION:
            return H("hint_buy_risky", None, idx, price=price, left=left)
        return H("hint_buy_ok", None, idx, price=price, left=left)
    if st.get("pending_draw"):
        return H("hint_roll_card", "roll")
    if phase == "roll":
        if me.get("in_jail"):
            if me.get("cards"):
                return H("hint_jail_card", "use_card")
            if money >= JAIL_FINE * 4:
                return H("hint_jail_pay", "pay_jail", fine=JAIL_FINE)
            return H("hint_jail_roll", "roll")
        ahead = rent_ahead(props, me["pos"], pid, money, 1)
        if ahead:
            a = ahead[0]
            return H("hint_rent_ahead", "roll", a["idx"], rent=a["rent"], pct=a["pct"])
        return H("hint_roll", "roll")
    # act phase, nothing pending
    for i, s in sorted(props.items(), key=lambda kv: -tiles[int(kv[0])].get("price", 0)):
        if s.get("owner") == pid and s.get("mortgaged") and money > REDEEM_CASH:
            cost = int(tiles[int(i)]["price"] // 2 * 1.1)
            if money - cost >= BUILD_CUSHION:
                return H("hint_redeem", "redeem", int(i), cost=cost)
    for i, cost in build_options(props, pid, tiles):
        if money - cost >= BUILD_CUSHION:
            return H("hint_build", "build", i, cost=cost)
    return H("hint_end", "end_turn")
