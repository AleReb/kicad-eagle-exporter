#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 Alejandro Rebolledo
"""KiCad 10 -> EAGLE XML fabrication snapshot (not an editable CAD migration).

Run with KiCad's Python. Windows: exportar.cmd input.kicad_pcb [output.brd]
Dependencies are local to _deps; the source board is never saved or modified.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
try:
    from . import runtime
except ImportError:
    import runtime
for dependency_path in (runtime.plugin_directory()/'_deps',HERE/'_deps'):
    if dependency_path.is_dir():sys.path.insert(0,str(dependency_path))
if os.environ.get('KICAD_EAGLE_DEPS'):sys.path.insert(0,os.environ['KICAD_EAGLE_DEPS'])


def load_runtime():
    pcbnew=runtime.require_pcbnew()
    try:
        from shapely import constrained_delaunay_triangles
        from shapely.geometry import Polygon
        from shapely.ops import unary_union
    except ImportError as exc:
        raise RuntimeError("Faltan dependencias para el Python de KiCad. Ejecuta scripts/install.py; consulta docs/INSTALL.md.") from exc
    return pcbnew, Polygon, unary_union, constrained_delaunay_triangles


def polyset_geometry(ps, Polygon, unary_union):
    """Read KiCad's polygons including holes, in millimetres."""
    def ring(chain):
        return [(chain.CPoint(i).x / 1e6, chain.CPoint(i).y / 1e6)
                for i in range(chain.PointCount())]
    polys = []
    for i in range(ps.OutlineCount()):
        shell = ring(ps.COutline(i))
        if len(shell) < 3:
            continue
        holes = [ring(ps.CHole(i, j)) for j in range(ps.HoleCount(i))]
        poly = Polygon(shell, holes)
        if not poly.is_valid:
            raise ValueError("KiCad produjo un polígono inválido. No se reparará automáticamente.")
        if not poly.is_empty:
            polys.append(poly)
    return unary_union(polys)


def board_geometry(board, layer, p, Polygon, unary_union):
    ps = p.SHAPE_POLY_SET()
    board.ConvertBrdLayerToPolygonalContours(layer, ps)
    # Filled zones may be stored as fractured rings with doubled bridge edges.
    # Restore holes and union overlaps using KiCad's own polygon engine first.
    ps.Unfracture()
    ps.Simplify()
    return polyset_geometry(ps, Polygon, unary_union)


def element(parent, tag, **attrs):
    return ET.SubElement(parent, tag, {k: str(v) for k, v in attrs.items()})


def fmt(value):
    # KiCad integer coordinates have a resolution of 1 nm.
    return f"{value:.6f}".rstrip("0").rstrip(".") or "0"


def net_name_information(board):
    """Non-blocking observations about distinct nets differing by whitespace."""
    import re
    groups = {}
    nets = {}
    for footprint in board.GetFootprints():
        for pad in footprint.Pads():
            name = pad.GetNetname()
            if not name:
                continue
            entry = nets.setdefault(name, {"source_name": name, "pads": [], "track_segments": 0})
            entry["pads"].append({"component": footprint.GetReference(), "pin": pad.GetNumber()})
    for track in board.GetTracks():
        name = track.GetNetname()
        if name:
            nets.setdefault(name, {"source_name": name, "pads": [], "track_segments": 0})["track_segments"] += 1
    for name in nets:
        groups.setdefault(re.sub(r'\s+', '', name), []).append(name)
    result = []
    for key, names in sorted(groups.items()):
        if len(names) < 2:
            continue
        related = []
        for name in sorted(names):
            entry = dict(nets[name])
            entry["pads"] = sorted(entry["pads"], key=lambda pad: (pad["component"], pad["pin"]))
            entry["single_pad_without_tracks"] = len(entry["pads"]) == 1 and entry["track_segments"] == 0
            related.append(entry)
        isolated = [f"{entry['pads'][0]['component']} pin {entry['pads'][0]['pin']}" for entry in related if entry["single_pad_without_tracks"]]
        message = "Redes distintas que solo se diferencian por espacios: " + ', '.join(repr(name) for name in sorted(names)) + "."
        if isolated:
            message += " Pads en una red de un solo pad y sin pistas: " + ', '.join(isolated) + ". Pueden no aparecer como conexiones pendientes en KiCad."
        message += " Se conservan separadas; revisar la intención del diseño. Esta nota no bloquea la exportación."
        result.append({"code": "net_names_differ_only_by_whitespace", "severity": "info", "message": message, "nets": related})
    return result


