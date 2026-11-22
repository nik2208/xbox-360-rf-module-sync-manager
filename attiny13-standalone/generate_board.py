#!/usr/bin/env python3
"""
Genera la basetta 3D in PET-G a rilievo (per nastro adesivo di rame)
per il controller di sync Xbox 360 Fat RF con ATtiny13A-SSU + MCP1700T-3302E/TT.

Schema di riferimento: https://agarmash.com/xbox-360-controller-receiver/schematic.png
Firmware di riferimento: https://github.com/agarmash/Xreceiver (Xreceiver13.hex)

Uso:
  ~/Devel/github/360/tools/venv/bin/python generate_board.py
"""
import math
import os
import sys
import numpy as np
from shapely.geometry import Point, LineString, Polygon, box
from shapely.ops import unary_union
import trimesh
from PIL import Image, ImageDraw, ImageFont

# Riutilizziamo step_prism.py da ~/Devel/github/360/esp32-360/scripts
sys.path.insert(0, os.path.expanduser("~/Devel/github/360/esp32-360/scripts"))
from step_prism import prisms_step

# ==============================================================================
# PARAMETRI FISICI (mm) — stessa convenzione PET-G + nastro di rame di diy-360
# ==============================================================================
BOARD_W = 48.0
BOARD_H = 29.0
CORNER_R = 2.0
BASE_THICK = 1.50      # plastica di base (10 strati da 0.15 mm)
RELIEF_H = 0.45        # rilievo piste/piazzole (3 strati da 0.15 mm — guida bene il cutter)
HOLE_CLEAR_R = 0.08    # piccolo margine sul foro nel rilievo

# Diametri fori e piazzole
DRILL_TH = 1.0         # fori passanti per R1-R3, C1-C2 (ripassare con punta 0.9-1.0)
PAD_TH_R = 1.55        # raggio piazzola TH (diametro 3.1 mm -> anello 1.05 mm)
DRILL_WIRE = 1.2       # fori piazzole fili / ISP
PAD_WIRE_R = 1.85      # raggio piazzola fili (diametro 3.7 mm)

# ==============================================================================
# COORDINATE COMPONENTI (vista lato RAME / RILIEVO, origine in alto a sinistra)
# +X verso destra, +Y verso il basso
# ==============================================================================
# U1: ATtiny13A-SSU (SOIC-8 stretto, 3.9 mm, passo 1.27 mm)
U1_X, U1_Y = 25.0, 15.5
U1_DX = 2.7            # distanza centro -> centro pad (5.4 mm tra colonne)
U1_PITCH = 1.27
U1_PINS = {
    1: (U1_X - U1_DX, U1_Y - 1.5 * U1_PITCH),  # RST  (PB5)
    2: (U1_X - U1_DX, U1_Y - 0.5 * U1_PITCH),  # NC
    3: (U1_X - U1_DX, U1_Y + 0.5 * U1_PITCH),  # NC
    4: (U1_X - U1_DX, U1_Y + 1.5 * U1_PITCH),  # GND
    5: (U1_X + U1_DX, U1_Y + 1.5 * U1_PITCH),  # CLK  (PB0 / MOSI)
    6: (U1_X + U1_DX, U1_Y + 0.5 * U1_PITCH),  # SYNC (PB1 / MISO)
    7: (U1_X + U1_DX, U1_Y - 0.5 * U1_PITCH),  # DATA (PB2 / SCK)
    8: (U1_X + U1_DX, U1_Y - 1.5 * U1_PITCH),  # 3V3  (VCC)
}

# U2: MCP1700T-3302E/TT (SOT-23-3, ruotato 90° CCW: pin 3 a SX, pin 2 in alto-DX, pin 1 in basso-DX)
U2_X, U2_Y = 11.5, 15.5
U2_PINS = {
    3: (U2_X - 1.05, U2_Y),         # VIN  (5V)  - lato singolo a sinistra
    2: (U2_X + 1.05, U2_Y - 0.95),  # VOUT (3V3) - in alto a destra
    1: (U2_X + 1.05, U2_Y + 0.95),  # GND        - in basso a destra
}

