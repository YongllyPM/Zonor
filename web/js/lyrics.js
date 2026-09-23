let currentLyrics = null;
let lyricsScrollPending = false;
let isEditing = false;
let editBackup = null;
let syncPreviewId = null;
let _semiParsedLines = null;
let _semiSongId = null;
let _semiPreviewTimer = null;
let _semiSearchText = '';

function showLyricsLoading() {
  const container = $('lyricsContainer');
  if (!container) return;
  exitEditMode();
  container.innerHTML = '<div class="lyrics-placeholder"><div class="lyrics-spinner"></div><p>Buscando letra sincronizada...</p></div>';
  updateLyricsTranslateBtn(null);
}

function showLyricsEmpty() {
  const container = $('lyricsContainer');
  if (!container) return;
  exitEditMode();
  container.innerHTML = '<div class="lyrics-placeholder"><p>Letra no disponible para esta canción</p><p class="text-muted" style="font-size:13px">Se busca en LRCLib y otras fuentes</p></div>';
  currentLyrics = null;
  updateLyricsTranslateBtn(null);
}

function exitEditMode() {
  if (isEditing) {
    isEditing = false;
    editBackup = null;
    const btn = $('btnEditLyrics');
    if (btn) btn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg> Editar';
  }
}

async function loadLyrics() {
  try {
    exitEditMode();
    showLyricsLoading();
    const lyricsData = await pywebview.api.getLyrics();
    if (lyricsData) renderLyrics(lyricsData);
    else showLyricsEmpty();
  } catch (e) {
    showLyricsEmpty();
  }
}

function renderLyrics(lyricsData) {
  const container = $('lyricsContainer');
  if (!container) return;
  if (!lyricsData?.lines?.length) {
    showLyricsEmpty();
    return;
  }

  currentLyrics = lyricsData;
  updateLyricsTranslateBtn(currentLyrics);
  const isSynced = lyricsData.type === 'synced' && lyricsData.lines.some(l => l.time > 0);
  let html = `<div class="lyrics-meta">${isSynced ? '● Sincronizada' : 'Letra sin sincronizar'} · ${escapeHtml(lyricsData.source || 'Zonor')}</div>`;
  html += '<div class="lyrics-lines">';
  lyricsData.lines.forEach((line, i) => {
    if (!line.text?.trim()) return;
    html += `<div class="lyric-line" data-idx="${i}" data-base-time="${line.time}" data-time="${line.time}">${escapeHtml(line.text)}</div>`;
  });
  html += '</div>';
  container.innerHTML = html;

  container.querySelectorAll('.lyric-line').forEach(el => {
    const t = parseFloat(el.dataset.time);
    if (t > 0) {
      el.onclick = () => {
        if (isEditing) return;
        ensureAudioCtx();
        activeAudio.currentTime = t;
        pywebview.api.seek(t);
        updateLyricsDisplay(t);
      };
    }
  });

  if (isSynced) updateLyricsDisplay(activeAudio.currentTime || 0);
}

function updateLyricsDisplay(position) {
  if (!currentLyrics?.lines) return;
  const linesEl = $('lyricsContainer')?.querySelector('.lyrics-lines');
  if (!linesEl) return;

  const children = linesEl.querySelectorAll('.lyric-line');
  if (!children.length) return;

  const isSynced = currentLyrics.type === 'synced';
  let activeIdx = -1;

  if (isSynced) {
    for (let i = currentLyrics.lines.length - 1; i >= 0; i--) {
      const line = currentLyrics.lines[i];
      const t = line.time;
      if (line.text?.trim() && t >= 0 && t <= position + 0.15) {
        activeIdx = i;
        break;
      }
    }
  }

  let visibleIdx = 0;
  for (let i = 0; i < currentLyrics.lines.length; i++) {
    if (!currentLyrics.lines[i].text?.trim()) continue;
    const el = children[visibleIdx];
    if (el) {
      el.classList.remove('active', 'past', 'upcoming');
      if (!isSynced) {
      } else if (i < activeIdx) {
        el.classList.add('past');
      } else if (i === activeIdx) {
        el.classList.add('active');
      } else {
        el.classList.add('upcoming');
      }
    }
    visibleIdx++;
  }

  if (isSynced && activeIdx >= 0 && !lyricsScrollPending) {
    lyricsScrollPending = true;
    requestAnimationFrame(() => {
      const currentLinesEl = $('lyricsContainer')?.querySelector('.lyrics-lines');
      const active = currentLinesEl?.querySelector('.lyric-line.active');
      if (active) active.scrollIntoView({ behavior: 'smooth', block: 'center' });
      lyricsScrollPending = false;
    });
    setTimeout(() => { lyricsScrollPending = false; }, 300);
  }
}

