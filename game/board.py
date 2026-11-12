"""36-tile "Business India Edition" board (9 tiles a side, four corners). Pure data, no UI.

Tile 0 = START (bottom-left corner). The tokens walk along the bottom row to the right, up the right-hand side, back
along the top row and down the left-hand side, exactly as on the printed board:
    0 START   9 GO TO JAIL   18 INCOME TAX   27 JAIL   (the four corners)
`img` is the file (without .png) in app/assets/tiles/ that holds the picture of the tile. `full=True` means the
picture is a finished card (name and price are part of it) that the app draws whole instead of its own strips.
"""

# colour of each group's tile strip (same colours as the printed board)
GROUP_COLORS = {
    "blue": "#101A5E", "green": "#1E4D38", "yellow": "#E5B02E", "red": "#A30F2C", "orange": "#E8680C",
    "purple": "#6B21B0", "cyan": "#2494A8", "brown": "#9C4B03",
    "station": "#2E9E4F",           # the 3 railway stations (green tiles)
    "utility": "#2B6CC4",           # Coal Factory, Electric Company, Water Works (blue tiles)
    "airport": "#7B3FB5",           # the Airport (purple tile), a set of its own
}
MAX_HOUSES = 3                      # a city takes at most 3 houses; the next building is the hotel
HOTEL = 5                           # value of `houses` that means "hotel" (the levels are 0, 1, 2, 3 and HOTEL)
RENT_MULT = [1, 5, 15, 35, 50, 70]  # index = `houses`: 0..3 houses, 5 = hotel (index 4 is not used any more)
STATION_RENT = 500                  # rent of a station / utility per owned tile of the SAME set: 500 / 1000 / 1500 for 1 / 2 / 3
AIRPORT_RENT_PER_POINT = 100        # Airport: the visitor rolls the two dice again and pays (dice total) x this
TAX_AMOUNT = 500


def _prop(hi, en, price, group, idx):
    base = max(2, price // 12)
    return dict(type="property", name=hi, en=en, price=price, group=group, img=f"t{idx:02d}", full=True,
                rents=[base * m for m in RENT_MULT], house_cost=(price // 100) * 50)


def _other(kind, hi, en, **kw):
    return dict(type=kind, name=hi, en=en, **kw)


# (kind, hindi, english, price, group)  -- "p" = city that can be built on, "s" = railway station, "u" = utility
# (Coal Factory / Electric Company / Water Works), "a" = the Airport
# Names and prices are the ones printed on the new tile pictures (app/assets/tiles/tNN.png).
_raw = [
    ("go", "स्टार्ट", "START"),                                          # 0
    ("p", "मुंबई", "Mumbai", 4000, "blue"),                              # 1
    ("s", "सीएसएमटी मुंबई", "CSMT Mumbai", 2000),                        # 2
    ("p", "नई दिल्ली", "New Delhi", 3500, "blue"),                       # 3
    ("s", "नई दिल्ली रेलवे स्टेशन", "New Delhi Railway Station", 2000),  # 4
    ("p", "दिल्ली", "Delhi", 4500, "blue"),                              # 5
    ("p", "शिमला", "Shimla", 3700, "green"),                             # 6
    ("luck",),                                                          # 7
    ("p", "ऋषिकेश", "Rishikesh", 3800, "green"),                         # 8
    ("gotojail", "जेल जाओ", "Go to Jail"),                               # 9
    ("p", "श्रीनगर", "Srinagar", 3900, "green"),                         # 10
    ("a", "हवाई अड्डा", "Airport", 2500),                                # 11
    ("p", "जयपुर", "Jaipur", 3600, "yellow"),                            # 12
    ("p", "बेंगलुरु", "Bengaluru", 3400, "yellow"),                      # 13
    ("s", "हावड़ा जंक्शन", "Howrah Junction", 2000),                     # 14
    ("p", "गोवा", "Goa", 3300, "yellow"),                                # 15
    ("fortune",),                                                       # 16
    ("p", "आगरा", "Agra", 3200, "red"),                                  # 17
    ("tax", "आयकर", "Income Tax", TAX_AMOUNT),                           # 18
    ("p", "उदयपुर", "Udaipur", 3100, "red"),                             # 19
    ("luck",),                                                          # 20
    ("p", "हैदराबाद", "Hyderabad", 3000, "red"),                         # 21
    ("u", "वाटर वर्क्स", "Water Works", 1500),                           # 22
    ("u", "बिजली कंपनी", "Electric Company", 1500),                      # 23
    ("u", "कोयला कारखाना", "Coal Factory", 2200),                        # 24
    ("p", "चंडीगढ़", "Chandigarh", 2900, "orange"),                      # 25
    ("p", "कोलकाता", "Kolkata", 2800, "orange"),                         # 26
    ("jail", "जेल", "Jail"),                                             # 27
    ("p", "अमृतसर", "Amritsar", 2700, "orange"),                         # 28
    ("p", "पुणे", "Pune", 2400, "magenta"),                              # 29
    ("fortune",),                                                       # 30
    ("p", "कोच्चि", "Kochi", 2500, "magenta"),                           # 31
    ("p", "चेन्नई", "Chennai", 2600, "magenta"),                         # 32
    ("p", "लेह लद्दाख", "Leh Ladakh", 2300, "teal"),                     # 33
    ("p", "मुन्नार", "Munnar", 2100, "teal"),                            # 34
    ("p", "विशाखापत्तनम", "Visakhapatnam", 2250, "teal"),                # 35
]
_GROUP_ALIAS = {"magenta": "purple", "teal": "cyan"}   # card colour -> key in GROUP_COLORS

TILES = []
for i, r in enumerate(_raw):
    k = r[0]
    if k == "p":
        TILES.append(_prop(r[1], r[2], r[3], _GROUP_ALIAS.get(r[4], r[4]), i))
    elif k in ("s", "u", "a"):
        kind = {"s": "station", "u": "utility", "a": "airport"}[k]       # each kind is its own set
        TILES.append(dict(type=kind, name=r[1], en=r[2], price=r[3], group=kind, img=f"t{i:02d}", full=True))
    elif k == "tax":
        TILES.append(_other("tax", r[1], r[2], amount=r[3], img=f"t{i:02d}", full=True))
    elif k == "luck":
        TILES.append(_other("luck", "किस्मत", "Luck", img="luck", full=True))
    elif k == "fortune":
        TILES.append(_other("fortune", "भाग्य", "Fortune", img="fortune", full=True))
    elif k == "go":
        TILES.append(_other(k, r[1], r[2], img=f"t{i:02d}", full=True))
    elif k == "jail":
        TILES.append(_other(k, r[1], r[2], img=f"t{i:02d}", full=True))
    elif k == "gotojail":
        TILES.append(_other(k, r[1], r[2], img=f"t{i:02d}", full=True))
    else:
        TILES.append(_other(k, r[1], r[2]))

N = len(TILES)
assert N == 36
START_POS, GOTOJAIL_POS, TAX_POS, JAIL_POS = 0, 9, 18, 27
assert [TILES[i]["type"] for i in (START_POS, GOTOJAIL_POS, TAX_POS, JAIL_POS)] == ["go", "gotojail", "tax", "jail"]
GROUPS = {}
for i, t in enumerate(TILES):
    if "group" in t:
        GROUPS.setdefault(t["group"], []).append(i)
