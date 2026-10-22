# MVP-06.V — Adjudicación semántica inicial de Blind Attempt #2

**Autoridad:** propuesta de revisión de fuentes realizada por Codex; `approved_by_human=false`. Requiere aprobación humana independiente. No se instanció `HumanTruth`, no se llamó `freeze_analysis` ni se alteró la adjudicación null del primer pase.

Run: `06v_43dee0eb834f48f6a7c77a6e94c37a5a`; HEAD `c1c6ff4870dc94009b10d62f47020ef6cdf9d580`.
Freeze: `ac217404caf1b316416ee03f111383cead3b6e87af59e5470b6367da8aad7412`.
First pass: `21f0d1e2e39e39f99ac5f1ad2fc0db51cebd9b774bff43f6b0c2b826b35979a0`.
Input set: `e95327800c5b0792f1a7dda99874d0440180305de1b6dc462ec78c6516c87e8d`.
JSON de esta revisión: SHA-256 `807b85cc6ce4d043fc5e5a4e32a3dffd73c46ab37dab8df112569599b8e27295`.

## Alcance y decisiones

**Integridad operacional: PASS. Calidad semántica: recomendación FAIL; aceptación formal pendiente de arquitecto.** El protocolo no fija umbrales semánticos suficientes; no se inventó uno. La recomendación deriva de omisiones materiales y dos estructuras confiadas incorrectas.

Se revisaron los31 Requirements,43 candidatos y8 Requested Evidence, todas las2 estructurasTRUSTED y casos dirigidos de fuentes/colas. No es lectura exhaustiva ni verdad humana aprobada de cada una de las253 páginas. Los249review conservan estados y razones, sin declararlos automáticamente innecesarios. Recall/accuracy globales no calculables. Los misses listados son un límite inferior por dominio; no sumar dominios como si fueran obligaciones independientes.

## Documentos originales

| Etiqueta | Documento | Páginas | SHA-256 |
|---|---|---:|---|
| D01 | 02. Bases Internacionales  ID-107478.pdf | 119 | `7ffad7029cf8660bdf124c6797846186bf1b1aa80b064ea24d5fd4a9d6ca12a8` |
| D02 | 2. Anexo_C.pdf | 1 | `996323b5fd6afac365fd811713da63c9964f4a4925df339b5fc8e1a885b579d2` |
| D03 | 1. Cuestionarios DD ANEXO.pdf | 20 | `7e4b94ae3130c1e1e46e1bc4ad89040a3d68351ab25b88c633a7c62bcd138670` |
| D04 | 4. Anexo PACMA.pdf | 26 | `0d6d8dbdc296109add69965efda636f97a1e759efbbaa1f188162350de2d8327` |
| D05 | 5. MODELO DE CONTRATO PARA BIENES.pdf | 55 | `ee9dabcabf257972489d4da5818334a2af0f3a0e4a22dd12b2e90c400c8391a5` |
| D06 | 01. Convocatoria  ID-107478.pdf | 3 | `c5b8e39e09d66d288b097faad99cfab22c5a9c5573e8187c1d428d8ee5de075f` |
| D07 | 2. Mecanismo GNR.pdf | 12 | `d0517f47b23c88593765876b11ea85a8fbc4ba7f1bc2fb9568c20bcaff00043f` |
| D08 | .DS_Store | N/A | `0c3c4c0b58647e4ca761e9fe61421b68208c9bc656714cd49c89031e85f20616` |
| D09 | 1. Anexo_B1_Relevadores GE V2.pdf | 5 | `4c5c09719046f8e8a84b929cfc8a930eb9d700938a5e6c88d0f21ae457d00208` |
| D10 | 3. Anexo CN Tipo 2.pdf | 11 | `e0958d05fbe305f768b3b156a0c26517de1400e61a314ebcfda346ab93e7836e` |
| D11 | 3. Anexo SSPA (Formato 4).pdf | 1 | `f94397fcdf557d9234b5b49327854ba93da35c36b38327f84b03113a781d5074` |

## Resultados medidos de revisión

- Requirements:15 con significado/categoría suficientes para la regla expresada;8 sustentados con incompletitud/clasificación defectuosa;8 contextuales/no obligación autónoma de licitante. Soporte semántico23/31=74.19%; completos15/31=48.39%. Son proporciones de esta propuesta, no precisión humana certificada.
- Evidence:1 documento identificado adecuadamente,5 referencias reales pero incompletas/mal tipadas,2 contextuales/no documento autónomo. Existencia semántica6/8=75%; identidad completa1/8=12.5%.
- Candidatos:37/43 coinciden tras normalizar whitespace;6 editados/segmentados requieren contexto. Cinco repeticiones del encabezadoCN y una repetición de la excepciónDA5 no son seis obligaciones nuevas. No confundir43 candidatos con31 obligaciones aprobadas.
- Dos estructurasTRUSTED revisadas:2 incorrectas /2. No hay Requirements/EvidenceTRUSTED; los registros de documentos/versiones representan metadata, no cumplimiento.
- Un conflicto surfaced es la continuación del índice de reglas de p13 a p14; no una contradicción contractual demostrada. Conflictos materiales suprimidos y revisiones innecesarias globales quedan sin adjudicar.

## Requirements — cada registro emitido

