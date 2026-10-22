from pathlib import Path
import json,hashlib,subprocess,collections,xml.etree.ElementTree as ET
R=Path('/Users/ceciliavalencia/LiticIA');B=R/'backend';c=json.loads(Path('/private/tmp/licitia_attempt9_context.json').read_text());p=Path(c['directory']);boot=Path(c['bootstrap_directory']);data=Path(c['data_dir'])
def sha(f):return hashlib.sha256(Path(f).read_bytes()).hexdigest()
def read(f):return json.loads(Path(f).read_text())
f=read(p/'first_pass.json')['payload'];sm=read(p/'structural_metrics.json');metrics=f['metrics']['first_pass'];selective=f['selective_metrics'];results={}
for label in ['focused','expanded','full']:
 xml=p/'regression'/('regression_'+label+'.xml');root=ET.parse(xml).getroot();assert not list(root.iter('failure')) and not list(root.iter('error'));results[label]=next(l for l in reversed((p/'regression'/(label+'.log')).read_text().splitlines()) if 'passed' in l)
for label in ['compileall','diff_check']:assert (p/'regression'/(label+'.log')).exists();results[label]='PASS'
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip()==c['head'];assert not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=R,text=True).strip()
subprocess.run(['git','diff','--check'],cwd=R,check=True)
old=read(boot/'historical_integrity_baseline.json');assert all(Path(k).is_file() and sha(k)==v for k,v in old.items())
sealed=read(p/'first_pass_artifact_manifest.json');assert all((data/k).is_file() and sha(data/k)==v for k,v in sealed.items())
providers=[x for x in f['providers'] if x['provider'] in ['TESSERACT','OLLAMA']];vision=[x for x in providers if x['provider']=='OLLAMA'];ocr=[x for x in providers if x['provider']=='TESSERACT'];assert len(vision)==len(ocr)==4;assert not any(x['provider']=='GUARD' for x in f['providers']);assert max(collections.Counter(x['configuration']['plan'] for x in vision).values())<=2
state={'status':'OPERATIONAL_PASS','head':c['head'],'tracked_clean':True,'staging_empty':True,'historical_files_verified':len(old),'frozen_data_artifacts_verified':len(sealed),'provider_calls':dict(ocr=len(ocr),vision=len(vision)),'regression':results,'semantic_adjudication':False}
(p/'closure_verification.json').write_text(json.dumps(state,indent=2)+'\n')
for name,args in [('git_status.txt',['status','--short']),('git_diff_stat.txt',['diff','--stat']),('git_diff_check.txt',['diff','--check'])]:
 r=subprocess.run(['git',*args],cwd=R,capture_output=True,text=True);assert r.returncode==0;(p/name).write_text(r.stdout+r.stderr)
