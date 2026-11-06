#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 Alejandro Rebolledo
"""Export a single-sheet KiCad 10 PCB + schematic to linked Eagle XML files.

Uses KiCad CLI's netlist as electrical authority. Native footprint grouping is
rebuilt from the tested fabrication exporter. Embedded symbols become an Eagle
library; original schematic placement, wires, labels, graphics are translated.
"""
from __future__ import annotations
import argparse
from collections import Counter,defaultdict
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
try:
    from . import kicad10_to_eagle as base
except ImportError:
    import kicad10_to_eagle as base

LIBRARY='KiCadProject'
E=base.element
F=base.fmt

def parse(text):
    stack=[];root=None
    for match in re.finditer(r'\(|\)|"(?:\\.|[^"\\])*"|[^\s()]+',text):
        token=match.group()
        if token=='(':
            node=[]
            if stack:stack[-1].append(node)
            elif root is not None:raise ValueError('Más de una expresión raíz.')
            else:root=node
            stack.append(node)
        elif token==')':
            if not stack:raise ValueError('Paréntesis de cierre inesperado.')
            stack.pop()
        else:
            if not stack:raise ValueError('Contenido fuera de la expresión raíz.')
            stack[-1].append(json.loads(token) if token.startswith('"') else token)
    if stack:raise ValueError('Expresión incompleta.')
    return root

def kids(node,key):return [x for x in node if isinstance(x,list) and x and x[0]==key]
def one(node,key,default=None):return next(iter(kids(node,key)),default)
def props(node):return {x[1]:x[2] for x in kids(node,'property')}
def numbers(node,key):return [float(x) for x in one(node,key)[1:]]
def safe(text):return re.sub(r'[^A-Za-z0-9_.+-]','_',text)
def eagle_net_names(names):
    """Map names one-to-one, including Eagle's case-insensitive namespace.

    Whitespace must not be stripped: KiCad can have both BTN_REG and BTN_REG .
    Merging those would introduce a connection absent from the source.
    """
    names=sorted(set(names))
    candidates={name:re.sub(r'[\s;:]', '_', name).upper() or 'N_KICAD' for name in names}
    result={};used=set()
    # Give already valid uppercase names priority over transformed candidates.
    for name in names:
        if candidates[name]==name and name!='OUTLINES':
            result[name]=name;used.add(name)
    for name in names:
        if name in result:continue
        stem=candidates[name]
        if stem=='OUTLINES':stem='OUTLINES_KICAD'
        candidate=stem;index=2
        while candidate in used:
            candidate=stem+'__K'+str(index);index+=1
        result[name]=candidate;used.add(candidate)
    assert len(set(result.values()))==len(names)
    return result

def normalize_project_nets(boardroot,schroot,pin_net):
    signals=boardroot.findall('.//board/signals/signal')
    nets=schroot.findall('.//sheet/nets/net')
    mapping=eagle_net_names([x.get('name') for x in signals+nets])
    for node in signals+nets:node.set('name',mapping[node.get('name')])
    return {key:mapping[value] for key,value in pin_net.items()},mapping
def point(x,y):return round(x,6),round(y,6)
def pos(node):return tuple(numbers(node,'at')[:2])
def stroke(node):return float(one(one(node,'stroke',[]),'width',['width','.1524'])[1]) or .1524
def alignment(effects):
    justify=one(effects,'justify',[])[1:]
    horizontal='left' if 'left' in justify else 'right' if 'right' in justify else 'center'
    vertical='top' if 'top' in justify else 'bottom' if 'bottom' in justify else 'center'
    return horizontal if vertical=='center' and horizontal=='center' else vertical+'-'+horizontal if horizontal!='center' else vertical+'-center'

