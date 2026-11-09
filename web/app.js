// SPDX-License-Identifier: GPL-3.0-only
import {makeZip,readZip} from './zip.js';
const $=id=>document.getElementById(id);
let files=[],urls=[],output=null,busy=false,loadGeneration=0;
const mode=()=>document.querySelector('input[name="mode"]:checked').value;
const status=(text,type='')=>{$('status').textContent=text;$('status').className=`status ${type}`;};
const basename=name=>name.split(/[\\/]/).at(-1).replace(/\.[^.]+$/,'');
const filename=()=>($('output-name').value.trim().replace(/[^\p{L}\p{N}_.-]/gu,'_').replace(/^\.+/,'').slice(0,80)||'mi_proyecto');
const sizes=n=>n<1024?`${n} B`:`${(n/1024).toFixed(1)} KB`;
function clearResult(){for(const url of urls)URL.revokeObjectURL(url);urls=[];output=null;$('results').hidden=true;$('output-placeholder').hidden=false;$('empty-preview').hidden=false;$('board-canvas').hidden=true;$('result-state').textContent='En espera';$('result-state').className='status-pill';}
function updateReady(){
  const hasPcb=!!$('pcb-select').value,hasSch=!!$('sch-select').value;
  $('convert').disabled=busy||!hasPcb||(mode()==='project'&&!hasSch);
  $('sch-field').hidden=mode()!=='project';
  $('requirements').textContent=mode()==='project'?'Selecciona la PCB y su esquemático correspondiente. El .kicad_pro es opcional: no contiene el circuito.':'Necesitas una placa .kicad_pcb con contorno cerrado y dos capas de cobre.';
}
function renderFiles(){
  const oldPcb=$('pcb-select').value,oldSch=$('sch-select').value;
  $('file-list').replaceChildren();
  for(const [i,file] of files.entries()){
    const row=document.createElement('div');row.className='file-row';
    const name=document.createElement('span');name.className='filename';name.textContent=file.name;name.title=file.name;
    const size=document.createElement('small');size.textContent=sizes(file.size);
    const remove=document.createElement('button');remove.type='button';remove.className='remove';remove.textContent='×';remove.disabled=busy;remove.setAttribute('aria-label',`Quitar ${file.name}`);
    remove.onclick=()=>{files.splice(i,1);clearResult();renderFiles();status('');};row.append(name,size,remove);$('file-list').append(row);
  }
  for(const [id,extension,old] of [['pcb-select','.kicad_pcb',oldPcb],['sch-select','.kicad_sch',oldSch]]){
    const select=$(id);select.replaceChildren();
    const empty=document.createElement('option');empty.value='';empty.textContent=`Selecciona un ${extension}`;select.append(empty);
    const matches=files.map((f,i)=>({f,i})).filter(({f})=>f.name.toLowerCase().endsWith(extension));
    for(const {f,i} of matches){const option=document.createElement('option');option.value=String(i);option.textContent=f.name;select.append(option);}
    if(old!==''&&matches.some(({i})=>String(i)===old))select.value=old;
    else if(matches.length===1)select.value=String(matches[0].i);
  }
  $('selectors').hidden=!files.length;
  if($('pcb-select').value!=='')$('output-name').value=basename(files[+$('pcb-select').value].name);
  updateReady();
}
async function loadFiles(incoming){
  if(busy)return;
  const generation=++loadGeneration;lock(true);clearResult();status('Leyendo archivos…');
  try{
    const additions=[];
    for(const file of incoming){
      if(file.size>80*1024*1024)throw Error(`${file.name}: máximo 80 MB por archivo ZIP o 64 MB por archivo KiCad.`);
      if(/\.zip$/i.test(file.name))additions.push(...await readZip(await file.arrayBuffer()));
      else if(/\.(kicad_pcb|kicad_sch|kicad_pro)$/i.test(file.name)){
        if(file.size>64*1024*1024)throw Error('El archivo KiCad supera 64 MB.');
        additions.push({name:file.name,text:await file.text(),size:file.size});
      }
      else throw Error(`Archivo no admitido: ${file.name}. Selecciona .kicad_pcb, .kicad_sch o .zip.`);
    }
    if(!additions.length)throw Error('No hay archivos KiCad dentro del ZIP.');
    const merged=[...files];for(const file of additions){const i=merged.findIndex(f=>f.name===file.name);if(i>=0)merged[i]=file;else merged.push(file);}
    if(merged.reduce((n,f)=>n+f.size,0)>96*1024*1024)throw Error('El conjunto de archivos supera 96 MB.');
    if(generation!==loadGeneration)return;
    files=merged;renderFiles();status(`${additions.length} archivo(s) leído(s). Todo permanece en tu equipo.`);
  }catch(error){status(error.message,'error');}
  finally{lock(false);$('files').value='';}
}
$('dropzone').onclick=()=>{if(!busy)$('files').click();};
$('files').onchange=()=>loadFiles([...$('files').files]);
for(const event of ['dragenter','dragover'])$('dropzone').addEventListener(event,e=>{e.preventDefault();$('dropzone').classList.add('dragover');});
for(const event of ['dragleave','drop'])$('dropzone').addEventListener(event,e=>{e.preventDefault();$('dropzone').classList.remove('dragover');});
$('dropzone').addEventListener('drop',e=>loadFiles([...e.dataTransfer.files]));
document.addEventListener('dragover',e=>e.preventDefault());document.addEventListener('drop',e=>e.preventDefault());
for(const input of document.querySelectorAll('input[name="mode"]'))input.onchange=()=>{clearResult();updateReady();status('');};
for(const id of ['pcb-select','sch-select'])$(id).onchange=()=>{
  clearResult();status('');
  if(id==='pcb-select'&&$(id).value!==''){
    const base=basename(files[+$(id).value].name);$('output-name').value=base;
    const schIndex=files.findIndex(f=>f.name.endsWith('.kicad_sch')&&basename(f.name)===base);if(schIndex>=0)$('sch-select').value=String(schIndex);
  }
  updateReady();
};
$('output-name').oninput=()=>{if(output)showDownloads();};
function lock(value){busy=value;for(const el of document.querySelectorAll('input,select,#dropzone,#demo,.remove'))el.disabled=value;updateReady();}
$('convert').onclick=()=>{
  if(busy)return;
  clearResult();lock(true);status('Convirtiendo y comprobando geometría y conexiones…');$('result-state').textContent='Convirtiendo';
  let worker;
  const done=()=>{clearTimeout(timeout);worker?.terminate();lock(false);};
  const error=message=>{done();$('result-state').textContent='Revisar entrada';status(message,'error');};
  const timeout=setTimeout(()=>error('El diseño superó el tiempo de conversión (90 s). Prueba un proyecto más pequeño o el plugin nativo.'),90000);
  try{
    worker=new Worker(new URL('./worker.js',import.meta.url),{type:'module'});
    worker.onmessage=({data})=>{
      if(!data.ok){error(data.error);return;}
      done();output=data.result;
      $('results').hidden=false;$('output-placeholder').hidden=true;$('empty-preview').hidden=true;$('board-canvas').hidden=false;
      $('result-state').textContent='Listo';$('result-state').className='status-pill ready';
      const stats=$('stats');stats.replaceChildren();
      for(const [value,label] of [[output.report.components,'Componentes'],[output.report.pads,'Pads'],[output.report.tracks,'Pistas'],[output.report.source_nets,'Redes']]){
        const div=document.createElement('div'),strong=document.createElement('strong'),small=document.createElement('small');strong.textContent=value;small.textContent=label;div.append(strong,small);stats.append(div);
      }
      $('notes').replaceChildren();for(const text of [...output.report.notes,...output.report.limitations]){const li=document.createElement('li');li.textContent=text;$('notes').append(li);}
      $('report').textContent=JSON.stringify(output.report,null,2);showDownloads();drawPreview(output.preview);
      status('Conversión terminada. Revisa el informe y abre el resultado en EAGLE antes de fabricar.','success');
    };
    worker.onerror=()=>error('No se pudo iniciar el conversor. Abre la web mediante HTTP o GitHub Pages, y comprueba que worker.js esté disponible.');
    worker.postMessage({pcb:files[+$('pcb-select').value].text,sch:mode()==='project'?files[+$('sch-select').value].text:null});
  }catch(e){error(e.message);}
};
function outputFiles(){
  const name=filename(),result={[`${name}.brd`]:output.brd};
  if(output.sch){result[`${name}.sch`]=output.sch;result[`${name}.lbr`]=output.lbr;}
  result[`${name}.${output.sch?'project-report':'report'}.json`]=JSON.stringify(output.report,null,2);
  result['LEEME.txt']='Conversión experimental a EAGLE XML 7.7.\nAbre .sch y .brd con el mismo nombre y en la misma carpeta.\nLa biblioteca está embebida; se incluye también como .lbr.\nRevisa conexiones, geometría, taladros y reglas antes de fabricar.\nNo es el formato binario de EAGLE 5 o anterior.\n';
  return result;
}
function showDownloads(){
  for(const url of urls)URL.revokeObjectURL(url);urls=[];$('downloads').replaceChildren();
  for(const [name,text] of Object.entries(outputFiles())){
    if(name==='LEEME.txt')continue;
    const url=URL.createObjectURL(new Blob([text],{type:name.endsWith('.json')?'application/json':'application/xml'}));urls.push(url);
    const link=document.createElement('a');link.href=url;link.download=name;const label=document.createElement('span');label.textContent=name;
    const small=document.createElement('small');small.textContent=`${sizes(new TextEncoder().encode(text).length)} ↓`;link.append(label,small);$('downloads').append(link);
  }
}
$('download-all').onclick=()=>{
  if(!output)return;
  const url=URL.createObjectURL(new Blob([makeZip(outputFiles())],{type:'application/zip'})),a=document.createElement('a');a.href=url;a.download=`${filename()}-eagle.zip`;a.click();setTimeout(()=>URL.revokeObjectURL(url),60000);
};
$('demo').onclick=async()=>{
  if(busy)return;lock(true);clearResult();status('Cargando ejemplo incluido…');
  try{
    const names=['demo.kicad_pcb','demo.kicad_sch'],responses=await Promise.all(names.map(n=>fetch(new URL(`./examples/${n}`,import.meta.url))));
    if(responses.some(r=>!r.ok))throw Error('No se pudo cargar el ejemplo.');
    const texts=await Promise.all(responses.map(r=>r.text()));files=names.map((name,i)=>({name,text:texts[i],size:new TextEncoder().encode(texts[i]).length}));
    document.querySelector('input[value="project"]').checked=true;renderFiles();status('Ejemplo listo. Pulsa «Convertir a EAGLE».');
  }catch(e){status(e.message,'error');}finally{lock(false);}
};
function arcPoints(item){
  if(!item.curve)return [item.a,item.b];
  const theta=item.curve*Math.PI/180,[x1,y1]=item.a,[x2,y2]=item.b,dx=x2-x1,dy=y2-y1;
  const cx=(x1+x2)/2-dy/(2*Math.tan(theta/2)),cy=(y1+y2)/2+dx/(2*Math.tan(theta/2));
  const r=Math.hypot(x1-cx,y1-cy),a=Math.atan2(y1-cy,x1-cx),steps=Math.max(12,Math.ceil(Math.abs(item.curve)/5));
  return Array.from({length:steps+1},(_,i)=>[cx+r*Math.cos(a+theta*i/steps),cy+r*Math.sin(a+theta*i/steps)]);
}
function drawPreview(items){
  const canvas=$('board-canvas'),rect=canvas.getBoundingClientRect(),ratio=devicePixelRatio||1;
  canvas.width=rect.width*ratio;canvas.height=rect.height*ratio;
  const ctx=canvas.getContext('2d');ctx.scale(ratio,ratio);
  const points=items.flatMap(n=>n.type==='wire'?arcPoints(n):n.type==='circle'?[[n.x-n.radius,n.y-n.radius],[n.x+n.radius,n.y+n.radius]]:[[n.x-n.sx,n.y-n.sy],[n.x+n.sx,n.y+n.sy]]);
  if(!points.length)return;
  let minX=Infinity,maxX=-Infinity,minY=Infinity,maxY=-Infinity;
  for(const [x,y] of points){minX=Math.min(minX,x);maxX=Math.max(maxX,x);minY=Math.min(minY,y);maxY=Math.max(maxY,y);}
  const scale=Math.min((rect.width-65)/(maxX-minX||1),(rect.height-65)/(maxY-minY||1));
  const tx=x=>(x-(minX+maxX)/2)*scale+rect.width/2,ty=y=>rect.height/2-(y-(minY+maxY)/2)*scale;
  for(const item of [...items].sort((a,b)=>(a.layer===20?2:a.layer===1?1:0)-(b.layer===20?2:b.layer===1?1:0))){
    ctx.strokeStyle=item.layer===20?'#536948':item.layer===16?'#6b96aa':'#9a613c';ctx.fillStyle=ctx.strokeStyle;ctx.lineCap='round';ctx.lineJoin='round';
    if(item.type==='wire'){
      ctx.beginPath();const ps=arcPoints(item);ctx.moveTo(tx(ps[0][0]),ty(ps[0][1]));for(const p of ps.slice(1))ctx.lineTo(tx(p[0]),ty(p[1]));ctx.lineWidth=Math.max(1,item.width*scale);ctx.stroke();
    }else if(item.type==='circle'){
      ctx.beginPath();ctx.arc(tx(item.x),ty(item.y),item.radius*scale,0,2*Math.PI);ctx.lineWidth=1;ctx.stroke();
    }else{
      ctx.save();ctx.translate(tx(item.x),ty(item.y));ctx.rotate(-(parseFloat(item.angle?.slice(1))||0)*Math.PI/180);ctx.beginPath();ctx.roundRect(-item.sx*scale/2,-item.sy*scale/2,item.sx*scale,item.sy*scale,Math.min(item.sx,item.sy)*scale*.24);ctx.fill();ctx.restore();
      if(item.drill){ctx.fillStyle='#f2f5eb';ctx.beginPath();ctx.arc(tx(item.x),ty(item.y),item.drill*scale/2,0,2*Math.PI);ctx.fill();}
    }
  }
}
new ResizeObserver(()=>{if(output)drawPreview(output.preview);}).observe($('preview'));
window.addEventListener('beforeunload',()=>urls.forEach(url=>URL.revokeObjectURL(url)));
updateReady();
