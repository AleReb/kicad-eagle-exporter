// SPDX-License-Identifier: GPL-3.0-only
// Browser port of the conservative native exporter. No KiCad runtime required.
export const kids = (n, k) => (n || []).filter(x => Array.isArray(x) && x[0] === k);
export const one = (n, k, d = null) => kids(n, k)[0] || d;
const val = (n, k, d = '') => one(n, k, [k, d])[1];
const nums = (n, k) => {
  const result = one(n, k);
  if (!result) throw Error(`Falta ${k} en ${n?.[0]}.`);
  return result.slice(1).filter(x => !Array.isArray(x)).map(x => {
    const number = Number(x);
    if (!Number.isFinite(number)) throw Error(`Valor numérico inválido en ${k}: ${x}`);
    return number;
  });
};
const props = n => Object.fromEntries(kids(n, 'property').map(p => [p[1], p[2]]));
const rad = a => a * Math.PI / 180;
const fmt = n => typeof n === 'number' ? String(Math.abs(n) < 0.0000005 ? 0 : +n.toFixed(6)) : String(n);
const safe = s => s.replace(/[^A-Za-z0-9_.+-]/g, '_');
const escape = s => String(s).replace(/[&<>"']/g, c => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&apos;'}[c]));
export function parse(text) {
  if (typeof text !== 'string' || text.length > 64 * 1024 * 1024) throw Error('Archivo vacío o demasiado grande (máximo 64 MB).');
  const stack = []; let root = null;
  const tokens = text.replace(/^\uFEFF/, '').matchAll(/\(|\)|"(?:\\[\s\S]|[^"\\])*"|[^\s()"]+|"/g);
  for (const [token] of tokens) {
    if (token === '(') {
      if (stack.length > 512) throw Error('El archivo tiene demasiados niveles.');
      const n = [];
      if (stack.length) stack.at(-1).push(n);
      else if (root) throw Error('Más de una expresión raíz.');
      else root = n;
      stack.push(n);
    } else if (token === ')') {
      if (!stack.length) throw Error('Paréntesis de cierre inesperado.');
      stack.pop();
    } else {
      if (!stack.length) throw Error('Contenido fuera de la expresión raíz.');
      if (token === '"') throw Error('Cadena de texto incompleta.');
      // KiCad strings support escaped quotes, backslashes and control escapes.
      stack.at(-1).push(token.startsWith('"') ? token.slice(1, -1).replace(/\\([\s\S])/g, (_, c) => ({n:'\n',r:'\r',t:'\t'}[c] ?? c)) : token);
    }
  }
  if (stack.length || !root?.length) throw Error('Expresión vacía o incompleta.');
  return root;
}

