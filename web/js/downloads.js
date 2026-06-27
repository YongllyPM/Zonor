function statusLabel(status) {
  const labels = {
    pending: 'En cola',
    downloading: 'Descargando',
    processing: 'Procesando',
    failed: 'Fallida',
    cancelled: 'Cancelada',
    completed: 'Completada',
  };
  return labels[status] || status || 'En cola';
}

async function loadDownloads() {
  const container = $('downloadsContent');
  container.innerHTML = '';

  try {
    const downloaded = await pywebview.api.getDownloadedSongs();
    const queue = await pywebview.api.getDownloads();

    if (!downloaded.length && !queue.length) {
      container.innerHTML = '<div class="placeholder"><svg viewBox="0 0 24 24" width="64" height="64" opacity="0.3"><path fill="currentColor" d="M19 9h-4V3H9v6H5l7 7 7-7zM5 18v2h14v-2H5z"/></svg><p>No hay descargas. Busca canciones y descárgalas.</p></div>';
      return;
    }

    // Download queue
    if (queue.length) {
      const section = document.createElement('div');
      section.innerHTML = '<h3 style="margin-bottom:12px;font-size:15px;font-weight:600">En progreso</h3>';
      queue.forEach(q => {
        const div = document.createElement('div');
        div.className = 'song-item';
        div.dataset.songId = q.song_id;
        div.innerHTML = `
          <span class="song-index">⬇</span>
          <div class="song-info">
            <div class="song-title">${escapeHtml(q.title || '')}</div>
            <div class="song-artist">${escapeHtml(q.artist || '')}</div>
          </div>
          <div class="download-progress-wrap">
            <div class="download-progress-bar">
              <div id="dl-progress-${q.song_id}" class="download-progress-fill" style="width:${q.progress || 0}%"></div>
            </div>
            <div class="download-status">${statusLabel(q.status)}</div>
          </div>
          <div class="song-actions">
            ${q.status === 'failed' ? `<button class="btn-icon" onclick="retryDownload('${q.song_id}')" title="Reintentar">
              <svg viewBox="0 0 24 24" width="16" height="16"><path fill="currentColor" d="M17.65 6.35A7.958 7.958 0 0012 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08A5.99 5.99 0 0112 18c-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z"/></svg>
            </button>` : ''}
            <button class="btn-icon" onclick="cancelDownload('${q.song_id}')" title="Cancelar">
              <svg viewBox="0 0 24 24" width="16" height="16"><path fill="currentColor" d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg>
            </button>
          </div>
        `;
        section.appendChild(div);
      });
      container.appendChild(section);
    }

    // Downloaded songs
    if (downloaded.length) {
      const section = document.createElement('div');
      section.innerHTML = '<h3 style="margin:16px 0 12px;font-size:15px;font-weight:600">Descargadas</h3>';
      const grid = document.createElement('div');
      grid.className = 'song-list';
      downloaded.forEach((song, i) => {
        const div = document.createElement('div');
        div.className = 'song-item';
        div.dataset.songId = song.id;
        div.innerHTML = `
          <span class="song-index">${i + 1}</span>
          <div class="song-thumb">${song.thumbnail ? `<img src="${song.thumbnail}" loading="lazy">` : ''}</div>
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
            <button class="btn-icon" onclick="event.stopPropagation();deleteDownloaded('${song.id}')" title="Eliminar">
              <svg viewBox="0 0 24 24" width="16" height="16"><path fill="currentColor" d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"/></svg>
            </button>
          </div>
        `;
        div.onclick = () => playSong(song.id);
        if (currentSong && song.id === currentSong.id) div.classList.add('active');
        grid.appendChild(div);
      });
      section.appendChild(grid);
      container.appendChild(section);
    }
  } catch(e) {}
}

function updateDownloadProgress(songId, progress) {
  const bar = $(`dl-progress-${songId}`);
  if (bar) {
    bar.style.width = Math.min(100, progress) + '%';
  }
  if (progress >= 100) {
    setTimeout(loadDownloads, 500);
  }
}

async function retryDownload(songId) {
  try {
    await pywebview.api.downloadSong(songId);
    showToast('Reintentando descarga');
    loadDownloads();
  } catch (e) {
    showToast('No se pudo reintentar', 'error');
  }
}

async function cancelDownload(songId) {
  await pywebview.api.cancelDownload(songId);
  showToast('Descarga cancelada');
  loadDownloads();
}

async function deleteDownloaded(songId) {
  if (!confirm('¿Eliminar descarga?')) return;
  await pywebview.api.deleteDownload(songId);
  showToast('Descarga eliminada');
  loadDownloads();
}
