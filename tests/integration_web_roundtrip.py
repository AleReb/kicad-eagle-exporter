# SPDX-License-Identifier: GPL-3.0-only
"""Optional native geometry check for JavaScript output, using KiCad Python.

Usage: python tests/integration_web_roundtrip.py source.kicad_pcb output.brd
Requires the existing plugin's KiCad/Shapely runtime; never shipped to the browser.
"""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'plugin/kicad_eagle_exporter'))
import kicad10_to_eagle as engine
from kicad10_project_to_eagle import eagle_net_names


def main():
    p, Polygon, union, _ = engine.load_runtime()
    from shapely.affinity import translate
    source = p.LoadBoard(sys.argv[1])
    target = p.LoadBoard(sys.argv[2], p.PCB_IO_MGR.EAGLE)
    result = {'components': len(list(target.GetFootprints())), 'tracks': len(list(target.GetTracks()))}
    expected = {f.GetReference() for f in source.GetFootprints() if any(pad.GetAttribute() != p.PAD_ATTRIB_NPTH for pad in f.Pads())}
    actual = {f.GetReference() for f in target.GetFootprints()}
    assert expected == actual, (expected, actual)
    # EAGLE import can choose its own drawing origin. Determine one translation
    # from a known physical pad, then compare both complete copper layers.
    ref = next(f.GetReference() for f in source.GetFootprints() if list(f.Pads()))
    before_fp = next(f for f in source.GetFootprints() if f.GetReference() == ref)
    after_fp = next(f for f in target.GetFootprints() if f.GetReference() == ref)
    first = next(iter(before_fp.Pads()))
    matching = next(x for x in after_fp.Pads() if x.GetNumber() == first.GetNumber())
    dx = (first.GetPosition().x - matching.GetPosition().x) / 1e6
    dy = (first.GetPosition().y - matching.GetPosition().y) / 1e6
    for layer, name in [(p.F_Cu, 'F.Cu'), (p.B_Cu, 'B.Cu')]:
        before = engine.board_geometry(source, layer, p, Polygon, union)
        after = translate(engine.board_geometry(target, layer, p, Polygon, union), xoff=dx, yoff=dy)
        distance = before.hausdorff_distance(after)
        assert distance < .015, (name, distance)
        result[name] = {'hausdorff_distance_mm': distance, 'symmetric_difference_mm2': before.symmetric_difference(after).area}
    # Every copper contact, including the extra lands used for composite pads,
    # must remain on the original physical pad's net after EAGLE reimport.
    source_nets = {(fp.GetReference(), pad.GetNumber()): pad.GetNetname() for fp in source.GetFootprints() for pad in fp.Pads()}
    names = eagle_net_names(name for name in source_nets.values() if name)
    for fp in target.GetFootprints():
        for pad in fp.Pads():
            number = pad.GetNumber().split('__')[0]
            key = (fp.GetReference(), number)
            if key in source_nets and source_nets[key]:
                assert names[source_nets[key]] == pad.GetNetname(), (key, source_nets[key], pad.GetNetname())
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
