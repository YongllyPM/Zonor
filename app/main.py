import os
import sys
import json
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import webview
from .api import API

api = None


class JSAPI:
    def __init__(self, api_instance):
        self._api = api_instance

    def getHome(self):
        return self._api.get_home()

    def prefetchHome(self):
        return self._api.prefetch_home()

    def getRemotePlaylistSongs(self, playlist_id):
        return self._api.get_remote_playlist_songs(playlist_id)

    def getAuthStatus(self):
        return self._api.get_auth_status()

    def loginWithHeaders(self, headers):
        return self._api.login_with_headers(headers)

    def loginFromBrowser(self):
        return self._api.login_from_browser()

    def loginOAuth(self):
        return self._api.login_oauth()

    def loginAuto(self):
        return self._api.login_auto()

    def loginWithCookie(self, cookie):
        return self._api.login_with_cookie(cookie)

    def logout(self):
        self._api.logout()

    def search(self, query, limit=20):
        return self._api.search(query, limit)

    def searchSuggestions(self, query):
        return self._api.search_suggestions(query)

    def getLibrary(self):
        return self._api.get_library()

    def getLikedSongs(self):
        return self._api.get_liked_songs()

    def getPlaylists(self):
        return self._api.get_playlists()

    def getPlaylistSongs(self, playlist_id):
        return self._api.get_playlist_songs(playlist_id)

    def createPlaylist(self, name, description=''):
        return self._api.create_playlist(name, description)

    def deletePlaylist(self, playlist_id):
        self._api.delete_playlist(playlist_id)

    def addToPlaylist(self, playlist_id, song_id, video_id=''):
        self._api.add_to_playlist(playlist_id, song_id, video_id or None)

    def removeFromPlaylist(self, playlist_id, song_id):
        self._api.remove_from_playlist(playlist_id, song_id)

    def playSong(self, song_id):
        return self._api.play_song(song_id)

    def playPlaylist(self, playlist_id, start_index=0):
        return self._api.play_playlist(playlist_id, start_index)

    def togglePlay(self):
        self._api.toggle_play()

    def seek(self, position):
        self._api.seek(position)

    def setVolume(self, volume):
        self._api.set_volume(volume)

    def getPlayerStatus(self):
        return self._api.get_player_status()

    def nextSong(self):
        return self._api.next_song()

    def prevSong(self):
        return self._api.prev_song()

    def getQueue(self):
        return self._api.get_queue()

    def queueNext(self):
        return self._api.queue_next()

    def queuePrev(self):
        return self._api.queue_prev()

    def getStreamUrl(self, song_id):
        return self._api.get_stream_url(song_id)

    def refreshStreamUrl(self, song_id):
        return self._api.refresh_stream_url(song_id)

    def isLiked(self, song_id):
        return self._api.is_liked(song_id)

    def toggleLike(self, song_id):
        return self._api.toggle_like(song_id)

    def downloadSong(self, song_id):
        return self._api.download_song(song_id)

    def getDownloads(self):
        return self._api.get_downloads()

    def getDownloadedSongs(self):
        return self._api.get_downloaded_songs()

    def deleteDownload(self, song_id):
        self._api.delete_download(song_id)

    def cancelDownload(self, song_id):
        self._api.cancel_download(song_id)

    def getLyrics(self, song_id=None):
        return self._api.get_lyrics(song_id)

    def startSync(self):
        self._api.start_sync()

    def stopSync(self):
        self._api.stop_sync()

    def forceSync(self):
        return self._api.force_sync()

    def fixSync(self):
        return self._api.fix_sync()

    def getAllSongs(self):
        return self._api.get_all_songs()

    def getSong(self, song_id):
        return self._api.get_song(song_id)

    def getThemes(self):
        return self._api.get_themes()

    def saveTheme(self, theme_json):
        return self._api.save_theme(theme_json)

    def deleteTheme(self, name):
        return self._api.delete_theme(name)

    def getCurrentTheme(self):
        return self._api.get_current_theme()

    def setTheme(self, name):
        return self._api.set_theme(name)

    def getSettings(self):
        return self._api.get_settings()

    def saveSettings(self, settings_json):
        self._api.save_settings(settings_json)

    def downloadAllLiked(self):
        return self._api.download_all_liked()


def main():
    global api

    api = API()
    js_api = JSAPI(api)

    web_root = Path(__file__).parent.parent / 'web'
    index_html = str(web_root / 'index.html')

    window = webview.create_window(
        'Zonor',
        index_html,
        js_api=js_api,
        width=1200,
        height=800,
        min_size=(900, 600),
        text_select=True,
        resizable=True,
    )
    api.set_window(window)

    try:
        window.events.loaded += lambda: api.prefetch_home()
    except Exception:
        api.prefetch_home()

    webview.start(debug=False)


if __name__ == '__main__':
    main()