| Registro / ID | Fuente | Clase | Juicio |
|---|---|---|---|
| R01 / `06e579c9-1243-4499-9e3e-36038789b05f` | D10 p1 | SUPPORTED_WITH_DEFECT | La obligación de declarar CN sí existe, sin porcentaje mínimo. El encabezado no conserva Formato 3, plazo ni acuses (§5.1); no equivale al manifiesto de origen de bienes. |
| R02 / `0e62445c-0f2b-496b-afeb-cef2c7fc115c` | D01 p78 | SUPPORTED_REQUIREMENT | Condicional a consorcio: cada integrante entrega Anexo 3/DD-8. No convertirlo en requisito de toda participación individual. |
| R03 / `15cff57b-f1ef-4f5d-b60b-3367c2b24215` | D05 p15 | CONTEXT_NOT_STANDALONE_BIDDER_REQUIREMENT | D05 es modelo sin completar: instrucción al redactor y Anexo en blanco; no acredita una obligación adoptada ni su aplicabilidad. |
| R04 / `27c544fb-0864-4cd4-a4db-7b19fae25822` | D01 p41 | CONTEXT_NOT_STANDALONE_BIDDER_REQUIREMENT | Excepción válida de no desechamiento del DA-5; NO es obligación positiva de presentar un documento. Conservar como criterio/exención, no como obligación autónoma. |
| R05 / `333fd8a5-fd98-411c-9b1f-731f7dbfe8f3` | D01 p50 | SUPPORTED_WITH_DEFECT | Obligación real pero “presente documento” queda sin identidad autónoma: DA-13, aceptación de e.firma. Falta el objeto documental en canonical_text. |
| R06 / `391e4c93-7ba6-4800-ac66-a7ea7fff9f49` | D01 p18 | SUPPORTED_REQUIREMENT | Considerar bases finales/modificaciones aplicables es regla real; no demuestra que existan modificaciones ni un Source Effect específico. |
| R07 / `3ca82ed7-36f1-4e8d-b11f-0715a4376886` | D01 p9 | SUPPORTED_REQUIREMENT | Alta inicial SISCEP tras comunicación: condición y cuenta/contraseña conservadas. |
| R08 / `49684e07-e5b0-4911-a635-87a45ab69df7` | D01 p97 | CONTEXT_NOT_STANDALONE_BIDDER_REQUIREMENT | Regla de la CONVOCANTE sobre PMR, no obligación autónoma del licitante. Además corta “Negociación de la” y pierde continuación p98. |
| R09 / `49c60937-8d1f-419a-8b15-bac938f5863e` | D01 p72 | SUPPORTED_WITH_DEFECT | Condicional real, pero “presente documento” en p72 es continuación de DD-2 (p71). No unificarla semánticamente con el manifiesto de origen p53–54 sólo por texto igual. |
| R10 / `5b8da589-a34f-4b2c-a740-94f6dd025ecd` | D01 p9 | SUPPORTED_REQUIREMENT | Aceptación del Acuerdo de Participante en SISCEP es real, aunque el inicio del fragmento arrastra una referencia de sección. |
| R11 / `5d7faff7-8c45-42e2-805d-df2c594e3866` | D01 p18 | CONTEXT_NOT_STANDALONE_BIDDER_REQUIREMENT | Instrucción de soporte condicionada a dudas; no acredita documentación de elegibilidad ni obligación técnica/comercial autónoma. |
| R12 / `612bd92d-561e-45d6-aad5-995f081dabd4` | D01 p19 | SUPPORTED_REQUIREMENT | Firma de última hoja por facultado, donde se solicite; no significa que cualquier persona o firma por ausencia sea válida. |
| R13 / `616d57e6-c3ee-4d6f-9fa1-a921a2c7b876` | D01 p19 | SUPPORTED_REQUIREMENT | Sobre1 comercial PDF/ZIP hasta100MB y documentos D-1: regla de presentación real; no lista todas sus evidencias. |
| R14 / `62e3ad43-9a1d-4778-bde2-84e768899c31` | D01 p19 | SUPPORTED_REQUIREMENT | Sobre1 técnico PDF/ZIP hasta100MB y D-3: regla real; no sustituye catálogo de obligaciones de B-1. |
| R15 / `821f3ddc-24ca-4806-91e8-3eb374281def` | D01 p87 | SUPPORTED_REQUIREMENT | DA-3 membretado y firmado real. Su mera mención no extrae por separado identificación, actas y poderes exigidos en la tabla. |
| R16 / `84d8fbdd-88b4-4a84-858b-aa3424624a3c` | D05 p54 | CONTEXT_NOT_STANDALONE_BIDDER_REQUIREMENT | Nota de modelo para cláusula de financiamiento >500 millones; D01 p14 dice Fuentes de Financiamiento No Aplica. Texto localizado real, aplicabilidad como obligación del Tender no sustentada. |
| R17 / `89c98a21-f2fb-4cac-8255-98d7a0e50d21` | D01 p19 | SUPPORTED_WITH_DEFECT | Presentación electrónica real, pero corta antes de enumerar los sobres y elimina 9. del ordinal 9.2; no es evidencia documental específica. |
| R18 / `968f5ed1-e00a-4ec8-b0ee-8e4c64edd40a` | D09 p2 | CONTEXT_NOT_STANDALONE_BIDDER_REQUIREMENT | Encabezado “Otros requisitos...” sin los numerales 2.1–2.8. No expresa una obligación verificable por sí solo. |
| R19 / `98e66b74-822c-4b2e-b276-de6d7c9accc6` | D01 p9 | SUPPORTED_REQUIREMENT | Corregir/re-enviar DA-1 si discrepa del SISCEP: requisito condicional real; el resto del párrafo fija consecuencia/plazo no conservados aquí. |
| R20 / `9bee03a8-65b8-4488-9b6c-8b6ac6ce9b9f` | D05 p15 | CONTEXT_NOT_STANDALONE_BIDDER_REQUIREMENT | Instrucción para redactar acuerdos referenciales/preparatorios, no el contrato puntual de D01 p15. Categoría EXPERIENCE tampoco está sustentada. |
| R21 / `aa1f93bf-31eb-40fc-b92e-3dcc61d00179` | D01 p21 | CONTEXT_NOT_STANDALONE_BIDDER_REQUIREMENT | Obligación del servidor público de levantar acta. Actor no es el participante; corte inicial “1,2 y3” pierde el contexto de sobres. |
| R22 / `b36d4067-3826-450b-bcdf-a9e444d3662e` | D01 p20 | SUPPORTED_REQUIREMENT | Sobre3 DD PDF/ZIP hasta100MB y anexo DD: obligación real; no implica extracción de sus documentos individuales. |
| R23 / `b441a0be-1a40-4ca5-a43e-ee2109bda71f` | D01 p100 | SUPPORTED_WITH_DEFECT | Regla real de desempate; omite del texto autónomo el supuesto de empate previo. No aplicar siempre a todos los participantes. |
| R24 / `b93900d2-75ca-46cf-957e-f9d16a169d39` | D01 p93 | SUPPORTED_REQUIREMENT | Firma autógrafa por facultado DA-3 en propuesta técnica, al menos última hoja. Solapa parcialmente R12, con alcance técnico más específico. |
| R25 / `c070594b-506e-442a-9f51-65bd4ee81482` | D01 p82 | SUPPORTED_REQUIREMENT | Fotografías actualizadas DD-12 realmente solicitadas. No aparecen como Requested Evidence individual en los ocho emitidos. |
| R26 / `c37f3047-96e3-4487-8a39-931c7f3ffaf1` | D01 p96 | SUPPORTED_REQUIREMENT | Aritmética correcta y corrección sin cambiar unitarios: criterio económico real, no permiso para fijar precio automáticamente. |
| R27 / `cc93193e-2bae-476f-8e24-2c38fc9e4949` | D01 p9 | SUPPORTED_REQUIREMENT | Reutilizar cuenta existente en los supuestos de RI/RC: condición alternativa a R07, no duplicado exacto. |
| R28 / `ceca7886-7d7c-4ac1-a2fc-e6ed98ba74d5` | D09 p3 | SUPPORTED_WITH_DEFECT | Corta en “estén en otro”, omite la traducción simple y la conformidad completa; categoría PERSONNEL no corresponde a documentación técnica/idioma. |
| R29 / `dbcfa05e-7635-4acf-b66f-25231371dca5` | D01 p94 | SUPPORTED_WITH_DEFECT | Congruencia de propuesta y soportes real; PERSONNEL es clasificación incorrecta. El defecto es categorización, no falta de respaldo textual. |
| R30 / `e167fdb1-8840-4e5e-8f34-ef01ca4ad221` | D01 p50 | SUPPORTED_WITH_DEFECT | Certificado e.firma/SAT por integrante de consorcio; corte A.C. pierde la identificación completa del emisor y la relación e.firma. |
| R31 / `ed560568-e01c-43c2-803e-956174e6305f` | D01 p19 | SUPPORTED_REQUIREMENT | Sobre2 económico PDF/ZIP hasta100MB y D-4: regla real; D-4 es criterio de evaluación, no el nombre de un único formato a entregar. |

