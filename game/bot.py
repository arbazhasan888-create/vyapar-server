"""Computer player. bot_step(g, rng) performs ONE action for the player whose turn it is
and returns the action's name, so the app can pace the bot's turn and show it to the human."""
from .board import TILES
from .rules import GameError


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


def bot_step(g, rng):
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
            if p["money"] > 600 and _try(g, pid, "pay_jail"):
                return "pay_jail"
        g.act(pid, "roll")
        return "roll"

    idx = g.pending_buy                                  # act phase
    if idx is not None:
        t = TILES[idx]
        reserve = 80 if (_completes_group(g, pid, idx) or t["type"] == "station") else 250
        if p["money"] - t["price"] >= reserve and _try(g, pid, "buy"):
            return "buy"

    if p["money"] > 700:                                 # redeem mortgaged tiles when rich
        for i in g.owned(pid):
            if g.props[i]["mortgaged"] and _try(g, pid, "redeem", tile=i):
                return "redeem"
    if p["money"] > 450:                                 # build houses, keep a cash cushion
        mine = sorted(g.owned(pid), key=lambda i: TILES[i].get("house_cost", 10 ** 6))
        for i in mine:
            if TILES[i]["type"] == "property" and p["money"] - TILES[i]["house_cost"] >= 300 and _try(g, pid, "build", tile=i):
                return "build"

    g.act(pid, "end_turn")
    return "end_turn"