// ===== EDIT MODE (Local) =====
function toggleEditLyrics() {
  if (!currentLyrics?.lines?.length) return;
  const container = $('lyricsContainer');
  if (!container) return;

  if (isEditing) {
    exitEditMode();
    renderLyrics(currentLyrics);
    return;
  }

  isEditing = true;
  editBackup = JSON.parse(JSON.stringify(currentLyrics));
  const btn = $('btnEditLyrics');
  if (btn) btn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></svg> Guardar';

  const lrcLines = currentLyrics.lines.map(l => {
    if (l.time > 0) {
      const mins = Math.floor(l.time / 60);
      const secs = Math.floor(l.time % 60);
      const millis = Math.floor((l.time % 1) * 100);
      return `[${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}.${String(millis).padStart(2, '0')}] ${l.text}`;
    }
    return l.text;
  });

  container.innerHTML = `
    <div class="lyrics-meta">Editando letra — los cambios se guardan localmente</div>
    <textarea id="lyricsEditArea" class="lyrics-edit-textarea">${escapeHtml(lrcLines.join('\n'))}</textarea>
    <div class="lyrics-edit-actions">
      <button class="btn-secondary" onclick="cancelLyricsEdit()">Cancelar</button>
      <button class="btn-primary" onclick="saveLyricsEdit()">Guardar localmente</button>
    </div>
  `;
}

function cancelLyricsEdit() {
  if (editBackup) {
    currentLyrics = editBackup;
    editBackup = null;
  }
  exitEditMode();
  if (currentLyrics?.lines?.length) {
    renderLyrics(currentLyrics);
  } else {
    showLyricsEmpty();
  }
}

async function saveLyricsEdit() {
  const textarea = $('lyricsEditArea');
  if (!textarea) return;
  const text = textarea.value;

  const lines = parseUserLyricsText(text);
  if (!lines.length) {
    showToast('La letra no puede estar vacía', 'error');
    return;
  }

  const hasTime = lines.some(l => l.time > 0);
  const newLyrics = {
    type: hasTime ? 'synced' : 'plain',
    lyrics: text,
    source: 'Editado localmente',
    lines: lines,
  };

  const songId = getCurrentSongId();
  if (songId) {
    try {
      await pywebview.api.saveLyricsEdit(songId, JSON.stringify(newLyrics));
    } catch (e) {
      showToast('Error al guardar: ' + e.message, 'error');
      return;
    }
  }

  currentLyrics = newLyrics;
  exitEditMode();
  renderLyrics(newLyrics);
  showToast('Letra guardada localmente', 'success');
}

// ===== AI TRANSCRIPTION =====
function showAiWarning() {
  if (!currentSong?.id) {
    showToast('Reproduce una canción primero', 'error');
    return;
  }
  $('aiWarningDialog').style.display = 'flex';
}

