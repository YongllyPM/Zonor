let syncActive = false;
let eqModalOpen = false;

async function loadSettings() {
  try {
    const settings = await pywebview.api.getSettings();
    $('defaultVolume').value = settings.volume || 80;
    $('volVal').textContent = settings.volume || 80;
    $('syncInterval').value = settings.sync_interval || 60;
    $('audioQuality').value = settings.audio_quality || 'best';
    $('audioFormat').value = settings.audio_format || 'mp3';
    $('crossfade').value = settings.crossfade || 0;
    $('skipSilence').checked = settings.skip_silence === 'true';
    if (settings.equalizer) {
      try {
        const eq = JSON.parse(settings.equalizer);
        document.querySelectorAll('.eq-band input').forEach(s => {
          const band = s.dataset.freq;
          if (eq[band] !== undefined) s.value = eq[band];
        });
      } catch(e) {}
    }
  } catch(e) {}
}

async function toggleSync() {
  syncActive = !syncActive;
  try {
    if (syncActive) {
      await pywebview.api.startSync();
      $('syncToggleBtn').textContent = 'Desactivar sincronización';
      showToast('Sincronización activada');
    } else {
      await pywebview.api.stopSync();
      $('syncToggleBtn').textContent = 'Activar sincronización';
      showToast('Sincronización desactivada');
    }
  } catch(e) {}
}

async function forceSync() {
  try {
    const result = await pywebview.api.forceSync();
    if (result) showToast('Sincronización completada');
    else showToast('Inicia sesión primero', 'error');
  } catch(e) { showToast('Error de sincronización', 'error'); }
}

async function fixSync() {
  try {
    const result = await pywebview.api.fixSync();
    if (result?.success) {
      showToast(result.message || 'Reparación completada');
      if (result.deleted > 0) loadPlaylists();
    } else {
      showToast(result?.error || 'Error al reparar', 'error');
    }
  } catch(e) { showToast('Error al reparar sincronización', 'error'); }
}

async function saveAllSettings() {
  const settings = {
    volume: parseInt($('defaultVolume').value),
    sync_interval: parseInt($('syncInterval').value) || 60,
    audio_quality: $('audioQuality').value,
    audio_format: $('audioFormat').value,
    crossfade: parseInt($('crossfade').value) || 0,
    skip_silence: $('skipSilence').checked ? 'true' : 'false',
  };
  const eqData = {};
  document.querySelectorAll('.eq-band input').forEach(s => {
    eqData[s.dataset.freq] = parseInt(s.value);
  });
  settings.equalizer = JSON.stringify(eqData);
  try {
    await pywebview.api.saveSettings(JSON.stringify(settings));
    showToast('Configuración guardada');
    applyAudioSettings(settings);
  } catch(e) { showToast('Error', 'error'); }
}

function applyAudioSettings(settings) {
  if (window.applyCrossfade) window.applyCrossfade(settings.crossfade || 0);
  if (window.applySkipSilence) window.applySkipSilence(settings.skip_silence === 'true');
  if (window.applyEqualizer && settings.equalizer) {
    try { window.applyEqualizer(JSON.parse(settings.equalizer)); } catch(e) {}
  }
}

async function downloadAllLiked() {
  try {
    showToast('Iniciando descarga de Me gusta...');
    const result = await pywebview.api.downloadAllLiked();
    showToast(`Descargando ${result.downloaded} de ${result.total} canciones`);
  } catch(e) { showToast('Error al descargar', 'error'); }
}

function toggleEqualizer() {
  const modal = document.getElementById('equalizerModal');
  if (!modal) return;
  eqModalOpen = !eqModalOpen;
  modal.style.display = eqModalOpen ? 'flex' : 'none';
}

function closeEqualizer() {
  eqModalOpen = false;
  document.getElementById('equalizerModal').style.display = 'none';
  saveAllSettings();
}

function resetEqualizer() {
  document.querySelectorAll('.eq-band input').forEach(s => s.value = 0);
  document.querySelectorAll('.eq-val').forEach(el => el.textContent = '0');
  if (window.applyEqualizer) window.applyEqualizer({});
}

function factoryReset() {
  if (!confirm('⚠️ ¿Restablecer todo?\n\nSe borrarán TODAS las descargas, playlists guardadas, canciones con "Me gusta", y se cerrará la sesión.\n\n¿Estás seguro?')) return;
  if (!confirm('Esta acción NO se puede deshacer. ¿Continuar?')) return;
  (async () => {
    try {
      const result = await pywebview.api.factoryReset();
      if (result?.success) {
        showToast('Reproductor restablecido. Se cerrará la ventana.', 'success');
        setTimeout(() => {
          if (window.close) window.close();
        }, 2000);
      } else {
        showToast('Error al restablecer: ' + (result?.error || 'desconocido'), 'error');
      }
    } catch (e) {
      showToast('Error al restablecer: ' + e.message, 'error');
    }
  })();
}
