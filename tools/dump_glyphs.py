"""One-time migration of upstream SFD glyphs to PNG assets and metric overrides.

Once the build workflow and the PNG assets and configuration are in place,
maintain and build from those resources directly. This script and the SFD sources
are no longer needed for routine builds.
Each run recreates the glyph directory and configuration; this script is a
migration utility, separate from the routine build workflow.
"""

import shutil
from pathlib import Path

from loguru import logger
from pixel_font_knife.bitmap.mono import MonoBitmap
from pixel_font_knife.cmap.file import CmapGlyphFile
from sfdfont import SfdFont, SfdBitmapGlyph, SfdBitmapStrike

from tools.config import paths, manifest
from tools.config.glyph import GlyphRules

CMAP_DIR = paths.GLYPHS_DIR.joinpath('cmap')


def resolve_bitmap(
        glyph_id: int,
        bitmap_strike: SfdBitmapStrike,
        id_to_bitmap_glyphs: dict[int, SfdBitmapGlyph],
        resolved_bitmaps: dict[int, tuple[MonoBitmap, int, int]],
        resolving: set[int],
) -> tuple[MonoBitmap, int, int]:
    """Recursively merge references; return the bitmap and its baseline-space bottom-left (xmin, ymin)."""
    # Cache completed merges; resolving tracks the active recursion chain to detect cycles.
    if glyph_id in resolved_bitmaps:
        return resolved_bitmaps[glyph_id]
    if glyph_id in resolving:
        raise ValueError(f'Cyclic bitmap reference: {glyph_id}')
    resolving.add(glyph_id)

    source = id_to_bitmap_glyphs[glyph_id]
    bitmap = MonoBitmap(bitmap_strike.pixels(source))
    # SFD bounds are inclusive: width = xmax - xmin + 1, and likewise for height.
    x_min, x_max = source.xmin, source.xmax
    y_min, y_max = source.ymin, source.ymax

    for reference in bitmap_strike.references:
        if reference.source != glyph_id:
            continue
        target, target_x_min, target_y_min = resolve_bitmap(
            reference.target, bitmap_strike, id_to_bitmap_glyphs, resolved_bitmaps, resolving,
        )
        # Reference offsets use baseline coordinates: positive x points right and positive y points up.
        target_x_min += reference.x
        target_y_min += reference.y
        target_x_max = target_x_min + target.width - 1
        target_y_max = target_y_min + target.height - 1

        # union() keeps the receiving canvas size, so first expand it to contain both bitmaps.
        if target_x_min < x_min:
            bitmap = bitmap.resize(left=x_min - target_x_min)
            x_min = target_x_min
        if target_x_max > x_max:
            bitmap = bitmap.resize(right=target_x_max - x_max)
            x_max = target_x_max
        if target_y_min < y_min:
            bitmap = bitmap.resize(bottom=y_min - target_y_min)
            y_min = target_y_min
        if target_y_max > y_max:
            bitmap = bitmap.resize(top=target_y_max - y_max)
            y_max = target_y_max

        # Image rows increase downward from the top-left, so subtract top bounds for the y offset.
        bitmap = bitmap.union(target, x=target_x_min - x_min, y=y_max - target_y_max)

    resolving.remove(glyph_id)
    resolved_bitmaps[glyph_id] = bitmap, x_min, y_min
    return resolved_bitmaps[glyph_id]


