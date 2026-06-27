// ===== HTML5 Audio Player =====
const audio = new Audio();
audio.volume = 0.8;
let currentQueue = [];
let currentQueueIndex = -1;
let shuffleOn = false;
let repeatMode = 'off'; // off | one | all
let shuffleOrder = [];
let streamRetryCount = 0;

// ===== Web Audio API (Equalizer, Crossfade, Skip Silence) =====
let audioCtx = null;
let eqGainNodes = {};
let eqFilters = [];
let crossfadeDuration = 0;
let skipSilenceEnabled = false;
let isCrossfading = false;
const EQ_FREQS = [60, 170, 310, 600, 1000, 3000, 6000, 12000, 16000];

function initAudioContext() {
  if (audioCtx) return;
  audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  const src = audioCtx.createMediaElementSource(audio);
  eqFilters = [];
  const freqs = [
    { f: 60, type: 'lowshelf' },
    { f: 170, type: 'peaking', Q: 0.7 },
    { f: 310, type: 'peaking', Q: 0.7 },
    { f: 600, type: 'peaking', Q: 0.7 },
    { f: 1000, type: 'peaking', Q: 0.7 },
    { f: 3000, type: 'peaking', Q: 0.7 },
    { f: 6000, type: 'peaking', Q: 0.7 },
    { f: 12000, type: 'peaking', Q: 0.7 },
    { f: 16000, type: 'highshelf' },
  ];
  let chain = src;
  freqs.forEach(({ f, type, Q }) => {
    const filter = audioCtx.createBiquadFilter();
    filter.type = type;
    filter.frequency.value = f;
    filter.gain.value = 0;
    filter.Q.value = Q || 0.7;
    chain.connect(filter);
    chain = filter;
    eqFilters.push({ freq: f, node: filter });
  });
  chain.connect(audioCtx.destination);
}

function applyEqualizer(eqData) {
  try {
    if (!audioCtx) initAudioContext();
    if (!eqFilters.length) return;
    if (!eqData || !Object.keys(eqData).length) {
      eqFilters.forEach(f => { f.node.gain.value = 0; });
      return;
    }
    eqFilters.forEach(f => {
      const val = eqData[f.freq];
      if (val !== undefined) {
        f.node.gain.value = Math.max(-12, Math.min(12, parseInt(val)));
      }
    });
  } catch(e) {}
}
window.applyEqualizer = applyEqualizer;

function applyCrossfade(duration) {
  crossfadeDuration = Math.max(0, Math.min(10, parseInt(duration) || 0));
}
window.applyCrossfade = applyCrossfade;

function applySkipSilence(enabled) {
  skipSilenceEnabled = enabled;
}
window.applySkipSilence = applySkipSilence;

function crossfadeToNext(nextFn) {
  if (!crossfadeDuration || crossfadeDuration <= 0 || isCrossfading) {
    nextFn();
    return;
  }
  isCrossfading = true;
  const startVol = audio.volume;
  const fadeSteps = 20;
  const stepTime = (crossfadeDuration * 1000) / fadeSteps;
  let step = 0;
  const fade = setInterval(() => {
    try {
      step++;
      const progress = step / fadeSteps;
      audio.volume = Math.max(0, startVol * (1 - progress));
      if (step >= fadeSteps) {
        clearInterval(fade);
        audio.volume = startVol;
        isCrossfading = false;
        nextFn();
      }
    } catch(e) {
      clearInterval(fade);
      isCrossfading = false;
      nextFn();
    }
  }, stepTime);
}



const ICONS = {
  shuffle: 'M10.59 9.17L5.41 4 4 5.41l5.17 5.17 1.42-1.41zM14.5 4l2.04 2.04L4 18.59 5.41 20 17.96 7.46 20 9.5V4h-5.5zm.33 9.41l-1.41 1.41 3.13 3.13L14.5 20H20v-5.5l-2.04 2.04-3.13-3.13z',
  repeat: 'M7 7h10v3l4-4-4-4v3H5v6h2V7zm10 10H7v-3l-4 4 4 4v-3h12v-6h-2v4z',
  repeatOne: 'M7 7h10v3l4-4-4-4v3H5v6h2V7zm10 10H7v-3l-4 4 4 4v-3h12v-6h-2v4zm-4-2V9h-1l-2 1v1h1.5v4H13z',
  like: 'M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z',
};

function fileUrl(path) {
  return 'file:///' + path.replace(/\\/g, '/').split('/').map(encodeURIComponent).join('/').replace(/%3A/g, ':');
}

function buildShuffleOrder() {
  shuffleOrder = currentQueue.map((_, i) => i);
  for (let i = shuffleOrder.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [shuffleOrder[i], shuffleOrder[j]] = [shuffleOrder[j], shuffleOrder[i]];
  }
  const pos = shuffleOrder.indexOf(currentQueueIndex);
  if (pos > 0) {
    shuffleOrder.splice(pos, 1);
    shuffleOrder.unshift(currentQueueIndex);
  }
}

