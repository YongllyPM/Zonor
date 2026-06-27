let currentThemeData = null;
let currentThemeName = 'Classic Dark Flat';

const THEMES = {
  'Classic Dark Flat': {
    colors: {
      bg_primary: '#0a0a0f', bg_secondary: '#12121a', bg_tertiary: '#1a1a2e',
      bg_card: '#16162b', bg_hover: '#1f1f35', bg_elevated: '#20203a',
      text_primary: '#e8e8f0', text_secondary: '#9898b8', text_muted: '#5c5c7a',
      accent: '#7c3aed', accent_hover: '#6d28d9', accent_secondary: '#ec4899',
      border: '#2a2a45', shadow: 'rgba(124, 58, 237, 0.15)',
      player_bg: '#12121a', sidebar_bg: '#0f0f18', input_bg: '#1a1a2e',
      success: '#22c55e', warning: '#f59e0b', error: '#ef4444',
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
    if (theme[themeKey]) root.style.setProperty(`--${cssVar}`, theme[themeKey]);
  });
}

function applyThemeByName(name) {
  const themeDef = THEMES[name];
  if (!themeDef) return;
  currentThemeName = name;
  currentThemeData = { ...themeDef.colors };
  applyTheme(currentThemeData);

  // Update active state in selector UI
  document.querySelectorAll('.theme-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.theme === name);
  });

  // Persist
  try {
    pywebview.api.setTheme(name);
  } catch(e) {}
}

const THEME_ALIASES = {
  'Oscuro': 'Classic Dark Flat',
  'Claro': 'Classic Dark Flat',  // fallback: no light theme yet
  'Azul': 'Classic Dark Flat',
  'Verde': 'Classic Dark Flat',
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
      btn.innerHTML = `<span>${name === 'Classic Dark Flat' ? 'Clásico' : 'Glass'}</span>`;
      btn.onclick = () => applyThemeByName(name);
      selector.appendChild(btn);
    });
    applyThemeByName(currentName);
  } catch(e) {}
}

function showThemeEditor() {
  if (!currentThemeData) { showToast('Carga un tema primero', 'error'); return; }
  const grid = document.getElementById('themeEditorGrid');
  if (!grid) return;
  grid.innerHTML = '';
  const labels = {
    bg_primary: 'Fondo principal', bg_secondary: 'Fondo secundario', bg_tertiary: 'Fondo terciario',
    bg_card: 'Tarjetas', bg_hover: 'Hover', bg_elevated: 'Elevado',
    text_primary: 'Texto principal', text_secondary: 'Texto secundario', text_muted: 'Texto gris',
    accent: 'Acento', accent_hover: 'Acento hover', accent_secondary: 'Acento 2',
    border: 'Bordes', player_bg: 'Fondo reproductor', sidebar_bg: 'Fondo sidebar',
    input_bg: 'Fondo inputs', success: 'Éxito', warning: 'Advertencia', error: 'Error',
  };
  Object.entries(labels).forEach(([key, label]) => {
    const item = document.createElement('div');
    item.className = 'theme-editor-item';
    item.innerHTML = `<label>${label}</label><input type="color" id="te-${key}" value="${currentThemeData[key] || '#000000'}">`;
    item.querySelector('input').oninput = function() {
      currentThemeData[key] = this.value;
      applyTheme(currentThemeData);
    };
    grid.appendChild(item);
  });
  const nameInput = document.getElementById('themeNameInput');
  if (nameInput) nameInput.value = currentThemeData.name + ' (personalizado)';
  const editor = document.getElementById('themeEditor');
  if (editor) editor.style.display = 'flex';
}

async function saveCustomTheme() {
  const nameInput = document.getElementById('themeNameInput');
  if (!nameInput) return;
  const name = nameInput.value.trim();
  if (!name) { showToast('Escribe un nombre', 'error'); return; }
  try {
    currentThemeData.name = name;
    await pywebview.api.saveTheme(JSON.stringify(currentThemeData));
    showToast('Tema guardado');
    closeDialog(null, 'themeEditor');
    loadThemes();
  } catch(e) { showToast('Error', 'error'); }
}

document.addEventListener('DOMContentLoaded', () => {
  loadThemes();
  loadSettings();
});
