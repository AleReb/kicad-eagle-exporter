# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 Alejandro Rebolledo
"""Small native dialog around the tested saved-file conversion engines."""
from pathlib import Path
import json
import traceback
import pcbnew
import wx

class EagleExportAction(pcbnew.ActionPlugin):
    def defaults(self):
        self.name='Exportar a Eagle / Bantam'
        self.category='Fabrication'
        self.description='Exportar PCB o proyecto vinculado a Eagle XML (KiCad 10)'
        self.show_toolbar_button=True
        self.icon_file_name=str(Path(__file__).with_name('icon.png'))

    def Run(self):
        board=pcbnew.GetBoard()
        if not board or not board.GetFileName():
            wx.MessageBox('Abre y guarda una placa antes de exportar.','Exportar a Eagle',wx.OK|wx.ICON_INFORMATION);return
        if board.IsModified():
            wx.MessageBox('Guarda los cambios de la placa antes de exportar. Para exportar el proyecto, guarda tambien el esquematico.','Exportar a Eagle',wx.OK|wx.ICON_INFORMATION);return
        source=Path(board.GetFileName())
        chooser=wx.SingleChoiceDialog(None,'Se exportan los archivos guardados. El original se conserva intacto.','Exportar a Eagle',
            ['Solo placa para Bantam / Eagle','Placa + esquematico + biblioteca para Eagle / Fusion'])
        try:
            if chooser.ShowModal()!=wx.ID_OK:return
            project=chooser.GetSelection()==1
        finally:chooser.Destroy()
        schematic=source.with_suffix('.kicad_sch')
        if project:
            sch=wx.FileDialog(None,'Selecciona el esquematico guardado',defaultDir=str(source.parent),defaultFile=schematic.name,
                              wildcard='KiCad schematic (*.kicad_sch)|*.kicad_sch',style=wx.FD_OPEN|wx.FD_FILE_MUST_EXIST)
            try:
                if sch.ShowModal()!=wx.ID_OK:return
                schematic=Path(sch.GetPath())
            finally:sch.Destroy()
        save=wx.FileDialog(None,'Guardar exportacion Eagle',defaultDir=str(source.parent),
            defaultFile=source.stem+'_eagle.brd',wildcard='Eagle board (*.brd)|*.brd',style=wx.FD_SAVE|wx.FD_OVERWRITE_PROMPT)
        try:
            if save.ShowModal()!=wx.ID_OK:return
            destination=Path(save.GetPath()).with_suffix('.brd')
        finally:save.Destroy()
        if project:
            affected=[destination.with_suffix(ext) for ext in ('.sch','.lbr','.project-report.json')]
            if any(path.exists() for path in affected):
                if wx.MessageBox('Se reemplazaran tambien el esquematico, la biblioteca y el informe con ese nombre. Continuar?',
                    'Actualizar exportacion',wx.YES_NO|wx.NO_DEFAULT|wx.ICON_QUESTION)!=wx.YES:return
        busy=wx.BusyInfo('Exportando el diseno. Espera un momento...')
        try:
            if project:
                from .kicad10_project_to_eagle import export_project
                report=export_project(schematic,source,destination.with_suffix(''),overwrite=True)
                report_path=destination.with_suffix('.project-report.json')
            else:
                from .kicad10_to_eagle import export_board
                report=export_board(source,destination,overwrite=True)
                report_path=destination.with_suffix('.report.json')
        except Exception as exc:
            del busy
            details=str(exc)
            if 'dependencias' in details or isinstance(exc,ImportError):
                details+='\n\nEjecuta scripts/install.py con el Python de KiCad para instalar las dependencias de este sistema.'
            wx.MessageBox(details,'No se pudo exportar',wx.OK|wx.ICON_ERROR);return
        del busy
        notes=report.get('informational_notes',[])
        suffix=f'\n{len(notes)} notas informativas en el informe.' if notes else ''
        wx.MessageBox(f'Exportacion completada:\n{destination}\n\nInforme:\n{report_path}{suffix}',
                      'Exportar a Eagle',wx.OK|wx.ICON_INFORMATION)
