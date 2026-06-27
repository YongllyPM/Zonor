let currentView = 'home';
let isPlaying = false;
let currentSong = null;
let playerStatus = { state: 'stopped', position: 0, duration: 0, volume: 80 };
let authStatus = { authenticated: false, user: null };

function $(id) { return document.getElementById(id); }

// ===== Navigation =====
function switchView(view) {
  document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  const v = $(`view-${view}`);
  if (v) v.classList.add('active');
  const nav = document.querySelector(`.nav-item[data-view="${view}"]`);
  if (nav) nav.classList.add('active');
  currentView = view;
  if (view === 'home') loadHome();
  if (view === 'library') loadLibrary();
  if (view === 'playlists') loadPlaylists();
  if (view === 'downloads') loadDownloads();
  if (view === 'liked') loadLikedView();
  if (view === 'artists') loadArtists();
  if (view === 'player') loadLyrics();
}

let viewHistory = ['home'];
let viewHistoryIndex = 0;

function historyBack() {
  if (viewHistoryIndex > 0) {
    viewHistoryIndex--;
    switchView(viewHistory[viewHistoryIndex]);
  }
}

function historyForward() {
  if (viewHistoryIndex < viewHistory.length - 1) {
    viewHistoryIndex++;
    switchView(viewHistory[viewHistoryIndex]);
  }
}

function pushView(view) {
  viewHistory = viewHistory.slice(0, viewHistoryIndex + 1);
  viewHistory.push(view);
  viewHistoryIndex = viewHistory.length - 1;
}

// ===== Auth =====
let authTab = 'quick';

function showAuthDialog() {
  $('authDialog').style.display = 'flex';
  switchAuthTab(authTab);
}

function switchAuthTab(tab) {
  authTab = tab;
  document.querySelectorAll('.auth-tab').forEach(t => t.classList.toggle('active', t.dataset.tab === tab));
  document.querySelectorAll('.auth-panel').forEach(p => p.style.display = p.id === `authPanel-${tab}` ? 'block' : 'none');
}

async function loginBrowser() {
  const btn = $('loginBrowserBtn');
  const fallback = $('quickManualFallback');
  if (btn) { btn.disabled = true; btn.textContent = 'Leyendo sesión del navegador...'; }
  try {
    const result = await pywebview.api.loginFromBrowser();
    if (result === true || result?.success) {
      await updateAuthUI();
      showToast('Sesión iniciada correctamente', 'success');
      closeDialog(null, 'authDialog');
      loadHome();
    } else if (result?.open_browser) {
      if (fallback) fallback.style.display = 'block';
      showToast(result.message || 'Abre YouTube Music e inicia sesión', 'info');
    } else {
      showToast(result?.error || 'No se pudo iniciar sesión', 'error');
    }
  } catch (e) { showToast('Error: ' + e, 'error'); }
  finally {
    if (btn) { btn.disabled = false; btn.textContent = 'Iniciar sesión automáticamente'; }
  }
}

async function loginAuto() {
  try {
    const result = await pywebview.api.loginAuto();
    if (result.success) {
      await updateAuthUI();
      showToast(`Bienvenido, ${result.user?.name || 'Usuario'}`, 'success');
      closeDialog(null, 'authDialog');
      loadHome();
    } else {
      showToast(result.error || 'No hay sesión guardada', 'error');
    }
  } catch (e) { showToast('Error al reconectar', 'error'); }
}

async function loginOAuth() {
  try {
    const result = await pywebview.api.loginOAuth();
    if (result === true || result?.success) {
      await updateAuthUI();
      showToast('Sesión iniciada', 'success');
      closeDialog(null, 'authDialog');
      loadHome();
    } else {
      const status = await pywebview.api.getAuthStatus();
      showToast(status.error || result?.error || 'OAuth no disponible. Usa cookie o headers.', 'error');
    }
  } catch (e) { showToast('OAuth no disponible. Usa cookie o headers.', 'error'); }
}