## Candidatos —43 ocurrencias

| Candidato / ID | Fuente | Clase / Requirement primario | Juicio |
|---|---|---|---|
| C01 / `072d8626-a201-4e41-a93d-318d297ecd77` | D01 p19 | SUPPORTED_REQUIREMENT / R31 | Sobre2 económico PDF/ZIP hasta100MB y D-4: regla real; D-4 es criterio de evaluación, no el nombre de un único formato a entregar. |
| C02 / `08db8df5-4462-4199-8d21-8077dfc8ad77` | D01 p9 | SUPPORTED_REQUIREMENT / R19 | Corregir/re-enviar DA-1 si discrepa del SISCEP: requisito condicional real; el resto del párrafo fija consecuencia/plazo no conservados aquí. |
| C03 / `0c0c7c02-9dcd-4f12-b400-8a97a1a0a681` | D01 p82 | SUPPORTED_REQUIREMENT / R25 | Fotografías actualizadas DD-12 realmente solicitadas. No aparecen como Requested Evidence individual en los ocho emitidos. |
| C04 / `0c83ddb2-ac97-4061-b4aa-36cdb5abfb88` | D05 p15 | CONTEXT_NOT_STANDALONE_BIDDER_REQUIREMENT / R20 | Instrucción para redactar acuerdos referenciales/preparatorios, no el contrato puntual de D01 p15. Categoría EXPERIENCE tampoco está sustentada. |
| C05 / `0deab145-9e17-41e3-a163-9c0b553c75d1` | D10 p10 | REPEATED_HEADER_OCCURRENCE / No se afirma vínculo secundario | Misma obligación general CN que C34; ocurrencia p10, no una obligación contractual nueva. |
| C06 / `1223eb17-289f-4d26-bdb6-3ce4dc18720b` | D05 p54 | CONTEXT_NOT_STANDALONE_BIDDER_REQUIREMENT / R16 | Nota de modelo para cláusula de financiamiento >500 millones; D01 p14 dice Fuentes de Financiamiento No Aplica. Texto localizado real, aplicabilidad como obligación del Tender no sustentada. |
| C07 / `123c4283-ee8d-4cfb-b73e-3d0c7485817a` | D01 p19 | SUPPORTED_WITH_DEFECT / R17 | Presentación electrónica real, pero corta antes de enumerar los sobres y elimina 9. del ordinal 9.2; no es evidencia documental específica. |
| C08 / `1a1deaca-c0b4-4eaa-86de-c4123781fde1` | D01 p72 | SUPPORTED_WITH_DEFECT / R09 | Condicional real, pero “presente documento” en p72 es continuación de DD-2 (p71). No unificarla semánticamente con el manifiesto de origen p53–54 sólo por texto igual. |
| C09 / `1e796e01-4154-4546-a88d-7c421aba4fb2` | D01 p9 | SUPPORTED_REQUIREMENT / R07 | Alta inicial SISCEP tras comunicación: condición y cuenta/contraseña conservadas. |
| C10 / `218b77ec-5301-4193-93a6-87bd0e2e83b2` | D01 p19 | SUPPORTED_REQUIREMENT / R14 | Sobre1 técnico PDF/ZIP hasta100MB y D-3: regla real; no sustituye catálogo de obligaciones de B-1. |
| C11 / `23db4bc3-148b-4deb-beb9-8f12627546cb` | D09 p2 | CONTEXT_NOT_STANDALONE_BIDDER_REQUIREMENT / R18 | Encabezado “Otros requisitos...” sin los numerales 2.1–2.8. No expresa una obligación verificable por sí solo. |
| C12 / `3ff41e93-519e-4871-a899-f7bade776bee` | D10 p8 | REPEATED_HEADER_OCCURRENCE / No se afirma vínculo secundario | Mismo encabezado CN p8; duplicidad textual de C34, no nuevo requisito. |
| C13 / `46f33501-1f11-4485-83e8-132eee75f0ea` | D10 p9 | REPEATED_HEADER_OCCURRENCE / No se afirma vínculo secundario | Mismo encabezado CN p9; no confundir con el Formato3 que empieza en esa página. |
| C14 / `5da417a7-9897-4121-8fea-9ca82292375f` | D01 p89 | DUPLICATE_CONTEXT_OCCURRENCE / No se afirma vínculo secundario | Repite excepción DA-5 p41/C35 en tabla p89; no obligación positiva adicional. |
| C15 / `644b77f9-d4fc-48a1-85b1-9bf1e93490f1` | D01 p21 | CONTEXT_NOT_STANDALONE_BIDDER_REQUIREMENT / R21 | Obligación del servidor público de levantar acta. Actor no es el participante; corte inicial “1,2 y3” pierde el contexto de sobres. |
| C16 / `6528aae4-2757-4f33-aecb-5d4d859b5a80` | D01 p93 | SUPPORTED_WITH_DEFECT / No se afirma vínculo secundario | Idioma/legibilidad real en D-3; texto pierde “su” antes de elaboración. No es transcripción literal perfecta ni falta de fuente. |
| C17 / `656d0cdb-57bc-44fc-a176-73a62001aea3` | D01 p50 | SUPPORTED_WITH_DEFECT / R05 | Obligación real pero “presente documento” queda sin identidad autónoma: DA-13, aceptación de e.firma. Falta el objeto documental en canonical_text. |
| C18 / `69c2b8b7-00b4-40cf-ac2e-30276109014b` | D10 p6 | REPEATED_HEADER_OCCURRENCE / No se afirma vínculo secundario | Mismo encabezado CN p6; no inferir que reglas de obras/servicios del cuerpo apliquen a suministro de bienes. |
| C19 / `70d0dd2b-1c23-42bf-89ae-0bd85d01f493` | D09 p1 | SUPPORTED_WITH_DEFECT / No se afirma vínculo secundario | Norma general de cumplir especificaciones real; encabezado no conserva los renglones de productos, normas ni cantidades. |
| C20 / `73777880-ca38-497b-95bb-df6e5c00c7d8` | D01 p9 | SUPPORTED_REQUIREMENT / R10 | Aceptación del Acuerdo de Participante en SISCEP es real, aunque el inicio del fragmento arrastra una referencia de sección. |
| C21 / `77b33ba0-d3fc-4dbe-84f7-554b27b1f3a6` | D01 p100 | SUPPORTED_WITH_DEFECT / R23 | Regla real de desempate; omite del texto autónomo el supuesto de empate previo. No aplicar siempre a todos los participantes. |
| C22 / `79926f0d-1458-4aca-8efe-c9f31a375c1f` | D01 p94 | SUPPORTED_REQUIREMENT / No se afirma vínculo secundario | Subrequisito real DT-9: números/descripciones, cantidades, unidad y firma. Cita segmentada/editada, no todas las viñetas de D-3. |
| C23 / `95017461-b1a4-47ed-93af-c8bc8bb89684` | D01 p19 | SUPPORTED_REQUIREMENT / R12 | Firma de última hoja por facultado, donde se solicite; no significa que cualquier persona o firma por ausencia sea válida. |
| C24 / `9cfde3c3-56cb-47ba-ab44-0dfe453ae759` | D01 p19 | SUPPORTED_REQUIREMENT / R13 | Sobre1 comercial PDF/ZIP hasta100MB y documentos D-1: regla de presentación real; no lista todas sus evidencias. |
| C25 / `9f63955e-7690-48c7-ab0d-0f48cd8f249d` | D01 p20 | SUPPORTED_REQUIREMENT / R22 | Sobre3 DD PDF/ZIP hasta100MB y anexo DD: obligación real; no implica extracción de sus documentos individuales. |
| C26 / `a70e5d64-b30b-45b5-a592-120920d43f88` | D01 p18 | CONTEXT_NOT_STANDALONE_BIDDER_REQUIREMENT / R11 | Instrucción de soporte condicionada a dudas; no acredita documentación de elegibilidad ni obligación técnica/comercial autónoma. |
| C27 / `a893319b-0d81-44f5-9256-68d5eca06a3d` | D10 p11 | REPEATED_HEADER_OCCURRENCE / No se afirma vínculo secundario | Mismo encabezado CN p11; instrucciones de formulario no son nuevas declaraciones ya presentadas. |
| C28 / `ad791a3b-7982-4270-90e8-76a0c539cfee` | D01 p78 | SUPPORTED_REQUIREMENT / R02 | Condicional a consorcio: cada integrante entrega Anexo 3/DD-8. No convertirlo en requisito de toda participación individual. |
| C29 / `af3d3a60-bed0-4508-afbb-456cd7525681` | D01 p18 | SUPPORTED_REQUIREMENT / R06 | Considerar bases finales/modificaciones aplicables es regla real; no demuestra que existan modificaciones ni un Source Effect específico. |
| C30 / `b1a44505-2142-45f8-833e-df60b1f894a3` | D01 p97 | CONTEXT_NOT_STANDALONE_BIDDER_REQUIREMENT / R08 | Regla de la CONVOCANTE sobre PMR, no obligación autónoma del licitante. Además corta “Negociación de la” y pierde continuación p98. |
| C31 / `b24f40b2-8d95-4b0e-b899-4b499bc73e18` | D01 p87 | SUPPORTED_REQUIREMENT / R15 | DA-3 membretado y firmado real. Su mera mención no extrae por separado identificación, actas y poderes exigidos en la tabla. |
| C32 / `b705ae17-2893-4f97-a2a4-d8142108eae3` | D01 p88 | SUPPORTED_WITH_DEFECT / No se afirma vínculo secundario | Documentos reales para personas físicas. Corte pierde la condición (Aplica para personas físicas) al final de viñeta. |
| C33 / `cb4b8707-03b3-4473-9eeb-aad087a6c7c8` | D01 p54 | SUPPORTED_WITH_DEFECT / No se afirma vínculo secundario | Obligación por consorcio del manifiesto de origen (p53–54), objeto diferente de DD-2/R09; no tratarlo como duplicado semántico sólo por fórmula textual. |
| C34 / `d6a6f395-e8f9-4d1e-b880-66ff4e5b85b3` | D10 p1 | SUPPORTED_WITH_DEFECT / R01 | La obligación de declarar CN sí existe, sin porcentaje mínimo. El encabezado no conserva Formato 3, plazo ni acuses (§5.1); no equivale al manifiesto de origen de bienes. |
| C35 / `dd222117-76cc-4e75-b62d-f99be4e03240` | D01 p41 | CONTEXT_NOT_STANDALONE_BIDDER_REQUIREMENT / R04 | Excepción válida de no desechamiento del DA-5; NO es obligación positiva de presentar un documento. Conservar como criterio/exención, no como obligación autónoma. |
| C36 / `de7d9362-6515-4c12-8f1b-0b8d77e86dd2` | D01 p49 | SUPPORTED_WITH_DEFECT / No se afirma vínculo secundario | Constancias a nombre del participante real; fragmento descontextualizado no identifica opiniones SAT/IMSS/INFONAVIT ni plazo p49. |
| C37 / `e6eec74b-fbbc-44f2-bf65-181e6209f8b3` | D01 p50 | SUPPORTED_WITH_DEFECT / R30 | Certificado e.firma/SAT por integrante de consorcio; corte A.C. pierde la identificación completa del emisor y la relación e.firma. |
| C38 / `e8a8b5bc-bcd7-47d6-aabc-e06f63ae580c` | D01 p93 | SUPPORTED_REQUIREMENT / R24 | Firma autógrafa por facultado DA-3 en propuesta técnica, al menos última hoja. Solapa parcialmente R12, con alcance técnico más específico. |
| C39 / `ee286b5e-1e17-4ef5-96f7-28aa7ccf1ac9` | D01 p96 | SUPPORTED_REQUIREMENT / R26 | Aritmética correcta y corrección sin cambiar unitarios: criterio económico real, no permiso para fijar precio automáticamente. |
| C40 / `f325106b-7acd-4ef6-bea1-9c8cf26a831a` | D01 p9 | SUPPORTED_REQUIREMENT / R27 | Reutilizar cuenta existente en los supuestos de RI/RC: condición alternativa a R07, no duplicado exacto. |
| C41 / `f40030cd-ceb3-4353-8871-723929b370ce` | D09 p3 | SUPPORTED_WITH_DEFECT / R28 | Corta en “estén en otro”, omite la traducción simple y la conformidad completa; categoría PERSONNEL no corresponde a documentación técnica/idioma. |
| C42 / `fc4b3c0f-3c6d-4281-90d0-2713240aa0ba` | D01 p94 | SUPPORTED_WITH_DEFECT / R29 | Congruencia de propuesta y soportes real; PERSONNEL es clasificación incorrecta. El defecto es categorización, no falta de respaldo textual. |
| C43 / `ffe5dd3e-8cf9-45ee-903f-45f2963c48c8` | D05 p15 | CONTEXT_NOT_STANDALONE_BIDDER_REQUIREMENT / R03 | D05 es modelo sin completar: instrucción al redactor y Anexo en blanco; no acredita una obligación adoptada ni su aplicabilidad. |

