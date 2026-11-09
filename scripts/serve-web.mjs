// SPDX-License-Identifier: GPL-3.0-only
import {createServer} from 'node:http';
import {readFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {resolve,extname,sep} from 'node:path';
const root=fileURLToPath(new URL('../web/',import.meta.url));
const types={'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8','.svg':'image/svg+xml','.json':'application/json','.md':'text/plain; charset=utf-8'};
const port=Number(process.env.PORT||8765);
createServer(async(req,res)=>{
  try{
    const path=decodeURIComponent(new URL(req.url,'http://localhost').pathname);
    const target=resolve(root,'.'+(path.endsWith('/')?path+'index.html':path));
    if(!target.startsWith(root.endsWith(sep)?root:root+sep)){res.writeHead(403).end();return;}
    const data=await readFile(target);res.writeHead(200,{'Content-Type':types[extname(target)]||'text/plain; charset=utf-8','Cache-Control':'no-store'});res.end(data);
  }catch{res.writeHead(404).end('Not found');}
}).listen(port,'127.0.0.1',()=>console.log(`KiCad → EAGLE: http://127.0.0.1:${port}`));
