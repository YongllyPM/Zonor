import re
import json
import os
import urllib.request
import urllib.parse
import time
from pathlib import Path


class LyricsFetcher:
    def __init__(self, ytmusic_handler=None):
        self.cache = {}
        self.ytmusic = ytmusic_handler

    def get_synced_lyrics(self, artist, title, duration=0, song_id=None, download_dir=None):
        cache_key = f"{artist}|{title}".lower()
        if cache_key in self.cache:
            return self.cache[cache_key]

        # 1. Try .lrc file alongside downloaded audio
        if download_dir:
            lyrics = self._from_lrc_file(artist, title, download_dir)
            if lyrics:
                self.cache[cache_key] = lyrics
                return lyrics

        # 2. Try syncedlyrics library (multi-provider)
        lyrics = self._from_syncedlyrics(artist, title, duration)
        if lyrics:
            self.cache[cache_key] = lyrics
            return lyrics

        # 3. Try YouTube Music API (if authenticated)
        if song_id and self.ytmusic and self.ytmusic.is_authenticated():
            lyrics = self._from_ytmusic(song_id, duration)
            if lyrics:
                self.cache[cache_key] = lyrics
                return lyrics

        # 4. Try YouTube via yt-dlp
        if song_id:
            lyrics = self._from_youtube(song_id, duration)
            if lyrics:
                self.cache[cache_key] = lyrics
                return lyrics

        # 5. Try LRCLib directly
        lyrics = self._from_lrclib(artist, title, duration)
        if lyrics:
            self.cache[cache_key] = lyrics
            return lyrics

        # 6. Try Spotify API
        lyrics = self._from_spotify(artist, title)
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

    def _from_syncedlyrics(self, artist, title, duration):
        try:
            import syncedlyrics
            query = f"{artist} - {title}"
            lrc_text = syncedlyrics.search(query, synced_only=True)
            if lrc_text:
                lines = self._parse_lrc(lrc_text)
                if lines:
                    return {
                        'type': 'synced',
                        'lyrics': lrc_text,
                        'source': 'SyncedLyrics',
                        'lines': lines
                    }
            lrc_text = syncedlyrics.search(query, synced_only=False)
            if lrc_text:
                lines = self._parse_lrc(lrc_text)
                if lines:
                    return {
                        'type': 'synced',
                        'lyrics': lrc_text,
                        'source': 'SyncedLyrics',
                        'lines': lines
                    }
                plain = [l for l in lrc_text.split('\n') if l.strip() and not l.startswith('[')]
                if plain:
                    lines = self._sync_plain(plain, duration)
                    return {
                        'type': 'synced' if any(l['time'] > 0 for l in lines) else 'plain',
                        'lyrics': '\n'.join(plain),
                        'source': 'SyncedLyrics',
                        'lines': lines
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
                    'lines': self._parse_lrc(data['syncedLyrics'])
                }
            elif data.get('plainLyrics'):
                plain = [l for l in data['plainLyrics'].split('\n') if l.strip()]
                lines = self._sync_plain(plain, duration)
                return {
                    'type': 'synced' if any(l['time'] > 0 for l in lines) else 'plain',
                    'lyrics': data['plainLyrics'],
                    'source': 'LRCLib',
                    'lines': lines
                }
        except Exception as e:
            print(f"LRCLib error: {e}")
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
        pattern = re.compile(r'\[(\d{2}):(\d{2})\.(\d{2,3})\]\s*(.*)')
        for line in lrc_text.split('\n'):
            m = pattern.match(line)
            if m:
                mins = int(m.group(1))
                secs = int(m.group(2))
                millis = int(m.group(3))
                if millis > 999:
                    millis = millis // 10
                time_secs = mins * 60 + secs + millis / 1000
                lines.append({'time': time_secs, 'text': m.group(4).strip()})
        return sorted(lines, key=lambda x: x['time'])

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
