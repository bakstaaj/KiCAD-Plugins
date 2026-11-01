#!/usr/bin/env python3
# gcode_common.py
# Geometry, board reading, and G-code generation functions shared by
# all plugin actions. pcbnew is imported locally inside the functions
# that need it so this module is importable outside KiCad as well.

import math
import os
import subprocess


GSENDER_EXECUTABLE = r"C:\Program Files\gSender Edge\gSender Edge.exe"


def open_in_gsender(path):
    """Open generated G-code explicitly in gSender V1.7.0-Edge-2."""
    if os.name != "nt":
        raise OSError("Automatic G-code opening is only configured for Windows.")
    if not os.path.isfile(GSENDER_EXECUTABLE):
        raise FileNotFoundError(
            "gSender V1.7.0-Edge-2 was not found at: " + GSENDER_EXECUTABLE
        )
    subprocess.Popen([GSENDER_EXECUTABLE, os.path.abspath(path)])


def mirror_xy(x, y, axis="None"):
    """Mirror a point about the selected G-code axis through (0, 0)."""
    if axis == "X axis":
        return x, -y
    if axis == "Y axis":
        return -x, y
    return x, y


def mirror_path(path, axis="None"):
    """Return a path mirrored about the selected G-code axis."""
    return [mirror_xy(x, y, axis) for x, y in path]


# ============================================================
# GEOMETRY
# ============================================================
def _area_assinada(pontos):
    # Gauss (shoelace) formula: area > 0 = CCW, area < 0 = CW
    area = 0.0
    n = len(pontos)
    for k in range(n):
        x1, y1 = pontos[k]
        x2, y2 = pontos[(k + 1) % n]
        area += x1 * y2 - x2 * y1
    return area / 2.0


def _inflate_poly(poly, amount_nm):
    """Call SHAPE_POLY_SET Inflate/Deflate handling API differences across KiCad versions.
    Positive amount_nm = expand outward, negative = shrink inward.
    Uses ALLOW_ACUTE_CORNERS (value 0) = mitre-like sharp corners.
    """
    import pcbnew

    ALLOW_ACUTE = 0   # CORNER_STRATEGY::ALLOW_ACUTE_CORNERS — sharpest corners
    MAX_ERR     = 5000  # 5 µm, only matters for round/chamfer strategies

    abs_nm = abs(amount_nm)

    if amount_nm >= 0:
        candidates = [
            (poly.Inflate, (abs_nm, ALLOW_ACUTE, MAX_ERR)),  # KiCad 7+
            (poly.Inflate, (abs_nm, 16, ALLOW_ACUTE)),       # KiCad 6 (segments, strategy)
            (poly.Inflate, (abs_nm, 16)),                    # KiCad 6 fallback
        ]
    else:
        deflate = getattr(poly, "Deflate", None)
        candidates = []
        if deflate:
            candidates += [
                (deflate, (abs_nm, ALLOW_ACUTE, MAX_ERR)),
                (deflate, (abs_nm, 16, ALLOW_ACUTE)),
                (deflate, (abs_nm, 16)),
            ]
        # KiCad 6 fallback: negative value passed to Inflate
        candidates += [
            (poly.Inflate, (amount_nm, ALLOW_ACUTE, MAX_ERR)),
            (poly.Inflate, (amount_nm, 16, ALLOW_ACUTE)),
            (poly.Inflate, (amount_nm, 16)),
        ]

    for fn, args in candidates:
        try:
            fn(*args)
            return
        except TypeError:
            continue

    raise RuntimeError(
        "SHAPE_POLY_SET: no compatible Inflate/Deflate signature found in this KiCad version"
    )


