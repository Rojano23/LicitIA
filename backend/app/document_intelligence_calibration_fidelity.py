"""Calibration only: independent fidelity dimensions, never contractual authority."""
from __future__ import annotations
import json
import re
import unicodedata
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.document_intelligence_calibration import Reference, Observation

MATERIAL_KINDS={'CRITICAL_TOKEN_MISMATCH','NUMERIC_MISMATCH','UNIT_MISMATCH','IDENTIFIER_MISMATCH','MATERIAL_TEXT_OMISSION'}


def whitespace(text: str) -> str:
    return ' '.join(unicodedata.normalize('NFC',text).split())


def comparison(expected: str, observed: str, *, kind: str='MATERIAL_TEXT_OMISSION',conflict=None) -> dict:
    norm=whitespace(observed)
    def contains(value, haystack):
        if kind in {'IDENTIFIER_MISMATCH','CRITICAL_TOKEN_MISMATCH'}:
            return bool(re.search(re.escape(value)+r'(?![A-Za-z0-9_/-])',haystack))
        return value in haystack
    if conflict:
        return {'kind':'REFERENCE_SOURCE_CONFLICT','golden_value':conflict.golden_value,
            'observed_value':observed,'source_reading':conflict.source_reading,'authority':conflict.authority,
            'review_required':True,'scored':False,'material':None}
    if contains(expected,observed):
        return {'kind':'EXACT','scored':True,'material':False}
    if contains(whitespace(expected),norm):
        return {'kind':'EXACT_FORMAT_DIFFERENCE','scored':True,'material':False}
    # Remove only the known standalone OCR separator, never identifier punctuation.
    if contains(whitespace(expected),re.sub(r'(?<=MODELO:)\s*\|\s*',' ',norm)):
        return {'kind':'OCR_NOISE','scored':True,'material':False}
    return {'kind':kind,'scored':True,'material':True}


def compare_fragments(text: str, reference: Reference) -> list[dict]:
    out=[]
    for expected in reference.material_fragments:
        conflict=next((c for c in reference.source_conflicts if c.golden_value in expected),None)
        kind=reference.fragment_dimensions.get(expected,'IDENTIFIER_MISMATCH' if expected.startswith('MODELO:') else 'MATERIAL_TEXT_OMISSION')
        conflict_value=next((r['model'] for r in equipment_rows(text) if r['model'] in {conflict.golden_value,conflict.source_reading}), '') if conflict else text
        found=comparison(expected,conflict_value if conflict else text,kind=kind,conflict=conflict)
        out.append({'expected':expected,**found})
    return out


def equipment_rows(text: str) -> list[dict]:
    """Literal diagnostic rows, not domain extraction or a new OCR adapter."""
    blocks=re.finditer(r'\b(?:MÓDULO|FUENTE|BATERÍAS)\b.*?\((\d+(?:[.,]\d+)?)\s+([^()]+)\)\.?',text,re.S)
    result=[]
    for match in blocks:
        raw=match.group(0)
        model=re.search(r'MODELO:\s*(?:\|\s*)?([^\s(),]+)',raw)
        description=whitespace(raw.split('MARCA:',1)[0]).strip(' ,•')
        result.append({'description':description,'model':model.group(1) if model else None,
            'quantity':match.group(1),'unit':whitespace(match.group(2)),'source_excerpt':raw})
    return result


