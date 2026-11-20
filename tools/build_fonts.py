import shutil

from loguru import logger
from pixel_font_builder import FontBuilder, Weight, SerifStyle, Spacing, Slant, Glyph, MonoRaster
from pixel_font_knife.cmap.context import CmapContext
from pixel_font_knife.cmap.file import CmapGlyphFile
from pixel_font_knife.named.file import NamedGlyphFile

from tools.config import paths, manifest, project
from tools.config.glyph import GlyphRules


def main() -> None:
    if paths.BUILD_DIR.exists():
        shutil.rmtree(paths.BUILD_DIR)
    paths.OUTPUTS_DIR.mkdir(parents=True)

    notdef_glyph_file = NamedGlyphFile.load_notdef(paths.GLYPHS_DIR.joinpath('notdef.png'))
    cmap_context = CmapContext.load(paths.GLYPHS_DIR.joinpath('cmap'))
    glyph_rules = GlyphRules.load()

    for glyph_flavor in manifest.GLYPH_FLAVORS:
        builder = FontBuilder()
        builder.font_metric.font_size = manifest.FONT_SIZE
        builder.font_metric.horizontal_layout.ascent = manifest.ASCENT
        builder.font_metric.horizontal_layout.descent = manifest.DESCENT
        builder.opentype_config.has_vertical_metrics = False

        builder.meta_info.version = project.VERSION
        builder.meta_info.family_name = f'{project.FAMILY_NAME_PREFIX}'
        if glyph_flavor is not None:
            builder.meta_info.family_name = f'{builder.meta_info.family_name} {glyph_flavor.capitalize()}'
        builder.meta_info.weight = Weight.REGULAR
        builder.meta_info.serif_style = SerifStyle.SANS_SERIF
        builder.meta_info.spacing = Spacing.DUOSPACED
        builder.meta_info.slant = Slant.UPRIGHT
        builder.meta_info.manufacturer = project.MANUFACTURER
        builder.meta_info.designer = project.DESIGNER
        builder.meta_info.description = project.DESCRIPTION
        builder.meta_info.copyright_info = project.COPYRIGHT_INFO
        builder.meta_info.license_info = project.LICENSE_INFO
        builder.meta_info.vendor_url = project.HOMEPAGE_URL
        builder.meta_info.designer_url = project.DESIGNER_URL
        builder.meta_info.license_url = project.LICENSE_URL

        glyph_sequence = [notdef_glyph_file] + cmap_context.get_glyph_sequence(glyph_flavor)
        for glyph_file in glyph_sequence:
            advance_width = glyph_file.canvas.advance_width()
            horizontal_offset_x, horizontal_offset_y = glyph_file.suggest_horizontal_offset(manifest.FONT_SIZE, manifest.BASELINE)

            glyph_key = glyph_file.file_path.stem

            horizontal_offset_x_ex = glyph_rules.x_offsets.get(glyph_key, 0)
            advance_width += horizontal_offset_x_ex
            horizontal_offset_x += horizontal_offset_x_ex

            advance_width = glyph_rules.advances.get(glyph_key, advance_width)

            builder.glyphs.append(Glyph(
                name=glyph_file.glyph_name,
                advance_width=advance_width,
                mono_raster=MonoRaster(
                    horizontal_offset=(horizontal_offset_x, horizontal_offset_y),
                    bitmap=glyph_file.suggest_bitmap(),
                ),
            ))

        character_mapping = cmap_context.get_character_mapping(glyph_flavor)
        builder.character_mapping.update(character_mapping)

        font_file_name = project.FILE_NAME_PREFIX
        if glyph_flavor is not None:
            font_file_name = f'{font_file_name}-{glyph_flavor}'

        for font_format in manifest.FONT_FORMATS:
            font_file_path = paths.OUTPUTS_DIR.joinpath(f'{font_file_name}.{font_format}')
            getattr(builder, f'save_{font_format.replace('.', '_').replace('-', '_')}')(font_file_path)
            logger.info('Make font: {!r}', str(font_file_path))


if __name__ == '__main__':
    main()