artifact_paths=[boot/'execution_profile.json',p/'pre_execution.json',p/'input_binding.json',p/'EXECUTION_STARTED.json',p/'first_pass.json',p/'FROZEN.json']
rows='\n'.join('| `'+str(x)+'` | `'+sha(x)+'` |' for x in artifact_paths)
comparison=[('IR',0,sm['blocks']),('Scope',0,2),('Attributes',0,0),('Quantities',0,2),('manifests',0,2),('OCR eligible',10,10),('OCR acquisitions',4,4),('Vision eligible',8,8),('Vision calls',4,4),('conflicts',2,2),('review records',292,296),('Requirements',31,31),('Requirement candidates',43,43),('Requested Evidence',8,8)]
text=f'''# Blind Attempt #9 — reporte operacional final

**OPERATIONAL PASS — sin adjudicación semántica.** El pipeline committed produjo al menos un StructuredEvidenceBlock Camelot-proven del corpus real, Scope, Quantity y manifest persistidos. Estos hechos no certifican corrección contractual ni cierran el release gate.

## Identidad, gates y corpus

Run_id `{c['run_id']}`. HEAD inicial/final `{c['head']}`. Root aislado `{data}`. Entorno establecido con establish_environment ANTES de Settings/database/main en cada proceso fresco; sin fallback ni cache clearing. Perfil DI_BLIND_SELECTIVE_001 / SELECTIVE_PERCEPTION / AUTO, blind-task-contracts-v1, perception-sufficiency-v2, DI_SELECTIVE_FREEZE_003.

Ollama GET /api/version y /api/tags:0.23.3, qwen3-vl:4b-instruct, digest ee4b975b58c17ce268cd19d40db35d5edc64603035d2ffc1fee1968eb0947f7b. Sin inferencia durante readiness, sin iniciar/modificar servicio. Tesseract5.5.3 /opt/homebrew/bin/tesseract, /opt/homebrew/share/tessdata/, spa+eng. Camelot-py2.0.0 lattice/combined, camelot-native-table-proof-v1. Identidades/config/dependencies completas en pre-freeze.

Prevención de reposo `caffeinate -ims`, PID52678, activa antes de generar identidad y durante todo el pipeline. sleep_assertions_start.txt y sleep_log_start.txt bajo bootstrap; sleep_log_end.txt y host_awake_verification.json aquí. No eventos Sleep/Wake/DarkWake en TODO el intervalo de ejecución: ninguna llamada estuvo atravesada por suspensión. Logs de assertions con la palabra Sleep no son eventos de suspensión. No se infieren timestamps individuales no registrados; las duraciones wall-clock sí son canónicas.

Reset exclusivo de licitia_validation_06v mediante pg_dump→dropdb→createdb→Alembic; dump previo y SHA preservados bajo bootstrap. Cero tenders/documentos antes del pre-freeze. Alembic current/head20261013_req_perception_prov_072, drift59 (55add/4remove), firma3abb0337a79b5faf56c2ced30e69d4482c47ab17e7e2fc925156ad59f760dde7; verificado antes/después del reset y al cierre. Sin nuevas migraciones ni reparación de esquema.

Importación API productiva de11originales, `.DS_Store` incluido, sin excluir ocultos. Completeness gate ANTES del binding:11/11 filename/hash/size/MIME idénticos al binding histórico Attempt4, cero faltantes/extras, root aislado para todos. Gate PASS; no reparación. Locators canónicos complementan input_binding en original_locators.json; generations vacías al bind según contrato. El gate final revalidó identidad código/root/freeze/binding/runtime/provider y fuentes antes del marcador exclusivo.

| Artefacto | SHA256 archivo completo |
|---|---|
{rows}

Los envelopes pre_execution/input_binding/first_pass tienen además hash de payload; FROZEN es marcador plano. EXECUTION_STARTED presente; FROZEN verificado; BLOCKED ausente. Ningún rerun del intento. First-pass congelado ANTES de métricas/replay/post-run; se sellaron {len(sealed)} archivos derivados/originales del root en first_pass_artifact_manifest.json. No cambios posteriores a esos archivos.

## Import y Native

1Tender,11documentos,10preparados/1unsupported/0fallos de preparación; Native253páginas,251con texto disponible en8documentos. Estados documentales8TEXT_EXTRACTION_COMPLETE/2NO_NATIVE_TEXT/1PENDING. `.DS_Store` siguió comportamiento normal unsupported/PENDING, sin exclusión manual.

## Camelot / Native proof / IR

2StructuredEvidenceBlocks,2table-derived,2positive item identities;1tabla aceptada representada en proofs con12celdas;2proofs CAMELOT_NATIVE_TABLE_001,2manifests verificados,0missing/0hash failures/0proof replay failures.37palabras Native únicas probadas;24fragmentos literales entre ambos bloques, incluyendo encabezados compartidos. No confundir palabras con fragments IR.

2bloques multiline; relaciones:16HEADER_OF,8DESCRIBES_ITEM,2UNIT_FOR,2VALUE_FOR,6CONTINUES. Ownership estructural registrado en proofs; su corrección contractual permanece sin adjudicar. Los dos bloques conservan revisión requerida y no adquieren trust automático.

Eligible PDF pages, Camelot pages evaluated, tables proposed/rejected/ambiguous, total cells proposed, ambiguous fragment ownership/rejected relationships y bloques descartados: **NOT_DIRECTLY_MEASURABLE**. Sólo se preservan propuestas aceptadas en manifests; no hay trazas completas de todas las evaluaciones y no se reejecuta el detector sobre el corpus para inventar totales.1tabla/12celdas son el subconjunto aceptado, no el total propuesto.

## Scope / Quantities / Attributes

ScopeDetails persistidos2, review-required2; Quantities persistidas2, review-required2; Attributes0. Scope/Quantity conservan padres/Native provenance y revisión, no conclusión humana. Conteos intermedios de candidates creados, grounding aceptado/rechazado, reconciliación, provisional/parent-resolved/rechazado/ambiguo: **NOT_DIRECTLY_MEASURABLE**, no se sustituyen por conteos persistidos. No se agregaron métricas/código. Attributes0 no es fallo operacional por sí solo; la limitación conocida de semántica embebida continúa sin tuning.

## Percepción y proveedores

OCR:1257planes;996Native suficiente,10insuficiente,251UNKNOWN sin contrato textual.1000UNRESOLVED/257NOT_ATTEMPTED;996Native suficiente + interpretación no resuelta sin adquisición. OCR needed/eligible10/10;4adquisiciones/4páginas;10resultados completados incluyendo6reuse;0failed/0retryexhausted/0budgetexhausted;1247SKIPPED,996evitados por suficienciaNative y251por contrato ausente. Son tareas, no996páginas. No inferir que1000interpretaciones pendientes son déficit perceptual.

Vision:8needed/8eligible/VISUAL_REQUIRED;4calls en2páginas y3fingerprints de tarea;2completed/2failed;1retry adicional,1retryexhausted,5budgetexhausted;0reuse/0avoided canónico. Diez resultados del executor no significan diez llamadas. Avoided0 sólo cubre planes construidos, no todos los contratos espaciales potenciales.

Wall durations Vision (receipts por guard id):

'''+ '\n'.join('- '+x['id']+': '+str(x['latency_ms'])+'ms, '+x['status'] for x in sorted(vision,key=lambda x:int(x['id'].split('-')[-1])))+'''

Dos fallos de DETAIL_TRANSCRIPTION conservados como fallos bounded. No se reclasifican como éxito ni se ajustan timeouts: uno registra60018ms, ligera sobrecarga wall del límite60s, sin suspensión. Flags timeout/truncated del guard permanecen tal como fueron registrados; no se inventan causas que el artifact no distingue.

OCR wall durations:

'''+ '\n'.join('- '+x['id']+': '+str(x['latency_ms'])+'ms, '+x['status'] for x in sorted(ocr,key=lambda x:int(x['id'].split('-')[-1])))+f'''

Budgets intactos:OCR8acquisitions/8pages,1attempt/fingerprint,30s ceiling60s,2x,8Mpx/8MiB,spa+eng; Vision4calls/4tasks/4pages/2attempts,60s,600/1000tokens,JSONretry0, mismo modelo/digest. Guard sin violaciones. Las adquisiciones están ligadas a déficits textuales/espaciales explícitos; interpretación no resuelta sola no elevó percepción.

## Salidas / provenance

Requirements31, candidates43, rejected requirement candidates0, RequestedEvidence8. Structure0trusted/253review/0unavailable. Review296 (253structure+31requirements+8evidence+2scope+2quantity); conflicts2; stale carry0. No juicio semántico.

Native/OCR/Vision por capacidad y estados están en first_pass.json, metrics.first_pass.perception_availability y selective_metrics.provenance_capabilities; estos últimos son slots por capacidad, no adquisiciones. Native251available/2unavailable por capacidad; OCR4available/249unavailable; VisionSTRUCTURE2available/251unavailable y TRANSCRIPTION0available/253unavailable. Scope2Native/Quantity2Native; STRUCTURE253NATIVE_PDF. Multi-capability/multispan no tiene contador global canónico: los2manifests verificados son multispan; no se inventa un agregado de todas las combinaciones de provenance. Datos completos de provenance conservados en snapshot y root sellado.

## Comparación operacional con #7

| Métrica | #7 | #9 |
|---|---:|---:|
'''+ '\n'.join(f'| {k} | {a} | {b} |' for k,a,b in comparison)+f'''

#8 permanece histórico operacionalmente inválido por suspensión; no baseline temporal. Ningún aumento es calificado como correcto o mejora semántica.

## Seguridad y regresión

Código sin cambios, mismoHEAD committed limpio, staging vacío; perfiles/providers/budgets sin modificaciones. Sin configuración Tender/filename/página específica, sin texto Camelot promovido como cita, Native proof obligatorio, ownership ambiguo no admitido por contrato, V4a/V6c intactos. Hash/replay de cada manifest pasó; guard sin adquisiciones fuera de plan/budget. Sin cambios de schema.

Post-run (sólo licitia_test; NO rerun del Tender):

'''+ '\n'.join('- '+k+': '+v for k,v in results.items())+f'''

Focused incluye CT/RT,SI/MG,ST,SC/DC,PS,Scope adapters/materializers,HumanReview/API,BR/FB/BH,OCR/Vision. CT32+RT22 incluidos; opt-in local_ollama excluido. Logs/JUnit/commands efectivos bajo regression/. Warnings heredados conservados, sin nuevos errores. Estas pruebas de contratos no adjudican calidad semántica real.

Históricos:4560archivos verificados intactos, Attempts1–8 y benchmark sin cambios. No source/stage/commit/push. Reportes nuevos untracked. Estado Git completo en git_status.txt. No nuevo slice ni rerun autorizado. Scripts operacionales de orquestación/reporte conservados por separado; no instrumentación de producción. El verificador auxiliar inicialmente intentó leer FROZEN como envelope, se corrigió a marcador plano antes de completar verificación; no cambió ningún artifact ni se repitió pipeline.

Bloqueadores operacionales:ninguno. Limitaciones: métricas internas no registradas se declaran NOT_DIRECTLY_MEASURABLE;2fallos Vision bounded; Attributes0; pendiente adjudicación semántica final. No se revisaron descripciones ni valores del corpus para decidir corrección.

LICITIA BLIND ATTEMPT #9 OPERATIONAL PASS — READY FOR FINAL MVP RELEASE-GATE ADJUDICATION
'''
(p/'operational_report.md').write_text(text)
manifest={str(x.relative_to(p)):sha(x) for x in p.rglob('*') if x.is_file() and x.name!='operational_artifact_manifest.json'}
(p/'operational_artifact_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps(state));print('REPORT',p/'operational_report.md')
