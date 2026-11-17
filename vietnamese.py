"""Build-time Vietnamese glyph extension for Allo UFO sources.

The original UFO files remain authoritative. This module composes the missing
Vietnamese Unicode characters in memory for every complete designspace master
and static source. It does not mutate files on disk.
"""

from __future__ import annotations

from copy import deepcopy
import unicodedata

from fontTools.pens.boundsPen import BoundsPen
from ufoLib2.objects import Anchor, Component

# Vietnamese Extended Additional: Ạ..ỹ plus the standalone horn vowels.
VIETNAMESE_CODEPOINTS = tuple(
    sorted(set(range(0x1EA0, 0x1EFA)) | {0x01A0, 0x01A1, 0x01AF, 0x01B0})
)

TONE_GLYPHS = {
    "\u0300": "gravecomb",
    "\u0301": "acutecomb",
    "\u0303": "tildecomb",
    "\u0309": "hookabovecomb",
    "\u0323": "dotbelowcomb",
}
SHAPE_MARKS = {"\u0302", "\u0306", "\u031B"}
HORN_NAMES = {"O": "Ohorn", "o": "ohorn", "U": "Uhorn", "u": "uhorn"}


def _anchor(glyph, name):
    return next((a for a in glyph.anchors if a.name == name), None)


def _bounds(font, glyph_name):
    pen = BoundsPen(font)
    font[glyph_name].draw(pen)
    if pen.bounds is None:
        raise ValueError(f"No outlines: {glyph_name}")
    return pen.bounds


def _append_component(glyph, name, x=0, y=0, scale=1):
    glyph.components.append(Component(name, (scale, 0, 0, scale, x, y)))


def _make_marks(font):
    """Draw auxiliary accents by reusing existing, weight-matched outlines."""
    if "hookabovecomb" not in font:
        hook = font.newGlyph("hookabovecomb")
        hook.unicodes = [0x0309]
        # A reduced curved quote is a first-pass hook-above. Review visually.
        _append_component(hook, "quoteright", -130, 590, 0.68)
        hook.anchors.append(Anchor(x=0, y=1118, name="_top"))

    if "dotbelowcomb" not in font:
        dot = font.newGlyph("dotbelowcomb")
        dot.unicodes = [0x0323]
        # Dot above has a matching weight; relocate it below the baseline.
        _append_component(dot, "dotaccentcomb", 0, -1650)
        dot.anchors.append(Anchor(x=236, y=0, name="_bottom"))

    if "horncomb" not in font:
        horn = font.newGlyph("horncomb")
        horn.unicodes = [0x031B]
        # Temporary stylistic horn based on the font's own curved quote.
        _append_component(horn, "quoteright", -65, 0, 0.48)
        horn.anchors.append(Anchor(x=0, y=0, name="_tophorn"))


def _make_horn_vowel(font, character, name):
    if name in font:
        return
    source = font[character]
    glyph = font.newGlyph(name)
    glyph.unicodes = [ord(unicodedata.normalize("NFC", character + "\u031B"))]
    glyph.width = source.width
    glyph.anchors = deepcopy(source.anchors)
    _append_component(glyph, character)

    left, bottom, right, top = _bounds(font, character)
    # Attach the horn to the outer upper-right curve/stem, in this master.
    _append_component(glyph, "horncomb", right - 120, top - 540)


def _unicode_map(font):
    return {cp: glyph.name for glyph in font for cp in glyph.unicodes}