def native_copper(board, outboard, signals, plain, xy, p):
    """Use standard Eagle pads/traces for the conservative, native MVP."""
    if any(not z.GetIsRuleArea() for z in board.Zones()):
        raise ValueError("El modo nativo aún no admite zonas. Usa --snapshot para una prueba experimental de cobre plano.")
    for item in list(board.GetDrawings()) + [g for fp in board.GetFootprints() for g in fp.GraphicalItems()]:
        if item.GetLayer() in (p.F_Cu,p.B_Cu):
            raise ValueError("Gráficos de cobre requieren el modo experimental --snapshot.")
    library = element(outboard.find("libraries"),"library",name="KiCadFabrication")
    packages = element(library,"packages")
    elements = outboard.find("elements")
    nets={}
    def net(item):
        name=item.GetNetname() or "FAB_UNCONNECTED"
        if name not in nets:
            nets[name]=element(signals,"signal",name=name,**{"class":0})
        return nets[name]
    pad_count=0
    composite_pad_count=0
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            size=pad.GetSize(); drill=pad.GetDrillSize()
            if pad.GetOffset().x or pad.GetOffset().y:
                raise ValueError("Pads con taladro desplazado requieren --snapshot.")
            if pad.GetAttribute()==p.PAD_ATTRIB_NPTH:
                # Already emitted as a plain hole; this prototype rejects NPTH copper.
                if size.x>drill.x or size.y>drill.y:
                    raise ValueError("NPTH con cobre requiere --snapshot.")
                continue
            if pad.GetAttribute() not in (p.PAD_ATTRIB_PTH,p.PAD_ATTRIB_SMD):
                raise ValueError("Tipo de pad no soportado en modo nativo.")
            shape=pad.GetShape()
            circular=shape==p.PAD_SHAPE_CIRCLE or (shape==p.PAD_SHAPE_OVAL and size.x==size.y)
            square=shape==p.PAD_SHAPE_RECT and size.x==size.y
            composite=False
            if pad.GetAttribute()==p.PAD_ATTRIB_PTH:
                composite=not ((circular or square) and size.x==size.y)
                if composite and shape not in (p.PAD_SHAPE_RECT,p.PAD_SHAPE_OVAL,p.PAD_SHAPE_ROUNDRECT):
                    raise ValueError("Forma de pad pasante requiere --snapshot.")
                if not pad.IsOnLayer(p.F_Cu) or not pad.IsOnLayer(p.B_Cu):
                    raise ValueError("Pad pasante con cobre asimétrico requiere --snapshot.")
            elif shape not in (p.PAD_SHAPE_RECT,p.PAD_SHAPE_OVAL,p.PAD_SHAPE_ROUNDRECT,p.PAD_SHAPE_CIRCLE):
                raise ValueError("Forma de pad SMD requiere --snapshot.")
            pad_count+=1
            identifier=f"P{pad_count}"
            package=element(packages,"package",name=identifier)
            common={"name":"1","x":"0","y":"0","rot":"R0","stop":"no","thermals":"no"}
            # Eagle stores roundness as an integer percentage. Record its
            # quantization through the independent geometry comparison.
            roundness=int(round(100 if shape in (p.PAD_SHAPE_OVAL,p.PAD_SHAPE_CIRCLE) else
                       200*pad.GetRoundRectRadiusRatio() if shape==p.PAD_SHAPE_ROUNDRECT else 0))
            contacts=['1']
            if pad.GetAttribute()==p.PAD_ATTRIB_PTH:
                element(package,"pad",**common,drill=fmt(drill.x/1e6),diameter=fmt(min(size.x,size.y)/1e6),
                        shape="square" if square and not composite else "round")
                if composite:
                    # The inscribed round PTH carries the hole. Two overlapping
                    # native SMD lands preserve the exact outer copper shape.
                    # All three contacts belong to the original electrical net.
                    composite_pad_count+=1
                    for layer,suffix in [(1,'TOP'),(16,'BOTTOM')]:
                        cname='LAND_'+suffix
                        element(package,'smd',name=cname,x=0,y=0,dx=fmt(size.x/1e6),dy=fmt(size.y/1e6),
                                layer=layer,roundness=fmt(roundness),rot='R0',stop='no',cream='no',thermals='no')
                        contacts.append(cname)
            else:
                layer=1 if pad.IsOnLayer(p.F_Cu) else 16 if pad.IsOnLayer(p.B_Cu) else None
                if layer is None: raise ValueError("SMD sin capa de cobre externa.")
                element(package,"smd",**common,dx=fmt(size.x/1e6),dy=fmt(size.y/1e6),layer=layer,cream="no",roundness=fmt(roundness))
            pos=pad.GetPosition(); x,y=xy(pos.x/1e6,pos.y/1e6)
            element(elements,"element",name=identifier,library="KiCadFabrication",package=identifier,
                    value=f"{fp.GetReference()}:{pad.GetNumber()}",x=x,y=y,
                    # KiCad pad angles and Eagle rotations are both positive
                    # counterclockwise in their displayed board coordinates.
                    rot="R"+fmt(pad.GetOrientationDegrees()%360))
            for contact in contacts:
                element(net(pad),"contactref",element=identifier,pad=contact)
    track_count=via_count=0
    for track in board.GetTracks():
        signal=net(track)
        if isinstance(track,p.PCB_VIA):
            if track.GetWidth(p.F_Cu)!=track.GetWidth(p.B_Cu):
                raise ValueError("Vía con diámetros diferentes por cara requiere --snapshot.")
            pos=track.GetPosition(); x,y=xy(pos.x/1e6,pos.y/1e6)
            element(signal,"via",x=x,y=y,extent="1-16",drill=fmt(track.GetDrillValue()/1e6),
                    diameter=fmt(track.GetWidth(p.F_Cu)/1e6),shape="round",alwaysstop="no")
            via_count+=1
            continue
        a,b=track.GetStart(),track.GetEnd(); x1,y1=xy(a.x/1e6,a.y/1e6); x2,y2=xy(b.x/1e6,b.y/1e6)
        attrs={"x1":x1,"y1":y1,"x2":x2,"y2":y2,"width":fmt(track.GetWidth()/1e6),
               "layer":1 if track.GetLayer()==p.F_Cu else 16}
        if isinstance(track,p.PCB_ARC):
            m=track.GetMid(); u=(a.x-m.x,a.y-m.y); v=(b.x-m.x,b.y-m.y)
            angle=math.acos(max(-1,min(1,(u[0]*v[0]+u[1]*v[1])/(math.hypot(*u)*math.hypot(*v)))))
            cross=(m.x-a.x)*(b.y-a.y)-(m.y-a.y)*(b.x-a.x)
            attrs['curve']=fmt(math.degrees(2*(math.pi-angle))*(1 if cross<0 else -1))
        element(signal,"wire",**attrs); track_count+=1
    # PTH pads/vias carry their own drills; retain only true mechanical holes.
    pth_positions={(round(pad.GetPosition().x/1e6,6),round(pad.GetPosition().y/1e6,6))
                   for fp in board.GetFootprints() for pad in fp.Pads() if pad.GetAttribute()==p.PAD_ATTRIB_PTH}
    pth_positions.update((round(t.GetPosition().x/1e6,6),round(t.GetPosition().y/1e6,6))
                         for t in board.GetTracks() if isinstance(t,p.PCB_VIA))
    transformed={xy(x,y) for x,y in pth_positions}
    for hole in list(plain.findall('hole')):
        if (hole.get('x'),hole.get('y')) in transformed: plain.remove(hole)
    return {"pads":pad_count,"composite_pth_pads":composite_pad_count,"tracks_including_arcs":track_count,"vias":via_count,"nets":len(nets)}