def document(kind,template):
    root=ET.Element('eagle',version='7.7.0'); drawing=E(root,'drawing')
    for tag in ('settings','grid','layers'):
        original=template.find('drawing/'+tag)
        if original is not None:drawing.append(deepcopy(original))
    layers=drawing.find('layers')
    for num,name,color in [(91,'Nets',2),(94,'Symbols',4),(95,'Names',7),(96,'Values',7),(97,'Info',7)]:
        if layers.find(f"layer[@number='{num}']") is None:E(layers,'layer',number=num,name=name,color=color,fill=1,visible='yes',active='yes')
    return root,E(drawing,kind)

def write_xml(path,root):
    ET.indent(root,space='  ')
    path.write_text('<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE eagle SYSTEM "eagle.dtd">\n'+ET.tostring(root,encoding='unicode')+'\n',encoding='utf8')

def graphics(parent,node,layer,convert=lambda x,y:(x,y)):
    """Translate drawings; electrical connectivity is handled separately."""
    tag=node[0];width=stroke(node)
    def wire(a,b):
        x1,y1=convert(*a);x2,y2=convert(*b)
        E(parent,'wire',x1=F(x1),y1=F(y1),x2=F(x2),y2=F(y2),width=F(width),layer=layer)
    if tag=='polyline':
        points=[tuple(float(v) for v in x[1:3]) for x in kids(one(node,'pts'),'xy')]
        for a,b in zip(points,points[1:]):wire(a,b)
    elif tag=='rectangle':
        a=numbers(node,'start');b=numbers(node,'end')
        fill=one(one(node,'fill',[]),'type',['type','none'])[1]
        if fill=='background':fill='none'
        if fill=='outline':
            x1,y1=convert(*a);x2,y2=convert(*b)
            E(parent,'rectangle',x1=F(min(x1,x2)),y1=F(min(y1,y2)),x2=F(max(x1,x2)),y2=F(max(y1,y2)),layer=layer)
        else:
            points=[a,(b[0],a[1]),b,(a[0],b[1]),a]
            for first,second in zip(points,points[1:]):wire(first,second)
    elif tag=='circle':
        x,y=convert(*numbers(node,'center'))
        E(parent,'circle',x=F(x),y=F(y),radius=F(numbers(node,'radius')[0]),width=F(width),layer=layer)
    elif tag=='text':
        x,y=convert(*pos(node));size=one(one(one(node,'effects',[]),'font',[]),'size',['size','1.27'])[1]
        E(parent,'text',x=F(x),y=F(y),size=size,layer=layer,font='vector',align=alignment(one(node,'effects',[]))).text=node[1]
    else:raise ValueError(f'Primitiva gráfica todavía no soportada: {tag}')

def symbol_units(lib):
    common=[];units=defaultdict(list)
    for sub in kids(lib,'symbol'):
        match=re.search(r'_(\d+)_(\d+)$',sub[1])
        if not match:raise ValueError('Nombre de unidad no reconocido: '+sub[1])
        unit,style=map(int,match.groups())
        if style not in (0,1):continue
        content=[x for x in sub[2:] if isinstance(x,list)]
        if unit==0:common.extend(content)
        else:units[unit].extend(content)
    return {unit:common+items for unit,items in units.items()}

def pin_data(pin):
    at=numbers(pin,'at');num=one(pin,'number')[1];name=one(pin,'name')[1]
    return {'number':num,'name':name,'x':at[0],'y':at[1],'angle':at[2],
            'length':numbers(pin,'length')[0],'type':pin[1]}

def world(instance,x,y):
    at=numbers(instance,'at');mirror=one(instance,'mirror')
    if mirror:
        if mirror[1]=='x':y=-y
        elif mirror[1]=='y':x=-x
        else:raise ValueError('Reflejo no reconocido.')
    angle=math.radians(at[2]);co=math.cos(angle);si=math.sin(angle)
    return point(at[0]+co*x-si*y,at[1]-si*x-co*y)

def instance_rotation(instance):
    angle=numbers(instance,'at')[2]%360;mirror=one(instance,'mirror')
    # Eagle M reflects local X. KiCad mirror y does the same; mirror x
    # is equivalent to mirror y followed by a half turn.
    if not mirror:return 'R'+F(angle)
    if mirror[1]=='x':angle=(angle+180)%360
    return 'MR'+F(angle)