export class Xml {
  constructor(tag, attrs = {}, text = '') { this.tag = tag; this.attrs = attrs; this.text = text; this.children = []; }
  add(tag, attrs = {}, text = '') { const n = new Xml(tag, attrs, text); this.children.push(n); return n; }
  toString() {
    const attrs = Object.entries(this.attrs).map(([k,v]) => ` ${k}="${escape(fmt(v))}"`).join('');
    return this.children.length || this.text ? `<${this.tag}${attrs}>${escape(this.text)}${this.children.join('')}</${this.tag}>` : `<${this.tag}${attrs}/>`;
  }
}
const xml = n => `<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE eagle SYSTEM "eagle.dtd">\n${n}\n`;
const LAYERS = [[1,'Top',4],[16,'Bottom',1],[17,'Pads',2],[18,'Vias',2],[19,'Unrouted',6],[20,'Dimension',15],[21,'tPlace',7],[22,'bPlace',7],[25,'tNames',7],[26,'bNames',7],[27,'tValues',7],[28,'bValues',7],[29,'tStop',7],[30,'bStop',7],[31,'tCream',7],[32,'bCream',7],[44,'Drills',7],[45,'Holes',7],[46,'Milling',3],[51,'tDocu',7],[52,'bDocu',7],[91,'Nets',2],[92,'Busses',1],[93,'Pins',2],[94,'Symbols',4],[95,'Names',7],[96,'Values',7],[97,'Info',7],[98,'Guide',6]];
function document(kind) {
  const root = new Xml('eagle', {version:'7.7.0'}), drawing = root.add('drawing');
  drawing.add('settings').add('setting', {alwaysvectorfont:'yes'});
  drawing.add('grid', {distance:'.1',unitdist:'mm',unit:'mm',style:'lines',multiple:1,display:'no',altdistance:'.01',altunitdist:'mm',altunit:'mm'});
  const layers = drawing.add('layers');
  for (const [number,name,color] of LAYERS) layers.add('layer', {number,name,color,fill:1,visible:'yes',active:'yes'});
  return [root, drawing.add(kind)];
}
export function netNames(names) {
  names = [...new Set(names)].sort();
  const result = new Map(), used = new Set();
  const candidate = n => n.replace(/[\s;:]/g, '_').toUpperCase() || 'N_KICAD';
  for (const n of names) if (n === candidate(n) && n !== 'OUTLINES') { result.set(n,n); used.add(n); }
  for (const n of names) {
    if (result.has(n)) continue;
    const stem = candidate(n) === 'OUTLINES' ? 'OUTLINES_KICAD' : candidate(n);
    let name = stem, i = 2;
    while (used.has(name)) name = `${stem}__K${i++}`;
    result.set(n, name); used.add(name);
  }
  return result;
}
const pointKey = p => p.map(fmt).join(',');
const layerId = s => ({'F.Cu':1,'B.Cu':16,'Edge.Cuts':20,'F.SilkS':21,'B.SilkS':22,'F.Fab':51,'B.Fab':52}[s]);
function curve(a,m,b) {
  const u = [a[0]-m[0], a[1]-m[1]], v = [b[0]-m[0], b[1]-m[1]];
  const lengths = Math.hypot(...u) * Math.hypot(...v);
  const cross = (m[0]-a[0])*(b[1]-a[1]) - (m[1]-a[1])*(b[0]-a[0]);
  if (lengths < 1e-12 || Math.abs(cross) < 1e-10) throw Error('Arco degenerado.');
  return 2 * (Math.PI - Math.acos(Math.max(-1,Math.min(1,(u[0]*v[0]+u[1]*v[1])/lengths)))) * 180 / Math.PI * Math.sign(cross);
}
function wire(parent,a,b,width,layer,extra = {}) {
  parent.add('wire',{x1:a[0],y1:a[1],x2:b[0],y2:b[1],width,layer,...extra});
}
function width(n) { return Number(val(one(n,'stroke',[]),'width',val(n,'width',.1524))) || .1524; }
function graphics(parent, n, layer, transform = (x,y) => [x,y]) {
  const tag = n[0].replace(/^(gr|fp)_/, '');
  const p = k => transform(...nums(n,k));
  if (tag === 'line') wire(parent,p('start'),p('end'),width(n),layer);
  else if (tag === 'arc') {
    const a=p('start'), m=p('mid'), b=p('end');
    wire(parent,a,b,width(n),layer,{curve:curve(a,m,b)});
  } else if (tag === 'rect' || tag === 'rectangle') {
    const a=nums(n,'start'), b=nums(n,'end'), ps=[a,[b[0],a[1]],b,[a[0],b[1]],a];
    for(let i=1;i<ps.length;i++) wire(parent,transform(...ps[i-1]),transform(...ps[i]),width(n),layer);
  } else if (tag === 'polyline' || tag === 'poly') {
    const ps = kids(one(n,'pts'),'xy').map(v=>transform(+v[1],+v[2]));
    for(let i=1;i<ps.length;i++) wire(parent,ps[i-1],ps[i],width(n),layer);
    if(tag==='poly' && ps.length>2) wire(parent,ps.at(-1),ps[0],width(n),layer);
  } else if (tag === 'circle') {
    const c=p('center'), radius=one(n,'radius') ? +val(n,'radius') : Math.hypot(...p('end').map((x,i)=>x-c[i]));
    parent.add('circle',{x:c[0],y:c[1],radius,width:width(n),layer});
  } else if (tag === 'text') {
    if(n.includes('hide') || val(one(n,'effects',[]),'hide') === 'yes') return;
    const at=p('at'), size=val(one(one(n,'effects',[]),'font',[]),'size',1.27);
    parent.add('text',{x:at[0],y:at[1],size,layer,font:'vector'},n[1]);
  } else throw Error(`Primitiva gráfica no admitida: ${n[0]}.`);
}
function positive(n, label) { if (!Number.isFinite(n) || n<=0) throw Error(`${label}: se necesita una medida positiva.`); return n; }

