import threading
import time
import json
from . import db
from . import ytmusic_handler


class SyncService:
    def __init__(self, ytmusic: ytmusic_handler.YTMusicHandler, on_sync_event=None):
        self.ytmusic = ytmusic
        self.on_sync_event = on_sync_event
        self._running = False
        self._thread = None
        self._sync_interval = 60

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._sync_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    def _sync_loop(self):
        while self._running:
            if self.ytmusic.is_authenticated():
                try:
                    self._sync_playlists()
                except Exception as e:
                    print(f"Sync error: {e}")
            time.sleep(self._sync_interval)

    def _sync_playlists(self):
        try:
            remote_playlists = self.ytmusic.get_playlists()
            local_playlists = db.get_playlists()

            local_by_sync = {p['sync_id']: p for p in local_playlists if p.get('sync_id')}
            local_by_home_id = {}
            for p in local_playlists:
                if p['id'].startswith('home_'):
                    local_by_home_id[p['id'][5:]] = p
            remote_by_id = {p['id']: p for p in remote_playlists}

            for rp in remote_playlists:
                song_count_hint = rp.get('song_count', 0)
                if rp['id'] in local_by_sync:
                    lp = local_by_sync[rp['id']]
                    db.save_playlist({
                        'id': lp['id'],
                        'name': rp['name'],
                        'description': rp.get('description', ''),
                        'thumbnail': rp.get('thumbnail', ''),
                        'song_count': song_count_hint,
                        'sync_id': rp['id']
                    })
                    remote_songs = self.ytmusic.get_playlist(rp['id'])
                    print(f"Sync: fetched {len(remote_songs)} songs for '{rp['name']}' (expected ~{song_count_hint})")
                    self._sync_playlist_songs(lp['id'], remote_songs, remote_count_hint=song_count_hint)
                    self._emit('playlist_updated', {'playlist_id': lp['id']})
                else:
                    if rp['id'] in local_by_home_id:
                        existing_id = local_by_home_id[rp['id']]
                        db.save_playlist({
                            'id': existing_id,
                            'name': rp['name'],
                            'description': rp.get('description', ''),
                            'thumbnail': rp.get('thumbnail', ''),
                            'song_count': song_count_hint,
                            'sync_id': rp['id']
                        })
                        pl_id = existing_id
                    else:
                        pl_id = f"sync_{rp['id']}"
                        db.save_playlist({
                            'id': pl_id,
                            'name': rp['name'],
                            'description': rp.get('description', ''),
                            'thumbnail': rp.get('thumbnail', ''),
                            'song_count': song_count_hint,
                            'sync_id': rp['id']
                        })
                    remote_songs = self.ytmusic.get_playlist(rp['id'])
                    print(f"Sync: fetched {len(remote_songs)} songs for NEW '{rp['name']}' (expected ~{song_count_hint})")
                    db.clear_playlist_songs(pl_id)
                    for song in remote_songs:
                        db.save_song(song)
                        db.add_song_to_playlist(pl_id, song['id'])
                    self._emit('playlist_added', {'playlist_id': pl_id})

            for lp in local_playlists:
                if lp.get('sync_id') and lp['sync_id'] not in remote_by_id:
                    db.delete_playlist(lp['id'])
                    self._emit('playlist_removed', {'playlist_id': lp['id']})

            db.cleanup_orphan_playlists()

        except Exception as e:
            print(f"Playlist sync error: {e}")

    def _sync_playlist_songs(self, local_playlist_id, remote_songs, remote_count_hint=None):
        existing = db.get_playlist_songs(local_playlist_id)
        existing_ids = {s['id'] for s in existing}
        remote_ids = {s['id'] for s in remote_songs}

        for song in remote_songs:
            if song['id'] not in existing_ids:
                db.save_song(song)
                db.add_song_to_playlist(local_playlist_id, song['id'])
            else:
                db.save_song(song)

        if remote_count_hint and len(remote_songs) < remote_count_hint * 0.9:
            print(f"Sync: skipping deletion for {local_playlist_id} — got {len(remote_songs)} of ~{remote_count_hint} songs")
            return

        for es in existing:
            if es['id'] not in remote_ids:
                db.remove_song_from_playlist(local_playlist_id, es['id'])

    def force_sync(self):
        if self.ytmusic.is_authenticated():
            self._sync_playlists()
            return True
        return False

    def _emit(self, event, data):
        if self.on_sync_event:
            self.on_sync_event(event, data)