## Requested Evidence — cada registro emitido

| Registro / ID | Fuente | Clase | Juicio |
|---|---|---|---|
| E01 / `0c5a44cf-d717-4a31-a820-e1c6b22ebd9b` | D01 p19 | CONTEXT_NOT_DOCUMENT | Mecánica de sobres, no documento autónomo. Solapa paquetes E02/E04/E06/E08; no contar como cinco documentos distintos. |
| E02 / `43f11605-14fa-4c0d-89c9-ebf544b402d8` | D01 p19 | SUPPORTED_BUT_INCOMPLETE | Propuesta económica real. Descripción cortada antes de referencia completa; falta DE-1 y sus campos. FORM sólo cubre el componente de formato, no todo el paquete. |
| E03 / `4c4d3da3-4144-42f3-a852-ffae76d0fba9` | D05 p15 | CONTEXT_NOT_DOCUMENT | Mención/instrucción de modelo con Anexo en blanco. La obligación real de DT-1 condicional se sustenta en D01 pp16/93, no en haber completado ese espacio de D05. |
| E04 / `70226a92-58c0-4eb3-a0dd-e67aac50611f` | D01 p20 | SUPPORTED_BUT_INCOMPLETE | Documentación DD real, pero FORM es demasiado estrecho para paquete de documentos. Omite inventario DD-1…DD-14 y condiciones. |
| E05 / `70c0c14b-4aa7-47c4-b4e5-b6596182591e` | D01 p87 | SUPPORTED_DOCUMENT | Documento DA-3 realmente requerido; página y fragmento correctos. Registro genérico DOCUMENT válido; anexos específicos no se materializan por nombrar el formato. |
| E06 / `87bc451c-e9f6-4730-be69-2779391a9bfe` | D01 p19 | SUPPORTED_BUT_INCOMPLETE | Paquete comercial real; FORM es demasiado estrecho. Corte pierde D-1 y no enumera documentos exigidos. |
| E07 / `ea60dedd-0c4f-4f3f-8c1a-f8bfc9c1619f` | D01 p50 | SUPPORTED_BUT_INCOMPLETE | CERTIFICATE sí corresponde al certificado e.firma, pero “EMITIDO POR EL A” está truncado y no identifica SAT/A.C. ni certificado completo. |
| E08 / `ea8b257b-b343-43ff-a408-f22b3de8c9a9` | D01 p19 | SUPPORTED_BUT_INCOMPLETE | Propuesta técnica real; texto cortado y sin lista DT-9, DT-11, catálogos/cartas. No considerar una evidencia satisfecha por existencia de este registro. |