class UnionFind:
    def __init__(self):self.parent={}
    def find(self,x):
        if x not in self.parent:self.parent[x]=x
        if self.parent[x]!=x:self.parent[x]=self.find(self.parent[x])
        return self.parent[x]
    def join(self,a,b):self.parent[self.find(a)]=self.find(b)

def source_graph(root,instances,definitions,pin_net):
    uf=UnionFind();pins={};wires=[];labels=[]
    for inst in instances:
        ref=props(inst)['Reference'];lib=definitions[one(inst,'lib_id')[1]]
        unit=int(one(inst,'unit')[1])
        for primitive in symbol_units(lib)[unit]:
            if primitive[0]!='pin':continue
            pin=pin_data(primitive);q=world(inst,pin['x'],pin['y'])
            pins[(ref,pin['number'])]=q;uf.find(q)
    for wire in kids(root,'wire'):
        ends=[point(*map(float,x[1:3])) for x in kids(one(wire,'pts'),'xy')]
        if len(ends)!=2:raise ValueError('Cable sin dos extremos.')
        wires.append((ends[0],ends[1],stroke(wire)))
        uf.join(ends[0],ends[1])
    for junction in kids(root,'junction'):uf.find(point(*pos(junction)))
    for tag in ('label','global_label','hierarchical_label'):
        for label in kids(root,tag):
            q=point(*pos(label));uf.find(q);labels.append((label[1],q,label))
    # Add global power symbols to the same label equivalence classes.
    for inst in instances:
        if props(inst)['Reference'].startswith('#PWR'):
            labels.append((props(inst)['Value'],world(inst,0,0),None))
    # Split T junctions and pins lying on a wire, but do not create nodes at
    # crossings that have no pin, endpoint or explicit junction.
    points=list(uf.parent)
    for a,b,_ in wires:
        for q in points:
            if min(a[0],b[0])-1e-6<=q[0]<=max(a[0],b[0])+1e-6 and min(a[1],b[1])-1e-6<=q[1]<=max(a[1],b[1])+1e-6:
                if abs((b[0]-a[0])*(q[1]-a[1])-(b[1]-a[1])*(q[0]-a[0]))<1e-5:uf.join(a,q)
    named={}
    for name,q,_ in labels:
        if name in named:uf.join(q,named[name])
        else:named[name]=q
    roots=defaultdict(set)
    for key,q in pins.items():
        if key in pin_net:roots[uf.find(q)].add(pin_net[key])
    conflicts={str(key):sorted(value) for key,value in roots.items() if len(value)>1}
    if conflicts:raise ValueError('La reconstrucción gráfica une redes diferentes: '+json.dumps(conflicts))
    roots={key:next(iter(value)) for key,value in roots.items()}
    return uf,pins,wires,labels,roots