def compare_equipment(text: str, reference: Reference) -> dict:
    actual=equipment_rows(text);unused=list(range(len(actual)));results=[]
    for expected in reference.equipment_rows:
        description=whitespace(expected.source_excerpt.split('MARCA:',1)[0]).strip(' ,•')
        index=next((i for i in unused if actual[i]['description']==description),None)
        conflict=next((c for c in reference.source_conflicts if c.golden_value==expected.model),None)
        if index is None:
            # A uniquely grounded model can locate a row despite a prose accent error.
            # Alternate source reading locates a disputed row; never adjudicates its model.
            values={expected.model} | ({conflict.source_reading} if conflict else set())
            matching=[i for i in unused if actual[i]['model'] in values]
            if len(matching)==1:
                index=matching[0]
        observed=actual[index] if index is not None else None
        if index is not None:unused.remove(index)
        findings=[]
        if conflict:
            findings.append(comparison(expected.model,observed['model'] or '' if observed else '',conflict=conflict))
        elif not observed or observed['model']!=expected.model:
            findings.append({'kind':'IDENTIFIER_MISMATCH','scored':True,'material':True})
        for field,kind in [('quantity','NUMERIC_MISMATCH'),('unit','UNIT_MISMATCH')]:
            if not observed or observed[field]!=getattr(expected,field):
                findings.append({'kind':kind,'scored':True,'material':True})
        results.append({'identity':expected.identity,'expected':expected.model_dump(mode='json'),'observed':observed,
            'row_present':observed is not None,'findings':findings,
            'binding_status':'MISSING' if not observed else 'REFERENCE_CONFLICT' if conflict else
                'MISMATCH' if findings else 'MATCH'})
    return {'expected_rows':len(results),'preserved_rows':sum(r['row_present'] for r in results),
        'quantity_matches':sum(r['observed'] is not None and r['observed']['quantity']==r['expected']['quantity'] for r in results),
        'unit_matches':sum(r['observed'] is not None and r['observed']['unit']==r['expected']['unit'] for r in results),
        'model_matches':sum(r['observed'] is not None and r['observed']['model']==r['expected']['model'] and
            not any(f['kind']=='REFERENCE_SOURCE_CONFLICT' for f in r['findings']) for r in results),
        'reference_conflicts':sum(r['binding_status']=='REFERENCE_CONFLICT' for r in results),
        'unexpected_rows':[actual[i] for i in unused], 'rows':results}


def diagnostic_raw(raw: str) -> str:
    # Only complete raw_visible_text strings; no repair of JSON or fabricated trailing characters.
    values=re.findall(r'"raw_visible_text"\s*:\s*("(?:\\.|[^"\\])*")',raw)
    return '\n'.join(json.loads(value) for value in values)


def transcription_fidelity(observation: Observation, reference: Reference) -> dict:
    failed=observation.provider=='VISION' and observation.provenance.get('runtime_status') not in {None,'COMPLETED'}
    canonical='' if failed else observation.text
    raw_text=diagnostic_raw(observation.provenance.get('raw_response_text','')) if failed else None
    findings=compare_fragments(canonical,reference) if not failed else []
    rows=compare_equipment(canonical,reference)
    diagnostic_rows=compare_equipment(raw_text,reference) if raw_text is not None else None
    return {'operational_status':'VALIDATION_FAILED' if failed else 'CANONICAL_RESULT_AVAILABLE',
        'canonical_status':'CANONICAL_RESULT_UNAVAILABLE' if failed else 'AVAILABLE',
        'canonical_text':canonical,'findings':findings,'equipment':rows,
        'material_omissions':None if failed else sum(f['kind']=='MATERIAL_TEXT_OMISSION' for f in findings),
        'raw_diagnostic':{'status':'PERCEPTION_PARTIAL','text':raw_text,'equipment':diagnostic_rows,
            'authority':'UNSCORED_DIAGNOSTIC','canonical':False} if failed else None,
        'output_truncated':'OUTPUT_TRUNCATED' in observation.provenance.get('warnings',()),
        'reference_conflicts':[f for r in (diagnostic_rows or rows)['rows'] for f in r['findings'] if f['kind']=='REFERENCE_SOURCE_CONFLICT'],
        'latency_ms':observation.latency_ms,'model_load_overhead':None,'total_process_timing':None,
        'safe_misses':int(failed and bool(reference.equipment_rows)) if failed else int(any(f['kind'] in MATERIAL_KINDS for f in findings)),
        'scoring':'SCORED' if not failed else 'UNSCORED_DIAGNOSTIC'}
