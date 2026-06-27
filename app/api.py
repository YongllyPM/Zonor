import json
import base64
import threading
import os
import time
from pathlib import Path
from . import db
from . import player as player_mod
from . import ytmusic_handler as yt_mod
from . import downloader as dl_mod
from . import lyrics as lyrics_mod
from . import sync as sync_mod
from . import themes as themes_mod
import traceback


class API:
    def __init__(self, window=None):
        self.window = window
        self.ytmusic = yt_mod.YTMusicHandler(on_auth_change=self._on_auth_change)
        self.player = player_mod.MusicPlayer(on_status_change=self._on_player_status)
        self.downloader = dl_mod.Downloader(
            on_progress=self._on_download_progress,
            on_error=self._on_download_error,
            ytmusic_handler=self.ytmusic,
        )
        self.lyrics_fetcher = lyrics_mod.LyricsFetcher(ytmusic_handler=self.ytmusic)
        self.sync_service = sync_mod.SyncService(self.ytmusic, on_sync_event=self._on_sync_event)
        self.current_playing_id = None
        self.current_queue = []
        self.queue_index = -1
        self._listeners = {}

        db.init_db()
        threading.Thread(target=self._post_init, daemon=True).start()

    def _post_init(self):
        if self.ytmusic._headers_file.exists():
            self.ytmusic.auto_login()
            if self.ytmusic.is_authenticated():
                try:
                    self.sync_service.force_sync()
                except Exception:
                    pass
        self._refresh_home_feed()

    def _empty_home(self):
        return {
            'recent': [],
            'new_releases': [],
            'listen_again': [],
            'trending': [],
            'top_songs': [],
            'playlists': [],
            'from_cache': False,
        }

    def _merge_recent(self, feed):
        local = db.get_recent_plays(15)
        seen = set()
        merged = []
        for s in local + feed.get('recent', []):
            sid = s.get('id')
            if sid and sid not in seen:
                seen.add(sid)
                merged.append(s)
        feed['recent'] = merged[:15]
        return feed

    def _refresh_home_feed(self):
        try:
            feed = self.ytmusic.get_home_feed()
            for key in ('trending', 'top_songs', 'new_releases', 'listen_again', 'recent'):
                for s in feed.get(key, []):
                    db.save_song(s)
            for pl in feed.get('playlists', []):
                if pl.get('id'):
                    db.save_playlist({
                        'id': f"home_{pl['id']}",
                        'name': pl.get('title') or pl.get('name', 'Playlist'),
                        'description': pl.get('description', ''),
                        'thumbnail': pl.get('thumbnail', ''),
                    })
            feed = self._merge_recent(feed)
            feed['from_cache'] = False
            db.cache_set('home_feed', feed, ttl=1800)
            self._emit('home_updated', feed)
            return feed
        except Exception as e:
            print(f"Home refresh error: {e}")
            return None

    def prefetch_home(self):
        threading.Thread(target=self._refresh_home_feed, daemon=True).start()

    def set_window(self, window):
        self.window = window

    def _emit(self, event, data=None):
        if self.window:
            try:
                js = json.dumps({'event': event, 'data': data})
                self.window.evaluate_js(f"window.__handlePyEvent({js})")
            except:
                pass

    def _on_auth_change(self, authenticated, user_info):
        self._emit('auth_changed', {'authenticated': authenticated, 'user': user_info})

    def _on_player_status(self, status):
        self._emit('player_status', status)
        if status.get('state') == 'playing' and status.get('current_song'):
            sid = status['current_song'].get('id')
            if sid and sid != self.current_playing_id:
                self.current_playing_id = sid
                self._emit('song_changed', status['current_song'])

    def _on_download_progress(self, song_id, progress):
        self._emit('download_progress', {'song_id': song_id, 'progress': progress})

    def _on_download_error(self, song_id, message):
        self._emit('download_error', {'song_id': song_id, 'error': message})

    def _on_sync_event(self, event, data):
        self._emit('sync_event', {'type': event, 'data': data})

    # ===== Auth =====
    def get_auth_status(self):
        return self.ytmusic.get_auth_status()

    def login_with_headers(self, headers_json):
        try:
            if isinstance(headers_json, str):
                headers = json.loads(headers_json)
            else:
                headers = headers_json
            return self.ytmusic.login_with_headers(headers)
        except:
            return False

    def login_from_browser(self):
        result = self.ytmusic.login_from_browser()
        if isinstance(result, dict):
            if result.get('success'):
                return True
            self.ytmusic.auth_error = result.get('error') or result.get('message')
            return result
        return result

    def login_oauth(self):
        result = self.ytmusic.login_oauth()
        if isinstance(result, dict):
            return result.get('success', False)
        return result

    def login_auto(self):
        return self.ytmusic.auto_login()

    def login_with_cookie(self, cookie):
        ok = self.ytmusic.login_with_cookie(cookie)
        return {'success': ok, 'error': self.ytmusic.auth_error}

    def logout(self):
        self.ytmusic.logout()

    def factoryReset(self):
        try:
            dl_dir = db.get_setting('download_folder') or str(Path(os.environ['APPDATA']) / 'Zonor' / 'downloads')
            import shutil
            if Path(dl_dir).exists():
                for f in Path(dl_dir).iterdir():
                    if f.is_file():
                        f.unlink()
            self.logout()
            db.clear_all()
            db.cache_clear()
            self.player.stop()
            self.current_queue = []
            self.queue_index = -1
            self.current_playing_id = None
            return {'success': True}
        except Exception as e:
            traceback.print_exc()
            return {'success': False, 'error': str(e)}

    # ===== Home / Charts =====
    def get_home(self):
        cached = db.cache_get('home_feed')
        if cached:
            result = self._merge_recent({**cached, 'from_cache': True})
        else:
            result = self._merge_recent(self._empty_home())
        threading.Thread(target=self._refresh_home_feed, daemon=True).start()
        return result

    def get_remote_playlist_songs(self, playlist_id):
        if not playlist_id:
            return []
        songs = self.ytmusic.get_playlist(playlist_id)
        for s in songs:
            db.save_song(s)
        return songs

    # ===== Search =====
    def search(self, query, limit=20):
        songs = self.ytmusic.search(query, limit)
        for s in songs:
            db.save_song(s)
        return songs

    def search_suggestions(self, query):
        return self.ytmusic.search_suggestions(query)

    # ===== Library =====
    def get_library(self):
        return self.ytmusic.get_library()

    def get_artists(self):
        return self.ytmusic.get_subscriptions()

    def get_artist_albums(self, channel_id):
        return self.ytmusic.get_artist_albums(channel_id)

    def get_liked_songs(self):

    def is_liked(self, song_id):
        return db.is_liked(song_id)

    def toggle_like(self, song_id):
        song = db.get_song(song_id)
        if not song:
            return {'liked': False, 'error': 'Canción no encontrada'}
        liked = not db.is_liked(song_id)
        db.save_song({**song, 'liked': 1 if liked else 0})
        vid = song.get('youtube_id', song.get('id', ''))
        if self.ytmusic.is_authenticated() and vid:
            try:
                self.ytmusic.rate_song(vid, 'LIKE' if liked else 'DISLIKE')
            except Exception:
                pass
        return {'liked': liked, 'song_id': song_id}

    def refresh_stream_url(self, song_id):
        song = db.get_song(song_id)
        if not song:
            return None
        vid = song.get('youtube_id', song.get('id', ''))
        if vid:
            self.player.invalidate_stream_cache(vid)
        return self.get_stream_url(song_id)

    def get_playlists(self):
        local = [p for p in db.get_playlists() if not p['id'].startswith('home_')]
        if self.ytmusic.is_authenticated():
            remote = self.ytmusic.get_playlists()
            for r in remote:
                found = any(l.get('sync_id') == r['id'] for l in local)
                if not found:
                    pl_id = f"sync_{r['id']}"
                    db.save_playlist({
                        'id': pl_id,
                        'name': r['name'],
                        'description': r.get('description', ''),
                        'thumbnail': r.get('thumbnail', ''),
                        'sync_id': r['id']
                    })
                    local.append({
                        'id': pl_id,
                        'name': r['name'],
                        'description': r.get('description', ''),
                        'thumbnail': r.get('thumbnail', ''),
                        'song_count': r.get('song_count', 0),
                        'sync_id': r['id'],
                    })
        return local

    def get_playlist_songs(self, playlist_id):
        local = db.get_playlist_songs(playlist_id)
        if not local and 'sync_' in playlist_id:
            sync_id = playlist_id.replace('sync_', '')
            if self.ytmusic.is_authenticated():
                songs = self.ytmusic.get_playlist(sync_id)
                for s in songs:
                    db.save_song(s)
                    db.add_song_to_playlist(playlist_id, s['id'])
                return songs
        return local

    def create_playlist(self, name, description=''):
        pl_id = f"local_{int(time.time())}"
        db.save_playlist({'id': pl_id, 'name': name, 'description': description})
        if self.ytmusic.is_authenticated():
            remote_id = self.ytmusic.create_playlist(name, description)
            if remote_id:
                db.save_playlist({'id': pl_id, 'name': name, 'description': description, 'sync_id': remote_id})
        return pl_id

    def delete_playlist(self, playlist_id):
        pl = None
        for p in db.get_playlists():
            if p['id'] == playlist_id:
                pl = p
                break
        if pl and pl.get('sync_id') and self.ytmusic.is_authenticated():
            self.ytmusic.delete_playlist_remote(pl['sync_id'])
        db.delete_playlist(playlist_id)

    def add_to_playlist(self, playlist_id, song_id, video_id=None):
        song = db.get_song(song_id)
        if not song:
            if self.ytmusic.is_authenticated() and video_id:
                song = {'id': song_id, 'title': song_id, 'artist': '', 'youtube_id': video_id}
                db.save_song(song)
        if song:
            db.add_song_to_playlist(playlist_id, song_id)
            pl = None
            for p in db.get_playlists():
                if p['id'] == playlist_id:
                    pl = p
                    break
            if pl and pl.get('sync_id') and video_id and self.ytmusic.is_authenticated():
                self.ytmusic.add_to_playlist(pl['sync_id'], video_id)

    def remove_from_playlist(self, playlist_id, song_id, video_id=None):
        db.remove_song_from_playlist(playlist_id, song_id)
        pl = None
        for p in db.get_playlists():
            if p['id'] == playlist_id:
                pl = p
                break
        if pl and pl.get('sync_id') and video_id and self.ytmusic.is_authenticated():
            self.ytmusic.remove_from_playlist(pl['sync_id'], video_id)

    # ===== Player =====
    def get_stream_url(self, song_id, preload_next=0):
        song = db.get_song(song_id)
        if not song:
            return None
        downloaded_path = self.downloader.get_download_path(song_id)
        if downloaded_path:
            http_url = self.downloader._server.url_for(downloaded_path)
            if http_url:
                return {'type': 'stream', 'url': http_url, 'song': song}
        vid = song.get('youtube_id', song.get('id', ''))
        if vid:
            url = self.player.get_stream_url(vid)
            if url:
                return {'type': 'stream', 'url': url, 'song': song}
        return None

    def play_song(self, song_id, queue=None):
        song = db.get_song(song_id)
        if not song:
            return None
        if queue:
            self.current_queue = queue
            self.queue_index = next((i for i, s in enumerate(queue) if s['id'] == song_id), 0)
        else:
            self.current_queue = [song]
            self.queue_index = 0
        result = self.get_stream_url(song_id)
        if result:
            result['queue'] = self.current_queue
            result['queue_index'] = self.queue_index
            self.current_playing_id = song_id
            db.record_play(song_id)
            self.player.on_state_change('playing', song)
            threading.Thread(target=self._prefetch_lyrics, args=(song_id,), daemon=True).start()
        # Preload next songs in queue
        if len(self.current_queue) > 1:
            next_vids = []
            for i in range(self.queue_index + 1, min(self.queue_index + 4, len(self.current_queue))):
                s = self.current_queue[i]
                vid = s.get('youtube_id', s.get('id', ''))
                if vid:
                    next_vids.append(vid)
            if next_vids:
                threading.Thread(target=self.player.preload_stream_urls, args=(next_vids,), daemon=True).start()
        return result

    def _prefetch_lyrics(self, song_id):
        try:
            self.get_lyrics(song_id)
        except Exception:
            pass

    def play_playlist(self, playlist_id, start_index=0):
        songs = db.get_playlist_songs(playlist_id)
        if not songs:
            sync_id = playlist_id.replace('sync_', '') if 'sync_' in playlist_id else ''
            if sync_id and self.ytmusic.is_authenticated():
                songs = self.ytmusic.get_playlist(sync_id)
                for s in songs:
                    db.save_song(s)
                    db.add_song_to_playlist(playlist_id, s['id'])

        if songs and start_index < len(songs):
            self.current_queue = songs
            self.queue_index = start_index
            return self.get_stream_url(songs[start_index]['id'])
        return None

    def queue_next(self):
        if self.queue_index < len(self.current_queue) - 1:
            self.queue_index += 1
            return self.get_stream_url(self.current_queue[self.queue_index]['id'])
        return None

    def queue_prev(self):
        if self.queue_index > 0:
            self.queue_index -= 1
            return self.get_stream_url(self.current_queue[self.queue_index]['id'])
        return None

    def toggle_play(self):
        self.player.toggle_play()
        self._emit('player_status', self.player.get_status())

    def seek(self, position):
        self.player.seek(position)

    def set_volume(self, volume):
        self.player.set_volume(volume)

    def get_player_status(self):
        return self.player.get_status()

    def next_song(self):
        result = self.queue_next()
        if result:
            self.player.on_state_change('playing', result.get('song'))
            self._emit('song_changed', result['song'])
        return result

    def prev_song(self):
        result = self.queue_prev()
        if result:
            self.player.on_state_change('playing', result.get('song'))
            self._emit('song_changed', result['song'])
        return result

    def get_queue(self):
        return self.current_queue

    # ===== Downloads =====
    def download_song(self, song_id):
        song = db.get_song(song_id)
        if song:
            thread = threading.Thread(target=self.downloader.download_song, args=(song,), daemon=True)
            thread.start()
            return True
        return False

    def get_downloads(self):
        return db.get_download_queue()

    def get_downloaded_songs(self):
        return db.get_downloaded_songs()

    def delete_download(self, song_id):
        self.downloader.delete_download(song_id)

    def cancel_download(self, song_id):
        self.downloader.cancel_download(song_id)

    def get_download_dir(self):
        return self.downloader.get_download_dir()

    # ===== Lyrics =====
    def get_lyrics(self, song_id=None):
        if song_id is None:
            song_id = self.current_playing_id
        if not song_id:
            return None

        song = db.get_song(song_id)
        if not song:
            return None

        cached = song.get('lyrics', '')
        if cached:
            try:
                return json.loads(cached)
            except:
                pass

        duration = song.get('duration', 0) or song.get('duration_seconds', 0)
        vid = song.get('youtube_id', song.get('id', ''))
        download_dir = self.downloader.download_dir if self.downloader else None
        lyrics = self.lyrics_fetcher.get_synced_lyrics(
            song['artist'], song['title'], duration,
            song_id=vid, download_dir=download_dir
        )
        if lyrics:
            if download_dir:
                self.lyrics_fetcher.save_lrc(song['artist'], song['title'], lyrics, download_dir)
            db.save_song({**song, 'lyrics': json.dumps(lyrics)})
        return lyrics

    # ===== Sync =====
    def start_sync(self):
        self.sync_service.start()

    def stop_sync(self):
        self.sync_service.stop()

    def force_sync(self):
        return self.sync_service.force_sync()

    def fix_sync(self):
        try:
            deleted = db.cleanup_orphan_playlists()
            if self.ytmusic.is_authenticated():
                self.sync_service.force_sync()
            return {
                'success': True,
                'message': f'Reparación completada. Playlists limpiadas: {deleted or 0}',
                'deleted': deleted or 0
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def set_sync_interval(self, interval):
        self.sync_service._sync_interval = interval

    # ===== Library (local) =====
    def get_all_songs(self):
        return db.get_all_songs()

    def get_song(self, song_id):
        return db.get_song(song_id)

    # ===== Themes =====
    def get_themes(self):
        return list(themes_mod.get_themes().values())

    def save_theme(self, theme_json):
        theme = json.loads(theme_json)
        return themes_mod.save_custom_theme(theme)

    def delete_theme(self, name):
        return themes_mod.delete_custom_theme(name)

    def get_current_theme(self):
        theme_name = db.get_setting('theme', 'Oscuro')
        themes = themes_mod.get_themes()
        return themes.get(theme_name, themes['Oscuro'])

    def set_theme(self, name):
        db.save_setting('theme', name)
        themes = themes_mod.get_themes()
        theme = themes.get(name, themes['Oscuro'])
        self._emit('theme_changed', theme)
        return theme

    # ===== Download All Liked =====
    def download_all_liked(self):
        songs = db.get_liked_songs()
        count = 0
        for song in songs:
            vid = song.get('youtube_id') or song.get('id', '')
            if vid and not song.get('downloaded'):
                self.download_song(song.get('id', vid))
                count += 1
        return {'downloaded': count, 'total': len(songs)}

    # ===== Settings =====
    def get_settings(self):
        return {
            'theme': db.get_setting('theme', 'Oscuro'),
            'volume': int(db.get_setting('volume', '80')),
            'sync_interval': int(db.get_setting('sync_interval', '60')),
            'download_dir': self.downloader.get_download_dir(),
            'audio_quality': db.get_setting('audio_quality', 'best'),
            'audio_format': db.get_setting('audio_format', 'mp3'),
            'crossfade': int(db.get_setting('crossfade', '0')),
            'skip_silence': db.get_setting('skip_silence', 'false'),
            'equalizer': db.get_setting('equalizer', ''),
        }

    def get_setting(self, key, default=''):
        return db.get_setting(key, default)

    def save_settings(self, settings_json):
        settings = json.loads(settings_json)
        for k, v in settings.items():
            db.save_setting(k, v)
        if 'volume' in settings:
            self.player.set_volume(int(settings['volume']))
        if 'theme' in settings:
            self.set_theme(settings['theme'])
        if 'sync_interval' in settings:
            self.set_sync_interval(int(settings['sync_interval']))
        self._emit('settings_updated', settings)
