# Zonor

Reproductor de YouTube Music de escritorio, sin anuncios, con descargas offline, letras sincronizadas, ecualizador y control total sobre la reproducción. Funciona con o sin cuenta de Google.

## Funciones

**Reproducción**
- Busca y reproduce cualquier canción, playlist o álbum de YouTube Music
- Modo aleatorio, repetición (una / todas), cola de reproducción
- Transiciones suaves (crossfade) configurables entre canciones
- Control de volumen, seek, atajos de teclado (Espacio, S, R, L, Shift+←/→)

**Descargas**
- Descarga canciones con metadatos, carátula incrustada y letras .lrc
- Calidad de audio seleccionable: 64k, 128k, 192k o 320k
- Formato seleccionable: MP3, M4A (AAC), Opus o FLAC
- Descarga masiva de todas las canciones de "Me gusta"
- Las descargas se reproducen desde servidor HTTP local (sin archivos locales bloqueados por CEF)

**Letras**
- Búsqueda automática al reproducir una canción
- Múltiples fuentes con respaldo: syncedlyrics, LRCLib, YouTube (yt-dlp), Spotify
- YouTube Music API si se inició sesión
- Guarda letras sincronizadas (.lrc) junto al audio descargado
- Las letras sin sincronizar se distribuyen automáticamente según la duración

**Ecualizador**
- 9 bandas de frecuencia: 60Hz, 170Hz, 310Hz, 600Hz, 1KHz, 3KHz, 6KHz, 12KHz, 16KHz
- Rango de -12dB a +12dB por banda
- Implementado con Web Audio API (BiquadFilterNode)
- Configuración persistente entre sesiones

**Personalización**
- Tema oscuro por defecto con editor de colores integrado
- Ajusta cada color del interfaz: fondos, texto, acentos, bordes, tarjetas
- Guarda y cambia entre temas creados por ti

**Sin cuenta**
- Navega por Inicio, busca canciones, explora playlists sin iniciar sesión
- Los likes, descargas y biblioteca son locales y persistentes
- Con cuenta: se sincronizan playlists, likes y biblioteca de YouTube Music

## Iniciar sesión (opcional)

Zonor funciona completo sin cuenta. Para funciones adicionales (biblioteca de YT Music, sincronización):

1. Abre Zonor y haz clic en "Iniciar Sesión" (esquina superior derecha)
2. Elige un método:
   - **Rápido (OAuth)**: abre el navegador, inicia sesión en Google, autoriza la app y vuelve automáticamente
   - **Sesión guardada**: si ya iniciaste sesión antes, se reconecta solo
   - **Avanzado**: pega manualmente las cookies o headers desde el navegador
3. Una vez conectado, Zonor sincroniza tus playlists y canciones likeadas

Si no quieres iniciar sesión, Zonor sigue funcionando al 100% con datos locales.

## Instalación

### Requisitos
- Windows 10 u 11
- Python 3.8 o superior (descargar de python.org)

### Paso a paso

1. **Descarga el proyecto** y extrae la carpeta `zonor`

2. **Ejecuta el instalador** haciendo doble clic en `setup.bat`

   Esto hace automáticamente:
   - Verifica que Python esté instalado
   - Instala todas las dependencias (pywebview, ytmusicapi, yt-dlp, Pillow, syncedlyrics)
   - Descarga yt-dlp.exe a la carpeta `bin/`
   - Genera el icono de la aplicación
   - Crea un acceso directo en el Escritorio que apunta a pythonw.exe (sin ventana CMD)
   - Verifica que todo esté correcto

3. **Abre Zonor** desde el acceso directo `Zonor.lnk` en el Escritorio

   O manualmente:
   ```
   pythonw run.py
   ```

4. **Para actualizar**, solo ejecuta `setup.bat` de nuevo

## Atajos de teclado

| Tecla | Acción |
|-------|--------|
| Espacio | Reproducir / Pausar |
| S | Aleatorio |
| R | Repetir |
| L | Me gusta |
| Shift + ← | Anterior |
| Shift + → | Siguiente |

## Notas

- Las descargas se guardan en `%APPDATA%\Zonor\downloads\`
- Los logs de error están en `%APPDATA%\Zonor\error.log`
- El reproductor usa yt-dlp para obtener URLs de streaming sin DRM
- Para mejor compatibilidad de audio, instala FFmpeg en `bin/ffmpeg.exe`