async function startTranscription() {
  $('aiWarningDialog').style.display = 'none';
  const songId = currentSong?.id;
  if (!songId) return;

  try {
    const check = await pywebview.api.checkTranscriber();
    if (!check?.available) {
      const missing = check?.error || 'whisper';
      const label = missing === 'ffmpeg' ? 'ffmpeg' : 'openai-whisper';
      $('aiProgressDialog').style.display = 'flex';
      $('aiProgressStatus').textContent = `Instalando ${label}...`;
      $('aiProgressFill').style.width = '0%';

      window.__onInstallProgress = function(d) {
        if (d.progress != null) $('aiProgressFill').style.width = Math.min(d.progress, 95) + '%';
        if (d.status) $('aiProgressStatus').textContent = d.status;
      };

      window.__onInstallError = function(d) {
        window.__onInstallProgress = null;
        window.__onInstallError = null;
        window.__onInstallDone = null;
        $('aiProgressDialog').style.display = 'none';
        showToast('Error instalando ' + label + ': ' + (d?.error || 'desconocido'), 'error');
      };

      window.__onInstallDone = function(d) {
        window.__onInstallProgress = null;
        window.__onInstallError = null;
        window.__onInstallDone = null;
        if (d?.success) {
          $('aiProgressStatus').textContent = 'Instalado. Iniciando transcripción...';
          $('aiProgressFill').style.width = '100%';
          setTimeout(() => startTranscription(), 500);
        } else {
          $('aiProgressDialog').style.display = 'none';
          showToast('No se pudo instalar: ' + (d?.error || 'error desconocido'), 'error');
        }
      };

      try {
        await pywebview.api.installTranscriber();
      } catch (e) {
        $('aiProgressDialog').style.display = 'none';
        showToast('Error al iniciar instalación: ' + e.message, 'error');
      }
      return;
    }
  } catch (e) {
    showToast('Error al verificar dependencias: ' + e.message, 'error');
    return;
  }

  $('aiProgressDialog').style.display = 'flex';
  $('aiProgressStatus').textContent = 'Iniciando transcripción...';
  $('aiProgressFill').style.width = '0%';

  window.__onTranscriptionProgress = function(d) {
    if (d.progress) $('aiProgressFill').style.width = Math.min(d.progress, 95) + '%';
    if (d.status) $('aiProgressStatus').textContent = d.status;
  };

  window.__onTranscriptionDone = function(d) {
    window.__onTranscriptionProgress = null;
    window.__onTranscriptionDone = null;
    window.__onTranscriptionError = null;
    $('aiProgressDialog').style.display = 'none';
    if (d?.lyrics) {
      currentLyrics = d.lyrics;
      renderLyrics(d.lyrics);
      showToast('Letra transcrita con IA correctamente', 'success');
    } else {
      showToast('Error: resultado vacío. Usando respaldo...', 'error');
      loadLyrics();
    }
  };

  window.__onTranscriptionError = function(d) {
    window.__onTranscriptionProgress = null;
    window.__onTranscriptionDone = null;
    window.__onTranscriptionError = null;
    $('aiProgressDialog').style.display = 'none';
    const errMsg = d?.error || 'Error desconocido';
    showToast('IA falló: ' + errMsg + '. Usando fuentes estándar...', 'error');
    loadLyrics();
  };

  try {
    const result = await pywebview.api.transcribeLyrics(songId);
    if (!result?.started) {
      window.__onTranscriptionError({ error: result?.error || 'No se pudo iniciar' });
    }
  } catch (e) {
    window.__onTranscriptionError({ error: e.message });
  }
}

function showConfirmDialog(title, message, cancelText, confirmText) {
  return new Promise((resolve) => {
    const existing = $('confirmDialog');
    if (existing) existing.remove();

    const overlay = document.createElement('div');
    overlay.id = 'confirmDialog';
    overlay.className = 'dialog-overlay';
    overlay.style.display = 'flex';
    overlay.onclick = (e) => { if (e.target === overlay) { overlay.remove(); resolve(false); } };

    overlay.innerHTML = `
      <div class="dialog dialog-sm" onclick="event.stopPropagation()">
        <div class="dialog-header">
          <h2>${escapeHtml(title)}</h2>
          <button class="btn-icon" onclick="this.closest('.dialog-overlay').remove()">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
          </button>
        </div>
        <div class="dialog-body" style="gap:16px">
          <p style="white-space:pre-wrap;margin:0">${escapeHtml(message)}</p>
          <div style="display:flex;gap:8px;justify-content:flex-end">
            <button class="btn-secondary" id="confirmCancelBtn">${escapeHtml(cancelText)}</button>
            <button class="btn-primary" id="confirmOkBtn">${escapeHtml(confirmText)}</button>
          </div>
        </div>
      </div>`;

    document.body.appendChild(overlay);

    overlay.querySelector('#confirmCancelBtn').onclick = () => { overlay.remove(); resolve(false); };
    overlay.querySelector('#confirmOkBtn').onclick = () => { overlay.remove(); resolve(true); };
  });
}

