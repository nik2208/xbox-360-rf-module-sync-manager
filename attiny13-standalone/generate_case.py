#!/usr/bin/env python3
"""
Genera:
  1. build/Xbox360_RF_Case_Part_A_ATtiny13_Slim.stl
     Guscio inferiore SLIM (+6.0 mm rispetto all'originale MakerWorld 1911648,
     altezza totale assemblata ~20.1 mm) compatibile al 100% con Part_B e Button:
     - culla per la basetta ATtiny13A (48 x 29 mm, lato rame/SMD verso il basso)
     - chiusura del vecchio scasso USB-C + passacavo tondo/U + labirinto ad S blocca-cavo
     - zero overhang, zero supporti di stampa
  2. build/Xbox360_RF_Diffuser.stl
     Anello diffusore da 0.45 mm (da stampare in bianco o trasparente e incollare/fissare
     sotto il coperchio Part_B) per sostituire il diffusore trasparente originale dei LED.

Uso:
  ~/Devel/github/360/tools/venv/bin/python generate_case.py
"""
import os
import sys
import numpy as np
import trimesh
from shapely.geometry import Point, Polygon, box
from shapely.ops import unary_union
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
REF_DIR = os.path.join(HERE, "Xbox+360+RF+Module+Box+-+DIY+Receiver")
OUT_DIR = os.path.join(HERE, "build")

# ==============================================================================
# PARAMETRI CASE SLIM
# ==============================================================================
EXTRA_DEPTH = 6.0      # estensione verso il basso (mm): totale assemblato ~20.1 mm!
ORIG_Z_MIN = -8.30
ORIG_FLOOR_TOP = -6.50
FLOOR_TOP_Z = ORIG_FLOOR_TOP - EXTRA_DEPTH    # -12.50 mm

# 3 colonnine viti originali del modulo RF
SCREW_HOLES = [
    (-42.65,  24.35),
    (  0.25, -21.55),
    ( 37.65,  24.35),
]

# Culla per la basetta ATtiny13A (48.0 x 29.0 mm) — spostata leggermente a sinistra
# per lasciare libero tutto il lato destro (X = +19 .. +42) al labirinto blocca-cavo ad S!
PCB_W, PCB_H = 48.0, 29.0
PCB_CLEAR = 0.35
CRADLE_CX, CRADLE_CY = -9.5, 1.5   # X = -33.5 .. +14.5, Y = -13.0 .. +16.0 (lontana da tutte e 3 le viti!)
STANDOFF_H = 2.2                   # appoggi bassi: SMD (1.75 mm) rivolti verso il basso!
RETAIN_H = 4.6                     # contenimento laterale (2.2 appoggio + 2.4 bordo PCB)
RETAIN_T = 1.8

# Passacavo e supporto ad S blocca-cavo (lato destro: X = +20 .. +48.25, Y = -18 .. +2)
CABLE_SLOT_Y = -9.0                # centro foro uscita cavo USB sulla parete destra
CABLE_SLOT_W = 4.6                 # larghezza canale/uscita (per cavo USB Ø 3.5-4.5 mm)
S_MAZE_H = 7.5                     # altezza pareti/perni del labirinto ad S dal fondo


def extrude_poly(poly, z0, z1):
    m = trimesh.creation.extrude_polygon(poly.buffer(0), height=(z1 - z0))
    m.apply_translation([0.0, 0.0, z0])
    return m


def build_diffuser():
    """Anello diffusore per i 4 LED del Ring of Light sotto Part_B (z = 4.00 mm)."""
    # Centro LED in Part_B = (0.25, 0.00), raggio archi LED = 15.25 mm, foro tasto r ~ 4.2 mm
    outer = Point(0.0, 0.0).buffer(17.5, resolution=64)
    inner = Point(0.0, 0.0).buffer(5.8, resolution=64)  # lascia passare libero il tasto centrale
    ring = outer.difference(inner)
    mesh = extrude_poly(ring, 0.0, 0.45)  # 3 strati da 0.15 mm -> diffonde bene anche in bianco!
    out_path = os.path.join(OUT_DIR, "Xbox360_RF_Diffuser.stl")
    mesh.export(out_path)
    print(f"  Scritto Diffusore STL: {out_path} (Ø ext 35.0 mm, Ø int 11.6 mm, h 0.45 mm, watertight={mesh.is_watertight})")


