# Cozette Rebuild

This project implements one possible solution to
[Cozette #227: FontForgectomy](https://github.com/the-moonwitch/Cozette/issues/227).
It moves glyph editing and font generation away from a single FontForge file,
using individual **PNG glyph files** in place of the text grids proposed in the
issue. The workflow follows [Ark Pixel Font](https://github.com/TakWolf/ark-pixel-font).

PNGs can be edited directly in a pixel editor such as Aseprite, with the result
visible immediately at its actual pixel proportions. Text grids are easy to
modify, but their appearance depends on the editor's font and line spacing.
Half-width character cells and gaps between lines can make the glyph look
flattened or otherwise distorted, regardless of the symbols used for pixels.

[Pixel Font Knife](https://github.com/TakWolf/pixel-font-knife) provides shared
conventions for glyph naming, bitmap placement, and variant selection.
[Pixel Font Builder](https://github.com/TakWolf/pixel-font-builder) exposes a
unified Python API for pixel fonts. The same glyph and metric records can be
exported directly to multiple outline, web, and bitmap font formats. Together
with PNG editing, this lets both the design and build stages operate independently
of FontForge. These libraries keep the build code focused on assembling assets
and applying Cozette's metric exceptions.

To keep this demonstration easy to read, the implementation deliberately keeps
the code and workflow small. It omits comprehensive glyph validation, vertical
layout metrics, and OpenType feature definitions. Most of these facilities are
also absent from the existing Cozette workflow. This is the scope of the current
demonstration; the toolchain can be extended to include these capabilities as
needed.

## One-time glyph extraction

[`tools/dump_glyphs.py`](tools/dump_glyphs.py) migrates the existing SFD sources to
PNG assets and a YAML configuration. It uses
[sfdfont](https://github.com/TakWolf/sfdfont-python) to read the bitmap strike,
recursively merges referenced glyphs, and preserves their original placement.
For example, the source stores `が` as its own voicing mark plus a reference to
`か`; the exported PNG contains the complete glyph.

```shell
uv run -m tools.dump_glyphs
```

The script extracts the base font and CrossedSeven overrides, creates the
`.notdef` asset, and records the metric information that PNG dimensions alone
cannot express. Running it recreates the glyph directory and configuration.

**Extraction is a one-time migration.** Once the PNG assets and build workflow
are established, maintain those resources directly. Routine builds no longer
need this script or the SFD sources.

## Resource conventions

```text
assets/
├── sfd/                          # Inputs for the one-time extraction
│   ├── Cozette.sfd
│   └── CozetteCrossedSeven.sfd
├── glyphs/
│   ├── notdef.png                # Missing-glyph image
│   └── cmap/
│       └── 0000-007F Basic Latin/
│           ├── 0030.png
│           ├── 0037.png
│           └── 0037 cross7.png
└── configs/
    └── glyphs.yaml               # Metric overrides and canvas exceptions
```

### Names and variants

Glyph filenames start with the uppercase hexadecimal Unicode code point, padded
to at least four digits. Pixel Font Knife organizes them into Unicode block
directories. An optional space and flavor suffix identifies a variant:

- `0037.png` is the base digit seven.
- `0037 cross7.png` is its CrossedSeven variant.

When building the `cross7` family, Knife selects a variant where one exists and
inherits the base glyph otherwise. Only the overridden glyphs need additional
PNG files. Configuration keys use the filename without `.png`, including any
flavor suffix, such as `'0037 cross7'`.

`notdef.png` is separate from the Unicode mapping directory. It is copied from
the source font's default character, U+0000, and has its own metric rule.

### Pixels and canvas placement

Each PNG pixel represents one font pixel. Filled pixels are opaque black and
the background is transparent. Transparent canvas padding carries layout
information, so editing a glyph includes maintaining its canvas and placement.

Cozette uses a fixed **13px em size and line height**, with ascent **10px** and
descent **-3px**. The baseline is 10px from the em top. A normal canvas therefore
covers baseline-space rows `-3..9`, inclusive. Glyphs retain their positions
relative to that baseline; their ink bounding boxes are not independently
recentered.

If a glyph extends vertically beyond the em box, add equal space above and
below it. This keeps the em box centered and lets Knife recover the original
vertical placement. For example, a 1px top overhang uses a 15px canvas while the
font's line height stays 13px. Canvas heights follow `13 + 2 × padding`.

Horizontally, the canvas includes the glyph's left spacing and extends toward
its advance boundary. Overhanging pixels are preserved. Negative left bearings
and advances that differ from the width-based calculation are recorded in YAML.
Empty glyphs can use positive-size transparent PNGs with explicit advances,
including zero.

### Metric configuration

[`assets/configs/glyphs.yaml`](assets/configs/glyphs.yaml) contains three groups:

```yaml
x-offsets:
  '0272': -1

advances:
  '0000': 6
  'notdef': 6

out-of-canvas:
  - '1CC0A'
  - 'FF9F'
```

- `x-offsets` restores negative horizontal placement and adjusts the advance
  derived from the PNG width.
- `advances` provides explicit advance values, taking precedence over the
  width-based calculation.
- `out-of-canvas` records glyphs that require a canvas taller than the normal
  13px em box. These glyphs are exported normally.

Glyph identifiers are quoted strings. `GlyphRules` loads and saves this
configuration, keeping bitmap editing separate from the exceptional metrics.

Some existing Cozette glyphs do not fit the intended duospaced layout of 6px and
12px cells cleanly. Many have a 6px advance but an ink bounding box 7px wide.
The migration preserves these shapes and their original metrics, accounting for
many of the exception entries. These glyphs may need correction in a later design
pass. As they are corrected to fit the intended cells, the corresponding metric
overrides can be removed and the configuration simplified.

## Font construction

Requires Python **3.15 or newer** and [uv](https://docs.astral.sh/uv/).
Run from the project root:

```shell
uv sync
uv run -m tools.build_fonts
```

[`tools/build_fonts.py`](tools/build_fonts.py) reads the PNGs and YAML directly.
It requires neither FontForge nor Java. The pipeline is:

```text
PNG assets + YAML rules
        ↓ Pixel Font Knife
Selected glyphs, trimmed bitmaps, and placement
        ↓ Apply metric overrides
Glyph / MonoRaster records
        ↓ Pixel Font Builder
Font files
```

For each family, Knife selects the appropriate glyph files. The build uses the
full PNG canvas width as the initial advance and obtains the trimmed bitmap's
baseline offset from Knife. It then restores the exceptional metrics:

```python
glyph_key = glyph_file.file_path.stem
x_offset = glyph_rules.x_offsets.get(glyph_key, 0)

advance_width += x_offset
horizontal_offset_x += x_offset
advance_width = glyph_rules.advances.get(glyph_key, advance_width)
```

For example, a 7px-wide `0272.png` with an x offset of `-1` restores an advance
of 6px. An explicit `advances` entry is the final value. Using canvas width as
the starting point also preserves source advances for combining characters.

The rule key comes from the **actual selected file**. An inherited `0272.png`
uses the `'0272'` rules even while building the `cross7` family. The same process
applies the `'notdef'` override, preserving its 6px advance.

The resulting `Glyph` records contain the restored advance, baseline offset,
and complete bitmap. Pixel Font Builder exports the base and `cross7` families
to outline, web, and bitmap font formats in `build/outputs/`. Each build recreates
`build/`. Layout and output formats are configured in
[`manifest.py`](tools/config/manifest.py); font metadata is configured in
[`project.py`](tools/config/project.py).

### Pixel Font Builder API

The API separates font metadata and global metrics from individual glyphs.
Each `Glyph` supplies its advance, and `MonoRaster` supplies the pixel matrix and
its position relative to the baseline. `character_mapping` connects Unicode
code points to glyph names. Output methods then write the desired formats:

```python
from pixel_font_builder import FontBuilder, Glyph, MonoRaster

builder = FontBuilder()
builder.meta_info.family_name = 'Pixel Example'
builder.font_metric.font_size = 13
builder.font_metric.horizontal_layout.ascent = 10
builder.font_metric.horizontal_layout.descent = -3
builder.opentype_config.has_vertical_metrics = False

builder.glyphs.append(Glyph(name='.notdef', advance_width=6))
builder.glyphs.append(Glyph(
    name='A',
    advance_width=6,
    mono_raster=MonoRaster(
        horizontal_offset=(1, 0),
        bitmap=[
            [0, 1, 0],
            [1, 0, 1],
            [1, 1, 1],
            [1, 0, 1],
        ],
    ),
))
builder.character_mapping[0x0041] = 'A'

builder.save_ttf('example.ttf')
builder.save_otf('example.otf')
builder.save_bdf('example.bdf')
```

The bitmap rows run from top to bottom; `0` is empty and `1` is filled.
`horizontal_offset` places the bitmap's bottom-left corner in baseline
coordinates, with positive x to the right and positive y upward. A `.notdef`
glyph is required; this minimal example uses an empty one. The Cozette build
supplies its extracted missing-glyph image and complete glyph set through the
same API.

The original font credits and MIT license are retained; see [LICENSE](LICENSE).