// ===== CORRECT MODE =====
function showCorrectDialog() {
  const dialog = $('correctLyricsDialog');
  if (dialog) dialog.style.display = 'flex';
}

async function autoCorrectLyrics() {
  const dialog = $('correctLyricsDialog');
  if (dialog) dialog.style.display = 'none';

  const songId = getCurrentSongId();
  if (!songId) return;

  const song = await pywebview.api.getSong(songId);
  if (!song) return;

  showToast('Buscando corrección automática en LRCLib...', 'info');

  const results = await pywebview.api.searchLyrics(song.artist, song.title);
  if (!results?.length) {
    showToast('No se encontraron resultados en LRCLib', 'error');
    return;
  }

  const bestResult = results[0];
  const fetched = await pywebview.api.fetchLyricsById(bestResult.id);
  if (!fetched?.lyrics) {
    showToast('No se pudo obtener la letra de LRCLib', 'error');
    return;
  }

  currentLyrics = {
    type: fetched.type,
    lyrics: fetched.lyrics,
    source: `LRCLib #${fetched.id}`,
    lines: fetched.lines,
  };

  if (songId) {
    try {
      await pywebview.api.saveLyricsEdit(songId, JSON.stringify(currentLyrics));
    } catch (e) {
      showToast('Error al guardar: ' + e.message, 'error');
    }
  }

  renderLyrics(currentLyrics);
  showToast('Letra corregida automáticamente desde LRCLib', 'success');
}

async function semiManualCorrect() {
  const dialog = $('correctLyricsDialog');
  if (dialog) dialog.style.display = 'none';
  const songId = getCurrentSongId();
  let artist = '', title = '';
  if (songId) {
    try {
      const song = await pywebview.api.getSong(songId);
      if (song) {
        artist = song.artist || '';
        title = song.title || '';
        const current = currentLyrics;
        if (current?.lyrics) {
          $('semiManualTextarea').value = current.lyrics;
        }
      }
    } catch (e) {}
  }
  const rec = $('semiRecommendText');
  if (rec) {
    const searchText = `letra${title ? ' de ' + title : ''}${artist ? ' de ' + artist : ''}`;
    _semiSearchText = searchText;
    rec.innerHTML = `Busca en tu navegador: <strong>${escapeHtml(searchText)}</strong>`;
  }
  $('semiPreview').style.display = 'none';
  $('semiAutoSync').checked = true;
  $('semiSubmitToLrclib').checked = false;
  $('semiManualDialog').style.display = 'flex';
}

function semiAutoPreview() {
  clearTimeout(_semiPreviewTimer);
  _semiPreviewTimer = setTimeout(() => {
    if ($('semiManualTextarea')?.value.trim()) {
      semiPreviewLyrics();
    }
  }, 800);
}

