# M10-B — inventario público y bloqueo de adquisición

Fecha de inventario: 2026-10-23. El bloqueo original de dos adapters fue revisado:
**CFE implementado y validado para revisión; Compras MX DEFERRED — SOURCE AUTOMATION RESTRICTED**.
[Contrato acotado vigente M10-B](discovery-cfe.md). Los conteos siguientes conservan el inventario previo.
M10-A ACCEPTED: `d9e9735ef97ad23f0b42b9c3aa3498ae60f71052`, sin push. MVP-09 CLOSED.

## CFE: superficie actual verificada

Entrada oficial: <https://msc.cfe.mx/Aplicaciones/NCFE/Concursos/>.
El HTML público publica `Procedure/getProcBusqueda` (POST), `Procedure/ObtenerCatalogos`
y un formulario POST `Procedure/Details`. No fue necesario browser automation.
Se usó la cookie/token CSRF que emite el formulario público, sin iniciar sesión.

Filtros publicados: tipo de procedimiento/contratación, entidad federativa, número,
descripción, estado, publicación exacta o rango, testigo social, carácter y modalidad.
Los inputs `type=date` envían ISO `YYYY-MM-DD`: las primeras consultas con fechas
`DD/MM/YYYY` respondieron 500; corregir al formato del formulario produjo 200 JSON.
Esto fue corrección de la consulta operacional, no evidencia de indisponibilidad CFE.

Consulta controlada: publicación 2026-10-01 a 2026-10-23, demás filtros según valores
públicos de «todos». Una respuesta JSON completa de 867 filas, 867 IDs distintos,
0 duplicados y 0 filas sin Id/Descripción. No se persistieron Opportunities.
El grid Kendo recibe el array completo y pagina **en el cliente** con pageSize 200;
no se observó paginación remota ni un total independiente. No confundir una respuesta
HTTP con cinco páginas remotas recorridas ni declarar completitud de un adapter inexistente.
Un futuro adapter puede entregar batches locales del array acotado, declarando ese mecanismo.

Campos reales: Id, Numero, Descripcion, EstadoProcedimiento, EntidadFederativa,
TipoProcedimientoClave, TipoContratacionClave, FechaPublicacion (`/Date(ms)/`),
TestimonioSocial y otros datos de adjudicación que no son precios de producto.
Identidad candidata: namespace CFE + Id; conservar Numero humano por separado.
Mapeo propuesto, **todavía no implementado**: descripción→title/description, fecha→published_date,
estado literal→source_status, tipos→event_type/supply_type. Empresa/Área Contratante
sólo se verificaron en detalle; no inferirlos desde el número o la entidad geográfica.

Se verificó un detalle por POST con su token público: 200 HTML; Empresa y Área Contratante
literales y 6 referencias de anexos. El HTML genera `Procedure/GetAnexo?id=<opaque token>`.
No se descargaron archivos ni se ejecutó JavaScript remoto. La estabilidad temporal de esos
identificadores de anexo no está certificada. GET `Details?id=...` respondió 404: **no publicar
un URL de detalle GET inventado**. La entrada pública es un enlace humano válido; un adapter
futuro debe documentar el contexto POST si conserva esa navegación.

## Compras MX: actual difusión, acceso bloqueado

Entrada oficial: <https://comprasmx.buengobierno.gob.mx/sitiopublico/> (200).
La propia [explicación oficial](https://comprasmx.buengobierno.gob.mx/compras-mx) distingue
esta difusión actual de las versiones históricas. El bundle público observado fue
`main.7b33046d5003f711.js`.

El bundle identifica el backend público
`https://upcp-cnetservicios.buengobierno.gob.mx/whitney/sitiopublico/`:
listado POST `expedientes/v2/pu_obtener?rows=...&page=...`, orden opcional,
detalle `expedientes/{id}?id_proceso=...` y anexos paginados por expediente.
Esto describe el cliente publicado, **no certifica respuestas/contratos de filas**.

El camino actual de listado usa un desafío PoW WASM (`solve_pow`), `challenge/init`,
`challenge/solve` y headers `X-Challenge-ID` / `X-Challenge-Answer`.
Una petición pública sin resolverlo devolvió 401 JSON «Acceso no permitido».
No se generó/resolvió el desafío, no se forjaron headers, no se intentó acceder por el endpoint
anterior para evitarlo y no se recurrió a autenticación, CAPTCHA bypass ni endpoints privados.

Por ello no están verificadas normalización, identidad autoritativa de filas, estados,
totales, documentos ni recorrido efectivo. **No crear fixtures que aparenten reproducir
un contrato de resultados aún no observado.** No existe adapter Compras MX implementado.
La dependencia/entidad seguirá siendo metadata de COMPRAS_MX, no una fuente por dependencia.

**DEFERRED — legacy/historical procurement sources**: CompraNet 3/5 no se visitaron.
No se reclama cobertura de todo el archivo histórico federal ni de todas las versiones CFE.

## Decisión arquitectónica vigente

Se autoriza completar CFE sobre el Core existente; Compras MX permanece diferido por
restricción externa. No se declara completo el plan original de dos adapters. El sitio
manualmente accesible no constituye autorización de adquisición automática. No resolver,
emular, reverse-engineer o eludir PoW; no browser bypass ni cookies/tokens de navegador.
No nuevas solicitudes a Compras MX en esta continuación, parser ni fixtures especulativas.
No sustitución por CompraNet histórico, contratos o PAAASOP.

Entradas públicas observadas previamente: portal raíz Compras MX, `/compras-mx`,
`/sitiopublico/`, bundle indicado arriba y backend público configurado por ese cliente.
Rutas publicadas observadas: listado expedientes/v2/pu_obtener, detalle expedientes/{id},
anexos expedientes/{id}/anexos, y rutas de referencia documental `documentos/recursos/ulck`
y `documentos/recursos/v2/pu_obtener` en el servicio documental anunciado. Sus contratos de
respuesta no se verificaron. Las rutas challenge/init y challenge/solve sólo se observaron
en el cliente, no se invocaron. No continuar la investigación del mecanismo PoW.

Futuro ComprasMXAdapter sólo con interfaz oficial de automatización documentada y autorizada;
registro/capabilities y dominio genérico ya admiten esa extensión, sin inventar soporte actual.
No migración079 ni dependencia nueva. CFE no amplía el soporte institucional de Tender Analysis.
M10-C sigue futuro después de revisión del slice acotado.

Evidencia operacional local, no destinada a Git:
`backend/reports/m10_b/source_inventory.json`, `m10a_commit.json` y `final_report.md`.
Capturas HTTP temporales permanecen en `/private/tmp`, fuera del repositorio; el inventario
conserva hashes, sin cookies/tokens CSRF ni cuerpos de respuestas. Los datos son públicos;
ningún documento o perfil privado se transmitió.
