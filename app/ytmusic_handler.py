import os
import json
import logging
import re
import webbrowser
from pathlib import Path

import ytmusicapi
from ytmusicapi import YTMusic

logger = logging.getLogger('zonor.auth')

try:
    import browser_cookie3
    HAS_BROWSER_COOKIE = True
except ImportError:
    HAS_BROWSER_COOKIE = False


class YTMusicHandler:
    def __init__(self, on_auth_change=None):
        self.yt = None
        self.authenticated = False
        self.user_info = None
        self.auth_error = None
        self.on_auth_change = on_auth_change
        self._headers_file = Path(os.environ.get('APPDATA', '')) / 'Zonor' / 'headers.json'
        self._oauth_file = Path(os.environ.get('APPDATA', '')) / 'Zonor' / 'oauth.json'
        self._oauth_creds_file = Path(os.environ.get('APPDATA', '')) / 'Zonor' / 'oauth_credentials.json'
        self._try_restore_session()

    def _try_restore_session(self):
        if not self._headers_file.exists():
            return
        try:
            self.yt = YTMusic(str(self._headers_file))
            account = self.yt.get_account_info()
            self.authenticated = True
            self.user_info = account
            self.auth_error = None
        except Exception as e:
            self.yt = YTMusic()
            self.authenticated = False
            self.user_info = None
            self.auth_error = str(e)

    def get_auth_status(self):
        if self.authenticated and self.yt:
            self._validate_session()
        return {
            'authenticated': self.authenticated,
            'user': self.user_info,
            'has_credentials': self._headers_file.exists() or self._oauth_file.exists(),
            'error': self.auth_error,
        }

    def _validate_session(self):
        if not self.yt:
            return False
        try:
            self.user_info = self.yt.get_account_info()
            self.authenticated = True
            self.auth_error = None
            return True
        except Exception:
            self.authenticated = False
            self.auth_error = 'Sesión expirada. Vuelve a iniciar sesión.'
            return False

    def auto_login(self):
        if not self._headers_file.exists():
            return {'success': False, 'error': 'No hay sesión guardada'}
        if self._validate_session():
            if self.on_auth_change:
                self.on_auth_change(True, self.user_info)
            return {'success': True, 'user': self.user_info}
        return {'success': False, 'error': self.auth_error or 'Sesión inválida'}

    def _normalize_headers_dict(self, headers):
        h = {}
        for key, value in headers.items():
            if value is None or value == '':
                continue
            if key.lower() == 'cookie':
                h['Cookie'] = value
            else:
                h[key] = value
        if 'Cookie' not in h and 'cookie' in headers:
            h['Cookie'] = headers['cookie']
        h.setdefault('Accept', '*/*')
        h.setdefault('Content-Type', 'application/json')
        h.setdefault('X-Goog-AuthUser', '0')
        h.setdefault('x-origin', 'https://music.youtube.com')
        h.setdefault('Authorization', 'SAPISIDHASH 0_0')
        return h

    def _parse_curl(self, text):
        headers = {}
        cookie = None
        for line in text.splitlines():
            line = line.strip().rstrip('\\').strip()
            m = re.match(r'-H\s+(?:"([^"]*)"|\'([^\']*)\')', line)
            if m:
                val = m.group(1) or m.group(2)
                key, _, value = val.partition(': ')
                if key.lower() == 'cookie':
                    cookie = value
                else:
                    headers[key] = value
        if cookie:
            headers['Cookie'] = cookie
        return headers

    def _save_headers_file(self, headers_dict=None, headers_raw=None):
        self._headers_file.parent.mkdir(parents=True, exist_ok=True)
        if headers_raw:
            parsed = self._parse_curl(headers_raw)
            parsed.update({
                'x-goog-authuser': '0',
                'x-origin': 'https://music.youtube.com',
                'Accept': '*/*',
                'Content-Type': 'application/json',
            })
            if 'Cookie' not in parsed:
                raise ValueError('No se encontró la cookie en el cURL. Asegúrate de haber iniciado sesión en Firefox.')
            headers_dict = parsed
        if headers_dict:
            normalized = self._normalize_headers_dict(headers_dict)
            with open(str(self._headers_file), 'w', encoding='utf-8') as f:
                json.dump(normalized, f, indent=2)
        else:
            raise ValueError('No headers provided')

    def _activate_session(self):
        try:
            self.yt = YTMusic(str(self._headers_file))
            account = self.yt.get_account_info()
            self.authenticated = True
            self.user_info = account
            self.auth_error = None
            if self.on_auth_change:
                self.on_auth_change(True, self.user_info)
            return True
        except Exception as e:
            logger.error(f"Session activation failed: {e}")
            self.auth_error = str(e)
            return False

    def login_with_cookie(self, cookie_string):
        cookie = cookie_string.strip()
        if not cookie:
            return False
        headers = {
            'Cookie': cookie,
            'x-origin': 'https://music.youtube.com',
            'Accept': '*/*',
            'Content-Type': 'application/json',
            'X-Goog-AuthUser': '0',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        }
        return self.login_with_headers(headers)

    def login_with_headers(self, headers_input):
        try:
            if isinstance(headers_input, str):
                raw = headers_input.strip()
                if not raw:
                    return False
                if raw.startswith('{'):
                    headers_dict = json.loads(raw)
                    self._save_headers_file(headers_dict=headers_dict)
                elif 'fetch(' in raw or '\n' in raw or raw.lower().startswith('accept:'):
                    self._save_headers_file(headers_raw=raw)
                else:
                    return self.login_with_cookie(raw)
            else:
                self._save_headers_file(headers_dict=headers_input)

            return self._activate_session()
        except Exception as e:
            logger.error(f"Auth error: {e}")
            self.auth_error = str(e)
            return False

    def _build_cookie_string(self, cookies):
        seen = set()
        parts = []
        for c in cookies:
            if c.name in seen:
                continue
            seen.add(c.name)
            parts.append(f"{c.name}={c.value}")
        return '; '.join(parts)

    def _extract_cookies_from_browsers(self):
        if not HAS_BROWSER_COOKIE:
            logger.warning("browser-cookie3 no instalado")
            return None
        domains = ['.youtube.com', 'music.youtube.com', '.google.com']
        browsers = []
        for loader_name in ['chrome', 'brave', 'edge', 'opera', 'opera_gx', 'firefox']:
            try:
                loader = getattr(browser_cookie3, loader_name, None)
                if loader:
                    browsers.append((loader_name, loader))
            except Exception:
                pass
        for name, loader in browsers:
            try:
                all_cookies = []
                for domain in domains:
                    try:
                        all_cookies.extend(loader(domain_name=domain))
                    except Exception:
                        pass
                if not all_cookies:
                    continue
                cookie_str = self._build_cookie_string(all_cookies)
                if not cookie_str:
                    continue
                headers = {
                    'Cookie': cookie_str,
                    'x-goog-authuser': '0',
                    'x-origin': 'https://music.youtube.com',
                    'Accept': '*/*',
                    'Content-Type': 'application/json',
                }
                self._save_headers_file(headers_dict=headers)
                if self._activate_session():
                    logger.info(f"Login automático desde {name}")
                    return True
            except Exception as e:
                logger.warning(f"Error con {name}: {e}")
                continue
        return False

    def login_from_browser(self):
        try:
            self._headers_file.parent.mkdir(parents=True, exist_ok=True)
            if self._headers_file.exists() and self._validate_session():
                if self.on_auth_change:
                    self.on_auth_change(True, self.user_info)
                return {'success': True, 'user': self.user_info}

            if self._extract_cookies_from_browsers():
                if self.on_auth_change:
                    self.on_auth_change(True, self.user_info)
                return {'success': True, 'user': self.user_info}

            webbrowser.open('https://music.youtube.com')
            self.auth_error = (
                'No se encontró sesión en tus navegadores. '
                'Abre YouTube Music e inicia sesión. Luego vuelve y dale clic en "Conectar".'
            )
            return {
                'success': False,
                'open_browser': True,
                'message': self.auth_error,
            }
        except Exception as e:
            self.auth_error = str(e)
            print(f"Browser auth error: {e}")
            return {'success': False, 'error': str(e)}

    def login_oauth(self):
        try:
            self._headers_file.parent.mkdir(parents=True, exist_ok=True)
            if self._oauth_file.exists():
                creds = self._load_oauth_credentials()
                if creds:
                    from ytmusicapi.auth.oauth.credentials import OAuthCredentials
                    oauth_creds = OAuthCredentials(creds['client_id'], creds['client_secret'])
                    self.yt = YTMusic(str(self._oauth_file), oauth_credentials=oauth_creds)
                    if self._validate_session():
                        return {'success': True, 'user': self.user_info}
                self.yt = YTMusic(str(self._oauth_file))
                if self._validate_session():
                    return {'success': True, 'user': self.user_info}

            creds = self._load_oauth_credentials()
            if not creds:
                self.auth_error = (
                    'OAuth requiere client_id y client_secret de Google Cloud Console. '
                    'Usa la pestaña Rápido o Avanzado con cookie/headers.'
                )
                return {'success': False, 'error': self.auth_error}

            ytmusicapi.setup_oauth(
                creds['client_id'],
                creds['client_secret'],
                filepath=str(self._oauth_file),
                open_browser=True,
            )
            from ytmusicapi.auth.oauth.credentials import OAuthCredentials
            oauth_creds = OAuthCredentials(creds['client_id'], creds['client_secret'])
            self.yt = YTMusic(str(self._oauth_file), oauth_credentials=oauth_creds)
            if self._validate_session():
                return {'success': True, 'user': self.user_info}
            self.auth_error = 'OAuth no completado'
            return {'success': False, 'error': self.auth_error}
        except Exception as e:
            self.auth_error = str(e)
            print(f"OAuth error: {e}")
            return {'success': False, 'error': str(e)}

    def _load_oauth_credentials(self):
        if not self._oauth_creds_file.exists():
            return None
        try:
            with open(str(self._oauth_creds_file), encoding='utf-8') as f:
                data = json.load(f)
            if data.get('client_id') and data.get('client_secret'):
                return data
        except Exception:
            pass
        return None

    def logout(self):
        self.authenticated = False
        self.user_info = None
        self.auth_error = None
        self.yt = None
        if self._headers_file.exists():
            self._headers_file.unlink()
        if self.on_auth_change:
            self.on_auth_change(False, None)

    def is_authenticated(self):
        return self.authenticated

    def ensure_auth(self):
        if self.yt is None:
            try:
                if self._headers_file.exists():
                    self.yt = YTMusic(str(self._headers_file))
                    self.authenticated = True
                    try:
                        self.user_info = self.yt.get_account_info()
                    except:
                        self.user_info = {'name': 'User'}
                    return True
                else:
                    self.yt = YTMusic()
                    self.authenticated = False
                    self.user_info = None
                    return True
            except:
                self.yt = YTMusic()
                self.authenticated = False
                self.user_info = None
                return True
        return True

    def search(self, query, limit=20):
        self.ensure_auth()
        if not self.yt:
            return []
        try:
            results = self.yt.search(query, limit=limit)
            songs = []
            for r in results:
                if r.get('resultType') == 'song' or r.get('videoType') == 'MUSIC_VIDEO_TYPE_ATV':
                    songs.append(self._parse_song(r))
            return songs[:limit]
        except Exception as e:
            print(f"Search error: {e}")
            return []

    def search_suggestions(self, query):
        self.ensure_auth()
        if not self.yt:
            return []
        try:
            return self.yt.get_search_suggestions(query)
        except:
            return []

    def get_playlists(self):
        if not self.authenticated:
            return []
        try:
            playlists = self.yt.get_library_playlists()
            return [{
                'id': p.get('playlistId', ''),
                'name': p.get('title', 'Untitled'),
                'description': p.get('description', ''),
                'thumbnail': p.get('thumbnails', [{}])[-1].get('url', '') if p.get('thumbnails') else '',
                'song_count': p.get('itemCount', 0),
                'sync_id': p.get('playlistId', '')
            } for p in playlists]
        except Exception as e:
            print(f"Get playlists error: {e}")
            return []

    def get_playlist(self, playlist_id):
        if not self.authenticated:
            return []
        try:
            pl = self.yt.get_playlist(playlist_id, limit=None)
            songs = []
            for t in pl.get('tracks', []):
                songs.append(self._parse_song(t))
            return songs
        except Exception as e:
            print(f"Get playlist error: {e}")
            return []

    def get_library(self):
        if not self.authenticated:
            return []
        try:
            songs = self.yt.get_library_songs(limit=100)
            return [self._parse_song(s) for s in songs]
        except Exception as e:
            print(f"Get library error: {e}")
            return []

    def get_subscriptions(self):
        if not self.authenticated:
            return []
        try:
            subs = self.yt.get_library_subscriptions(limit=50)
            artists = []
            for s in subs:
                artist = {
                    'id': s.get('browseId', ''),
                    'name': s.get('artist', s.get('title', 'Unknown')),
                    'subscribers': s.get('subscribers', ''),
                    'thumbnails': s.get('thumbnails', []),
                    'thumbnail': s.get('thumbnails', [{}])[-1].get('url', '') if s.get('thumbnails') else '',
                }
                artists.append(artist)
            return artists
        except Exception as e:
            print(f"Get subscriptions error: {e}")
            return []

    def get_artist_albums(self, channel_id, params=None):
        if not self.authenticated:
            return []
        try:
            data = self.yt.get_artist(channel_id)
            albums = []
            for section in ['albums', 'singles', 'videos']:
                for item in data.get(section, {}).get('results', []):
                    albums.append({
                        'id': item.get('browseId', ''),
                        'title': item.get('title', ''),
                        'year': item.get('year', ''),
                        'thumbnails': item.get('thumbnails', []),
                        'thumbnail': item.get('thumbnails', [{}])[-1].get('url', '') if item.get('thumbnails') else '',
                    })
            return {
                'name': data.get('name', ''),
                'description': data.get('description', ''),
                'thumbnails': data.get('thumbnails', []),
                'thumbnail': data.get('thumbnails', [{}])[-1].get('url', '') if data.get('thumbnails') else '',
                'subscribers': data.get('subscribers', ''),
                'albums': albums,
            }
        except Exception as e:
            print(f"Get artist error: {e}")
            return None

    def get_liked_songs(self):
        if not self.authenticated:
            return []
        try:
            songs = self.yt.get_liked_songs(limit=100)
            return [self._parse_song(s) for s in songs.get('tracks', [])]
        except Exception as e:
            print(f"Get liked error: {e}")
            return []

    def get_history(self):
        if not self.authenticated:
            return []
        try:
            history = self.yt.get_history()
            return [self._parse_song(s) for s in history[:20]]
        except Exception as e:
            print(f"History error: {e}")
            return []

    def _extract_playlist_count(self, item):
        for key in ('itemCount', 'count', 'songCount', 'videoCount', 'trackCount'):
            val = item.get(key)
            if val is not None:
                try:
                    n = int(val)
                    if n > 0:
                        return n
                except (TypeError, ValueError):
                    pass
        subtitle = item.get('subtitle', '')
        if isinstance(subtitle, list):
            parts = []
            for part in subtitle:
                if isinstance(part, dict):
                    parts.append(part.get('text', ''))
                else:
                    parts.append(str(part))
            subtitle = ' '.join(parts)
        if isinstance(subtitle, str) and subtitle:
            m = re.search(r'(\d[\d,]*)', subtitle.replace(',', ''))
            if m:
                try:
                    return int(m.group(1))
                except ValueError:
                    pass
        return 0

    def _resolve_playlist_count(self, playlist_id):
        if not playlist_id or not self.authenticated:
            return 0
        try:
            pl = self.yt.get_playlist(playlist_id, limit=1)
            count = pl.get('trackCount') or pl.get('songCount')
            if count:
                return int(count)
            tracks = pl.get('tracks', [])
            if tracks:
                return len(tracks)
        except Exception:
            pass
        return 0

    def get_home_feed(self):
        self.ensure_auth()
        result = {
            'recent': [],
            'new_releases': [],
            'listen_again': [],
            'trending': [],
            'top_songs': [],
            'playlists': [],
        }
        if not self.yt:
            return result

        try:
            charts = self.yt.get_charts(country='US')
            seen_songs = set()
            for v in charts.get('videos', []):
                pl_id = v.get('playlistId')
                if not pl_id:
                    continue
                try:
                    pl = self.yt.get_playlist(pl_id, limit=12)
                    for t in pl.get('tracks', []):
                        song = self._parse_song(t)
                        sid = song.get('id')
                        if not sid or sid in seen_songs:
                            continue
                        seen_songs.add(sid)
                        if len(result['trending']) < 10:
                            result['trending'].append(song)
                        elif len(result['top_songs']) < 10:
                            result['top_songs'].append(song)
                        else:
                            break
                except Exception:
                    pass
        except Exception as e:
            print(f"Charts error: {e}")

        if self.authenticated:
            try:
                result['recent'] = self.get_history()
            except Exception:
                pass

            try:
                home = self.yt.get_home()
                seen_pl = set()
                resolve_budget = 6
                for section in home:
                    section_title = (section.get('title') or '').lower()
                    items = section.get('contents') or section.get('items') or []
                    for item in items:
                        if item.get('videoId'):
                            song = self._parse_song(item)
                            if 'new' in section_title or 'novedad' in section_title or 'release' in section_title or 'estreno' in section_title:
                                if len(result['new_releases']) < 12:
                                    result['new_releases'].append(song)
                            elif any(k in section_title for k in ('listen', 'escuch', 'again', 'otra vez', 'mix')):
                                if len(result['listen_again']) < 12:
                                    result['listen_again'].append(song)
                            continue

                        pl_id = item.get('playlistId') or item.get('browseId')
                        if not pl_id or pl_id in seen_pl:
                            continue
                        if not (item.get('title') or item.get('thumbnails') or item.get('playlistId')):
                            continue
                        seen_pl.add(pl_id)
                        pl = self._parse_playlist(item)
                        if pl.get('song_count', 0) == 0 and resolve_budget > 0:
                            pl['song_count'] = self._resolve_playlist_count(pl_id)
                            resolve_budget -= 1
                        if len(result['playlists']) < 10:
                            result['playlists'].append(pl)
            except Exception as e:
                print(f"Home feed error: {e}")

        return result

    def get_chart(self):
        feed = self.get_home_feed()
        return {
            'trending': feed.get('trending', []),
            'top_songs': feed.get('top_songs', []),
            'playlists': feed.get('playlists', []),
        }

    def get_stream_url(self, video_id):
        if not video_id:
            return None
        try:
            return f"https://www.youtube.com/watch?v={video_id}"
        except:
            return None

    def rate_song(self, video_id, rating='LIKE'):
        if not self.authenticated:
            return False
        try:
            self.yt.rate_song(video_id, rating)
            return True
        except:
            return False

    def add_to_playlist(self, playlist_id, video_id):
        if not self.authenticated:
            return False
        try:
            self.yt.add_playlist_items(playlist_id, [video_id])
            return True
        except:
            return False

    def remove_from_playlist(self, playlist_id, video_id):
        if not self.authenticated:
            return False
        try:
            playlist = self.yt.get_playlist(playlist_id)
            for t in playlist.get('tracks', []):
                if t.get('videoId') == video_id:
                    self.yt.remove_playlist_items(playlist_id, [t])
                    return True
        except:
            pass
        return False

    def create_playlist(self, title, description=''):
        if not self.authenticated:
            return None
        try:
            pl_id = self.yt.create_playlist(title, description)
            return pl_id
        except:
            return None

    def delete_playlist_remote(self, playlist_id):
        if not self.authenticated:
            return False
        try:
            self.yt.delete_playlist(playlist_id)
            return True
        except:
            return False

    def get_watch_playlist(self, video_id):
        if not self.authenticated:
            return []
        try:
            pl = self.yt.get_watch_playlist(video_id)
            tracks = []
            for t in pl.get('tracks', []):
                tracks.append(self._parse_song(t))
            return tracks
        except Exception:
            return []

    def _parse_duration(self, item):
        raw = item.get('duration')
        if isinstance(raw, (int, float)):
            return int(raw)
        secs = item.get('duration_seconds')
        if isinstance(secs, (int, float)):
            return int(secs)
        length = item.get('lengthSeconds')
        if isinstance(length, (int, float)):
            return int(length)
        if isinstance(raw, str) and ':' in raw:
            parts = raw.split(':')
            try:
                if len(parts) == 2:
                    return int(parts[0]) * 60 + int(parts[1])
                elif len(parts) == 3:
                    return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
            except:
                pass
        return 0

    def _parse_playlist(self, item):
        thumbnails = item.get('thumbnails', [])
        if not thumbnails and 'thumbnail' in item:
            thumbnails = item['thumbnail'].get('thumbnails', []) if isinstance(item['thumbnail'], dict) else []
        pl_id = item.get('playlistId') or item.get('browseId', '')
        return {
            'id': pl_id,
            'title': item.get('title', 'Unknown'),
            'name': item.get('title', 'Unknown'),
            'description': item.get('description', ''),
            'thumbnail': thumbnails[-1].get('url', '') if thumbnails else '',
            'song_count': self._extract_playlist_count(item),
        }

    def _parse_song(self, item):
        thumbnails = item.get('thumbnails', [])
        if not thumbnails and 'thumbnail' in item:
            thumbnails = item['thumbnail'].get('thumbnails', []) if isinstance(item['thumbnail'], dict) else []

        duration = self._parse_duration(item)

        return {
            'id': item.get('videoId', item.get('entityId', '')),
            'title': item.get('title', 'Unknown'),
            'artist': ', '.join([a.get('name', '') for a in item.get('artists', [])]) if item.get('artists') else (item.get('artist', {}).get('name', 'Unknown') if isinstance(item.get('artist'), dict) else item.get('artist', 'Unknown')),
            'album': item.get('album', {}).get('name', '') if isinstance(item.get('album'), dict) else (item.get('album', '')),
            'duration': duration,
            'duration_seconds': duration,
            'thumbnail': thumbnails[-1].get('url', '') if thumbnails else '',
            'youtube_id': item.get('videoId', ''),
            'explicit': item.get('isExplicit', False),
            'feedback': item.get('feedback', {}),
            'setVideoId': item.get('setVideoId', ''),
        }
