"""Hindi / English texts for everything the game ENGINE says (log lines, banners, errors, cards, tile names).

The engine never stores a finished sentence any more. It stores a key + parameters, e.g.
    {"k": "rent", "p": {"name": "<player id>", "owner": "<player id>", "tile": 13, "amt": 28}}
and every app turns that into text in the language the player has chosen, so the log and the banners
change language the moment the player switches it (old lines included).

Parameter conventions
    name / owner / other / p1 / p2 : player ids   -> replaced by the player's display name
    tile                           : tile index   -> replaced by the city name in the chosen language
    deck + ci                      : "luck"|"fortune" + card index (dice total - 2) -> deck name and card text
"""
from .board import TILES
from .cards import LUCK, FORTUNE

LANGS = ("hi", "en")
DEFAULT_LANG = "hi"

PLAYER_KEYS = ("name", "owner", "other", "p1", "p2")

DECK_NAMES = {"hi": {"luck": "किस्मत", "fortune": "भाग्य"},
              "en": {"luck": "Luck", "fortune": "Fortune"}}
DECK_CARDS = {"luck": LUCK, "fortune": FORTUNE}

LOG = {
    "hi": {
        "start": "खेल शुरू! पहली बारी: {name}",
        "jail": "{name} जेल गया!",
        "go": "{name} को स्टार्ट पार करने पर ₹{amt} मिला।",
        "arrive": "{name} पहुँचा: {tile}",
        "rent": "{name} ने {owner} को {tile} का ₹{amt} किराया दिया।",
        "tax": "{name} ने ₹{amt} टैक्स दिया।",
        "card": "{name} ने {deck} कार्ड उठाया (पासा {roll}): {card}",
        "roll": "{name} ने पासा फेंका: {d1} + {d2}",
        "jail_double": "{name} डबल लाकर जेल से छूटा।",
        "jail_auto": "3 बारी पूरी: ₹{amt} जुर्माना देकर छूटे।",
        "buy": "{name} ने {tile} ₹{price} में खरीदा।",
        "again": "{name} को दोबारा पासा फेंकना है।",
        "turn": "अब {name} की बारी।",
        "pay_jail": "{name} ने ₹{amt} देकर जेल छोड़ी।",
        "use_card": "{name} ने छुट्टी कार्ड इस्तेमाल किया।",
        "build": "{name} ने {tile} में मकान बनाया (कुल {n})।",
        "build_hotel": "{name} ने {tile} में होटल बनाया!",
        "sell": "{name} ने {tile} का मकान बेचा।",
        "sell_hotel": "{name} ने {tile} का होटल बेचा।",
        "mortgage": "{name} ने {tile} गिरवी रखा।",
        "redeem": "{name} ने {tile} छुड़ाया।",
        "bankrupt": "{name} दिवालिया हो गया!",
        "left": "{name} खेल छोड़कर चला गया।",
        "win": "{name} जीत गया!",
        "trade_offer": "{name} ने {other} को सौदा भेजा।",
        "trade_done": "{p1} और {p2} का सौदा पक्का!",
        "trade_cancel": "सौदा रद्द हुआ।",
        "auction_start": "{name} ने {tile} नहीं खरीदा: नीलामी शुरू! (दाम ₹{price})",
        "auction_bid": "{name} ने {tile} पर ₹{amt} की बोली लगाई।",
        "auction_pass": "{name} ने बोली छोड़ी।",
        "auction_won": "{name} ने नीलामी में {tile} ₹{price} में जीता।",
        "auction_none": "{tile} पर किसी ने बोली नहीं लगाई।",
        "no_buy": "{name} ने {tile} नहीं खरीदा।",
    },
    "en": {
        "start": "Game on! First turn: {name}",
        "jail": "{name} went to jail!",
        "go": "{name} collected ₹{amt} for passing START.",
        "arrive": "{name} landed on {tile}",
        "rent": "{name} paid {owner} ₹{amt} rent for {tile}.",
        "tax": "{name} paid ₹{amt} tax.",
        "card": "{name} drew a {deck} card (dice {roll}): {card}",
        "roll": "{name} rolled {d1} + {d2}",
        "jail_double": "{name} rolled a double and got out of jail.",
        "jail_auto": "3 turns done: paid a ₹{amt} fine and got out.",
        "buy": "{name} bought {tile} for ₹{price}.",
        "again": "{name} gets to roll again.",
        "turn": "Now it's {name}'s turn.",
        "pay_jail": "{name} paid ₹{amt} to leave jail.",
        "use_card": "{name} used a Get Out of Jail card.",
        "build": "{name} built a house on {tile} (total {n}).",
        "build_hotel": "{name} built a hotel on {tile}!",
        "sell": "{name} sold a house on {tile}.",
        "sell_hotel": "{name} sold the hotel on {tile}.",
        "mortgage": "{name} mortgaged {tile}.",
        "redeem": "{name} redeemed {tile}.",
        "bankrupt": "{name} went bankrupt!",
        "left": "{name} left the game.",
        "win": "{name} wins!",
        "trade_offer": "{name} sent a deal to {other}.",
        "trade_done": "Deal done between {p1} and {p2}!",
        "trade_cancel": "The deal was cancelled.",
        "auction_start": "{name} passed on {tile}: auction starts! (price ₹{price})",
        "auction_bid": "{name} bid ₹{amt} for {tile}.",
        "auction_pass": "{name} dropped out of the bidding.",
        "auction_won": "{name} won {tile} at auction for ₹{price}.",
        "auction_none": "Nobody bid for {tile}.",
        "no_buy": "{name} did not buy {tile}.",
    },
}

