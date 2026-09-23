import json
import base64
import threading
import os
import time
from pathlib import Path
import webview
from . import db
from . import player as player_mod
from . import ytmusic_handler as yt_mod
from . import downloader as dl_mod
from . import lyrics as lyrics_mod
from . import sync as sync_mod
from . import themes as themes_mod
from . import transcriber as tr_mod
from . import deezer as dz_mod
from . import itunes as it_mod
import traceback


class API:
    def __init__(self, window=None):
        self.window = window
        self.ytmusic = yt_mod.YTMusicHandler(on_auth_change=self._on_auth_change)
        self.deezer = dz_mod.DeezerClient()
        self.itunes = it_mod.iTunesClient()
        self.player = player_mod.MusicPlayer(on_status_change=self._on_player_status)
        self.downloader = dl_mod.Downloader(
            on_progress=self._on_download_progress,
            on_error=self._on_download_error,
            ytmusic_handler=self.ytmusic,
        )
        self.downloader._server.set_stream_resolver(self.player.get_stream_url)
        self.lyrics_fetcher = lyrics_mod.LyricsFetcher(ytmusic_handler=self.ytmusic)
        self.transcriber = tr_mod.Transcriber(downloader=self.downloader, ytmusic_handler=self.ytmusic)
        self.sync_service = sync_mod.SyncService(self.ytmusic, on_sync_event=self._on_sync_event)
        self.current_playing_id = None
        self.current_queue = []
        self.queue_index = -1
        self._listeners = {}

        db.init_db()
        threading.Thread(target=self._post_init, daemon=True).start()
        threading.Thread(target=self._backup_check_loop, daemon=True).start()

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

    def _enrich_with_platform_catalog(self, feed):
        try:
            deezer_trending = self.deezer.get_chart(min(12, 12))
            apple_trending = self.itunes.get_top_songs(min(12, 12))
        except Exception as e:
            print(f"Platform catalog error: {e}")
            deezer_trending, apple_trending = [], []
        combined = [('deezer', deezer_trending), ('apple', apple_trending)]
        for plat, songs in combined:
            for s in songs:
                s['platform'] = plat
                db.save_song(s)
        combined_trending = feed.get('trending', []) + deezer_trending + apple_trending
        feed['trending'] = combined_trending[:28]
        combined_hits = feed.get('top_songs', []) + deezer_trending[:8]
        feed['top_songs'] = combined_hits[:28]
        feed['deezer_trending'] = deezer_trending[:12]
        feed['apple_trending'] = apple_trending[:12]
        return feed

    def _refresh_home_feed(self):
        try:
            try:
                feed = self.ytmusic.get_home_feed()
            except Exception as e:
                print(f"YT home feed error: {e}")
                feed = {}
            for key in ('trending', 'top_songs', 'new_releases', 'listen_again', 'recent'):
                for s in feed.get(key, []):
                    s['platform'] = 'youtube'
                    db.save_song(s)
            for pl in feed.get('playlists', []):
                if pl.get('id'):
                    db.save_playlist({
                        'id': f"home_{pl['id']}",
                        'name': pl.get('title') or pl.get('name', 'Playlist'),
                        'description': pl.get('description', ''),
                        'thumbnail': pl.get('thumbnail', ''),
                    })
            feed = self._enrich_with_platform_catalog(feed)
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
        db.clear_playlist_data()
        db.cache_clear()

    def factoryReset(self):
        try:
            dl_dir = db.get_setting('download_folder') or str(Path(os.environ['APPDATA']) / 'Zonor' / 'downloads')
            import shutil
            if Path(dl_dir).exists():
                for f in Path(dl_dir).iterdir():
                    if f.is_file():
                        f.unlink()
            db.factory_reset_db()
            self.ytmusic.logout()
            self.player.current_song = None
            self.player.state = 'stopped'
            self.player.position = 0
            self.player.duration = 0
            self.player.invalidate_stream_cache()
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

    # ===== Platform catalog =====
    def get_platform_catalog(self, platform, limit=24):
        songs = []
        if platform == 'deezer':
            songs = self.deezer.get_chart(limit)
        elif platform == 'apple':
            songs = self.itunes.get_top_songs(limit)
        elif platform == 'youtube':
            try:
                try:
                    feed = self.ytmusic.get_home_feed()
                except Exception as e:
                    print(f"YT catalog error: {e}")
                    feed = {}
                songs = (feed.get('trending') or []) + (feed.get('top_songs') or [])
            except Exception as e:
                print(f"YT catalog error: {e}")
            if not songs:
                songs = db.get_liked_songs()[:limit] or db.get_recent_plays(limit)
        for s in songs:
            s['platform'] = platform
            db.save_song(s)
        return songs

    # ===== Search =====
    def search(self, query, limit=20):
        db.add_search_history(query)
        songs = self.ytmusic.search(query, limit)
        for s in songs:
            s['platform'] = 'youtube'
            db.save_song(s)
        cats = [('deezer', self.deezer), ('apple', self.itunes)]
        for plat, client in cats:
            for s in client.search(query, max(limit // 2, 10)):
                s['platform'] = plat
                db.save_song(s)
                songs.append(s)
        return songs

    def search_suggestions(self, query):
        return self.ytmusic.search_suggestions(query)

    def get_search_history(self):
        return db.get_search_history()

    def clear_search_history(self):
        db.clear_search_history()
        return True

    # ===== Library =====
    def get_library(self):
        return self.ytmusic.get_library()

    def get_artists(self):
        return self.ytmusic.get_subscriptions()

    def get_artist_albums(self, channel_id):
        return self.ytmusic.get_artist_albums(channel_id)

    def get_liked_songs(self):
        return db.get_liked_songs()

    def get_recent_plays(self, limit=15):
        return db.get_recent_plays(limit)

    def update_song_duration(self, song_id, duration):
        song = db.get_song(song_id)
        if song:
            db.save_song({**song, 'duration': int(duration)})
            return {'ok': True}
        return {'ok': False}

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
        if 'sync_' in playlist_id and self.ytmusic.is_authenticated():
            sync_id = playlist_id.replace('sync_', '')
            try:
                songs = self.ytmusic.get_playlist(sync_id)
                if songs:
                    db.clear_playlist_songs(playlist_id)
                    for s in songs:
                        db.save_song(s)
                        db.add_song_to_playlist(playlist_id, s['id'])
                    return songs
            except Exception:
                pass
        return db.get_playlist_songs(playlist_id)

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
        self.current_playing_id = song_id
        db.record_play(song_id)
        self._emit('recent_played', {'song_id': song_id})
        downloaded_path = self.downloader.get_download_path(song_id)
        if downloaded_path:
            http_url = self.downloader._server.url_for(downloaded_path)
            if http_url:
                song = dict(song)
                thumb = song.get('thumbnail', '')
                if thumb and not thumb.startswith('http://127.0.0.1'):
                    thumb_file = f"{song_id}.jpg"
                    thumb_path = Path(self.downloader.download_dir) / thumb_file
                    if thumb_path.exists():
                        song['thumbnail'] = self.downloader._server.url_for(str(thumb_path))
                return {'type': 'stream', 'url': http_url, 'song': song}
        vid = song.get('youtube_id', song.get('id', ''))
        if song.get('platform') != 'youtube' and not vid:
            vid = self._resolve_to_youtube(song)
            if vid:
                song = {**song, 'youtube_id': vid}
                db.save_song(song)
        if vid:
            local_url = self.downloader._server.url_for_stream(vid)
            if local_url:
                return {'type': 'stream', 'url': local_url, 'song': song}
            url = self.player.get_stream_url(vid)
            if url:
                return {'type': 'stream', 'url': url, 'song': song}
        return None

    def _resolve_to_youtube(self, song):
        try:
            query = f"{song.get('artist', '')} {song.get('title', '')}".strip()
            results = self.ytmusic.search(query, limit=5)
            for r in results:
                vid = r.get('youtube_id') or r.get('id')
                if vid:
                    return vid
        except Exception as e:
            print(f"Resolve error: {e}")
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
            self.player.on_state_change('playing', song)
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
        if not song:
            return False
        if song.get('platform') != 'youtube' and not (song.get('youtube_id') or ''):
            vid = self._resolve_to_youtube(song)
            if not vid:
                self._emit('download_error', {'song_id': song_id, 'error': 'No se encontró esta canción en YouTube Music para descargarla.'})
                return False
            song = {**song, 'youtube_id': vid}
            db.save_song(song)
        thread = threading.Thread(target=self.downloader.download_song, args=(song,), daemon=True)
        thread.start()
        return True

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

    def open_download_dir(self):
        import subprocess
        path = self.downloader.get_download_dir()
        if not path:
            return {'ok': False, 'error': 'Sin carpeta de descargas'}
        try:
            if os.name == 'nt':
                subprocess.Popen(['explorer', path])
            elif sys.platform == 'darwin':
                subprocess.Popen(['open', path])
            else:
                subprocess.Popen(['xdg-open', path])
            return {'ok': True}
        except Exception as e:
            return {'ok': False, 'error': str(e)}

    # ===== Lyrics =====
    def get_lyrics(self, song_id=None):
        if song_id is None:
            song_id = self.current_playing_id
        if not song_id:
            return None

        song = db.get_song(song_id)
        if not song:
            return None

        duration = song.get('duration', 0) or song.get('duration_seconds', 0)

        cached = song.get('lyrics', '')
        if cached:
            try:
                lyrics = json.loads(cached)
                if lyrics and lyrics.get('lines'):
                    rescaled = self._autosync_lyrics(lyrics, duration)
                    if rescaled is not lyrics:
                        db.save_song({**song, 'lyrics': json.dumps(rescaled)})
                    lyrics = rescaled
                return lyrics
            except:
                pass

        vid = song.get('youtube_id', song.get('id', ''))
        download_dir = self.downloader.download_dir if self.downloader else None
        lyrics = self.lyrics_fetcher.get_synced_lyrics(
            song['artist'], song['title'], duration,
            song_id=vid, download_dir=download_dir
        )
        if lyrics:
            lyrics = self._autosync_lyrics(lyrics, duration)
            if download_dir:
                self.lyrics_fetcher.save_lrc(song['artist'], song['title'], lyrics, download_dir)
            db.save_song({**song, 'lyrics': json.dumps(lyrics)})
        return lyrics

    def _autosync_lyrics(self, lyrics, actual_duration):
        lines = lyrics.get('lines') or []
        if not lines or lyrics.get('type') != 'synced':
            return lyrics
        has_time = any(l.get('time', 0) > 0 for l in lines)
        if not has_time:
            return lyrics
        actual_duration = actual_duration or 0
        src_duration = lyrics.get('duration') or 0
        if src_duration <= 0:
            return lyrics
        if actual_duration <= 0:
            return lyrics
        diff_ratio = actual_duration / src_duration
        if 0.92 <= diff_ratio <= 1.08:
            return lyrics
        scale = min(max(diff_ratio, 0.5), 2.0)
        scaled = []
        for l in lines:
            nl = dict(l)
            t = nl.get('time', 0)
            if t > 0:
                nl['time'] = round(t * scale, 3)
            scaled.append(nl)
        return {
            **lyrics,
            'type': 'synced',
            'lines': scaled,
            'source': f"{lyrics.get('source', '')} · auto-ajustada (×{scale:.2f})",
        }

    def save_lyrics_edit(self, song_id, lyrics_json):
        try:
            song = db.get_song(song_id)
            if not song:
                return {'success': False, 'error': 'Canción no encontrada'}
            db.save_song({**song, 'lyrics': lyrics_json})
            return {'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def translate_lyrics(self, song_id=None, target_lang=None):
        if song_id is None:
            song_id = self.current_playing_id
        if not song_id:
            return None
        if not target_lang:
            target_lang = db.get_setting('translation_lang', 'es')
        song = db.get_song(song_id)
        if not song:
            return None
        cached = song.get('lyrics', '')
        lyrics_data = None
        if cached:
            try:
                lyrics_data = json.loads(cached)
            except:
                pass
        if not lyrics_data:
            lyrics_data = self.get_lyrics(song_id)
        if not lyrics_data:
            return None
        original = lyrics_data.get('original') or lyrics_data
        if lyrics_data.get('translated_from'):
            if lyrics_data.get('lang') == target_lang:
                return lyrics_data
            lyrics_data = original
        translated = self.lyrics_fetcher.translate_lyrics(lyrics_data, target_lang)
        if translated:
            if translated is not lyrics_data:
                translated = {**translated, 'original': original}
            db.save_song({**song, 'lyrics': json.dumps(translated)})
        return translated

    def search_lyrics(self, artist, title):
        return self.lyrics_fetcher.search_lrclib(artist, title)

    def fetch_lyrics_by_id(self, lrclib_id):
        return self.lyrics_fetcher.fetch_lrclib_by_id(lrclib_id)

    def submit_lyrics_correction(self, artist, title, album, duration, plain_lyrics, synced_lyrics):
        self._emit('lrclib_submit_start', {})

        def _run():
            def on_progress(pct, msg):
                self._emit('lrclib_submit_progress', {'progress': pct, 'status': msg})
            try:
                result = self.lyrics_fetcher.submit_to_lrclib(
                    artist, title, album, duration, plain_lyrics, synced_lyrics,
                    on_progress=on_progress,
                )
            except Exception as e:
                result = {'success': False, 'error': str(e)}
            self._emit('lrclib_submit_done', result)

        threading.Thread(target=_run, daemon=True).start()
        return {'started': True}

    def transcribe_lyrics(self, song_id):
        try:
            song = db.get_song(song_id)
            if not song:
                return {'started': False, 'error': 'Canción no encontrada'}

            downloaded_path = self.downloader.get_download_path(song_id) if self.downloader else None

            def _run():
                def on_progress(pct, msg):
                    self._emit('transcription_progress', {'progress': pct, 'status': msg})
                def on_error(sid, error):
                    self._emit('transcription_error', {'error': error})
                def on_done(sid, result):
                    try:
                        db.save_song({**song, 'lyrics': json.dumps(result)})
                    except Exception:
                        pass
                    self._emit('transcription_done', {'lyrics': result})

                self.transcriber.set_callbacks(on_progress=on_progress, on_error=on_error, on_done=on_done)
                self.transcriber.transcribe(song_id, audio_path=downloaded_path)

            threading.Thread(target=_run, daemon=True).start()
            return {'started': True}
        except Exception as e:
            return {'started': False, 'error': str(e)}

    def check_transcriber(self):
        return self.transcriber.is_available()

    def install_transcriber(self):
        import threading
        def _run():
            def on_progress(pct, msg):
                self._emit('install_progress', {'progress': pct, 'status': msg})
            def on_error(sid, error):
                self._emit('install_error', {'error': error})
            def on_done(sid, result):
                pass
            self.transcriber.set_callbacks(on_progress=on_progress, on_error=on_error, on_done=on_done)
            result = self.transcriber.install()
            self._emit('install_done', result)
        threading.Thread(target=_run, daemon=True).start()
        return {'started': True}

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
        theme_name = db.get_setting('theme', 'Android Verde')
        themes = themes_mod.get_themes()
        return themes.get(theme_name, themes['Android Verde'])

    def set_theme(self, name):
        db.save_setting('theme', name)
        themes = themes_mod.get_themes()
        theme = themes.get(name, themes['Android Verde'])
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

    # ===== Data Export / Import / Backup =====
    def export_data(self):
        try:
            data = db.export_all_data()
            data['created_at'] = int(time.time())
            default_name = f"zonor_backup_{time.strftime('%Y-%m-%d_%H-%M-%S')}.json"
            path = self.window.create_file_dialog(
                webview.SAVE_DIALOG,
                save_filename=default_name,
                file_types=('Archivo JSON (*.json)',),
            )
            if not path:
                return {'ok': False, 'error': 'Cancelado'}
            if isinstance(path, (list, tuple)):
                path = path[0]
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return {'ok': True, 'path': path}
        except Exception as e:
            traceback.print_exc()
            return {'ok': False, 'error': str(e)}

    def import_data(self):
        try:
            path = self.window.create_file_dialog(
                webview.OPEN_DIALOG,
                file_types=('Archivo JSON (*.json)',),
            )
            if not path:
                return {'ok': False, 'error': 'Cancelado'}
            if isinstance(path, (list, tuple)):
                path = path[0]
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if not isinstance(data, dict) or 'songs' not in data:
                return {'ok': False, 'error': 'Archivo no válido'}
            db.import_all_data(data)
            self._reload_after_import()
            self._emit('library_changed', {})
            return {'ok': True, 'path': path}
        except Exception as e:
            traceback.print_exc()
            return {'ok': False, 'error': str(e)}

    def _reload_after_import(self):
        try:
            self.ytmusic.auto_login()
            if self.ytmusic.is_authenticated():
                try:
                    self.sync_service.force_sync()
                except Exception:
                    pass
        except Exception:
            pass
        self.player.current_song = None
        self.player.state = 'stopped'
        self.player.position = 0
        self.player.duration = 0
        self.player.invalidate_stream_cache()
        self.current_queue = []
        self.queue_index = -1
        self.current_playing_id = None

    def _backup_check_loop(self):
        while True:
            try:
                if db.get_setting('backup_enabled', 'true') == 'true':
                    self._run_scheduled_backup()
            except Exception as e:
                print(f"Backup check error: {e}")
            time.sleep(3600)

    def _run_scheduled_backup(self):
        interval = db.get_setting('backup_interval', 'monthly')
        seconds = {'daily': 86400, 'weekly': 604800, 'monthly': 2592000}.get(interval, 2592000)
        last = int(db.get_setting('last_backup', '0') or 0)
        if time.time() - last < seconds:
            return
        try:
            result = self._write_backup_file()
            db.save_setting('last_backup', str(int(time.time())))
            self._emit('backup_created', {'path': result.get('path', '')})
        except Exception as e:
            print(f"Backup error: {e}")

    def _write_backup_file(self):
        backup_dir = db.get_setting('backup_dir', '')
        if not backup_dir:
            backup_dir = str(Path(os.environ.get('APPDATA', '')) / 'Zonor' / 'backups')
        dest = Path(backup_dir)
        dest.mkdir(parents=True, exist_ok=True)
        data = db.export_all_data()
        data['created_at'] = int(time.time())
        path = dest / 'zonor_backup.json'
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return {'ok': True, 'path': str(path)}

    def backup_now(self):
        try:
            result = self._write_backup_file()
            db.save_setting('last_backup', str(int(time.time())))
            self._emit('backup_created', {'path': result.get('path', '')})
            return result
        except Exception as e:
            traceback.print_exc()
            return {'ok': False, 'error': str(e)}

    def get_backup_info(self):
        backup_dir = db.get_setting('backup_dir', '') or str(Path(os.environ.get('APPDATA', '')) / 'Zonor' / 'backups')
        last = db.get_setting('last_backup', '0') or '0'
        files = []
        try:
            p = Path(backup_dir) / 'zonor_backup.json'
            if p.exists():
                files.append({'name': p.name, 'size': p.stat().st_size, 'created': int(p.stat().st_mtime)})
        except Exception:
            pass
        return {
            'enabled': db.get_setting('backup_enabled', 'true') == 'true',
            'interval': db.get_setting('backup_interval', 'monthly'),
            'backup_dir': backup_dir,
            'last_backup': int(last) if last else 0,
            'files': files,
        }

    # ===== Settings =====
    def get_settings(self):
        return {
            'theme': db.get_setting('theme', 'Android Verde'),
            'volume': int(db.get_setting('volume', '80')),
            'sync_interval': int(db.get_setting('sync_interval', '60')),
            'download_dir': self.downloader.get_download_dir(),
            'audio_quality': db.get_setting('audio_quality', 'best'),
            'audio_quality_youtube': db.get_setting('audio_quality_youtube', 'high'),
            'audio_quality_deezer': db.get_setting('audio_quality_deezer', 'best'),
            'audio_quality_apple': db.get_setting('audio_quality_apple', 'high'),
            'audio_format': db.get_setting('audio_format', 'mp3'),
            'crossfade': int(db.get_setting('crossfade', '0')),
            'skip_silence': db.get_setting('skip_silence', 'false'),
            'equalizer': db.get_setting('equalizer', ''),
            'translation_lang': db.get_setting('translation_lang', 'es'),
            'backup_enabled': db.get_setting('backup_enabled', 'true'),
            'backup_interval': db.get_setting('backup_interval', 'monthly'),
            'last_backup': int(db.get_setting('last_backup', '0') or 0),
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