def _add_tone(font, glyph, source, mark_name, stacked):
    if mark_name == "dotbelowcomb":
        anchor = _anchor(source, "bottom")
        if anchor is None:
            raise ValueError(f"Missing bottom anchor: {source.name}")
        mark_anchor = _anchor(font[mark_name], "_bottom")
        _append_component(
            glyph, mark_name, anchor.x - mark_anchor.x, anchor.y - mark_anchor.y
        )
        return

    anchor = _anchor(source, "top")
    if anchor is None:
        raise ValueError(f"Missing top anchor: {source.name}")
    mark_anchor = _anchor(font[mark_name], "_top")
    if not stacked:
        _append_component(
            glyph, mark_name, anchor.x - mark_anchor.x, anchor.y - mark_anchor.y
        )
        return

    # Two marks need to fit the existing Windows ascent (2061 UPM units).
    # Place the smaller tone slightly to the right of the circumflex/breve.
    scale = 0.60
    win_ascent = font.info.openTypeOS2WinAscent
    mark_top = _bounds(font, mark_name)[3]
    desired_top = min(win_ascent - 16, anchor.y + 200)
    _append_component(
        glyph,
        mark_name,
        anchor.x + 105 - scale * mark_anchor.x,
        desired_top - scale * mark_top,
        scale,
    )


def _new_glyph(font, codepoint, source_name, tone_name, stacked):
    name = f"uni{codepoint:04X}"
    if name in font:
        raise ValueError(f"Glyph name already exists without U+{codepoint:04X}: {name}")
    source = font[source_name]
    glyph = font.newGlyph(name)
    glyph.unicodes = [codepoint]
    glyph.width = source.width
    glyph.anchors = deepcopy(source.anchors)
    _append_component(glyph, source_name)
    _add_tone(font, glyph, source, tone_name, stacked)
    return name


def extend_vietnamese(font):
    """Add missing Vietnamese characters; return the number of new glyphs.

    Sparse designspace layers are deliberately untouched: they may only contain
    a subset of the source outlines. Complete masters and static UFOs have the
    required bases and marks.
    """
    required = {
        "A", "a", "E", "e", "I", "i", "O", "o", "U", "u", "Y", "y",
        "quoteright", "dotaccentcomb", "acutecomb", "gravecomb", "tildecomb",
        "Acircumflex", "acircumflex", "Abreve", "abreve",
    }
    if not required.issubset(font.keys()):
        return 0

    before = set(font.keys())
    _make_marks(font)
    for base, name in HORN_NAMES.items():
        _make_horn_vowel(font, base, name)

    mapping = _unicode_map(font)
    for codepoint in VIETNAMESE_CODEPOINTS:
        if codepoint in mapping:
            continue
        decomposition = unicodedata.normalize("NFD", chr(codepoint))
        base, modifiers = decomposition[0], decomposition[1:]
        shape = next((mark for mark in modifiers if mark in SHAPE_MARKS), None)
        tone = next((mark for mark in modifiers if mark in TONE_GLYPHS), None)
        if tone is None or len(modifiers) != (2 if shape else 1):
            raise ValueError(f"Unsupported Vietnamese decomposition: U+{codepoint:04X}")

        # NFD places dot-below before circumflex/breve (combining classes).
        # Select marks by type, not by their position in the sequence.
        stacked = shape in {"\u0302", "\u0306"} and tone != "\u0323"
        if shape is None:
            source_name = "idotless" if base == "i" and tone != "\u0323" else base
        else:
            shaped_character = unicodedata.normalize("NFC", base + shape)
            try:
                source_name = mapping[ord(shaped_character)]
            except KeyError as exc:
                raise ValueError(f"Missing shape base U+{ord(shaped_character):04X}") from exc

        added_name = _new_glyph(
            font, codepoint, source_name, TONE_GLYPHS[tone], stacked
        )
        mapping[codepoint] = added_name

    # Let new characters inherit base kerning groups where possible.
    for group, names in font.groups.items():
        if not group.startswith("public.kern"):
            continue
        for codepoint in VIETNAMESE_CODEPOINTS:
            name = mapping[codepoint]
            if name in before or name in names:
                continue
            base = unicodedata.normalize("NFD", chr(codepoint))[0]
            if base in names:
                names.append(name)

    # Preserve the source-defined order; append generated glyphs consistently.
    generated = sorted(set(font.keys()) - before)
    if "public.glyphOrder" in font.lib:
        order = font.lib["public.glyphOrder"]
        order.extend(name for name in generated if name not in order)
    return len(generated)
