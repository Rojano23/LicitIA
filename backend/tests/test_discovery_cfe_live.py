"""Opt-in CFE public metadata only; no Compras MX/DB/binary retrieval."""
import os,json
from datetime import date
from pathlib import Path
from time import perf_counter
import pytest
from app.discovery_contract import SourceQuery
from app.discovery_cfe import CFEProcurementAdapter

@pytest.mark.live_discovery
@pytest.mark.skipif(os.environ.get('LICITIA_DISCOVERY_CFE_LIVE')!='1',reason='Explicit public CFE opt-in only')
def test_public_cfe_metadata_batches():
    query=SourceQuery(areas=['public'],page_size=10,
        published_from=date.fromisoformat(os.environ.get('LICITIA_CFE_FROM','2026-10-22')),
        published_to=date.fromisoformat(os.environ.get('LICITIA_CFE_TO','2026-10-22')))
    adapter=CFEProcurementAdapter();seen={};cursor=None;visited=set();start=perf_counter()
    report={'source':'CFE','query':query.model_dump(mode='json'),'capabilities':adapter.capabilities(),
        'batches_attempted':0,'batches_completed':0,'rows_retrieved':0,'duplicates':0,'conflicting_duplicates':0,
        'malformed_rows':0,'document_references':0,'parser_issues':[],'terminal':False,'source_total':None,
        'no_database_writes':True,'no_binary_downloads':True,'no_compras_mx_requests':True}
    try:
        for _ in range(2000):
            report['batches_attempted']+=1
            try:batch=adapter.fetch(query,'public',cursor)
            except Exception as exc:
                report['error_type']=type(exc).__name__;report['error_code']=str(exc)[:120];break
            report['batches_completed']+=1;report['rows_retrieved']+=batch.raw_count
            report['parser_issues'].extend(batch.issues)
            report['malformed_rows']+=sum(p['code']=='MALFORMED_ROW' for p in batch.issues)
            for row in batch.rows:
                if row.external_id in seen:
                    report['duplicates']+=1;report['conflicting_duplicates']+=seen[row.external_id]!=row.source_fingerprint
                seen[row.external_id]=row.source_fingerprint;report['document_references']+=len(row.documents)
            if batch.terminal:report['terminal']=True;break
            if not batch.next_cursor or batch.next_cursor in visited:report['error_code']='INVALID_CONTINUATION';break
            visited.add(batch.next_cursor);cursor=batch.next_cursor
    finally:
        report['unique_opportunities']=len(seen);report['acquisition_observation']=adapter.observation.copy()
        report['seconds']=round(perf_counter()-start,3)
        report['status']='SUCCESS' if report['terminal'] and not report['parser_issues'] and not report['conflicting_duplicates'] else 'PARTIAL' if seen else 'FAILED'
        Path('reports/m10_b/cfe_live_final.json').write_text(json.dumps(report,indent=2)+'\n');adapter.close()
    assert report['status']=='SUCCESS',report
    assert report['unique_opportunities']>0,report
