"""M10-D opt-in: bounded current public metadata, no DB writes/binary/Compras requests."""
from datetime import date
from pathlib import Path
from time import perf_counter
import json,os
import pytest
from app.discovery_contract import SourceQuery
from app.discovery_pemex import PEMEXConcursosAdapter,AREAS
from app.discovery_cfe import CFEProcurementAdapter

@pytest.mark.live_discovery
@pytest.mark.skipif(os.environ.get('LICITIA_M10D_LIVE')!='1',reason='Explicit M10-D public metadata opt-in')
@pytest.mark.parametrize('source',['PEMEX','CFE'])
def test_closure_public_metadata(source):
    cls=PEMEXConcursosAdapter if source=='PEMEX' else CFEProcurementAdapter
    areas=list(AREAS) if source=='PEMEX' else ['public'];adapter=cls();report={'source':source,'areas':{},'no_binary_downloads':True,'no_database_writes':True,'no_compras_mx_requests':True}
    query=SourceQuery(areas=areas,page_size=20,published_from=date(2026,10,22),published_to=date(2026,10,23));report['query']=query.model_dump(mode='json');started=perf_counter();overall={}
    try:
        for area in areas:
            seen={};visited=set();cursor=None;v={'batches':0,'rows':0,'documents':0,'duplicates':0,'conflicts':0,'issues':0,'source_total':None,'terminal':False};report['areas'][area]=v
            for _ in range(12):
                try:batch=adapter.fetch(query,area,cursor)
                except Exception as exc:
                    v['error_type']=type(exc).__name__;v['error_code']=str(exc) if str(exc).isupper() and len(str(exc))<120 else 'SOURCE_UNAVAILABLE_OR_CONTRACT_ERROR';break
                v['batches']+=1;v['rows']+=batch.raw_count;v['issues']+=len(batch.issues);v['source_total']=batch.source_total
                for row in batch.rows:
                    v['duplicates']+=row.external_id in seen;v['conflicts']+=row.external_id in seen and seen[row.external_id]!=row.source_fingerprint
                    seen[row.external_id]=row.source_fingerprint;overall[row.external_id]=row.source_fingerprint;v['documents']+=len(row.documents)
                if batch.terminal:v['terminal']=True;break
                if not batch.next_cursor or batch.next_cursor in visited:v['error_code']='INVALID_CONTINUATION';break
                visited.add(batch.next_cursor);cursor=batch.next_cursor
            v['unique']=len(seen)
            v['status']='SUCCESS' if v['terminal'] and not v['issues'] and not v['conflicts'] and v['source_total'] in {None,len(seen)} else 'PARTIAL' if seen else 'FAILED'
        report['status']='SUCCESS' if all(v['status']=='SUCCESS' for v in report['areas'].values()) else 'PARTIAL' if overall else 'FAILED'
    finally:
        report['unique_overall']=len(overall);report['seconds']=round(perf_counter()-started,3)
        if hasattr(adapter,'observation'):report['acquisition_observation']=adapter.observation
        adapter.close();directory=Path(os.environ.get('LICITIA_DISCOVERY_REPORT_ROOT','reports/m10_d'));directory.mkdir(parents=True,exist_ok=True)
        (directory/('live_'+source.lower()+'.json')).write_text(json.dumps(report,indent=2)+'\n')
    assert report['status']=='SUCCESS',report