async function loginWithQuickCurl() {
  const raw = $('quickCurlInput')?.value.trim();
  if (!raw) { showToast('Pega el cURL de Firefox primero', 'error'); return; }
  try {
    const result = await pywebview.api.loginWithHeaders(raw);
    if (result) {
      await updateAuthUI();
      showToast('Sesión iniciada correctamente', 'success');
      closeDialog(null, 'authDialog');
      loadHome();
    } else {
      const status = await pywebview.api.getAuthStatus();
      showToast(status.error || 'Error al iniciar sesión. Revisa que el cURL tenga la cookie.', 'error');
    }
  } catch (e) { showToast('Error: ' + e, 'error'); }
}

async function loginWithCookie() {
  const raw = $('cookieInput')?.value.trim();
  if (!raw) { showToast('Pega tu cookie de sesión', 'error'); return; }
  try {
    const result = await pywebview.api.loginWithCookie(raw);
    if (result.success) {
      await updateAuthUI();
      showToast('Conectado con cookie', 'success');
      closeDialog(null, 'authDialog');
      loadHome();
    } else {
      showToast(result.error || 'Cookie inválida', 'error');
    }
  } catch (e) { showToast('Error', 'error'); }
}

async function loginWithHeaders() {
  const raw = $('headersInput').value.trim();
  if (!raw) { showToast('Pega los headers primero', 'error'); return; }
  if (raw.startsWith('{')) {
    try {
      const headers = JSON.parse(raw);
      if (!headers.cookie && !headers.Cookie) {
        showToast('Falta "cookie" o "Cookie" en el JSON', 'error');
        return;
      }
    } catch (e) {
      showToast('JSON inválido. Revisa el formato.', 'error');
      return;
    }
  }
  try {
    const result = await pywebview.api.loginWithHeaders(raw);
    if (result) {
      await updateAuthUI();
      showToast('Sesión iniciada correctamente', 'success');
      closeDialog(null, 'authDialog');
      loadHome();
    } else {
      const status = await pywebview.api.getAuthStatus();
      showToast(status.error || 'Headers inválidos', 'error');
    }
  } catch (e) { showToast('Error: ' + e, 'error'); }
}

async function logout() {
  await pywebview.api.logout();
  await updateAuthUI();
  showToast('Sesión cerrada');
}

async function updateAuthUI() {
  try {
    const status = await pywebview.api.getAuthStatus();
    authStatus = status;
    const btn = $('authBtnText');
    const settingsBtn = $('settingsAuthStatus');
    const settingsActions = $('settingsAuthActions');
    if (status.authenticated) {
      btn.textContent = status.user?.name || 'Conectado';
      if (settingsBtn) settingsBtn.innerHTML = `<span style="color:var(--success)">✓ Conectado como ${escapeHtml(status.user?.name || 'Usuario')}</span>`;
      if (settingsActions) settingsActions.innerHTML = `<button class="btn-text" onclick="logout()" style="color:var(--error)">Cerrar sesión</button>`;
    } else {
      btn.textContent = status.has_credentials ? 'Reconectar' : 'Iniciar Sesión';
      if (settingsBtn) {
        settingsBtn.innerHTML = status.has_credentials
          ? '<span class="text-muted">Sesión expirada — <button class="btn-text" onclick="loginAuto()">reconectar</button></span>'
          : '<span class="text-muted">No conectado</span>';
      }
      if (settingsActions) settingsActions.innerHTML = '<button class="btn-primary" onclick="showAuthDialog()">Iniciar sesión</button>';
    }
  } catch(e) {}
}

// ===== Events from Python =====
window.__handlePyEvent = function(data) {
  const event = data.event;
  const d = data.data;
  switch (event) {
    case 'player_status':
      updatePlayerStatus(d);
      break;
    case 'song_changed':
      currentSong = d;
      updateNowPlaying(d);
      loadLyrics();
      break;
    case 'download_progress':
      updateDownloadProgress(d.song_id, d.progress);
      break;
    case 'download_error':
      showToast('Descarga fallida: ' + (d.error || 'error'), 'error');
      if (currentView === 'downloads') loadDownloads();
      break;
    case 'auth_changed':
      updateAuthUI();
      break;
    case 'theme_changed':
      if (d && d.name && window.applyThemeByName) {
        window.applyThemeByName(d.name);
      } else {
        applyTheme(d);
      }
      break;
    case 'sync_event':
      showToast(`Sync: ${d.type}`);
      break;
    case 'home_updated':
      renderHomeFeed(d);
      break;
    case 'settings_updated':
      showToast('Configuración guardada');
      break;
  }
};