# Condensatori 1 uF a foro passante (passo 5.08 mm)
C1_POS = (7.2, 15.5)   # 5V
C1_NEG = (7.2, 20.58)  # GND

C2_POS = (15.6, 11.42) # 3V3
C2_NEG = (15.6, 16.50) # GND

# Resistenze 10 kOhm 1/4W a foro passante (montate sul retro liscio)
R1_TOP = (19.6, 3.8)   # 3V3 (passo 9.8 mm -> perfetto per 1/4W)
R1_BOT = (19.6, 13.6)  # RST

R2_TOP = (34.4, 4.5)   # 3V3 (passo 12.7 mm)
R2_BOT = (34.4, 17.2)  # SYNC

R3_TOP = (39.2, 4.5)   # 3V3 (passo 18.0 mm)
R3_BOT = (39.2, 22.5)  # CLK

# Piazzole fili / ISP
PADS_WIRE = {
    "3V3":  (3.8, 4.5),    # 3.3V (out MCP1700 o ingresso 3.3V diretto) + ISP VCC
    "5V":   (3.8, 15.5),   # 5V USB (solo se si monta MCP1700)
    "GND":  (3.8, 24.5),   # GND + ISP GND
    "RST":  (24.5, 9.0),   # ISP RESET
    "DATA": (44.0, 11.2),  # RF pin 6 / ISP SCK
    "SYNC": (44.0, 17.2),  # RF pin 5 (tasto centrale) / ISP MISO
    "CLK":  (44.0, 22.5),  # RF pin 7 / ISP MOSI
}

# ==============================================================================
# COSTRUZIONE GEOMETRIE RAME PER OGNI RETE
# ==============================================================================
def rect_pad(cx, cy, w, h):
    return box(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)

def round_pad(cx, cy, r):
    return Point(cx, cy).buffer(r, resolution=24)

def trace(pts, width):
    return LineString(pts).buffer(width / 2.0, cap_style=1, join_style=1, resolution=16)