function semiPreviewLyrics() {
  const textarea = $('semiManualTextarea');
  if (!textarea) return;
  const text = textarea.value.trim();
  if (!text) {
    showToast('Pega la letra primero', 'error');
    return;
  }

  const lines = parseUserLyricsText(text);
  const hasTime = lines.some(l => l.time > 0);

  if (!hasTime && $('semiAutoSync')?.checked) {
    const duration = getCurrentSongDuration();
    if (duration > 0) {
      const interval = duration / Math.max(lines.length, 1);
      lines.forEach((l, i) => { l.time = i * interval; });
    }
  }

  _semiParsedLines = lines;
  _semiSongId = getCurrentSongId();

  const preview = $('semiPreviewLines');
  const count = $('semiLineCount');
  if (count) count.textContent = lines.length;

  let html = '';
  lines.forEach((l, i) => {
    const t = l.time > 0 ? formatLrcTime(l.time) : '';
    const playBtn = l.time > 0
      ? `<button class="semi-play-btn" onclick="semiPlayLine(${l.time})" title="Escuchar desde aquí"><svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"/></svg></button>`
      : '';
    html += `<div class="semi-line" data-time="${l.time || 0}">${playBtn}<span class="semi-time">${t ? '[' + t + ']' : ''}</span><span class="semi-text">${escapeHtml(l.text)}</span></div>`;
  });
  preview.innerHTML = html || '<p class="text-muted">Sin líneas válidas</p>';
  $('semiPreview').style.display = 'block';
}

function semiBuildLyricsObject(lines) {
  const hasTime = lines.some(l => l.time > 0);
  const lrcText = lines.map(l => {
    if (l.time > 0) {
      const t = formatLrcTime(l.time);
      return `[${t}]${l.text}`;
    }
    return l.text;
  }).join('\n');
  return {
    type: hasTime ? 'synced' : 'plain',
    lyrics: lrcText,
    source: 'Corregido manualmente',
    lines: lines,
  };
}

async function semiSaveLocalOnly() {
  if (!_semiParsedLines?.length) {
    semiPreviewLyrics();
    if (!_semiParsedLines?.length) return;
  }
  const newLyrics = semiBuildLyricsObject(_semiParsedLines);
  const songId = _semiSongId || getCurrentSongId();
  if (songId) {
    try {
      await pywebview.api.saveLyricsEdit(songId, JSON.stringify(newLyrics));
    } catch (e) {
      showToast('Error al guardar: ' + e.message, 'error');
      return;
    }
  }
  currentLyrics = newLyrics;
  renderLyrics(newLyrics);
  $('semiManualDialog').style.display = 'none';
  _semiParsedLines = null;
  showToast('Letra guardada localmente', 'success');
}

async function semiSaveAndSubmit() {
  if (!_semiParsedLines?.length) {
    semiPreviewLyrics();
    if (!_semiParsedLines?.length) return;
  }
  const newLyrics = semiBuildLyricsObject(_semiParsedLines);
  const songId = _semiSongId || getCurrentSongId();
  if (songId) {
    try {
      await pywebview.api.saveLyricsEdit(songId, JSON.stringify(newLyrics));
    } catch (e) {
      showToast('Error al guardar local: ' + e.message, 'error');
      return;
    }
  }
  currentLyrics = newLyrics;
  renderLyrics(newLyrics);

  const song = songId ? await pywebview.api.getSong(songId) : null;
  try {
    const ok = await pywebview.api.submitLyricsCorrection(
      song?.artist || '',
      song?.title || '',
      song?.album || '',
      song?.duration || 0,
      newLyrics.type === 'plain' ? newLyrics.lyrics : '',
      newLyrics.type === 'synced' ? newLyrics.lyrics : '',
    );
    if (ok?.started) {
      showLrclibSubmitToast();
    } else if (ok?.success) {
      showToast('Letra guardada y enviada a LRCLib como corrección', 'success');
    } else if (ok?.error) {
      showToast('LRCLib rechazó el envío: ' + ok.error, 'warning');
    } else {
      showToast('Letra guardada localmente, pero LRCLib rechazó el envío', 'warning');
    }
  } catch (e) {
    showToast('Letra guardada localmente, error al enviar a LRCLib: ' + e.message, 'error');
  }

  $('semiManualDialog').style.display = 'none';
  _semiParsedLines = null;
}

// ===== SYNC MODE (Search & Preview) =====
async function openSyncDialog() {
  const songId = getCurrentSongId();
  if (songId) {
    try {
      const song = await pywebview.api.getSong(songId);
      if (song) {
        $('syncSearchArtist').value = song.artist || '';
        $('syncSearchTitle').value = song.title || '';
      }
    } catch (e) {}
  }
  $('syncResults').innerHTML = '<p class="text-muted">Presiona "Buscar" para buscar en LRCLib</p>';
  $('syncPreview').style.display = 'none';
  $('syncLyricsDialog').style.display = 'flex';
}