export function convertBoard(text) {
  const source = parse(text);
  if(source[0] !== 'kicad_pcb') throw Error('Selecciona una PCB moderna .kicad_pcb.');
  const copper = (one(source,'layers',[]) || []).filter(n=>Array.isArray(n) && n[2]==='signal');
  if(copper.length!==2 || copper.some(n=>!['F.Cu','B.Cu'].includes(n[1]))) throw Error('Solo se admiten placas de dos capas: F.Cu y B.Cu.');
  if(kids(source,'zone').some(n=>!one(n,'keepout'))) throw Error('La versión web no admite zonas de cobre. Conserva las zonas y usa el conversor nativo, o trabaja sobre una copia sin zonas.');
  const [root,board] = document('board');
  board.add('description',{},'Converted locally from KiCad. Experimental EAGLE 7.7 XML; verify before manufacturing.');
  const plain=board.add('plain'), library=board.add('libraries').add('library',{name:'KiCadWeb'});
  const packages=library.add('packages'), symbols=library.add('symbols'), devicesets=library.add('devicesets');
  board.add('attributes'); board.add('variantdefs');
  board.add('classes').add('class',{number:0,name:'default',width:0,drill:0});
  const rules=board.add('designrules',{name:'default'});
  rules.add('description',{language:'en'},'Default rules. Review for your fabrication process.');
  rules.add('param',{name:'layerSetup',value:'(1*16)'});
  board.add('autorouter');
  const elements=board.add('elements'), signals=board.add('signals'); board.add('errors');
  const netIds = new Map(kids(source,'net').map(n=>[n[1],n[2]]));
  const netSource = n => {
    const v=one(n,'net');if(!v)return '';
    // KiCad 10 stores net names directly; older modern formats use net codes.
    if(v.length===2&&!netIds.size)return v[1]||'';
    if(v[1]==='0')return '';
    const name=v[2]??netIds.get(v[1]);if(!name)throw Error(`Red desconocida: ${v[1]}.`);return name;
  };
  const nets = new Map(), pinNets = new Map(), components=new Map(), preview=[], notes=[];
  const signal = name => {
    if(!name) throw Error('Pista o vía sin red. Asigna su red en KiCad antes de convertir.');
    if(!nets.has(name)) nets.set(name,signals.add('signal',{name,class:0}));
    return nets.get(name);
  };
  const xy=(x,y)=>[x,-y];
  const outline=[];
  function draw(n,transform=xy) {
    const layer=val(n,'layer');
    if(layer==='F.Cu'||layer==='B.Cu') throw Error('Gráficos de cobre no admitidos en la versión web.');
    const id=layerId(layer);
    if(!id) {notes.push(`Gráfico de ${layer} omitido (capa no exportada).`);return;}
    if(!['gr_line','gr_arc','gr_rect','gr_circle','gr_poly','gr_text','fp_line','fp_arc','fp_rect','fp_circle','fp_poly','fp_text'].includes(n[0])) {
      if(id===20) throw Error(`Contorno ${n[0]} no admitido.`);
      notes.push(`Gráfico ${n[0]} de ${layer} omitido.`);return;
    }
    graphics(plain,n,id,transform);
    if(id===20) {
      const tag=n[0].slice(3);
      if(tag==='line'||tag==='arc') outline.push([transform(...nums(n,'start')),transform(...nums(n,'end'))]);
      else if(tag==='rect') {const a=nums(n,'start'),b=nums(n,'end');const ps=[a,[b[0],a[1]],b,[a[0],b[1]],a].map(p=>transform(...p));for(let i=1;i<ps.length;i++)outline.push([ps[i-1],ps[i]]);}
      else if(tag==='circle') {const c=transform(...nums(n,'center')); outline.push([c,c]);}
      else throw Error('Edge.Cuts admite líneas, arcos, rectángulos y círculos.');
    }
  }
  for(const n of source) if(Array.isArray(n)&&n[0].startsWith('gr_')) draw(n);
  let padCount=0, composite=0, drills=0;
  for(const [index,fp] of kids(source,'footprint').entries()) {
    const properties=props(fp), ref=properties.Reference || kids(fp,'fp_text').find(n=>n[1]==='reference')?.[2];
    if(!ref || components.has(ref)) throw Error(`Referencia vacía o duplicada: ${ref || '(vacía)'}.`);
    const [fx,fy,fa=0]=nums(fp,'at'), angle=rad(fa);
    const world=(x,y)=>[fx+x*Math.cos(angle)+y*Math.sin(angle),-(fy-x*Math.sin(angle)+y*Math.cos(angle))];
    const origin=xy(fx,fy), pkg=packages.add('package',{name:`PKG_${index+1}`});
    const comp={ref,value:properties.Value||'',pkg:pkg.attrs.name,pads:new Map(),fp}; components.set(ref,comp);
    elements.add('element',{name:ref,library:'KiCadWeb',package:comp.pkg,value:comp.value,x:origin[0],y:origin[1],rot:'R0'});
    for(const n of fp) if(Array.isArray(n)&&n[0].startsWith('fp_')&&n[0]!=='fp_text') draw(n,world);
    for(const pad of kids(fp,'pad')) {
      const num=pad[1], type=pad[2], shape=pad[3], at=nums(pad,'at'), size=nums(pad,'size'), [px,py]=world(at[0],at[1]);
      if(one(pad,'padstack')||pad.includes('remove_unused_layers')||val(pad,'remove_unused_layers','no')==='yes')throw Error(`${ref} pad ${num}: padstack o eliminación de anillos no admitidos.`);
      const [sx,sy]=size.map(x=>positive(x,`${ref} pad ${num}`));
      if(one(pad,'primitives') || one(pad,'chamfer') || one(pad,'rect_delta') || one(pad,'options')) throw Error(`${ref} pad ${num}: forma personalizada no admitida.`);
      const drill=one(pad,'drill'), layers=one(pad,'layers',[]).slice(1);
      if(drill?.includes('oval') || one(drill,'offset')) throw Error(`${ref} pad ${num}: taladro ranurado o desplazado no admitido.`);
      const diameter=drill ? positive(+drill[1],`${ref} taladro`) : 0;
      if(type==='np_thru_hole') {
        if(!diameter || Math.abs(sx-diameter)>1e-6 || Math.abs(sy-diameter)>1e-6) throw Error(`${ref}: NPTH con cobre o forma no circular.`);
        plain.add('hole',{x:px,y:py,drill:diameter}); drills++;continue;
      }
      if(!['smd','thru_hole'].includes(type) || !['circle','rect','oval','roundrect'].includes(shape)) throw Error(`${ref} pad ${num}: tipo ${type}/${shape} no admitido.`);
      if(!num) throw Error(`${ref}: pad eléctrico sin número.`);
      if(shape==='circle' && Math.abs(sx-sy)>1e-6) throw Error(`${ref}: pad circular con dimensiones diferentes.`);
      const hasTop=layers.includes('*.Cu')||layers.includes('F.Cu'), hasBottom=layers.includes('*.Cu')||layers.includes('B.Cu');
      if(type==='smd' && hasTop===hasBottom) throw Error(`${ref}: SMD debe pertenecer a una sola cara externa.`);
      if(type==='thru_hole' && (!diameter||!hasTop||!hasBottom||diameter>Math.min(sx,sy))) throw Error(`${ref}: pad pasante incompatible.`);
      if(layers.some(l=>/^In\d+\.Cu$/.test(l))) throw Error('Pads con capas internas no admitidos.');
      const ratio=Number(val(pad,'roundrect_rratio',.25));
      if(shape==='roundrect' && (ratio<0||ratio>.5)) throw Error('Radio de pad redondeado inválido.');
      const roundness=shape==='rect'?0:shape==='roundrect'?Math.round(200*ratio):100;
      // PCB files store pad positions relative to the footprint, but angles in
      // board orientation (unlike standalone footprint library files).
      const common={x:px-origin[0],y:py-origin[1],rot:`R${fmt((at[2]||0)%360)}`,stop:'no',thermals:'no'};
      const contacts=[], used=new Set([...comp.pads.values()].flat());
      const contactName=suffix=>{let name=num+suffix,i=2;while(used.has(name))name=num+suffix+'_'+i++;used.add(name);contacts.push(name);return name;};
      if(type==='thru_hole') {
        const simple=(shape==='circle'||shape==='rect')&&Math.abs(sx-sy)<1e-6;
        pkg.add('pad',{...common,name:contactName(''),drill:diameter,diameter:Math.min(sx,sy),shape:simple&&shape==='rect'?'square':'round'});drills++;
        if(!simple) {
          composite++;
          for(const [layer,suffix] of [[1,'__TOP'],[16,'__BOTTOM']]) pkg.add('smd',{...common,name:contactName(suffix),dx:sx,dy:sy,layer,roundness,cream:'no'});
        }
      } else pkg.add('smd',{...common,name:contactName(''),dx:sx,dy:sy,layer:hasTop?1:16,roundness,cream:'no'});
      comp.pads.set(num,[...(comp.pads.get(num)||[]),...contacts]);
      const name=netSource(pad), key=JSON.stringify([ref,num]);
      if(pinNets.has(key)&&pinNets.get(key)!==name) throw Error(`${ref} pad ${num}: pads repetidos con redes diferentes.`);
      pinNets.set(key,name);
      if(name) for(const contact of contacts) signal(name).add('contactref',{element:ref,pad:contact});
      preview.push({type:'pad',x:px,y:py,sx,sy,angle:common.rot,layer:hasTop?1:16,drill:diameter});padCount++;
    }
    if(!comp.pads.size) {
      // Mechanical holes and graphics stay in board/plain. An empty component
      // would have no schematic part and break EAGLE's board/schematic pairing.
      components.delete(ref);packages.children.splice(packages.children.indexOf(pkg),1);
      elements.children.pop();
    }
  }
  let tracks=0,vias=0;
  for(const tag of ['segment','arc','via']) for(const n of kids(source,tag)) {
    const target=signal(netSource(n));
    if(tag==='via') {
      if(n.includes('blind')||n.includes('micro')||one(n,'padstack')||JSON.stringify(one(n,'layers')?.slice(1))!==JSON.stringify(['F.Cu','B.Cu'])) throw Error('Solo se admiten vías pasantes uniformes F.Cu–B.Cu.');
      const [x,y]=xy(...nums(n,'at')), drill=positive(+val(n,'drill'),'Taladro de vía'), size=positive(+val(n,'size'),'Diámetro de vía');
      if(drill>=size) throw Error('La vía necesita cobre alrededor del taladro.');
      target.add('via',{x,y,extent:'1-16',drill,diameter:size,shape:'round',alwaysstop:'no'});vias++;drills++;
      preview.push({type:'pad',x,y,sx:size,sy:size,drill,layer:1});
    } else {
      const layer=layerId(val(n,'layer'));
      if(![1,16].includes(layer)) throw Error('Pista en una capa no admitida.');
      const a=xy(...nums(n,'start')),b=xy(...nums(n,'end')),w=positive(+val(n,'width'),'Ancho de pista');
      const extra=tag==='arc'?{curve:curve(a,xy(...nums(n,'mid')),b)}:{};
      wire(target,a,b,w,layer,extra);preview.push({type:'wire',a,b,width:w,layer,...extra});tracks++;
    }
  }
  if(!outline.length) throw Error('Falta un contorno Edge.Cuts cerrado.');
  const degrees=new Map();
  for(const [a,b] of outline) for(const p of [a,b]) {const k=pointKey(p);degrees.set(k,(degrees.get(k)||0)+1);}
  if([...degrees.values()].some(n=>n!==2)) throw Error('Edge.Cuts tiene extremos abiertos o ramificaciones. Cierra el contorno en KiCad.');
  const plainEdges=plain.children.filter(n=>+n.attrs.layer===20);
  // Exact bounds of outline circles/arcs are not needed for conversion; the
  // drawing preview includes all endpoints and sampled arc extrema.
  for(const edge of plainEdges) {
    if(edge.tag==='wire') preview.push({type:'wire',a:[edge.attrs.x1,edge.attrs.y1],b:[edge.attrs.x2,edge.attrs.y2],width:edge.attrs.width,layer:20,curve:edge.attrs.curve});
    if(edge.tag==='circle') preview.push({type:'circle',x:edge.attrs.x,y:edge.attrs.y,radius:edge.attrs.radius,layer:20});
  }
  notes.push('Máscara, pasta, modelos 3D, reglas originales y áreas de exclusión no se exportan. Revisar reglas y capas de fabricación en EAGLE.');
  return {root,board,library,symbols,devicesets,nets,pinNets,components,preview,source,report:{engine:'kicad-eagle-web/0.1.0',format:'EAGLE XML 7.7',pads:padCount,composite_pth_pads:composite,tracks,vias,drills,components:components.size,source_nets:nets.size,notes:[...new Set(notes)],limitations:['Exportación experimental; requiere revisión visual y eléctrica en EAGLE.','La comprobación web no ejecuta el DRC ni kicad-cli.','Contorno comprobado por cierre de extremos; no se comprueban todas las intersecciones.']}};
}

