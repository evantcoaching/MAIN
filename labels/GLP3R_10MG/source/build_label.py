"""Rebuild the GLP3-R 10MG label as pure vector art at 47 x 22 mm.

All text is converted to outlines, so the output needs no fonts.
Outputs: SVG (RGB) and PDF (CMYK) with identical geometry.
"""
import sys, os
from fontTools.ttLib import TTFont
from fontTools.pens.basePen import BasePen
from fontTools.varLib.instancer import instantiateVariableFont
from reportlab.pdfgen import canvas
from reportlab.lib.colors import CMYKColor

FONTS = sys.argv[1]
OUT = sys.argv[2]
W, H = 47.0, 22.0  # mm

TEAL_RGB = "#00ACB0"
TEAL_CMYK = (0.80, 0.0, 0.35, 0.0)
BLACK_RGB = "#111111"
BLACK_CMYK = (0, 0, 0, 1.0)


def load(name, **axes):
    f = TTFont(os.path.join(FONTS, name))
    if axes:
        f = instantiateVariableFont(f, axes)
    return f


F = {
    "anton": load("Anton-Regular.ttf"),
    "mono": load("SpaceMono-Regular.ttf"),
    "mont_sb": load("Montserrat%5Bwght%5D.ttf", wght=600),
    "mont_b": load("Montserrat%5Bwght%5D.ttf", wght=700),
    "mont_m": load("Montserrat%5Bwght%5D.ttf", wght=500),
    "arch_bio": load("Archivo%5Bwdth,wght%5D.ttf", wght=900, wdth=100),
    "arch_c": load("Archivo%5Bwdth,wght%5D.ttf", wght=400, wdth=88),
    "arch_cm": load("Archivo%5Bwdth,wght%5D.ttf", wght=600, wdth=88),
}


class CubicPen(BasePen):
    """Records a path as moveTo/lineTo/curveTo(cubic)/close in font units."""

    def __init__(self, gs):
        super().__init__(gs)
        self.ops = []

    def _moveTo(self, p):
        self.ops.append(("M", p))

    def _lineTo(self, p):
        self.ops.append(("L", p))

    def _curveToOne(self, a, b, c):
        self.ops.append(("C", a, b, c))

    def _closePath(self):
        self.ops.append(("Z",))

    _endPath = _closePath


# ---- primitive store: everything is a filled path or stroked path in mm, y-down
items = []  # (kind, ops, color, stroke_width)


def xf(ops, fn):
    out = []
    for op in ops:
        out.append((op[0],) + tuple(fn(p) for p in op[1:]))
    return out


def cap_height(font):
    if True:  # measure the real 'H' rather than trusting OS/2
        gs = font.getGlyphSet()
        pen = CubicPen(gs)
        gs["H"].draw(pen)
        ch = max(p[1] for op in pen.ops for p in op[1:])
    return ch


def text_ops(s, font, cap_mm, tracking=0.0):
    """Return (ops in mm with baseline at y=0, y-down, x starting at 0, width)."""
    upm = font["head"].unitsPerEm
    scale = cap_mm / cap_height(font)
    cmap = font.getBestCmap()
    gs = font.getGlyphSet()
    hmtx = font["hmtx"]
    x = 0.0
    ops = []
    n = len(s)
    for i, ch in enumerate(s):
        g = cmap[ord(ch)]
        pen = CubicPen(gs)
        gs[g].draw(pen)
        ox = x
        ops += xf(pen.ops, lambda p, ox=ox: (ox + p[0] * scale, -p[1] * scale))
        x += hmtx[g][0] * scale
        if i < n - 1:
            x += tracking * cap_mm
    # trim to visible ink for accurate centering
    xs = [p[0] for op in ops for p in op[1:]]
    return ops, (min(xs) if xs else 0), (max(xs) if xs else x)


def text(s, font, cap, x, y, anchor="start", tracking=0.0, color="k", rot=0, width=None, maxw=None):
    """Place text; (x, y) = baseline anchor point. rot=90 reads bottom-to-top.
    If width is given, cap height is scaled so ink width equals width."""
    f = F[font]
    ops, x0, x1 = text_ops(s, f, cap, tracking)
    if width or (maxw and x1 - x0 > maxw):
        k = (width or maxw) / (x1 - x0)
        cap *= k
        ops, x0, x1 = text_ops(s, f, cap, tracking)
    w = x1 - x0
    dx = {"start": -x0, "middle": -x0 - w / 2, "end": -x1}[anchor]
    if rot == 0:
        fn = lambda p: (x + p[0] + dx, y + p[1])
    else:  # rotate -90 (reads upward): local (u, v) -> (x + v, y - u)
        fn = lambda p: (x + p[1], y - (p[0] + dx))
    items.append(("fill", xf(ops, fn), color, 0))
    return w, cap


