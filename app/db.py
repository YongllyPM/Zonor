import sqlite3
import os
import json
import time
from pathlib import Path

DB_DIR = Path(os.environ.get('APPDATA', '')) / 'Zonor'
DB_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DB_DIR / 'library.db'


def get_conn():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS songs (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            artist TEXT NOT NULL,
            album TEXT DEFAULT '',
            duration INTEGER DEFAULT 0,
            thumbnail TEXT DEFAULT '',
            youtube_id TEXT DEFAULT '',
            downloaded INTEGER DEFAULT 0,
            file_path TEXT DEFAULT '',
            added_at INTEGER DEFAULT (unixepoch()),
            lyrics TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS playlists (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            thumbnail TEXT DEFAULT '',
            sync_id TEXT DEFAULT '',
            last_sync INTEGER DEFAULT 0,
            created_at INTEGER DEFAULT (unixepoch())
        );

        CREATE TABLE IF NOT EXISTS playlist_songs (
            playlist_id TEXT NOT NULL,
            song_id TEXT NOT NULL,
            position INTEGER DEFAULT 0,
            added_at INTEGER DEFAULT (unixepoch()),
            PRIMARY KEY (playlist_id, song_id),
            FOREIGN KEY (playlist_id) REFERENCES playlists(id) ON DELETE CASCADE,
            FOREIGN KEY (song_id) REFERENCES songs(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS download_queue (
            id TEXT PRIMARY KEY,
            song_id TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            progress INTEGER DEFAULT 0,
            created_at INTEGER DEFAULT (unixepoch()),
            FOREIGN KEY (song_id) REFERENCES songs(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS cache (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            expires INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS play_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            song_id TEXT NOT NULL,
            played_at INTEGER DEFAULT (unixepoch()),
            FOREIGN KEY (song_id) REFERENCES songs(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS search_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query TEXT NOT NULL,
            searched_at INTEGER DEFAULT (unixepoch())
        );
    """)
    try:
        conn.execute("ALTER TABLE songs ADD COLUMN liked INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE songs ADD COLUMN platform TEXT DEFAULT 'youtube'")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE songs ADD COLUMN spotify_id TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()


def save_setting(key, value):
    conn = get_conn()
    conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
    conn.commit()
    conn.close()


def get_setting(key, default=None):
    conn = get_conn()
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    conn.close()
    return row['value'] if row else default


def save_song(song):
    conn = get_conn()
    existing = conn.execute("SELECT liked, downloaded, file_path FROM songs WHERE id = ?", (song['id'],)).fetchone()
    liked = song.get('liked', existing['liked'] if existing else 0)
    downloaded = existing['downloaded'] if existing else 0
    file_path = existing['file_path'] if existing else ''
    platform = song.get('platform', 'youtube')
    spotify_id = song.get('spotify_id', '')
    conn.execute("""INSERT OR REPLACE INTO songs
        (id, title, artist, album, duration, thumbnail, youtube_id, lyrics, liked, downloaded, file_path, platform, spotify_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (song['id'], song['title'], song['artist'], song.get('album', ''),
         song.get('duration', 0), song.get('thumbnail', ''),
         song.get('youtube_id', ''), song.get('lyrics', ''), 1 if liked else 0,
         downloaded, file_path, platform, spotify_id))
    conn.commit()
    conn.close()


def is_liked(song_id):
    conn = get_conn()
    row = conn.execute("SELECT liked FROM songs WHERE id = ?", (song_id,)).fetchone()
    conn.close()
    return bool(row and row['liked'])


def set_liked(song_id, liked=True):
    conn = get_conn()
    conn.execute("UPDATE songs SET liked = ? WHERE id = ?", (1 if liked else 0, song_id))
    conn.commit()
    conn.close()


def get_liked_songs():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM songs WHERE liked = 1 ORDER BY added_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_song(song_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM songs WHERE id = ?", (song_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_songs():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM songs ORDER BY title").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_downloaded_songs():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM songs WHERE downloaded = 1 ORDER BY title").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_playlist(playlist):
    conn = get_conn()
    conn.execute("""INSERT OR REPLACE INTO playlists
        (id, name, description, thumbnail, sync_id)
        VALUES (?, ?, ?, ?, ?)""",
        (playlist['id'], playlist['name'], playlist.get('description', ''),
         playlist.get('thumbnail', ''), playlist.get('sync_id', '')))
    conn.commit()
    conn.close()


def delete_playlist(playlist_id):
    conn = get_conn()
    conn.execute("DELETE FROM playlist_songs WHERE playlist_id = ?", (playlist_id,))
    conn.execute("DELETE FROM playlists WHERE id = ?", (playlist_id,))
    conn.commit()
    conn.close()


def cleanup_orphan_playlists():
    conn = get_conn()
    deleted = 0
    deleted += conn.execute("""DELETE FROM playlists WHERE id LIKE 'home_%' AND sync_id = ''""").rowcount
    deleted += conn.execute("""DELETE FROM playlists WHERE id NOT LIKE 'local_%' AND sync_id = '' AND id NOT IN (
        SELECT playlist_id FROM playlist_songs
    )""").rowcount
    conn.execute("""DELETE FROM playlist_songs WHERE playlist_id NOT IN (SELECT id FROM playlists)""")
    conn.commit()
    conn.close()
    return deleted


def get_playlists():
    conn = get_conn()
    rows = conn.execute("""SELECT p.*, COUNT(ps.song_id) as song_count
        FROM playlists p LEFT JOIN playlist_songs ps ON p.id = ps.playlist_id
        GROUP BY p.id ORDER BY p.name""").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_playlist_songs(playlist_id):
    conn = get_conn()
    rows = conn.execute("""SELECT s.* FROM songs s
        JOIN playlist_songs ps ON s.id = ps.song_id
        WHERE ps.playlist_id = ? ORDER BY ps.position""", (playlist_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def clear_playlist_songs(playlist_id):
    conn = get_conn()
    conn.execute("DELETE FROM playlist_songs WHERE playlist_id = ?", (playlist_id,))
    conn.commit()
    conn.close()


def add_song_to_playlist(playlist_id, song_id, position=None):
    conn = get_conn()
    if position is None:
        row = conn.execute("SELECT COALESCE(MAX(position), 0) + 1 as pos FROM playlist_songs WHERE playlist_id = ?",
                          (playlist_id,)).fetchone()
        position = row['pos'] if row else 0
    conn.execute("INSERT OR IGNORE INTO playlist_songs (playlist_id, song_id, position) VALUES (?, ?, ?)",
                (playlist_id, song_id, position))
    conn.commit()
    conn.close()


def remove_song_from_playlist(playlist_id, song_id):
    conn = get_conn()
    conn.execute("DELETE FROM playlist_songs WHERE playlist_id = ? AND song_id = ?",
                (playlist_id, song_id))
    conn.commit()
    conn.close()


def add_download(song_id):
    conn = get_conn()
    conn.execute("""INSERT INTO download_queue (id, song_id, status, progress)
        VALUES (?, ?, 'pending', 0)
        ON CONFLICT(id) DO UPDATE SET status='pending', progress=0""",
                (song_id, song_id))
    conn.commit()
    conn.close()


def update_download(song_id, status, progress=0, file_path=''):
    conn = get_conn()
    conn.execute("""UPDATE download_queue SET status = ?, progress = ? WHERE song_id = ?""",
                (status, progress, song_id))
    conn.execute("""UPDATE songs SET downloaded = ?, file_path = ? WHERE id = ?""",
                (1 if status == 'completed' else 0, file_path, song_id))
    conn.commit()
    conn.close()


def get_download_queue():
    conn = get_conn()
    rows = conn.execute("""SELECT d.*, s.title, s.artist FROM download_queue d
        JOIN songs s ON d.song_id = s.id
        WHERE d.status IN ('pending', 'downloading', 'processing', 'failed')
        ORDER BY d.created_at DESC""").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def record_play(song_id):
    conn = get_conn()
    conn.execute("INSERT INTO play_history (song_id) VALUES (?)", (song_id,))
    conn.execute("""DELETE FROM play_history WHERE id NOT IN (
        SELECT id FROM play_history ORDER BY played_at DESC LIMIT 100)""")
    conn.commit()
    conn.close()


def get_recent_plays(limit=15):
    conn = get_conn()
    rows = conn.execute("""SELECT s.* FROM songs s
        INNER JOIN play_history h ON s.id = h.song_id
        GROUP BY s.id
        ORDER BY MAX(h.played_at) DESC, MAX(h.id) DESC LIMIT ?""", (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ===== Search history =====
def add_search_history(query):
    query = (query or '').strip()
    if not query:
        return
    conn = get_conn()
    conn.execute("DELETE FROM search_history WHERE query = ?", (query,))
    conn.execute("INSERT INTO search_history (query) VALUES (?)", (query,))
    conn.execute("""DELETE FROM search_history WHERE id NOT IN (
        SELECT id FROM search_history ORDER BY searched_at DESC LIMIT 12)""")
    conn.commit()
    conn.close()


def get_search_history(limit=12):
    conn = get_conn()
    rows = conn.execute(
        "SELECT query, MAX(searched_at) as searched_at FROM search_history "
        "GROUP BY query ORDER BY searched_at DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def clear_search_history():
    conn = get_conn()
    conn.execute("DELETE FROM search_history")
    conn.commit()
    conn.close()


def cache_get(key):
    conn = get_conn()
    import time
    row = conn.execute("SELECT value, expires FROM cache WHERE key = ?", (key,)).fetchone()
    conn.close()
    if row and (row['expires'] == 0 or row['expires'] > int(time.time())):
        return json.loads(row['value'])
    return None


def clear_all():
    conn = get_conn()
    conn.execute("DELETE FROM songs")
    conn.execute("DELETE FROM playlists")
    conn.execute("DELETE FROM playlist_songs")
    conn.execute("DELETE FROM downloads")
    conn.execute("DELETE FROM recent_plays")
    conn.execute("DELETE FROM cache")
    conn.execute("DELETE FROM settings WHERE key NOT IN ('download_folder', 'color_overrides', 'active_theme', 'volume', 'crossfade', 'skip_silence', 'repeat_mode', 'shuffle_enabled')")
    conn.commit()
    conn.close()


def factory_reset_db():
    conn = get_conn()
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("DELETE FROM songs")
    conn.execute("DELETE FROM playlists")
    conn.execute("DELETE FROM playlist_songs")
    conn.execute("DELETE FROM download_queue")
    conn.execute("DELETE FROM play_history")
    conn.execute("DELETE FROM cache")
    conn.execute("DELETE FROM settings")
    conn.commit()
    conn.close()

def clear_playlist_data():
    conn = get_conn()
    conn.execute("DELETE FROM songs")
    conn.execute("DELETE FROM playlists")
    conn.execute("DELETE FROM playlist_songs")
    conn.execute("DELETE FROM recent_plays")
    conn.commit()
    conn.close()

def cache_clear():
    conn = get_conn()
    conn.execute("DELETE FROM cache")
    conn.commit()
    conn.close()


def cache_set(key, value, ttl=3600):
    conn = get_conn()
    import time
    expires = int(time.time()) + ttl
    conn.execute("INSERT OR REPLACE INTO cache (key, value, expires) VALUES (?, ?, ?)",
                (key, json.dumps(value), expires))
    conn.commit()
    conn.close()


# ===== Export / Import / Backup =====

def export_all_data():
    conn = get_conn()
    data = {
        'version': 1,
        'settings': {r['key']: r['value'] for r in conn.execute("SELECT key, value FROM settings").fetchall()},
        'songs': [dict(r) for r in conn.execute("SELECT * FROM songs").fetchall()],
        'playlists': [dict(r) for r in conn.execute("SELECT * FROM playlists").fetchall()],
        'playlist_songs': [dict(r) for r in conn.execute("SELECT * FROM playlist_songs").fetchall()],
        'download_queue': [dict(r) for r in conn.execute("SELECT * FROM download_queue").fetchall()],
        'play_history': [dict(r) for r in conn.execute("SELECT song_id, played_at FROM play_history").fetchall()],
    }
    conn.close()
    auth_dir = Path(os.environ.get('APPDATA', '')) / 'Zonor'
    data['auth_files'] = {}
    for name in ('headers.json', 'oauth.json', 'oauth_credentials.json'):
        p = auth_dir / name
        if p.exists():
            try:
                data['auth_files'][name] = p.read_text(encoding='utf-8')
            except Exception:
                pass
    return data


def import_all_data(data):
    conn = get_conn()
    conn.execute("PRAGMA foreign_keys=OFF")
    for table in ('playlist_songs', 'play_history', 'download_queue', 'songs', 'playlists', 'settings'):
        conn.execute(f"DELETE FROM {table}")
    conn.execute("DELETE FROM sqlite_sequence WHERE name='play_history'")

    for key, value in (data.get('settings') or {}).items():
        if key in ('download_folder',):
            continue
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))

    for s in data.get('songs') or []:
        conn.execute("""INSERT OR REPLACE INTO songs
            (id, title, artist, album, duration, thumbnail, youtube_id, lyrics, liked, downloaded, file_path, platform, spotify_id, added_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (s.get('id', ''), s.get('title', ''), s.get('artist', ''),
             s.get('album', ''), s.get('duration', 0), s.get('thumbnail', ''),
             s.get('youtube_id', ''), s.get('lyrics', ''),
             1 if s.get('liked') else 0, 1 if s.get('downloaded') else 0,
             s.get('file_path', ''), s.get('platform', 'youtube'),
             s.get('spotify_id', ''), s.get('added_at', int(time.time()))))

    for p in data.get('playlists') or []:
        conn.execute("""INSERT OR REPLACE INTO playlists
            (id, name, description, thumbnail, sync_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (p.get('id', ''), p.get('name', ''), p.get('description', ''),
             p.get('thumbnail', ''), p.get('sync_id', ''), p.get('created_at', int(time.time()))))

    for ps in data.get('playlist_songs') or []:
        conn.execute("""INSERT OR REPLACE INTO playlist_songs (playlist_id, song_id, position, added_at)
            VALUES (?, ?, ?, ?)""",
            (ps.get('playlist_id', ''), ps.get('song_id', ''), ps.get('position', 0), ps.get('added_at', int(time.time()))))

    for d in data.get('download_queue') or []:
        conn.execute("""INSERT OR REPLACE INTO download_queue (id, song_id, status, progress, created_at)
            VALUES (?, ?, ?, ?, ?)""",
            (d.get('id', d.get('song_id', '')), d.get('song_id', ''), d.get('status', 'pending'),
             d.get('progress', 0), d.get('created_at', int(time.time()))))

    for h in data.get('play_history') or []:
        conn.execute("INSERT INTO play_history (song_id, played_at) VALUES (?, ?)",
                     (h.get('song_id', ''), h.get('played_at', int(time.time()))))

    conn.commit()
    conn.close()

    auth_dir = Path(os.environ.get('APPDATA', '')) / 'Zonor'
    auth_dir.mkdir(parents=True, exist_ok=True)
    for name, content in (data.get('auth_files') or {}).items():
        if name not in ('headers.json', 'oauth.json', 'oauth_credentials.json'):
            continue
        try:
            (auth_dir / name).write_text(content, encoding='utf-8')
        except Exception:
            pass
    return True