def make_symbol(parent,name,items,lib):
    symbol=E(parent,'symbol',name=name);pins={}
    hidden_names=one(one(lib,'pin_names',[]),'hide',['hide','no'])[1]=='yes'
    hidden_numbers=one(one(lib,'pin_numbers',[]),'hide',['hide','no'])[1]=='yes'
    for item in items:
        if item[0]!='pin':graphics(symbol,item,94);continue
        pin=pin_data(item);number=pin['number']
        if number in pins:raise ValueError('Número de pin duplicado en símbolo: '+number)
        pins[number]=pin
        directions={'input':'in','output':'out','bidirectional':'io','tri_state':'hiz',
                    'passive':'pas','power_in':'pwr','power_out':'pwr','open_collector':'oc',
                    'open_emitter':'oc','no_connect':'nc','unspecified':'io','free':'pas'}
        # A point pin fixes the electrical terminal exactly; the source pin
        # stroke is drawn explicitly to preserve arbitrary KiCad pin lengths.
        E(symbol,'pin',name=number,x=F(pin['x']),y=F(pin['y']),visible='off',length='point',
          direction=directions.get(pin['type'],'pas'),rot='R'+F(pin['angle']%360))
        a=math.radians(pin['angle']);ex=pin['x']+math.cos(a)*pin['length'];ey=pin['y']+math.sin(a)*pin['length']
        E(symbol,'wire',x1=F(pin['x']),y1=F(pin['y']),x2=F(ex),y2=F(ey),width='.1524',layer=94)
        if not hidden_names and pin['name'] not in ('~',''):
            E(symbol,'text',x=F(ex+.3*math.cos(a)),y=F(ey+.3*math.sin(a)),size='1',layer=94,
              align='center-left' if math.cos(a)>=0 else 'center-right',font='vector').text=pin['name']
        if not hidden_numbers:
            E(symbol,'text',x=F((pin['x']+ex)/2),y=F((pin['y']+ey)/2+.3),size='.8',layer=94,font='vector').text=number
    for prop in kids(lib,'property'):
        if prop[1] not in ('Reference','Value'):continue
        at=numbers(prop,'at');effects=one(prop,'effects',[])
        size=one(one(effects,'font',[]),'size',['size','1.27'])[1]
        E(symbol,'text',x=F(at[0]),y=F(at[1]),size=size,layer=95 if prop[1]=='Reference' else 96,
          rot='R'+F(at[2]%360),font='vector',align=alignment(effects)).text='>NAME' if prop[1]=='Reference' else '>VALUE'
    return pins

def regroup_board(tree,board,components):
    """Combine the tested per-pad packages into their original components."""
    out=tree.find('drawing/board');oldlib=out.find('libraries/library')
    oldpackages={x.get('name'):x for x in oldlib.findall('packages/package')}
    oldelements=list(out.find('elements'));footprints={f.GetReference():f for f in board.GetFootprints()}
    library=ET.Element('library',name=LIBRARY);packages=E(library,'packages')
    symbols=E(library,'symbols');devicesets=E(library,'devicesets')
    report_path={};mapping={};padnames=defaultdict(lambda:defaultdict(list))
    # Board coordinates are translated by the base export; each element remains
    # at an original pad position until regrouping finishes.
    grouped=defaultdict(list)
    for item in oldelements:
        ref,num=item.get('value').rsplit(':',1);grouped[ref].append((num,item))
    for ref,comp in components.items():
        if ref not in footprints:raise ValueError('Componente sin encapsulado en la placa: '+ref)
        fp=footprints[ref];items=grouped[ref]
        if not items:raise ValueError('Componente sin pads exportados: '+ref)
        # Locate the original footprint origin relative to one known pad.
        first_num,first=items[0]
        pad=next(x for x in fp.Pads() if x.GetNumber()==first_num)
        origin_x=float(first.get('x'))-(pad.GetPosition().x-fp.GetPosition().x)/1e6
        origin_y=float(first.get('y'))+(pad.GetPosition().y-fp.GetPosition().y)/1e6
        package=E(packages,'package',name='PKG_'+safe(ref));used=set()
        for num,item in items:
            for primitive in oldpackages[item.get('package')]:
                primitive=deepcopy(primitive)
                oldname=primitive.get('name')
                candidate=num if oldname=='1' else num+'__'+oldname
                newname=candidate;suffix=2
                while newname in used:newname=candidate+'_'+str(suffix);suffix+=1
                used.add(newname);mapping[(item.get('name'),oldname)]=(ref,newname)
                padnames[ref][num].append(newname)
                primitive.set('name',newname)
                primitive.set('x',F(float(item.get('x'))-origin_x))
                primitive.set('y',F(float(item.get('y'))-origin_y))
                primitive.set('rot',item.get('rot','R0'))
                package.append(primitive)
        out.find('elements').append(ET.Element('element',name=ref,library=LIBRARY,package=package.get('name'),
            value=comp.findtext('value',''),x=F(origin_x),y=F(origin_y),rot='R0'))
        report_path[ref]=package.get('name')
    for old in oldelements:out.find('elements').remove(old)
    for contact in out.findall('signals/signal/contactref'):
        target=mapping[(contact.get('element'),contact.get('pad'))]
        contact.set('element',target[0]);contact.set('pad',target[1])
    out.find('libraries').remove(oldlib);out.find('libraries').append(library)
    return library,symbols,devicesets,padnames,report_path

