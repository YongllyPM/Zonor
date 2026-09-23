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
        self.stream_resolver = None

    def set_stream_resolver(self, resolver):
        self.stream_resolver = resolver

    def _log_process(self, msg):
        try:
            log_file = Path(os.environ.get('APPDATA', '')) / 'Zonor' / 'download.log'
            log_file.parent.mkdir(parents=True, exist_ok=True)
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(f"{msg}\n")
        except Exception:
            pass

    def start(self):
        import http.server
        import socketserver
        import urllib.request

        download_dir = str(self.download_dir)

        class _Handler(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=download_dir, **kwargs)

            def log_message(self, format, *args):
                pass

            def end_headers(self):
                self.send_header('Access-Control-Allow-Origin', '*')
                super().end_headers()

            def _proxy_stream(self, suffix):
                import urllib.error
                handler = self.server
                server = getattr(handler, 'download_server', None)
                if not server or not server.stream_resolver:
                    self.send_error(404)
                    return
                video_id = suffix.strip()
                if not video_id:
                    self.send_error(400)
                    return
                server._log_process(f"[stream] GET /stream/{video_id} range={self.headers.get('Range')}")
                try:
                    remote = server.stream_resolver(video_id)
                except Exception as e:
                    server._log_process(f"[stream] resolve FAILED {video_id}: {e}")
                    self.send_error(502, message='stream resolve failed')
                    return
                if not remote:
                    server._log_process(f"[stream] resolve EMPTY {video_id}")
                    self.send_error(404)
                    return
                headers = {
                    'User-Agent': 'Mozilla/5.0',
                    'Accept': 'audio/webm,audio/ogg,audio/mp4,*/*;q=0.8',
                }
                rng = self.headers.get('Range')
                if not rng:
                    rng = 'bytes=0-'
                rng = self._clamp_range(rng)
                if rng:
                    headers['Range'] = rng
                req = urllib.request.Request(remote, headers=headers, method='GET')
                try:
                    upstream = urllib.request.urlopen(req, timeout=30)
                    server._log_process(f"[stream] upstream {upstream.status} {upstream.headers.get('Content-Type')} {upstream.headers.get('Content-Range')}")
                except urllib.error.HTTPError as e:
                    if e.code == 403 and self.headers.get('Range') and self.headers.get('Range').rstrip().endswith('-'):
                        fallback = 'bytes=0-1048575'
                        headers2 = dict(headers)
                        headers2['Range'] = fallback
                        try:
                            req2 = urllib.request.Request(remote, headers=headers2, method='GET')
                            upstream = urllib.request.urlopen(req2, timeout=30)
                            server._log_process(f"[stream] upstream 403-retry {upstream.status} {upstream.headers.get('Content-Type')} {upstream.headers.get('Content-Range')}")
                        except Exception as e2:
                            server._log_process(f"[stream] upstream 403-retry FAIL: {e2}")
                            self.send_error(502)
                            return
                    else:
                        server._log_process(f"[stream] upstream http {e.code} for {video_id}")
                        self.send_error(502 if e.code == 502 else e.code if e.code in (403, 404) else 502)
                        return
                except Exception as e:
                    server._log_process(f"[stream] upstream err {e} for {video_id}")
                    self.send_error(502)
                    return
                try:
                    self.send_response(upstream.status)
                    ctype = upstream.headers.get('Content-Type') or 'application/octet-stream'
                    self.send_header('Content-Type', ctype)
                    if upstream.headers.get('Content-Length'):
                        self.send_header('Content-Length', upstream.headers['Content-Length'])
                    if upstream.headers.get('Content-Range'):
                        self.send_header('Content-Range', upstream.headers['Content-Range'])
                    if upstream.headers.get('Accept-Ranges'):
                        self.send_header('Accept-Ranges', upstream.headers['Accept-Ranges'])
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    while True:
                        chunk = upstream.read(65536)
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                except Exception:
                    pass
                finally:
                    upstream.close()

            def _clamp_range(self, rng):
                if not rng:
                    return None
                rng = rng.strip()
                m = re.match(r'^bytes=(\d*)-(\d*)$', rng)
                if not m:
                    return None
                start, end = m.group(1), m.group(2)
                if start == '' and end == '':
                    return 'bytes=0-1048575'
                if end == '':
                    return f'bytes={start}-{int(start) + 1048575}'
                return f'bytes={start or 0}-{end}'

            def do_GET(self):
                path = self.path.split('?', 1)[0]
                if path.startswith('/stream/'):
                    self._proxy_stream(path[len('/stream/'):])
                    return
                return super().do_GET()

            def do_HEAD(self):
                path = self.path.split('?', 1)[0]
                if path.startswith('/stream/'):
                    self._proxy_stream(path[len('/stream/'):])
                    return
                return super().do_HEAD()

        try:
            self._server = socketserver.TCPServer(("127.0.0.1", 0), _Handler)
            self._server.download_server = self
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

    def url_for_stream(self, video_id):
        if not self.port:
            return None
        return f"http://127.0.0.1:{self.port}/stream/{video_id}"


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

    def _save_thumbnail(self, song, song_id):
        try:
            thumb_url = song.get('thumbnail', '')
            if not thumb_url:
                return
            thumb_filename = f"{song_id}.jpg"
            thumb_path = self.download_dir / thumb_filename
            import urllib.request
            req = urllib.request.Request(thumb_url, headers={
                'User-Agent': 'Mozilla/5.0',
            })
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = resp.read()
            thumb_path.write_bytes(data)
            local_url = self._server.url_for(str(thumb_path))
            conn = db.get_conn()
            conn.execute("UPDATE songs SET thumbnail = ? WHERE id = ?", (local_url, song_id))
            conn.commit()
            conn.close()
        except Exception as e:
            self._log(f"Thumbnail save error: {e}")

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
            platform = song.get('platform', 'youtube')
            if self._use_library or self.ytdlp_bin == 'library':
                return self._download_with_library(url, song, song_id, output_template, safe_title, progress_hook, platform)

            return self._download_with_subprocess(url, song, song_id, output_template, safe_title, progress_hook, platform)
        except Exception as e:
            if not self._running.get(song_id, False):
                db.update_download(song_id, 'cancelled', 0)
                return {'error': 'Cancelada'}
            return self._fail(song_id, str(e))
        finally:
            self._running.pop(song_id, None)

    def _get_audio_format_opts(self, platform='youtube'):
        from . import db
        fmt = db.get_setting('audio_format', 'mp3')
        quality = db.get_setting(f'audio_quality_{platform}', '') or db.get_setting('audio_quality', 'best')
        quality_map = {'best': '320', 'high': '192', 'medium': '128', 'low': '64'}
        q = quality_map.get(quality, '192')
        return fmt, q

    def _build_ydl_opts(self, output_template, progress_hook, platform='youtube'):
        fmt, q = self._get_audio_format_opts(platform)
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

    def _download_with_library(self, url, song, song_id, output_template, safe_title, progress_hook, platform='youtube'):
        import yt_dlp
        opts = self._build_ydl_opts(output_template, progress_hook, platform)
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
            self._save_thumbnail(song, song_id)
            return {'success': True, 'path': final_path}
        return self._fail(song_id, 'No se generó el archivo de audio')

    def _download_with_subprocess(self, url, song, song_id, output_template, safe_title, progress_hook, platform='youtube'):
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
            fmt, q = self._get_audio_format_opts(platform)
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
            self._save_thumbnail(song, song_id)
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
        thumb_path = self.download_dir / f"{song_id}.jpg"
        try:
            thumb_path.unlink(missing_ok=True)
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
