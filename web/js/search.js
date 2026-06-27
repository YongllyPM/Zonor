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
    suggestions.style.display = 'none';
    placeholder.style.display = 'flex';
    return;
  }

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
      div.innerHTML = `
        <span class="song-index">${i + 1}</span>
        <div class="song-thumb">${song.thumbnail ? `<img src="${song.thumbnail}" loading="lazy">` : '<svg viewBox="0 0 24 24" width="20" height="20"><path fill="currentColor" d="M12 3v10.55c-.59-.34-1.27-.55-2-.55-2.21 0-4 1.79-4 4s1.79 4 4 4 4-1.79 4-4V7h4V3h-6z"/></svg>'}</div>
        <div class="song-info">
          <div class="song-title">${escapeHtml(song.title)}</div>
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
