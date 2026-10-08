# AminoBio vial labels (47 × 22 mm)

Vector labels generated from one template. `all_labels_preview.png` shows every label.

| Folder | Use |
|---|---|
| `svg/` | Editable vector (RGB), opens in Illustrator / Inkscape / Affinity / Figma |
| `pdf/` | Print-ready, CMYK, all text converted to outlines (no fonts or images) |

- Artboard: exactly 47 × 22 mm, no bleed. Rounded frame sits 0.5 mm inside the edge.
- Colours: black = K100 (`#111111`), teal = C80 M0 Y35 K0 in the PDF (`#00ACB0` in the SVG).
- Barcode: real Code 128 encoding the batch number (`373777` on all labels for now), 0.24 mm module.
- Long product names are fitted automatically (wider, or split onto two lines at `/` or a space).

## Adding or changing a product

Edit `products.csv` (`name, amount, unit, vial_ml, components`) and regenerate.
`components` is optional: blend contents separated by `/` (e.g. `10MG / 10MG`), printed under the name.
For an `A/B` name with one component per part, each sits directly under its part.


```
python3 source/build_labels.py <fonts-dir> products.csv .
```

Needs `fonttools`, `reportlab`, `pypdf`, and these free Google Fonts in `<fonts-dir>`:
`Anton-Regular.ttf`, `SpaceMono-Regular.ttf`, `Montserrat[wght].ttf`, `Archivo[wdth,wght].ttf`
(file names as downloaded from github.com/google/fonts, with `[`/`]` URL-encoded).