async function performLyricsSearch() {
  const artist = $('syncSearchArtist').value.trim();
  const title = $('syncSearchTitle').value.trim();
  if (!artist || !title) {
    showToast('Ingresa artista y título', 'error');
    return;
  }

  $('syncPreview').style.display = 'none';
  $('syncResults').innerHTML = '<div class="lyrics-spinner" style="margin:20px auto"></div>';

  try {
    const results = await pywebview.api.searchLyrics(artist, title);
    if (!results?.length) {
      $('syncResults').innerHTML = '<p class="text-muted">No se encontraron resultados en LRCLib</p>';
      return;
    }

    let html = `<div class="sync-result-count">${results.length} resultado(s) · <a href="#" onclick="event.preventDefault();autoAcceptBest()">Aceptar el mejor</a></div>`;
    results.forEach(r => {
      const badge = r.has_synced ? '<span class="sync-badge synced">Sincronizada</span>' : '<span class="sync-badge plain">Sin sincronía</span>';
      const dur = r.duration ? ` · ${Math.floor(r.duration / 60)}:${String(Math.floor(r.duration % 60)).padStart(2, '0')}` : '';
      html += `<div class="sync-result-item" onclick="previewSyncResult(${r.id})" data-id="${r.id}">
        <div class="sync-result-info">
          <strong>${escapeHtml(r.title)}</strong>
          <span class="text-muted">${escapeHtml(r.artist)}${dur}</span>
        </div>
        ${badge}
      </div>`;
    });
    $('syncResults').innerHTML = html;
  } catch (e) {
    $('syncResults').innerHTML = `<p class="text-muted">Error: ${escapeHtml(e.message)}</p>`;
  }
}

async function autoAcceptBest() {
  const resultsEl = $('syncResults');
  const first = resultsEl?.querySelector('.sync-result-item');
  if (!first) return;
  const id = parseInt(first.dataset.id);
  await previewSyncResult(id);
  await acceptSyncResult();
}

async function previewSyncResult(id) {
  syncPreviewId = id;
  $('syncPreview').style.display = 'block';
  $('syncPreviewText').textContent = 'Cargando...';
  $('btnAcceptSync').disabled = true;

  try {
    const data = await pywebview.api.fetchLyricsById(id);
    if (!data?.lyrics) {
      $('syncPreviewText').textContent = 'No se pudo obtener la letra';
      return;
    }
    const text = data.lyrics;
    $('syncPreviewText').textContent = text;
    $('syncPreviewText').dataset.artist = data.artist || '';
    $('syncPreviewText').dataset.title = data.title || '';
    $('syncPreviewText').dataset.duration = data.duration || 0;
    $('syncPreviewText').dataset.album = data.album || '';
    $('syncPreviewText').dataset.isSynced = data.type === 'synced' ? '1' : '0';
    $('btnAcceptSync').disabled = false;
  } catch (e) {
    $('syncPreviewText').textContent = 'Error: ' + e.message;
  }
}

function hideSyncPreview() {
  $('syncPreview').style.display = 'none';
  syncPreviewId = null;
}

