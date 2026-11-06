#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 Alejandro Rebolledo
"""Build source and PCM ZIP archives, excluding binary dependencies and user PCBs."""
from pathlib import Path
import hashlib
import json
import zipfile

ROOT=Path(__file__).resolve().parents[1]

def included(path):
    return not any(part in ('_deps','__pycache__','.git','dist','build','test-output') for part in path.parts) and path.suffix not in ('.pyc','.zip')

def build():
    dist=ROOT/'dist';dist.mkdir(exist_ok=True)
    metadata=json.loads((ROOT/'metadata.json').read_text(encoding='utf8'))
    version=metadata['versions'][0]['version']
    package=ROOT/'plugin/kicad_eagle_exporter'
    pcm=dist/f'kicad-eagle-exporter-{version}-pcm.zip'
    with zipfile.ZipFile(pcm,'w',zipfile.ZIP_DEFLATED) as archive:
        archive.write(ROOT/'metadata.json','metadata.json')
        for notice in ('LICENSE','NOTICE.md'):archive.write(ROOT/notice,'plugins/'+notice)
        for path in sorted(package.rglob('*')):
            if path.is_file() and included(path.relative_to(ROOT)):
                archive.write(path,'plugins/'+path.relative_to(package).as_posix())
    source=dist/f'kicad-eagle-exporter-{version}-source.zip'
    with zipfile.ZipFile(source,'w',zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(ROOT.rglob('*')):
            relative=path.relative_to(ROOT)
            if path.is_file() and included(relative):archive.write(path,'kicad-eagle-exporter/'+relative.as_posix())
    checksums={path.name:hashlib.sha256(path.read_bytes()).hexdigest() for path in (pcm,source)}
    (dist/'SHA256SUMS.txt').write_text(''.join(f'{digest}  {name}\n' for name,digest in checksums.items()),encoding='utf8')
    print(json.dumps({'archives':[str(pcm),str(source)],'sha256':checksums},indent=2))
    return pcm,source

if __name__=='__main__':build()
