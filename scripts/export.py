#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 Alejandro Rebolledo
"""Portable launcher: export.py board|project INPUT [exporter options]."""
import argparse
import importlib.util
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
PACKAGE=ROOT/'plugin/kicad_eagle_exporter'
spec=importlib.util.spec_from_file_location('eagle_runtime',PACKAGE/'runtime.py')
runtime=importlib.util.module_from_spec(spec);spec.loader.exec_module(runtime)
parser=argparse.ArgumentParser(description=__doc__,add_help=False)
parser.add_argument('--python');parser.add_argument('mode',choices=['board','project'],nargs='?')
args,rest=parser.parse_known_args()
if args.mode is None:
    parser.print_help();raise SystemExit(0)
try:python=runtime.find_python(args.python)
except RuntimeError as exc:parser.error(str(exc))
engine=PACKAGE/('kicad10_project_to_eagle.py' if args.mode=='project' else 'kicad10_to_eagle.py')
raise SystemExit(subprocess.call([str(python),str(engine),*rest]))