def _offset_caminho(pontos, raio):
    """Offset polygon using KiCad's built-in SHAPE_POLY_SET (no external dependencies).
    Positive raio = expand outward, negative = shrink inward.

    Points are received in Y-up convention (Y flipped from KiCad native).
    We un-flip Y before calling Inflate so that winding direction is correct
    for SHAPE_POLY_SET/Clipper, then re-flip the result.
    """
    import pcbnew

    NM = 1_000_000  # 1 mm = 1,000,000 nm (KiCad internal units)

    poly = pcbnew.SHAPE_POLY_SET()
    poly.NewOutline()
    pts = pontos[:-1] if len(pontos) > 1 and pontos[0] == pontos[-1] else list(pontos)
    for x, y in pts:
        poly.Append(int(round(x * NM)), int(round(-y * NM)))  # un-flip Y → KiCad native

    if raio != 0:
        _inflate_poly(poly, int(round(raio * NM)))

    if poly.OutlineCount() == 0 or poly.Outline(0).PointCount() < 3:
        raise ValueError(
            "Offset produced empty geometry (hole smaller than cutter diameter?)"
        )

    outline = poly.Outline(0)
    result = [
        (pcbnew.ToMM(outline.CPoint(i).x), -pcbnew.ToMM(outline.CPoint(i).y))  # re-flip Y
        for i in range(outline.PointCount())
    ]
    result.append(result[0])  # close the polygon
    return result


def _garantir_sentido_oposto(ref, caminho):
    if (_area_assinada(ref) > 0) == (_area_assinada(caminho) > 0):
        return list(reversed(caminho))
    return caminho


def separar_e_offsetar(contornos, raio):
    # largest area = outer contour; the rest are holes
    ordenados = sorted(contornos, key=lambda c: abs(_area_assinada(c)), reverse=True)
    externo = _offset_caminho(ordenados[0], raio)
    furos = []
    for bruto in ordenados[1:]:
        furo = _offset_caminho(bruto, -raio)
        furo = _garantir_sentido_oposto(externo, furo)
        furos.append(furo)
    return externo, furos


# ============================================================
# READ BOARD OUTLINE FROM PCBNEW
#
# KiCad uses Y-down coordinates internally. Coordinates are made
# relative to the board's Drill/place file origin, then Y is negated
# for conventional machine coordinates (Y-up).
# ============================================================
def get_board_contours(board):
    """Read outline in mm relative to KiCad's Drill/place file origin; machine Y is up."""
    import pcbnew

    origin = board.GetDesignSettings().GetAuxOrigin()

    outlines = pcbnew.SHAPE_POLY_SET()
    try:
        board.GetBoardPolygonOutlines(outlines, True)   # KiCad 8+
    except TypeError:
        board.GetBoardPolygonOutlines(outlines)         # KiCad 6/7

    if outlines.OutlineCount() == 0:
        raise RuntimeError("No board outline found. Check the Edge Cuts layer.")

    contornos = []
    for i in range(outlines.OutlineCount()):
        chain = outlines.Outline(i)
        pts = [(pcbnew.ToMM(chain.CPoint(j).x - origin.x),
                -pcbnew.ToMM(chain.CPoint(j).y - origin.y))
               for j in range(chain.PointCount())]
        if len(pts) >= 3:
            contornos.append(pts)
        for h in range(outlines.HoleCount(i)):
            hole = outlines.Hole(i, h)
            pts = [(pcbnew.ToMM(hole.CPoint(j).x - origin.x),
                    -pcbnew.ToMM(hole.CPoint(j).y - origin.y))
                   for j in range(hole.PointCount())]
            if len(pts) >= 3:
                contornos.append(pts)

    if not contornos:
        raise RuntimeError("Board outline has fewer than 3 points.")

    return contornos