def build_nets():
    nets = {}

    # 1. 5V: pad 5V -> C1+ -> U2 pin 3 (VIN)
    nets["5V"] = unary_union([
        round_pad(*PADS_WIRE["5V"], PAD_WIRE_R),
        round_pad(*C1_POS, PAD_TH_R),
        rect_pad(*U2_PINS[3], 1.3, 0.9),
        trace([PADS_WIRE["5V"], C1_POS, U2_PINS[3]], 1.6),
    ])

    # 2. 3V3: pad 3V3 -> rail alto -> R1_TOP, R2_TOP, R3_TOP -> C2+ -> U2 pin 2 (dissipatore) -> U1 pin 8
    u2_vout = U2_PINS[2]
    u1_vcc = U1_PINS[8]
    nets["3V3"] = unary_union([
        round_pad(*PADS_WIRE["3V3"], PAD_WIRE_R),
        round_pad(*C2_POS, PAD_TH_R),
        round_pad(*R1_TOP, PAD_TH_R),
        round_pad(*R2_TOP, PAD_TH_R),
        round_pad(*R3_TOP, PAD_TH_R),
        rect_pad(*u2_vout, 1.3, 0.85),
        rect_pad(*u1_vcc, 2.0, 0.65),
        # Piccolo piano dissipatore sul lato VOUT dell'MCP1700 (sopra U2 pin 2 e attorno a C2+)
        box(12.2, 9.8, 16.6, 14.2),
        trace([u2_vout, (13.4, 14.2)], 0.85),
        # Rail 3V3 in alto (largo 2.0 mm)
        trace([PADS_WIRE["3V3"], (15.6, 4.5), R1_TOP, (28.7, 4.5), R2_TOP, R3_TOP], 2.0),
        # Salita da C2+ al rail 3V3
        trace([C2_POS, (15.6, 4.5)], 2.0),
        # Discesa dal rail 3V3 a U1 pin 8 (VCC) - dritto in verticale a x=28.7
        trace([(28.7, 4.5), (28.7, u1_vcc[1]), u1_vcc], 0.65),
        trace([(28.7, 4.5), (28.7, 12.2)], 1.6),
    ])

    # 3. GND: pad GND -> rail basso -> C1-, C2-, U2 pin 1 (dissipatore), U1 pin 4
    u2_gnd = U2_PINS[1]
    u1_gnd = U1_PINS[4]
    nets["GND"] = unary_union([
        round_pad(*PADS_WIRE["GND"], PAD_WIRE_R),
        round_pad(*C1_NEG, PAD_TH_R),
        round_pad(*C2_NEG, PAD_TH_R),
        rect_pad(*u2_gnd, 1.3, 0.85),
        rect_pad(*u1_gnd, 2.0, 0.70),
        # Piano dissipatore GND ampio sotto U2 pin 1 e C2-
        box(12.0, 17.2, 16.8, 25.4),
        trace([u2_gnd, (13.4, 17.2)], 0.85),
        # Rail GND in basso (largo 2.4 mm)
        trace([PADS_WIRE["GND"], (7.2, 24.5), (15.6, 24.5), (22.3, 24.5)], 2.4),
        trace([C1_NEG, (7.2, 24.5)], 2.0),
        # Salita a U1 pin 4 (GND)
        trace([(22.3, 24.5), (22.3, 18.0)], 2.2),
        trace([(22.3, 18.0), u1_gnd], 1.4),
        # Collegamento U2 pin 1 -> C2-
        trace([u2_gnd, C2_NEG], 1.1),
    ])

    # 4. RST: U1 pin 1 -> R1_BOT -> pad RST (ISP)
    u1_rst = U1_PINS[1]
    nets["RST"] = unary_union([
        round_pad(*R1_BOT, PAD_TH_R),
        round_pad(*PADS_WIRE["RST"], PAD_WIRE_R),
        rect_pad(*u1_rst, 2.0, 0.70),
        trace([R1_BOT, u1_rst], 1.2),
        trace([u1_rst, (22.3, 9.0), PADS_WIRE["RST"]], 1.3),
    ])

    # 5. DATA (PB2 / SCK / RF pin 6): U1 pin 7 -> passa sotto R2 e R3 -> pad DATA
    u1_data = U1_PINS[7]
    nets["DATA"] = unary_union([
        rect_pad(*u1_data, 2.0, 0.65),
        round_pad(*PADS_WIRE["DATA"], PAD_WIRE_R),
        trace([u1_data, (30.5, u1_data[1]), (31.8, 11.2)], 0.65),
        trace([(31.8, 11.2), PADS_WIRE["DATA"]], 1.5),
    ])

    # 6. SYNC (PB1 / MISO / RF pin 5): U1 pin 6 -> R2_BOT -> passa sotto R3 -> pad SYNC
    u1_sync = U1_PINS[6]
    nets["SYNC"] = unary_union([
        rect_pad(*u1_sync, 2.0, 0.65),
        round_pad(*R2_BOT, PAD_TH_R),
        round_pad(*PADS_WIRE["SYNC"], PAD_WIRE_R),
        trace([u1_sync, (29.8, u1_sync[1]), (31.5, 17.2)], 0.65),
        trace([(31.5, 17.2), R2_BOT, PADS_WIRE["SYNC"]], 1.5),
    ])

    # 7. CLK (PB0 / MOSI / RF pin 7): U1 pin 5 -> R3_BOT -> pad CLK
    u1_clk = U1_PINS[5]
    nets["CLK"] = unary_union([
        rect_pad(*u1_clk, 2.0, 0.65),
        round_pad(*R3_BOT, PAD_TH_R),
        round_pad(*PADS_WIRE["CLK"], PAD_WIRE_R),
        trace([u1_clk, (29.2, u1_clk[1]), (31.2, 22.5)], 0.65),
        trace([(31.2, 22.5), R3_BOT, PADS_WIRE["CLK"]], 1.5),
    ])

    return nets

