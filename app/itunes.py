import json
import urllib.parse
import urllib.request


class iTunesClient:
    def __init__(self):
        pass

    def _get(self, params):
        url = 'https://itunes.apple.com/search?' + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={'User-Agent': 'Zonor/1.0'})
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                return json.loads(r.read().decode())
        except Exception as e:
            print(f"iTunes API error: {e}")
            return None

    def _parse_track(self, track):
        return {
            'id': f"it_{track.get('trackId', '')}",
            'title': track.get('trackName', 'Unknown'),
            'artist': track.get('artistName', ''),
            'album': track.get('collectionName', ''),
            'duration': (track.get('trackTimeMillis') or 0) / 1000,
            'duration_seconds': (track.get('trackTimeMillis') or 0) / 1000,
            'thumbnail': track.get('artworkUrl100', '').replace('100x100bb', '300x300bb'),
            'youtube_id': '',
            'explicit': bool(track.get('trackExplicitness', '') == 'explicit'),
            'platform': 'apple',
            'spotify_id': '',
            'is_playable_download': True,
        }

    def search(self, query, limit=20):
        params = {'term': query, 'media': 'music', 'entity': 'song', 'limit': min(limit, 50)}
        data = self._get(params)
        if not data:
            return []
        tracks = data.get('results', [])
        return [self._parse_track(t) for t in tracks[:limit]]

    def get_top_songs(self, limit=15):
        url = f'https://rss.applemarketingtools.com/api/v2/us/music/most-played/{min(limit, 50)}/songs.json'
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'Zonor/1.0'}), timeout=15) as r:
                data = json.loads(r.read().decode())
            items = (data.get('feed') or {}).get('results', [])
            tracks = []
            for it in items:
                tracks.append({
                    'id': f"it_{it.get('id', '')}",
                    'title': it.get('name', 'Unknown'),
                    'artist': it.get('artistName', ''),
                    'album': it.get('albumName', ''),
                    'duration': it.get('duration', 0),
                    'duration_seconds': it.get('duration', 0),
                    'thumbnail': it.get('artworkUrl100', '').replace('100x100bb', '300x300bb'),
                    'youtube_id': '',
                    'explicit': False,
                    'platform': 'apple',
                    'spotify_id': '',
                    'is_playable_download': True,
                })
            return tracks[:limit]
        except Exception as e:
            print(f"iTunes top songs error: {e}")
            return []