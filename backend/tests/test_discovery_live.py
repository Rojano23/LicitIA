"""Explicit opt-in, public PEMEX metadata only, no persistence into product DB."""
import os,json
from pathlib import Path
from datetime import date
from time import perf_counter
import pytest
from app.discovery_contract import SourceQuery
from app.discovery_pemex import PEMEXConcursosAdapter,AREAS

@pytest.mark.live_discovery
@pytest.mark.skipif(os.environ.get('LICITIA_DISCOVERY_LIVE')!='1',reason='Explicit public-source network opt-in only')
def test_public_pemex_current_multi_area_and_continuation():
    adapter=PEMEXConcursosAdapter();query=SourceQuery(areas=list(AREAS),published_from=date(2026,10,1),page_size=20)
    report={'source':'PEMEX','adapter_version':adapter.version,'acquisition':adapter.capabilities(),
        'query':query.model_dump(mode='json'),'areas':{},'no_database_writes':True,'no_document_downloads':True}
    start=perf_counter();overall={}
    try:
        for area in query.areas:
            seen={};cursors=set();cursor=None
            summary={'pages_attempted':0,'pages_completed':0,'raw_rows':0,'unique':0,'duplicates':0,'document_references':0,
                'malformed_rows':0,'parser_issues':0,'source_total':None,'terminal':False,'status':'FAILED'}
            report['areas'][area]=summary
            for _ in range(200):
                summary['pages_attempted']+=1
                try:batch=adapter.fetch(query,area,cursor)
                except Exception as exc:
                    summary['error_type']=type(exc).__name__;summary['error']=str(exc)[:200];break
                summary['pages_completed']+=1;summary['raw_rows']+=batch.raw_count
                summary['parser_issues']+=len(batch.issues)
                summary['malformed_rows']+=sum(i['code']=='MALFORMED_ROW' for i in batch.issues)
                if batch.source_total is not None:summary['source_total']=batch.source_total
                for row in batch.rows:
                    summary['duplicates']+=row.external_id in seen;seen[row.external_id]=row.source_fingerprint
                    summary['document_references']+=len(row.documents);overall[row.external_id]=row.source_fingerprint
                if batch.terminal:summary['terminal']=True;break
                if not batch.next_cursor or batch.next_cursor in cursors:summary['error']='CONTINUATION_CYCLE_OR_MISSING';break
                cursors.add(batch.next_cursor);cursor=batch.next_cursor
            summary['unique']=len(seen)
            count_ok=summary['source_total'] is None or summary['source_total']==len(seen)
            summary['status']='SUCCESS' if summary['terminal'] and count_ok and not summary['parser_issues'] else 'PARTIAL' if seen else 'FAILED'
    finally:
        adapter.close();report['seconds']=round(perf_counter()-start,3);report['unique_overall']=len(overall)
        report['status']='SUCCESS' if all(a['status']=='SUCCESS' for a in report['areas'].values()) else 'PARTIAL' if overall else 'FAILED'
        Path('reports/m10_a/live.json').write_text(json.dumps(report,indent=2)+'\n')
    assert any(a['pages_completed'] for a in report['areas'].values()),report
    assert all(a['pages_completed']>0 for a in report['areas'].values()),report
    assert any(a['pages_completed']>1 for a in report['areas'].values()),report
    assert report['status']=='SUCCESS',report