// ===== Toast =====
let toastTimeout;

function showToast(msg, type = 'info') {
  const t = $('toast');
  t.textContent = msg;
  t.style.display = 'block';
  t.style.borderLeft = type === 'error' ? '4px solid var(--error)' : type === 'success' ? '4px solid var(--success)' : '4px solid var(--accent)';
  clearTimeout(toastTimeout);
  toastTimeout = setTimeout(() => t.style.display = 'none', 3000);
}

// ===== Dialog =====
function closeDialog(e, id) {
  if (e && e.target !== e.currentTarget) return;
  $(id).style.display = 'none';
}

// ===== Home =====
function showHomeLoading(show) {
  const el = $('homeLoading');
  if (el) el.style.display = show ? 'block' : 'none';
}

function showHomeSection(id, show) {
  const el = $(id);
  if (el) el.style.display = show ? 'block' : 'none';
}

function renderHomeFeed(chart) {
  if (!chart) return;
  showHomeLoading(false);

  const sections = [
    ['homeRecentSection', 'homeRecentGrid', chart.recent],
    ['homeNewSection', 'homeNewGrid', chart.new_releases],
    ['homeListenAgainSection', 'homeListenAgainGrid', chart.listen_again],
    ['homeTrendingSection', 'homeTrendingGrid', chart.trending],
    ['homeTopSection', 'homeTopGrid', chart.top_songs],
  ];
  let hasContent = false;
  sections.forEach(([secId, gridId, songs]) => {
    if (songs && songs.length) {
      showHomeSection(secId, true);
      renderSongGrid($(gridId), songs);
      hasContent = true;
    } else {
      showHomeSection(secId, false);
    }
  });

  if (chart.playlists && chart.playlists.length) {
    showHomeSection('homePlaylistSection', true);
    renderPlaylistGrid($('homePlaylistGrid'), chart.playlists);
    hasContent = true;
  } else {
    showHomeSection('homePlaylistSection', false);
  }

  if (!hasContent && !chart.from_cache) {
    showHomeLoading(true);
  }
}

async function loadHome() {
  try {
    $('homeLiked').style.display = 'block';
    loadLikedSongs();
    showHomeLoading(true);
    const chart = await pywebview.api.getHome();
    renderHomeFeed(chart);
  } catch (e) {
    showHomeLoading(false);
  }
}

async function playHomePlaylist(playlistId) {
  try {
    const songs = await pywebview.api.getRemotePlaylistSongs(playlistId);
    if (!songs?.length) { showToast('Playlist vacía o no disponible', 'error'); return; }
    currentQueue = songs;
    currentQueueIndex = 0;
    if (shuffleOn) buildShuffleOrder();
    await pywebview.api.playSong(songs[0].id, songs);
    return playAtIndex(0);
  } catch (e) { showToast('No se pudo abrir la playlist', 'error'); }
}

async function loadLikedSongs() {
  try {
    const songs = await pywebview.api.getLikedSongs();
    renderSongGrid($('homeLikedGrid'), songs);
  } catch(e) {}
}

async function loadLikedView() {
  try {
    const songs = await pywebview.api.getLikedSongs();
    renderSongGrid($('likedGrid'), songs);
  } catch(e) {}
}

