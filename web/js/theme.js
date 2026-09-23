let currentThemeData = null;
let currentThemeName = 'Android Verde';

const THEMES = {
  'Android Verde': {
    colors: {
      bg_primary: '#121314', bg_secondary: '#1e1f22', bg_tertiary: '#26272b',
      bg_card: '#1e1f22', bg_hover: '#2a2b30', bg_elevated: '#28292d',
      text_primary: '#e3e2e6', text_secondary: '#c4c6d0', text_muted: '#8a8d96',
      accent: '#a8eff0', accent_hover: '#8fd6d8', accent_secondary: '#a8c7fa',
      border: 'rgba(255,255,255,0.07)', shadow: 'rgba(168, 239, 240, 0.30)',
      player_bg: '#16171a', sidebar_bg: '#121314', input_bg: '#26272b',
      success: '#7ee08a', warning: '#f6c177', error: '#f19898',
    },
  },
  'Android Azul': {
    colors: {
      bg_primary: '#121314', bg_secondary: '#1e1f22', bg_tertiary: '#26272b',
      bg_card: '#1e1f22', bg_hover: '#2a2b30', bg_elevated: '#28292d',
      text_primary: '#e3e2e6', text_secondary: '#c4c6d0', text_muted: '#8a8d96',
      accent: '#a8c7fa', accent_hover: '#8fb0e0', accent_secondary: '#a8eff0',
      border: 'rgba(255,255,255,0.07)', shadow: 'rgba(168, 199, 250, 0.30)',
      player_bg: '#16171a', sidebar_bg: '#121314', input_bg: '#26272b',
      success: '#7ee08a', warning: '#f6c177', error: '#f19898',
    },
  },
  'Android Rosa': {
    colors: {
      bg_primary: '#121314', bg_secondary: '#1e1f22', bg_tertiary: '#26272b',
      bg_card: '#1e1f22', bg_hover: '#2a2b30', bg_elevated: '#28292d',
      text_primary: '#e3e2e6', text_secondary: '#c4c6d0', text_muted: '#8a8d96',
      accent: '#ffb3c1', accent_hover: '#e69cab', accent_secondary: '#ffd3a8',
      border: 'rgba(255,255,255,0.07)', shadow: 'rgba(255, 179, 193, 0.30)',
      player_bg: '#16171a', sidebar_bg: '#121314', input_bg: '#26272b',
      success: '#7ee08a', warning: '#f6c177', error: '#f19898',
    },
  },
  'Android Morado': {
    colors: {
      bg_primary: '#121314', bg_secondary: '#1e1f22', bg_tertiary: '#26272b',
      bg_card: '#1e1f22', bg_hover: '#2a2b30', bg_elevated: '#28292d',
      text_primary: '#e3e2e6', text_secondary: '#c4c6d0', text_muted: '#8a8d96',
      accent: '#d0bcff', accent_hover: '#b9a5e8', accent_secondary: '#ffb3c1',
      border: 'rgba(255,255,255,0.07)', shadow: 'rgba(208, 188, 255, 0.30)',
      player_bg: '#16171a', sidebar_bg: '#121314', input_bg: '#26272b',
      success: '#7ee08a', warning: '#f6c177', error: '#f19898',
    },
  },
  'Android Ámbar': {
    colors: {
      bg_primary: '#121314', bg_secondary: '#1e1f22', bg_tertiary: '#26272b',
      bg_card: '#1e1f22', bg_hover: '#2a2b30', bg_elevated: '#28292d',
      text_primary: '#e3e2e6', text_secondary: '#c4c6d0', text_muted: '#8a8d96',
      accent: '#ffd3a8', accent_hover: '#e6bc90', accent_secondary: '#a8eff0',
      border: 'rgba(255,255,255,0.07)', shadow: 'rgba(255, 211, 168, 0.30)',
      player_bg: '#16171a', sidebar_bg: '#121314', input_bg: '#26272b',
      success: '#7ee08a', warning: '#f6c177', error: '#f19898',
    },
  },
  'Android Blanco': {
    colors: {
      bg_primary: '#121314', bg_secondary: '#1e1f22', bg_tertiary: '#26272b',
      bg_card: '#1e1f22', bg_hover: '#2a2b30', bg_elevated: '#28292d',
      text_primary: '#ffffff', text_secondary: '#d6d8dd', text_muted: '#9da0a6',
      accent: '#ffffff', accent_hover: '#d9d9de', accent_secondary: '#e3e2e6',
      border: 'rgba(255,255,255,0.08)', shadow: 'rgba(255, 255, 255, 0.25)',
      player_bg: '#16171a', sidebar_bg: '#121314', input_bg: '#26272b',
      success: '#7ee08a', warning: '#f6c177', error: '#f19898',
    },
  },
  'Android Negro': {
    colors: {
      bg_primary: '#000000', bg_secondary: '#0a0a0c', bg_tertiary: '#111114',
      bg_card: '#0f0f12', bg_hover: '#16161a', bg_elevated: '#16161a',
      text_primary: '#f5f5f7', text_secondary: '#c8c9cf', text_muted: '#8f9198',
      accent: '#ffffff', accent_hover: '#d0d0d6', accent_secondary: '#9aa0a6',
      border: 'rgba(255,255,255,0.10)', shadow: 'rgba(0, 0, 0, 0.55)',
      player_bg: '#0a0a0c', sidebar_bg: '#000000', input_bg: '#111114',
      success: '#7ee08a', warning: '#f6c177', error: '#f19898',
    },
  },
};