## Casos fuente y omisiones materiales

Registros fuente propuestos, nunca insertados a la DB ni usados como fixtures de desarrollo. Una referencia amplia no equivale a conservar cada obligación atómica. Cada ID está ligado a documento/página/hash en JSON.

| Dominio | Ausentes individuales, límite inferior | Componentes incompletos |
|---|---:|---:|
| ATTRIBUTES | 10 | 0 |
| QUANTITIES | 4 | 0 |
| REQUESTED_EVIDENCE | 18 | 0 |
| REQUIREMENTS | 18 | 2 |
| SCOPE | 8 | 0 |

| Caso | Fuente / sección | Hecho fuente | Resultado |
|---|---|---|---|
| REQUIREMENTS-01 | D01 p15 / 2.1 | Entrega en 60 días naturales desde formalización | MISSING |
| REQUIREMENTS-02 | D01 p15 / 2.3 | DDP nacionales / DAP extranjeros, destino final | MISSING |
| REQUIREMENTS-03 | D01 p15 / 3.1 | Precios fijos, dos decimales y sin IVA al cotizar | MISSING |
| REQUIREMENTS-04 | D01 p16 / 3.6 | Subcontratación no aplica | MISSING |
| REQUIREMENTS-05 | D09 p1 / 1.1 | Suministro conforme a los dos modelos GE y cantidades de la tabla | MISSING |
| REQUIREMENTS-06 | D09 p2 / 1.2 | Contenedor con espuma, ESD y protección contra humedad | MISSING |
| REQUIREMENTS-07 | D09 p2 / 1.2 | Dos juegos de cables de comunicación de cada puerto del relevador | MISSING |
| REQUIREMENTS-08 | D09 p2 / 1.2 | Software libre licencia en USB para Windows10 | MISSING |
| REQUIREMENTS-09 | D09 p2 / 2.2 | Anexar catálogos/fichas/dibujos/boletines del fabricante identificando partidas, marca y modelo | MISSING |
| REQUIREMENTS-10 | D09 p3 / 2.6 | Carta de componentes nuevos, compatibles y ensamble correcto | MISSING |
| REQUIREMENTS-11 | D09 p3 / 2.7 | Compromiso de avisar entrega con48h de anticipación | MISSING |
| REQUIREMENTS-12 | D09 p3 / 2.7 | Marcar bienes con centro de trabajo y contrato, letra>=10mm | MISSING |
| REQUIREMENTS-13 | D09 p3 / 3.1 | Comprometer carta original fabricante y certificados de calidad en entrega | MISSING |
| REQUIREMENTS-14 | D01 p49 / DA-12 | Opiniones positivas SAT/IMSS/INFONAVIT posteriores al fallo con plazo de3 días hábiles | MISSING |
| REQUIREMENTS-15 | D01 p94 / D-3 | Cotizar total de partidas y conformidad de cada una | MISSING |
| REQUIREMENTS-16 | D01 p32 / 33 | Adoptar/mantener programa Pemex CUMPLE o compromiso de implementar propio | MISSING |
| REQUIREMENTS-17 | D09 p3 / 2.5/2.8 | Carta compromiso de cumplimiento Formato4 SSPA si resulta ganador | MISSING |
| REQUIREMENTS-18 | D10 p2 / 5.1.1–5.1.3 (pp2–4) | Formato3 de CN, plazo anual y acuse: detalles no conservados por R01 | INCOMPLETE_COMPONENT |
| REQUIREMENTS-19 | D09 p3 / 2.3 | Traducción simple de adjuntos en otro idioma: perdida al cortar R28 | INCOMPLETE_COMPONENT |
| REQUESTED_EVIDENCE-01 | D09 p2 / 2.2 | Catálogos/fichas/dibujos/boletines emitidos por fabricante para oferta | MISSING |
| REQUESTED_EVIDENCE-02 | D09 p3 / 2.5/2.8 | Carta compromiso SSPA de adjudicado | MISSING |
| REQUESTED_EVIDENCE-03 | D09 p3 / 2.6 | Carta de componentes nuevos/compatibles/ensamble | MISSING |
| REQUESTED_EVIDENCE-04 | D09 p3 / 2.7 | Manifiesto de compromiso aviso de entrega y marcado | MISSING |
| REQUESTED_EVIDENCE-05 | D09 p3 / 3.1 | Carta original fabricante con certificados de calidad para entrega | MISSING |
| REQUESTED_EVIDENCE-06 | D09 p4 / 3.2 | Copia de nota de remisión con descripción/especificaciones | MISSING |
| REQUESTED_EVIDENCE-07 | D09 p4 / 3.4 | Contrato impreso en2 juegos para entrega | MISSING |
| REQUESTED_EVIDENCE-08 | D01 p49 / DA-12 | Opinión positiva SAT, etapa posterior al fallo | MISSING |
| REQUESTED_EVIDENCE-09 | D01 p49 / DA-12 | Opinión positiva IMSS, etapa posterior al fallo | MISSING |
| REQUESTED_EVIDENCE-10 | D01 p49 / DA-12 | Opinión positiva INFONAVIT, etapa posterior al fallo | MISSING |
| REQUESTED_EVIDENCE-11 | D01 p82 / DD-12 | Fotografías actualizadas fachada/áreas; R25 sí detecta requisito, no Requested Evidence | MISSING |
| REQUESTED_EVIDENCE-12 | D10 p2 / 5.1.1 | Formato3 declaración CN de bienes, no porcentaje mínimo exigido | MISSING |
| REQUESTED_EVIDENCE-13 | D01 p78 / DD-8 | Cuestionario Anexo3 completo, firmado y escaneado; R02 sólo cubre condición de consorcio | MISSING |
| REQUESTED_EVIDENCE-14 | D01 p8 / II.3.a | DA-1 manifiesto de interés por plazo del cronograma | MISSING |
| REQUESTED_EVIDENCE-15 | D01 p87 / D-1 / DA-3 | Identificación oficial vigente con fotografía y ambos lados | MISSING |
| REQUESTED_EVIDENCE-16 | D01 p87 / D-1 / DA-3 | Primera acta constitutiva y última reforma para persona moral | MISSING |
| REQUESTED_EVIDENCE-17 | D01 p87 / D-1 / DA-3 | Poder de representante para firmar contrato, cuando aplique | MISSING |
| REQUESTED_EVIDENCE-18 | D01 p87 / D-1 / DA-3 | Constancia situación fiscal, distinta de opinión positiva SAT | MISSING |
| SCOPE-01 | D09 p1 / 1.1 / partida1 | Suministrar relevador F60-U03-HKH-F8L-H6L-M6B-P6B-W7K | MISSING |
| SCOPE-02 | D09 p1 / 1.1 / partida2 | Suministrar relevador L90-U03-HLH-F8L-H6E-LXX-NXX-S6A-U6K-W7K | MISSING |
| SCOPE-03 | D09 p2 / 1.2 / partidas1y2 | Entregar cables de comunicación por puerto | MISSING |
| SCOPE-04 | D09 p2 / 1.2 / partidas1y2 | Entregar software de configuración/comunicación enUSB | MISSING |
| SCOPE-05 | D09 p2 / 1.2 / partidas1y2 | Embalaje con espuma, protecciónESD y humedad | MISSING |
| SCOPE-06 | D09 p3 / 2.7 | Marcado con centro de trabajo/número de contrato | MISSING |
| SCOPE-07 | D09 p3 / 2.7 | Coordinación de recepción mediante aviso anticipado | MISSING |
| SCOPE-08 | D09 p3 / 3 / pp3–4 | Documentación acompañante de entrega: carta, nota, fichas, contrato | MISSING |
| ATTRIBUTES-01 | D09 p1 / 1.1 | Marca/fabricante GE MULTILIN | MISSING |
| ATTRIBUTES-02 | D09 p1 / 1.1 partida1 | Modelo F60-U03-HKH-F8L-H6L-M6B-P6B-W7K | MISSING |
| ATTRIBUTES-03 | D09 p1 / 1.1 partida2 | Modelo L90-U03-HLH-F8L-H6E-LXX-NXX-S6A-U6K-W7K | MISSING |
| ATTRIBUTES-04 | D09 p2 / 1.2 | Compatibilidad del software con Windows10 | MISSING |
| ATTRIBUTES-05 | D09 p1 / 1.1.1 | Norma IEC60255-1:2022, cláusula8 | MISSING |
| ATTRIBUTES-06 | D09 p2 / 1.2 | Protección antiestáticaESD | MISSING |
| ATTRIBUTES-07 | D09 p3 / 2.7 | Dimensión mínima de marcado10mm | MISSING |
| ATTRIBUTES-08 | D01 p15 / 2.1 | Plazo de entrega60 días naturales desde formalización | MISSING |
| ATTRIBUTES-09 | D01 p15 / 3.1 | Precios fijos | MISSING |
| ATTRIBUTES-10 | D01 p16 / 3.2 | Moneda permitida MXN o USD | MISSING |
| QUANTITIES-01 | D09 p1 / 1.1 partida1 | 1 PZA de modelo F60; confirmación visual independiente D02p1 | MISSING |
| QUANTITIES-02 | D09 p1 / 1.1 partida2 | 2 PZA de modelo L90; confirmación visual independiente D02p1 | MISSING |
| QUANTITIES-03 | D09 p2 / 1.2 | 2 juegos de cables de comunicación de cada puerto; no inferir número de puertos ni total de cables | MISSING |
| QUANTITIES-04 | D09 p4 / 3.4 | 2 juegos de contrato impreso; son documentación, no dos relevadores adicionales | MISSING |
| REQUIREMENTS-20 | D11 p1 / Formato4 / VIII Formatos | Formatos6y7 sí aplican y deben entregarse5 días hábiles posteriores a la entrega del requerimiento | MISSING |

