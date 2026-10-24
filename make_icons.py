import math, os, struct, zlib

NAVY, GOLD = (11, 31, 63), (184, 145, 58)

def clamp(v):
    return 0.0 if v < 0 else 1.0 if v > 1 else v

def make(size, path):
    cx = cy = size / 2
    R, r = size * 0.31, size * 0.20
    rows = []
    for y in range(size):
        row = bytearray([0])
        for x in range(size):
            dx, dy = x + 0.5 - cx, y + 0.5 - cy
            d = math.hypot(dx, dy)
            deg = abs(math.degrees(math.atan2(dy, dx)))
            a = min(clamp(R - d + 0.5), clamp(d - r + 0.5),
                    clamp((deg - 40) * math.pi / 180 * d + 0.5))
            row += bytes(int(NAVY[i] + (GOLD[i] - NAVY[i]) * a) for i in range(3))
        rows.append(bytes(row))
    def chunk(t, d):
        c = struct.pack(">I", len(d)) + t + d
        return c + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(b"".join(rows), 9))
           + chunk(b"IEND", b""))
    open(path, "wb").write(png)

os.makedirs("static", exist_ok=True)
make(192, "static/icon-192.png")
make(512, "static/icon-512.png")
print("ICONS OK")