# Lista fori passanti: (x, y, diametro, etichetta)
DRILLS = [
    (*PADS_WIRE["3V3"],  DRILL_WIRE, "3V3"),
    (*PADS_WIRE["5V"],   DRILL_WIRE, "5V"),
    (*PADS_WIRE["GND"],  DRILL_WIRE, "GND"),
    (*PADS_WIRE["RST"],  DRILL_WIRE, "RST"),
    (*PADS_WIRE["DATA"], DRILL_WIRE, "DATA"),
    (*PADS_WIRE["SYNC"], DRILL_WIRE, "SYNC"),
    (*PADS_WIRE["CLK"],  DRILL_WIRE, "CLK"),
    (*C1_POS, DRILL_TH, "C1+"),
    (*C1_NEG, DRILL_TH, "C1-"),
    (*C2_POS, DRILL_TH, "C2+"),
    (*C2_NEG, DRILL_TH, "C2-"),
    (*R1_TOP, DRILL_TH, "R1a"),
    (*R1_BOT, DRILL_TH, "R1b"),
    (*R2_TOP, DRILL_TH, "R2a"),
    (*R2_BOT, DRILL_TH, "R2b"),
    (*R3_TOP, DRILL_TH, "R3a"),
    (*R3_BOT, DRILL_TH, "R3b"),
]

def rounded_board():
    return box(CORNER_R, CORNER_R, BOARD_W - CORNER_R, BOARD_H - CORNER_R).buffer(CORNER_R, resolution=16)

# ==============================================================================
# VERIFICA DRC AUTOMATICA
# ==============================================================================
def run_drc(nets, board_poly):
    print("=== VERIFICA DRC ===")
    ok = True
    names = list(nets.keys())
    for name, geom in nets.items():
        if geom.geom_type != "Polygon":
            print(f"  [ERRORE] Rete {name} non e' connessa in un'unica isola ({geom.geom_type})!")
            ok = False
        if not board_poly.buffer(-0.8).contains(geom):
            print(f"  [WARN] Rete {name} vicina al bordo (<0.8 mm)")

    min_overall = 999.0
    min_pair = None
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            d = nets[names[i]].distance(nets[names[j]])
            if d < min_overall:
                min_overall = d
                min_pair = (names[i], names[j])
            if d < 0.55:
                print(f"  [ERRORE] Distanza troppo bassa tra {names[i]} e {names[j]}: {d:.3f} mm")
                ok = False
            elif d < 0.9:
                print(f"  [INFO] Solco stretto (zona pin SMD) tra {names[i]} e {names[j]}: {d:.3f} mm")
    print(f"  Solco minimo globale: {min_overall:.3f} mm ({min_pair[0]} <-> {min_pair[1]})")

    for x, y, dia, lbl in DRILLS:
        pt = Point(x, y)
        inside = [n for n, g in nets.items() if g.contains(pt)]
        if len(inside) != 1:
            print(f"  [ERRORE] Foro {lbl} ({x},{y}) dentro {inside}")
            ok = False
        else:
            ring = nets[inside[0]].boundary.distance(pt) - dia / 2.0
            if ring < 0.6:
                print(f"  [WARN] Anello stretto su {lbl}: {ring:.2f} mm")
    print("  DRC:", "OK ✅" if ok else "ERRORI ❌")
    return ok

# ==============================================================================
# ESPORTAZIONE 3D (STL + STEP)
# ==============================================================================
def flip_y_coords(coords):
    """Mappa (x, y_svg) -> (x, BOARD_H - y_svg) così la vista da +Z coincide 1:1 con il 2D."""
    return [(x, BOARD_H - y) for x, y in coords]

