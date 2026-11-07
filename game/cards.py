"""Original Chance / Chest cards (own text, not copied from any board game)."""

CHANCE = [
    dict(text="सीधे GO पर जाओ और ₹200 लो।", en="Go straight to GO and collect ₹200.", kind="move_to", value=0),
    dict(text="मुंबई की यात्रा करो। रास्ते में GO पार करो तो ₹200 लो।", en="Take a trip to Mumbai. If you pass GO, collect ₹200.", kind="move_to", value=39),
    dict(text="पटना घूमने जाओ।", en="Go sightseeing in Patna.", kind="move_to", value=13),
    dict(text="3 कदम पीछे जाओ।", en="Move back 3 spaces.", kind="move_rel", value=-3),
    dict(text="सीधे जेल जाओ!", en="Go straight to jail!", kind="jail", value=0),
    dict(text="तेज़ गाड़ी चलाने का जुर्माना ₹50।", en="Speeding fine: pay ₹50.", kind="money", value=-50),
    dict(text="शेयर बाज़ार से ₹150 का लाभ।", en="Stock market profit: collect ₹150.", kind="money", value=150),
    dict(text="जेल से छुट्टी कार्ड (अपने पास रखो)।", en="Get Out of Jail card (keep it).", kind="jail_free", value=0),
    dict(text="हर खिलाड़ी को ₹25 दो।", en="Pay every player ₹25.", kind="pay_each", value=25),
]
CHEST = [
    dict(text="बैंक की भूल से ₹200 मिले।", en="Bank error in your favour: collect ₹200.", kind="money", value=200),
    dict(text="डॉक्टर की फ़ीस ₹50 दो।", en="Doctor's fee: pay ₹50.", kind="money", value=-50),
    dict(text="जन्मदिन! हर खिलाड़ी से ₹10 लो।", en="It's your birthday! Collect ₹10 from every player.", kind="collect_each", value=10),
    dict(text="स्कूल की फ़ीस ₹100 दो।", en="School fees: pay ₹100.", kind="money", value=-100),
    dict(text="पुरानी बीमा राशि ₹100 मिली।", en="Old insurance matured: collect ₹100.", kind="money", value=100),
    dict(text="जेल से छुट्टी कार्ड (अपने पास रखो)।", en="Get Out of Jail card (keep it).", kind="jail_free", value=0),
    dict(text="सीधे जेल जाओ!", en="Go straight to jail!", kind="jail", value=0),
    dict(text="दिवाली बोनस ₹75 मिला।", en="Diwali bonus: collect ₹75.", kind="money", value=75),
]