def build_washers_m14():
    """3 rondelle di fissaggio (Ø 5.6 mm, foro Ø 1.6 mm, h 1.0 mm) per usare le viti M1.4x6/8 del kit occhiali."""
    parts = []
    for i in range(3):
        cx = i * 8.0
        w = Point(cx, 0.0).buffer(2.8, resolution=36).difference(Point(cx, 0.0).buffer(0.8, resolution=24))
        parts.append(extrude_poly(w, 0.0, 1.0))
    mesh = trimesh.util.concatenate(parts)
    out_path = os.path.join(OUT_DIR, "Xbox360_RF_Washers_M14.stl")
    mesh.export(out_path)
    print(f"  Scritto Rondelle M1.4 STL: {out_path} (3x Ø 5.6 mm, foro Ø 1.6 mm, h 1.0 mm)")


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    pa_path = os.path.join(REF_DIR, "Xbox360_RF_Case_Part_A.stl")
    pb_path = os.path.join(REF_DIR, "Xbox360_RF_Case_Part_B.stl")
    if not os.path.exists(pa_path):
        print(f"ERRORE: non trovo {pa_path}")
        sys.exit(1)

    pa = trimesh.load(pa_path)
    print(f"Caricato Part_A: bounds={np.round(pa.bounds, 2).tolist()}, watertight={pa.is_watertight}")

    # 1. Estendiamo Part_A verso il basso di 6.0 mm (spostando tutti i vertici sotto z=-6.0)
    pa_deep = pa.copy()
    verts = pa_deep.vertices.copy()
    verts[verts[:, 2] < -6.0, 2] -= EXTRA_DEPTH
    pa_deep.vertices = verts
    print(f"  Part_A Slim (+{EXTRA_DEPTH} mm): bounds={np.round(pa_deep.bounds, 2).tolist()}, watertight={pa_deep.is_watertight}")

    # 2. Chiudiamo il vecchio scasso rettangolare USB-C sulla parete destra (X = 43.0 .. 48.25, Y = 5.0 .. 19.5)
    #    Resta perfettamente a filo con la parete esterna (X=48.25) e sotto il gradino di incastro (z=-1.25).
    usb_plug = extrude_poly(box(43.2, 4.5, 48.25, 20.5), FLOOR_TOP_Z - 0.1, -1.25)

    # 3. Culla per la basetta ATtiny13A (48 x 29 mm) — lato rame/SMD rivolto verso il basso
    half_w = PCB_W / 2.0 + PCB_CLEAR
    half_h = PCB_H / 2.0 + PCB_CLEAR
    x0, x1 = CRADLE_CX - half_w, CRADLE_CX + half_w
    y0, y1 = CRADLE_CY - half_h, CRADLE_CY + half_h

    add_parts = [usb_plug]
    corner_len = 9.0
    ledge_in = 3.2
    corners = [
        (x0, y0, +1, +1),
        (x1, y0, -1, +1),
        (x0, y1, +1, -1),
        (x1, y1, -1, -1),
    ]
    for cx, cy, sx, sy in corners:
        wall_x = box(
            min(cx - sx * RETAIN_T, cx + sx * corner_len),
            min(cy - sy * RETAIN_T, cy),
            max(cx - sx * RETAIN_T, cx + sx * corner_len),
            max(cy - sy * RETAIN_T, cy),
        )
        wall_y = box(
            min(cx - sx * RETAIN_T, cx),
            min(cy - sy * RETAIN_T, cy + sy * corner_len),
            max(cx - sx * RETAIN_T, cx),
            max(cy - sy * RETAIN_T, cy + sy * corner_len),
        )
        ledge = box(
            min(cx, cx + sx * ledge_in),
            min(cy, cy + sy * ledge_in),
            max(cx, cx + sx * ledge_in),
            max(cy, cy + sy * ledge_in),
        )
        add_parts.append(extrude_poly(unary_union([wall_x, wall_y]), FLOOR_TOP_Z - 0.15, FLOOR_TOP_Z + RETAIN_H))
        add_parts.append(extrude_poly(ledge, FLOOR_TOP_Z - 0.15, FLOOR_TOP_Z + STANDOFF_H))

    # 4. Supporto ad S blocca-cavo USB (nel vano destro: X = +21 .. +41, Y = -18 .. 0)
    #    Il cavo entra dall'interno (X ~ +21, Y ~ -13), fa una doppia curva ad S attorno
    #    a 3 setti arrotondati (canale da ~4.4 mm) ed esce dritto dalla fessura a (X=48.25, Y=-9.0).
    #    Ogni setto e' arrotondato (buffer r=1.4 mm) per non pizzicare la guaina del cavo!
    s_walls_2d = [
        # Parete inferiore di guida del canale S (chiude verso il basso a Y = -17.5)
        box(22.0, -19.5, 42.5, -17.0),
        # Parete superiore di guida del canale S (chiude verso l'alto a Y = -0.5)
        box(22.0, -1.0, 42.5, 1.5),
        # Setto 1 (scende dall'alto a X = 26.5): lascia passaggio in basso (Y = -17.0 .. -11.8 -> 5.2 mm)
        box(25.2, -11.6, 27.8, 0.5).buffer(0.8, resolution=16),
        # Setto 2 (sale dal basso a X = 33.5): lascia passaggio in alto (Y = -6.2 .. -1.0 -> 5.2 mm)
        box(32.2, -18.5, 34.8, -6.4).buffer(0.8, resolution=16),
        # Setto 3 (scende dall'alto a X = 40.0): guida verso l'uscita centrata a Y = -9.0 (passaggio -17..-11.6)
        # No: facciamo uscire il cavo dritto a Y = -9.0 dopo la curva intorno al Setto 2!
        # Quindi il Setto 3 blocca dal basso sotto l'uscita (Y = -18.5 .. -12.0) e dall'alto (Y = -6.0 .. 0.5)
        box(39.0, -18.5, 41.4, -12.2).buffer(0.6, resolution=16),
        box(39.0, -5.8, 41.4, 0.5).buffer(0.6, resolution=16),
    ]
    for sw in s_walls_2d:
        add_parts.append(extrude_poly(sw, FLOOR_TOP_Z - 0.15, FLOOR_TOP_Z + S_MAZE_H))

    # 4b. Riempiamo i 3 fori M2 originali (Ø 3.4 mm) e aggiungiamo 3 collarini di centraggio
    #     (Ø 2.6 mm, h 1.4 mm sopra z=-1.90) con foro pilota Ø 1.15 mm per viti M1.4x6 o M1.4x8!
    pilot_holes = []
    for hx, hy in SCREW_HOLES:
        # Tappo che riempie il foro Ø 3.4 mm originale fino a z=-1.90
        fill_cyl = trimesh.creation.cylinder(radius=2.1, height=(-1.90 - (ORIG_Z_MIN - EXTRA_DEPTH)), sections=32)
        fill_cyl.apply_translation([hx, hy, (-1.90 + (ORIG_Z_MIN - EXTRA_DEPTH)) / 2.0])
        add_parts.append(fill_cyl)
        # Collarino di centraggio sopra la mensola RF (-1.90 .. -0.50, entra nel foro PCB RF)
        collar = trimesh.creation.cylinder(radius=1.30, height=1.55, sections=32)
        collar.apply_translation([hx, hy, -1.90 + 1.55 / 2.0 - 0.15])
        add_parts.append(collar)
        # Foro pilota autofilettante Ø 1.15 mm (profondo 7.5 mm per viti M1.4x6 o M1.4x8)
        ph = trimesh.creation.cylinder(radius=0.575, height=8.0, sections=24)
        ph.apply_translation([hx, hy, -0.50 - 3.8])
        pilot_holes.append(ph)

    # 5. Unione booleana completa
    print("  Unione booleana manifold3d...")
    solid = trimesh.boolean.union([pa_deep] + add_parts, engine="manifold")

    # 6. Tagliamo la fessura di uscita del cavo USB + i 3 fori pilota M1.4
    slot_h = 12.0
    slot_box = trimesh.creation.box(
        extents=[10.0, CABLE_SLOT_W, slot_h],
        transform=trimesh.transformations.translation_matrix([45.5, CABLE_SLOT_Y, FLOOR_TOP_Z + 2.3 + slot_h / 2.0]),
    )
    slot_cyl = trimesh.creation.cylinder(radius=CABLE_SLOT_W / 2.0, height=10.0, sections=24)
    slot_cyl.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2.0, [0, 1, 0]))
    slot_cyl.apply_translation([45.5, CABLE_SLOT_Y, FLOOR_TOP_Z + 2.3])

    cable_cut = trimesh.boolean.union([slot_box, slot_cyl], engine="manifold")
    solid = trimesh.boolean.difference([solid, cable_cut] + pilot_holes, engine="manifold")

    # Trasliamo in Z cosi' il fondo appoggia esattamente su Z = 0.0
    z_shift = -solid.bounds[0][2]
    solid.apply_translation([0.0, 0.0, z_shift])

    out_stl = os.path.join(OUT_DIR, "Xbox360_RF_Case_Part_A_ATtiny13_Slim.stl")
    solid.export(out_stl)
    print(f"  Scritto Case Slim STL: {out_stl}")
    print(f"  Dimensioni guscio inferiore: {np.round(solid.extents, 2).tolist()} mm (assemblato con Part_B: ~20.1 mm)")
    print(f"  Watertight: {solid.is_watertight}, Volume: {solid.volume/1000:.2f} cm^3")

    # 7. Generiamo diffusore LED per Part_B + 3 rondelle per viti M1.4
    build_diffuser()
    build_washers_m14()

    # 8. Anteprima PNG aggiornata
    pb = trimesh.load(pb_path)
    pb.apply_translation([0.0, 0.0, z_shift])
    render_preview(solid, pb, z_shift)