## Cero Scope, Attributes y Quantities

Cero NO es semánticamente correcto como descripción de las fuentes. Se identificaron8 obligaciones de alcance,10 atributos/condiciones y4 cantidades explícitas como muestra mínima; materializados0/8,0/10 y0/4 en esos conjuntos dirigidos. No es recall global de todo el expediente.

B-1 (D09p1) enumera1PZA F60 y2PZA L90 marcaGE; AnexoC (D02p1, lectura visual) confirma ambos renglones. D09p2 agrega2 juegos de cables por cada puerto y softwareUSB/Windows10; no se conoce el número de puertos y NO se multiplica. D09p4 exige2 juegos del contrato impreso, que no son cantidad de equipos.

No atribuir todo a PDFs de imagen: B-1 ya tiene textoNative con alcance material. El materializador de Scope conserva proveedor semántico opcional y adapterpredeterminado de detalleVision; bajo AVAILABLE_ONLY no se generó percepción adicional. Es limitación de cobertura del camino configurado, no demostración de que el Tender carezca de alcance.

## Confianza y seguridad

- `45a0afe3-7362-40cc-92d0-9c78ab8936eb` (D03 p12): **TRUSTED_INCORRECT propuesto**. Cuestionario de integridad, columna No y pregunta1; no partida contractual. Anchor No/1 cruza columnas.
- `67617b58-a491-4ae6-ad11-5dc08f3d727f` (D01 p13): **TRUSTED_INCORRECT propuesto**. Índice de reglas de participación, no partida contractual; “Concepto/1” no prueba ITEM_1.