def get_npth_routing_paths(board, tool_diameter):
    """Return circular NPTH center paths suitable for routing with this tool.

    Holes smaller than the cutter and non-circular drilled slots are omitted.
    Returned points use the same drill/place origin and Y-up coordinates as G-code.
    """
    import pcbnew

    origin = board.GetDesignSettings().GetAuxOrigin()
    paths = []
    tolerance = 1e-6

    for footprint in board.GetFootprints():
        for pad in footprint.Pads():
            if pad.GetAttribute() != pcbnew.PAD_ATTRIB_NPTH:
                continue

            drill = pad.GetDrillSize()
            diameter_x = pcbnew.ToMM(drill.x)
            diameter_y = pcbnew.ToMM(drill.y)
            if diameter_x + tolerance < tool_diameter or diameter_y + tolerance < tool_diameter:
                continue

            # Do not approximate an oblong NPTH slot as a circle.
            if abs(diameter_x - diameter_y) > 0.01:
                continue

            diameter = (diameter_x + diameter_y) / 2.0
            position = pad.GetPosition()
            center = (
                pcbnew.ToMM(position.x - origin.x),
                -pcbnew.ToMM(position.y - origin.y),
            )
            radius = max(0.0, (diameter - tool_diameter) / 2.0)

            if radius <= tolerance:
                # A matching-size cutter makes the hole by plunging at its center.
                paths.append([center, center])
                continue

            count = max(24, min(144, int(math.ceil(2.0 * math.pi * radius / 0.25))))
            circle = [
                (
                    center[0] + radius * math.cos(2.0 * math.pi * i / count),
                    center[1] + radius * math.sin(2.0 * math.pi * i / count),
                )
                for i in range(count)
            ]
            circle.append(circle[0])
            paths.append(circle)

    return paths


# ============================================================
# READ DRILL HOLES FROM PCBNEW
#
# Reads all PTH and NPTH pads without translating their coordinates,
# so their G-code positions use the same KiCad Drill/place file origin
# as the outline. Y is inverted for conventional Y-up machine coordinates.
# ============================================================
def get_drill_holes(board, include_pth=True, include_npth=True, include_vias=True):
    """Return (diameter_mm, x, y) for drilled pads and optional through vias."""
    import pcbnew

    origin = board.GetDesignSettings().GetAuxOrigin()

    furos = []
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            attr = pad.GetAttribute()
            if attr == pcbnew.PAD_ATTRIB_PTH and not include_pth:
                continue
            if attr == pcbnew.PAD_ATTRIB_NPTH and not include_npth:
                continue
            if attr not in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH):
                continue
            diameter = pcbnew.ToMM(pad.GetDrillSize().x)
            if diameter <= 0:
                continue
            pos = pad.GetPosition()
            x = pcbnew.ToMM(pos.x - origin.x)
            y = -pcbnew.ToMM(pos.y - origin.y)   # KiCad Y-down -> machine Y-up
            furos.append((diameter, x, y))

    if include_vias:
        for item in board.GetTracks():
            if not isinstance(item, pcbnew.PCB_VIA):
                continue
            # Blind/buried and microvias are not through-holes; don't turn
            # them into full-depth CNC drilling operations.
            if item.GetViaType() != pcbnew.VIATYPE_THROUGH:
                continue
            diameter = pcbnew.ToMM(item.GetDrillValue())
            if diameter <= 0:
                continue
            pos = item.GetPosition()
            x = pcbnew.ToMM(pos.x - origin.x)
            y = -pcbnew.ToMM(pos.y - origin.y)   # KiCad Y-down -> machine Y-up
            furos.append((diameter, x, y))

    if not furos:
        raise RuntimeError("No selected drilled pads or through vias found on this board.")

    return furos


# ============================================================
# DRILL — GROUP AND SORT
# ============================================================
def agrupar_por_diametro(furos):
    """Group (diameter, x, y) list into [(diameter, [(x,y),...]), ...] sorted small to large."""
    grupos = {}
    for diameter, x, y in furos:
        grupos.setdefault(diameter, []).append((x, y))
    chaves = sorted(grupos.keys(), key=lambda d: (d is None, d))
    return [(d, grupos[d]) for d in chaves]


def ordenar_vizinho_mais_proximo(furos, inicio=(0.0, 0.0)):
    """Greedy nearest-neighbour sort to minimise XY travel. O(n²)."""
    restantes = list(furos)
    ordenados = []
    px, py = inicio
    while restantes:
        idx = min(range(len(restantes)),
                  key=lambda i: (restantes[i][0] - px) ** 2 + (restantes[i][1] - py) ** 2)
        px, py = restantes[idx]
        ordenados.append(restantes.pop(idx))
    return ordenados