function applyTheme(theme) {
  if (!theme) return;
  currentThemeData = theme;
  const root = document.documentElement;
  const map = {
    'bg-primary': 'bg_primary', 'bg-secondary': 'bg_secondary',
    'bg-tertiary': 'bg_tertiary', 'bg-card': 'bg_card',
    'bg-hover': 'bg_hover', 'bg-elevated': 'bg_elevated',
    'text-primary': 'text_primary', 'text-secondary': 'text_secondary',
    'text-muted': 'text_muted', 'accent': 'accent',
    'accent-hover': 'accent_hover', 'accent-secondary': 'accent_secondary',
    'border': 'border', 'shadow': 'shadow',
    'player-bg': 'player_bg', 'sidebar-bg': 'sidebar_bg',
    'input-bg': 'input_bg', 'success': 'success',
    'warning': 'warning', 'error': 'error',
  };
  Object.entries(map).forEach(([cssVar, themeKey]) => {
    if (!theme[themeKey]) return;
    const value = theme[themeKey];
    root.style.setProperty(`--${cssVar}`, value);
    document.body.style.setProperty(`--${cssVar}`, value);
  });
}

function applyThemeByName(name, persist = true) {
  const themeDef = THEMES[name];
  if (!themeDef) return;
  currentThemeName = name;
  currentThemeData = { ...themeDef.colors };
  applyTheme(currentThemeData);

  // Activar/desactivar estilos específicos de Material You
  document.body.classList.toggle('material-you', name.startsWith('Android'));

  // Update active state in selector UI
  document.querySelectorAll('.theme-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.theme === name);
  });

  // Persist
  if (persist) {
    try {
      pywebview.api.setTheme(name);
    } catch(e) {}
  }
}

const THEME_ALIASES = {
  'Oscuro': 'Android Verde',
  'Claro': 'Android Blanco',
  'Azul': 'Android Azul',
  'Verde': 'Android Verde',
  'Material You': 'Android Verde',
};

async function loadThemes() {
  try {
    let currentName = currentThemeName;
    try {
      const current = await pywebview.api.getCurrentTheme();
      if (current && current.name) {
        const alias = THEME_ALIASES[current.name];
        currentName = alias || (THEMES[current.name] ? current.name : currentThemeName);
      }
    } catch(e) {}
    const selector = document.getElementById('themeSelector');
    if (!selector) return;
    selector.innerHTML = '';
    Object.keys(THEMES).forEach(name => {
      const btn = document.createElement('div');
      btn.className = 'theme-btn' + (name === currentName ? ' active' : '');
      btn.dataset.theme = name;
      const t = THEMES[name];
      const c = t.colors;
      btn.style.background = `linear-gradient(135deg, ${c.accent}, ${c.bg_primary})`;
      btn.title = name;
      btn.innerHTML = `<span>${name.replace('Android ', '')}</span>`;
      btn.onclick = () => applyThemeByName(name);
      selector.appendChild(btn);
    });
    applyThemeByName(currentName, false);
  } catch(e) {}
}

function showThemeEditor() {
  if (!currentThemeData) { showToast('Carga un tema primero', 'error'); return; }
  document.getElementById('themeEditorModal').style.display = 'flex';
}