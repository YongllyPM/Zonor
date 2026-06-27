let currentLyrics = null;
let lyricsScrollPending = false;

function showLyricsLoading() {
  const container = $('lyricsContainer');
  if (!container) return;
  container.innerHTML = '<div class="lyrics-placeholder"><div class="lyrics-spinner"></div><p>Buscando letra sincronizada...</p></div>';
}

function showLyricsEmpty() {
  const container = $('lyricsContainer');
  if (!container) return;
  container.innerHTML = '<div class="lyrics-placeholder"><p>Letra no disponible para esta canción</p><p class="text-muted" style="font-size:13px">Se busca en LRCLib y otras fuentes</p></div>';
  currentLyrics = null;
}

async function loadLyrics() {
  try {
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
  const isSynced = lyricsData.type === 'synced' && lyricsData.lines.some(l => l.time > 0);
  let html = `<div class="lyrics-meta">${isSynced ? '● Sincronizada' : 'Letra sin sincronizar'} · ${escapeHtml(lyricsData.source || 'Zonor')}</div>`;
  html += '<div class="lyrics-lines">';
  lyricsData.lines.forEach((line, i) => {
    if (!line.text?.trim()) return;
    html += `<div class="lyric-line" data-idx="${i}" data-time="${line.time}">${escapeHtml(line.text)}</div>`;
  });
  html += '</div>';
  container.innerHTML = html;

  container.querySelectorAll('.lyric-line').forEach(el => {
    const t = parseFloat(el.dataset.time);
    if (t >= 0) {
      el.onclick = () => {
        audio.currentTime = t;
        pywebview.api.seek(t);
        updateLyricsDisplay(t);
      };
    }
  });

  if (isSynced) updateLyricsDisplay(audio.currentTime || 0);
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
      if (line.text?.trim() && line.time >= 0 && line.time <= position + 0.15) {
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
        // plain lyrics - no highlight
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
      const active = linesEl.querySelector('.lyric-line.active');
      if (active) active.scrollIntoView({ behavior: 'smooth', block: 'center' });
      lyricsScrollPending = false;
    });
  }
}
