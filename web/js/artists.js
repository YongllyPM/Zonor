let currentArtistId = null;

async function loadArtists() {
  try {
    const artists = await pywebview.api.getArtists();
    const grid = $('artistsGrid');
    if (!artists?.length) {
      grid.innerHTML = '<p class="text-muted" style="padding:20px">No hay artistas. Inicia sesión para ver tus suscripciones.</p>';
      return;
    }
    grid.innerHTML = artists.map(a => `
      <div class="artist-card" onclick="showArtistDetail('${a.id}')">
        <img src="${a.thumbnail || 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><circle cx="50" cy="50" r="45" fill="%23333"/><text x="50" y="55" text-anchor="middle" fill="%23999" font-size="30">${(a.name[0]||'?').toUpperCase()}</text></svg>'}" alt="${a.name}" loading="lazy">
        <div class="name">${a.name}</div>
        <div class="subs">${a.subscribers || 'Artista'}</div>
      </div>
    `).join('');
  } catch(e) { showToast('Error al cargar artistas', 'error'); }
}

async function showArtistDetail(channelId) {
  currentArtistId = channelId;
  pushView('artists');
  switchView('artists');
  try {
    const data = await pywebview.api.getArtistAlbums(channelId);
    if (!data) { showToast('Error al cargar artista', 'error'); return; }

    $('artistsGrid').style.display = 'none';
    $('artistDetail').style.display = 'block';
    $('artistDetailImg').src = data.thumbnail || '';
    $('artistDetailName').textContent = data.name;
    $('artistDetailSubs').textContent = data.subscribers || '';

    const list = $('artistAlbumsList');
    if (!data.albums?.length) {
      list.innerHTML = '<p class="text-muted">Sin álbumes disponibles</p>';
      return;
    }
    list.innerHTML = data.albums.map(a => `
      <div class="artist-card" onclick="playHomePlaylist('${a.id}')">
        <img src="${a.thumbnail || ''}" alt="${a.title}" loading="lazy" style="border-radius:8px">
        <div class="name">${a.title}</div>
        <div class="subs">${a.year || ''}</div>
      </div>
    `).join('');
  } catch(e) { showToast('Error al cargar artista', 'error'); }
}

function showArtistsGrid() {
  switchView('artists');
  currentArtistId = null;
}
