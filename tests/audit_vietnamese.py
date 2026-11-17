#!/usr/bin/env python3
"""Audit Vietnamese Unicode coverage in the original, unmodified Allo UFOs.

This audit intentionally NEVER calls extend_vietnamese(): generated glyphs
must not mask the gaps we are trying to identify in the actual source.
"""
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
import unicodedata

import ufoLib2

ROOT = Path(__file__).resolve().parents[1]
VOWELS = ("a", "ă", "â", "e", "ê", "i", "o", "ô", "ơ", "u", "ư", "y")
TONES = ("", "\u0300", "\u0301", "\u0309", "\u0303", "\u0323")


def vietnamese_letters():
    """146 precomposed Vietnamese letters: 12 vowels x 6 tones x 2 cases + Đ/đ."""
    letters = {}
    for vowel in VOWELS:
        for case in (vowel.upper(), vowel):
            for tone in TONES:
                char = unicodedata.normalize("NFC", case + tone)
                if len(char) != 1:
                    raise ValueError(f"Not a precomposed Unicode character: {case!r} + {tone!r}")
                letters[ord(char)] = vowel
    letters[ord("Đ")] = "đ"
    letters[ord("đ")] = "đ"
    if len(letters) != 146:
        raise AssertionError(f"Unexpected Vietnamese alphabet size: {len(letters)}")
    return letters


REQUIRED = vietnamese_letters()


def missing_in_font(font):
    mapped = {cp for glyph in font for cp in glyph.unicodes}
    return frozenset(REQUIRED) - mapped


def scan_sources():
    paths = sorted((ROOT / "sources/masters").glob("*.ufo"))
    paths += sorted((ROOT / "sources/static").glob("*.ufo"))
    if not paths:
        raise RuntimeError("No UFO source files found")
    results = []
    for path in paths:
        font = ufoLib2.Font.open(path)
        results.append((path.relative_to(ROOT).as_posix(), missing_in_font(font)))
    return results


def format_codepoints(values):
    return ", ".join(f"U+{cp:04X}" for cp in sorted(values))


def render_report(results):
    common_missing = set.intersection(*(set(missing) for _, missing in results))
    all_missing = set.union(*(set(missing) for _, missing in results))
    profiles = Counter(tuple(sorted(missing)) for _, missing in results)
    lines = [
        "# Vietnamese glyph coverage — original UFO sources",
        "",
        "This audit scans the **unchanged UFO source glyph mappings before build-time",
        "Vietnamese glyph generation**. Passing a font-build test does not imply that",
        "the original sources contain these characters.",
        "",
        "**Scope:** 146 Vietnamese NFC precomposed letters (12 vowel forms × 6 tones ×",
        "uppercase/lowercase, plus Đ/đ). This is Unicode coverage, **not visual QA**",
        "or a full OpenType mark-positioning test.",
        "",
        f"- Sources inspected: **{len(results)}**",
        f"- Source coverage in every inspected font: **{146 - len(all_missing)}/146**",
        f"- Characters missing in every inspected source: **{len(common_missing)}**",
        f"- Characters missing in at least one source: **{len(all_missing)}**",
        f"- Distinct source coverage profiles: **{len(profiles)}**",
        "",
        "## Missing glyphs grouped by Vietnamese vowel",
        "",
        "| Vowel | Missing uppercase | Missing lowercase | Unicode code points |",
        "|---|---|---|---|",
    ]
    for vowel in VOWELS:
        group = {cp for cp, form in REQUIRED.items() if form == vowel}
        missing = common_missing & group
        upper = "".join(chr(cp) for cp in sorted(missing) if chr(cp).isupper())
        lower = "".join(chr(cp) for cp in sorted(missing) if chr(cp).islower())
        lines.append(
            f"| {vowel} | {upper or '—'} | {lower or '—'} | {format_codepoints(missing) or '—'} |"
        )
    d_missing = common_missing & {ord("Đ"), ord("đ")}
    lines.append(f"| đ | {('Đ' if ord('Đ') in d_missing else '—')} | "
                 f"{('đ' if ord('đ') in d_missing else '—')} | "
                 f"{format_codepoints(d_missing) or '—'} |")
    lines += [
        "",
        "## Coverage differences between UFO sources",
        "",
    ]
    if len(profiles) == 1:
        lines.append("All inspected UFOs have the same Vietnamese code point coverage.")
    else:
        lines.extend([
            "| Source | Missing |",
            "|---|---:|",
        ])
        for path, missing in results:
            lines.append(f"| {path} | {len(missing)} |")
        lines.extend([
            "",
            "### Code points missing in some, but not all sources",
            "",
            format_codepoints(all_missing - common_missing),
        ])
    lines += [
        "",
        "## Limitations",
        "",
        "- This checks mapped glyphs in UFO sources, not the released OTF/TTF/WOFF2 files.",
        "- A mapped glyph might still have incorrect outlines, accent placement, spacing or kerning.",
        "- Decomposed text (NFD), combining-mark positioning and stylistic alternates require",
        "  additional shaping tests and type-design review.",
        "",
    ]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Write a Markdown audit report to this file")
    parser.add_argument(
        "--strict", action="store_true",
        help="Exit with a failure if any source is missing a required Vietnamese letter",
    )
    args = parser.parse_args()
    results = scan_sources()
    report = render_report(results)
    print(report)
    if args.output:
        args.output.write_text(report, encoding="utf-8")
    if args.strict and any(missing for _, missing in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
