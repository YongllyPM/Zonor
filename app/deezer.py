import json
import urllib.parse
import urllib.request


class DeezerClient:
    def __init__(self):
        pass

    def _get(self, path, params=None):
        url = f"https://api.deezer.com{path}"
        if params:
            url += '?' + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={'User-Agent': 'Zonor/1.0'})
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                return json.loads(r.read().decode())
        except Exception as e:
            print(f"Deezer API error: {e}")
            return None

    def _parse_track(self, track):
        album = track.get('album', {}) or {}
        artist = track.get('artist', {}) or {}
        return {
            'id': f"dz_{track.get('id', '')}",
            'title': track.get('title', 'Unknown'),
            'artist': artist.get('name', ''),
            'album': album.get('title', ''),
            'duration': track.get('duration', 0),
            'duration_seconds': track.get('duration', 0),
            'thumbnail': album.get('cover_medium', album.get('cover', '')),
            'youtube_id': '',
            'explicit': bool(track.get('explicit_lyrics', False)),
            'platform': 'deezer',
            'spotify_id': '',
            'is_playable_download': True,
        }

    def search(self, query, limit=20):
        data = self._get('/search', {'q': query, 'limit': min(limit, 50)})
        if not data:
            return []
        tracks = data.get('data', [])
        return [self._parse_track(t) for t in tracks[:limit]]

    def get_chart(self, limit=15):
        data = self._get('/chart/0/tracks', {'limit': min(limit, 50)})
        if not data:
            return []
        tracks = data.get('data', [])
        return [self._parse_track(t) for t in tracks[:limit]]

    def get_track(self, track_id):
        data = self._get(f'/track/{track_id}')
        if not data:
            return None
        return self._parse_track(data)