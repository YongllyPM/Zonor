let syncActive = false;
let eqModalOpen = false;

async function loadSettings() {
  try {
    const settings = await pywebview.api.getSettings();
    $('defaultVolume').value = settings.volume || 80;
    $('volVal').textContent = settings.volume || 80;
    $('syncInterval').value = settings.sync_interval || 60;
    $('audioQualityYoutube').value = settings.audio_quality_youtube || 'high';
    $('audioQualityDeezer').value = settings.audio_quality_deezer || 'best';
    $('audioQualityApple').value = settings.audio_quality_apple || 'high';
    $('audioFormat').value = settings.audio_format || 'mp3';
    $('crossfade').value = settings.crossfade || 0;
    $('skipSilence').checked = settings.skip_silence === 'true';
    $('translationLang').value = settings.translation_lang || 'es';
    $('backupEnabled').checked = settings.backup_enabled === 'true';
    $('backupInterval').value = settings.backup_interval || 'monthly';
    if (settings.last_backup) {
      const d = new Date(settings.last_backup * 1000);
      $('lastBackupLabel').textContent = d.toLocaleString();
    } else {
      $('lastBackupLabel').textContent = 'Nunca';
    }
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
    audio_quality_youtube: $('audioQualityYoutube').value,
    audio_quality_deezer: $('audioQualityDeezer').value,
    audio_quality_apple: $('audioQualityApple').value,
    audio_format: $('audioFormat').value,
    crossfade: parseInt($('crossfade').value) || 0,
    skip_silence: $('skipSilence').checked ? 'true' : 'false',
    translation_lang: $('translationLang').value || 'es',
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
  if (settings.volume !== undefined && window.setVolume) {
    window.setVolume(settings.volume);
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

async function exportData() {
  try {
    showToast('Guardando datos...');
    const result = await pywebview.api.exportData();
    if (result?.ok) {
      showToast('Datos exportados', 'success');
    } else {
      showToast(result?.error || 'Exportación cancelada', 'error');
    }
  } catch(e) { showToast('Error al exportar: ' + e.message, 'error'); }
}

async function importData() {
  if (!confirm('⚠️ Importar datos reemplazará TODA la biblioteca actual (canciones, playlists, descargas y ajustes) con el contenido del archivo.\n\n¿Continuar?')) return;
  try {
    const result = await pywebview.api.importData();
    if (result?.ok) {
      showToast('Datos importados correctamente', 'success');
      if (window.loadLibrary) window.loadLibrary();
      if (window.loadPlaylists) window.loadPlaylists();
      if (window.loadSettings) window.loadSettings();
      if (window.loadDownloads) window.loadDownloads();
    } else {
      showToast(result?.error || 'Importación cancelada', 'error');
    }
  } catch(e) { showToast('Error al importar: ' + e.message, 'error'); }
}

async function backupNow() {
  try {
    showToast('Creando copia de seguridad...');
    const result = await pywebview.api.backupNow();
    if (result?.ok) {
      showToast('Copia creada: ' + result.path, 'success');
      if (window.loadSettings) window.loadSettings();
    } else {
      showToast(result?.error || 'Error al crear la copia', 'error');
    }
  } catch(e) { showToast('Error: ' + e.message, 'error'); }
}

async function saveBackupSettings() {
  let settings = {};
  try {
    const current = await pywebview.api.getSettings();
    settings = current || {};
  } catch(e) {}
  settings.backup_enabled = $('backupEnabled').checked ? 'true' : 'false';
  settings.backup_interval = $('backupInterval').value;
  try {
    await pywebview.api.saveSettings(JSON.stringify(settings));
    showToast('Configuración de copias guardada');
  } catch(e) {}
}

async function factoryReset() {
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