def export_project(schematic,pcb,destination,overwrite=False):
    p,*_=base.load_runtime()
    schematic=schematic.resolve();pcb=pcb.resolve();destination=destination.resolve()
    hashes={str(path):hashlib.sha256(path.read_bytes()).hexdigest() for path in (schematic,pcb)}
    parsed=parse(schematic.read_text(encoding='utf8'))
    if kids(parsed,'sheet'):raise ValueError('Esta primera versión requiere un esquemático de una hoja.')
    definitions={x[1]:x for x in kids(one(parsed,'lib_symbols'),'symbol')}
    instances=kids(parsed,'symbol')
    for node in parsed:
        if isinstance(node,list) and node[0] in ('bus','bus_entry','text_box','image'):
            raise ValueError('Elemento de esquemático todavía no soportado: '+node[0])
    paths={ext:destination.with_suffix(ext) for ext in ('.sch','.brd','.lbr','.project-report.json')}
    if not overwrite and any(path.exists() for path in paths.values()):raise ValueError('La salida existe; usa --overwrite u otro nombre.')
    cli=base.runtime.find_cli()
    with tempfile.TemporaryDirectory(prefix='kicad_project_') as tmp:
        tmp=Path(tmp);netpath=tmp/'source.xml'
        run=subprocess.run([str(cli),'sch','export','netlist','--format','kicadxml','--output',str(netpath),str(schematic)],capture_output=True,text=True,encoding='utf8',errors='replace')
        if run.returncode:raise ValueError('KiCad no pudo calcular la netlist: '+run.stderr+run.stdout)
        netlist=ET.parse(netpath)
        components={x.get('ref'):x for x in netlist.findall('components/comp')}
        board=p.LoadBoard(str(pcb))
        pad_net={(fp.GetReference(),pad.GetNumber()):pad.GetNetname() for fp in board.GetFootprints() for pad in fp.Pads()}
        netmap={};pin_net={};notes=[]
        for net in netlist.findall('nets/net'):
            name=net.get('name');keys=[(x.get('ref'),x.get('pin')) for x in net.findall('node')]
            assigned={pad_net[key] for key in keys if key in pad_net and pad_net[key]}
            if len(assigned)>1:raise ValueError('Placa y esquemático discrepan en la red '+name+': '+str(assigned))
            target=next(iter(assigned),name);netmap[name]=target
            if any(other!=name and mapped==target for other,mapped in netmap.items()):
                raise ValueError('La placa une dos redes distintas del esquemático: '+target)
            if target!=name:notes.append('Nombre normalizado: '+name+' → '+target)
            for key in keys:
                if key not in pad_net:raise ValueError('Pin sin pad correspondiente: '+str(key))
                if pad_net[key] and pad_net[key]!=target:raise ValueError('Red incompatible: '+str(key))
                pin_net[key]=target
        missing=[key for key,value in pad_net.items() if key[0] in components and key not in pin_net and value]
        if missing:raise ValueError('Pads conectados que no figuran en la netlist: '+str(missing))
        uf,pins,wires,labels,roots=source_graph(parsed,instances,definitions,pin_net)
        base_report=base.export_board(pcb,tmp/'base.brd')
        tree=ET.parse(tmp/'base.brd').getroot()
        library,symbols,devicesets,padnames,packages=regroup_board(tree,board,components)
        # Every library unit is copied once, retaining actual symbol outlines.
        symbol_cache={};unit_pins={}
        for libid,lib in definitions.items():
            for unit,items in symbol_units(lib).items():
                name=safe(libid)+'_U'+str(unit)
                symbol_cache[(libid,unit)]=name
                unit_pins[(libid,unit)]=make_symbol(symbols,name,items,lib)
        schroot,sch=document('schematic',tree)
        E(sch,'description').text='Converted from KiCad 10: linked PCB, schematic and embedded library.'
        libs=E(sch,'libraries')
        E(sch,'attributes');E(sch,'variantdefs');classes=E(sch,'classes');E(classes,'class',number=0,name='default',width=0,drill=0)
        parts=E(sch,'parts');sheets=E(sch,'sheets');sheet=E(sheets,'sheet');plain=E(sheet,'plain')
        placed=E(sheet,'instances');nets=E(sheet,'nets')
        paper=one(parsed,'paper');height=float(paper[3]) if paper and paper[1]=='User' else 297.0
        def page(x,y):return x,height-y
        gates={};references=defaultdict(list)
        for inst in instances:
            ref=props(inst)['Reference']
            if ref in components:references[ref].append(inst)
        for ref,comp in components.items():
            if ref not in references:raise ValueError('Componente sin instancia en la hoja: '+ref)
            libids={one(inst,'lib_id')[1] for inst in references[ref]}
            if len(libids)!=1:raise ValueError('Componente con símbolos incompatibles: '+ref)
            libid=next(iter(libids));ds=E(devicesets,'deviceset',name='DEV_'+safe(ref),uservalue='yes')
            gs=E(ds,'gates');devices=E(ds,'devices');dev=E(devices,'device',name='',package=packages[ref]);connects=E(dev,'connects')
            covered=set()
            for inst in references[ref]:
                unit=int(one(inst,'unit')[1]);gate='G$'+str(unit);gates[(ref,unit)]=gate
                E(gs,'gate',name=gate,symbol=symbol_cache[(libid,unit)],x=0,y=0,addlevel='must')
                for num in unit_pins[(libid,unit)]:
                    if num in padnames[ref]:
                        E(connects,'connect',gate=gate,pin=num,pad=' '.join(padnames[ref][num]),route='all');covered.add(num)
            if set(padnames[ref])-covered:raise ValueError('Pads sin pin de símbolo: '+ref+' '+str(set(padnames[ref])-covered))
            tech=E(dev,'technologies');E(tech,'technology',name='')
            E(parts,'part',name=ref,library=LIBRARY,deviceset=ds.get('name'),device='',value=comp.findtext('value',''))
        for inst in instances:
            ref=props(inst)['Reference'];libid=one(inst,'lib_id')[1];unit=int(one(inst,'unit')[1]);x,y=page(*pos(inst))
            if ref not in components:
                # Power markers are electrical labels in Eagle. Preserve the
                # visible icon as sheet graphics without inventing PCB parts.
                for primitive in symbol_units(definitions[libid])[unit]:
                    if primitive[0]!='pin':graphics(plain,primitive,97,lambda xx,yy:page(*world(inst,xx,yy)))
                continue
            place=E(placed,'instance',part=ref,gate=gates[(ref,unit)],x=F(x),y=F(y),smashed='yes',rot=instance_rotation(inst))
            for prop in kids(inst,'property'):
                if prop[1] not in ('Reference','Value'):continue
                effects=one(prop,'effects',[])
                if one(effects,'hide',['hide','no'])[1]=='yes':continue
                px,py=page(*pos(prop));angle=numbers(prop,'at')[2]%360
                size=one(one(effects,'font',[]),'size',['size','1.27'])[1]
                # Eagle 7 attributes only support bottom-left anchoring. Shift
                # the source anchor approximately; normal text supports align.
                align=alignment(effects);text=props(inst).get(prop[1],'')
                tw=float(size)*.6*len(text)
                ox=0 if align.endswith('left') else -tw if align.endswith('right') else -tw/2
                oy=0 if align.startswith('bottom') else -float(size) if align.startswith('top') else -float(size)/2
                theta=math.radians(angle);px+=ox*math.cos(theta)-oy*math.sin(theta);py+=ox*math.sin(theta)+oy*math.cos(theta)
                E(place,'attribute',name='NAME' if prop[1]=='Reference' else 'VALUE',x=F(px),y=F(py),size=size,layer=95 if prop[1]=='Reference' else 96,rot='R'+F(angle),display='value')
        for tag in ('text','rectangle','polyline','circle','arc'):
            for item in kids(parsed,tag):graphics(plain,item,97,page)
        for nc in kids(parsed,'no_connect'):
            x,y=page(*pos(nc));d=.35
            for sign in (-1,1):
                E(plain,'wire',x1=F(x-d),y1=F(y-sign*d),x2=F(x+d),y2=F(y+sign*d),width='.127',layer=97)
        # Preserve original connected wire groups instead of drawing long new
        # cross-sheet wires. Named labels tie separate segments of the same net.
        segments={};eagle_nets={}
        def segment(q,name=None):
            key=uf.find(q);name=name or roots.get(key)
            if name is None:return None
            if name not in eagle_nets:eagle_nets[name]=E(nets,'net',name=name,**{'class':0})
            if key not in segments:segments[key]=E(eagle_nets[name],'segment')
            return segments[key]
        for (ref,num),q in pins.items():
            if (ref,num) not in pin_net:continue
            inst=next(i for i in references[ref] if num in unit_pins[(one(i,'lib_id')[1],int(one(i,'unit')[1]))])
            unit=int(one(inst,'unit')[1]);seg=segment(q,pin_net[(ref,num)])
            E(seg,'pinref',part=ref,gate=gates[(ref,unit)],pin=num)
        for a,b,width in wires:
            seg=segment(a)
            if seg is None:raise ValueError('Cable sin red determinable: '+str((a,b)))
            x1,y1=page(*a);x2,y2=page(*b)
            E(seg,'wire',x1=F(x1),y1=F(y1),x2=F(x2),y2=F(y2),width=F(width),layer=91)
        for junction in kids(parsed,'junction'):
            q=point(*pos(junction));seg=segment(q)
            if seg is not None:
                x,y=page(*q);E(seg,'junction',x=F(x),y=F(y))
        labelled=set()
        for text,q,label in labels:
            seg=segment(q)
            if seg is None:continue
            if (uf.find(q),q) in labelled:continue
            labelled.add((uf.find(q),q));x,y=page(*q)
            angle=numbers(label,'at')[2] if label else 0
            E(seg,'label',x=F(x),y=F(y),size='1.27',layer=95,rot='R'+F(angle%360))
        E(sch,'errors')
        libs.append(deepcopy(library))
        lbrroot,lbr=document('library',tree)
        lbr.set('name',LIBRARY)
        for item in library:lbr.append(deepcopy(item))
        tree.find('drawing/board/description').text='KiCad 10 linked project export. Original components grouped; matching schematic and library supplied.'
        pin_net,eagle_names=normalize_project_nets(tree,schroot,pin_net)
        result=validate_linked(tree,schroot,pin_net,components,padnames)
        result['eagle_net_name_map']=eagle_names
        result['eagle_net_names_valid']=all(name and not re.search(r'[\s;:]',name) and name==name.upper() for name in eagle_names.values())
        result['distinct_source_nets_preserved']=len(set(eagle_names.values()))==len(eagle_names)
        informational_notes=deepcopy(base_report.get('informational_notes',[]))
        for note in informational_notes:
            for net in note['nets']:net['eagle_name']=eagle_names[net['source_name']]
        result.update({'kicad_version':p.Version(),'source_files_unchanged':True,'source_sha256':hashes,
                       'notes':notes+base_report.get('notes',[]),'informational_notes':informational_notes,
                       'board_dimensions_mm':base_report['board_size_mm'],
                       'source_wires':len(wires),'exported_wires':len(schroot.findall('.//sheet/nets/net/segment/wire')),
                       'schematic_units':len(placed),'library_symbols':len(symbols),
                       'no_connect_markers':len(kids(parsed,'no_connect')),
                       'limitations':['Primera versión: una hoja; sin buses ni imágenes.',
                                      'Pin strokes drawn explicitly; names and labels may need visual adjustment.',
                                      'Sin modelos 3D ni vínculo a bibliotecas gestionadas de Fusion.',
                                      'Importación y edición en Fusion pendientes de prueba.']})
        for path,digest in hashes.items():
            if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=digest:raise ValueError('El origen cambió durante la exportación.')
        staged={'.brd':tree,'.sch':schroot,'.lbr':lbrroot}
        destination.parent.mkdir(parents=True,exist_ok=True)
        for ext,doc in staged.items():write_xml(tmp/('project'+ext),doc)
        (tmp/'project.project-report.json').write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf8')
        for ext,path in paths.items():path.write_bytes((tmp/('project'+ext)).read_bytes())
        return result

