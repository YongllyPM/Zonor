import os
import json
import re
import sys
import tempfile
import threading
import subprocess
import urllib.request
import zipfile
import shutil
from pathlib import Path


class Transcriber:
    BIN_DIR = Path(__file__).parent.parent / 'bin'

    def __init__(self, downloader=None, ytmusic_handler=None):
        self.downloader = downloader
        self.ytmusic_handler = ytmusic_handler
        self._running = False
        self._progress = 0
        self._status = ''
        self._model_size = 'base'
        self._on_progress = None
        self._on_error = None
        self._on_done = None

    def set_callbacks(self, on_progress=None, on_error=None, on_done=None):
        self._on_progress = on_progress
        self._on_error = on_error
        self._on_done = on_done

    def _find_ffmpeg(self):
        for name in ['ffmpeg.exe', 'ffmpeg']:
            local = self.BIN_DIR / name
            if local.exists():
                return str(local)
        try:
            subprocess.run(
                ['ffmpeg', '-version'],
                capture_output=True, timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            return 'ffmpeg'
        except Exception:
            return None

    def is_available(self):
        try:
            import whisper
        except ImportError:
            return {'available': False, 'error': 'whisper'}
        if not self._find_ffmpeg():
            return {'available': False, 'error': 'ffmpeg'}
        return {'available': True}

    def get_status(self):
        return {'running': self._running, 'progress': self._progress, 'status': self._status}

    def install(self):
        self._running = True
        self._progress = 0
        self._on_progress(0, 'Verificando dependencias...')

        ffmpeg_ok = self._find_ffmpeg() is not None
        whisper_ok = False
        try:
            import whisper
            whisper_ok = True
        except ImportError:
            pass

        if ffmpeg_ok and whisper_ok:
            self._on_progress(100, 'Todo instalado')
            self._running = False
            return {'success': True, 'message': 'Todo ya estaba instalado'}

        steps = (0 if whisper_ok else 1) + (0 if ffmpeg_ok else 1)
        current = 0

        if not whisper_ok:
            self._on_progress(int(current / steps * 100), 'Instalando openai-whisper...')
            ok, err = self._install_whisper()
            if not ok:
                self._running = False
                self._on_error(0, f'Error instalando whisper: {err}')
                return {'success': False, 'error': f'whisper: {err}'}
            current += 1

        if not ffmpeg_ok:
            self._on_progress(int(current / steps * 100), 'Descargando ffmpeg...')
            ok, err = self._install_ffmpeg()
            if not ok:
                self._running = False
                self._on_error(0, f'Error descargando ffmpeg: {err}')
                return {'success': False, 'error': f'ffmpeg: {err}'}
            current += 1

        self._on_progress(100, 'Instalación completada')
        self._running = False
        return {'success': True, 'message': 'Dependencias instaladas correctamente'}

    def _install_whisper(self):
        try:
            self._on_progress(10, 'Instalando openai-whisper (puede tardar)...')
            proc = subprocess.run(
                [sys.executable, '-m', 'pip', 'install', 'openai-whisper'],
                capture_output=True, text=True, timeout=600,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            if proc.returncode != 0:
                return False, proc.stderr[-500:] if proc.stderr else 'Error desconocido'
            return True, None
        except subprocess.TimeoutExpired:
            return False, 'La instalación tardó demasiado (>10 min)'
        except Exception as e:
            return False, str(e)

    def _install_ffmpeg(self):
        try:
            self.BIN_DIR.mkdir(parents=True, exist_ok=True)

            if os.name == 'nt':
                url = 'https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip'
                zip_name = 'ffmpeg.zip'
            else:
                url = 'https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linux64-gpl.tar.xz'
                zip_name = 'ffmpeg.tar.xz'

            zip_path = self.BIN_DIR / zip_name
            self._on_progress(20, 'Descargando ffmpeg desde GitHub...')

            req = urllib.request.Request(url, headers={'User-Agent': 'Zonor/1.0'})
            with urllib.request.urlopen(req, timeout=120) as resp:
                total = int(resp.headers.get('Content-Length', 0))
                downloaded = 0
                chunk_size = 256 * 1024
                with open(zip_path, 'wb') as f:
                    while True:
                        chunk = resp.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total > 0:
                            pct = 20 + int(downloaded / total * 40)
                            self._on_progress(min(pct, 60), f'Descargando ffmpeg... {downloaded // (1024*1024)}MB/{total // (1024*1024)}MB')

            self._on_progress(60, 'Extrayendo ffmpeg...')
            if zip_name.endswith('.zip'):
                with zipfile.ZipFile(zip_path, 'r') as zf:
                    for member in zf.namelist():
                        if member.endswith('ffmpeg.exe') or (member.endswith('ffmpeg') and '/bin/' in member):
                            data = zf.read(member)
                            out = self.BIN_DIR / 'ffmpeg.exe'
                            out.write_bytes(data)
                            out.chmod(0o755)
                            break
                    else:
                        for member in zf.namelist():
                            if 'ffmpeg' in member.split('/')[-1].lower() and not member.endswith('/'):
                                data = zf.read(member)
                                out = self.BIN_DIR / ('ffmpeg.exe' if os.name == 'nt' else 'ffmpeg')
                                out.write_bytes(data)
                                out.chmod(0o755)
                                break
            else:
                import tarfile
                with tarfile.open(zip_path, 'r:xz') as tf:
                    for member in tf.getmembers():
                        if member.name.endswith('ffmpeg') and '/bin/' in member.name:
                            tf.extract(member, self.BIN_DIR)
                            extracted = self.BIN_DIR / member.name
                            final = self.BIN_DIR / 'ffmpeg'
                            if extracted != final:
                                extracted.rename(final)
                            final.chmod(0o755)
                            break

            try:
                zip_path.unlink()
            except Exception:
                pass

            ffmpeg = self._find_ffmpeg()
            if not ffmpeg:
                return False, 'ffmpeg se descargó pero no se encontró el ejecutable'

            self._on_progress(100, 'ffmpeg instalado correctamente')
            return True, None

        except Exception as e:
            return False, str(e)

    def _setup_whisper_path(self):
        ffmpeg = self._find_ffmpeg()
        if ffmpeg and ffmpeg != 'ffmpeg':
            ffmpeg_dir = str(Path(ffmpeg).parent)
            if ffmpeg_dir not in os.environ.get('PATH', ''):
                os.environ['PATH'] = ffmpeg_dir + os.pathsep + os.environ.get('PATH', '')

    def transcribe(self, song_id, audio_path=None):
        self._running = True
        self._progress = 0
        self._status = 'Iniciando...'

        try:
            import whisper
        except ImportError:
            self._fail(song_id, 'Whisper no instalado')
            return None

        self._setup_whisper_path()

        audio_file = audio_path
        temp_dir = None

        try:
            if not audio_file or not Path(audio_file).exists():
                self._update_status('Descargando audio temporal...')
                if self.downloader and self.ytmusic_handler:
                    temp_dir = tempfile.mkdtemp()
                    audio_file = self._download_temp_audio(song_id, temp_dir)
                    if not audio_file:
                        self._fail(song_id, 'No se pudo obtener el audio')
                        return None
                else:
                    self._fail(song_id, 'No hay fuente de audio disponible')
                    return None

            self._update_status(f'Cargando modelo Whisper ({self._model_size})...')
            self._progress = 10
            model = whisper.load_model(self._model_size)

            self._update_status('Transcribiendo audio...')
            self._progress = 30

            result = model.transcribe(
                audio_file,
                language='es',
                task='transcribe',
                verbose=False,
            )

            self._progress = 80
            self._update_status('Procesando resultados...')

            segments = result.get('segments', [])
            if not segments:
                self._fail(song_id, 'Whisper no detectó voz en el audio')
                return None

            lines = []
            for seg in segments:
                text = seg.get('text', '').strip()
                if not text:
                    continue
                start = seg.get('start', 0)
                lines.append({'time': start, 'text': text})

            if not lines:
                self._fail(song_id, 'No se generaron líneas de letra')
                return None

            lrc_lines = []
            for l in lines:
                mins = int(l['time'] // 60)
                secs = int(l['time'] % 60)
                millis = int((l['time'] % 1) * 100)
                lrc_lines.append(f"[{mins:02d}:{secs:02d}.{millis:02d}]{l['text']}")
            lrc_text = '\n'.join(lrc_lines)

            result_data = {
                'type': 'synced',
                'lyrics': lrc_text,
                'source': 'Whisper AI',
                'lines': lines,
            }

            self._progress = 100
            self._status = 'Completado'
            self._running = False

            if self._on_done:
                self._on_done(song_id, result_data)

            return result_data

        except Exception as e:
            self._fail(song_id, str(e))
            return None

        finally:
            self._running = False
            if temp_dir and Path(temp_dir).exists():
                shutil.rmtree(temp_dir, ignore_errors=True)

    def _download_temp_audio(self, song_id, temp_dir):
        try:
            vid = None
            if self.ytmusic_handler:
                song = None
                if hasattr(self.ytmusic_handler, 'yt') and self.ytmusic_handler.yt:
                    try:
                        from . import db
                        song = db.get_song(song_id)
                    except Exception:
                        pass
                if not song:
                    return None
                vid = song.get('youtube_id', song.get('id', ''))

            if not vid:
                return None

            url = f"https://www.youtube.com/watch?v={vid}"
            out_path = str(Path(temp_dir) / 'audio')

            import yt_dlp
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': f'{out_path}.%(ext)s',
                'quiet': True,
                'no_warnings': True,
                'noplaylist': True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                ext = info.get('ext', 'm4a')
                audio_file = f"{out_path}.{ext}"
                if Path(audio_file).exists():
                    return audio_file

            for f in Path(temp_dir).iterdir():
                if f.is_file() and f.stat().st_size > 0:
                    return str(f)
            return None

        except Exception as e:
            print(f"Temp audio download error: {e}")
            return None

    def _update_status(self, msg):
        self._status = msg
        if self._on_progress:
            self._on_progress(self._progress, msg)

    def _fail(self, song_id, error):
        self._running = False
        self._status = f'Error: {error}'
        if self._on_error:
            self._on_error(song_id, error)
        print(f"Transcriber error for {song_id}: {error}")
