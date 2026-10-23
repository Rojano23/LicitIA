# M9-A — revisión open source para arquitectura de propuestas

Consulta de fuentes primarias:2026-10-22. Referencias de diseño, sin dependencias nuevas.
No documentos ni precios enviados a servicios; sólo documentación pública consultada.

| Proyecto / fuente | Licencia comprobada | Patrón útil / futuro | Decisión M9-A |
|---|---|---|---|
| [python-docx](https://python-docx.readthedocs.io/en/latest/) / [repo/licencia](https://github.com/python-openxml/python-docx/blob/master/LICENSE) | MIT | DOCX editable con párrafos/tablas/estilos; renderer separado del input tipado en M9-C | Referencia para escritura futura; candidata futura; corrección M9-C: no estaba instalada como dependencia directa del runtime |
| [Jinja](https://jinja.palletsprojects.com/en/stable/templates/) / [licencia](https://github.com/pallets/jinja/blob/main/LICENSE.txt) | BSD-3-Clause | Separar datos de plantilla/layout; no poner cálculo comercial en plantilla, M9-B/C | Sólo referencia; no nuevas plantillas ni dependencia |
| [XlsxWriter](https://xlsxwriter.readthedocs.io/) / [licencia](https://github.com/jmcnamara/XlsxWriter/blob/main/LICENSE.txt) | BSD-2-Clause | Hojas/tablas/celdas como salida editable determinista, M9-C; comparar con openpyxl ya usado por M7-C antes de añadir otro writer | Sólo referencia; no instalar |
| [frictionless-py](https://github.com/frictionlessdata/frictionless-py) / [licencia](https://github.com/frictionlessdata/frictionless-py/blob/main/LICENSE.md), [Data Package](https://specs.frictionlessdata.io/data-package/) | MIT del código | Descriptor versionado separado de recursos/artefactos, manifiesto con identidades; M9-C/D | Referencia, no paquete ZIP/manifiesto de outputs ahora |
| [OCFL1.1](https://ocfl.io/1.1/spec/) | CC-BY4.0 del documento, no licencia de biblioteca | Inventarios/verificación e historial de versiones inmutables; separar working state de versión preservada | Patrón de referencia con atribución; no implementar OCFL ni copiar código |

Interpretación arquitectónica propia: el DTO versionado y snapshot verificado alimentarán
renderers intercambiables locales en M9-B/C; ProposalVersion conserva configuración y
referencia de snapshot sin duplicar su subgrafo. Freeze fija configuración/hash, no produce
archivos. Las secciones son genéricas y no dependen de un formato institucional final.

Se revisó además [docxtpl](https://github.com/elapouya/python-docx-template/blob/master/LICENSE.txt):
LGPL-2.1 según su licencia; no se seleccionó como dependencia permisiva para este slice.
No se presume que sea MIT por usar python-docx/Jinja. Antes de incorporar cualquier writer
futuro se revisarán versión fijada, dependencias transitivas, notices y distribución comercial.
La revisión actual no certifica licencias de un bundle futuro ni decide el diseño final.

## Selección efectiva M9-C

Se incorpora python-docx1.2.0 (MIT), ReportLab5.1.0 (BSD-3-Clause), lxml6.1.3
(BSD-3-Clause y notices transitivos). Se reutilizan openpyxl3.1.5 (MIT), charset-normalizer3.5.1
(MIT) y Pillow fijado. Pins/hashes de wheels en lock RC macOS arm64/CPython3.13.
No se incorpora XlsxWriter, Jinja/docxtpl, Office automation ni servicios externos.
ReportLab usa Vera local con licencia Bitstream Vera que permite distribución en software;
se conservan licencias en [notices](licenses/proposal-exports/). No se usa ReportLab PLUS/pyRXP.
Fuentes primarias: [python-docx](https://github.com/python-openxml/python-docx/blob/master/LICENSE),
[ReportLab FAQ](https://docs.reportlab.com/developerfaqs/),
[lxml copyright](https://lxml.de/copyright.html). Los notices del wheel fijado prevalecen
para distribución; esta revisión se limita a dependencias incorporadas al slice.
