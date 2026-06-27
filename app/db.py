import sqlite3
import os
import json
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
    """)
    try:
        conn.execute("ALTER TABLE songs ADD COLUMN liked INTEGER DEFAULT 0")
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
    conn.execute("""INSERT OR REPLACE INTO songs
        (id, title, artist, album, duration, thumbnail, youtube_id, lyrics, liked, downloaded, file_path)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (song['id'], song['title'], song['artist'], song.get('album', ''),
         song.get('duration', 0), song.get('thumbnail', ''),
         song.get('youtube_id', ''), song.get('lyrics', ''), 1 if liked else 0,
         downloaded, file_path))
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
        ORDER BY h.played_at DESC LIMIT ?""", (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


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