# ============================================================
# DEPTH PASSES
# ============================================================
def calcular_profundidades(cut_depth, multi_depth):
    if multi_depth <= 0:
        raise ValueError("Depth per pass must be positive")
    eps = 1e-6
    depths = []
    z = 0.0
    while z > cut_depth + eps:
        z -= multi_depth
        if z < cut_depth + eps:
            z = cut_depth
        depths.append(z)
    return depths


# ============================================================
# TABS / SEGMENTS  (cut only)
# ============================================================
def _distancias_acumuladas(caminho):
    cum = [0.0]
    for i in range(len(caminho) - 1):
        x1, y1 = caminho[i]
        x2, y2 = caminho[i + 1]
        cum.append(cum[-1] + math.hypot(x2 - x1, y2 - y1))
    return cum


def _rotacionar_para_meio_do_primeiro_segmento(caminho):
    # rotate closed path so tab 0 falls on a straight segment, not a corner
    x0, y0 = caminho[0]
    x1, y1 = caminho[1]
    meio = ((x0 + x1) / 2, (y0 + y1) / 2)
    return [meio] + caminho[1:-1] + [caminho[0], meio]


def _ponto_na_distancia(caminho, cum, distancia):
    for i in range(len(cum) - 1):
        if cum[i] <= distancia <= cum[i + 1]:
            L = cum[i + 1] - cum[i]
            if L == 0:
                return caminho[i]
            t = (distancia - cum[i]) / L
            x1, y1 = caminho[i]
            x2, y2 = caminho[i + 1]
            return (x1 + (x2 - x1) * t, y1 + (y2 - y1) * t)
    return caminho[-1]


def _snap_tab_to_path(caminho, cum, point):
    px, py = point
    best_distance_sq = float("inf")
    best_along = 0.0
    for i in range(len(cum) - 1):
        x1, y1 = caminho[i]
        x2, y2 = caminho[i + 1]
        dx, dy = x2 - x1, y2 - y1
        length_sq = dx * dx + dy * dy
        if length_sq == 0:
            t = 0.0
        else:
            t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / length_sq))
        qx, qy = x1 + t * dx, y1 + t * dy
        distance_sq = (px - qx) ** 2 + (py - qy) ** 2
        if distance_sq < best_distance_sq:
            best_distance_sq = distance_sq
            best_along = cum[i] + t * math.sqrt(length_sq)
    return best_along, math.sqrt(best_distance_sq)


def _ponto_circular(caminho, cum, distancia):
    perimetro = cum[-1]
    normalizada = distancia % perimetro
    return _ponto_na_distancia(caminho, cum, normalizada)


def _segmento_circular(caminho, cum, inicio, fim):
    perimetro = cum[-1]
    pts = [_ponto_circular(caminho, cum, inicio)]
    vertices = []
    primeiro_ciclo = math.floor(inicio / perimetro) - 1
    ultimo_ciclo = math.ceil(fim / perimetro) + 1
    for ciclo in range(primeiro_ciclo, ultimo_ciclo + 1):
        for i in range(len(cum) - 1):
            distancia = cum[i] + ciclo * perimetro
            if inicio + 1e-9 < distancia < fim - 1e-9:
                vertices.append((distancia, caminho[i]))
    vertices.sort(key=lambda item: item[0])
    pts.extend(point for _distance, point in vertices)
    pts.append(_ponto_circular(caminho, cum, fim))
    return pts


