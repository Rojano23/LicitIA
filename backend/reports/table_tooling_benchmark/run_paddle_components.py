"""Local modular PaddleOCR benchmark, not a PP-StructureV3 end-to-end claim."""
import os,json,time,resource,hashlib,socket
from pathlib import Path
BASE=Path(__file__).resolve().parent
os.environ['PADDLE_PDX_CACHE_HOME']=str(BASE/'paddle_cache')
os.environ['PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK']='True'
os.environ['PADDLE_PDX_MODEL_SOURCE']='HuggingFace'
from paddleocr import LayoutDetection,TableStructureRecognition,PaddleOCR
from PIL import Image
models=BASE/'models'
common={'device':'cpu','enable_mkldnn':False,'cpu_threads':4}
start=time.perf_counter()
layout=LayoutDetection(model_name='PP-DocLayout-S',model_dir=str(models/'PP-DocLayout-S'),**common)
structure=TableStructureRecognition(model_name='SLANet_plus',model_dir=str(models/'SLANet_plus'),**common)
ocr=PaddleOCR(text_detection_model_name='PP-OCRv5_mobile_det',text_detection_model_dir=str(models/'PP-OCRv5_mobile_det'),text_recognition_model_name='latin_PP-OCRv5_mobile_rec',text_recognition_model_dir=str(models/'latin_PP-OCRv5_mobile_rec'),use_doc_orientation_classify=False,use_doc_unwarping=False,use_textline_orientation=False,**common)
startup=time.perf_counter()-start
# All inference local; deny network connections after model initialization.
def deny(*args,**kwargs):raise RuntimeError('Network forbidden during local inference')
socket.socket.connect=deny

def convert(x):
 if isinstance(x,dict):return {str(k):convert(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [convert(v) for v in x]
 if hasattr(x,'tolist'):return x.tolist()
 if hasattr(x,'item'):return x.item()
 return x

def result(x):return convert(x.json['res'])
image=BASE/'pages/ANEXOC_P1_2x.png'
output=[]
for repeat in range(2):
 start=time.perf_counter();l=result(layout.predict(str(image),batch_size=1)[0]);tables=[]
 for i,box in enumerate(l['boxes']):
  if box['label']!='table':continue
  bounds=box['coordinate'];crop=Image.open(image).crop(tuple(bounds));crop_path=BASE/'pages'/f'paddle_table_{repeat}_{i}.png';crop.save(crop_path)
  s=result(structure.predict(str(crop_path),batch_size=1)[0]);o=result(ocr.predict(str(crop_path))[0])
  tables.append({'table_box_pixels':box,'crop_path':str(crop_path),'structure':s,'ocr':o,'geometry_transform':'source PDF top-left points = (crop pixel coordinate + table crop origin)/2'})
 output.append({'repeat':repeat,'seconds':time.perf_counter()-start,'layout':l,'tables':tables})
 (BASE/f'paddle_components_repeat{repeat}.json').write_text(json.dumps(output[-1],ensure_ascii=False,indent=2))
 print('repeat',repeat,'tables',len(tables),'seconds',output[-1]['seconds'],flush=True)
summary={'pipeline':'PaddleOCR independent LayoutDetection + TableStructureRecognition + OCR components, not full PP-StructureV3','models':['PP-DocLayout-S','SLANet_plus','PP-OCRv5_mobile_det','latin_PP-OCRv5_mobile_rec'],'parameters':common|{'render_scale':2,'use_doc_orientation_classify':False,'use_doc_unwarping':False,'use_textline_orientation':False},'startup_seconds':startup,'repeat_seconds':[r['seconds'] for r in output],'max_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'network_disabled_during_inference':True,'reference_boxes_used_for_detection':False}
(BASE/'paddle_summary.json').write_text(json.dumps(summary,indent=2))
