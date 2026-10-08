# GLP3-R 10 MG vial label (47 × 22 mm)

Vector rebuild of the original raster label.

| File | Use |
|---|---|
| `GLP3R_10MG_label_47x22mm.pdf` | Print-ready, CMYK, all text converted to outlines (no fonts or images) |
| `GLP3R_10MG_label_47x22mm.svg` | Editable vector (RGB), opens in Illustrator / Inkscape / Affinity |
| `GLP3R_10MG_label_preview.png` | Quick-look preview only |

- Artboard: exactly 47 × 22 mm, no bleed. The rounded frame sits 0.5 mm inside the edge.
- Colours: black = K100 (`#111111`), teal = C80 M0 Y35 K0 in the PDF (`#00ACB0` in the SVG).
- Barcode: real Code 128 encoding `373777`, 0.24 mm module.
- Fonts used before outlining (all free, Google Fonts): Anton, Space Mono, Montserrat, Archivo.

Regenerate: `python3 source/build_label.py <fonts-dir> <output-basename>` (needs `fonttools`, `reportlab`).