function getNextIndex() {
  if (!currentQueue.length) return -1;
  if (repeatMode === 'one') return currentQueueIndex;
  if (shuffleOn) {
    const pos = shuffleOrder.indexOf(currentQueueIndex);
    if (pos < shuffleOrder.length - 1) return shuffleOrder[pos + 1];
    if (repeatMode === 'all') return shuffleOrder[0];
    return -1;
  }
  if (currentQueueIndex < currentQueue.length - 1) return currentQueueIndex + 1;
  if (repeatMode === 'all') return 0;
  return -1;
}

function getPrevIndex() {
  if (!currentQueue.length) return -1;
  if (audio.currentTime > 3) return currentQueueIndex;
  if (shuffleOn) {
    const pos = shuffleOrder.indexOf(currentQueueIndex);
    if (pos > 0) return shuffleOrder[pos - 1];
    if (repeatMode === 'all') return shuffleOrder[shuffleOrder.length - 1];
    return currentQueueIndex;
  }
  if (currentQueueIndex > 0) return currentQueueIndex - 1;
  if (repeatMode === 'all') return currentQueue.length - 1;
  return currentQueueIndex;
}

async function loadAndPlay(data) {
  if (!data) return false;
  currentSong = data.song || currentSong;
  if (data.queue) {
    currentQueue = data.queue;
    currentQueueIndex = data.queue_index ?? currentQueueIndex;
  }
  if (shuffleOn) buildShuffleOrder();

  if (data.type === 'file') {
    audio.src = fileUrl(data.path);
  } else if (data.type === 'stream') {
    audio.src = data.url;
  } else {
    showToast('Error de reproducción', 'error');
    return false;
  }

  await audio.play();
  streamRetryCount = 0;
  isPlaying = true;
  updatePlayButtons(true);
  updateNowPlaying(currentSong);
  updateLikeButtons();
  prefetchLyrics(currentSong?.id);
  return true;
}

async function playSong(songId) {
  try {
    const data = await pywebview.api.playSong(songId);
    if (!data) { showToast('No se puede reproducir esta canción', 'error'); return false; }
    currentQueue = data.queue || [data.song];
    currentQueueIndex = data.queue_index ?? currentQueue.findIndex(s => s.id === songId);
    if (currentQueueIndex < 0) currentQueueIndex = 0;
    if (shuffleOn) buildShuffleOrder();
    return loadAndPlay(data);
  } catch (e) {
    showToast('Error al reproducir: ' + e.message, 'error');
    return false;
  }
}

async function playPlaylist(playlistId, startIndex) {
  startIndex = startIndex || 0;
  try {
    const songs = await pywebview.api.getPlaylistSongs(playlistId);
    if (!songs?.length) { showToast('Playlist vacía', 'error'); return; }
    currentQueue = songs;
    currentQueueIndex = startIndex;
    if (shuffleOn) buildShuffleOrder();
    await pywebview.api.playSong(songs[startIndex].id);
    return playAtIndex(startIndex);
  } catch (e) { showToast('Error', 'error'); }
}

async function playAtIndex(index) {
  if (index < 0 || index >= currentQueue.length) return false;
  currentQueueIndex = index;
  const data = await pywebview.api.getStreamUrl(currentQueue[index].id);
  if (data) {
    data.queue = currentQueue;
    data.queue_index = index;
    return loadAndPlay(data);
  }
  return false;
}

async function togglePlay() {
  if (!currentSong) { showToast('Selecciona una canción primero'); return; }
  try {
    if (audio.paused) {
      await audio.play();
      isPlaying = true;
    } else {
      audio.pause();
      isPlaying = false;
    }
    updatePlayButtons(isPlaying);
    pywebview.api.togglePlay();
  } catch (e) {}
}

async function nextSong() {
  const nextIdx = getNextIndex();
  if (nextIdx < 0) { showToast('Fin de la cola'); return false; }
  return playAtIndex(nextIdx);
}

async function prevSong() {
  if (audio.currentTime > 3 && currentSong) {
    audio.currentTime = 0;
    return true;
  }
  const prevIdx = getPrevIndex();
  if (prevIdx === currentQueueIndex && audio.currentTime <= 3) return false;
  return playAtIndex(prevIdx);
}

function toggleShuffle() {
  shuffleOn = !shuffleOn;
  if (shuffleOn && currentQueue.length) buildShuffleOrder();
  updateModeButtons();
  showToast(shuffleOn ? 'Aleatorio activado' : 'Aleatorio desactivado');
}

