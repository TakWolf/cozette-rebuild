from typing import Literal, get_args

FONT_SIZE = 13  # em size
BASELINE = 10  # from em top
ASCENT = 10
DESCENT = -3

type GlyphFlavor = Literal[
    None,
    'cross7',
]
GLYPH_FLAVORS = list[GlyphFlavor](get_args(GlyphFlavor.__value__))

type FontFormat = Literal[
    'otf',
    'otf.woff',
    'otf.woff2',
    'ttf',
    'ttf.woff',
    'ttf.woff2',
    'ms-bitmap.ttf',
    'otb',
    'dfont',
    'bdf',
    'pcf',
]
FONT_FORMATS = list[FontFormat](get_args(FontFormat.__value__))