function renderSongGrid(container, songs, startIdx = 0) {
  container.innerHTML = '';
  if (!songs || !songs.length) {
    container.innerHTML = '<div class="text-muted" style="padding:20px">No hay canciones</div>';
    return;
  }
  songs.forEach((song, i) => {
    const div = document.createElement('div');
    div.className = 'song-item';
    div.dataset.songId = song.id;
    const liked = song.liked ? ' liked' : '';
    div.innerHTML = `
      <span class="song-index">${startIdx + i + 1}</span>
      <div class="song-thumb">${song.thumbnail ? `<img src="${song.thumbnail}" loading="lazy">` : '<svg viewBox="0 0 24 24" width="20" height="20"><path fill="currentColor" d="M12 3v10.55c-.59-.34-1.27-.55-2-.55-2.21 0-4 1.79-4 4s1.79 4 4 4 4-1.79 4-4V7h4V3h-6z"/></svg>'}</div>
      <div class="song-info">
        <div class="song-title">${escapeHtml(song.title)}</div>
        <div class="song-artist">${escapeHtml(song.artist)}</div>
      </div>
      <div class="song-album">${escapeHtml(song.album || '')}</div>
      <span class="song-duration">${formatDuration(song.duration)}</span>
      <div class="song-actions">
        <button class="btn-icon btn-like${liked}" data-song-id="${song.id}" onclick="event.stopPropagation();toggleLike('${song.id}')" title="Me gusta">
          <svg viewBox="0 0 24 24" width="16" height="16"><path fill="currentColor" d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/></svg>
        </button>
        <button class="btn-icon play-btn" data-song-id="${song.id}" title="Reproducir">
          <svg viewBox="0 0 24 24" width="16" height="16"><path fill="currentColor" d="M8 5v14l11-7z"/></svg>
        </button>
        <button class="btn-icon" onclick="event.stopPropagation();showAddToPlaylist('${song.id}')" title="Agregar a playlist">
          <svg viewBox="0 0 24 24" width="16" height="16"><path fill="currentColor" d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z"/></svg>
        </button>
        <button class="btn-icon" onclick="event.stopPropagation();downloadSong('${song.id}')" title="Descargar">
          <svg viewBox="0 0 24 24" width="16" height="16"><path fill="currentColor" d="M19 9h-4V3H9v6H5l7 7 7-7zM5 18v2h14v-2H5z"/></svg>
        </button>
      </div>
    `;
    div.onclick = () => playSong(song.id, songs);
    const playBtn = div.querySelector('.play-btn');
    if (playBtn) playBtn.onclick = (e) => { e.stopPropagation(); playSong(song.id, songs); };
    if (currentSong && song.id === currentSong.id) div.classList.add('active');
    container.appendChild(div);
  });
}

function renderPlaylistGrid(container, playlists) {
  container.innerHTML = '';
  playlists.forEach(pl => {
    const div = document.createElement('div');
    div.className = 'playlist-card';
    const name = pl.title || pl.name || 'Playlist';
    const count = pl.song_count || pl.songCount || 0;
    div.innerHTML = `
      <div class="playlist-card-thumb">
        ${pl.thumbnail ? `<img src="${pl.thumbnail}" loading="lazy">` : '<svg viewBox="0 0 24 24" width="48" height="48"><path fill="currentColor" d="M15 6H3v2h12V6zm0 4H3v2h12v-2zM3 16h8v-2H3v2zM17 6v8.18c-.31-.11-.65-.18-1-.18-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3V8h3V6h-5z"/></svg>'}
      </div>
      <div class="playlist-card-body">
        <div class="playlist-card-name">${escapeHtml(name)}</div>
        <div class="playlist-card-count">${count > 0 ? count + ' canciones' : 'Playlist'}</div>
      </div>
    `;
    div.style.cursor = 'pointer';
    div.onclick = () => playHomePlaylist(pl.id);
    container.appendChild(div);
  });
}

function escapeHtml(str) {
  if (!str) return '';
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

function formatDuration(secs) {
  if (!secs || secs <= 0) return '0:00';
  const m = Math.floor(secs / 60);
  const s = Math.floor(secs % 60);
  return `${m}:${s.toString().padStart(2, '0')}`;
}

function formatTime(secs) {
  if (!secs || secs < 0) return '0:00';
  const m = Math.floor(secs / 60);
  const s = Math.floor(secs % 60);
  return `${m}:${s.toString().padStart(2, '0')}`;
}

// ===== Init =====
document.addEventListener('DOMContentLoaded', async () => {
  await updateAuthUI();
  try {
    const settings = await pywebview.api.getSettings();
    if (settings.volume) {
      document.querySelectorAll('.volume-slider').forEach(s => s.value = settings.volume);
      $('volVal').textContent = settings.volume;
      audio.volume = settings.volume / 100;
    }
  } catch(e) {}
  try {
    await pywebview.api.startSync();
  } catch(e) {}
  updateModeButtons();
  loadHome();
});
