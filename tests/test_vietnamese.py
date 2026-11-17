"""Regression checks for Vietnamese Unicode support in source UFOs."""

from pathlib import Path
import unittest

from fontTools.pens.boundsPen import BoundsPen
import ufoLib2

from vietnamese import VIETNAMESE_CODEPOINTS, extend_vietnamese

ROOT = Path(__file__).resolve().parents[1]
SOURCES = [
    "sources/masters/Allo-opsz14-wght400-ROND50.ufo",
    "sources/masters/Allo-opsz32-wght900-ROND100.ufo",
    "sources/static/Allo-Regular.ufo",
    "sources/static/Allo-Oblique.ufo",
]

EXAMPLE = (
    "Tiếng Việt: Trường học, cộng đồng, dự án, "
    "người Việt, chữ Ữ, Ợ, Ậ, ể, ẵ, ỡ, ỷ."
)


def cmap(font):
    return {value: glyph.name for glyph in font for value in glyph.unicodes}


class VietnameseCoverageTests(unittest.TestCase):
    def test_complete_precomposed_unicode_and_bounds(self):
        for source in SOURCES:
            with self.subTest(source=source):
                font = ufoLib2.Font.open(ROOT / source)
                original = set(font.keys())
                self.assertGreater(extend_vietnamese(font), 0)
                unicode_map = cmap(font)

                expected = set(VIETNAMESE_CODEPOINTS)
                expected.update(map(ord, EXAMPLE))
                expected.discard(0x000A)
                missing = expected - set(unicode_map)
                self.assertFalse(missing, f"Unmapped characters: {[hex(n) for n in sorted(missing)]}")

                for codepoint in VIETNAMESE_CODEPOINTS:
                    name = unicode_map[codepoint]
                    glyph = font[name]
                    pen = BoundsPen(font)
                    glyph.draw(pen)
                    self.assertIsNotNone(pen.bounds, f"Empty U+{codepoint:04X} ({source})")
                    if name not in original:
                        low, high = pen.bounds[1], pen.bounds[3]
                        self.assertGreaterEqual(
                            low, -font.info.openTypeOS2WinDescent,
                            f"U+{codepoint:04X} clipped at the bottom ({source})",
                        )
                        self.assertLessEqual(
                            high, font.info.openTypeOS2WinAscent,
                            f"U+{codepoint:04X} clipped at the top ({source})",
                        )

                self.assertEqual(extend_vietnamese(font), 0, "Generation must be idempotent")

    def test_combining_mark_codepoints(self):
        font = ufoLib2.Font.open(ROOT / SOURCES[0])
        extend_vietnamese(font)
        unicode_map = cmap(font)
        for cp in (0x0309, 0x031B, 0x0323):
            with self.subTest(codepoint=hex(cp)):
                self.assertIn(cp, unicode_map)


if __name__ == "__main__":
    unittest.main()
