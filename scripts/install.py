#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 Alejandro Rebolledo
"""Install into a user plugin directory; dependencies match KiCad's Python."""
import argparse
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'plugin/kicad_eagle_exporter'
spec=importlib.util.spec_from_file_location('eagle_runtime',SOURCE/'runtime.py')
runtime=importlib.util.module_from_spec(spec);spec.loader.exec_module(runtime)

def install(destination,python,skip_dependencies=False):
    destination=Path(destination).expanduser().resolve()
    destination.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='eagle-plugin-') as temporary:
        staged=Path(temporary)/'kicad_eagle_exporter'
        shutil.copytree(SOURCE,staged,ignore=shutil.ignore_patterns('_deps','__pycache__','*.pyc'))
        for notice in ('LICENSE','NOTICE.md'):
            if (ROOT/notice).exists():shutil.copy2(ROOT/notice,staged/notice)
        if not skip_dependencies:
            subprocess.run([str(python),'-m','pip','install','--only-binary=:all:','--target',str(staged/'_deps'),
                            '-r',str(ROOT/'requirements.txt')],check=True)
            probe='import sys;sys.path.insert(0,sys.argv[1]);import pcbnew,shapely;from shapely import constrained_delaunay_triangles;print(pcbnew.Version(),shapely.__version__)'
            subprocess.run([str(python),'-c',probe,str(staged/'_deps')],check=True)
        if destination.exists():
            # Preserve unknown user files and prior dependency files on updates.
            shutil.copytree(staged,destination,dirs_exist_ok=True)
        else:shutil.copytree(staged,destination)
    return destination

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--python',help='Python executable that imports pcbnew 10.0.x')
    parser.add_argument('--plugin-dir',type=Path,help='Exact destination folder; includes kicad_eagle_exporter')
    parser.add_argument('--skip-dependencies',action='store_true',help='For users who already installed Shapely for KiCad Python')
    parser.add_argument('--dry-run',action='store_true')
    args=parser.parse_args()
    try:
        python=runtime.find_python(args.python)
        destination=args.plugin_dir or runtime.plugin_directory()
        print('KiCad Python:',python);print('Plugin directory:',destination)
        if args.dry_run:return 0
        install(destination,python,args.skip_dependencies)
    except (RuntimeError,OSError,subprocess.CalledProcessError) as exc:
        print('Installation failed:',exc,file=sys.stderr);return 1
    print('Installed. Restart PCB Editor or refresh external plugins.');return 0

if __name__=='__main__':raise SystemExit(main())