ERR = {
    "hi": {
        "need_players": "{min} से {max} खिलाड़ी चाहिए।",
        "at_least": "कम से कम {min} खिलाड़ी चाहिए।",
        "no_player": "खिलाड़ी नहीं मिला।",
        "game_over": "खेल खत्म हो चुका है।",
        "you_bankrupt": "आप दिवालिया हो चुके हैं।",
        "bad_move": "अमान्य चाल।",
        "not_turn": "अभी आपकी बारी नहीं है।",
        "already_rolled": "आप पासा फेंक चुके हैं।",
        "nothing_to_buy": "खरीदने के लिए कुछ नहीं है।",
        "poor": "पैसे कम हैं।",
        "roll_first": "पहले पासा फेंको।",
        "card_roll_first": "पहले किस्मत/भाग्य के लिए पासा फेंको।",
        "no_card_roll": "अभी कार्ड के लिए पासा नहीं फेंकना है।",
        "in_debt": "आप कर्ज़ में हैं। संपत्ति गिरवी रखो या दिवालिया घोषित करो।",
        "no_fine_now": "अभी जुर्माना नहीं दे सकते।",
        "card_unusable": "कार्ड अभी इस्तेमाल नहीं हो सकता।",
        "not_yours": "यह संपत्ति आपकी नहीं है।",
        "no_build": "यहाँ मकान नहीं बन सकता।",
        "need_group": "पूरे रंग-समूह के मालिक बनो।",
        "mortgaged_group": "गिरवी संपत्ति वाले समूह में निर्माण नहीं हो सकता।",
        "hotel_exists": "होटल पहले से बन चुका है।",
        "build_even": "मकान बराबर-बराबर बनाओ।",
        "no_house": "बेचने के लिए मकान नहीं है।",
        "sell_even": "पहले ज़्यादा मकान वाली जगह से बेचो।",
        "already_mortgaged": "पहले से गिरवी है।",
        "sell_group_first": "पहले इस समूह के मकान बेचो।",
        "not_mortgaged": "यह गिरवी नहीं है।",
        "not_in_debt": "आप कर्ज़ में नहीं हैं।",
        "owner_poor": "{name} के पास इतने पैसे नहीं हैं।",
        "trade_houses": "मकान वाले समूह का सौदा नहीं हो सकता।",
        "wrong_player": "गलत खिलाड़ी चुना।",
        "trade_pending": "पहले से एक सौदा चल रहा है।",
        "trade_empty": "सौदे में कुछ तो शामिल करो।",
        "trade_no_card": "{name} के पास छुट्टी कार्ड नहीं है।",
        "no_trade_for_you": "आपके लिए कोई सौदा नहीं है।",
        "no_trade": "कोई सौदा नहीं है।",
        "auction_busy": "नीलामी चल रही है। पहले बोली पूरी होने दो।",
        "no_auction": "अभी कोई नीलामी नहीं चल रही।",
        "not_bidder": "अभी आपकी बोली की बारी नहीं है।",
        "bad_bid": "बोली की रकम सही नहीं है।",
        "bid_low": "बोली कम से कम ₹{min} होनी चाहिए।",
        # server
        "room_not_found": "कमरा नहीं मिला।",
        "game_started": "खेल शुरू हो चुका है।",
        "room_full": "कमरा भरा हुआ है।",
        "only_host_start": "सिर्फ़ होस्ट खेल शुरू कर सकता है।",
        "only_host_color": "सिर्फ़ होस्ट रंग चुन सकता है।",
        "voice_long": "आवाज़ संदेश बहुत लंबा है।",
    },
    "en": {
        "need_players": "{min} to {max} players are needed.",
        "at_least": "At least {min} players are needed.",
        "no_player": "Player not found.",
        "game_over": "The game is over.",
        "you_bankrupt": "You are bankrupt.",
        "bad_move": "Invalid move.",
        "not_turn": "It's not your turn.",
        "already_rolled": "You have already rolled.",
        "nothing_to_buy": "There is nothing to buy.",
        "poor": "Not enough money.",
        "roll_first": "Roll the dice first.",
        "card_roll_first": "Roll the dice for your Luck / Fortune first.",
        "no_card_roll": "There is no Luck / Fortune dice roll right now.",
        "in_debt": "You are in debt. Mortgage a property or declare bankruptcy.",
        "no_fine_now": "You can't pay the fine right now.",
        "card_unusable": "You can't use the card right now.",
        "not_yours": "You don't own this property.",
        "no_build": "You can't build here.",
        "need_group": "Own the whole colour group first.",
        "mortgaged_group": "You can't build in a group that has a mortgaged property.",
        "hotel_exists": "A hotel is already built.",
        "build_even": "Build houses evenly.",
        "no_house": "There is no house to sell.",
        "sell_even": "Sell from the property with more houses first.",
        "already_mortgaged": "Already mortgaged.",
        "sell_group_first": "Sell this group's houses first.",
        "not_mortgaged": "This property is not mortgaged.",
        "not_in_debt": "You are not in debt.",
        "owner_poor": "{name} doesn't have that much money.",
        "trade_houses": "A group with houses can't be traded.",
        "wrong_player": "Wrong player selected.",
        "trade_pending": "A deal is already in progress.",
        "trade_empty": "Add something to the deal first.",
        "trade_no_card": "{name} doesn't have a Jail card.",
        "no_trade_for_you": "There is no deal for you.",
        "no_trade": "There is no deal.",
        "auction_busy": "An auction is running. Let the bidding finish first.",
        "no_auction": "There is no auction right now.",
        "not_bidder": "It is not your turn to bid.",
        "bad_bid": "That bid amount is not valid.",
        "bid_low": "Your bid must be at least ₹{min}.",
        # server
        "room_not_found": "Room not found.",
        "game_started": "The game has already started.",
        "room_full": "The room is full.",
        "only_host_start": "Only the host can start the game.",
        "only_host_color": "Only the host can choose colours.",
        "voice_long": "The voice message is too long.",
    },
}