function units(lib) {
  const common=[], result=new Map();
  if(one(lib,'extends')) throw Error('Símbolos heredados sin resolver no admitidos.');
  for(const n of kids(lib,'symbol')) {
    const match=n[1].match(/_(\d+)_(\d+)$/);
    if(!match) throw Error(`Unidad de símbolo no reconocida: ${n[1]}`);
    const u=+match[1], style=+match[2];
    if(style>1) continue;
    const items=n.slice(2).filter(Array.isArray);
    if(u===0)common.push(...items);else result.set(u,[...(result.get(u)||[]),...items]);
  }
  for(const [u,items] of result) result.set(u,[...common,...items]);
  return result;
}
function worldSymbol(inst,x,y) {
  const mirror=val(inst,'mirror');
  if(mirror==='x')y=-y;else if(mirror==='y')x=-x;else if(mirror)throw Error('Reflejo de símbolo no reconocido.');
  const [ix,iy,angle=0]=nums(inst,'at'), c=Math.cos(rad(angle)),s=Math.sin(rad(angle));
  return [ix+c*x-s*y,iy-s*x-c*y];
}
class UnionFind {
  constructor(){this.parent=new Map();this.positions=new Map();}
  add(p){const k=pointKey(p);if(!this.parent.has(k)){this.parent.set(k,k);this.positions.set(k,p);}return k;}
  find(k){let root=k;while(this.parent.get(root)!==root)root=this.parent.get(root);while(k!==root){const next=this.parent.get(k);this.parent.set(k,root);k=next;}return root;}
  root(p){return this.find(this.add(p));}
  join(a,b){this.parent.set(this.root(a),this.root(b));}
}
export function convertProject(board, text) {
  const source=parse(text);
  if(source[0]!=='kicad_sch') throw Error('Se necesita un esquemático moderno .kicad_sch.');
  for(const tag of ['sheet','bus','bus_entry','image','text_box','netclass_flag']) if(kids(source,tag).length) throw Error(`Proyecto no admitido: ${tag}. Se requiere una hoja sin buses ni imágenes.`);
  const definitions=new Map(kids(one(source,'lib_symbols'),'symbol').map(n=>[n[1],n]));
  const instances=kids(source,'symbol'), uf=new UnionFind(), pins=[], wires=[],labels=[],refInstances=new Map();
  const unitCache=new Map();
  for(const [id,lib] of definitions)unitCache.set(id,units(lib));
  for(const inst of instances) {
    const pr=props(inst),ref=pr.Reference,id=val(inst,'lib_id'),unit=+val(inst,'unit',1);
    if(+val(inst,'convert',1)!==1) throw Error('Representación alternativa de símbolo no admitida.');
    const items=unitCache.get(id)?.get(unit);
    if(!items) throw Error(`No se encuentra el símbolo embebido ${id}, unidad ${unit}.`);
    if(!ref)throw Error('Símbolo sin referencia.');
    const virtual=ref.startsWith('#');
    if(!virtual && val(inst,'on_board','yes')==='no')throw Error(`${ref}: símbolo excluido de la PCB no admitido en el proyecto web.`);
    if(!virtual) {
      if(!board.components.has(ref))throw Error(`Componente sin encapsulado en la PCB: ${ref}.`);
      if(!refInstances.has(ref))refInstances.set(ref,[]);
      if(refInstances.get(ref).some(i=>+val(i,'unit',1)===unit))throw Error(`${ref}: unidad duplicada.`);
      refInstances.get(ref).push(inst);
    }
    for(const pin of items.filter(n=>n[0]==='pin')) {
      const number=val(pin,'number'),[x,y]=nums(pin,'at'),q=worldSymbol(inst,x,y);
      uf.add(q);pins.push({ref,number,q,unit,virtual});
      if(ref.startsWith('#PWR'))labels.push({name:pr.Value,q});
    }
  }
  for(const ref of board.components.keys()) if(board.components.get(ref).pads.size && !refInstances.has(ref))throw Error(`Encapsulado con pads sin símbolo: ${ref}.`);
  for(const n of kids(source,'wire')) {
    const ends=kids(one(n,'pts'),'xy').map(p=>[+p[1],+p[2]]);
    if(ends.length!==2)throw Error('Cable sin dos extremos.');
    uf.join(...ends);wires.push({a:ends[0],b:ends[1],width:width(n)});
  }
  const junctions=kids(source,'junction').map(n=>nums(n,'at').slice(0,2));
  for(const q of junctions)uf.add(q);
  for(const tag of ['label','global_label','hierarchical_label'])for(const n of kids(source,tag)){const q=nums(n,'at').slice(0,2);uf.add(q);labels.push({name:n[1],q});}
  if(uf.positions.size*wires.length>15e6)throw Error('Esquemático demasiado complejo para la comprobación web. Usa el plugin nativo.');
  for(const {a,b} of wires) for(const q of uf.positions.values()) {
    if(q[0]>=Math.min(a[0],b[0])-1e-6&&q[0]<=Math.max(a[0],b[0])+1e-6&&q[1]>=Math.min(a[1],b[1])-1e-6&&q[1]<=Math.max(a[1],b[1])+1e-6&&Math.abs((b[0]-a[0])*(q[1]-a[1])-(b[1]-a[1])*(q[0]-a[0]))<1e-5)uf.join(a,q);
  }
  const named=new Map();
  for(const {name,q} of labels) {if(named.has(name))uf.join(q,named.get(name));else named.set(name,q);}
  const groups=new Map();
  for(const p of pins) if(!p.virtual){const r=uf.root(p.q);if(!groups.has(r))groups.set(r,[]);groups.get(r).push(p);}
  const roots=new Map(), claimed=new Map();
  for(const [r,ps] of groups) {
    const assigned=new Set();
    for(const p of ps) {
      const key=JSON.stringify([p.ref,p.number]);
      if(!board.pinNets.has(key))throw Error(`Pin sin pad correspondiente: ${p.ref}.${p.number}.`);
      if(board.pinNets.get(key))assigned.add(board.pinNets.get(key));
    }
    if(assigned.size>1)throw Error(`El esquemático une redes distintas de la PCB: ${[...assigned].join(', ')}.`);
    if(assigned.size===1) {
      const name=[...assigned][0];
      if(ps.some(p=>!board.pinNets.get(JSON.stringify([p.ref,p.number]))))throw Error(`La red ${name} contiene un pin sin red en la PCB.`);
      if(claimed.has(name)&&claimed.get(name)!==r)throw Error(`La PCB une grupos separados del esquemático en ${name}. Comprueba etiquetas y conexiones.`);
      claimed.set(name,r);roots.set(r,name);
    }else if(ps.length>1)throw Error('Hay pines conectados en el esquemático sin red asignada en la PCB.');
  }
  const seen=new Set(pins.filter(p=>!p.virtual).map(p=>JSON.stringify([p.ref,p.number])));
  for(const [key,name] of board.pinNets) if(name&&!seen.has(key))throw Error(`Pad conectado sin pin en el esquemático: ${key}.`);
  for(const nc of kids(source,'no_connect')) {
    const r=uf.root(nums(nc,'at').slice(0,2));
    if(roots.has(r)) {
      const name=roots.get(r),ps=groups.get(r)||[],signal=board.nets.get(name);
      // KiCad generates a separate named net for intentional NC pads. Accept
      // only isolated NC pads: no copper routes, shared pins or named labels.
      const isolated=/^unconnected-/i.test(name)&&ps.length===1&&!signal?.children.some(n=>n.tag==='wire'||n.tag==='via')&&!labels.some(l=>uf.root(l.q)===r);
      if(!isolated)throw Error(`Un pin marcado como no conectado tiene una red activa en la PCB: ${name}.`);
    }
  }
  // Each used library unit becomes a symbol. Devices preserve one-to-many
  // mappings for duplicate pads and composite through-hole copper lands.
  const symbolNames=new Map(),symbolPins=new Map();
  const directions={input:'in',output:'out',bidirectional:'io',tri_state:'hiz',passive:'pas',power_in:'pwr',power_out:'pwr',open_collector:'oc',open_emitter:'oc',no_connect:'nc',unspecified:'io',free:'pas'};
  for(const inst of instances) {
    if(props(inst).Reference.startsWith('#'))continue;
    const id=val(inst,'lib_id'),unit=+val(inst,'unit',1),key=JSON.stringify([id,unit]);
    if(symbolNames.has(key))continue;
    const name=`SYM_${symbolNames.size+1}`,sym=board.symbols.add('symbol',{name}),numbers=new Set();
    symbolNames.set(key,name);symbolPins.set(key,numbers);
    for(const item of unitCache.get(id).get(unit)) {
      if(item[0]!=='pin') {graphics(sym,item,94);continue;}
      const num=val(item,'number'),[x,y,a=0]=nums(item,'at'),length=+val(item,'length');
      if(numbers.has(num))throw Error(`Pin duplicado en símbolo: ${id}.${num}.`);
      numbers.add(num);
      sym.add('pin',{name:num,x,y,visible:'off',length:'point',direction:directions[item[1]]||'pas',rot:`R${a}`});
      const end=[x+length*Math.cos(rad(a)),y+length*Math.sin(rad(a))];
      wire(sym,[x,y],end,.1524,94);
      const pinName=val(item,'name');
      if(pinName&&pinName!=='~')sym.add('text',{x:end[0]+.3,y:end[1]+.3,size:1,layer:94,font:'vector'},pinName);
      sym.add('text',{x:(x+end[0])/2,y:(y+end[1])/2+.3,size:.8,layer:94,font:'vector'},num);
    }
    sym.add('text',{x:0,y:2,size:1.27,layer:95},'>NAME');sym.add('text',{x:0,y:-2,size:1.27,layer:96},'>VALUE');
  }
  const [schRoot,sch]=document('schematic');
  sch.add('description',{},'Linked KiCad web export. Connectivity reconstructed locally and compared with PCB pad nets.');
  sch.add('libraries').children.push(board.library);
  sch.add('attributes');sch.add('variantdefs');sch.add('classes').add('class',{number:0,name:'default',width:0,drill:0});
  const parts=sch.add('parts'),sheet=sch.add('sheets').add('sheet'),plain=sheet.add('plain'),placed=sheet.add('instances'),nets=sheet.add('nets');
  const page=(x,y)=>[x,-y];
  for(const [ref,insts] of refInstances) {
    const comp=board.components.get(ref),ds=board.devicesets.add('deviceset',{name:`DEV_${safe(comp.pkg)}`,uservalue:'yes'});
    const gates=ds.add('gates'),device=ds.add('devices').add('device',{name:'',package:comp.pkg}),connects=device.add('connects'),covered=new Set();
    for(const inst of insts) {
      const unit=+val(inst,'unit',1),id=val(inst,'lib_id'),key=JSON.stringify([id,unit]),gate=`G$${unit}`;
      gates.add('gate',{name:gate,symbol:symbolNames.get(key),x:0,y:0,addlevel:'must'});
      for(const num of symbolPins.get(key)) if(comp.pads.has(num)){connects.add('connect',{gate,pin:num,pad:comp.pads.get(num).join(' '),route:'all'});covered.add(num);}
      const [x,y]=page(...nums(inst,'at')),mirror=val(inst,'mirror');
      let angle=nums(inst,'at')[2]||0;if(mirror==='x')angle+=180;
      const placedInst=placed.add('instance',{part:ref,gate,x,y,smashed:'yes',rot:`${mirror?'M':''}R${angle%360}`});
      for(const p of kids(inst,'property')) if(['Reference','Value'].includes(p[1])&&val(one(p,'effects',[]),'hide','no')!=='yes') {
        const [px,py]=page(...nums(p,'at'));
        placedInst.add('attribute',{name:p[1]==='Reference'?'NAME':'VALUE',x:px,y:py,size:val(one(one(p,'effects',[]),'font',[]),'size',1.27),layer:p[1]==='Reference'?95:96,display:'value',rot:`R${nums(p,'at')[2]||0}`});
      }
    }
    if([...comp.pads.keys()].some(p=>!covered.has(p)))throw Error(`${ref}: encapsulado con pads sin correspondencia en el símbolo.`);
    device.add('technologies').add('technology',{name:''});
    parts.add('part',{name:ref,library:'KiCadWeb',deviceset:ds.attrs.name,device:'',value:props(insts[0]).Value||comp.value});
    // Match board and schematic values to avoid consistency warnings.
    board.board.children.find(n=>n.tag==='elements').children.find(n=>n.attrs.name===ref).attrs.value=props(insts[0]).Value||comp.value;
  }
  for(const inst of instances) if(props(inst).Reference.startsWith('#')) {
    for(const item of unitCache.get(val(inst,'lib_id')).get(+val(inst,'unit',1)))if(item[0]!=='pin')graphics(plain,item,97,(x,y)=>page(...worldSymbol(inst,x,y)));
  }
  for(const tag of ['text','rectangle','polyline','circle','arc'])for(const n of kids(source,tag))graphics(plain,n,97,page);
  for(const nc of kids(source,'no_connect')){const [x,y]=page(...nums(nc,'at'));for(const sign of [-1,1])wire(plain,[x-.35,y-sign*.35],[x+.35,y+sign*.35],.127,97);}
  const eagleNets=new Map(), segments=new Map();
  const segment = q => {
    const r=uf.root(q),name=roots.get(r);if(!name)return null;
    if(!eagleNets.has(name))eagleNets.set(name,nets.add('net',{name,class:0}));
    // Labels already joined equal-name islands. A single segment may contain
    // disconnected graphical wires; the EAGLE net name preserves equivalence.
    if(!segments.has(r))segments.set(r,eagleNets.get(name).add('segment'));
    return segments.get(r);
  };
  const emittedPins=new Set();
  for(const p of pins)if(!p.virtual) {
    const target=segment(p.q),key=JSON.stringify([p.ref,p.unit,p.number]);
    if(target&&!emittedPins.has(key)){target.add('pinref',{part:p.ref,gate:`G$${p.unit}`,pin:p.number});emittedPins.add(key);}
  }
  for(const w of wires){const target=segment(w.a);if(!target)throw Error('Cable sin red determinable a partir de los pads de la PCB.');wire(target,page(...w.a),page(...w.b),w.width,91);}
  for(const q of junctions){const target=segment(q);if(target){const [x,y]=page(...q);target.add('junction',{x,y});}}
  for(const {q} of labels){const target=segment(q);if(target){const [x,y]=page(...q);target.add('label',{x,y,size:1.27,layer:95});}}
  sch.add('errors');
  const [libRoot,lib]=document('library');lib.attrs.name='KiCadWeb';lib.children=board.library.children;
  const nameMap=netNames([...board.nets.keys()]);
  for(const [name,node] of board.nets)node.attrs.name=nameMap.get(name);
  for(const [name,node] of eagleNets)node.attrs.name=nameMap.get(name);
  board.report.mode='project';board.report.schematic_units=placed.children.length;
  board.report.schematic_wires=wires.length;board.report.checked_pinrefs=emittedPins.size;
  board.report.connectivity_check='Reconstructed schematic graph compared with PCB pad nets; no kicad-cli netlist used.';
  board.report.eagle_net_name_map=Object.fromEntries(nameMap);
  board.report.notes.push('Esquemático de una hoja; posiciones conservadas. Revisar textos y nombres de pines. Bibliotecas embebidas.');
  return {brd:xml(board.root),sch:xml(schRoot),lbr:xml(libRoot),report:board.report,preview:board.preview};
}
export function convert(pcbText, schematicText = null) {
  const board=convertBoard(pcbText);
  if(schematicText)return convertProject(board,schematicText);
  const mapping=netNames([...board.nets.keys()]);
  for(const [name,node] of board.nets)node.attrs.name=mapping.get(name);
  board.report.mode='board';board.report.eagle_net_name_map=Object.fromEntries(mapping);
  return {brd:xml(board.root),report:board.report,preview:board.preview};
}