def poly_to_step_dict(poly, z0, z1):
    outer = flip_y_coords(list(poly.exterior.coords)[:-1])
    holes = [flip_y_coords(list(r.coords)[:-1]) for r in poly.interiors]
    return {"outer": outer, "holes": holes, "z0": z0, "z1": z1}

def poly_to_trimesh(poly, z0, z1):
    # Crea poligono con Y invertita per 3D
    ext = flip_y_coords(list(poly.exterior.coords))
    ints = [flip_y_coords(list(r.coords)) for r in poly.interiors]
    p3 = Polygon(ext, ints).buffer(0)
    mesh = trimesh.creation.extrude_polygon(p3, height=(z1 - z0))
    mesh.apply_translation([0.0, 0.0, z0])
    return mesh

def export_3d(out_dir, board_poly, nets):
    drill_union = unary_union([Point(x, y).buffer(d / 2.0, resolution=24) for x, y, d, _ in DRILLS])
    drill_relief = unary_union([Point(x, y).buffer(d / 2.0 + HOLE_CLEAR_R, resolution=24) for x, y, d, _ in DRILLS])

    base_with_holes = board_poly.difference(drill_union)
    relief_polys = []
    for name, geom in nets.items():
        g = geom.difference(drill_relief)
        if g.geom_type == "Polygon":
            relief_polys.append(g)
        else:
            relief_polys.extend(list(g.geoms))

    # 1. STEP (base + isole di rilievo)
    step_items = [poly_to_step_dict(base_with_holes, 0.0, BASE_THICK)]
    for rp in relief_polys:
        step_items.append(poly_to_step_dict(rp, BASE_THICK, BASE_THICK + RELIEF_H))
    step_path = os.path.join(out_dir, "x360_rf_attiny13_rilievo.step")
    prisms_step(step_path, "x360_rf_attiny13_rilievo", step_items, 0.0, BASE_THICK)
    print(f"  Scritto STEP: {step_path}")

    # 2. STL watertight (unione booleana manifold3d della base + rilievi)
    base_mesh = poly_to_trimesh(base_with_holes, 0.0, BASE_THICK)
    # Estendiamo i rilievi leggermente dentro la base (-0.02 mm) per unione booleana pulita
    relief_meshes = [poly_to_trimesh(rp, BASE_THICK - 0.02, BASE_THICK + RELIEF_H) for rp in relief_polys]
    combined = trimesh.boolean.union([base_mesh] + relief_meshes, engine="manifold")
    stl_path = os.path.join(out_dir, "x360_rf_attiny13_rilievo.stl")
    combined.export(stl_path)
    print(f"  Scritto STL:  {stl_path} (watertight={combined.is_watertight}, volume={combined.volume:.1f} mm^3)")

# ==============================================================================
# ESPORTAZIONE SVG 1:1 E ANTEPRIMA PNG ANNOTATA
# ==============================================================================
def poly_to_svg_path(poly):
    def ring_d(coords):
        pts = [f"{x:.3f},{y:.3f}" for x, y in coords[:-1]]
        return "M " + " L ".join(pts) + " Z"
    d = ring_d(list(poly.exterior.coords))
    for r in poly.interiors:
        d += " " + ring_d(list(r.coords))
    return d

