import subprocess
import os
import threading
import json
import time
from pathlib import Path


class MusicPlayer:
    def __init__(self, on_status_change=None):
        self.on_status_change = on_status_change
        self.current_song = None
        self.state = 'stopped'
        self.volume = 80
        self.position = 0
        self.duration = 0
        self._playback_thread = None
        self._stream_cache = {}
        self._stream_cache_ttl = 3 * 3600
        self._find_ytdlp()

    def _find_ytdlp(self):
        candidates = [
            str(Path(__file__).parent.parent / 'bin' / 'yt-dlp.exe'),
            'yt-dlp.exe', 'yt-dlp',
        ]
        if os.environ.get('YTDLP_PATH'):
            candidates.insert(0, os.environ['YTDLP_PATH'])
        self.ytdlp_bin = None
        for c in candidates:
            try:
                subprocess.run([c, '--version'], capture_output=True, timeout=5,
                               creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                self.ytdlp_bin = c
                break
            except:
                continue
        if not self.ytdlp_bin:
            try:
                import yt_dlp
                self.ytdlp_bin = 'library'
            except:
                pass

    @property
    def available(self):
        return self.ytdlp_bin is not None

    def get_stream_url(self, video_id, use_cache=True):
        if not video_id:
            return None
        if use_cache and video_id in self._stream_cache:
            cached_url, expires = self._stream_cache[video_id]
            if time.time() < expires:
                return cached_url
        try:
            url = f"https://www.youtube.com/watch?v={video_id}"
            if self.ytdlp_bin == 'library':
                import yt_dlp
                ydl_opts = {'format': 'bestaudio', 'quiet': True}
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                    stream = None
                    for fmt in info.get('formats', []):
                        if fmt.get('acodec') and fmt.get('acodec') != 'none':
                            stream = fmt.get('url')
                            break
                    if not stream:
                        stream = info.get('url')
                    if stream:
                        self._stream_cache[video_id] = (stream, time.time() + self._stream_cache_ttl)
                    return stream
            else:
                result = subprocess.run(
                    [self.ytdlp_bin, '-g', '--format', 'bestaudio', url],
                    capture_output=True, text=True, timeout=30,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                )
                if result.returncode == 0:
                    stream = result.stdout.strip().split('\n')[0]
                    if stream:
                        self._stream_cache[video_id] = (stream, time.time() + self._stream_cache_ttl)
                    return stream
        except Exception as e:
            print(f"Stream URL error: {e}")
        return None

    def invalidate_stream_cache(self, video_id=None):
        if video_id:
            self._stream_cache.pop(video_id, None)
        else:
            self._stream_cache.clear()

    def toggle_play(self):
        if self.state == 'playing':
            self.state = 'paused'
        elif self.state == 'paused':
            self.state = 'playing'
        if self.on_status_change:
            self.on_status_change(self._get_status())

    def seek(self, position):
        self.position = max(0, position)
        if self.on_status_change:
            self.on_status_change(self._get_status())

    def get_downloaded_path(self, song_id):
        from . import db
        song = db.get_song(song_id)
        if song and song.get('downloaded') and song.get('file_path'):
            p = Path(song['file_path'])
            if p.exists():
                return str(p)
        return None

    def on_playback_started(self, song_id, queue=None):
        pass

    def on_playback_ended(self):
        if self.on_status_change:
            self.state = 'stopped'
            self.position = 0
            self.on_status_change(self._get_status())

    def on_position_update(self, position, duration):
        self.position = position
        self.duration = duration
        if self.on_status_change:
            self.on_status_change(self._get_status())

    def on_state_change(self, state, song=None):
        self.state = state
        if song:
            self.current_song = song
        if self.on_status_change:
            self.on_status_change(self._get_status())

    def _get_status(self):
        return {
            'state': self.state,
            'position': self.position,
            'duration': self.duration,
            'volume': self.volume,
            'current_song': self.current_song
        }

    def get_status(self):
        return self._get_status()

    def set_volume(self, vol):
        self.volume = max(0, min(100, vol))
