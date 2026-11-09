// SPDX-License-Identifier: GPL-3.0-only
// ZIP store writer and bounded ZIP reader (stored/deflate; no dependencies).
const encoder=new TextEncoder(),decoder=new TextDecoder('utf-8',{fatal:true});
const table=Uint32Array.from({length:256},(_,n)=>{for(let i=0;i<8;i++)n=(n&1)?0xedb88320^(n>>>1):n>>>1;return n>>>0;});
export const crc32=bytes=>{let c=0xffffffff;for(const b of bytes)c=table[(c^b)&255]^(c>>>8);return(c^0xffffffff)>>>0;};
const join=parts=>{const result=new Uint8Array(parts.reduce((n,p)=>n+p.length,0));let offset=0;for(const p of parts){result.set(p,offset);offset+=p.length;}return result;};
export function makeZip(files) {
  const local=[],central=[];let offset=0;
  for(const [name,content] of Object.entries(files)) {
    const filename=encoder.encode(name),data=typeof content==='string'?encoder.encode(content):content,crc=crc32(data);
    const h=new Uint8Array(30+filename.length),v=new DataView(h.buffer);
    v.setUint32(0,0x04034b50,true);v.setUint16(4,20,true);v.setUint16(6,0x800,true);
    v.setUint16(12,33,true);v.setUint32(14,crc,true);v.setUint32(18,data.length,true);v.setUint32(22,data.length,true);v.setUint16(26,filename.length,true);h.set(filename,30);
    const ch=new Uint8Array(46+filename.length),cv=new DataView(ch.buffer);
    cv.setUint32(0,0x02014b50,true);cv.setUint16(4,20,true);cv.setUint16(6,20,true);cv.setUint16(8,0x800,true);cv.setUint16(14,33,true);
    cv.setUint32(16,crc,true);cv.setUint32(20,data.length,true);cv.setUint32(24,data.length,true);cv.setUint16(28,filename.length,true);cv.setUint32(42,offset,true);ch.set(filename,46);
    local.push(h,data);central.push(ch);offset+=h.length+data.length;
  }
  const end=new Uint8Array(22),v=new DataView(end.buffer),count=central.length;
  v.setUint32(0,0x06054b50,true);v.setUint16(8,count,true);v.setUint16(10,count,true);v.setUint32(12,central.reduce((n,b)=>n+b.length,0),true);v.setUint32(16,offset,true);
  return join([...local,...central,end]);
}
export async function readZip(input) {
  const bytes=input instanceof Uint8Array?input:new Uint8Array(input),v=new DataView(bytes.buffer,bytes.byteOffset,bytes.byteLength);
  const fail=()=>{throw Error('ZIP inválido, incompleto o ZIP64 no admitido.');};
  if(bytes.length<22||bytes.length>80*1024*1024)throw Error('El ZIP debe pesar menos de 80 MB.');
  let eocd=-1;
  for(let i=bytes.length-22;i>=Math.max(0,bytes.length-65557);i--)if(v.getUint32(i,true)===0x06054b50&&i+22+v.getUint16(i+20,true)===bytes.length){eocd=i;break;}
  if(eocd<0)fail();
  const count=v.getUint16(eocd+10,true),start=v.getUint32(eocd+16,true),length=v.getUint32(eocd+12,true);
  if(count>2000||v.getUint16(eocd+4,true)||v.getUint16(eocd+6,true)||start+length>eocd||count!==v.getUint16(eocd+8,true))fail();
  const files=[],names=new Set();let pos=start,total=0;
  for(let i=0;i<count;i++) {
    if(pos+46>start+length||v.getUint32(pos,true)!==0x02014b50)fail();
    const flags=v.getUint16(pos+8,true),method=v.getUint16(pos+10,true),crc=v.getUint32(pos+16,true),compressed=v.getUint32(pos+20,true),size=v.getUint32(pos+24,true);
    const nl=v.getUint16(pos+28,true),el=v.getUint16(pos+30,true),cl=v.getUint16(pos+32,true),local=v.getUint32(pos+42,true);
    if(pos+46+nl+el+cl>start+length)fail();
    const name=decoder.decode(bytes.slice(pos+46,pos+46+nl));pos+=46+nl+el+cl;
    if(!/\.(kicad_pcb|kicad_sch|kicad_pro)$/i.test(name)||name.includes('__MACOSX/'))continue;
    if(name.split(/[\\/]/).includes('..')||name.startsWith('/')||names.has(name))throw Error('Nombres de archivo no válidos o duplicados dentro del ZIP.');
    names.add(name);
    if(flags&1)throw Error('No se admiten ZIP con contraseña.');
    if(![0,8].includes(method))throw Error('Usa un ZIP normal con compresión Deflate.');
    total+=size;if(size>64*1024*1024||total>96*1024*1024)throw Error('El contenido del ZIP supera el límite de 96 MB.');
    if(local+30>start||v.getUint32(local,true)!==0x04034b50)fail();
    const offset=local+30+v.getUint16(local+26,true)+v.getUint16(local+28,true);
    if(offset+compressed>start)fail();
    let data=bytes.slice(offset,offset+compressed);
    if(method===8) {
      let stream;
      try{stream=new Blob([data]).stream().pipeThrough(new DecompressionStream('deflate-raw'));}
      catch{throw Error('Este navegador no puede descomprimir ZIP. Usa Chrome, Edge o Firefox actualizado, o selecciona los archivos sueltos.');}
      const reader=stream.getReader(),chunks=[];let expanded=0;
      while(true){const {done,value}=await reader.read();if(done)break;expanded+=value.length;if(expanded>size){await reader.cancel();fail();}chunks.push(value);}
      data=join(chunks);
    }
    if(data.length!==size||crc32(data)!==crc)throw Error(`El archivo ${name} está dañado (CRC incorrecto).`);
    files.push({name,text:decoder.decode(data),size:data.length});
  }
  if(pos!==start+length)fail();
  return files;
}