def render_preview(part_a, part_b, z_shift):
    scale = 6.5
    W, H = int(115 * scale), int(75 * scale)
    SH = int(32 * scale)
    img = Image.new("RGB", (W, H + SH + 70), (250, 250, 252))
    draw = ImageDraw.Draw(img)

    z_cradle = FLOOR_TOP_Z + z_shift + 3.5
    draw.text((20, 12), f"VISTA INTERNA SLIM (z={z_cradle:.1f} mm) — Basetta 48x29 mm (SX) + Labirinto ad S blocca-cavo (DX)", fill=(20, 20, 30))

    def to_xy(x, y):
        return (int((x + 60.0) * scale), int((38.0 - y) * scale) + 32)

    sec = part_a.section(plane_origin=[0, 0, z_cradle], plane_normal=[0, 0, 1])
    if sec:
        for ent in sec.entities:
            pts = sec.vertices[ent.points]
            px = [to_xy(p[0], p[1]) for p in pts]
            if len(px) >= 2:
                draw.line(px, fill=(30, 80, 180), width=2)

    # Ingombro basetta ATtiny13A
    p0 = to_xy(CRADLE_CX - PCB_W / 2, CRADLE_CY + PCB_H / 2)
    p1 = to_xy(CRADLE_CX + PCB_W / 2, CRADLE_CY - PCB_H / 2)
    draw.rectangle([p0[0], p0[1], p1[0], p1[1]], outline=(217, 119, 36), width=3)
    draw.text((p0[0] + 10, p0[1] + 10), "Basetta ATtiny13A\n(48 x 29 mm, SMD giu')", fill=(180, 83, 9))

    # Percorso indicativo del cavo USB nel labirinto ad S
    cable_pts = [
        to_xy(21.5, -14.2), to_xy(26.5, -14.2), to_xy(30.0, -9.0),
        to_xy(33.5, -3.5), to_xy(37.2, -9.0), to_xy(49.5, -9.0),
    ]
    draw.line(cable_pts, fill=(220, 38, 38), width=4)
    draw.text(to_xy(22.5, -21.5), "Cavo USB (blocca-cavo ad S)", fill=(220, 38, 38))

    for i, (hx, hy) in enumerate(SCREW_HOLES, 1):
        cx, cy = to_xy(hx, hy)
        draw.text((cx + 12, cy - 8), f"Vite #{i}", fill=(20, 120, 60))

    # Pannello 2: sezione laterale XZ
    oy = H + 55
    draw.text((20, oy - 24), "SEZIONE LATERALE SLIM (h totale ~20.1 mm) — Guscio (blu) + Part_B (verde) + Diffusore LED (ciano)", fill=(20, 20, 30))

    def to_xz(x, z):
        return (int((x + 60.0) * scale), int(oy + SH - (z + 2.0) * scale))

    for mesh, col in [(part_a, (30, 80, 180)), (part_b, (21, 128, 61))]:
        sxz = mesh.section(plane_origin=[0, CRADLE_CY, 0], plane_normal=[0, 1, 0])
        if sxz:
            for ent in sxz.entities:
                pts = sxz.vertices[ent.points]
                px = [to_xz(p[0], p[2]) for p in pts]
                if len(px) >= 2:
                    draw.line(px, fill=col, width=2)

    # Disegna basetta ATtiny13A (SMD verso il basso)
    z_pcb0 = FLOOR_TOP_Z + z_shift + STANDOFF_H
    z_pcb1 = z_pcb0 + 1.95
    a = to_xz(CRADLE_CX - PCB_W / 2, z_pcb1)
    b = to_xz(CRADLE_CX + PCB_W / 2, z_pcb0)
    draw.rectangle([a[0], a[1], b[0], b[1]], fill=(251, 191, 36), outline=(180, 83, 9), width=2)
    draw.text((a[0] + 8, a[1] - 16), "Basetta ATtiny13A (R/C sopra, SMD sotto)", fill=(180, 83, 9))

    # Linea modulo RF
    z_rf = -1.90 + z_shift
    rf0 = to_xz(-44.0, z_rf + 1.6)
    rf1 = to_xz(40.0, z_rf)
    draw.rectangle([rf0[0], rf0[1], rf1[0], rf1[1]], outline=(220, 38, 38), width=2)
    draw.text((rf0[0] + 8, rf0[1] - 16), "Modulo RF Xbox 360", fill=(220, 38, 38))

    # Diffusore LED sotto Part_B (z = 4.00 + z_shift)
    z_dif = 4.00 + z_shift
    for dx0, dx1 in [(-17.25, -5.55), (6.05, 17.75)]:
        d0 = to_xz(dx0, z_dif)
        d1 = to_xz(dx1, z_dif - 0.45)
        draw.rectangle([d0[0], d0[1], d1[0], d1[1]], fill=(6, 182, 212), outline=(14, 116, 144), width=1)

    out_png = os.path.join(OUT_DIR, "anteprima_case.png")
    img.save(out_png)
    print(f"  Scritto PNG: {out_png}")


if __name__ == "__main__":
    main()
