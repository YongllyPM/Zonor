// ===== Playlists =====
let currentPlaylistId = null;

async function loadPlaylists() {
  $('playlistsGrid').style.display = '';
  $('playlistDetail').style.display = 'none';
  currentPlaylistId = null;
  try {
    const playlists = await pywebview.api.getPlaylists();
    const grid = $('playlistsGrid');
    const list = $('playlistList');
    grid.innerHTML = '';
    list.innerHTML = '';

    if (!playlists.length) {
      grid.innerHTML = '<div class="placeholder"><p>No hay playlists aún</p></div>';
      return;
    }

    playlists.forEach(pl => {
      const card = document.createElement('div');
      card.className = 'playlist-card';
      card.innerHTML = `
        <div class="playlist-card-thumb">
          ${pl.thumbnail ? `<img src="${pl.thumbnail}">` : '<svg viewBox="0 0 24 24" width="40" height="40"><path fill="currentColor" d="M15 6H3v2h12V6zm0 4H3v2h12v-2zM3 16h8v-2H3v2zM17 6v8.18c-.31-.11-.65-.18-1-.18-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3V8h3V6h-5z"/></svg>'}
        </div>
        <div class="playlist-card-body">
          <div class="playlist-card-name">${escapeHtml(pl.name)}</div>
          <div class="playlist-card-count">${pl.song_count || 0} canciones</div>
        </div>
      `;
      card.onclick = () => showPlaylistDetail(pl.id);
      grid.appendChild(card);

      const item = document.createElement('div');
      item.className = 'playlist-item';
      item.innerHTML = `<svg viewBox="0 0 24 24" width="16" height="16"><path fill="currentColor" d="M15 6H3v2h12V6zm0 4H3v2h12v-2zM3 16h8v-2H3v2zM17 6v8.18c-.31-.11-.65-.18-1-.18-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3V8h3V6h-5z"/></svg> ${escapeHtml(pl.name)}`;
      item.onclick = () => showPlaylistDetail(pl.id);
      list.appendChild(item);
    });
  } catch(e) {}
}

async function showPlaylistDetail(playlistId) {
  currentPlaylistId = playlistId;
  pushView('playlists');
  switchView('playlists');
  $('playlistsGrid').style.display = 'none';
  $('playlistDetail').style.display = 'block';

  try {
    const songs = await pywebview.api.getPlaylistSongs(playlistId);
    const playlists = await pywebview.api.getPlaylists();
    const pl = playlists.find(p => p.id === playlistId);
    $('playlistDetailName').textContent = pl ? pl.name : 'Playlist';
    $('playlistDetailSongs').innerHTML = '';
    renderSongGrid($('playlistDetailSongs'), songs, 0);
  } catch(e) {}
}

function playPlaylistDetail() {
  if (currentPlaylistId) playPlaylist(currentPlaylistId, 0);
}

function showPlaylistsGrid() {
  switchView('playlists');
  currentPlaylistId = null;
}

function showCreatePlaylist() {
  $('playlistNameInput').value = '';
  $('playlistDescInput').value = '';
  $('playlistDialogTitle').textContent = 'Nueva playlist';
  $('playlistDialog').style.display = 'flex';
}

async function confirmCreatePlaylist() {
  const name = $('playlistNameInput').value.trim();
  if (!name) { showToast('Escribe un nombre', 'error'); return; }
  try {
    await pywebview.api.createPlaylist(name, $('playlistDescInput').value.trim());
    showToast('Playlist creada');
    closeDialog(null, 'playlistDialog');
    loadPlaylists();
  } catch(e) { showToast('Error', 'error'); }
}

async function deleteCurrentPlaylist() {
  if (!currentPlaylistId) return;
  if (!confirm('¿Eliminar esta playlist?')) return;
  try {
    await pywebview.api.deletePlaylist(currentPlaylistId);
    showToast('Playlist eliminada');
    showPlaylistsGrid();
    loadPlaylists();
  } catch(e) { showToast('Error', 'error'); }
}