def _segmentos_com_tabs_manuais(caminho, cum, gap_size, tool_diameter, tab_points):
    vao = gap_size + tool_diameter
    perimetro = cum[-1]
    if not tab_points:
        raise ValueError("Manual tab placement requires at least one X,Y point.")

    centros = []
    max_snap_distance = max(5.0, vao * 2.0)
    for point in tab_points:
        distancia, snap_distance = _snap_tab_to_path(caminho, cum, point)
        if snap_distance > max_snap_distance:
            raise ValueError(
                f"Tab point ({point[0]:.3f}, {point[1]:.3f}) mm is "
                f"{snap_distance:.2f} mm from the cut path. Choose a point "
                f"within {max_snap_distance:.2f} mm of the outside edge."
            )
        centros.append(distancia % perimetro)

    centros.sort()
    meio_vao = vao / 2.0
    for i, centro in enumerate(centros):
        proximo = centros[(i + 1) % len(centros)]
        if i == len(centros) - 1:
            proximo += perimetro
        if proximo - centro < vao:
            raise ValueError("Manual tab points are too close together; their tabs overlap.")

    segs = []
    for i, centro in enumerate(centros):
        proximo = centros[(i + 1) % len(centros)]
        if i == len(centros) - 1:
            proximo += perimetro
        inicio_corte = centro + meio_vao
        fim_corte = proximo - meio_vao
        segs.append(_segmento_circular(caminho, cum, inicio_corte, fim_corte))
    return segs


def calcular_segmentos(caminho, gap_size, tool_diameter, num_gaps, tab_points=None):
    vao = gap_size + tool_diameter
    if num_gaps < 1:
        raise ValueError("Number of tabs must be at least 1")
    if tab_points is not None:
        if len(tab_points) != num_gaps:
            raise ValueError(
                f"Enter exactly {num_gaps} manual tab point(s), matching Number of tabs."
            )
        cum = _distancias_acumuladas(caminho)
        if cum[-1] <= 0:
            raise ValueError("Outside cut path has zero length.")
        return _segmentos_com_tabs_manuais(caminho, cum, gap_size, tool_diameter, tab_points)

    caminho = _rotacionar_para_meio_do_primeiro_segmento(caminho)
    cum = _distancias_acumuladas(caminho)
    perimetro = cum[-1]
    espacamento = perimetro / num_gaps
    if vao >= espacamento:
        raise ValueError("Tab size too large for the number of tabs / perimeter")
    segs = []
    for i in range(num_gaps):
        inicio = i * espacamento + vao
        fim = (i + 1) * espacamento
        pts = [_ponto_na_distancia(caminho, cum, inicio)]
        for j in range(1, len(cum) - 1):
            if inicio < cum[j] < fim:
                pts.append(caminho[j])
        pts.append(_ponto_na_distancia(caminho, cum, fim))
        segs.append(pts)
    return segs


# ============================================================
# G-CODE GENERATION — BOARD CUT
# ============================================================
def _add_probe_start(lines, points, options):
    """Add an operator-confirmed GRBL probe cycle at the job's XY center."""
    points = list(points)
    if not points:
        return
    if options["END_Z"] <= 0 or options["PROBE_FEED"] <= 0:
        raise ValueError("End Z / probe travel and probe feed rate must both be positive.")
    probe_travel = options["END_Z"] + 1.0

    x_center = (min(point[0] for point in points) + max(point[0] for point in points)) / 2.0
    y_center = (min(point[1] for point in points) + max(point[1] for point in points)) / 2.0
    lines.extend([
        "(Z probe setup: touch location becomes G54 Z0; no probe-plate offset)",
        "G54",
        "G53 G0 Z0.000",
        f"G0 X{x_center:.3f} Y{y_center:.3f}",
        "G4 P0.5",
        "M0 ;Attach probe clip to the tool and connect the probe plate to the PCB, then resume to probe",
        f"G10 L20 P1 Z{probe_travel:.3f}",
        "(Probe stroke is End Z height plus 1mm from machine Z0)",
        "G38.2 Z0.000 F{:.1f}".format(options["PROBE_FEED"]),
        "G10 L20 P1 Z0.000",
        "G53 G0 Z0.000",
        "M0 ;Remove the probe clip, then resume to start the job",
    ])


