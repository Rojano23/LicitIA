from pathlib import Path
import json,hashlib,xml.etree.ElementTree as ET,subprocess
B=Path(__file__).resolve().parent
schema=json.loads((B/'schema_verification.json').read_text());seal=json.loads((B/'pre_acceptance_implementation_seal.json').read_text());accept=json.loads((B/'b1_acceptance.json').read_text());files=json.loads((B/'changed_files.json').read_text())
reg={};counts={}
for label in ['focused','expanded','full']:
 p=B/f'regression_{label}.xml'
 if not p.exists():continue
 root=ET.parse(p).getroot();suites=list(root.iter('testsuite'))
 summary=next((l for l in reversed((B/f'regression_{label}.log').read_text().splitlines()) if 'passed' in l),'PENDING')
 reg[label]={'tests':sum(int(s.get('tests')) for s in suites),'failures':sum(int(s.get('failures'))+int(s.get('errors')) for s in suites),'summary':summary}
 if label=='expanded':
  for case in root.iter('testcase'):
   k=case.attrib['classname'];counts[k]=counts.get(k,0)+1
(B/'regression_results.json').write_text(json.dumps(reg,indent=2)+'\n');(B/'regression_module_counts.json').write_text(json.dumps(counts,indent=2)+'\n')
text=f'''# Camelot → canonical Native → IR — reporte del spike

Estado: **COMPLETE — READY FOR ARCHITECT REVIEW**, sujeto a los resultados finales adjuntos. No stage/commit/push, no Blind Attempt9.
HEAD inicial/actual: `0b04fc7677e670fb487683ac904d3c3a89daa373`.

## Dependency / license

Paquete exacto demostrado en benchmark: **camelot-py==2.0.0** (import camelot). Agregado con pin exacto en requirements.txt y pyproject.toml, según las dos declaraciones existentes del repo. Python backend3.13.15 compatible con Requires-Python>=3.10 de Camelot; pipcheck PASS. No pdfplumber, PaddleOCR o docTR añadidos; sin extras ML/OCR/Ghostscript.

MIT verificado contra repositorio/release: https://github.com/camelot-dev/camelot/blob/v2.0.0/LICENSE. Se reutilizó la evidencia aceptada/hashes de licenses del benchmark antes de instalar. Materiales: playa-pdf MIT, OpenCV-headless Apache2.0, PDFium/pypdfium2 BSD/Apache y notices transitivos, numpy/pandas/openpyxl con licencias permisivas. No se requieren pesos ni licencia de modelo para esta configuración. Versions/licencias resueltas en dependency_assessment.json; record técnico `docs/camelot-table-dependency.md`. No se da garantía legal: distribuir las licencias/notices del bundle real, especialmente PDFium; opcionales/backends no evaluados quedan fuera de la conclusión comercial.

## Camino productivo / autoridad

PDF original local verificado → CamelotTableRelationshipAdapter → propuesta física tipada → coordenadas normalizadas → pertenencia única de palabras Native + acuerdo literal → fragmentos Native independientes → StructuredEvidenceBlock → manifest/grounding → Scope → Quantity/Attribute existentes.

Camelot propone región/topología/celdas; **Native prueba el texto y la fuente**. Raw text Camelot sólo existe dentro de metadata comparativa/debug del proposal; ni FieldBinding ni source_excerpt se crean a partir de ese texto. No hay CamelotScope ni nuevo dominio. Se reutiliza la gramática positiva item/description/quantity/unit existente, sin vocabulario de Tender, tolerancias del B1, partnumber→model ni inferencia de atributos de prosa.

Default para evidencia Native FULL_PAGE digital PDF con generación válida y probe genérico de header shape existente. Nada de routing por Tender/archivo/página/marca. Si falta una precondición, geometría/owner es ambiguo o texto no corresponde, se abstiene/falla cerrado. Fallo de interpretación no crea insuficiencia perceptual ni adquisiciones.

## Coordenadas y ejecución acotada

Origen Camelot bottom-left, y hacia arriba; Native/PyMuPDF top-left, y hacia abajo. Transformación `(x0, H-y1, x1, H-y0)` determinista y reversible. No offsets mágicos. Page dimensions reales; contrato sólo admite rotation0, MediaBox=CropBox y origen(0,0). Páginas rotadas/crop especiales abstienen; CT15/28 lo ejercitan.

Configuración genérica exacta sellada antes de B1:

```json
{json.dumps(seal['configuration'],indent=2)}
```

Config SHA256 `{seal['config_sha256']}`. Parser lattice/combined, PDFium; fallback de backend explícitamenteFalse para no seleccionar Ghostscript si falta PDFium. Es la única diferencia de control de disponibilidad respecto al default con fallback de la biblioteca: no se cambiaron parámetros físicos para el benchmark. No hubo tuning después de ver el resultado.

Worker local aislado: deadline padre35s y CPU30s, original128MiB, proposal2MiB,32tablas/4096celdas y límites IR/text/word existentes. Timeouts/exit no0 son errores explícitos sin fallback. Resource POSIX es requisito del worker; Windows no validado. Memoria está acotada por inputs/output y aislamiento temporal, **sin un hard cap OS de RAM** en este spike; no se afirma garantía contra todo PDF patológico.

LRU de proceso máximo16proposals físicos, clave path/hash original/page/config/dependency identity; revalida bytes Native/original antes de cada lookup. No cache persistente, GC, stream de logs ni nueva retención. Proceso nuevo reejecuta detección. El parser renderiza localmente pero no invoca proveedor OCR/Vision.

## Proof y literalidad

Policy `camelot-native-table-proof-v1`, formato `CAMELOT_NATIVE_TABLE_001`. Proposal conserva detector/version, parser/engine/config hash, source identity hash, página/bbox, índice tabla, filas/columnas/celdas, bordes y raw text; Source del bloque conserva tender/document/page/revision/generation/originalSHA/textSHA. La identidad de Source se liga criptográficamente al proposal; no se usa filename para semántica.

Se requieren topología rectangular completa, bandas de fila/columna consistentes, celdas sin solapamiento y pertenencia única por centro de palabra Native. Se acepta que una caja tipográfica cruce un borde si la relación física propuesta y el texto Native la prueban; no se añade epsilon. Todo valor de celda debe coincidir con Native ordenado modulo whitespace. Ausencia/mismatch no se reemplaza con DataFrame.

Native block/line IDs definen fragmentos literales separados; sus offsets apuntan al texto canónico. La composición de FieldBinding/CONTINUES no es una nueva cita literal. Proof retiene celdas/roles/fragmentrefs y cajas/offsets reales de cada palabra. Proposal y proof tienen SHA256 deterministas, además del hash del manifest.

Validation comprueba Source activo/generación/página/literales, hashes proposal/proof, configuración/dependencies, y replay del bloque completo. Missing manifest/source, tampering, source/hash/page mismatch, config incompatible y ownership ambiguo rechazan/review sin fallback escondido. No se introdujo esquema SQL: artifacts en la provenance existente.

## Coexistencia V6d y seguridad

No se elimina V6d. Su builder positivo se factoriza sin cambiar criterios/semántica. Materialización Native elegible usa sólo Camelot como detector físico; no consenso/doble producción con V6d. Legacy text-only reconstruction sigue existente. NATIVE_RULED_TABLE_001 histórico se reproduce por el detector V6d específico; proofs ausentes se serializan exactamente como antes. CT23 verifica un manifest V6d auténtico desde PDF generado y su replay, y RT sigue sin modificaciones.

V4a: números solos no crean Scope; tabla requiere columnas explícitas, ID entero positivo, cantidad/unidad reconocidas y fuente válida. TOC/cuestionario/numeración/broken/merged abstienen. Todos los outputs quedan review_required=True, confidenceNone; no promoción de estructura contractual a trusted. Quantity/Attribute son provisionales hasta Scope y nunca adquieren autoridad humana automática.

V6c/perception-sufficiency-v2, eligibility OCR/Vision, budgets/modelos/task contracts, Requirements/Evidence no cambiaron. Los archivos protegidos se comparan al HEAD inicial en la verificación final.

## Matriz CT / PDF real

**32CT +22RT =54passed**,6warnings,60.56s, antes del benchmark. CT01–CT28 incluyen parametrizaciones CT07/15. Todo caso positivo comienza en PDF generado, API import/extract-pages/normalize reales; no hay Native/IR inyectado. Negativos de propuesta corrupta usan la propuesta física real alterada sólo para comprobar la frontera de confianza.

CT01–03/08: Scope multirow, quantity/unit y brand/model bajo padre correcto sin intercambio entre vecinos; CT04 continuación multiline sin duplicación; CT05 header repetido; CT06/07 overflow de fuentes9/12/13/15 y offsets genéricos, nunca el valorB1; CT09/10 TOC/cuestionario; CT11/27 broken/merged; CT12 texto detector no Native; CT13 ownership/celdas ambiguas; CT14/25/26 generación/hash/page; CT15 coordenadas; CT16 replay/hash determinista; CT17 tamper; CT18 multispan; CT19 idempotencia; CT20 vocabulario genérico; CT21 missingmanifest; CT22 config hash; CT23 legacyV6d; CT24 whitespace de detector no reemplaza citaNative; CT28 rotatedabstention.

E2E genérico por producción: **2 Scope +2 Quantity +4 Attributes**, brand/model en columnas explícitas, todos con padres correctos y provenance. Las pruebas mockean/deniegan proveedores; Camelot y Native son reales. Esto no certifica recall general ni calidad ML.

## B1 aceptación autorizada, no blind

`pre_acceptance_implementation_seal.json` conserva hashes de código/dependencies/config después de CT/RT. Se importó el **original B1** completo a un root nuevo de aceptación en licitia_test; hash original coincide con benchmark. Nunca se escribió en Attempts/DBvalidation histórica. CT output ya estaba verde; ningún archivo de implementación sellado cambió después de ver B1.

Resultado default: **2 StructuredEvidenceBlocks /2 Scope candidates /2 ScopeDetails /2 Quantities /0 Attributes**, manifests2 validados.

| Item | Quantity/unit | Asociación descripción | Estado |
|---|---|---|---|
| 1 | 1PZA | F60… dentro de descripción Native de fila1 | review_required, confidenceNone |
| 2 | 2PZA | L90… dentro de descripción Native de fila2 | review_required, confidenceNone |

37/37 palabras Native únicas probadas en celdas (cabeceras compartidas contadas una vez), 12fragmentos literales en cada bloque. Las43referencias de palabras acumuladas entre bloques incluyen encabezados repetidos como soporte; no son43palabras únicas ni37fragments IR. No se inventan métricas de ejecución histórica.

Los0Attributes de B1 son una discrepancia/capability boundary explícita: los adapters existentes no soportan automáticamente labels FABRICANTE/MARCA o número de parte embebidos en descripción como columnas brand/model. Se conserva ese texto bajo su Scope; **no se amplía la gramática** para fabricar Attributes o model canónico. D se demuestra con E2E genérico de columnas soportadas; B1 mide IR/Scope/Quantity y asociación de los literales.

Proofs/manifests íntegros, hashes del archivo iguales al locator, Source canónico y generación originales. Normas2columnas de B1 no generaron Scope extra: los únicos dos outputs son los ítems humanos1/2. Evidencia completa en b1_acceptance.json y acceptance_data/provenance.

## Páginas secundarias

B1p2, Basesp41, Cuestionariosp12 y AnexoCp1:4aceptaciones estructurales **0bloques**. Sólo lectura de interpretación sobre canonical Native preparado en datos nuevos; no se materializaron objetos semánticos secundarios. Se preservan hashes de originales y de copias de página usadas. Formularios/normas/weak table no producen falseScope. AnexoC no recibe ninguna verdad B1; Native vacío no dispara OCR/Vision. Abstención no equivale a declarar ausencia de items reales en el escaneo.

## Freeze / DB / regression

Freeze003 permanece `DI_SELECTIVE_FREEZE_003`; implementation_versions agrega proof-policy Camelot, config/hash completo y versiones resueltas (Camelot,playa,PDFium,OpenCV,numpy,pandas,PyMuPDF). No se reescriben freezes históricos ni se crea freeze de Attempt9. Fuente y motor se verifican al replay; cambio de dependency/config implica prueba incompatible, no reutilización silenciosa.

Alembic current/head `{schema['head_revision'][0]}`, drift{schema['difference_count']} (55add/4remove), firma `{schema['signature_sha256']}`. Sin migración, cambios ORM o nuevos blobs.

Resultados finales disponibles:

```json
{json.dumps(reg,indent=2,ensure_ascii=False)}
```

Comandos exactos (intérprete backend absoluto) en regression_commands.json; logs/JUnit/conteos por módulo adjuntos. Focused570 incluye CT/RT,SI/MG,ST/propagación,SC/DC,PS,Scopeadapters/materializadores,humanreview/API,BR/FB/BH,OCR/Vision. Ampliada incluye DI/compatibility/audit/calibración/structure; full excluye sólo local_ollama real. Compileall app/scripts/tests y diffcheck registrados por el mismo driver. Warnings heredados SWIG,python_multipart,Alembic path_separator y Paddle ccache se conservan en logs; ninguna inferencia real certificada por mocks.

## Archivos y cierre

Modificados:

'''+'\n'.join('- `'+p+'`' for p in files['modified'])+'''

Nuevos implementación/tests/docs:

'''+'\n'.join('- `'+p+'`' for p in files['new'])+'''

Reportes, benchmark acceptance script, JUnit, datos derivados y sellos sólo bajo reports/camelot_native_table_spike, untracked. No stage/commit/push. Providers reales ejecutados: **ninguno**; Native/Camelot local físico sí. El test heredado de Tesseract puede consultar versión del binario con reconocimiento simulado; no se ejecutó OCR de estos documentos.

Integridad exacta y conteo de historia en final_integrity.json. No modificación de Attempts1–8 ni del benchmark aceptado, no rerun de8, no Attempt9. Limitaciones: sólo digitalNative/headers conocidos, geometría rectangular no ambigua, sin rotación/crop especial; sin atributos arbitrarios/partnumber inferido; cache16 efímero, resourcePOSIX y sin hardcap de RAM. No blockers de implementación si las suites finales están verdes; aceptación arquitectónica sigue pendiente.

**Attempt9 aún no queda autorizado/ejecutable**: el spike aporta evidencia técnica para solicitar revisión, pero faltan aceptación arquitectónica, commit de producción y HEAD limpio. Las páginas conocidas siguen declaradas expuestas; no representan out-of-sample nuevo.

LICITIA CAMELOT NATIVE TABLE INTEGRATION SPIKE COMPLETE — READY FOR ARCHITECT REVIEW
'''
(B/'integration_report.md').write_text(text)
print('Report',B/'integration_report.md')