async function acceptSyncResult() {
  if (!syncPreviewId) return;
  const preview = $('syncPreviewText');
  const text = preview.textContent;
  if (!text || text === 'Cargando...' || text.startsWith('No se pudo') || text.startsWith('Error')) return;

  try {
    const data = await pywebview.api.fetchLyricsById(syncPreviewId);
    if (!data) {
      showToast('Error al obtener la letra', 'error');
      return;
    }

    const newLyrics = {
      type: data.type,
      lyrics: data.lyrics,
      source: `LRCLib #${data.id}`,
      lines: data.lines,
    };

    const songId = getCurrentSongId();
    if (songId) {
      await pywebview.api.saveLyricsEdit(songId, JSON.stringify(newLyrics));
    }

    currentLyrics = newLyrics;
    renderLyrics(newLyrics);

    if ($('syncSubmitToLrclib')?.checked) {
      try {
        const ok = await pywebview.api.submitLyricsCorrection(
          data.artist || preview.dataset.artist || '',
          data.title || preview.dataset.title || '',
          data.album || preview.dataset.album || '',
          data.duration || parseInt(preview.dataset.duration) || 0,
          data.type === 'plain' ? data.lyrics : '',
          data.type === 'synced' ? data.lyrics : '',
        );
        if (ok?.started) {
          showLrclibSubmitToast();
        } else if (ok?.success) {
          showToast('Letra aceptada y enviada como corrección a LRCLib', 'success');
        } else if (ok?.error) {
          showToast('LRCLib rechazó el envío: ' + ok.error, 'warning');
        } else {
          showToast('Letra aceptada localmente, falló el envío a LRCLib', 'warning');
        }
      } catch (e) {
        showToast('Letra aceptada localmente, pero falló el envío a LRCLib: ' + e.message, 'error');
      }
    } else {
      showToast('Letra sincronizada correctamente', 'success');
    }

    $('syncLyricsDialog').style.display = 'none';
    syncPreviewId = null;
  } catch (e) {
    showToast('Error: ' + e.message, 'error');
  }
}

// ===== Helpers =====
function getCurrentSongId() {
  if (typeof currentSong !== 'undefined' && currentSong?.id) {
    return currentSong.id;
  }
  if (currentLyrics?.lines?.length && $('lyricsContainer')?.querySelector('.lyric-line')) {
    const songIdEl = document.querySelector('[data-song-id]');
    if (songIdEl) return songIdEl.dataset.songId;
  }
  return null;
}

function getCurrentSongDuration() {
  if (typeof currentSong !== 'undefined' && currentSong?.duration) {
    return currentSong.duration;
  }
  if (currentLyrics?.lines?.length) {
    const maxTime = Math.max(...currentLyrics.lines.map(l => l.time));
    if (maxTime > 0) return maxTime + 5;
  }
  return 180;
}

