let searchTimeout = null;

function debounceSearch() {
  clearTimeout(searchTimeout);
  searchTimeout = setTimeout(doSearch, 350);
}

async function doSearch() {
  const query = $('searchInput').value.trim();
  const results = $('searchResults');
  const suggestions = $('searchSuggestions');
  const placeholder = $('searchPlaceholder');

  if (!query || query.length < 2) {
    results.innerHTML = '';
    placeholder.style.display = 'none';
    showSearchHistory();
    return;
  }

  suggestions.style.display = 'none';
  placeholder.style.display = 'none';

  try {
    const songs = await pywebview.api.search(query);
    results.innerHTML = '';

    if (!songs || !songs.length) {
      results.innerHTML = '<div class="placeholder"><p>Sin resultados</p></div>';
      return;
    }

    songs.forEach((song, i) => {
      const div = document.createElement('div');
      div.className = 'song-item';
      div.dataset.songId = song.id;
      notePlatform(song.id, song.platform || 'youtube');
      const platformBadgeHtml = platformBadge(song.platform || 'youtube');
      div.innerHTML = `
        <span class="song-index">${i + 1}</span>
        ${songThumbMarkup(song)}
        <div class="song-info">
          <div class="song-title">${escapeHtml(song.title)} ${platformBadgeHtml}</div>
          <div class="song-artist">${escapeHtml(song.artist)}</div>
        </div>
        <div class="song-album">${escapeHtml(song.album || '')}</div>
        <span class="song-duration">${formatDuration(song.duration)}</span>
        <div class="song-actions">
          <button class="btn-icon" onclick="event.stopPropagation();playSong('${song.id}')" title="Reproducir">
            <svg viewBox="0 0 24 24" width="16" height="16"><path fill="currentColor" d="M8 5v14l11-7z"/></svg>
          </button>
          <button class="btn-icon" onclick="event.stopPropagation();downloadSong('${song.id}')" title="Descargar">
            <svg viewBox="0 0 24 24" width="16" height="16"><path fill="currentColor" d="M19 9h-4V3H9v6H5l7 7 7-7zM5 18v2h14v-2H5z"/></svg>
          </button>
          <button class="btn-icon" onclick="event.stopPropagation();showAddToPlaylist('${song.id}')" title="Añadir a playlist">
            <svg viewBox="0 0 24 24" width="16" height="16"><path fill="currentColor" d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z"/></svg>
          </button>
        </div>
      `;
      div.onclick = () => playSong(song.id);
      if (currentSong && song.id === currentSong.id) div.classList.add('active');
      results.appendChild(div);
    });
  } catch(e) {}
}

async function loadLibrary() {
  try {
    const songs = await pywebview.api.getLibrary();
    if (songs.length) {
      renderSongGrid($('libraryContent'), songs);
    } else {
      $('libraryContent').innerHTML = '<div class="placeholder"><p>Inicia sesión para ver tu biblioteca de YT Music</p><button class="btn-primary" onclick="showAuthDialog()" style="margin-top:12px">Iniciar sesión</button></div>';
    }
  } catch(e) {}
}

async function showSearchHistory() {
  const suggestions = $('searchSuggestions');
  const placeholder = $('searchPlaceholder');
  try {
    const history = await pywebview.api.getSearchHistory();
    if (!history || !history.length) {
      suggestions.style.display = 'none';
      placeholder.style.display = 'flex';
      return;
    }
    suggestions.innerHTML = '';
    const title = document.createElement('div');
    title.style.cssText = 'padding:10px 16px;font-size:12px;text-transform:uppercase;letter-spacing:.05em;color:var(--text-muted);display:flex;justify-content:space-between;align-items:center;';
    title.innerHTML = '<span>Busquedas recientes</span><button class="btn-text" onclick="clearSearchHistory()" style="font-size:12px">Limpiar</button>';
    suggestions.appendChild(title);
    history.forEach(h => {
      const item = document.createElement('div');
      item.className = 'search-suggestion-item';
      item.innerHTML = `
        <svg viewBox="0 0 24 24" width="14" height="14" style="vertical-align:-2px;margin-right:8px;opacity:.6"><path fill="currentColor" d="M8 5v14l11-7z"/></svg>
        <span>${escapeHtml(h.query)}</span>
      `;
      item.onclick = () => {
        $('searchInput').value = h.query;
        doSearch();
        $('searchInput').focus();
      };
      suggestions.appendChild(item);
    });
    suggestions.style.display = 'block';
  } catch(e) {
    suggestions.style.display = 'none';
    placeholder.style.display = 'flex';
  }
}

async function clearSearchHistory() {
  try {
    await pywebview.api.clearSearchHistory();
    showSearchHistory();
  } catch(e) {}
}
