import json
import os
from pathlib import Path

THEMES_DIR = Path(os.environ.get('APPDATA', '')) / 'Zonor' / 'themes'
THEMES_DIR.mkdir(parents=True, exist_ok=True)

BASE_THEMES = {
    'Oscuro': {
        'name': 'Oscuro',
        'bg_primary': '#0a0a0f',
        'bg_secondary': '#12121a',
        'bg_tertiary': '#1a1a2e',
        'bg_card': '#16162b',
        'bg_hover': '#1f1f35',
        'bg_elevated': '#20203a',
        'text_primary': '#e8e8f0',
        'text_secondary': '#9898b8',
        'text_muted': '#5c5c7a',
        'accent': '#7c3aed',
        'accent_hover': '#6d28d9',
        'accent_secondary': '#ec4899',
        'border': '#2a2a45',
        'shadow': 'rgba(124, 58, 237, 0.15)',
        'player_bg': '#12121a',
        'sidebar_bg': '#0f0f18',
        'input_bg': '#1a1a2e',
        'success': '#22c55e',
        'warning': '#f59e0b',
        'error': '#ef4444',
    },
    'Claro': {
        'name': 'Claro',
        'bg_primary': '#f8f9fa',
        'bg_secondary': '#ffffff',
        'bg_tertiary': '#f0f0f5',
        'bg_card': '#ffffff',
        'bg_hover': '#e8e8f0',
        'bg_elevated': '#ffffff',
        'text_primary': '#1a1a2e',
        'text_secondary': '#5c5c7a',
        'text_muted': '#9898b8',
        'accent': '#7c3aed',
        'accent_hover': '#6d28d9',
        'accent_secondary': '#ec4899',
        'border': '#e0e0ea',
        'shadow': 'rgba(124, 58, 237, 0.1)',
        'player_bg': '#ffffff',
        'sidebar_bg': '#f0f0f5',
        'input_bg': '#f0f0f5',
        'success': '#22c55e',
        'warning': '#f59e0b',
        'error': '#ef4444',
    },
    'Azul': {
        'name': 'Azul',
        'bg_primary': '#0b1120',
        'bg_secondary': '#111827',
        'bg_tertiary': '#1e293b',
        'bg_card': '#1a2332',
        'bg_hover': '#253344',
        'bg_elevated': '#1e293b',
        'text_primary': '#e2e8f0',
        'text_secondary': '#94a3b8',
        'text_muted': '#64748b',
        'accent': '#3b82f6',
        'accent_hover': '#2563eb',
        'accent_secondary': '#06b6d4',
        'border': '#334155',
        'shadow': 'rgba(59, 130, 246, 0.15)',
        'player_bg': '#111827',
        'sidebar_bg': '#0b1120',
        'input_bg': '#1e293b',
        'success': '#22c55e',
        'warning': '#f59e0b',
        'error': '#ef4444',
    },
    'Verde': {
        'name': 'Verde',
        'bg_primary': '#0a0f0a',
        'bg_secondary': '#0f1a0f',
        'bg_tertiary': '#1a2e1a',
        'bg_card': '#142214',
        'bg_hover': '#1a301a',
        'bg_elevated': '#1a2e1a',
        'text_primary': '#e0f0e0',
        'text_secondary': '#90b890',
        'text_muted': '#5a7a5a',
        'accent': '#22c55e',
        'accent_hover': '#16a34a',
        'accent_secondary': '#06b6d4',
        'border': '#2a452a',
        'shadow': 'rgba(34, 197, 94, 0.15)',
        'player_bg': '#0f1a0f',
        'sidebar_bg': '#0a0f0a',
        'input_bg': '#1a2e1a',
        'success': '#22c55e',
        'warning': '#f59e0b',
        'error': '#ef4444',
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
