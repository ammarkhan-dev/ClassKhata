import os, struct, zlib

BG1, BG2 = (17, 42, 84), (8, 22, 46)
GOLD, DARK = (212, 173, 85), (154, 122, 44)
SHAPES = [
    ("poly", [(166, 236), (346, 236), (346, 326), (256, 372), (166, 326)], DARK),
    ("poly", [(102, 230), (256, 300), (410, 230), (256, 160)], (12, 30, 62)),
    ("poly", [(102, 220), (256, 290), (410, 220), (256, 150)], GOLD),
    ("poly", [(407, 222), (413, 222), (413, 306), (407, 306)], GOLD),
    ("circle", (410, 314, 12), GOLD),
]

def inside(shape, x, y):
    kind, g, _ = shape
    if kind == "circle":
        return (x - g[0]) ** 2 + (y - g[1]) ** 2 <= g[2] ** 2
    sign = 0
    n = len(g)
    for i in range(n):
        x1, y1 = g[i]
        x2, y2 = g[(i + 1) % n]
        c = (x2 - x1) * (y - y1) - (y2 - y1) * (x - x1)
        if c == 0:
            continue
        s = 1 if c > 0 else -1
        if sign == 0:
            sign = s
        elif s != sign:
            return False
    return True

def bbox(shape):
    kind, g, _ = shape
    if kind == "circle":
        return g[0] - g[2], g[1] - g[2], g[0] + g[2], g[1] + g[2]
    xs = [p[0] for p in g]
    ys = [p[1] for p in g]
    return min(xs), min(ys), max(xs), max(ys)

def chunk(t, d):
    c = struct.pack(">I", len(d)) + t + d
    return c + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)

def make(size, path):
    k = 512 / size
    boxes = [bbox(s) for s in SHAPES]
    raw = bytearray()
    for py in range(size):
        t = py / (size - 1)
        bg = tuple(int(BG1[i] + (BG2[i] - BG1[i]) * t) for i in range(3))
        row = bytearray(bg * size)
        dy = (py + 0.5) * k
        for shape, (x0, y0, x1, y1) in zip(SHAPES, boxes):
            if dy < y0 - k or dy > y1 + k:
                continue
            col = shape[2]
            for px in range(max(0, int(x0 / k) - 1), min(size, int(x1 / k) + 2)):
                hit = 0
                for oy in (0.25, 0.75):
                    for ox in (0.25, 0.75):
                        if inside(shape, (px + ox) * k, (py + oy) * k):
                            hit += 1
                if hit:
                    a = hit / 4
                    j = px * 3
                    for i in range(3):
                        row[j + i] = int(row[j + i] + (col[i] - row[j + i]) * a)
        raw += b"\x00" + row
    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
           + chunk(b"IEND", b""))
    open(path, "wb").write(png)

os.makedirs("static", exist_ok=True)
make(192, "static/icon-192.png")
make(512, "static/icon-512.png")
print("ICONS OK")
