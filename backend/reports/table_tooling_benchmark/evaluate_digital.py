"""Reference-based evaluation only; never changes extraction settings or product."""
import json,re,dataclasses,inspect
from pathlib import Path
from pdfplumber.table import TableSettings
import camelot.parsers as parsers
BASE=Path(__file__).resolve().parent
reference=json.loads((BASE/'reference_proposed.json').read_text())
def iou(a,b):
 inter=max(0,min(a[2],b[2])-max(a[0],b[0]))*max(0,min(a[3],b[3])-max(a[1],b[1]));den=(a[2]-a[0])*(a[3]-a[1])+(b[2]-b[0])*(b[3]-b[1])-inter
 return inter/den if den else 0
def norm(s):return ' '.join((s or '').split())
records=[]
for path in sorted((BASE/'results').glob('*.json')):
 x=json.loads(path.read_text());tables=x['tables'] or [];refs=reference['pages'][x['page']]['tables'];evaluated=[]
 for r in refs:
  candidates=sorted([(iou(t['bbox'],r['bbox']),t) for t in tables],key=lambda p:p[0],reverse=True)
  overlap,t=candidates[0] if candidates else (0,None)
  detected=overlap>.5
  fields=[]
  if 'items' in r:
   for expected in r['items']:
    rows=[row for row in t['matrix'] if len(row)==4 and norm(row[0])==expected['id']] if t and detected else []
    row=rows[0] if len(rows)==1 else None
    fields.append({'item_id':expected['id'],'item_unique_in_correct_four_column_row':bool(row),'quantity_and_unit_in_correct_row':bool(row and norm(row[2])==expected['unit'] and norm(row[3])==expected['quantity']),'brand_literal_in_owned_description':bool(row and expected['brand'] in norm(row[1])),'part_number_literal_in_owned_description':bool(row and expected['model'] in norm(row[1])),'note':'Part number is a literal source field; not automatically canonical model.'})
  evaluated.append({'reference_table':r['name'],'bbox_iou':overlap,'detected':detected,'expected_shape':[r['rows_including_header'],len(r['columns'])],'actual_shape':[t['rows'],t['columns']] if t else None,'logical_rows_correct':bool(detected and t['rows']==r['rows_including_header']),'columns_correct':bool(detected and t['columns']==len(r['columns'])),'item_fields':fields})
 outside=sum(not any(iou(t['bbox'],r['bbox'])>.5 for r in refs) for t in tables)
 records.append({'page':x['page'],'tool':x['tool'],'configuration':x['configuration'],'evaluations':evaluated,'tables_outside_reference_regions':outside,'literal_assessment':'Critical fields compared exactly modulo whitespace only; not a page-wide character-error-rate certification.'})
(BASE/'page_field_evaluation.json').write_text(json.dumps(records,ensure_ascii=False,indent=2))
configs=json.loads((BASE/'digital_configurations.json').read_text())
defaults={'pdfplumber':{name:dataclasses.asdict(TableSettings.resolve(value)) for name,value in configs['pdfplumber'].items()},'camelot_parser_constructor_signatures':{n:str(inspect.signature(getattr(parsers,n))) for n in ['Lattice','Stream','Network','Hybrid']}}
(BASE/'effective_defaults.json').write_text(json.dumps(defaults,indent=2))
print('Evaluated configurations:',len(records))