def dump_glyphs(
        sfd_file_path: Path,
        flavor: str | None,
        glyph_rules: GlyphRules,
) -> None:
    """Extract one SFD, append flavor suffixes to variant filenames, and collect metric overrides."""
    font = SfdFont.load(sfd_file_path)

    assert len(font.bitmap_strikes) == 1
    bitmap_strike = font.bitmap_strikes[0]
    assert bitmap_strike.pixelsize == manifest.FONT_SIZE
    assert bitmap_strike.ascent == manifest.ASCENT
    # SFD descent is a positive length; the configured DESCENT is a negative baseline coordinate.
    assert bitmap_strike.descent == -manifest.DESCENT

    # Match glyph metadata to bitmaps by glyph_id, which is distinct from the Unicode code point.
    id_to_bitmap_glyphs = {
        bitmap_glyph.glyph_id: bitmap_glyph
        for bitmap_glyph in bitmap_strike.glyphs
    }

    resolved_bitmaps = {}
    resolving = set()

    for glyph in font.glyphs:
        code_point = glyph.unicode
        bitmap_glyph = id_to_bitmap_glyphs[glyph.glyph_id]

        glyph_file_name = f'{code_point:04X}'
        if flavor is not None:
            # Follow Knife variant naming, for example: 0037 cross7.png.
            glyph_file_name = f'{glyph_file_name} {flavor}'

        # pixels() decodes only the local bitmap; resolve references before trimming transparent padding.
        bitmap, source_x_min, source_y_min = resolve_bitmap(
            glyph.glyph_id, bitmap_strike, id_to_bitmap_glyphs, resolved_bitmaps, resolving,
        )
        bitmap, padding = bitmap.trim()

        # Adjust the origin after trimming; x_max here is the exclusive right edge.
        x_min = source_x_min + padding.left
        x_max = bitmap.width + x_min
        advance = bitmap_glyph.advance

        if x_min < 0:
            # When building, add this negative offset to both the x bearing and the advance derived from PNG width.
            glyph_rules.x_offsets[glyph_file_name] = x_min
        elif x_min > 0:
            bitmap = bitmap.resize(left=x_min)

        if x_max < advance:
            bitmap = bitmap.resize(right=advance - x_max)
        elif x_max > advance:
            # Keep the overhanging pixels; use this explicit advance instead of deriving it during the build.
            glyph_rules.advances[glyph_file_name] = advance

        # Trimming bottom padding increases the baseline-space y coordinate; y_max is also exclusive.
        y_min = source_y_min + padding.bottom
        y_max = bitmap.height + y_min

        if y_min >= manifest.DESCENT and y_max <= manifest.ASCENT:
            # Place the ink in the fixed 13px em box, preserving its position relative to the baseline.
            bitmap = bitmap.resize(
                top=manifest.ASCENT - y_max,
                bottom=y_min - manifest.DESCENT,
            )
        else:
            top = manifest.ASCENT - y_max
            bottom = y_min - manifest.DESCENT
            # Negative padding indicates overhang: expand equally above and below the em box to preserve placement.
            # For example, a 1px top overhang needs a 15px canvas; the fixed line height remains 13px.
            if top < 0:
                bottom -= top
                top = 0
            if bottom < 0:
                top -= bottom
                bottom = 0
            bitmap = bitmap.resize(top=top, bottom=bottom)

            glyph_rules.out_of_canvas.append(glyph_file_name)

        glyph_file_path = CmapGlyphFile.get_normalized_dir(code_point, CMAP_DIR).joinpath(f'{glyph_file_name}.png')
        glyph_file_path.parent.mkdir(parents=True, exist_ok=True)
        bitmap.save_png(glyph_file_path)
        logger.info('{}', glyph_file_path)


def main() -> None:
    # Recreate the migration outputs, then generate PNGs and rules for both base and variant glyphs.
    if paths.GLYPHS_DIR.exists():
        shutil.rmtree(paths.GLYPHS_DIR)
    CMAP_DIR.mkdir(parents=True)

    glyph_rules = GlyphRules()

    dump_glyphs(
        paths.SFD_DIR.joinpath('Cozette.sfd'),
        None,
        glyph_rules,
    )
    dump_glyphs(
        paths.SFD_DIR.joinpath('CozetteCrossedSeven.sfd'),
        'cross7',
        glyph_rules,
    )

    # Remove an orphaned blank variant entry absent from the base font and unused by the upstream build.
    CMAP_DIR.joinpath('1E0A7 cross7.png').unlink()
    # Upstream sets DEFAULT_CHAR=0; reuse the U+0000 missing-glyph box as a separate .notdef asset.
    CMAP_DIR.joinpath('0000-007F Basic Latin', '0000.png').copy(paths.GLYPHS_DIR.joinpath('notdef.png'))
    glyph_rules.advances['notdef'] = glyph_rules.advances['0000']

    glyph_rules.save()


if __name__ == '__main__':
    main()