function formatLrcTime(seconds) {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  const millis = Math.floor((seconds % 1) * 100);
  return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}.${String(millis).padStart(2, '0')}`;
}

function parseUserLyricsText(text) {
  const lines = [];
  const pattern = /\[(\d{2}):(\d{2})[.:](\d{1,3})\]\s*(.*)/;
  for (const line of text.split('\n')) {
    const m = pattern.exec(line);
    if (m) {
      const mins = parseInt(m[1]);
      const secs = parseInt(m[2]);
      const frac = m[3];
      const fracSecs = frac.length === 2 ? parseInt(frac) / 100 : parseInt(frac) / 1000;
      lines.push({
        time: mins * 60 + secs + fracSecs,
        text: m[4].trim(),
      });
    } else if (line.trim()) {
      lines.push({ time: 0, text: line.trim() });
    }
  }
  return lines.sort((a, b) => a.time - b.time);
}

async function translateCurrentLyrics() {
  if (!currentLyrics) {
    showToast('No hay letra para traducir', 'error');
    return;
  }
  if (currentLyrics.translated_from) {
    await untranslateLyrics();
    return;
  }
  const btn = $('btnTranslateLyrics');
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="spin"><path d="m5 8 6 6"/><path d="m4 14 6-6 2-3"/><path d="M2 5h12"/><path d="M7 2v3"/><path d="m22 22-5-10-5 10"/><path d="M14 18h6"/></svg> Traduciendo...';
  }
  try {
    const songId = getCurrentSongId();
    const translated = await pywebview.api.translateLyrics(songId || null, null);
    if (translated && translated.lines && translated.lines.length) {
      currentLyrics = translated;
      renderLyrics(translated);
      showToast(`Letra traducida a ${translated.lang || 'es'}`, 'success');
    } else {
      showToast('No se pudo traducir la letra', 'error');
    }
  } catch (e) {
    showToast('Error al traducir: ' + (e.message || e), 'error');
  } finally {
    if (btn) {
      btn.disabled = false;
      updateLyricsTranslateBtn(currentLyrics);
    }
  }
}

async function untranslateLyrics() {
  const original = currentLyrics.original;
  if (!original?.lines?.length) {
    showToast('No se puede revertir la traducción', 'error');
    return;
  }
  const btn = $('btnTranslateLyrics');
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="spin"><path d="m5 8 6 6"/><path d="m4 14 6-6 2-3"/><path d="M2 5h12"/><path d="M7 2v3"/><path d="m22 22-5-10-5 10"/><path d="M14 18h6"/></svg> Revirtiendo...';
  }
  try {
    const songId = getCurrentSongId();
    if (songId) {
      await pywebview.api.saveLyricsEdit(songId, JSON.stringify(original));
    }
    delete original.original;
    currentLyrics = original;
    renderLyrics(original);
    showToast('Traducción desactivada', 'success');
  } catch (e) {
    showToast('Error al revertir: ' + (e.message || e), 'error');
  } finally {
    if (btn) btn.disabled = false;
    updateLyricsTranslateBtn(currentLyrics);
  }
}

function updateLyricsTranslateBtn(lyricsData) {
  const btn = $('btnTranslateLyrics');
  if (!btn) return;
  const isTranslated = !!(lyricsData?.translated_from);
  btn.classList.toggle('active', isTranslated);
  const label = isTranslated
    ? '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m5 8 6 6"/><path d="m4 14 6-6 2-3"/><path d="M2 5h12"/><path d="M7 2v3"/><path d="m22 22-5-10-5 10"/><path d="M14 18h6"/></svg> Restaurar'
    : '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m5 8 6 6"/><path d="m4 14 6-6 2-3"/><path d="M2 5h12"/><path d="M7 2v3"/><path d="m22 22-5-10-5 10"/><path d="M14 18h6"/></svg> Traducir';
  btn.title = isTranslated ? 'Restaurar letra original' : 'Traducir letra al idioma configurado';
  if (!btn.disabled) btn.innerHTML = label;
}

function copySemiRecommend() {
  if (!_semiSearchText) {
    showToast('No hay búsqueda para copiar', 'error');
    return;
  }
  navigator.clipboard.writeText(_semiSearchText).then(() => {
    showToast('Búsqueda copiada al portapapeles', 'success');
  }).catch(() => {
    const ta = document.createElement('textarea');
    ta.value = _semiSearchText;
    document.body.appendChild(ta);
    ta.select();
    document.execCommand('copy');
    document.body.removeChild(ta);
    showToast('Búsqueda copiada al portapapeles', 'success');
  });
}

function semiPlayLine(time) {
  if (!activeAudio || !activeAudio.src) {
    showToast('No hay canción reproduciéndose', 'error');
    return;
  }
  ensureAudioCtx();
  activeAudio.currentTime = time;
  if (activeAudio.paused) {
    activeAudio.play().catch(() => {});
  }
  document.querySelectorAll('.semi-line.playing').forEach(el => el.classList.remove('playing'));
  const line = document.querySelector(`.semi-line[data-time="${time}"]`);
  if (line) line.classList.add('playing');
}

function showLrclibSubmitToast() {
  if (typeof showToast !== 'function') return;
  showToast('Enviando a LRCLib: resolviendo desafío de seguridad...');

  window.__onLrclibSubmitProgress = function(d) {
    if (d?.status && typeof showToast === 'function') {
      showToast('LRCLib: ' + d.status, 'info');
    }
  };
  window.__onLrclibSubmitDone = function(d) {
    window.__onLrclibSubmitProgress = null;
    window.__onLrclibSubmitDone = null;
    if (d?.success) {
      showToast('Letra publicada en LRCLib correctamente', 'success');
    } else if (d?.error) {
      showToast('LRCLib rechazó el envío: ' + d.error, 'warning');
    } else {
      showToast('LRCLib rechazó el envío', 'warning');
    }
  };
}
