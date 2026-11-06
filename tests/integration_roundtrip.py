# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 Alejandro Rebolledo
"""Run explicitly with KiCad 10 Python and its matching Shapely dependency."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'plugin/kicad_eagle_exporter'))
import kicad10_to_eagle as engine
from synthetic_fixture import demo

def main():
    p,Polygon,union,triangulate=engine.load_runtime()
    from shapely.affinity import translate
    result={}
    output=ROOT/'test-output';output.mkdir(exist_ok=True)
    original=demo(output)
    source=output/'prueba_kicad10.kicad_pcb';destination=output/'prueba_kicad10.brd'
    digest=hashlib.sha256(source.read_bytes()).hexdigest()
    report=engine.export_board(source,destination,overwrite=True)
    reimported=p.LoadBoard(str(destination),p.PCB_IO_MGR.EAGLE)
    assert report['board_size_mm']==[30.0,20.0]
    assert report['cutouts']==1 and report['drill_count']==3
    assert hashlib.sha256(source.read_bytes()).hexdigest()==digest
    for layer,name in [(p.F_Cu,'F.Cu'),(p.B_Cu,'B.Cu')]:
        before=engine.board_geometry(original,layer,p,Polygon,union)
        after=translate(engine.board_geometry(reimported,layer,p,Polygon,union),xoff=10,yoff=30)
        distance=before.hausdorff_distance(after)
        assert distance<.015,(name,distance)
        result[name]={'hausdorff_distance_mm':distance,'symmetric_difference_mm2':before.symmetric_difference(after).area}
    result['source_unchanged']=True;result['kicad_version']=p.Version()
    (output/'integration-result.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