def validate_linked(boardroot,schroot,pin_net,components,padnames):
    library=schroot.find('drawing/schematic/libraries/library')
    devices={ds.get('name'):ds for ds in library.findall('devicesets/deviceset')}
    parts={part.get('name'):part for part in schroot.findall('.//schematic/parts/part')}
    pcbparts={part.get('name'):part for part in boardroot.findall('.//board/elements/element')}
    if set(parts)!=set(components) or set(pcbparts)!=set(components):raise ValueError('Conjunto de componentes inconsistente.')
    sch_contacts={};expanded=defaultdict(set)
    for net in schroot.findall('.//sheet/nets/net'):
        for pin in net.findall('segment/pinref'):
            key=(pin.get('part'),pin.get('pin'))
            if key in sch_contacts:raise ValueError('Pin repetido en la netlist exportada: '+str(key))
            sch_contacts[key]=net.get('name')
            part=parts[key[0]];ds=devices[part.get('deviceset')]
            connect=next((x for x in ds.findall('devices/device/connects/connect') if x.get('gate')==pin.get('gate') and x.get('pin')==key[1]),None)
            if connect is None:raise ValueError('Pin sin relación a pads: '+str(key))
            for pad in connect.get('pad').split():expanded[net.get('name')].add((key[0],pad))
    if sch_contacts!=pin_net:raise ValueError('La netlist del esquemático generado no coincide con KiCad.')
    board_contacts=defaultdict(set)
    for net in boardroot.findall('.//board/signals/signal'):
        for contact in net.findall('contactref'):board_contacts[net.get('name')].add((contact.get('element'),contact.get('pad')))
    if dict(expanded)!=dict(board_contacts):raise ValueError('Las conexiones del esquemático y la placa no coinciden.')
    return {'kicad_version':'10.0.x','parts':len(parts),'nets':len(expanded),'source_pin_connections':len(pin_net),
            'eagle_pad_connections':sum(map(len,expanded.values())),'schematic_netlist_matches_kicad':True,
            'schematic_board_consistent':True,'fusion_import_tested':False}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('schematic',type=Path);parser.add_argument('--pcb',type=Path)
    parser.add_argument('--output',type=Path,help='Ruta base, sin extensión, de los archivos de salida.')
    parser.add_argument('--overwrite',action='store_true');args=parser.parse_args()
    try:
        result=export_project(args.schematic,args.pcb or args.schematic.with_suffix('.kicad_pcb'),
                              args.output or args.schematic.with_name(args.schematic.stem+'_eagle'),args.overwrite)
    except Exception as exc:
        print('ERROR: '+str(exc),file=sys.stderr);return 1
    print(json.dumps(result,indent=2,ensure_ascii=False));return 0

if __name__=='__main__':raise SystemExit(main())