def export_board(source, destination, *, refill=True, overwrite=False, snapshot=False):
    p, Polygon, unary_union, triangulate = load_runtime()
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if source == destination:
        raise ValueError("La salida debe ser distinta del archivo original.")
    if source.suffix.lower() != ".kicad_pcb" or not source.is_file():
        raise ValueError("La entrada debe ser una placa .kicad_pcb existente.")
    if destination.suffix.lower() != ".brd":
        raise ValueError("La salida debe tener extensión .brd.")
    report_path = destination.with_suffix(".report.json")
    if not overwrite and (destination.exists() or report_path.exists()):
        raise ValueError("La salida o su informe ya existen. Usa otro nombre o --overwrite.")
    board = p.LoadBoard(str(source))
    if board.GetCopperLayerCount() != 2:
        raise ValueError("Solo se admiten F.Cu/B.Cu. No se descartan capas internas.")
    outline_ps = p.SHAPE_POLY_SET()
    if not board.GetBoardPolygonOutlines(outline_ps, False):
        raise ValueError("Edge.Cuts debe formar un contorno cerrado y válido.")
    outline = polyset_geometry(outline_ps, Polygon, unary_union)
    if outline.geom_type != "Polygon" or outline.is_empty:
        raise ValueError("Se requiere una sola placa; no se admiten islas separadas.")
    drills = {}
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            size = pad.GetDrillSize()
            if not size.x and not size.y:
                continue
            if size.x != size.y or pad.GetDrillShape() != p.PAD_DRILL_SHAPE_CIRCLE:
                raise ValueError(f"Agujero ranurado no soportado: {fp.GetReference()} pad {pad.GetNumber()}.")
            pos = pad.GetPosition()
            drills[(pos.x, pos.y, size.x)] = "pad"
    straight_tracks = []
    for track in board.GetTracks():
        if isinstance(track, p.PCB_VIA):
            if track.GetViaType() != p.VIATYPE_THROUGH:
                raise ValueError("No se admiten vías ciegas, enterradas ni microvías.")
            pos = track.GetPosition()
            drills[(pos.x, pos.y, track.GetDrillValue())] = "via"
        elif not isinstance(track, p.PCB_ARC):
            straight_tracks.append(track)
    # Refill only the in-memory board. Never call SaveBoard on the source.
    if refill and len(board.Zones()):
        p.ZONE_FILLER(board).Fill(board.Zones())
    if not refill:
        for zone in board.Zones():
            if not zone.GetIsRuleArea() and not zone.IsFilled():
                raise ValueError("Hay zonas sin relleno. Ejecuta sin --no-refill.")
    xmin, ymin, xmax, ymax = outline.bounds

    def xy(x, y):
        # One reflection only: KiCad Y down -> Eagle Y up. Bottom is NOT mirrored.
        return fmt(x - xmin), fmt(ymax - y)

    root = ET.Element("eagle", version="7.7.0")
    drawing = element(root, "drawing")
    element(drawing, "settings")
    element(drawing, "grid", distance="0.1", unitdist="mm", unit="mm", display="no")
    layers = element(drawing, "layers")
    for number, name, color in [(1,"Top",4),(16,"Bottom",1),(17,"Pads",2),
                                (18,"Vias",2),(20,"Dimension",15),(21,"tPlace",7),(22,"bPlace",7),
                                (25,"tNames",7),(26,"bNames",7),(27,"tValues",7),(28,"bValues",7),
                                (44,"Drills",7),(45,"Holes",7),(51,"tDocu",7),(52,"bDocu",7)]:
        element(layers, "layer", number=number, name=name, color=color, fill=1, visible="yes", active="yes")
    outboard = element(drawing, "board")
    element(outboard, "description").text = (
        "KiCad 10 fabrication export. No schematic or original footprint library semantics. "
        "Experimental: validate import and CAM in Bantam before fabrication.")
    plain = element(outboard, "plain")
    for ring in [outline.exterior, *outline.interiors]:
        coords = list(ring.coords)
        for a, b in zip(coords, coords[1:]):
            x1, y1 = xy(*a); x2, y2 = xy(*b)
            element(plain, "wire", x1=x1, y1=y1, x2=x2, y2=y2, width="0", layer=20)
    for x, y, diameter in sorted(drills):
        xx, yy = xy(x / 1e6, y / 1e6)
        element(plain, "hole", x=xx, y=yy, drill=fmt(diameter / 1e6))
    element(outboard, "libraries")
    element(outboard, "attributes")
    element(outboard, "variantdefs")
    classes = element(outboard, "classes")
    element(classes, "class", number=0, name="default", width=0, drill=0)
    rules = element(outboard, "designrules", name="KiCad fabrication snapshot")
    element(rules, "param", name="layerSetup", value="(1*16)")
    element(rules, "param", name="mdWireWire", value="0mil")
    element(outboard, "autorouter")
    element(outboard, "elements")
    signals = element(outboard, "signals")
    report = {
        "status": "experimental_unverified_in_bantam", "kicad_version": p.Version(),
        "source": str(source), "output": str(destination),
        "board_size_mm": [xmax-xmin, ymax-ymin], "cutouts": len(outline.interiors),
        "drill_count": len(drills), "zone_count": len(board.Zones()), "refill": refill,
        "coordinate_transform": {"x": "source_x - xmin", "y": "ymax - source_y",
                                 "xmin_mm": xmin, "ymax_mm": ymax},
        "layers": {}, "mode": "snapshot" if snapshot else "native", "notes": [],
        "limitations": [
            "Exportación de fabricación: sin esquemático ni agrupación de pads en componentes originales.",
            "Contornos curvos y cobre aproximados por la poligonización de KiCad.",
            "No exporta serigrafía, máscara, pasta, modelos 3D ni reglas de diseño originales.",
            "No calcula herramientas, profundidad, origen de máquina ni G-code.",
        ]}
    report['informational_notes'] = net_name_information(board)
    report['notes'].extend(note['message'] for note in report['informational_notes'])
    if not snapshot:
        report['native_objects']=native_copper(board,outboard,signals,plain,xy,p)
        if report['native_objects']['composite_pth_pads']:
            report['notes'].append("Pads pasantes complejos: taladro nativo y cobre adicional conectado a la misma red. Redondez expresada en porcentajes enteros de Eagle.")
    else:
        report['limitations'].extend([
            "Snapshot: cobre en triángulos de ancho cero; aceptación en Bantam pendiente.",
            "Snapshot: redes aplanadas y agujeros exportados como hole mecánico."])
    total_area = 0.0
    for layer, eagle_layer, name in [(p.F_Cu,1,"F.Cu"),(p.B_Cu,16,"B.Cu")]:
        geom = board_geometry(board, layer, p, Polygon, unary_union)
        if geom.is_empty:
            report["layers"][name] = {"copper_area_mm2": 0, "triangles": 0}
            continue
        if not outline.buffer(0.00001).covers(geom):
            report['notes'].append(f"{name}: cobre en el exterior del contorno o en un recorte; se conserva sin modificar.")
        total_area += geom.area
        triangles = list(triangulate(geom).geoms)
        rebuilt = unary_union(triangles)
        error = geom.symmetric_difference(rebuilt).area
        if error > max(1e-8, geom.area * 1e-10):
            raise ValueError(f"La triangulación altera cobre de {name}: {error} mm².")
        if not snapshot:
            report['layers'][name]={"copper_area_mm2":geom.area}
            continue
        signal = element(signals, "signal", name=f"FAB_{name.replace('.', '_')}", **{"class": 0})
        # Keep genuine straight traces as wires for older importers. They already
        # exist in the flattened copper, so this adds no invented geometry.
        wire_count = 0
        for track in straight_tracks:
            if track.GetLayer() != layer:
                continue
            a, b = track.GetStart(), track.GetEnd()
            x1,y1 = xy(a.x/1e6,a.y/1e6); x2,y2 = xy(b.x/1e6,b.y/1e6)
            element(signal,"wire",x1=x1,y1=y1,x2=x2,y2=y2,width=fmt(track.GetWidth()/1e6),layer=eagle_layer)
            wire_count += 1
        for tri in triangles:
            polygon = element(signal, "polygon", width="0", layer=eagle_layer,
                              isolate="0", thermals="no", orphans="yes", rank=1)
            for x, y in list(tri.exterior.coords)[:-1]:
                xx, yy = xy(x, y)
                element(polygon, "vertex", x=xx, y=yy)
        report["layers"][name] = {"copper_area_mm2": geom.area,
            "triangles": len(triangles), "native_straight_wires": wire_count,
            "triangulation_error_mm2": error}
    if not total_area:
        raise ValueError("La placa no contiene cobre exportable.")
    element(outboard, "errors")
    ET.indent(root, space="  ")
    xml = '<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE eagle SYSTEM "eagle.dtd">\n'
    xml += ET.tostring(root, encoding="unicode") + "\n"
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Conversion must finish successfully before any output is committed.
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=destination.parent,
                                     suffix=".tmp", delete=False) as f:
        f.write(xml)
        temporary = Path(f.name)
    try:
        if not overwrite and destination.exists():
            raise ValueError("La salida apareció durante la conversión; no se sobrescribe.")
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description="Exporta una instantánea de fabricación KiCad 10 a Eagle .brd.")
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path, nargs="?")
    parser.add_argument("--no-refill", action="store_true", help="Utilizar los rellenos guardados, sin recalcular.")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--snapshot", action="store_true", help="Experimental: cobre aplanado, incluyendo zonas y pads complejos.")
    args = parser.parse_args()
    output = args.output or args.input.with_name(args.input.stem + "_bantam.brd")
    try:
        report = export_board(args.input, output, refill=not args.no_refill, overwrite=args.overwrite,snapshot=args.snapshot)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(f"Generado: {report['output']}")
    print(f"Placa: {report['board_size_mm']} mm; agujeros: {report['drill_count']}")
    print("Prototipo: verifica la geometria y las trayectorias en Bantam antes de cortar.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
