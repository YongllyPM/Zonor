#!/usr/bin/env python3
"""
Zonor - Lanzador
Reproductor de YouTube Music con descargas, letras sincronizadas y temas.
"""
import sys
import os
import traceback
from pathlib import Path

# Ocultar ventana CMD en Windows (fallback para python.exe)
if sys.platform == 'win32':
    try:
        import ctypes
        import time
        for _ in range(10):
            _hwnd = ctypes.windll.kernel32.GetConsoleWindow()
            if _hwnd:
                ctypes.windll.user32.ShowWindow(_hwnd, 0)
                break
            time.sleep(0.01)
    except Exception:
        pass

_LOG = Path(os.environ.get('APPDATA', '')) / 'Zonor' / 'error.log'
_LOG.parent.mkdir(parents=True, exist_ok=True)

import logging
logging.basicConfig(
    filename=str(_LOG),
    level=logging.ERROR,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
)

# Ensure app directory is in path
sys.path.insert(0, str(Path(__file__).parent))

def _log_error(msg):
    with open(str(_LOG), 'a') as f:
        f.write(f"{msg}\n")

try:
    from app.main import main
    main()
except ImportError as e:
    _log_error(f"ImportError: {e}")
    msg = f"{e}\n\nEjecuta el instalador:\n  {Path(__file__).parent / 'setup.bat'}"
    _log_error(msg)
    print(msg)
    sys.exit(1)
except Exception as e:
    tb = traceback.format_exc()
    _log_error(f"Error: {e}\n{tb}")
    print(f"Error: {e}")
    print(tb)
    sys.exit(1)
