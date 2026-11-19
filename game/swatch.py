"""Colour boxes inside hint texts.

A hint sentence names a colour set ("yellow", "dark blue", "station" ...). The sentence is built as plain text, so
each colour name is followed by ONE private-use marker character. The Hint window (app.main.HintPopup) turns every
marker into a small coloured box drawn right after the name. No Kivy in here: it can be tested on its own.
"""
import re

GAP = "\u00a0"                                   # no-break space: the room the box is drawn in
GROUP_ORDER = ("orange", "red", "yellow", "blue", "cyan", "purple", "brown", "station", "utility", "airport")
SWATCH_CHARS = {g: chr(0xE010 + i) for i, g in enumerate(GROUP_ORDER)}   # group -> marker character
CHAR_GROUP = {c: g for g, c in SWATCH_CHARS.items()}                     # marker character -> group
SWATCH_RE = re.compile("[" + SWATCH_CHARS[GROUP_ORDER[0]] + "-" + SWATCH_CHARS[GROUP_ORDER[-1]] + "]")


def with_swatch(name, group):
    """`name` (the colour's word in the player's language) followed by the marker of `group`.
    A group without a colour (None, unknown) gives the plain name."""
    c = SWATCH_CHARS.get(group)
    return f"{name}{GAP}{c}" if c else name


def markers_to_refs(markup, width=5, font=None):
    """In text that is already markup-safe: every marker becomes a [ref=sw:<group>] zone holding `width` no-break
    spaces (the zone Kivy reports back in Label.refs, where the box is drawn). `font` = a font that certainly has the
    space glyph (the Latin font), so the zone has a width whatever the language is."""
    inner = GAP * width
    if font:
        inner = f"[font={font}]{inner}[/font]"
    return SWATCH_RE.sub(lambda m: f"[ref=sw:{CHAR_GROUP[m.group()]}]{inner}[/ref]", markup)


def strip_markers(text):
    """The text without the markers (for plain places: toasts, logs, tests)."""
    return SWATCH_RE.sub("", text).replace(GAP + GAP, GAP) if text else text
