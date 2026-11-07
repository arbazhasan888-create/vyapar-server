"""40-tile board with Indian cities. Pure data, no UI."""

GROUP_COLORS = {
    "brown": "#8B5A2B", "sky": "#87CEEB", "pink": "#E75480", "orange": "#F28C28",
    "red": "#E53935", "yellow": "#FDD835", "green": "#2E9E4F", "blue": "#1E4FD8",
    "station": "#555555", "utility": "#999999",
}
RENT_MULT = [1, 5, 15, 35, 50, 70]  # 0 houses .. 4 houses, 5 = hotel


def _prop(hi, en, price, group, idx):
    base = max(2, price // 12)
    house = 50 if idx < 10 else 100 if idx < 20 else 150 if idx < 30 else 200
    return dict(type="property", name=hi, en=en, price=price, group=group,
                rents=[base * m for m in RENT_MULT], house_cost=house)


def _other(kind, hi, en, **kw):
    return dict(type=kind, name=hi, en=en, **kw)


_raw = [
    ("go", "गो", "GO"),
    ("p", "गुवाहाटी", "Guwahati", 60, "brown"),
    ("chest",),
    ("p", "भुवनेश्वर", "Bhubaneswar", 60, "brown"),
    ("tax", "आयकर", "Income Tax", 200),
    ("station",),
    ("p", "पणजी", "Panaji", 100, "sky"),
    ("chance",),
    ("p", "आगरा", "Agra", 100, "sky"),
    ("p", "वडोदरा", "Vadodara", 120, "sky"),
    ("jail", "जेल (दर्शन)", "Just Visiting"),
    ("p", "लुधियाना", "Ludhiana", 140, "pink"),
    ("util", "बिजली", "Electricity"),
    ("p", "पटना", "Patna", 140, "pink"),
    ("p", "भोपाल", "Bhopal", 160, "pink"),
    ("station",),
    ("p", "इंदौर", "Indore", 160, "orange"),
    ("chest",),
    ("p", "नागपुर", "Nagpur", 180, "orange"),
    ("p", "कोच्चि", "Kochi", 200, "orange"),
    ("free", "मुफ़्त पार्किंग", "Free Parking"),
    ("p", "लखनऊ", "Lucknow", 220, "red"),
    ("chance",),
    ("p", "चंडीगढ़", "Chandigarh", 220, "red"),
    ("p", "जयपुर", "Jaipur", 240, "red"),
    ("station",),
    ("p", "पुणे", "Pune", 260, "yellow"),
    ("p", "हैदराबाद", "Hyderabad", 260, "yellow"),
    ("util", "पानी", "Water"),
    ("p", "अहमदाबाद", "Ahmedabad", 280, "yellow"),
    ("gotojail", "जेल जाओ", "Go To Jail"),
    ("p", "कोलकाता", "Kolkata", 300, "green"),
    ("p", "चेन्नई", "Chennai", 300, "green"),
    ("chest",),
    ("p", "बेंगलुरु", "Bengaluru", 320, "green"),
    ("station",),
    ("chance",),
    ("p", "दिल्ली", "Delhi", 350, "blue"),
    ("tax", "सुपर टैक्स", "Super Tax", 100),
    ("p", "मुंबई", "Mumbai", 400, "blue"),
]

TILES = []
for i, r in enumerate(_raw):
    k = r[0]
    if k == "p":
        TILES.append(_prop(r[1], r[2], r[3], r[4], i))
    elif k == "station":
        TILES.append(dict(type="station", name="स्टेशन", en="Station", price=200, group="station"))
    elif k == "util":
        TILES.append(dict(type="utility", name=r[1], en=r[2], price=150, group="utility"))
    elif k == "tax":
        TILES.append(_other("tax", r[1], r[2], amount=r[3]))
    elif k == "chest":
        TILES.append(_other("chest", "किस्मत", "Luck"))
    elif k == "chance":
        TILES.append(_other("chance", "अवसर", "Chance"))
    else:
        TILES.append(_other(k, r[1], r[2]))

N = len(TILES)
assert N == 40
GROUPS = {}
for i, t in enumerate(TILES):
    if "group" in t:
        GROUPS.setdefault(t["group"], []).append(i)