La provenance apunta a páginas existentes: el error es semántico de tipo de tabla/owner, no documento o página inventados. El anchor “No/1” de D03p12 combina columnaNo con pregunta1. D01p13 enumera reglas1–21 y p14 continúa22–33. Ninguna es el catálogo de suministros.

Estos mismos2 casos serían2 TRUSTED_INCORRECT y subsetestructural2 si una persona los aprueba en el contrato canónico inclusivo; no cuatro errores ni prueba de cuatro obligaciones contractuales falsas. No hubo propagación a Scope/Attributes/Quantities confiados: no existen registros de esos dominios.

No se identificaron fuentes/documentos de evidencia fabricados en los outputs examinados; sí pérdida de fidelidad/contexto en seis citas y descripciones truncadas (p.ej.E07). Eso no certifica todos los campos recursivos de provenance. No se asigna0 a conflictos suprimidos o revisión innecesaria sin verdad exhaustiva.

Los31Requirements y8Evidence enreview preservan abstención; una revisión correcta puede seguir siendo inútil o incompleta. R01normalization_confidence0.9855/R04=1.0 no son confianza contractual ni autoridad humana.

## Documento unsupported y pérdida de percepción

D08 es `.DS_Store`, identificado por encabezadoBud1 y `file -b` como Apple Desktop Services Store. No se identificó información contractual perdida por su indisponibilidad Native. No se extrajo ni inyectó su contenido como evidencia.