def tile_name(lang, idx, tiles=None):
    """City / tile name in `lang`. `tiles` is the list the server sent (falls back to the built-in board)."""
    tl = (tiles or TILES)[int(idx)]
    return tl.get("en") or tl["name"] if lang == "en" else tl["name"]


def tile_label(lang, tl):
    """Same, for a tile dict."""
    return (tl.get("en") or tl["name"]) if lang == "en" else tl["name"]


def deck_name(lang, deck):
    return DECK_NAMES.get(lang, DECK_NAMES["hi"]).get(deck, deck)


def card_text(lang, deck, ci):
    cards = DECK_CARDS[deck]
    c = cards[int(ci) % len(cards)]
    return c["en"] if lang == "en" else c["text"]


def _fill(template, p, lang, names, tiles):
    q = dict(p)
    for k in PLAYER_KEYS:
        if k in q and names and q[k] in names:
            q[k] = names[q[k]]
    if "deck" in q and "ci" in q:
        q["card"] = card_text(lang, q["deck"], q["ci"])
    if "deck" in q:
        q["deck"] = deck_name(lang, q["deck"])
    if "tile" in q:
        q["tile"] = tile_name(lang, q["tile"], tiles)
    try:
        return template.format(**q)
    except (KeyError, IndexError):
        return template


def log_text(lang, entry, names=None, tiles=None):
    """Text of one log line / event. `entry` is {"k": key, "p": params, ...}; an old-style plain string is returned as is."""
    if isinstance(entry, str):
        return entry
    key = entry.get("k")
    table = LOG.get(lang, LOG["hi"])
    if key not in table:
        return entry.get("text", "")
    return _fill(table[key], entry.get("p", {}), lang, names, tiles)


def err_text(lang, key, params=None, fallback=""):
    table = ERR.get(lang, ERR["hi"])
    if key not in table:
        return fallback
    return _fill(table[key], params or {}, lang, None, None)
