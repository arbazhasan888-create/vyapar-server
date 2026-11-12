"""Luck and Fortune cards of the Business India Edition board.

When a token lands on a Luck / Fortune tile the player's two dice are rolled once more and the total (2..12)
decides which line of the card applies - the same table that is printed in the middle of the board.
Index 0 of each list is the line for a total of 2, index 10 the line for 12.

kind / value:
    money         +value from the bank, -value to the bank
    collect_each  collect `value` from every other player
    collect_one   collect `value` from one other player (the richest one)
    repairs       value = (per house, per hotel), paid to the bank
    holiday       pay `value` to the bank
    jail          go to jail
"""

LUCK = [
    dict(text="क्विज़ प्रतियोगिता जीती! बैंक से ₹500 लो।", en="You have won a Quiz Competition, collect ₹500 from the bank.", kind="money", value=500),
    dict(text="आग से नुकसान, बैंक को ₹1000 दो।", en="Loss due to fire, pay ₹1000 to the bank.", kind="money", value=-1000),
    dict(text="वर्ष के निर्यातक का पुरस्कार, बैंक से ₹1500 लो।", en="Prize for Exporter of the Year, collect ₹1500 from the bank.", kind="money", value=1500),
    dict(text="शेयर बाज़ार में नुकसान, बैंक को ₹1250 दो।", en="Loss in Share Market, pay ₹1250 to the bank.", kind="money", value=-1250),
    dict(text="आपका जन्मदिन है, हर खिलाड़ी से ₹250 लो।", en="It is your birthday, collect ₹250 from each player.", kind="collect_each", value=250),
    dict(text="पुलिस ने जुर्माना किया, बैंक को ₹500 दो।", en="Fined by Police, pay ₹500 to the bank.", kind="money", value=-500),
    dict(text="शेयरों पर लाभांश मिला, बैंक से ₹1000 लो।", en="Receive dividend on Shares, collect ₹1000 from the bank.", kind="money", value=1000),
    dict(text="इलाज का बिल, बैंक को ₹750 दो।", en="Pay Medical Bill ₹750 to the bank.", kind="money", value=-750),
    dict(text="कॉपीराइट उल्लंघन पर मुकदमा, किसी एक खिलाड़ी से ₹750 लो।", en="Sue for copyright infringement, collect ₹750 from any player.", kind="collect_one", value=750),
    dict(text="जेल जाओ।", en="Go to Jail.", kind="jail", value=0),
    dict(text="दिया हुआ कर्ज़ वापस मिला, बैंक से ₹1250 लो।", en="Loan given received back, collect ₹1250 from the bank.", kind="money", value=1250),
]
FORTUNE = [
    dict(text="कर्ज़ पर ब्याज, बैंक को ₹1000 दो।", en="Pay Interest on Loan ₹1000 to the bank.", kind="money", value=-1000),
    dict(text="लॉटरी जीती, बैंक से ₹1250 लो।", en="Win the Lottery, collect ₹1250 from the bank.", kind="money", value=1250),
    dict(text="जेल जाओ।", en="Go to Jail.", kind="jail", value=0),
    dict(text="आयकर रिफ़ंड, बैंक से ₹1000 लो।", en="Collect Income Tax Refund ₹1000 from the bank.", kind="money", value=1000),
    dict(text="बच्चे की स्कूल फ़ीस, बैंक को ₹1250 दो।", en="Pay child's School Fees ₹1250 to the bank.", kind="money", value=-1250),
    dict(text="शादी का तोहफ़ा मिला, हर खिलाड़ी से ₹500 लो।", en="Received Wedding Gift ₹500 from Each player.", kind="collect_each", value=500),
    dict(text="मरम्मत: हर मकान के ₹50, हर होटल के ₹100 दो।", en="Make repairs: Each House ₹50, Each Hotel ₹100.", kind="repairs", value=(50, 100)),
    dict(text="त्योहार बोनस, बैंक से ₹1000 लो।", en="Receive Festival Bonus ₹1000 from the bank.", kind="money", value=1000),
    dict(text="बीमा प्रीमियम, बैंक को ₹500 दो।", en="Pay Insurance Premium ₹500 to the bank.", kind="money", value=-500),
    dict(text="फिक्स्ड डिपॉजिट पर ब्याज, बैंक से ₹750 लो।", en="Interest earned on Fixed Deposit, Collect ₹750 from the bank.", kind="money", value=750),
    dict(text="छुट्टी पर जाओ, बैंक को ₹3000 दो।", en="Go to a Holiday, pay ₹3000 to the bank.", kind="holiday", value=3000),
]
