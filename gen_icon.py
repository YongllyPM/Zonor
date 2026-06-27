import struct, io, os, sys
from PIL import Image

path = sys.argv[1]
d = os.path.dirname(path)
img = Image.open(path)
sizes = [16, 32, 48, 64, 128, 256]

hdr = struct.pack('<HHH', 0, 1, len(sizes))
entries = b''
data = b''
offset = 6 + 16 * len(sizes)

for s in sizes:
    b = io.BytesIO()
    img.resize((s, s), Image.LANCZOS).save(b, format='PNG')
    png = b.getvalue()
    w = 0 if s == 256 else s
    h = 0 if s == 256 else s
    entries += struct.pack('<BBBBHHII', w, h, 0, 0, 1, 0, len(png), offset)
    data += png
    offset += len(png)

with open(os.path.join(d, 'zonor.ico'), 'wb') as f:
    f.write(hdr + entries + data)

print('OK')
