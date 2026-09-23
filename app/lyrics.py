import re
import json
import os
import hashlib
import urllib.request
import urllib.parse
import time
import unicodedata
from pathlib import Path


COVER_SUFFIXES = re.compile(
    r'\s*[\(\[][^\)\]]*cover[^\)\]]*[\)\]]\s*'
    r'|\s*cover\s*(de|del|by|di|von|par)?\s*\S+.*'
    r'|\s*[\(\[][^\)\]]*(acústico|acoustic|live|en vivo|ao vivo)[^\)\]]*[\)\]]\s*',
    re.IGNORECASE
)

LANG_COMMON_WORDS = {
    'es': set('que de el la los las un una por con no más pero como este ha si ya '
              'todo muy bien también entre hasta sobre cuando desde donde cada sin '
              'otro otra otros otras ahora aquí donde así porque sin bajo antes '
              'después ellos ellas mi mis tu tus su sus nos les dio dar haya sido '
              'tiene hay fue ser estar haber hacer decir poder querer ir venir '
              'saber ver poner salir llevar decir'.split()),
    'pt': set('que de o a os as um uma por com não mais mas como este esta isso '
              'também entre até sobre quando desde onde cada sem outro outra outros '
              'agora aqui onde assim porque antes depois eles elas meu minha seus '
              'suas nos lhes foi ser estar haver fazer poder querer ir vir saber '
              'ver pôr sair levar dizer ter há'.split()),
    'fr': set('que de le la les un une des en pour avec mais plus ce ces son sa '
              'ses leur leurs nous vous ils elles aussi entre sur quand depuis '
              'comme autre autres où pourquoi sans avant après être avoir faire '
              'dire aller venir voir pouvoir vouloir savoir mettre donner prendre'.split()),
    'it': set('che di il la le lo gli un una dei per con non più ma come questo '
              'questa questo anche tra su quando da dove ogni senza altro altra '
              'altri essere avere fare dire andare venire vedere potere volere '
              'sapere mettere dare prendere'.split()),
    'de': set('der die das ein eine den dem des und in von zu ist nicht mit auf '
              'für an er sie es auch als wie noch nach bei über aber aus hat nur '
              'oder am vor wenn dass ich du wir ihr habe bist sind haben wird '
              'wurde kann soll will muss'.split()),
    'ja': set(),
    'ko': set(),
    'zh': set(),
    'ru': set(),
    'ar': set(),
    'hi': set(),
}


def _char_range(ch):
    cp = ord(ch)
    if 0x3040 <= cp <= 0x309F or 0x30A0 <= cp <= 0x30FF or 0x4E00 <= cp <= 0x9FFF:
        return 'ja'
    if 0xAC00 <= cp <= 0xD7AF or 0x1100 <= cp <= 0x11FF:
        return 'ko'
    if 0x0400 <= cp <= 0x04FF:
        return 'ru'
    if 0x0600 <= cp <= 0x06FF or 0xFB50 <= cp <= 0xFDFF or 0xFE70 <= cp <= 0xFEFF:
        return 'ar'
    if 0x0900 <= cp <= 0x097F:
        return 'hi'
    return None


def detect_language(text, title_hint='', artist_hint=''):
    if not text:
        return 'en'

    combined_hint = f"{title_hint} {artist_hint}".lower()
    if any(kw in combined_hint for kw in [' cover', 'acoustic', 'acústico', 'ao vivo', 'live version']):
        pass

    all_text = text.lower()
    words = re.findall(r'[a-záéíóúñüàèìòùâêîôûãõäëïöÿç]+', all_text)
    if not words:
        pass
    else:
        word_set = set(words)
        best_lang = 'en'
        best_score = 0
        for lang, common in LANG_COMMON_WORDS.items():
            if lang in ('ja', 'ko', 'zh', 'ru', 'ar', 'hi'):
                continue
            if not common:
                continue
            score = len(word_set & common)
            if score > best_score:
                best_score = score
                best_lang = lang
        if best_score >= 3:
            return best_lang

    char_langs = {}
    sample = text[:3000]
    for ch in sample:
        if ch.isalpha():
            r = _char_range(ch)
            if r:
                char_langs[r] = char_langs.get(r, 0) + 1
    if char_langs:
        dominant = max(char_langs, key=char_langs.get)
        total_alpha = sum(1 for ch in sample if ch.isalpha())
        if total_alpha > 0 and char_langs[dominant] / total_alpha > 0.15:
            return dominant

    return 'en'


