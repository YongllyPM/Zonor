import json
import os
from pathlib import Path

THEMES_DIR = Path(os.environ.get('APPDATA', '')) / 'Zonor' / 'themes'
THEMES_DIR.mkdir(parents=True, exist_ok=True)

BASE_THEMES = {
    'Android Verde': {
        'name': 'Android Verde',
        'bg_primary': '#121314',
        'bg_secondary': '#1e1f22',
        'bg_tertiary': '#26272b',
        'bg_card': '#1e1f22',
        'bg_hover': '#2a2b30',
        'bg_elevated': '#28292d',
        'text_primary': '#e3e2e6',
        'text_secondary': '#c4c6d0',
        'text_muted': '#8a8d96',
        'accent': '#a8eff0',
        'accent_hover': '#8fd6d8',
        'accent_secondary': '#a8c7fa',
        'border': 'rgba(255,255,255,0.07)',
        'shadow': 'rgba(168, 239, 240, 0.30)',
        'player_bg': '#16171a',
        'sidebar_bg': '#121314',
        'input_bg': '#26272b',
        'success': '#7ee08a',
        'warning': '#f6c177',
        'error': '#f19898',
    },
    'Android Azul': {
        'name': 'Android Azul',
        'bg_primary': '#121314',
        'bg_secondary': '#1e1f22',
        'bg_tertiary': '#26272b',
        'bg_card': '#1e1f22',
        'bg_hover': '#2a2b30',
        'bg_elevated': '#28292d',
        'text_primary': '#e3e2e6',
        'text_secondary': '#c4c6d0',
        'text_muted': '#8a8d96',
        'accent': '#a8c7fa',
        'accent_hover': '#8fb0e0',
        'accent_secondary': '#a8eff0',
        'border': 'rgba(255,255,255,0.07)',
        'shadow': 'rgba(168, 199, 250, 0.30)',
        'player_bg': '#16171a',
        'sidebar_bg': '#121314',
        'input_bg': '#26272b',
        'success': '#7ee08a',
        'warning': '#f6c177',
        'error': '#f19898',
    },
    'Android Rosa': {
        'name': 'Android Rosa',
        'bg_primary': '#121314',
        'bg_secondary': '#1e1f22',
        'bg_tertiary': '#26272b',
        'bg_card': '#1e1f22',
        'bg_hover': '#2a2b30',
        'bg_elevated': '#28292d',
        'text_primary': '#e3e2e6',
        'text_secondary': '#c4c6d0',
        'text_muted': '#8a8d96',
        'accent': '#ffb3c1',
        'accent_hover': '#e69cab',
        'accent_secondary': '#ffd3a8',
        'border': 'rgba(255,255,255,0.07)',
        'shadow': 'rgba(255, 179, 193, 0.30)',
        'player_bg': '#16171a',
        'sidebar_bg': '#121314',
        'input_bg': '#26272b',
        'success': '#7ee08a',
        'warning': '#f6c177',
        'error': '#f19898',
    },
    'Android Morado': {
        'name': 'Android Morado',
        'bg_primary': '#121314',
        'bg_secondary': '#1e1f22',
        'bg_tertiary': '#26272b',
        'bg_card': '#1e1f22',
        'bg_hover': '#2a2b30',
        'bg_elevated': '#28292d',
        'text_primary': '#e3e2e6',
        'text_secondary': '#c4c6d0',
        'text_muted': '#8a8d96',
        'accent': '#d0bcff',
        'accent_hover': '#b9a5e8',
        'accent_secondary': '#ffb3c1',
        'border': 'rgba(255,255,255,0.07)',
        'shadow': 'rgba(208, 188, 255, 0.30)',
        'player_bg': '#16171a',
        'sidebar_bg': '#121314',
        'input_bg': '#26272b',
        'success': '#7ee08a',
        'warning': '#f6c177',
        'error': '#f19898',
    },
    'Android Ámbar': {
        'name': 'Android Ámbar',
        'bg_primary': '#121314',
        'bg_secondary': '#1e1f22',
        'bg_tertiary': '#26272b',
        'bg_card': '#1e1f22',
        'bg_hover': '#2a2b30',
        'bg_elevated': '#28292d',
        'text_primary': '#e3e2e6',
        'text_secondary': '#c4c6d0',
        'text_muted': '#8a8d96',
        'accent': '#ffd3a8',
        'accent_hover': '#e6bc90',
        'accent_secondary': '#a8eff0',
        'border': 'rgba(255,255,255,0.07)',
        'shadow': 'rgba(255, 211, 168, 0.30)',
        'player_bg': '#16171a',
        'sidebar_bg': '#121314',
        'input_bg': '#26272b',
        'success': '#7ee08a',
        'warning': '#f6c177',
        'error': '#f19898',
    },
    'Android Blanco': {
        'name': 'Android Blanco',
        'bg_primary': '#121314',
        'bg_secondary': '#1e1f22',
        'bg_tertiary': '#26272b',
        'bg_card': '#1e1f22',
        'bg_hover': '#2a2b30',
        'bg_elevated': '#28292d',
        'text_primary': '#ffffff',
        'text_secondary': '#d6d8dd',
        'text_muted': '#9da0a6',
        'accent': '#ffffff',
        'accent_hover': '#d9d9de',
        'accent_secondary': '#e3e2e6',
        'border': 'rgba(255,255,255,0.08)',
        'shadow': 'rgba(255, 255, 255, 0.25)',
        'player_bg': '#16171a',
        'sidebar_bg': '#121314',
        'input_bg': '#26272b',
        'success': '#7ee08a',
        'warning': '#f6c177',
        'error': '#f19898',
    },
    'Android Negro': {
        'name': 'Android Negro',
        'bg_primary': '#000000',
        'bg_secondary': '#0a0a0c',
        'bg_tertiary': '#111114',
        'bg_card': '#0f0f12',
        'bg_hover': '#16161a',
        'bg_elevated': '#16161a',
        'text_primary': '#f5f5f7',
        'text_secondary': '#c8c9cf',
        'text_muted': '#8f9198',
        'accent': '#ffffff',
        'accent_hover': '#d0d0d6',
        'accent_secondary': '#9aa0a6',
        'border': 'rgba(255,255,255,0.10)',
        'shadow': 'rgba(0, 0, 0, 0.55)',
        'player_bg': '#0a0a0c',
        'sidebar_bg': '#000000',
        'input_bg': '#111114',
        'success': '#7ee08a',
        'warning': '#f6c177',
        'error': '#f19898',
    },
}


def get_themes():
    themes = {}
    themes.update(BASE_THEMES)
    for f in THEMES_DIR.glob('*.json'):
        try:
            with open(str(f)) as fh:
                theme = json.load(fh)
                if 'name' in theme:
                    themes[theme['name']] = theme
        except:
            pass
    return themes


def save_custom_theme(theme_data):
    path = THEMES_DIR / f"{theme_data['name']}.json"
    with open(str(path), 'w') as f:
        json.dump(theme_data, f, indent=2)
    return theme_data


def delete_custom_theme(name):
    path = THEMES_DIR / f"{name}.json"
    if path.exists():
        path.unlink()
        return True
    return False
