"""Computer player. bot_step(g, rng) performs ONE action for the player whose turn it is
and returns the action's name, so the app can pace the bot's turn and show it to the human."""
import random

from .board import TILES
from .rules import GameError, AUCTION_STEP


def _try(g, pid, action, **kw):
    try:
        g.act(pid, action, **kw)
        return True
    except GameError:
        return False


def _completes_group(g, pid, idx):
    t = TILES[idx]
    if t["type"] != "property":
        return False
    return all(g.owner_of(i) == pid for i, x in enumerate(TILES) if x.get("group") == t["group"] and i != idx)


def _round100(x):
    return max(AUCTION_STEP, int(round(x / 100.0)) * 100)


def _auction_step(g, rng):
    """The computer is the bidder: raise up to what the land is worth to it (never below a cash cushion) or pass.
    Worth = printed price x a factor, higher when the land completes a colour group for the bot. The factor is drawn
    from a generator seeded with (bot, land, roll), so it stays the same for the whole auction and is not stored."""
    a = g.auction
    p = g.get(a["bidder"])
    idx = a["tile"]
    price = TILES[idx]["price"]
    mine = random.Random(f"{p['id']}:{idx}:{g.roll_seq}")
    worth = int(price * (mine.uniform(1.2, 1.8) if _completes_group(g, p["id"], idx) else mine.uniform(0.7, 1.15)))
    low = g.auction_min()
    cap = min(worth, p["money"] - 600)                              # keep some cash
    if low > cap:
        g.act(p["id"], "pass_bid")
        return "pass_bid"
    if a["bid"] == 0:                                               # open at a sensible price, not at the minimum
        amount = max(low, _round100(price * rng.uniform(0.3, 0.5)))
    else:                                                           # bigger steps keep a bot-vs-bot auction short
        amount = a["bid"] + _round100(price * rng.uniform(0.04, 0.10))
    g.act(p["id"], "bid", amount=max(low, min(cap, amount)))
    return "bid"


def bot_step(g, rng):
    if g.auction:                                        # an auction is running: the bidder acts, whoever's turn it is
        return _auction_step(g, rng)
    p = g.cur()
    pid = p["id"]

    if p["money"] < 0:                                   # in debt: sell houses, mortgage, else go bankrupt
        mine = g.owned(pid)
        rng.shuffle(mine)
        for action in ("sell", "mortgage"):
            for i in mine:
                if _try(g, pid, action, tile=i):
                    return action
        g.act(pid, "bankrupt")
        return "bankrupt"

    if g.phase == "roll":
        if p["in_jail"]:
            if p["cards"] and _try(g, pid, "use_card"):
                return "use_card"
            if p["money"] > 6000 and _try(g, pid, "pay_jail"):
                return "pay_jail"
        g.act(pid, "roll")
        return "roll"

    if g.pending_draw:                                   # landed on Luck / Fortune (card) or on an owned Airport (rent): roll the dice
        g.act(pid, "roll_card")
        return "roll_card"

    idx = g.pending_buy                                  # act phase
    if idx is not None:
        t = TILES[idx]
        reserve = 800 if (_completes_group(g, pid, idx) or t["type"] in ("station", "utility", "airport")) else 2500
        if p["money"] - t["price"] >= reserve and _try(g, pid, "buy"):
            return "buy"
        g.act(pid, "skip")                               # does not want it at this price: auction
        return "skip"

    if p["money"] > 7000:                                # redeem mortgaged tiles when rich
        for i in g.owned(pid):
            if g.props[i]["mortgaged"] and _try(g, pid, "redeem", tile=i):
                return "redeem"
    if p["money"] > 4500:                                # build houses, keep a cash cushion
        mine = sorted(g.owned(pid), key=lambda i: TILES[i].get("house_cost", 10 ** 6))
        for i in mine:
            if TILES[i]["type"] == "property" and p["money"] - TILES[i]["house_cost"] >= 3000 and _try(g, pid, "build", tile=i):
                return "build"

    g.act(pid, "end_turn")
    return "end_turn"