class LyricsFetcher:
    def __init__(self, ytmusic_handler=None):
        self.cache = {}
        self.ytmusic = ytmusic_handler

    @staticmethod
    def _clean_for_search(text):
        clean = COVER_SUFFIXES.sub('', text)
        clean = re.sub(r'\s*[\(\[][^\)\]]*(remix|sped up|slowed|nightcore|live|acoustic)[^\)\]]*[\)\]]\s*', '', clean, flags=re.IGNORECASE)
        clean = re.sub(r'\s*-\s*(cover|remix|live|acoustic|sped up|slowed).*$', '', clean, flags=re.IGNORECASE)
        clean = re.sub(r'\s+', ' ', clean).strip()
        return clean or text

    def get_synced_lyrics(self, artist, title, duration=0, song_id=None, download_dir=None):
        cache_key = f"{artist}|{title}".lower()
        if cache_key in self.cache:
            return self.cache[cache_key]

        clean_artist = self._clean_for_search(artist)
        clean_title = self._clean_for_search(title)

        if download_dir:
            lyrics = self._from_lrc_file(clean_artist, clean_title, download_dir)
            if lyrics:
                self.cache[cache_key] = lyrics
                return lyrics

        if song_id:
            lyrics = self._from_youtube(song_id, duration)
            if lyrics:
                yt_lang = detect_language(lyrics.get('lyrics', ''), title, artist)
                if yt_lang not in ('en', 'unknown'):
                    self.cache[cache_key] = lyrics
                    return lyrics
                lyrics = None

        if song_id and self.ytmusic and self.ytmusic.is_authenticated():
            lyrics = self._from_ytmusic(song_id, duration)
            if lyrics:
                ytm_lang = detect_language(lyrics.get('lyrics', ''), title, artist)
                if ytm_lang not in ('en', 'unknown'):
                    self.cache[cache_key] = lyrics
                    return lyrics
                lyrics = None

        lyrics = self._from_lrclib_best(clean_artist, clean_title, duration, title_hint=title, artist_hint=artist)
        if lyrics:
            self.cache[cache_key] = lyrics
            return lyrics

        lyrics = self._from_syncedlyrics(clean_artist, clean_title, duration, title_hint=title, artist_hint=artist)
        if lyrics:
            self.cache[cache_key] = lyrics
            return lyrics

        lyrics = self._from_spotify(clean_artist, clean_title)
        if lyrics:
            self.cache[cache_key] = lyrics
            return lyrics

        return None

    def _from_lrc_file(self, artist, title, download_dir):
        safe = self._safe_name(artist, title)
        for f in Path(download_dir).iterdir():
            if f.suffix == '.lrc' and safe in f.stem:
                try:
                    text = f.read_text(encoding='utf-8')
                    lines = self._parse_lrc(text)
                    if lines:
                        return {
                            'type': 'synced',
                            'lyrics': text,
                            'source': 'Archivo LRC',
                            'lines': lines
                        }
                    plain = [l.strip() for l in text.split('\n') if l.strip() and not l.startswith('[')]
                    if plain:
                        lines = self._sync_plain(plain, 0)
                        return {
                            'type': 'plain',
                            'lyrics': '\n'.join(plain),
                            'source': 'Archivo LRC',
                            'lines': lines
                        }
                except Exception:
                    pass
        return None

    def _from_youtube(self, song_id, duration):
        try:
            import subprocess
            import sys
            root = Path(__file__).parent.parent
            ytdlp = None
            for c in [str(root / 'bin' / 'yt-dlp.exe'), 'yt-dlp.exe', 'yt-dlp']:
                try:
                    subprocess.run([c, '--version'], capture_output=True, timeout=3,
                                   creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                    ytdlp = c
                    break
                except Exception:
                    continue
            if not ytdlp:
                try:
                    import yt_dlp
                    ytdlp = 'library'
                except ImportError:
                    return None

            url = f"https://www.youtube.com/watch?v={song_id}"
            if ytdlp == 'library':
                import yt_dlp
                with yt_dlp.YoutubeDL({'quiet': True, 'no_warnings': True}) as ydl:
                    info = ydl.extract_info(url, download=False)
                    lyrics_text = info.get('lyrics') or ''
                    if not lyrics_text and info.get('description'):
                        desc = info.get('description', '')
                        lyrics_text = self._extract_from_description(desc)
                    if not lyrics_text:
                        return None
            else:
                cmd = [ytdlp, '--quiet', '--no-warnings', '--print', '%(lyrics)s',
                       '--print', '%(description)s', url]
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=15,
                                      creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                out = proc.stdout.strip()
                if not out:
                    return None
                parts = out.split('\n', 1)
                lyrics_text = parts[0] or ''
                if not lyrics_text and len(parts) > 1:
                    lyrics_text = self._extract_from_description(parts[1])
                if not lyrics_text:
                    return None

            lines = self._parse_lrc(lyrics_text)
            if lines:
                return {
                    'type': 'synced',
                    'lyrics': lyrics_text,
                    'source': 'YouTube',
                    'lines': lines
                }
            plain = [l.strip() for l in lyrics_text.split('\n') if l.strip()]
            if plain:
                lines = self._sync_plain(plain, duration)
                return {
                    'type': 'synced' if any(l['time'] > 0 for l in lines) else 'plain',
                    'lyrics': '\n'.join(plain),
                    'source': 'YouTube',
                    'lines': lines
                }
        except Exception as e:
            print(f"YouTube lyrics error: {e}")
        return None

    def _extract_from_description(self, desc):
        lines = desc.split('\n')
        lyrics = []
        in_lyrics = False
        for line in lines:
            lower = line.strip().lower()
            if 'lyrics' in lower and ('---' in line or '===' in line or '___' in line):
                in_lyrics = True
                continue
            if in_lyrics and (lower.startswith('tracklist') or lower.startswith('album') or
                             'follow' in lower or 'subscribe' in lower):
                if len(lyrics) > 3:
                    break
                in_lyrics = False
                continue
            if in_lyrics and line.strip():
                lyrics.append(line.strip())
        return '\n'.join(lyrics) if len(lyrics) > 3 else ''

    def _sync_plain(self, lines, duration):
        if not duration or duration <= 0:
            return [{'time': 0, 'text': l} for l in lines]
        interval = duration / max(len(lines), 1)
        return [{'time': i * interval, 'text': l} for i, l in enumerate(lines)]

    def _from_syncedlyrics(self, artist, title, duration, title_hint='', artist_hint=''):
        try:
            import syncedlyrics
            query = f"{artist} - {title}"
            lrc_text = syncedlyrics.search(query, synced_only=True)
            if lrc_text:
                lang = detect_language(lrc_text, title_hint, artist_hint)
                lines = self._parse_lrc(lrc_text)
                if lines:
                    return {
                        'type': 'synced',
                        'lyrics': lrc_text,
                        'source': f'SyncedLyrics [{lang}]',
                        'lines': lines,
                        'lang': lang,
                    }
            lrc_text = syncedlyrics.search(query, synced_only=False)
            if lrc_text:
                lang = detect_language(lrc_text, title_hint, artist_hint)
                lines = self._parse_lrc(lrc_text)
                if lines:
                    return {
                        'type': 'synced',
                        'lyrics': lrc_text,
                        'source': f'SyncedLyrics [{lang}]',
                        'lines': lines,
                        'lang': lang,
                    }
                plain = [l for l in lrc_text.split('\n') if l.strip() and not l.startswith('[')]
                if plain:
                    lines = self._sync_plain(plain, duration)
                    return {
                        'type': 'synced' if any(l['time'] > 0 for l in lines) else 'plain',
                        'lyrics': '\n'.join(plain),
                        'source': f'SyncedLyrics [{lang}]',
                        'lines': lines,
                        'lang': lang,
                    }
        except ImportError:
            pass
        except Exception as e:
            print(f"SyncedLyrics error: {e}")
        return None

    def _from_ytmusic(self, song_id, duration):
        try:
            yt = getattr(self.ytmusic, 'yt', None)
            if not yt:
                return None
            playlist = yt.get_watch_playlist(song_id)
            if not playlist:
                return None
            lyrics_id = None
            if isinstance(playlist, dict):
                for item in playlist.get('tracks', []):
                    if item.get('lyrics'):
                        lyrics_id = item['lyrics']
                        break
                if not lyrics_id and playlist.get('lyrics'):
                    lyrics_id = playlist['lyrics']
            if not lyrics_id:
                return None
            lyrics_data = yt.get_lyrics(lyrics_id)
            if not lyrics_data:
                return None
            if isinstance(lyrics_data, dict):
                source = lyrics_data.get('source', 'YouTube Music')
                if lyrics_data.get('lyrics'):
                    lrc_text = lyrics_data['lyrics']
                    lines = self._parse_lrc(lrc_text)
                    if lines:
                        return {
                            'type': 'synced',
                            'lyrics': lrc_text,
                            'source': source,
                            'lines': lines
                        }
                    plain = [l for l in lrc_text.split('\n') if l.strip()]
                    if plain:
                        lines = self._sync_plain(plain, duration)
                        return {
                            'type': 'synced' if any(l['time'] > 0 for l in lines) else 'plain',
                            'lyrics': '\n'.join(plain),
                            'source': source,
                            'lines': lines
                        }
        except Exception as e:
            print(f"YouTube Music lyrics error: {e}")
        return None

    def _from_lrclib(self, artist, title, duration):
        try:
            artist_enc = urllib.parse.quote(artist)
            title_enc = urllib.parse.quote(title)
            url = f"https://lrclib.net/api/get?artist_name={artist_enc}&track_name={title_enc}"
            if duration > 0:
                url += f"&duration={int(duration)}"

            req = urllib.request.Request(url, headers={
                'User-Agent': 'Zonor/1.0',
                'Accept': 'application/json'
            })
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode())

            if data.get('syncedLyrics'):
                return {
                    'type': 'synced',
                    'lyrics': data['syncedLyrics'],
                    'source': 'LRCLib',
                    'lines': self._parse_lrc(data['syncedLyrics']),
                    'duration': data.get('duration') or 0,
                }
            elif data.get('plainLyrics'):
                plain = [l for l in data['plainLyrics'].split('\n') if l.strip()]
                lines = self._sync_plain(plain, duration)
                return {
                    'type': 'synced' if any(l['time'] > 0 for l in lines) else 'plain',
                    'lyrics': data['plainLyrics'],
                    'source': 'LRCLib',
                    'lines': lines,
                    'duration': data.get('duration') or 0,
                }
        except Exception as e:
            print(f"LRCLib error: {e}")
        return None

    def _from_lrclib_best(self, artist, title, duration, title_hint='', artist_hint=''):
        try:
            params = urllib.parse.urlencode({
                'artist_name': artist,
                'track_name': title,
            })
            url = f"https://lrclib.net/api/search?{params}"
            req = urllib.request.Request(url, headers={
                'User-Agent': 'Zonor/1.0',
                'Accept': 'application/json'
            })
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())

            if not data or not isinstance(data, list):
                return None

            hint_lang = detect_language('', title_hint, artist_hint)
            scored = []
            for item in data:
                synced = item.get('syncedLyrics', '')
                plain = item.get('plainLyrics', '')
                text = synced or plain
                if not text:
                    continue
                lang = detect_language(text, title_hint, artist_hint)
                dur = item.get('duration', 0)
                dur_diff = abs(dur - duration) if duration > 0 and dur > 0 else 9999
                score = 0
                if lang == hint_lang:
                    score += 100
                if dur_diff < 3:
                    score += 50
                elif dur_diff < 10:
                    score += 20
                elif dur_diff < 30:
                    score += 5
                scored.append((score, item, lang, synced, plain))

            scored.sort(key=lambda x: x[0], reverse=True)

            for score, item, lang, synced, plain in scored[:5]:
                if synced:
                    lines = self._parse_lrc(synced)
                    if lines:
                        return {
                            'type': 'synced',
                            'lyrics': synced,
                            'source': f'LRCLib [{lang}]',
                            'lines': lines,
                            'lang': lang,
                            'lrclib_id': item.get('id'),
                            'duration': item.get('duration', 0) or 0,
                        }
                elif plain:
                    plain_lines = [l for l in plain.split('\n') if l.strip()]
                    if plain_lines:
                        lines = self._sync_plain(plain_lines, duration or item.get('duration', 0))
                        return {
                            'type': 'synced' if any(l['time'] > 0 for l in lines) else 'plain',
                            'lyrics': plain,
                            'source': f'LRCLib [{lang}]',
                            'lines': lines,
                            'lang': lang,
                            'lrclib_id': item.get('id'),
                            'duration': item.get('duration', 0) or 0,
                        }

            if scored:
                score, item, lang, synced, plain = scored[0]
                if synced:
                    lines = self._parse_lrc(synced)
                    if lines:
                        return {
                            'type': 'synced',
                            'lyrics': synced,
                            'source': f'LRCLib [{lang}]',
                            'lines': lines,
                            'lang': lang,
                        }
                elif plain:
                    plain_lines = [l for l in plain.split('\n') if l.strip()]
                    if plain_lines:
                        lines = self._sync_plain(plain_lines, duration or item.get('duration', 0))
                        return {
                            'type': 'synced' if any(l['time'] > 0 for l in lines) else 'plain',
                            'lyrics': plain,
                            'source': f'LRCLib [{lang}]',
                            'lines': lines,
                            'lang': lang,
                        }

        except Exception as e:
            print(f"LRCLib search error: {e}")
        return None

    def _from_spotify(self, artist, title):
        try:
            query = urllib.parse.quote(f"{artist} {title}")
            url = f"https://spotify-lyric-api-984e7b4face0.herokuapp.com/?trackname={query}"
            req = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0'
            })
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode())

            if data.get('lyrics'):
                lines = []
                for line in data['lyrics']:
                    if isinstance(line, dict):
                        lines.append({
                            'time': line.get('time', 0) / 1000,
                            'text': line.get('words', '')
                        })
                    elif isinstance(line, str):
                        lines.append({'time': 0, 'text': line})

                return {
                    'type': 'synced' if any(l['time'] > 0 for l in lines) else 'plain',
                    'lyrics': '\n'.join([l['text'] for l in lines]),
                    'source': 'Spotify',
                    'lines': lines
                }
        except Exception as e:
            print(f"Spotify lyrics error: {e}")
        return None

    def _parse_lrc(self, lrc_text):
        lines = []
        pattern = re.compile(r'\[(\d{2}):(\d{2})[.:](\d{1,3})\]\s*(.*)')
        for line in lrc_text.split('\n'):
            m = pattern.match(line)
            if m:
                mins = int(m.group(1))
                secs = int(m.group(2))
                frac = m.group(3)
                if len(frac) == 2:
                    frac_secs = int(frac) / 100
                else:
                    frac_secs = int(frac) / 1000
                time_secs = mins * 60 + secs + frac_secs
                lines.append({'time': time_secs, 'text': m.group(4).strip()})
        lines = [l for l in lines if l['text']]
        lines = self._strip_credit_lines(lines)
        return sorted(lines, key=lambda x: x['time'])

    _CREDIT_RE = re.compile(
        r'^\s*(作词|作曲|作詞|編曲|编曲|制作|製作|出品|监制|監製|企画|企划|混音|後期|'
        r'lyrics? by|music by|composed by|composer|produced by|producer|written by|'
        r'arranged by|written and composed|vocals? by|performed by|mastered by|'
        r'engineered by|mixed by|recorded by|thanks? to|special thanks|'
        r'translation by|official lyrics|album\b|lyrics and music|music & lyrics)\s*[:：]?-?\s*',
        re.IGNORECASE
    )

    def _strip_credit_lines(self, lines):
        if not lines or not any(l['time'] > 0 for l in lines):
            return lines
        first_vocal = None
        for l in lines:
            t = l['time']
            if t <= 0:
                continue
            if self._CREDIT_RE.match(l['text']):
                continue
            first_vocal = t
            break
        if first_vocal is None:
            return lines
        kept = []
        for l in lines:
            if 0 < l['time'] < first_vocal and self._CREDIT_RE.match(l['text']):
                continue
            kept.append(l)
        if len(kept) == len(lines):
            return lines
        return kept or lines

    def _safe_name(self, artist, title):
        name = re.sub(r'[<>:"/\\|?*]', '_', f"{artist} - {title}")
        return name[:180] or 'track'

    def save_lrc(self, artist, title, lyrics_data, download_dir):
        if not lyrics_data or not download_dir:
            return
        safe = self._safe_name(artist, title)
        lrc_path = Path(download_dir) / f"{safe}.lrc"
        try:
            lines = lyrics_data.get('lines', [])
            if not lines:
                return
            lrc_lines = []
            has_time = any(l.get('time', 0) > 0 for l in lines)
            if has_time:
                for l in lines:
                    t = l.get('time', 0)
                    mins = int(t // 60)
                    secs = int(t % 60)
                    millis = int((t % 1) * 100)
                    lrc_lines.append(f"[{mins:02d}:{secs:02d}.{millis:02d}]{l['text']}")
            else:
                for l in lines:
                    lrc_lines.append(l['text'])
            lrc_path.write_text('\n'.join(lrc_lines), encoding='utf-8')
        except Exception as e:
            print(f"Save LRC error: {e}")

    def get_plain_lyrics(self, artist, title):
        result = self.get_synced_lyrics(artist, title)
        if result:
            return result.get('lyrics', '')
        return ''

    def search_lrclib(self, artist, title):
        try:
            params = urllib.parse.urlencode({
                'artist_name': artist,
                'track_name': title,
            })
            url = f"https://lrclib.net/api/search?{params}"
            req = urllib.request.Request(url, headers={
                'User-Agent': 'Zonor/1.0',
                'Accept': 'application/json'
            })
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
            results = []
            for item in data if isinstance(data, list) else []:
                results.append({
                    'id': item.get('id'),
                    'artist': item.get('artistName', ''),
                    'title': item.get('trackName', ''),
                    'album': item.get('albumName', ''),
                    'duration': item.get('duration', 0),
                    'has_synced': bool(item.get('syncedLyrics')),
                    'has_plain': bool(item.get('plainLyrics')),
                })
            return results
        except Exception as e:
            print(f"LRCLib search error: {e}")
            return []

    def fetch_lrclib_by_id(self, lrclib_id):
        try:
            url = f"https://lrclib.net/api/get/{lrclib_id}"
            req = urllib.request.Request(url, headers={
                'User-Agent': 'Zonor/1.0',
                'Accept': 'application/json'
            })
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
            if not data:
                return None
            synced = data.get('syncedLyrics')
            plain = data.get('plainLyrics')
            if synced or plain:
                text = synced or plain
                lines = self._parse_lrc(text) if synced else self._sync_plain(
                    [l for l in plain.split('\n') if l.strip()], data.get('duration', 0))
                has_time = any(l.get('time', 0) > 0 for l in lines)
                return {
                    'id': data.get('id'),
                    'type': 'synced' if has_time else 'plain',
                    'lyrics': text,
                    'lines': lines,
                    'source': f"LRCLib #{data.get('id')}",
                    'artist': data.get('artistName', ''),
                    'title': data.get('trackName', ''),
                    'album': data.get('albumName', ''),
                    'duration': data.get('duration', 0),
                }
            return None
        except Exception as e:
            print(f"LRCLib fetch error: {e}")
            return None

    def submit_to_lrclib(self, artist, title, album, duration, plain_lyrics, synced_lyrics,
                         on_progress=None):
        """Envía letras a LRCLib usando el nuevo sistema de proof-of-work challenge."""
        try:
            if on_progress:
                on_progress(5, 'Solicitando challenge...')

            challenge = self._request_challenge()
            if not challenge:
                return {'success': False, 'error': 'No se pudo obtener el challenge'}

            prefix = challenge.get('prefix')
            target = challenge.get('target')
            if not prefix or not target:
                return {'success': False, 'error': 'Challenge inválido'}

            if on_progress:
                on_progress(20, 'Resolviendo desafío de seguridad...')

            nonce = self._solve_challenge(prefix, target, on_progress)
            if nonce is None:
                return {'success': False, 'error': 'No se pudo resolver el challenge'}

            token = f"{prefix}:{nonce}"

            if on_progress:
                on_progress(80, 'Publicando letras...')

            body = {
                'artistName': artist,
                'trackName': title,
                'albumName': album or '',
                'duration': int(duration) if duration else 0,
                'plainLyrics': plain_lyrics or '',
            }
            if synced_lyrics:
                body['syncedLyrics'] = synced_lyrics
            data = json.dumps(body).encode()
            req = urllib.request.Request(
                'https://lrclib.net/api/publish',
                data=data,
                headers={
                    'User-Agent': 'Zonor/1.0 (https://github.com/YongllyPM/Zonor)',
                    'Content-Type': 'application/json',
                    'Accept': 'application/json',
                    'X-Publish-Token': token,
                },
                method='POST'
            )
            with urllib.request.urlopen(req, timeout=20) as resp:
                return {'success': resp.status in (200, 201, 204)}
        except urllib.error.HTTPError as e:
            try:
                detail = e.read().decode('utf-8', 'replace')
            except Exception:
                detail = ''
            msg = f"HTTP {e.code}: {e.reason}"
            if detail and '<' not in detail:
                msg += f" — {detail[:200]}"
            print(f"LRCLib publish HTTP error: {msg}")
            return {'success': False, 'error': msg}
        except Exception as e:
            print(f"LRCLib submit error: {e}")
            return {'success': False, 'error': str(e)}

    def _request_challenge(self):
        try:
            req = urllib.request.Request(
                'https://lrclib.net/api/request-challenge',
                headers={
                    'User-Agent': 'Zonor/1.0 (https://github.com/YongllyPM/Zonor)',
                    'Accept': 'application/json',
                },
                method='POST'
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode('utf-8'))
        except Exception as e:
            print(f"LRCLib request-challenge error: {e}")
            return None

    @staticmethod
    def _solve_challenge(prefix, target, on_progress=None):
        """Encuentra un nonce tal que SHA256(prefix:nonce) < target (comparado como hex)."""
        target_hex = target.lower()
        try:
            target_int = int(target_hex, 16)
        except ValueError:
            return None

        started = time.time()
        last_report = time.time()
        n = 0
        while True:
            digest = hashlib.sha256(f"{prefix}:{n}".encode()).hexdigest()
            if int(digest, 16) < target_int:
                return str(n)
            n += 1
            now = time.time()
            if on_progress and now - last_report >= 1:
                last_report = now
                rate = n / max(now - started, 0.1)
                on_progress(20, f'Resolviendo desafío de seguridad... {n:,} intentos'
                                f' ({rate:,.0f}/s)')
            if now - started > 300:
                return None

    @staticmethod
    def translate_text(text, target_lang='es', source_lang='auto'):
        if not text or not text.strip():
            return text
        try:
            url = 'https://translate.googleapis.com/translate_a/single'
            params = urllib.parse.urlencode({
                'client': 'gtx',
                'sl': source_lang,
                'tl': target_lang,
                'dt': 't',
                'q': text,
            })
            req = urllib.request.Request(
                f"{url}?{params}",
                headers={'User-Agent': 'Mozilla/5.0'}
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode())
            if data and data[0]:
                return ''.join(part[0] for part in data[0] if part[0])
            return text
        except Exception as e:
            print(f"Translation error: {e}")
            return text

    def translate_lyrics(self, lyrics_data, target_lang='es'):
        if not lyrics_data or not lyrics_data.get('lines'):
            return lyrics_data
        source_lang = detect_language(
            lyrics_data.get('lyrics', ''),
            lyrics_data.get('title_hint', ''),
            lyrics_data.get('artist_hint', '')
        )
        if source_lang == target_lang:
            return lyrics_data

        translated_lines = []
        batch = []
        indices = []
        for i, line in enumerate(lyrics_data['lines']):
            text = line.get('text', '').strip()
            if text:
                batch.append(text)
                indices.append(i)
            else:
                translated_lines.append({'time': line.get('time', 0), 'text': ''})

        BATCH_SIZE = 40
        translated_texts = [''] * len(batch)
        for start in range(0, len(batch), BATCH_SIZE):
            end = min(start + BATCH_SIZE, len(batch))
            chunk = '\n'.join(batch[start:end])
            translated_chunk = self.translate_text(chunk, target_lang, source_lang)
            chunk_lines = translated_chunk.split('\n')
            for j, t_line in enumerate(chunk_lines):
                if start + j < len(translated_texts):
                    translated_texts[start + j] = t_line.strip()

        result_map = {}
        for idx, t_text in zip(indices, translated_texts):
            result_map[idx] = t_text

        new_lines = []
        for i, line in enumerate(lyrics_data['lines']):
            text = result_map.get(i, line.get('text', ''))
            new_lines.append({'time': line.get('time', 0), 'text': text})

        new_lyrics_text = '\n'.join(l['text'] for l in new_lines if l['text'])
        return {
            'type': lyrics_data.get('type', 'plain'),
            'lyrics': new_lyrics_text,
            'source': f"{lyrics_data.get('source', 'Zonor')} → {target_lang.upper()}",
            'lines': new_lines,
            'lang': target_lang,
            'translated_from': source_lang,
        }