def rect(x, y, w, h, r=0.0, color="k", stroke=None):
    k = 0.5523 * r
    if r == 0:
        ops = [("M", (x, y)), ("L", (x + w, y)), ("L", (x + w, y + h)), ("L", (x, y + h)), ("Z",)]
    else:
        ops = [
            ("M", (x + r, y)), ("L", (x + w - r, y)),
            ("C", (x + w - r + k, y), (x + w, y + r - k), (x + w, y + r)),
            ("L", (x + w, y + h - r)),
            ("C", (x + w, y + h - r + k), (x + w - r + k, y + h), (x + w - r, y + h)),
            ("L", (x + r, y + h)),
            ("C", (x + r - k, y + h), (x, y + h - r + k), (x, y + h - r)),
            ("L", (x, y + r)),
            ("C", (x, y + r - k), (x + r - k, y), (x + r, y)),
            ("Z",),
        ]
    if stroke:
        items.append(("stroke", ops, color, stroke))
    else:
        items.append(("fill", ops, color, 0))


def line(x1, y1, x2, y2, sw, color="k"):
    items.append(("stroke", [("M", (x1, y1)), ("L", (x2, y2))], color, sw))


# ---- Code 128 (set C) -------------------------------------------------------
C128 = ["212222","222122","222221","121223","121322","131222","122213","122312","132212","221213",
"221312","231212","112232","122132","122231","113222","123122","123221","223211","221132",
"221231","213212","223112","312131","311222","321122","321221","312212","322112","322211",
"212123","212321","232121","111323","131123","131321","112313","132113","132311","211313",
"231113","231311","112133","112331","132131","113123","113321","133121","313121","211331",
"231131","213113","213311","213131","311123","311321","331121","312113","312311","332111",
"314111","221411","431111","111224","111422","121124","121421","141122","141221","112214",
"112412","122114","122411","142112","142211","241211","221114","413111","241112","134111",
"111242","121142","121241","114212","124112","124211","411212","421112","421211","212141",
"214121","412121","111143","111341","131141","114113","114311","411113","411311","113141",
"114131","311141","411131","211412","211214","211232","2331112"]


def code128c(digits):
    vals = [105] + [int(digits[i:i + 2]) for i in range(0, len(digits), 2)]
    chk = (vals[0] + sum(v * i for i, v in enumerate(vals[1:], 1))) % 103
    pat = "".join(C128[v] for v in vals + [chk]) + C128[106]
    return [int(c) for c in pat]  # alternating bar/space widths in modules


def barcode_vertical(digits, x, y_top, bar_len, module):
    """Bars run horizontally, code reads top->bottom (rotated 90deg)."""
    yy = y_top
    for i, wmod in enumerate(code128c(digits)):
        if i % 2 == 0:
            rect(x, yy, bar_len, wmod * module)
        yy += wmod * module
    return yy - y_top


# ============================== LAYOUT (mm) ==================================
M = 0.5          # border inset
SW = 0.18        # hairline stroke
rect(0, 0, W, H, color="w")                      # white background
rect(M, M, W - 2 * M, H - 2 * M, r=1.0, stroke=SW)  # frame

# ---- left panel: x 1.5 .. 26.3, centre 13.9
LX0, LX1 = 1.6, 26.2
LC = (LX0 + LX1) / 2
text("GLP3-R", "anton", 7.0, LC, 10.1, "middle", tracking=0.02, width=21.0)
text("10 MG · 3 ML", "mono", 1.75, LC, 13.0, "middle", tracking=0.02, maxw=14.5)
pill_w, pill_h = 18.6, 2.5
rect(LC - pill_w / 2, 14.05, pill_w, pill_h, r=0.55, stroke=SW)
text("3ml MULTIPLE USE VIAL", "mont_sb", 1.0, LC, 14.05 + pill_h / 2 + 0.5, "middle", tracking=0.12, maxw=15.6)
line(LX0 + 0.2, 17.55, LX1 - 0.2, 17.55, SW)
text("FOR RESEARCH & LABORATORY USE ONLY.", "mont_m", 0.8, LC, 19.6, "middle", tracking=0.35, maxw=22.6)

# ---- logo column: AMINO (black) + BIO (teal), reading bottom-to-top
LOGO_BASE = 31.55       # shared baseline (right side) of the rotated wordmark
# size both words to the same cap height so AMINO+gap+BIO spans the column
LOGO_Y0, LOGO_Y1, GAP = 18.35, 2.0, 0.45
wa = text_ops("AMINO", F["anton"], 1.0)
wb = text_ops("BIO", F["arch_bio"], 1.0)
unit = (wa[2] - wa[1]) + (wb[2] - wb[1])
cap_logo = min(4.3, (LOGO_Y0 - LOGO_Y1 - GAP) / unit)
amino_len, _ = text("AMINO", "anton", cap_logo, LOGO_BASE, LOGO_Y0, "start", rot=90)
text("BIO", "arch_bio", cap_logo, LOGO_BASE, LOGO_Y0 - amino_len - GAP, "start", rot=90, color="t")
_, cap_tag = text("PEPTIDE SCIENCE", "arch_cm", 0.6, 29.4, 20.45, "middle", tracking=0.10, maxw=4.5)
text("ADVANCING", "arch_cm", cap_tag, 29.4, 19.62, "middle", tracking=0.10)
line(32.35, 2.0, 32.35, 20.6, SW)

