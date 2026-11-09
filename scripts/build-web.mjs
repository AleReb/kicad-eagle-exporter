// SPDX-License-Identifier: GPL-3.0-only
import {readdir,readFile,mkdir,writeFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {join,relative} from 'node:path';
import {makeZip} from '../web/zip.js';
const root=fileURLToPath(new URL('../web/',import.meta.url)),out=fileURLToPath(new URL('../dist/',import.meta.url));
const files={};
async function collect(dir){for(const entry of await readdir(dir,{withFileTypes:true})){
  if(['tests','package.json','node_modules'].includes(entry.name))continue;
  const path=join(dir,entry.name);if(entry.isDirectory())await collect(path);else files[relative(root,path).replaceAll('\\','/')]=new Uint8Array(await readFile(path));
}}
await collect(root);await mkdir(out,{recursive:true});const path=join(out,'kicad-eagle-web-github-pages.zip');await writeFile(path,makeZip(files));console.log(path);