function toggleRepeat() {
  const modes = ['off', 'all', 'one'];
  repeatMode = modes[(modes.indexOf(repeatMode) + 1) % modes.length];
  updateModeButtons();
  const labels = { off: 'Repetir desactivado', all: 'Repetir playlist', one: 'Repetir canción' };
  showToast(labels[repeatMode]);
}

function updateModeButtons() {
  document.querySelectorAll('.btn-shuffle').forEach(el => {
    el.classList.toggle('active-mode', shuffleOn);
  });
  document.querySelectorAll('.btn-repeat').forEach(el => {
    el.classList.remove('repeat-all', 'repeat-one');
    if (repeatMode === 'all') el.classList.add('active-mode', 'repeat-all');
    else if (repeatMode === 'one') el.classList.add('active-mode', 'repeat-one');
  });
}

async function toggleLike(songId) {
  const id = songId || currentSong?.id;
  if (!id) return;
  try {
    const result = await pywebview.api.toggleLike(id);
    updateLikeButtons(result.liked, id);
    showToast(result.liked ? 'Añadido a Me gusta' : 'Quitado de Me gusta', 'success');
  } catch (e) {
    showToast('Error al actualizar Me gusta', 'error');
  }
}

async function updateLikeButtons(liked, songId) {
  const id = songId || currentSong?.id;
  if (liked === undefined && id) {
    try { liked = await pywebview.api.isLiked(id); } catch (e) { liked = false; }
  }
  document.querySelectorAll('.btn-like').forEach(btn => {
    const match = !btn.dataset.songId || btn.dataset.songId === id;
    if (match) btn.classList.toggle('liked', !!liked);
  });
}

function prefetchLyrics(songId) {
  if (!songId) return;
  showLyricsLoading();
  pywebview.api.getLyrics(songId).then(lyrics => {
    if (lyrics && currentSong?.id === songId) renderLyrics(lyrics);
    else if (!lyrics && currentSong?.id === songId) showLyricsEmpty();
  }).catch(() => showLyricsEmpty());
}

function seekFromClick(e) {
  const bar = $('progressBar') || $('miniProgress');
  if (!bar) return;
  const rect = bar.getBoundingClientRect();
  const pct = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
  const pos = pct * (audio.duration || 0);
  audio.currentTime = pos;
  pywebview.api.seek(pos);
}

function seekMiniFromClick(e) {
  const bar = $('miniProgress');
  if (!bar) return;
  const rect = bar.getBoundingClientRect();
  const pct = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
  audio.currentTime = pct * (audio.duration || 0);
}

async function setVolume(val) {
  const v = parseInt(val) / 100;
  audio.volume = Math.max(0, Math.min(1, v));
  playerStatus.volume = parseInt(val);
  document.querySelectorAll('.volume-slider').forEach(s => { if (s.value != val) s.value = val; });
  try { await pywebview.api.setVolume(parseInt(val)); } catch (e) {}
}

// ===== Audio Events =====
let lastLyricsTick = 0;
audio.addEventListener('timeupdate', () => {
  const pos = audio.currentTime || 0;
  const dur = audio.duration || 0;
  playerStatus.position = pos;
  playerStatus.duration = dur;

  const ct = $('currentTime');
  const tt = $('totalTime');
  const mct = $('miniCurrentTime');
  const mtt = $('miniTotalTime');
  if (ct) ct.textContent = formatTime(pos);
  if (tt) tt.textContent = formatTime(dur);
  if (mct) mct.textContent = formatTime(pos);
  if (mtt) mtt.textContent = formatTime(dur);

  if (dur > 0) {
    const pct = Math.min(100, (pos / dur) * 100) + '%';
    const pf = $('progressFill');
    const mpf = $('miniProgressFill');
    if (pf) pf.style.width = pct;
    if (mpf) mpf.style.width = pct;
  }

  const now = performance.now();
  if (now - lastLyricsTick > 80) {
    lastLyricsTick = now;
    updateLyricsDisplay(pos);
  }
});

audio.addEventListener('play', () => {
  isPlaying = true;
  playerStatus.state = 'playing';
  updatePlayButtons(true);
});

audio.addEventListener('pause', () => {
  isPlaying = false;
  playerStatus.state = 'paused';
  updatePlayButtons(false);
});

audio.addEventListener('ended', async () => {
  if (repeatMode === 'one' && currentSong) {
    audio.currentTime = 0;
    await audio.play();
    return;
  }
  crossfadeToNext(async () => {
    await nextSong();
  });
});

audio.addEventListener('error', async () => {
  if (!currentSong || streamRetryCount >= 2) {
    showToast('Error de reproducción', 'error');
    updatePlayButtons(false);
    return;
  }
  streamRetryCount++;
  try {
    const data = await pywebview.api.refreshStreamUrl(currentSong.id);
    if (data?.type === 'stream' || data?.type === 'file') {
      audio.src = data.type === 'stream' ? data.url : data.path;
      await audio.play();
      return;
    }
  } catch (e) {}
  showToast('Error de reproducción', 'error');
  updatePlayButtons(false);
});