# ---- info panel: x 33.0 .. 41.4
IX0, IX1 = 33.0, 41.3
IC = (IX0 + IX1) / 2
rect(IX0, 2.0, IX1 - IX0, 3.6, r=0.45, color="t")
text("10 MG", "anton", 2.15, IC, 2.0 + 1.8 + 1.075, "middle", tracking=0.06)
rect(IX0, 6.35, IX1 - IX0, 2.3, r=0.45, stroke=SW)
text("PURITY > 99%", "mont_b", 0.9, IC, 6.35 + 1.15 + 0.45, "middle", tracking=0.04, maxw=7.0)
line(IX0, 9.45, IX1, 9.45, SW)
text("STORE 2–8 °C", "arch_c", 0.95, IX0 + 0.05, 11.2, tracking=0.04)
text("(36 °F – 46 °F)", "arch_c", 0.95, IX0 + 0.05, 12.75, tracking=0.04)
line(IX0, 14.0, IX1, 14.0, SW)
_, cap_w = text("PROTECT FROM LIGHT", "arch_c", 0.75, IX0 + 0.05, 15.6, tracking=0.05, maxw=IX1 - IX0 - 0.1)
for i, s in enumerate(["DO NOT FREEZE", "DO NOT SHAKE"], 1):
    text(s, "arch_c", cap_w, IX0 + 0.05, 15.6 + i * 1.45, tracking=0.05)

# ---- barcode + batch number (real Code 128-C encoding "373777")
BAR_X, BAR_LEN, MOD = 43.45, 2.55, 0.24
blen = sum(code128c("373777")) * MOD
btop = (H - blen) / 2
barcode_vertical("373777", BAR_X, btop, BAR_LEN, MOD)
text("BN 373777", "arch_c", 0.85, 43.05, btop + blen, "start", rot=90, tracking=0.08)

# ================================ OUTPUT =====================================
def svg_d(ops):
    s = []
    for op in ops:
        if op[0] == "Z":
            s.append("Z")
        else:
            s.append(op[0] + " ".join(f"{p[0]:.4f} {p[1]:.4f}" for p in op[1:]))
    return "".join(s)


RGB = {"k": BLACK_RGB, "t": TEAL_RGB, "w": "#FFFFFF"}
CMYK = {"k": BLACK_CMYK, "t": TEAL_CMYK, "w": (0, 0, 0, 0)}

svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}mm" height="{H}mm" viewBox="0 0 {W} {H}">',
       "<title>GLP3-R 10 MG label 47x22mm</title>"]
for kind, ops, c, sw in items:
    if kind == "fill":
        svg.append(f'<path d="{svg_d(ops)}" fill="{RGB[c]}" fill-rule="nonzero"/>')
    else:
        svg.append(f'<path d="{svg_d(ops)}" fill="none" stroke="{RGB[c]}" stroke-width="{sw}" stroke-linecap="butt" stroke-linejoin="round"/>')
svg.append("</svg>")
open(OUT + ".svg", "w").write("\n".join(svg))

MM = 72 / 25.4
cv = canvas.Canvas(OUT + ".pdf", pagesize=(W * MM, H * MM), pageCompression=1)
cv.setTitle("GLP3-R 10 MG label 47x22mm")
cv.setAuthor("")
cv.setCreator("vector rebuild")
P = lambda p: (p[0] * MM, (H - p[1]) * MM)
for kind, ops, c, sw in items:
    path = cv.beginPath()
    for op in ops:
        if op[0] == "M":
            path.moveTo(*P(op[1]))
        elif op[0] == "L":
            path.lineTo(*P(op[1]))
        elif op[0] == "C":
            a, b, d = (P(q) for q in op[1:])
            path.curveTo(*a, *b, *d)
        else:
            path.close()
    col = CMYKColor(*CMYK[c])
    if kind == "fill":
        cv.setFillColor(col)
        cv.drawPath(path, stroke=0, fill=1, fillMode=1)
    else:
        cv.setStrokeColor(col)
        cv.setLineWidth(sw * MM)
        cv.setLineJoin(1)
        cv.drawPath(path, stroke=1, fill=0)
cv.showPage()
cv.save()
print("ok", len(items), "objects")
