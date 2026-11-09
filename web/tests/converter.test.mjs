// SPDX-License-Identifier: GPL-3.0-only
import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {parse,one,kids,netNames,convert,convertBoard} from '../converter.js';
import {makeZip,readZip,crc32} from '../zip.js';
import {deflateRawSync} from 'node:zlib';
const pcb=readFileSync(new URL('../examples/demo.kicad_pcb',import.meta.url),'utf8');
const sch=readFileSync(new URL('../examples/demo.kicad_sch',import.meta.url),'utf8');
test('parser preserves empty strings, escapes, Unicode and net whitespace',()=>{
  const root=parse('(root (a "") (b "á & \\"x\\"\\n") (net "GND "))');
  assert.equal(one(root,'a')[1],'');assert.equal(one(root,'b')[1],'á & "x"\n');assert.equal(one(root,'net')[1],'GND ');
});
test('parser rejects incomplete, extra roots and unterminated strings',()=>{
  for(const text of ['(root','(root))','(a)(b)','(a "broken)','(a) garbage',''])assert.throws(()=>parse(text));
});
test('net naming is deterministic and never merges collisions or case variants',()=>{
  const names=['GND','gnd','GND ','A B','A_B','A:B','A;B','OUTLINES',''];
  const mapping=netNames(names);assert.equal(new Set(mapping.values()).size,names.length);
  assert.equal(mapping.get('A_B'),'A_B');assert.equal(mapping.get('GND'),'GND');
  for(const name of mapping.values()){assert.ok(name);assert.equal(name,name.toUpperCase());assert.doesNotMatch(name,/[\s;:]/);assert.notEqual(name,'OUTLINES');}
  assert.deepEqual(mapping,netNames([...names].reverse()));
});
test('board exports grouped components, arc, via and composite oval PTH',()=>{
  const result=convert(pcb);assert.equal(result.report.components,1);assert.equal(result.report.pads,2);assert.equal(result.report.tracks,5);assert.equal(result.report.vias,1);
  assert.equal(result.report.composite_pth_pads,1);assert.match(result.brd,/<eagle version="7.7.0">/);assert.match(result.brd,/<element name="J1"/);
  assert.match(result.brd,/pad="2__TOP"/);assert.match(result.brd,/pad="2__BOTTOM"/);assert.match(result.brd,/curve="-180"/);assert.equal(result.sch,undefined);
});
test('project retains schematic pin to board pad relationships and bundled library',()=>{
  const result=convert(pcb,sch);assert.equal(result.report.checked_pinrefs,2);assert.equal(result.report.schematic_wires,2);assert.equal(result.report.schematic_units,1);
  assert.match(result.sch,/<connect gate="G\$1" pin="2" pad="2 2__TOP 2__BOTTOM" route="all"/);
  assert.match(result.sch,/<pinref part="J1" gate="G\$1" pin="1"/);assert.match(result.lbr,/<library name="KiCadWeb">/);assert.match(result.sch,/<net name="GND"/);
});
test('unsupported copper zones, internal copper and slots fail explicitly',()=>{
  assert.throws(()=>convert(pcb.replace('(setup','(zone (net 1)) (setup')),/zonas/);
  assert.throws(()=>convert(pcb.replace('(2 "B.Cu" signal)','(2 "B.Cu" signal) (4 "In1.Cu" signal)')),/dos capas/);
  assert.throws(()=>convert(pcb.replace('(drill 1)','(drill oval 1 2)')),/ranurado/);
  assert.throws(()=>convert(pcb.replace('(layers "F.Cu" "B.Cu") (net 1)','blind (layers "F.Cu" "B.Cu") (net 1)')),/vías pasantes/);
});
test('open outlines and copper graphics fail',()=>{
  assert.throws(()=>convert(pcb.replace('(gr_rect (start 15 12) (end 52 38)','(gr_line (start 15 12) (end 52 38)')),/extremos abiertos/);
  assert.throws(()=>convert(pcb.replace('(layer "Edge.Cuts")','(layer "F.Cu")')),/Gráficos de cobre/);
});
test('unconnected pads remain outside signals instead of sharing a fake net',()=>{
  const result=convert(pcb.replace('(net 2 "+3V3")))','))'));
  assert.doesNotMatch(result.brd,/<contactref element="J1" pad="2"/);assert.doesNotMatch(result.brd,/FAB_UNCONNECTED/);
});
test('zero and non-finite dimensions fail',()=>{
  assert.throws(()=>convert(pcb.replace('(width 0.65)','(width NaN)')),/positiva/);
  assert.throws(()=>convert(pcb.replace('(size 2.2 2.2)','(size 0 2.2)')),/positiva/);
});
test('rotated footprints transform relative pad locations and retain absolute pad angle',()=>{
  const board=convertBoard(pcb.replace('(at 24 22)','(at 24 22 90)').replace('(at 5.08 0)','(at 5.08 0 90)'));
  const pkg=board.library.children[0].children[0],pads=pkg.children.filter(n=>n.tag==='pad');
  assert.ok(Math.abs(pads[1].attrs.x)<1e-6);assert.ok(Math.abs(pads[1].attrs.y-5.08)<1e-6);assert.equal(pads[1].attrs.rot,'R90');
});
test('KiCad 10 direct named nets are supported',()=>{
  const modern=pcb.replace('(net 1 "GND") (net 2 "+3V3")','').replaceAll('(net 1 "GND")','(net "GND")').replaceAll('(net 2 "+3V3")','(net "+3V3")').replaceAll('(net 1)','(net "GND")').replaceAll('(net 2)','(net "+3V3")');
  assert.equal(convert(modern,sch).report.source_nets,2);
});
test('padless graphics do not create unmatched EAGLE components',()=>{
  const extra='(footprint "Demo:Graphic" (layer "F.Cu") (at 0 0) (property "Reference" "GRAPHIC") (fp_line (start 16 13) (end 17 13) (stroke (width .1)) (layer "F.SilkS")))';
  const result=convert(pcb.replace('(setup',extra+' (setup'),sch);
  assert.equal(result.report.components,1);assert.doesNotMatch(result.brd,/<element name="GRAPHIC"/);
});
test('special padstacks and unused-layer annulus removal are rejected',()=>{
  assert.throws(()=>convert(pcb.replace('(drill 1)','(drill 1) (padstack (mode custom))')),/padstack/);
  assert.throws(()=>convert(pcb.replace('(drill 1)','(drill 1) (remove_unused_layers yes)')),/anillos/);
  assert.equal(convert(pcb.replace('(drill 1)','(drill 1) (remove_unused_layers no)')).report.pads,2);
});
test('schematic graph rejects shorts and missing pins',()=>{
  assert.throws(()=>convert(pcb,sch.replace('(xy 35 50) (xy 44.92 50)','(xy 44.92 50) (xy 55.08 50)')),/redes distintas/);
  assert.throws(()=>convert(pcb,sch.replace('(number "2"','(number "9"')),/sin pad/);
  assert.throws(()=>convert(pcb,sch.replace('(label "+3V3"','(label "GND"')),/redes distintas/);
});
test('schematic graph rejects split networks and extra connected PCB pads',()=>{
  assert.throws(()=>convert(pcb.replace('(net 2 "+3V3")))','(net 1 "GND")))'),sch),/grupos separados/);
  assert.throws(()=>convert(pcb,sch.replace('(symbol (lib_id','(sheet (at 0 0)) (symbol (lib_id')),/una hoja/);
});
test('no-connect markers cannot hide connected pins',()=>{
  assert.throws(()=>convert(pcb,sch.replace('(wire (pts','(no_connect (at 44.92 50)) (wire (pts')),/no conectado/);
});
test('XML escapes user content',()=>{
  assert.match(convert(pcb.replace('"POWER"','"A&B<test>"')).brd,/value="A&amp;B&lt;test&gt;"/);
});
test('stored ZIP roundtrip, CRC validation and selected extension filtering',async()=>{
  const data=makeZip({'carpeta/demo.kicad_pcb':pcb,'carpeta/demo.kicad_sch':sch,'README.txt':'ignored'});
  const result=await readZip(data);assert.equal(result.length,2);assert.equal(result[0].text,pcb);assert.equal(result[1].text,sch);
  const damaged=data.slice();damaged[80]^=1;await assert.rejects(()=>readZip(damaged),/CRC/);
  assert.equal(crc32(new TextEncoder().encode('123456789')),0xcbf43926);
});
test('deflated ZIP, including central sizes and local data descriptor flag',async()=>{
  const data=makeZip({'demo.kicad_pcb':pcb}),v=new DataView(data.buffer),nameLength=v.getUint16(26,true),offset=30+nameLength;
  const compressed=new Uint8Array(deflateRawSync(new TextEncoder().encode(pcb))),centralOffset=v.getUint32(data.length-6,true);
  const tail=data.slice(centralOffset),tv=new DataView(tail.buffer);
  tv.setUint16(10,8,true);tv.setUint32(20,compressed.length,true);tv.setUint32(tail.length-6,offset+compressed.length,true);
  const head=data.slice(0,offset),hv=new DataView(head.buffer);hv.setUint16(6,0x808,true);hv.setUint16(8,8,true);hv.setUint32(18,compressed.length,true);
  const zip=new Uint8Array(head.length+compressed.length+tail.length);zip.set(head);zip.set(compressed,head.length);zip.set(tail,head.length+compressed.length);
  assert.equal((await readZip(zip))[0].text,pcb);
});
test('ZIP guards traversal, expansion limit, truncation, encryption and duplicates',async()=>{
  await assert.rejects(()=>readZip(makeZip({'../evil.kicad_pcb':pcb})),/Nombres/);
  await assert.rejects(()=>readZip(new Uint8Array(10)),/ZIP/);
  const zip=makeZip({'demo.kicad_pcb':pcb}),v=new DataView(zip.buffer),central=v.getUint32(zip.length-6,true);
  v.setUint32(central+24,65*1024*1024,true);await assert.rejects(()=>readZip(zip),/límite/);
  const encrypted=makeZip({'demo.kicad_pcb':pcb}),ev=new DataView(encrypted.buffer);ev.setUint16(ev.getUint32(encrypted.length-6,true)+8,1,true);await assert.rejects(()=>readZip(encrypted),/contraseña/);
});
