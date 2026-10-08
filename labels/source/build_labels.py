"""Generate the AminoBio 47 x 22 mm vial labels as pure vector art.

Reads products.csv (name, amount, unit, vial_ml) and writes one SVG (RGB) and
one PDF (CMYK) per row. All text is converted to outlines, so the outputs need
no fonts.

Usage: python3 build_labels.py <fonts-dir> <products.csv> <out-dir>
"""
import csv, os, re, sys
from fontTools.ttLib import TTFont
from fontTools.pens.basePen import BasePen
from fontTools.varLib.instancer import instantiateVariableFont
from reportlab.pdfgen import canvas
from reportlab.lib.colors import CMYKColor

FONTS, CSV_PATH, OUT_DIR = sys.argv[1:4]
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




def fit_cap(s, font, max_cap, max_w, tracking=0.0):
    ops, x0, x1 = text_ops(s, F[font], 1.0, tracking)
    return min(max_cap, max_w / (x1 - x0))


def split_name(name):
    """Ways to break a name into two lines: at '/' if it has one, else at a
    space, else at a hyphen (so 'BPC-157/TB-500' never breaks inside BPC-157)."""
    out = []
    sep = next((c for c in "/ -" if c in name), None)
    if sep is None:
        return out
    for m in re.finditer(re.escape(sep), name):
        i = m.start()
        if m.group() == " ":
            a, b = name[:i], name[i + 1:]
        else:  # keep the slash / hyphen at the end of line one
            a, b = name[:i + 1], name[i + 1:]
        a, b = a.strip(), b.strip()
        if a and b:
            out.append((a, b))
    return out


# ============================== LAYOUT (mm) ==================================
M = 0.5          # border inset
SW = 0.18        # hairline stroke
LX0, LX1 = 1.6, 26.2
LC = (LX0 + LX1) / 2
NAME_W = 21.0                                   # width that sets the GLP3-R reference size
NAME_W_LONG = 22.8                              # long names may run a little wider
NAME_BASE = 10.1                                # baseline of the (last) name line
NAME_MAX_CAP = fit_cap("GLP3-R", "anton", 99, NAME_W, 0.02)   # original GLP3-R size
TWO_LINE_BELOW = 4.6                            # single-line cap smaller than this -> try two lines
NAME_TRACK = 0.02


def draw_name(name):
    cap1 = fit_cap(name, "anton", NAME_MAX_CAP, NAME_W_LONG, NAME_TRACK)
    if cap1 >= TWO_LINE_BELOW or not split_name(name):
        text(name, "anton", cap1, LC, NAME_BASE, "middle", tracking=NAME_TRACK)
        return
    # two lines: same cap height on both, largest that fits width and height
    gap = 0.75
    best = None
    for a, b in split_name(name):
        c = min(fit_cap(a, "anton", 99, NAME_W_LONG, NAME_TRACK),
                fit_cap(b, "anton", 99, NAME_W_LONG, NAME_TRACK),
                (NAME_MAX_CAP - gap) / 2)
        if best is None or c > best[0]:
            best = (c, a, b)
    c, a, b = best
    if c <= cap1:  # splitting doesn't help
        text(name, "anton", cap1, LC, NAME_BASE, "middle", tracking=NAME_TRACK)
        return
    text(a, "anton", c, LC, NAME_BASE - c - gap, "middle", tracking=NAME_TRACK)
    text(b, "anton", c, LC, NAME_BASE, "middle", tracking=NAME_TRACK)


