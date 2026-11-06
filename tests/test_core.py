# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 Alejandro Rebolledo
import importlib.util
import os
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'plugin/kicad_eagle_exporter'))
import kicad10_project_to_eagle as project
import kicad10_to_eagle as board
import runtime

class NetNames(unittest.TestCase):
    def test_spaces_and_collisions_do_not_merge_distinct_nets(self):
        names=['/BTN_REG','/BTN_REG ','/BTN_REG_','GND','gnd','A:B','A;B','A B','OUTLINES']
        mapping=project.eagle_net_names(names)
        self.assertEqual(len(set(mapping.values())),len(names))
        self.assertEqual(mapping['/BTN_REG'],'/BTN_REG')
        self.assertEqual(mapping['/BTN_REG_'],'/BTN_REG_')
        for name in mapping.values():
            self.assertNotRegex(name,r'[\s;:]')
            self.assertEqual(name,name.upper())
            self.assertNotEqual(name,'OUTLINES')
        self.assertEqual(mapping,project.eagle_net_names(reversed(names)))

    def test_source_parser_preserves_escaped_text_and_empty_atoms(self):
        result=project.parse('(root (text "line\\nnext") (value "") (at -1.25 2))')
        self.assertEqual(project.one(result,'text')[1],'line\nnext')
        self.assertEqual(project.one(result,'value')[1],'')

    def test_parser_rejects_incomplete_input(self):
        with self.assertRaises(ValueError):project.parse('(root (child)')

class InstallationPaths(unittest.TestCase):
    def test_platform_defaults(self):
        home=Path('/test-home')
        self.assertEqual(runtime.plugin_directory('linux',home,{}),home/'.local/share/kicad/10.0/scripting/plugins/kicad_eagle_exporter')
        for platform in ('darwin','win32'):
            self.assertEqual(runtime.plugin_directory(platform,home,{}),home/'Documents/KiCad/10.0/scripting/plugins/kicad_eagle_exporter')

    def test_configured_document_root(self):
        result=runtime.plugin_directory('linux',Path('/user'),{'KICAD_DOCUMENTS_HOME':'/custom'})
        self.assertEqual(result,Path('/custom/10.0/scripting/plugins/kicad_eagle_exporter'))

    def test_xdg_override(self):
        result=runtime.plugin_directory('linux',Path('/user'),{'XDG_DATA_HOME':'/xdg'})
        self.assertEqual(result,Path('/xdg/kicad/10.0/scripting/plugins/kicad_eagle_exporter'))

class ReportNotes(unittest.TestCase):
    def test_whitespace_variants_report_isolated_pad(self):
        class Pad:
            def __init__(self,net,num):self.net=net;self.num=num
            def GetNetname(self):return self.net
            def GetNumber(self):return self.num
        class Footprint:
            def GetReference(self):return 'C_TEST1'
            def Pads(self):return [Pad('BUTTON','1'),Pad('BUTTON ','2')]
        class Board:
            def GetFootprints(self):return [Footprint()]
            def GetTracks(self):return []
        notes=board.net_name_information(Board())
        self.assertEqual(len(notes),1)
        self.assertEqual(notes[0]['severity'],'info')
        self.assertEqual({n['source_name'] for n in notes[0]['nets']},{'BUTTON','BUTTON '})
        self.assertTrue(all(n['single_pad_without_tracks'] for n in notes[0]['nets']))

if __name__=='__main__':unittest.main()
