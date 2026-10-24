import {beforeEach,it,expect,vi} from 'vitest';
import axios from 'axios';
import {documentPath,tendersApi} from './tenders';
beforeEach(()=>vi.restoreAllMocks());
it('UIR3-37: identifiers are URL segments, never arbitrary filesystem URLs',()=>{const url=documentPath('/api','t','../../etc/passwd');expect(url).toBe('/api/tenders/t/documents/..%2F..%2Fetc%2Fpasswd');expect(url).not.toContain('file://');});
it('UIR3-39: malformed pages fail closed instead of populating viewer',async()=>{vi.spyOn(axios,'get').mockResolvedValue({data:[{document_id:'a',page_number:-1,text:'wrong'}]});await expect(tendersApi.pages('/api','t','a')).rejects.toThrow('INVALID_PAGES');});
it('UIR3-39: non binary content cannot masquerade as PDF',async()=>{vi.spyOn(axios,'get').mockResolvedValue({data:'<html>unavailable</html>'});await expect(tendersApi.content('/api','t','a')).rejects.toThrow('INVALID_PDF');});
it('single-file import validates result identity and sends exact immutable File with canonical fields',async()=>{const file=new File(['exact bytes'],'source.pdf');const post=vi.spyOn(axios,'post').mockResolvedValue({data:[{filename:'wrong.pdf',status:'IMPORTED'}]});await expect(tendersApi.import('/api','t',file,'NEW_REVISION','target')).rejects.toThrow('INVALID_IMPORT_RESULT');const body=post.mock.calls[0][1] as FormData;expect(body.get('files')).toMatchObject({name:file.name,size:file.size,type:file.type});expect(body.get('revision_of_document_id')).toBe('target');expect(body.get('conflict_action')).toBe('NEW_REVISION');});
it('folder import fixes multipart basename, preserves safe relative metadata and original bytes',async()=>{
 const file=new File(['exact folder bytes'],'Same.pdf',{type:'application/pdf'});Object.defineProperty(file,'webkitRelativePath',{value:'Root/Folder/Same.pdf'});
 const post=vi.spyOn(axios,'post').mockResolvedValue({data:[{filename:'Same.pdf',status:'IMPORTED',document_id:'new'}]});
 await tendersApi.import('/api','t',file,'NONE',undefined,'Root/Folder/Same.pdf');const body=post.mock.calls[0][1] as FormData;const transmitted=body.get('files') as File;
 expect(transmitted.name).toBe('Same.pdf');expect(body.get('source_relative_paths')).toBe('Root/Folder/Same.pdf');expect(file.webkitRelativePath).toBe('Root/Folder/Same.pdf');
 const contents=await new Promise<string>((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(String(reader.result));reader.onerror=reject;reader.readAsText(transmitted);});expect(contents).toBe('exact folder bytes');
});
