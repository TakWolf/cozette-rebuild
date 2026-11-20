from pathlib import Path

PROJECT_ROOT_DIR = Path(__file__).parents[2]

ASSETS_DIR = PROJECT_ROOT_DIR.joinpath('assets')
SFD_DIR = ASSETS_DIR.joinpath('sfd')
CONFIGS_DIR = ASSETS_DIR.joinpath('configs')
GLYPHS_DIR = ASSETS_DIR.joinpath('glyphs')
