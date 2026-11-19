"""Computer player. bot_step(g, rng) performs ONE action for the player whose turn it is
and returns the action's name, so the app can pace the bot's turn and show it to the human."""
import random

from .board import TILES, GROUPS
from .value import trade_value
from .rules import GameError, AUCTION_STEP


LEVELS = ("easy", "normal", "hard")
DEFAULT_LEVEL = "normal"

# How careful each computer level is. "normal" is exactly the computer that existed before levels were added.
#   skip      chance (0..1) that the computer declines a land it could afford (it then goes to auction)
#   reserve   cash that must stay after buying (a land that completes a set / station / utility / airport, any other land)
#   worth     auction value of a land as a multiple of its price: (ordinary land, land that completes a set)
#   cushion   cash that must stay after bidding in an auction
#   trade     how much more than it gives the computer wants to get back in a trade (range)
#   build     the computer builds when it has more than build[0] cash and keeps build[1] afterwards
#   redeem    the computer redeems mortgaged lands when it has more than this
#   jail      the computer pays the jail fine when it has more than this (cards are always used first)
#   smart     Hard only: pays debts by mortgaging lands before selling houses, and offers trades that complete its colour sets
LEVEL_CFG = {
    "easy":   dict(smart=False, skip=0.25, reserve=(2500, 2500), worth=((0.50, 0.90), (0.80, 1.25)), cushion=1500, trade=(0.85, 1.00),
                   build=(7500, 5000), redeem=9500, jail=9000),
    "normal": dict(smart=False, skip=0.0, reserve=(800, 2500), worth=((0.70, 1.15), (1.20, 1.80)), cushion=600, trade=(1.05, 1.25),
                   build=(4500, 3000), redeem=7000, jail=6000),
    "hard":   dict(smart=True, skip=0.0, reserve=(300, 1200), worth=((0.90, 1.35), (1.60, 2.30)), cushion=300, trade=(1.20, 1.45),
                   build=(2800, 1500), redeem=5000, jail=2500),
}


def cfg_of(level):
    return LEVEL_CFG.get(level) or LEVEL_CFG[DEFAULT_LEVEL]


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


def _auction_step(g, rng, cfg):
    """The computer is the bidder: raise up to what the land is worth to it (never below a cash cushion) or pass.
    Worth = printed price x a factor, higher when the land completes a colour group for the bot. The factor is drawn
    from a generator seeded with (bot, land, roll), so it stays the same for the whole auction and is not stored."""
    a = g.auction
    p = g.get(a["bidder"])
    idx = a["tile"]
    price = TILES[idx]["price"]
    mine = random.Random(f"{p['id']}:{idx}:{g.roll_seq}")
    lo, hi = cfg["worth"][1] if _completes_group(g, p["id"], idx) else cfg["worth"][0]
    worth = int(price * mine.uniform(lo, hi))
    low = g.auction_min()
    cap = min(worth, p["money"] - cfg["cushion"])                   # keep some cash
    if low > cap:
        g.act(p["id"], "pass_bid")
        return "pass_bid"
    if a["bid"] == 0:                                               # open at a sensible price, not at the minimum
        amount = max(low, _round100(price * rng.uniform(0.3, 0.5)))
    else:                                                           # bigger steps keep a bot-vs-bot auction short
        amount = a["bid"] + _round100(price * rng.uniform(0.04, 0.10))
    g.act(p["id"], "bid", amount=max(low, min(cap, amount)))
    return "bid"


JAIL_CARD_VALUE = 600


def _tile_value(g, pid, idx, receiving):
    """What a land is worth to the computer player `pid`: the printed price (a mortgaged land counts less); more when
    it completes a colour set for the computer; when it is given away, more when it breaks the computer's own set."""
    t = TILES[idx]
    v = float(t["price"]) * (0.6 if g.props[idx]["mortgaged"] else 1.0)
    if t["type"] == "property":
        if receiving and _completes_group(g, pid, idx):
            v *= 2.2
        elif not receiving:
            if any(g.owner_of(i) == pid for i, x in enumerate(TILES) if x.get("group") == t["group"] and i != idx):
                v *= 1.3                                  # it is part of a set the computer is collecting
            for o in g.alive():                           # the human would get a full set: very unwilling
                if o["id"] != pid and _completes_group(g, o["id"], idx):
                    v *= 2.5
                    break
    return v


def _trade_reply(g, rng, cfg):
    """The computer is asked to accept or refuse the pending trade. It accepts when what it gets is worth clearly
    more than what it gives (a small margin, a little different from bot to bot) and it keeps a cash cushion."""
    tr = g.trade
    pid = tr["to"]
    p = g.get(pid)
    mine = random.Random(f"trade:{pid}:{g.roll_seq}:{tr['frm']}")
    gets = sum(_tile_value(g, pid, i, True) for i in tr["give_tiles"]) + tr["give_cash"] \
        + JAIL_CARD_VALUE * tr.get("give_cards", 0)
    gives = sum(_tile_value(g, pid, i, False) for i in tr["get_tiles"]) + tr["get_cash"] \
        + JAIL_CARD_VALUE * tr.get("get_cards", 0)
    ok = gets >= gives * mine.uniform(*cfg["trade"]) and p["money"] - tr["get_cash"] + tr["give_cash"] >= 1000
    if ok and _try(g, pid, "accept_trade"):
        return "accept_trade"
    g.act(pid, "reject_trade")
    return "reject_trade"