def draw_label(name, amount, unit, vial_ml, batch="373777"):
    items.clear()
    rect(0, 0, W, H, color="w")                      # white background
    rect(M, M, W - 2 * M, H - 2 * M, r=1.0, stroke=SW)  # frame

    # ---- left panel
    dose = f"{amount} {unit}"
    sub = dose if unit == "ML" else f"{dose} · {vial_ml} ML"
    draw_name(name)
    text(sub, "mono", 1.75, LC, 13.0, "middle", tracking=0.02, maxw=14.5)
    pill_w, pill_h = 18.6, 2.5
    rect(LC - pill_w / 2, 14.05, pill_w, pill_h, r=0.55, stroke=SW)
    text(f"{vial_ml}ml MULTIPLE USE VIAL", "mont_sb", 1.0, LC, 14.05 + pill_h / 2 + 0.5, "middle",
         tracking=0.12, maxw=15.6)
    line(LX0 + 0.2, 17.55, LX1 - 0.2, 17.55, SW)
    text("FOR RESEARCH & LABORATORY USE ONLY.", "mont_m", 0.8, LC, 19.6, "middle", tracking=0.35, maxw=22.6)

    # ---- logo column: AMINO (black) + BIO (teal), reading bottom-to-top
    LOGO_BASE = 31.55       # shared baseline (right side) of the rotated wordmark
    LOGO_Y0, LOGO_Y1, GAP = 18.35, 2.0, 0.45
    wa = text_ops("AMINO", F["anton"], 1.0)
    wb = text_ops("BIO", F["arch_bio"], 1.0)
    unit_len = (wa[2] - wa[1]) + (wb[2] - wb[1])
    cap_logo = min(4.3, (LOGO_Y0 - LOGO_Y1 - GAP) / unit_len)
    amino_len, _ = text("AMINO", "anton", cap_logo, LOGO_BASE, LOGO_Y0, "start", rot=90)
    text("BIO", "arch_bio", cap_logo, LOGO_BASE, LOGO_Y0 - amino_len - GAP, "start", rot=90, color="t")
    _, cap_tag = text("PEPTIDE SCIENCE", "arch_cm", 0.6, 29.4, 20.45, "middle", tracking=0.10, maxw=4.5)
    text("ADVANCING", "arch_cm", cap_tag, 29.4, 19.62, "middle", tracking=0.10)
    line(32.35, 2.0, 32.35, 20.6, SW)

    # ---- info panel
    IX0, IX1 = 33.0, 41.3
    IC = (IX0 + IX1) / 2
    rect(IX0, 2.0, IX1 - IX0, 3.6, r=0.45, color="t")
    text(dose, "anton", 2.15, IC, 2.0 + 1.8 + 1.075, "middle", tracking=0.06, maxw=IX1 - IX0 - 1.0)
    rect(IX0, 6.35, IX1 - IX0, 2.3, r=0.45, stroke=SW)
    text("PURITY > 99%", "mont_b", 0.9, IC, 6.35 + 1.15 + 0.45, "middle", tracking=0.04, maxw=7.0)
    # storage + handling block, condensed and anchored to the bottom of the panel
    BOT, LEAD = 20.45, 1.12      # last baseline (aligns with PEPTIDE SCIENCE), line pitch
    cap_s = 0.85
    cap_w = fit_cap("PROTECT FROM LIGHT", "arch_c", cap_s, IX1 - IX0 - 0.1, 0.05)
    lines = [("STORE 2–8 °C", cap_s), ("(36 °F – 46 °F)", cap_s), None,
             ("PROTECT FROM LIGHT", cap_w), ("DO NOT FREEZE", cap_w), ("DO NOT SHAKE", cap_w)]
    y = BOT
    for item in reversed(lines):
        if item is None:          # small break between storage temp and handling notes
            y -= 0.35
            continue
        text(item[0], "arch_c", item[1], IX0 + 0.05, y, tracking=0.05)
        y -= LEAD
    line(IX0, y + LEAD - cap_s - 0.75, IX1, y + LEAD - cap_s - 0.75, SW)

    # ---- barcode + batch number (real Code 128-C)
    BAR_X, BAR_LEN, MOD = 43.45, 2.55, 0.24
    blen = sum(code128c(batch)) * MOD
    btop = (H - blen) / 2
    barcode_vertical(batch, BAR_X, btop, BAR_LEN, MOD)
    text(f"BN {batch}", "arch_c", 0.85, 43.05, btop + blen, "start", rot=90, tracking=0.08)


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
MM = 72 / 25.4


def write_svg(path, title):
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}mm" height="{H}mm" viewBox="0 0 {W} {H}">',
           f"<title>{title.replace('&', '&amp;')}</title>"]
    for kind, ops, c, sw in items:
        if kind == "fill":
            svg.append(f'<path d="{svg_d(ops)}" fill="{RGB[c]}" fill-rule="nonzero"/>')
        else:
            svg.append(f'<path d="{svg_d(ops)}" fill="none" stroke="{RGB[c]}" stroke-width="{sw}" '
                       'stroke-linecap="butt" stroke-linejoin="round"/>')
    svg.append("</svg>")
    open(path, "w").write("\n".join(svg))


def write_pdf(path, title):
    cv = canvas.Canvas(path, pagesize=(W * MM, H * MM), pageCompression=1)
    P = lambda p: (p[0] * MM, (H - p[1]) * MM)
    for kind, ops, c, sw in items:
        pth = cv.beginPath()
        for op in ops:
            if op[0] == "M":
                pth.moveTo(*P(op[1]))
            elif op[0] == "L":
                pth.lineTo(*P(op[1]))
            elif op[0] == "C":
                a, b, d = (P(q) for q in op[1:])
                pth.curveTo(*a, *b, *d)
            else:
                pth.close()
        col = CMYKColor(*CMYK[c])
        if kind == "fill":
            cv.setFillColor(col)
            cv.drawPath(pth, stroke=0, fill=1, fillMode=1)
        else:
            cv.setStrokeColor(col)
            cv.setLineWidth(sw * MM)
            cv.setLineJoin(1)
            cv.drawPath(pth, stroke=1, fill=0)
    cv.showPage()
    cv.save()

    # reportlab always emits an unused Helvetica reference; strip it so the PDF
    # contains no font objects at all (keeps print preflight clean).
    r = PdfReader(path)
    w = PdfWriter()
    w.add_page(r.pages[0])
    pg = w.pages[0]
    data = re.sub(rb"BT\s*/F1[^\n]*?ET\s*", b"", pg.get_contents().get_data(), flags=re.S)
    s = DecodedStreamObject()
    s.set_data(data)
    pg[NameObject("/Contents")] = w._add_object(s.flate_encode())
    if "/Font" in pg["/Resources"]:
        del pg["/Resources"][NameObject("/Font")]
    w.add_metadata({"/Title": title})
    w.write(path)


def slug(name, amount, unit):
    return re.sub(r"[^A-Za-z0-9]+", "_", f"{name}_{amount}{unit}").strip("_")


from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject, DecodedStreamObject

os.makedirs(os.path.join(OUT_DIR, "svg"), exist_ok=True)
os.makedirs(os.path.join(OUT_DIR, "pdf"), exist_ok=True)
with open(CSV_PATH, newline="") as f:
    rows = list(csv.DictReader(f))
for row in rows:
    name, amount = row["name"].strip(), row["amount"].strip()
    unit, vial = row["unit"].strip().upper(), row["vial_ml"].strip()
    draw_label(name, amount, unit, vial)
    base = f"{slug(name, amount, unit)}_label_47x22mm"
    title = f"{name} {amount} {unit} label 47x22mm"
    write_svg(os.path.join(OUT_DIR, "svg", base + ".svg"), title)
    write_pdf(os.path.join(OUT_DIR, "pdf", base + ".pdf"), title)
    print("ok", base)