audio.addEventListener('loadedmetadata', () => {
  playerStatus.duration = audio.duration || 0;
  const dur = Math.floor(audio.duration || 0);
  const tt = $('totalTime');
  const mtt = $('miniTotalTime');
  const t = formatTime(dur);
  if (tt) tt.textContent = t;
  if (mtt) mtt.textContent = t;
  if (currentSong && dur > 0) {
    pywebview.api.updateSongDuration(currentSong.id, dur).catch(() => {});
  }
});

function updatePlayButtons(playing) {
  const paths = playing
    ? 'M6 19h4V5H6v14zm8-14v14h4V5h-4z'
    : 'M8 5v14l11-7z';
  [['mainPlayBtn', 36], ['miniPlayBtn', 30], ['homePlayBtn', 32]].forEach(([id, size]) => {
    const el = $(id);
    if (el) el.innerHTML = `<svg viewBox="0 0 24 24" width="${size}" height="${size}"><path fill="currentColor" d="${paths}"/></svg>`;
  });
}

function updateNowPlaying(song) {
  if (!song) return;
  const fields = [
    ['homeCurrentTitle', song.title || 'Sin título'],
    ['homeCurrentArtist', song.artist || ''],
    ['miniTitle', song.title || 'Sin título'],
    ['miniArtist', song.artist || ''],
    ['playerTitle', song.title || 'Selecciona una canción'],
    ['playerArtist', song.artist || ''],
  ];
  fields.forEach(([id, text]) => { const el = $(id); if (el) el.textContent = text; });
  const thumb = song.thumbnail ? `<img src="${song.thumbnail}" alt="">` : '';
  ['homeCurrentThumb', 'miniThumb', 'playerThumb'].forEach(id => {
    const el = $(id);
    if (el) el.innerHTML = thumb || el.innerHTML;
  });
  const cont = $('homeContinuePlaying');
  if (cont) cont.style.display = 'block';
  document.querySelectorAll('.song-item.active').forEach(el => el.classList.remove('active'));
  document.querySelectorAll(`.song-item[data-song-id="${song.id}"]`).forEach(el => el.classList.add('active'));
  updateLikeButtons(undefined, song.id);
}

// Keyboard shortcuts
document.addEventListener('keydown', (e) => {
  if (e.target.matches('input, textarea')) return;
  if (e.code === 'Space') { e.preventDefault(); togglePlay(); }
  if (e.code === 'ArrowRight' && e.shiftKey) nextSong();
  else if (e.code === 'ArrowLeft' && e.shiftKey) prevSong();
  if (e.code === 'KeyL' && currentSong) toggleLike();
  if (e.code === 'KeyS') toggleShuffle();
  if (e.code === 'KeyR') toggleRepeat();
});

// ===== Download =====
async function downloadSong(songId) {
  try {
    await pywebview.api.downloadSong(songId);
    showToast('Descarga iniciada');
    if (currentView === 'downloads') loadDownloads();
  } catch (e) { showToast('Error al descargar', 'error'); }
}

// ===== Add to Playlist =====
let addToPlaylistTargetId = null;

async function showAddToPlaylist(songId) {
  addToPlaylistTargetId = songId;
  const chooser = $('playlistChooser');
  try {
    const playlists = await pywebview.api.getPlaylists();
    chooser.innerHTML = '';
    if (!playlists.length) {
      chooser.innerHTML = '<div class="text-muted" style="padding:12px">No hay playlists. Crea una primero.</div>';
    }
    playlists.forEach(pl => {
      const btn = document.createElement('button');
      btn.className = 'btn-text btn-full';
      btn.textContent = pl.name;
      btn.onclick = () => addToPlaylistConfirm(pl.id);
      chooser.appendChild(btn);
    });
    chooser.innerHTML += '<hr style="border-color:var(--border);margin:8px 0">';
    const createBtn = document.createElement('button');
    createBtn.className = 'btn-primary btn-full';
    createBtn.textContent = '+ Nueva playlist';
    createBtn.onclick = () => { closeDialog(null, 'addToPlaylistDialog'); showCreatePlaylist(); };
    chooser.appendChild(createBtn);
  } catch (e) {}
  $('addToPlaylistDialog').style.display = 'flex';
}

async function addToPlaylistConfirm(playlistId) {
  if (!addToPlaylistTargetId) return;
  try {
    const song = await pywebview.api.getSong(addToPlaylistTargetId);
    const videoId = song?.youtube_id || '';
    await pywebview.api.addToPlaylist(playlistId, addToPlaylistTargetId, videoId);
    showToast('Agregada a la playlist');
    closeDialog(null, 'addToPlaylistDialog');
  } catch (e) { showToast('Error', 'error'); }
}