Distintamente, D02p1 yD11p1 son PDFs soportados, pero su contenido relevante es imagen y Native no lo percibió. D11 selecciona numeralesSSPA; secciónVI Salud esN/A y Formatos6y7 síaplican con5 días hábiles posteriores a entrega del requerimiento. No se reconstruyen cláusulas externas por esos números.

## Clasificación arquitectónica

- **confidence/trust policy defect**: Dos grupos contractuales confiados creados desde índice/cuestionario; abstención estructural insuficiente sin semántica del rol de tabla. Fuentes: D01p13, D03p12.
- **generic extraction defect**: Corte por oraciones, abreviaturas y bordes de página pierde condiciones, objetos y listas; encabezados tratados como registros autónomos. Fuentes: D09p3/R28, D01p97–98/R08, D01p50/E07.
- **semantic classification defect**: PERSONNEL para documentación técnica; EXPERIENCE para nota de redacción; FORM para paquetes DD/comerciales. Fuentes: R20, R28, R29, E04, E06.
- **normalization defect**: R09 yC33 requieren objeto/contexto distinto pese a fórmula igual; no se demuestra merge erróneo persistido: sólo riesgo de equivalencia por léxico y pérdida de identidad documental. R01/DA5 tienen repeticiones legítimas que no son nuevos hechos. Fuentes: D01p53–54, D01p71–72, D10encabezados.
- **perception/capability limitation**: Native insuficiente en dosPDFs de imagen. Bajo AVAILABLE_ONLY la ausencia es resultado esperado, semánticamente material. Fuentes: D02p1, D11p1.
- **expected MVP limitation**: Scope predeterminado sin proveedor semántico instalado ni adquisición nueva no consume automáticamente todo alcance Native. Cero hijos no prueba ausencia de obligaciones. Fuentes: D09pp1–4, backend/app/scope_detail_materializer.py, backend/app/scope_detail_adapters.py.
- **provenance defect**: Defecto semántico de fidelidad de citas/objeto:6 candidatos no son literal normalizado exacto; E07 carece emisor/objeto completo. Documentos/páginas fuente sí existen. Fuentes: C16, C19, C22, C32, C33, C36, E07.
- **unsupported-source limitation**: Native no soporta Finder metadata; indisponibilidad explícita adecuada y sin pérdida contractual identificada. Fuentes: D08.
- **no defect**: Preparación por capacidad continuó sin documentos ficticios; hubo abstención de confianza contractual en31 Requirements y8 Evidence. No nueva inferencia para cubrir huecos. Fuentes: frozenfirstpass, executionledger.

## Próxima decisión

Revisión humana de este ledger y los2 juicios de estructura; priorizar control genérico de identidad/rol de tablas y cobertura disponible, con fixtures sintéticos futuros. Cualquier cambio requiere slice/commit separado y, si se autoriza otro blind run, Attempt3 nuevo. No certificar MVP06/MVP07 con este pase.

Se preservaron ambos intentos y todos los archivos históricos. No se modificó código, schema, migración, configuración de proveedores, DB ni outputs congelados. Sin extracción productiva repetida, proveedores, Attempt3, stage, commit o push. Los TXT/PNG nuevos son ayudas de lectura de adjudicación fuera de los resultadosproductivos, no percepción de Attempt2.