def export_svg(out_dir, board_poly, nets):
    drill_relief = unary_union([Point(x, y).buffer(d / 2.0 + HOLE_CLEAR_R, resolution=24) for x, y, d, _ in DRILLS])
    pad_m = 4.0
    W, H = BOARD_W + 2 * pad_m, BOARD_H + 2 * pad_m
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W:.2f}mm" height="{H:.2f}mm" viewBox="{-pad_m} {-pad_m} {W} {H}">',
        '  <rect x="-4" y="-4" width="100%" height="100%" fill="#ffffff"/>',
        f'  <path d="{poly_to_svg_path(board_poly)}" fill="#f2f4f7" stroke="#222" stroke-width="0.25"/>',
    ]
    for name, geom in nets.items():
        g = geom.difference(drill_relief)
        geoms = [g] if g.geom_type == "Polygon" else list(g.geoms)
        for p in geoms:
            lines.append(f'  <path d="{poly_to_svg_path(p)}" fill="#d97724" fill-rule="evenodd" stroke="#8a440c" stroke-width="0.1"/>')
    for x, y, dia, lbl in DRILLS:
        lines.append(f'  <circle cx="{x:.2f}" cy="{y:.2f}" r="{dia/2:.2f}" fill="#ffffff" stroke="#111" stroke-width="0.15"/>')
    # Sagome SMD (U1, U2)
    lines.append(f'  <rect x="{U1_X-2.0:.2f}" y="{U1_Y-2.5:.2f}" width="4.0" height="5.0" fill="none" stroke="#1d4ed8" stroke-width="0.2" stroke-dasharray="0.5,0.4"/>')
    lines.append(f'  <circle cx="{U1_X-1.2:.2f}" cy="{U1_Y-1.7:.2f}" r="0.35" fill="#1d4ed8"/>')
    lines.append(f'  <rect x="{U2_X-0.7:.2f}" y="{U2_Y-1.5:.2f}" width="1.4" height="3.0" fill="none" stroke="#1d4ed8" stroke-width="0.2" stroke-dasharray="0.5,0.4"/>')
    # Sagome TH (sul retro, tratteggiate in verde)
    for (x1, y1), (x2, y2), lbl in [
        (R1_TOP, R1_BOT, "R1 10k"), (R2_TOP, R2_BOT, "R2 10k"), (R3_TOP, R3_BOT, "R3 10k"),
        (C1_POS, C1_NEG, "C1 1uF"), (C2_POS, C2_NEG, "C2 1uF"),
    ]:
        lines.append(f'  <line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" stroke="#15803d" stroke-width="0.35" stroke-dasharray="0.8,0.5"/>')
    # Etichette
    for lbl, (x, y) in PADS_WIRE.items():
        lines.append(f'  <text x="{x:.2f}" y="{y-2.3:.2f}" font-family="sans-serif" font-size="1.8" font-weight="bold" text-anchor="middle" fill="#111">{lbl}</text>')
    lines.append(f'  <text x="{U1_X:.2f}" y="{U1_Y+0.5:.2f}" font-family="sans-serif" font-size="1.3" font-weight="bold" text-anchor="middle" fill="#1d4ed8">U1</text>')
    lines.append(f'  <text x="{U2_X:.2f}" y="{U2_Y+0.4:.2f}" font-family="sans-serif" font-size="1.1" font-weight="bold" text-anchor="middle" fill="#1d4ed8">U2</text>')
    lines.append('</svg>')
    svg_path = os.path.join(out_dir, "anteprima_rame_1a1.svg")
    with open(svg_path, "w") as f:
        f.write("\n".join(lines))
    print(f"  Scritto SVG:  {svg_path}")

