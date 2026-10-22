"""Isolated benchmark only. Full pages; generic fixed configs; two runs each."""
import json,time,hashlib,resource,warnings,sys,importlib.metadata as meta
from pathlib import Path
import pdfplumber,camelot
BASE=Path(__file__).resolve().parent
P_CONFIGS={
 'lines':{},
 'lines_strict':{'vertical_strategy':'lines_strict','horizontal_strategy':'lines_strict'},
 'text':{'vertical_strategy':'text','horizontal_strategy':'text'},
 'text_tolerance5':{'vertical_strategy':'text','horizontal_strategy':'text','snap_tolerance':5,'join_tolerance':5,'intersection_tolerance':5},
 'lines_text':{'vertical_strategy':'lines','horizontal_strategy':'text'},
 'text_lines':{'vertical_strategy':'text','horizontal_strategy':'lines'},
}
C_CONFIGS={
 'lattice_combined':{'flavor':'lattice','engine':'combined'},
 'lattice_vector':{'flavor':'lattice','engine':'vector'},
 'lattice_raster':{'flavor':'lattice','engine':'raster'},
 'stream':{'flavor':'stream'},
 'stream_split':{'flavor':'stream','split_text':True},
 'network':{'flavor':'network'},
 'hybrid':{'flavor':'hybrid'},
 'auto':{'flavor':'auto'},
}
def canon(x):return json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':'))
def extract_plumber(path,config):
 with pdfplumber.open(path) as pdf:
  page=pdf.pages[0];result=[]
  for table in page.find_tables(config):
   result.append({'bbox':table.bbox,'rows':len(table.rows),'columns':len(table.columns),'matrix':table.extract(),
    'cells':[{'bbox':cell,'characters':[{'text':ch['text'],'bbox':[ch['x0'],ch['top'],ch['x1'],ch['bottom']]} for ch in page.chars if cell[0]<=((ch['x0']+ch['x1'])/2)<=cell[2] and cell[1]<=((ch['top']+ch['bottom'])/2)<=cell[3]]} for cell in table.cells]})
  return result
def extract_camelot(path,config,height):
 ts=camelot.read_pdf(str(path),pages='1',suppress_stdout=True,parallel=False,**config)
 return [{'bbox_bottom_origin':list(t._bbox),'bbox':[t._bbox[0],height-t._bbox[3],t._bbox[2],height-t._bbox[1]],'rows':t.shape[0],'columns':t.shape[1],'matrix':t.df.values.tolist(),'parser_report':t.parsing_report,
  'cells':[{'row':i,'column':j,'text':c.text,'bbox':[c.x1,height-c.y2,c.x2,height-c.y1],'bbox_bottom_origin':[c.x1,c.y1,c.x2,c.y2],'borders':{'left':c.left,'right':c.right,'top':c.top,'bottom':c.bottom}} for i,row in enumerate(t.cells) for j,c in enumerate(row)]} for t in ts]
configs={'pdfplumber':P_CONFIGS,'camelot':C_CONFIGS}
(BASE/'digital_configurations.json').write_text(json.dumps(configs,indent=2))
(BASE/'results').mkdir(exist_ok=True)
summary=[]
for page in json.loads((BASE/'page_manifest.json').read_text()):
 for tool,choices in configs.items():
  for label,config in choices.items():
   runs=[];durations=[];messages=[];errors=[]
   for repeat in range(2):
    start=time.perf_counter()
    try:
     with warnings.catch_warnings(record=True) as caught:
      warnings.simplefilter('always')
      value=extract_plumber(BASE/'pages'/f"{page['key']}.pdf",config) if tool=='pdfplumber' else extract_camelot(BASE/'pages'/f"{page['key']}.pdf",config,page['height'])
      messages.extend(str(w.message) for w in caught)
     runs.append(value)
    except Exception as exc:errors.append({'repeat':repeat,'type':type(exc).__name__,'message':str(exc)});runs.append(None)
    durations.append(time.perf_counter()-start)
   # Camelot reports incidental table order/page numbers only, stable for repeated same page.
   digest=lambda x:hashlib.sha256(canon(x).encode()).hexdigest()
   record={'page':page['key'],'tool':tool,'configuration':label,'parameters':config,'repeat_seconds':durations,'deterministic':digest(runs[0])==digest(runs[1]),'max_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'warnings':sorted(set(messages)),'errors':errors,'tables':runs[0],'repeat_structure_sha256':[digest(x) for x in runs]}
   (BASE/'results'/f"{page['key']}__{tool}__{label}.json").write_text(json.dumps(record,ensure_ascii=False,indent=2))
   summary.append({k:v for k,v in record.items() if k!='tables'}|{'table_shapes':[[t['rows'],t['columns']] for t in runs[0]] if runs[0] else []})
   print(page['key'],tool,label,summary[-1]['table_shapes'],'errors',len(errors),flush=True)
(BASE/'digital_summary.json').write_text(json.dumps(summary,indent=2))
(BASE/'versions.json').write_text(json.dumps({name:meta.version(name) for name in ['pdfplumber','camelot-py','pdfminer.six','playa-pdf','pypdfium2','opencv-python-headless','pandas','numpy']},indent=2))
