import yaml

from tools.config import paths


class GlyphRules:
    @staticmethod
    def load() -> GlyphRules:
        data = yaml.safe_load(paths.CONFIGS_DIR.joinpath('glyphs.yaml').read_bytes())
        x_offsets = data.get('x-offsets', {})
        advances = data.get('advances', {})
        out_of_canvas = list(data.get('out-of-canvas', ()))
        return GlyphRules(
            x_offsets,
            advances,
            out_of_canvas,
        )

    x_offsets: dict[str, int]
    advances: dict[str, int]
    out_of_canvas: list[str]

    def __init__(
            self,
            x_offsets: dict[str, int] | None = None,
            advances: dict[str, int] | None = None,
            out_of_canvas: list[str] | None = None,
    ) -> None:
        self.x_offsets = x_offsets if x_offsets is not None else {}
        self.advances = advances if advances is not None else {}
        self.out_of_canvas = out_of_canvas if out_of_canvas is not None else []

    def save(self) -> None:
        data = {
            'x-offsets': self.x_offsets,
            'advances': self.advances,
            'out-of-canvas': sorted(self.out_of_canvas),
        }
        sections = []
        for section_name, entries in data.items():
            lines = []
            if isinstance(entries, dict):
                for glyph_name, value in entries.items():
                    quoted_name = yaml.safe_dump(glyph_name, allow_unicode=True, default_style="'").strip()
                    lines.append(f'  {quoted_name}: {value}')
                empty_value = '{}'
            else:
                for glyph_name in entries:
                    quoted_name = yaml.safe_dump(glyph_name, allow_unicode=True, default_style="'").strip()
                    lines.append(f'  - {quoted_name}')
                empty_value = '[]'
            if lines:
                sections.append(f'{section_name}:\n' + '\n'.join(lines))
            else:
                sections.append(f'{section_name}: {empty_value}')

        paths.CONFIGS_DIR.mkdir(parents=True, exist_ok=True)
        paths.CONFIGS_DIR.joinpath('glyphs.yaml').write_text(
            '\n\n'.join(sections) + '\n',
            'utf-8',
        )
