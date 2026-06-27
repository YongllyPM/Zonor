import subprocess
import os
import json
import re
import shutil
import threading
from pathlib import Path
from . import db
from . import lyrics as lyrics_mod


class DownloadServer:
    def __init__(self, download_dir):
        self.download_dir = download_dir
        self.port = None
        self._server = None
        self._thread = None

    def start(self):
        import http.server
        import socketserver

        download_dir = str(self.download_dir)

        class _Handler(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=download_dir, **kwargs)

            def log_message(self, format, *args):
                pass

            def end_headers(self):
                self.send_header('Access-Control-Allow-Origin', '*')
                super().end_headers()

        try:
            self._server = socketserver.TCPServer(("127.0.0.1", 0), _Handler)
            self.port = self._server.server_address[1]
            self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
            self._thread.start()
        except Exception as e:
            print(f"[Zonor] Download server error: {e}")

    def stop(self):
        if self._server:
            self._server.shutdown()

    def url_for(self, file_path):
        filename = os.path.basename(file_path)
        return f"http://127.0.0.1:{self.port}/{filename}"


class Downloader:
    def __init__(self, on_progress=None, on_error=None, ytmusic_handler=None):
        self.on_progress = on_progress
        self.on_error = on_error
        self.ytmusic_handler = ytmusic_handler
        self.download_dir = Path(os.environ.get('APPDATA', '')) / 'Zonor' / 'downloads'
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self._server = DownloadServer(self.download_dir)
        self._server.start()
        self._running = {}
        self._log_file = Path(os.environ.get('APPDATA', '')) / 'Zonor' / 'download.log'
        self._log_file.parent.mkdir(parents=True, exist_ok=True)
        self.ytdlp_bin = None
        self.ffmpeg_bin = None
        self._use_library = False
        self._find_tools()

    def _log(self, msg):
        try:
            with open(self._log_file, 'a', encoding='utf-8') as f:
                f.write(f"{msg}\n")
        except Exception:
            pass

    def _find_tools(self):
        root = Path(__file__).parent.parent
        ytdlp_candidates = [
            os.environ.get('YTDLP_PATH', ''),
            str(root / 'bin' / 'yt-dlp.exe'),
            'yt-dlp.exe',
            'yt-dlp',
        ]
        for c in ytdlp_candidates:
            if not c:
                continue
            try:
                subprocess.run([c, '--version'], capture_output=True, timeout=8,
                               creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                self.ytdlp_bin = c
                break
            except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
                continue

        if not self.ytdlp_bin:
            try:
                import yt_dlp  # noqa: F401
                self._use_library = True
                self.ytdlp_bin = 'library'
            except ImportError:
                pass

        ffmpeg_candidates = [
            os.environ.get('FFMPEG_PATH', ''),
            str(root / 'bin' / 'ffmpeg.exe'),
            'ffmpeg.exe',
            'ffmpeg',
        ]
        for c in ffmpeg_candidates:
            if not c:
                continue
            if shutil.which(c) or Path(c).is_file():
                try:
                    subprocess.run([c, '-version'], capture_output=True, timeout=5,
                                   creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                    self.ffmpeg_bin = c
                    break
                except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
                    continue

    @property
    def available(self):
        return self.ytdlp_bin is not None

    def _safe_filename(self, song):
        artist = song.get('artist') or 'Unknown'
        title = song.get('title') or song.get('id', 'track')
        name = re.sub(r'[<>:"/\\|?*]', '_', f"{artist} - {title}")
        return name[:180] or 'track'

    def _resolve_output_path(self, base_path):
        base = Path(base_path)
        if base.suffix:
            base = base.with_suffix('')
        for ext in ('.mp3', '.m4a', '.opus', '.ogg', '.webm', '.aac', '.flac', '.wav'):
            candidate = base.with_suffix(ext)
            if candidate.exists():
                return str(candidate)
        if base.exists():
            return str(base)
        matches = sorted(self.download_dir.glob(f"{base.name}.*"))
        if matches:
            return str(matches[-1])
        return None

    def _fail(self, song_id, message):
        self._log(f"FAIL {song_id}: {message}")
        db.update_download(song_id, 'failed', 0)
        if self.on_error:
            self.on_error(song_id, message)
        return {'error': message}

    def _fetch_lyrics_for(self, song):
        try:
            fetcher = lyrics_mod.LyricsFetcher(ytmusic_handler=self.ytmusic_handler)
            vid = song.get('youtube_id') or song.get('id', '')
            duration = song.get('duration', 0) or song.get('duration_seconds', 0)
            lyrics = fetcher.get_synced_lyrics(
                song.get('artist', ''), song.get('title', ''),
                duration, song_id=vid, download_dir=self.download_dir
            )
            if lyrics:
                fetcher.save_lrc(song.get('artist', ''), song.get('title', ''), lyrics, self.download_dir)
        except Exception as e:
            self._log(f"Lyrics fetch error: {e}")

    def download_song(self, song, video_id=None):
        if not self.available:
            return {'error': 'yt-dlp no encontrado. Ejecuta setup.bat'}

        vid = video_id or song.get('youtube_id') or song.get('id', '')
        if not vid:
            return {'error': 'Sin ID de video'}

        song_id = song['id']
        self._running[song_id] = True
        db.add_download(song_id)
        db.update_download(song_id, 'downloading', 0)

        safe_title = self._safe_filename(song)
        output_template = str(self.download_dir / f"{safe_title}.%(ext)s")
        url = f"https://www.youtube.com/watch?v={vid}"

        def progress_hook(d):
            if not self._running.get(song_id, False):
                raise Exception('Cancelada')
            status = d.get('status')
            if status == 'downloading':
                total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
                downloaded = d.get('downloaded_bytes') or 0
                pct = int(downloaded / total * 100) if total else 0
                db.update_download(song_id, 'downloading', pct)
                if self.on_progress:
                    self.on_progress(song_id, pct)
            elif status == 'finished':
                db.update_download(song_id, 'processing', 95)
                if self.on_progress:
                    self.on_progress(song_id, 95)

        try:
            if self._use_library or self.ytdlp_bin == 'library':
                return self._download_with_library(url, song, song_id, output_template, safe_title, progress_hook)

            return self._download_with_subprocess(url, song, song_id, output_template, safe_title, progress_hook)
        except Exception as e:
            if not self._running.get(song_id, False):
                db.update_download(song_id, 'cancelled', 0)
                return {'error': 'Cancelada'}
            return self._fail(song_id, str(e))
        finally:
            self._running.pop(song_id, None)

    def _get_audio_format_opts(self):
        from . import db
        fmt = db.get_setting('audio_format', 'mp3')
        quality = db.get_setting('audio_quality', 'best')
        quality_map = {'best': '320', 'high': '192', 'medium': '128', 'low': '64'}
        q = quality_map.get(quality, '192')
        return fmt, q

    def _build_ydl_opts(self, output_template, progress_hook):
        fmt, q = self._get_audio_format_opts()
        opts = {
            'format': 'bestaudio[ext=m4a]/bestaudio/best',
            'outtmpl': output_template,
            'noplaylist': True,
            'quiet': True,
            'no_warnings': True,
            'progress_hooks': [progress_hook],
            'encoding': 'utf-8',
        }
        if self.ffmpeg_bin:
            opts['ffmpeg_location'] = str(Path(self.ffmpeg_bin).parent) if Path(self.ffmpeg_bin).is_file() else self.ffmpeg_bin
            opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': fmt,
                'preferredquality': q,
            }]
            opts['writethumbnail'] = True
            opts['embedthumbnail'] = True
            opts['addmetadata'] = True
        return opts

    def _download_with_library(self, url, song, song_id, output_template, safe_title, progress_hook):
        import yt_dlp
        opts = self._build_ydl_opts(output_template, progress_hook)
        final_path = None
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if info:
                prepared = ydl.prepare_filename(info)
                final_path = self._resolve_output_path(prepared)
        if not final_path:
            final_path = self._resolve_output_path(self.download_dir / safe_title)
        if final_path and self._running.get(song_id, False):
            db.update_download(song_id, 'completed', 100, final_path)
            if self.on_progress:
                self.on_progress(song_id, 100)
            self._log(f"OK {song_id}: {final_path}")
            self._fetch_lyrics_for(song)
            return {'success': True, 'path': final_path}
        return self._fail(song_id, 'No se generó el archivo de audio')

    def _download_with_subprocess(self, url, song, song_id, output_template, safe_title, progress_hook):
        cmd = [
            self.ytdlp_bin, url,
            '-f', 'bestaudio[ext=m4a]/bestaudio/best',
            '-o', output_template,
            '--no-playlist',
            '--newline',
            '--print', 'after_move:filepath',
        ]
        if self.ffmpeg_bin:
            ffmpeg_dir = str(Path(self.ffmpeg_bin).parent) if Path(self.ffmpeg_bin).is_file() else ''
            if ffmpeg_dir:
                cmd.extend(['--ffmpeg-location', ffmpeg_dir])
            fmt, q = self._get_audio_format_opts()
            cmd.extend(['-x', '--audio-format', fmt, '--audio-quality', f'{q}K',
                        '--embed-thumbnail', '--add-metadata'])

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8',
            errors='replace',
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0,
        )

        stdout, stderr = proc.communicate()
        final_path = None
        stderr_lines = []

        for line in (stdout or '').splitlines():
            line = line.strip()
            if not line:
                continue
            if line.startswith('{') and 'path' in line:
                try:
                    data = json.loads(line)
                    if data.get('path'):
                        final_path = data['path']
                except json.JSONDecodeError:
                    pass
            elif any(line.lower().endswith(ext) for ext in ('.mp3', '.m4a', '.opus', '.webm', '.ogg', '.aac')):
                if Path(line).exists():
                    final_path = line
            elif '[download]' in line and '%' in line:
                try:
                    pct = int(line.split('%')[0].split()[-1])
                    db.update_download(song_id, 'downloading', pct)
                    if self.on_progress:
                        self.on_progress(song_id, pct)
                except (ValueError, IndexError):
                    pass

        if stderr:
            stderr_lines = stderr.splitlines()

        if not final_path:
            final_path = self._resolve_output_path(self.download_dir / safe_title)

        if proc.returncode == 0 and final_path and self._running.get(song_id, False):
            db.update_download(song_id, 'completed', 100, final_path)
            if self.on_progress:
                self.on_progress(song_id, 100)
            self._log(f"OK {song_id}: {final_path}")
            self._fetch_lyrics_for(song)
            return {'success': True, 'path': final_path}

        err = '\n'.join(stderr_lines[-6:]) if stderr_lines else 'Error desconocido de yt-dlp'
        if 'ffmpeg' in err.lower() and not self.ffmpeg_bin:
            err = 'Falta ffmpeg para convertir a MP3. Se descargará audio nativo (m4a). Reintenta.'
        return self._fail(song_id, err[:300])

    def cancel_download(self, song_id):
        self._running[song_id] = False
        db.update_download(song_id, 'cancelled', 0)

    def get_download_path(self, song_id):
        song = db.get_song(song_id)
        if song and song.get('downloaded') and song.get('file_path'):
            p = Path(song['file_path'])
            if p.exists():
                return str(p)
        return None

    def delete_download(self, song_id):
        song = db.get_song(song_id)
        if song and song.get('file_path'):
            try:
                Path(song['file_path']).unlink(missing_ok=True)
            except OSError:
                pass
        db.update_download(song_id, 'deleted', 0)
        conn = db.get_conn()
        conn.execute("DELETE FROM download_queue WHERE song_id = ?", (song_id,))
        conn.execute("UPDATE songs SET downloaded = 0, file_path = '' WHERE id = ?", (song_id,))
        conn.commit()
        conn.close()

    def get_download_dir(self):
        return str(self.download_dir)
