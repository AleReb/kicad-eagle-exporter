// SPDX-License-Identifier: GPL-3.0-only
import {convert} from './converter.js';
self.onmessage=({data})=>{
  try{self.postMessage({ok:true,result:convert(data.pcb,data.sch)});}
  catch(error){self.postMessage({ok:false,error:error.message||String(error)});}
};