def _raise_cash(g, pid, rng, smart):
    """In debt: sell houses / mortgage lands until the debt is paid. The smart computer mortgages lands that are not part
    of a set it has built on first and gives up houses last; the others pick lands at random (sell before mortgage)."""
    mine = g.owned(pid)
    rng.shuffle(mine)
    if smart:
        def keep(i):                                   # 0 = give up first, bigger = keep longer
            t, s = TILES[i], g.props[i]
            full = t["type"] == "property" and all(g.owner_of(j) == pid for j in GROUPS[t["group"]])
            return 2 if s["houses"] else 1 if full else 0
        mine.sort(key=lambda i: (keep(i), -TILES[i]["price"]))
        order = ("mortgage", "sell")
    else:
        order = ("sell", "mortgage")
    for action in order:
        for i in mine:
            if _try(g, pid, action, tile=i):
                return action
    return None


def _propose_trade(g, pid, rng, cfg):
    """Hard computer: ask another player for ONE land that completes a colour set, paying with a land that is of no use
    to the computer plus cash. The offer is only made when the other player would see it as a good deal (so it has a
    real chance), and only once every few rounds, so a human is not pestered. Returns True if an offer was made."""
    last = getattr(g, "_bot_offer", {})                                # pid -> roll_seq of its last offer (not saved)
    if g.trade or g.auction or g.roll_seq - last.get(pid, -999) < 5 * len(g.players):
        return False                                                   # a computer makes an offer only every ~5 rounds
    me = g.get(pid)
    if me["money"] < 2000:
        return False
    last[pid] = g.roll_seq
    g._bot_offer = last
    mine = g.owned(pid)
    spare = [i for i in mine if not g.props[i]["houses"] and not g.props[i]["mortgaged"]
             and not (TILES[i]["type"] == "property" and any(g.owner_of(j) == pid for j in GROUPS[TILES[i]["group"]] if j != i))]
    for o in g.alive():
        if o["id"] == pid:
            continue
        want = [i for i in g.owned(o["id"]) if _completes_group(g, pid, i) and not g.props[i]["mortgaged"]]
        for idx in want:
            gives = [None] + spare
            rng.shuffle(gives)
            for give in gives:
                for cash in range(0, min(me["money"] - 1500, int(TILES[idx]["price"] * 1.6)) + 1, 250):
                    gt = [give] if give is not None else []
                    if not gt and not cash:
                        continue
                    mine_gets = _tile_value(g, pid, idx, True)
                    mine_gives = sum(_tile_value(g, pid, i, False) for i in gt) + cash
                    if mine_gets < mine_gives * 1.15:
                        continue
                    v = trade_value(g.props, o["id"], pid, get_tiles=gt, get_cash=cash, give_tiles=[idx])
                    if v and v["level"] >= 1 and _try(g, pid, "propose_trade", to=o["id"], give_tiles=gt, give_cash=cash,
                                                      get_tiles=[idx], get_cash=0):
                        return True
    return False


def bot_step(g, rng, level=DEFAULT_LEVEL):
    """Perform ONE action of the computer player whose turn it is. level: "easy", "normal" or "hard" (see LEVEL_CFG)."""
    cfg = cfg_of(level)
    if g.auction:                                        # an auction is running: the bidder acts, whoever's turn it is
        return _auction_step(g, rng, cfg)
    if g.trade and g.trade["to"].startswith("bot"):      # somebody offered the computer a deal: answer it first
        return _trade_reply(g, rng, cfg)
    p = g.cur()
    pid = p["id"]

    if p["money"] < 0:                                   # in debt: sell houses, mortgage, else go bankrupt
        done = _raise_cash(g, pid, rng, cfg["smart"])
        if done:
            return done
        g.act(pid, "bankrupt")
        return "bankrupt"

    if g.phase == "roll":
        if p["in_jail"]:
            if p["cards"] and _try(g, pid, "use_card"):
                return "use_card"
            if p["money"] > cfg["jail"] and _try(g, pid, "pay_jail"):
                return "pay_jail"
        g.act(pid, "roll")
        return "roll"

    if g.pending_draw:                                   # landed on Luck / Fortune (card) or on an owned Airport (rent): roll the dice
        g.act(pid, "roll_card")
        return "roll_card"

    idx = g.pending_buy                                  # act phase
    if idx is not None:
        t = TILES[idx]
        reserve = cfg["reserve"][0] if (_completes_group(g, pid, idx) or t["type"] in ("station", "utility", "airport")) \
            else cfg["reserve"][1]
        careless = cfg["skip"] and not _completes_group(g, pid, idx) and rng.random() < cfg["skip"]
        if not careless and p["money"] - t["price"] >= reserve and _try(g, pid, "buy"):
            return "buy"
        g.act(pid, "skip")                               # does not want it at this price: auction
        return "skip"

    if p["money"] > cfg["redeem"]:                       # redeem mortgaged tiles when rich
        for i in g.owned(pid):
            if g.props[i]["mortgaged"] and _try(g, pid, "redeem", tile=i):
                return "redeem"
    if p["money"] > cfg["build"][0]:                     # build houses, keep a cash cushion
        mine = sorted(g.owned(pid), key=lambda i: TILES[i].get("house_cost", 10 ** 6))
        for i in mine:
            if TILES[i]["type"] == "property" and p["money"] - TILES[i]["house_cost"] >= cfg["build"][1] and _try(g, pid, "build", tile=i):
                return "build"

    if cfg["smart"] and _propose_trade(g, pid, rng, cfg):
        return "propose_trade"
    g.act(pid, "end_turn")
    return "end_turn"