def export_png(out_dir, board_poly, nets):
    """Anteprima PNG ad alta risoluzione con vista LATO RAME (sopra) e LATO COMPONENTI TH (sotto, specchiata)."""
    scale = 22.0  # px / mm
    margin_x, margin_y = 60, 70
    bw, bh = int(BOARD_W * scale), int(BOARD_H * scale)
    img_w = bw + 2 * margin_x + 260
    img_h = 2 * bh + 3 * margin_y + 60
    img = Image.new("RGB", (img_w, img_h), (250, 250, 252))
    draw = ImageDraw.Draw(img)

    try:
        font_lg = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 22)
        font_md = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 16)
        font_sm = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 13)
    except Exception:
        font_lg = font_md = font_sm = ImageFont.load_default()

    drill_relief = unary_union([Point(x, y).buffer(d / 2.0 + HOLE_CLEAR_R, resolution=24) for x, y, d, _ in DRILLS])

    def to_px(x, y, ox, oy, mirror_x=False):
        xx = (BOARD_W - x) if mirror_x else x
        return (ox + xx * scale, oy + y * scale)

    def draw_poly(poly, fill, outline, ox, oy, mirror_x=False):
        pts = [to_px(x, y, ox, oy, mirror_x) for x, y in list(poly.exterior.coords)]
        draw.polygon(pts, fill=fill, outline=outline)
        for r in poly.interiors:
            hpts = [to_px(x, y, ox, oy, mirror_x) for x, y in list(r.coords)]
            draw.polygon(hpts, fill=(242, 244, 247), outline=outline)

    # --- PANNELLO 1: LATO RAME / RILIEVO (stampa verso l'alto, SMD qui) ---
    ox1, oy1 = margin_x, margin_y
    draw.text((ox1, oy1 - 45), "LATO RAME / RILIEVO (+0.2 mm) — Salda qui ATtiny13A (U1), MCP1700 (U2) e fili", fill=(20, 20, 30), font=font_lg)
    draw_poly(board_poly, (238, 242, 246), (40, 40, 50), ox1, oy1)

    for name, geom in nets.items():
        g = geom.difference(drill_relief)
        geoms = [g] if g.geom_type == "Polygon" else list(g.geoms)
        for p in geoms:
            draw_poly(p, (217, 119, 36), (138, 68, 12), ox1, oy1)

    for x, y, dia, lbl in DRILLS:
        px, py = to_px(x, y, ox1, oy1)
        r = (dia / 2.0) * scale
        draw.ellipse((px - r, py - r, px + r, py + r), fill=(255, 255, 255), outline=(20, 20, 20), width=2)

    # Contorni SMD U1 e U2
    u1_box = [*to_px(U1_X - 2.0, U1_Y - 2.5, ox1, oy1), *to_px(U1_X + 2.0, U1_Y + 2.5, ox1, oy1)]
    draw.rectangle(u1_box, outline=(29, 78, 216), width=3)
    dot = to_px(U1_X - 1.2, U1_Y - 1.7, ox1, oy1)
    draw.ellipse((dot[0] - 5, dot[1] - 5, dot[0] + 5, dot[1] + 5), fill=(29, 78, 216))
    draw.text(to_px(U1_X - 1.4, U1_Y - 0.5, ox1, oy1), "U1\n13A", fill=(29, 78, 216), font=font_sm)

    u2_box = [*to_px(U2_X - 0.7, U2_Y - 1.5, ox1, oy1), *to_px(U2_X + 0.7, U2_Y + 1.5, ox1, oy1)]
    draw.rectangle(u2_box, outline=(29, 78, 216), width=3)
    draw.text(to_px(U2_X - 1.5, U2_Y - 3.0, ox1, oy1), "U2 MCP1700", fill=(29, 78, 216), font=font_sm)

    # Etichette piazzole
    pad_notes = {
        "3V3": "3V3 (ISP VCC)",
        "5V": "5V (opz. USB)",
        "GND": "GND (ISP GND)",
        "RST": "RST (ISP)",
        "DATA": "DATA (RF6 / SCK)",
        "SYNC": "SYNC (RF5 / MISO)",
        "CLK": "CLK (RF7 / MOSI)",
    }
    for lbl, (x, y) in PADS_WIRE.items():
        px, py = to_px(x, y, ox1, oy1)
        if x < 10:
            draw.text((px - 15, py - 38), lbl, fill=(10, 10, 10), font=font_md)
        elif x > 40:
            draw.text((px + 32, py - 10), pad_notes[lbl], fill=(10, 10, 10), font=font_md)
        else:
            draw.text((px - 28, py - 38), pad_notes[lbl], fill=(10, 10, 10), font=font_sm)

    # Etichette R/C sul lato rame (tratteggiate / leggere per riferimento)
    for p1, p2, lbl in [
        (R1_TOP, R1_BOT, "R1 10k"), (R2_TOP, R2_BOT, "R2 10k"), (R3_TOP, R3_BOT, "R3 10k"),
        (C1_POS, C1_NEG, "C1 1uF"), (C2_POS, C2_NEG, "C2 1uF"),
    ]:
        draw.line([to_px(*p1, ox1, oy1), to_px(*p2, ox1, oy1)], fill=(21, 128, 61), width=2)
        mx, my = (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2
        draw.text(to_px(mx + 0.5, my - 0.8, ox1, oy1), lbl, fill=(21, 128, 61), font=font_sm)

    # --- PANNELLO 2: LATO LISCIO / RETRO (specchiato, inserisci qui R1-R3 e C1-C2) ---
    ox2, oy2 = margin_x, 2 * margin_y + bh + 20
    draw.text((ox2, oy2 - 45), "LATO LISCIO (sul piano di stampa) — Inserisci da qui R1-R3 (10k) e C1-C2 (1uF)", fill=(20, 20, 30), font=font_lg)
    draw_poly(board_poly, (245, 247, 250), (40, 40, 50), ox2, oy2, mirror_x=True)

    # Disegna componenti TH sul lato liscio
    for p1, p2, lbl, is_cap in [
        (R1_TOP, R1_BOT, "R1 10k", False),
        (R2_TOP, R2_BOT, "R2 10k", False),
        (R3_TOP, R3_BOT, "R3 10k", False),
        (C1_POS, C1_NEG, "C1 1uF (+ sopra)", True),
        (C2_POS, C2_NEG, "C2 1uF (+ sopra)", True),
    ]:
        q1 = to_px(*p1, ox2, oy2, mirror_x=True)
        q2 = to_px(*p2, ox2, oy2, mirror_x=True)
        draw.line([q1, q2], fill=(80, 80, 90), width=4)
        mx, my = (q1[0] + q2[0]) / 2, (q1[1] + q2[1]) / 2
        if is_cap:
            r = 32
            draw.ellipse((mx - r, my - r, mx + r, my + r), fill=(191, 219, 254), outline=(30, 64, 175), width=3)
            draw.text((q1[0] + 14, q1[1] - 10), "+", fill=(220, 38, 38), font=font_lg)
            draw.text((mx - 22, my - 8), lbl.split()[0], fill=(30, 64, 175), font=font_md)
        else:
            draw.rectangle((mx - 14, my - 38, mx + 14, my + 38), fill=(254, 240, 138), outline=(161, 98, 7), width=3)
            draw.text((mx + 18, my - 10), lbl, fill=(113, 63, 18), font=font_md)

    for x, y, dia, lbl in DRILLS:
        px, py = to_px(x, y, ox2, oy2, mirror_x=True)
        r = (dia / 2.0) * scale
        draw.ellipse((px - r, py - r, px + r, py + r), fill=(255, 255, 255), outline=(20, 20, 20), width=2)
        if lbl in PADS_WIRE:
            draw.text((px - 18, py + 16), lbl, fill=(40, 40, 40), font=font_sm)

    png_path = os.path.join(out_dir, "anteprima_montaggio.png")
    img.save(png_path)
    print(f"  Scritto PNG:  {png_path}")

def main():
    here = os.path.dirname(os.path.abspath(__file__))
    out_dir = os.path.join(here, "build")
    os.makedirs(out_dir, exist_ok=True)

    board_poly = rounded_board()
    nets = build_nets()
    ok = run_drc(nets, board_poly)
    if not ok:
        sys.exit(1)

    export_3d(out_dir, board_poly, nets)
    export_svg(out_dir, board_poly, nets)
    export_png(out_dir, board_poly, nets)
    print(f"\nFatto! Dimensioni basetta: {BOARD_W:.1f} x {BOARD_H:.1f} mm, spessore {BASE_THICK:.1f} + {RELIEF_H:.1f} mm rilievo.")

if __name__ == "__main__":
    main()
