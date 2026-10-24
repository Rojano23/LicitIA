import {beforeEach,it,expect,vi} from 'vitest';
import axios from 'axios';
import {documentPath,tendersApi} from './tenders';
beforeEach(()=>vi.restoreAllMocks());
it('UIR3-37: identifiers are URL segments, never arbitrary filesystem URLs',()=>{const url=documentPath('/api','t','../../etc/passwd');expect(url).toBe('/api/tenders/t/documents/..%2F..%2Fetc%2Fpasswd');expect(url).not.toContain('file://');});
it('UIR3-39: malformed pages fail closed instead of populating viewer',async()=>{vi.spyOn(axios,'get').mockResolvedValue({data:[{document_id:'a',page_number:-1,text:'wrong'}]});await expect(tendersApi.pages('/api','t','a')).rejects.toThrow('INVALID_PAGES');});
it('UIR3-39: non binary content cannot masquerade as PDF',async()=>{vi.spyOn(axios,'get').mockResolvedValue({data:'<html>unavailable</html>'});await expect(tendersApi.content('/api','t','a')).rejects.toThrow('INVALID_PDF');});
it('single-file import validates result identity and sends exact immutable File with canonical fields',async()=>{const file=new File(['exact bytes'],'source.pdf');const post=vi.spyOn(axios,'post').mockResolvedValue({data:[{filename:'wrong.pdf',status:'IMPORTED'}]});await expect(tendersApi.import('/api','t',file,'NEW_REVISION','target')).rejects.toThrow('INVALID_IMPORT_RESULT');const body=post.mock.calls[0][1] as FormData;expect(body.get('files')).toBe(file);expect(body.get('revision_of_document_id')).toBe('target');expect(body.get('conflict_action')).toBe('NEW_REVISION');});
