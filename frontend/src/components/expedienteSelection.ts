/** Browser selection only. The canonical importer accepts arbitrary original formats;
 * extraction and preview support are separate. No archive expansion or content parsing. */
export type SelectedOriginal={clientImportId:string;file:File;relativePath?:string;omittedReason?:string};
export type ImportSession={id:string;tenderId:string;files:SelectedOriginal[];omittedCount?:number};
export function safeRelativePath(value:string):string|undefined{
 const path=value.replace(/\\/g,'/');
 if(!path||path.startsWith('/')||/^[a-z]:/i.test(path)||/[\x00-\x1f]/.test(path)||path.split('/').some(p=>!p||p==='.'||p==='..'))return undefined;
 return path;
}
export const displayFilename=(name:string)=>name.replace(/\\/g,'/').split('/').pop()||'Archivo sin nombre';
export function selectedOriginal(file:File,path=file.webkitRelativePath||file.name):SelectedOriginal{
 const relativePath=safeRelativePath(path);
 return {clientImportId:crypto.randomUUID(),file,relativePath,...(!relativePath?{omittedReason:'La ubicación relativa del archivo no es segura.'}:{})};
}
// Narrow browser interface: directory reader requires repeated calls until an empty batch.
export type DroppedEntry={name:string;isFile:boolean;isDirectory:boolean;file:(success:(file:File)=>void,error:(error:DOMException)=>void)=>void;createReader:()=>{readEntries:(success:(entries:DroppedEntry[])=>void,error:(error:DOMException)=>void)=>void}};
export async function enumerateEntry(entry:DroppedEntry,parent=''):Promise<SelectedOriginal[]>{
 const path=parent?`${parent}/${entry.name}`:entry.name;
 if(entry.isFile)return [selectedOriginal(await new Promise<File>((resolve,reject)=>entry.file(resolve,reject)),path)];
 if(!entry.isDirectory)throw new Error('UNSUPPORTED_BROWSER_ENTRY');
 if(!safeRelativePath(path))throw new Error('UNSAFE_DIRECTORY');
 const reader=entry.createReader(),files:SelectedOriginal[]=[];
 for(;;){const children=await new Promise<DroppedEntry[]>((resolve,reject)=>reader.readEntries(resolve,reject));if(!children.length)break;for(const child of children)files.push(...await enumerateEntry(child,path));}
 return files;
}
export async function droppedOriginals(transfer:DataTransfer):Promise<SelectedOriginal[]>{
 // Capture every handle synchronously while the drop event still owns its data store.
 const entries=Array.from(transfer.items??[]).filter(i=>i.kind==='file').map(item=>({entry:item.webkitGetAsEntry?.() as DroppedEntry|null,file:item.getAsFile()}));
 if(!entries.length)return Array.from(transfer.files).map(f=>selectedOriginal(f));
 const files:SelectedOriginal[]=[];
 for(const item of entries){if(item.entry)files.push(...await enumerateEntry(item.entry));else if(item.file)files.push(selectedOriginal(item.file));else throw new Error('DIRECTORY_DROP_UNAVAILABLE');}
 return files;
}
