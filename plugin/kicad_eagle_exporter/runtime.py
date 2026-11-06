# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 Alejandro Rebolledo
"""Discover KiCad's own Python and CLI without mixing Python ABIs."""
from __future__ import annotations
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

PACKAGE = Path(__file__).resolve().parent

def python_candidates(platform=None, home=None, environ=None):
    platform=platform or sys.platform;home=Path(home or Path.home());env=os.environ if environ is None else environ
    candidates=[]
    if env.get('KICAD_EAGLE_PYTHON'):candidates.append(Path(env['KICAD_EAGLE_PYTHON']))
    candidates.append(Path(sys.executable))
    if platform=='win32':
        candidates.extend([Path(env.get('ProgramFiles','C:/Program Files'))/'KiCad/10.0/bin/python.exe'])
    elif platform=='darwin':
        for root in (Path('/Applications/KiCad'),home/'Applications/KiCad'):
            for bundle in (root/'KiCad.app',root/'pcbnew.app'):
                candidates.extend(bundle.glob('Contents/Frameworks/Python.framework/Versions/*/bin/python3*'))
                candidates.extend(bundle.glob('Contents/MacOS/python3*'))
        candidates.extend([Path('/usr/local/bin/python3'),Path('/opt/homebrew/bin/python3'),Path('/usr/bin/python3')])
    else:
        candidates.extend([Path('/usr/bin/python3'),Path('/usr/local/bin/python3')])
    path_python=shutil.which('python3') or shutil.which('python')
    if path_python:candidates.append(Path(path_python))
    return list(dict.fromkeys(candidates))

def probe_python(executable):
    code='import sys,json,pcbnew; print(json.dumps({"kicad":pcbnew.Version(),"python":sys.version.split()[0],"executable":sys.executable}))'
    try:
        run=subprocess.run([str(executable),'-c',code],capture_output=True,text=True,timeout=20)
        if run.returncode:return None
        result=json.loads(run.stdout.strip().splitlines()[-1])
        return result if result['kicad'].startswith('10.0.') else None
    except (OSError,ValueError,subprocess.TimeoutExpired,IndexError):return None

def find_python(explicit=None):
    candidates=[Path(explicit)] if explicit else python_candidates()
    for candidate in candidates:
        if candidate.is_file() and probe_python(candidate):return candidate
    raise RuntimeError('No se encontro un Python con pcbnew de KiCad 10. Usa --python RUTA o KICAD_EAGLE_PYTHON. Consulta docs/INSTALL.md.')

def require_pcbnew():
    try:
        import pcbnew
    except ImportError:
        python=find_python()
        if Path(sys.executable).resolve()==python.resolve():raise RuntimeError('Este Python no puede importar pcbnew.')
        raise SystemExit(subprocess.call([str(python),str(Path(sys.argv[0]).resolve()),*sys.argv[1:]]))
    if not pcbnew.Version().startswith('10.0.'):
        raise RuntimeError('Se requiere KiCad 10.0.x; detectado '+pcbnew.Version())
    return pcbnew

def find_cli():
    name='kicad-cli.exe' if sys.platform=='win32' else 'kicad-cli'
    candidates=[]
    if os.environ.get('KICAD_EAGLE_CLI'):candidates.append(Path(os.environ['KICAD_EAGLE_CLI']))
    candidates.append(Path(sys.executable).parent/name)
    try:
        import pcbnew
        for parent in Path(pcbnew.__file__).resolve().parents:
            candidates.extend([parent/name,parent/'bin'/name,parent/'MacOS'/name])
    except ImportError:pass
    discovered=shutil.which(name)
    if discovered:candidates.append(Path(discovered))
    candidates.extend([Path('/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli'),Path('/usr/bin/kicad-cli')])
    for candidate in dict.fromkeys(candidates):
        if not candidate.is_file():continue
        try:
            run=subprocess.run([str(candidate),'--version'],capture_output=True,text=True,timeout=15)
            if run.returncode==0 and run.stdout.strip().startswith('10.0.'):return candidate
        except (OSError,subprocess.TimeoutExpired):continue
    raise RuntimeError('No se encontro kicad-cli 10.0.x. Configura KICAD_EAGLE_CLI con su ruta.')

def plugin_directory(platform=None,home=None,environ=None):
    platform=platform or sys.platform;home=Path(home or Path.home());env=os.environ if environ is None else environ
    if env.get('KICAD_DOCUMENTS_HOME'):root=Path(env['KICAD_DOCUMENTS_HOME'])
    elif platform in ('win32','darwin'):root=home/'Documents'/'KiCad'
    else:root=Path(env.get('XDG_DATA_HOME',str(home/'.local/share')))/'kicad'
    return root/'10.0/scripting/plugins'/'kicad_eagle_exporter'