def gerar_gcode_corte(segs_externo, furos, profundidades, o):
    lines = []
    add = lines.append

    add("(G-CODE generated BY Gerber2Gcode KiCad Plugin - Board Cut)")
    add("")
    add("G21")          # units in millimetres
    add("G90")          # absolute coordinates
    add("G94")          # feed rate in units per minute
    add("G17")          # XY plane
    add("M5")           # spindle off
    points = [point for path in list(segs_externo) + list(furos) for point in path]
    _add_probe_start(lines, points, o)
    add(f"G0 Z{o['SAFE_Z']:.3f}")
    add(f"M3 S{o['SPINDLE_RPM']}")
    add(f"G04 P{o['DWELL']}")
    add("")

    # holes/cutouts first (closed loop, no tabs)
    for furo in furos:
        for z in profundidades:
            x0, y0 = furo[0]
            add(f"G0 X{x0:.3f} Y{y0:.3f}")
            add(f"G1 Z{z:.3f} F{o['FEED_Z']:.1f}")
            for x, y in furo[1:]:
                add(f"G1 X{x:.3f} Y{y:.3f} F{o['FEED_XY']:.1f}")
            add(f"G0 Z{o['SAFE_Z']:.3f}")

    # outer contour with tabs
    for z in profundidades:
        for seg in segs_externo:
            x0, y0 = seg[0]
            add(f"G0 X{x0:.3f} Y{y0:.3f}")
            add(f"G1 Z{z:.3f} F{o['FEED_Z']:.1f}")
            for x, y in seg[1:]:
                add(f"G1 X{x:.3f} Y{y:.3f} F{o['FEED_XY']:.1f}")
            add(f"G0 Z{o['SAFE_Z']:.3f}")

    add("M5")
    if points:
        x_park = (min(point[0] for point in points) + max(point[0] for point in points)) / 2.0
        y_park = max(point[1] for point in points)
        add("(Park: machine Z home, job X midpoint and job maximum Y)")
        add("G53 G0 Z0.000")
        add(f"G0 X{x_park:.3f} Y{y_park:.3f}")
    else:
        add(f"G0 Z{o['END_Z']:.3f}")
    add("M2")

    return "\n".join(lines)


# ============================================================
# G-CODE GENERATION — DRILL
# ============================================================
def gerar_gcode_furacao(grupos, o):
    lines = []
    add = lines.append

    add("(G-CODE generated BY Gerber2Gcode KiCad Plugin - Drill)")
    add("")
    add("G21")          # units in millimetres
    add("G90")          # absolute coordinates
    add("G94")          # feed rate in units per minute
    add("G17")          # XY plane
    add("M5")           # ensure spindle is off
    points = [point for _diameter, holes in grupos for point in holes]
    _add_probe_start(lines, points, o)
    add(f"G0 Z{o['SAFE_Z']:.3f}")
    add("")

    for diameter, furos in grupos:
        if diameter is None:
            add("(Bit: unknown diameter)")
        else:
            add(f"(Bit: {diameter:.3f}mm - {len(furos)} holes)")
        add("M5")
        add(f"G0 Z{o['TOOLCHANGE_Z']:.3f}")
        add("M0")           # pause: change bit and resume
        add(f"M3 S{o['SPINDLE_RPM']}")
        add(f"G04 P{o['DWELL']}")
        add("")

        for x, y in furos:
            add(f"G0 X{x:.3f} Y{y:.3f}")
            add(f"G1 Z{o['DRILL_DEPTH']:.3f} F{o['FEED_Z']:.1f}")
            add(f"G0 Z{o['SAFE_Z']:.3f}")

        add("")

    add("M5")
    if points:
        x_park = (min(point[0] for point in points) + max(point[0] for point in points)) / 2.0
        y_park = max(point[1] for point in points)
        add("(Park: machine Z home, job X midpoint and job maximum Y)")
        add("G53 G0 Z0.000")
        add(f"G0 X{x_park:.3f} Y{y_park:.3f}")
    else:
        add(f"G0 Z{o['END_Z']:.3f}")
    add("M2")

    return "\n".join(lines)
