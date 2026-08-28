# LicitIA — Product UI Blueprint v0.1

**Estado:** Draft aprobado como guía de producto  
**Fecha:** 2026-08-28  
**Alcance:** Primer MVP single-user  
**Referencia:** Trabajo acumulado hasta cierre de MVP-02 — Document Intelligence Foundation

---

## 1. Propósito del documento

Este documento define la **filosofía de interfaz, navegación y experiencia de usuario de LicitIA** para el primer MVP.

No es una especificación visual final ni obliga a reproducir exactamente los mockups actuales de Stitch. Su objetivo es conservar las decisiones de producto ya tomadas y evitar que la UI definitiva termine reflejando la arquitectura interna del software en lugar del flujo real de trabajo de una persona que prepara licitaciones.

Las pantallas actuales usadas durante MVP-01 y MVP-02 deben entenderse principalmente como una:

> **Engineering / Acceptance UI**

Su propósito actual es permitir validar motores, estados, trazabilidad, versiones, resultados y decisiones humanas.

La futura interfaz comercial será una:

> **Product UI**

Su propósito será traducir toda la complejidad interna de LicitIA en decisiones, pendientes, evidencia y acciones claras para el usuario.

---

## 2. Usuario objetivo del primer MVP

El primer MVP está diseñado para un **usuario individual que realiza prácticamente todo el proceso de licitación por sí mismo**.

Este usuario puede encargarse de:

- revisar la convocatoria y bases;
- identificar requisitos;
- integrar documentación legal, fiscal, financiera y administrativa;
- realizar revisión técnica;
- solicitar y comparar cotizaciones;
- definir soluciones;
- costear partidas;
- preparar la propuesta;
- revisar faltantes antes de presentar.

Por esta razón:

- **RBAC no es requisito de salida del primer MVP**;
- no se diseñará todavía una experiencia separada para Legal, Compras, Ingeniería, Dirección, etc.;
- el piloto inicial debe permitir que un solo usuario tenga acceso completo al flujo.

RBAC se diseñará después de pruebas reales y retroalimentación, cuando exista evidencia de cómo distintas empresas separan responsabilidades.

---

## 3. Job-to-be-Done principal

La experiencia del producto debe ayudar a responder:

> **“Recibí una licitación. ¿Qué me están pidiendo, qué tengo, qué me falta, qué debo cotizar y qué debo hacer para presentar una propuesta completa y trazable?”**

El flujo general objetivo es:

```text
Recibo licitación
      ↓
Cargo documentos
      ↓
LicitIA organiza y entiende el expediente
      ↓
Identifico requisitos
      ↓
Relaciono evidencia de mi empresa
      ↓
Evalúo cumplimiento
      ↓
Identifico partidas
      ↓
Defino soluciones
      ↓
Solicito / cargo cotizaciones
      ↓
Calculo costos y precio
      ↓
Integro propuesta
      ↓
Reviso pendientes y riesgos
      ↓
Presento expediente
```

---

## 4. Principios UX de LicitIA

### 4.1 La navegación sigue el trabajo del usuario, no los motores internos

El usuario no debe pensar en:

- OCR;
- NormalizedContent;
- chunks;
- classifier version;
- resolver version;
- reference graph;
- processing status interno.

Debe pensar en:

- documentos;
- requisitos;
- cumplimiento;
- faltantes;
- partidas;
- cotizaciones;
- costos;
- propuesta.

---

### 4.2 Evidence and traceability underneath; clarity and action on top

La complejidad interna puede ser alta, pero la experiencia no debe serlo.

Toda conclusión importante debe seguir siendo trazable a:

- documento;
- página;
- fragmento;
- evidencia;
- decisión humana cuando corresponda.

Pero esa información debe aparecer cuando aporta valor, no dominar la pantalla principal.

---

### 4.3 AI propone; el usuario confirma, corrige o rechaza

LicitIA puede:

- sugerir clasificación;
- identificar requisitos;
- proponer relaciones;
- sugerir evidencia;
- detectar posibles incumplimientos;
- detectar faltantes;
- extraer cotizaciones;
- sugerir estimados.

El usuario conserva la autoridad sobre decisiones críticas.

---

### 4.4 Documento encontrado ≠ requisito satisfecho

La UI nunca debe inducir al usuario a asumir cumplimiento únicamente porque existe un archivo relacionado.

Ejemplo:

```text
Documento encontrado
        ≠
Requisito satisfecho
```

La evidencia debe evaluarse contra el contenido y la condición exigida.

---

### 4.5 Progressive disclosure

La información se organiza en tres niveles:

#### Nivel 1 — Product UI
Lo que necesita el usuario para trabajar.

Ejemplos:

- Documento listo.
- Requiere revisión.
- Falta evidencia.
- Encontramos dos versiones posibles.
- Cotización vencida.
- Sin precio.
- Requisito no cubierto.

#### Nivel 2 — Evidencia / detalle
Disponible al abrir un requisito, documento, partida o alerta.

Ejemplos:

- documento fuente;
- página;
- fragmento;
- documento de evidencia;
- motivo de revisión;
- candidato seleccionado.

#### Nivel 3 — Diagnóstico técnico
Reservado para soporte, administración o desarrollo.

Ejemplos:

- UUID;
- SHA-256;
- OCR provider;
- normalized sources;
- chunks;
- engine version;
- audit codes;
- internal processing status.

---

## 5. Traducción de estados técnicos a lenguaje de producto

| Estado técnico / interno | Etiqueta de producto sugerida |
|---|---|
| `TEXT_EXTRACTION_COMPLETE` | Documento procesado |
| `NO_NATIVE_TEXT` | Requirió lectura OCR |
| `AMBIGUOUS_REFERENCES` | Hay relaciones por revisar |
| `UNRESOLVED_REFERENCES` | Se mencionan documentos no encontrados |
| `HUMAN_RESOLVED` | Vinculado manualmente |
| `CURRENT_FILENAME_COLLISION` | Hay dos versiones posibles del mismo documento |
| `MISSING_NORMALIZED_CONTENT` | Documento aún no listo para análisis |
| `STALE_ANALYSIS_VERSION` | Ocultar al usuario normal; mostrar en diagnóstico |
| `PENDING` | Pendiente de procesamiento |
| `CONFIRMED` | Confirmado |
| `SUGGESTED` | Sugerencia de LicitIA |
| `NEEDS_REVIEW` | Requiere revisión |

La Product UI debe priorizar mensajes completos sobre códigos internos.

Ejemplo:

> **Encontramos dos documentos con el mismo nombre. Revisa cuál corresponde.**

en lugar de:

> `CURRENT_FILENAME_COLLISION`

---

## 6. Navegación propuesta para el primer MVP

La navegación debe mantenerse simple y orientada al proceso.

```text
LICITIA
│
├── Inicio
│
├── Licitaciones
│    └── [Licitación seleccionada]
│         ├── Resumen
│         ├── Documentos
│         ├── Requisitos
│         ├── Cumplimiento
│         └── Oferta
│              ├── Partidas
│              ├── Cotizaciones
│              ├── Proveedores
│              ├── Costeo
│              └── Propuesta
│
├── Mi empresa
│    ├── Datos generales
│    ├── Documentos legales
│    ├── Documentos fiscales
│    ├── Documentos financieros
│    ├── Experiencia
│    ├── Personal
│    ├── Certificaciones
│    └── Biblioteca documental
│
├── Reportes
└── Configuración
     └── Diagnóstico
```

### Nota sobre “Partidas / Anexo C”

La navegación principal debe utilizar **Partidas**.

“Anexo C” puede mostrarse cuando el documento o institución concreta utiliza ese nombre.

El Core de LicitIA no debe depender de nomenclatura específica de PEMEX u otra institución.

### Nota sobre “Cumplimiento técnico”

Debe evolucionar a:

> **Cumplimiento**

porque el análisis futuro abarcará:

- administrativo;
- legal;
- fiscal;
- financiero;
- experiencia;
- personal;
- técnico;
- comercial;
- económico;
- seguridad.

---

## 7. Experiencias principales del producto

El Blueprint v0.1 define ocho experiencias principales.

---

### 7.1 Centro de Licitaciones / Dashboard

**Objetivo:** que el usuario entienda en menos de un minuto qué necesita atención.

Conceptos a conservar del mockup:

- licitaciones activas;
- próximas a cierre;
- en análisis;
- listas para presentar;
- licitaciones recientes;
- requisitos pendientes;
- documentos por vencer;
- cotizaciones pendientes.

La Product UI debe priorizar:

```text
¿Qué tengo que hacer hoy?
¿Qué está en riesgo?
¿Qué está próximo a vencer?
¿Qué licitación requiere atención?
```

#### Restricción

No mostrar porcentajes decorativos o arbitrarios.

Ejemplo:

`Cumplimiento 91%`

sólo será válido si existe una definición matemática estable y documentada.

Mientras tanto, preferir:

- 62 requisitos con evidencia;
- 9 sin evidencia;
- 5 no cumplen;
- 10 pendientes de revisión.

**Referencia visual:** `Dashbrd.png`

---

### 7.2 Nueva Licitación

**Objetivo:** crear el workspace y cargar el corpus inicial.

Conceptos a conservar:

- drag & drop;
- PDF, DOCX, XLSX;
- procesamiento local;
- estado de procesamiento;
- resumen preliminar.

El mensaje de privacidad/local processing debe ser visible:

> **Los documentos se procesan localmente.**

El panel de progreso debe utilizar lenguaje de producto.

Ejemplo:

```text
Leyendo documentos                  ✓
Organizando expediente              ✓
Identificando documentos            ✓
Buscando requisitos                 En proceso
Relacionando partidas               Pendiente
```

OCR puede mostrarse sólo en detalle técnico.

**Referencia visual:** `NuevaLicita(1).png`

---

### 7.3 Workspace / Resumen de una Licitación

**Objetivo:** ser la pantalla principal de trabajo después de cargar una licitación.

Debe responder:

- ¿qué documentos hay?;
- ¿qué documentos requieren atención?;
- ¿cuántos requisitos se identificaron?;
- ¿qué falta?;
- ¿qué partidas requieren cotización?;
- ¿qué riesgos existen?;
- ¿qué tan cerca estoy de presentar?;

Esta pantalla se diseñará con mayor precisión después de Requirement, Evidence y Compliance Engine.

---

### 7.4 Documentos + Visor de Evidencia

**Objetivo:** permitir navegar el expediente y comprobar cualquier conclusión de LicitIA contra la fuente.

Concepto central:

```text
Requisito
    ↓
Ver fuente
    ↓
Documento
    ↓
Página exacta
    ↓
Texto resaltado
```

Debe permitir también el camino inverso cuando corresponda:

```text
Documento
    ↓
Fragmento
    ↓
Requisitos asociados
```

El usuario no necesita conocer cómo se obtuvo el texto.

Debe poder responder:

> **“Muéstrame dónde dice eso.”**

**Referencia visual:** `VisorDoctos.png`

---

### 7.5 Requisitos + Matriz de Cumplimiento

**Objetivo:** convertirse en el centro operativo de interpretación de la licitación.

Estructura conceptual:

| Campo | Significado |
|---|---|
| ID | Identificador de Requirement |
| Categoría | Dominio funcional |
| Requisito | Obligación interpretada |
| Obligatorio | Condición de obligatoriedad |
| Evidencia esperada | Qué debería demostrar cumplimiento |
| Evidencia encontrada | Documento de la empresa / propuesta |
| Estado | Resultado de evaluación |
| Fuente | Documento + página + fragmento |

Estados candidatos oficiales:

- **Cumple**
- **Revisar**
- **No cumple**
- **Sin evidencia**

La matriz debe permitir filtrar por:

- categoría;
- estado;
- obligatoriedad;
- pendiente de revisión;
- documento;
- partida cuando corresponda.

#### Trazabilidad bidireccional

```text
REQUISITO
   │
   ├── Ver fuente ─────► documento de licitación
   │
   └── Ver evidencia ──► documento de empresa
```

**Referencia visual:** `MatrizRequisitos(1).png`

---

### 7.6 Partidas + Cotizaciones + Costeo

#### Catálogo de Partidas

**Objetivo:** organizar la parte comercial y técnica de cada ítem licitado.

Campos conceptuales:

- partida;
- descripción;
- cantidad;
- unidad;
- requerimiento;
- solución propuesta;
- marca/modelo;
- proveedor;
- cotización;
- costo;
- precio;
- estado.

Filtros útiles:

- sin cotización;
- alto riesgo;
- requiere revisión técnica;
- sin solución propuesta;
- precio histórico;
- cotización vencida.

**Referencia visual:** `Cat_part.png`

#### Detalle de Costeo

**Objetivo:** explicar cómo se construye el costo y precio de una partida.

Conceptos:

- equipo;
- flete;
- seguro;
- ingeniería;
- documentación;
- pruebas;
- servicios;
- otros costos directos;
- margen o markup;
- precio;
- impuestos.

La UI debe mostrar claramente la **provenance** del costo:

- Supplier Quote;
- Cost Book;
- Historical Estimate;
- Manual Override.

Ejemplo:

> **Costo estimado basado en histórico. Falta cotización formal del proveedor.**

#### Regla financiera obligatoria

**Margin ≠ Markup**

Si se utiliza margen:

```text
Precio = Costo / (1 - Margen)
```

Si se utiliza markup:

```text
Precio = Costo × (1 + Markup)
```

La UI nunca debe llamar “margen” a un incremento aplicado sobre costo.

**Referencia visual:** `DetalleCost.png`

---

### 7.7 Gestión de Proveedores

**Objetivo:** apoyar cotizaciones y sourcing sin convertir el primer MVP en un SRM complejo.

Funciones iniciales:

- catálogo de proveedores;
- contacto;
- especialidad/categoría;
- cotizaciones cargadas;
- partidas cotizadas;
- fecha de última cotización;
- documentos relacionados;
- búsqueda y filtros.

Carga de cotizaciones:

```text
Cotización PDF / Excel / Word
          ↓
LicitIA
          ↓
Proveedor
Fecha
Vigencia
Moneda
Partidas
Marca/modelo
Precio
Tiempo de entrega
```

#### Evitar en primer MVP métricas sin fundamento

No congelar todavía:

- estrellas;
- “nivel de cumplimiento 98%”;
- “tiempo de respuesta promedio”;
- ranking automático.

Sólo incorporar métricas cuando su origen y significado estén claramente definidos.

**Referencia visual:** `Proveedores.png`

---

### 7.8 Mi Empresa / Base Documental

**Objetivo:** representar el corpus documental del participante.

Esta experiencia se definirá con mayor profundidad a partir de:

> **Golden Company Pack #001**

Se espera que incluya:

- datos generales;
- legal/corporativo;
- fiscal;
- financiero;
- experiencia;
- personal;
- certificaciones;
- seguridad;
- documentación técnica recurrente;
- documentos vigentes;
- documentos por vencer;
- historial de versiones.

La UI debe ayudar al usuario a saber:

```text
¿Qué tengo?
¿Qué está vigente?
¿Qué está por vencer?
¿Qué documento puedo reutilizar?
¿Qué requisito de esta licitación puede cubrir?
```

---

### 7.9 Propuesta / Cierre de Expediente

**Objetivo:** consolidar el trabajo antes de presentar.

Debe mostrar como mínimo:

- documentos pendientes;
- requisitos sin evidencia;
- incumplimientos;
- revisiones humanas pendientes;
- partidas sin cotizar;
- riesgos;
- propuesta técnica;
- propuesta económica;
- checklist final.

Conceptualmente:

```text
Documentación                 Lista / Pendiente
Requisitos                    Listos / Revisar
Partidas                      Cotizadas / Pendientes
Propuesta técnica             Lista / Pendiente
Propuesta económica           Lista / Pendiente
Riesgos                       X abiertos
```

LicitIA podrá preparar carpetas o documentos, pero no debe presentar automáticamente una licitación.

---

## 8. Relación entre Product UI y arquitectura interna

La Product UI debe desacoplarse de los motores.

```text
PRODUCT UI
────────────────────────────
Documentos
Requisitos
Cumplimiento
Partidas
Cotizaciones
Costeo
Propuesta

            ↓

DOMAIN / ENGINES
────────────────────────────
Document Intelligence
Requirement Engine
Evidence Engine
Compliance Engine
Commercial Engine
Proposal Assembly

            ↓

TRACEABILITY
────────────────────────────
Documents
Pages
Excerpts
Human Decisions
Versions
Relationships
Provenance
```

Los motores pueden evolucionar sin obligar al usuario a aprender nuevos conceptos técnicos.

---

## 9. Diagnóstico técnico

La UI técnica actual no debe eliminarse.

Puede mantenerse en una sección:

```text
Configuración
    ↓
Diagnóstico
```

Ejemplos de información:

- processing status;
- UUID;
- SHA-256;
- OCR;
- classifier version;
- reference version;
- normalized sources;
- chunks;
- corpus audit;
- graph relationships;
- stale analysis;
- engine warnings.

Esta capa será especialmente útil durante pilotos reales cuando un usuario reporte:

> “Este documento no lo entendió.”

---

## 10. Criterios de diseño visual

Las referencias Stitch actuales muestran una dirección adecuada para LicitIA.

Conservar como guía:

- aplicación desktop-first;
- sidebar oscura;
- fondo claro;
- tablas como instrumento principal;
- cards sólo para resumen;
- badges para estados;
- alta densidad de información, pero organizada;
- poco ornamento;
- acciones explícitas;
- evidencia accesible bajo demanda.

No convertir LicitIA en una interfaz centrada en chat.

La IA debe estar **dentro del workflow**, no sustituir el workflow.

Ejemplo:

```text
Carta de fabricante requerida

Estado: Sin evidencia

LicitIA:
No encontré una carta de fabricante
asociada a esta partida.

[Agregar documento]
[Revisar requisito]
```

---

## 11. Referencias visuales oficiales v0.1

### Core Product References

1. `Dashbrd.png`  
   Centro de Licitaciones / Dashboard.

2. `NuevaLicita(1).png`  
   Nueva Licitación / carga y progreso de análisis.

3. `VisorDoctos.png`  
   Visor documental y evidencia.

4. `MatrizRequisitos(1).png`  
   Matriz de requisitos y cumplimiento.

5. `Cat_part.png`  
   Catálogo de partidas.

6. `DetalleCost.png`  
   Detalle de costeo.

### Supporting Product Reference

7. `Proveedores.png`  
   Gestión de proveedores y carga de cotizaciones.

---

## 12. Cómo deben utilizarse los mockups

Cada mockup se considera:

> **REFERENCE ONLY — NOT FINAL UI**

### Conservar

- concepto de workflow;
- jerarquía de información;
- modelo general de interacción;
- densidad;
- organización por tablas, cards y paneles;
- dirección visual desktop.

### No congelar

- labels exactos;
- porcentajes;
- métricas;
- estructura final del sidebar;
- nombres específicos como “Anexo C”;
- scoring de proveedores;
- colores exactos;
- iconografía;
- wording técnico;
- estilos visuales finales.

---

## 13. Qué no se diseñará todavía

Queda explícitamente fuera del Blueprint v0.1:

- RBAC;
- vistas separadas por departamentos;
- workflows de aprobación multiusuario;
- colaboración simultánea;
- comentarios de equipo;
- asignación de tareas;
- permisos granulares;
- proveedor scoring avanzado;
- dashboards ejecutivos multirol;
- UX móvil;
- automatización de presentación final.

Estas decisiones se tomarán después del piloto single-user.

---

## 14. Roadmap de UI

```text
MVP-02 Document Intelligence
             ✅
             ↓
Product UI Blueprint v0.1
             ↓
Golden Company Pack #001
             ↓
Requirement Engine
             ↓
Evidence Engine
             ↓
Company Documentation
             ↓
Compliance Engine
             ↓
Commercial / Proposal Flow
             ↓
Golden Scenario end-to-end
             ↓
Stitch v2
             ↓
Product UI Hardening
             ↓
Piloto single-user
             ↓
Feedback real
             ↓
RBAC / colaboración
```

---

## 15. Criterio para regenerar Stitch

No regenerar la UI definitiva únicamente por completar nuevos motores.

Regenerar **Stitch v2** cuando existan datos y workflows reales de:

- Requirement Engine;
- Evidence Engine;
- Company Documentation;
- Compliance Engine;
- Commercial Engine;
- Proposal flow.

En ese momento el mockup debe reflejar datos reales producidos por LicitIA, no suposiciones visuales.

---

## 16. Criterio UX para el piloto

El primer MVP estará listo para piloto cuando una persona que prepara licitaciones por sí sola pueda:

1. crear una licitación;
2. cargar el corpus documental;
3. entender el expediente;
4. identificar requisitos;
5. revisar fuente y evidencia;
6. identificar documentación faltante;
7. evaluar cumplimiento;
8. gestionar partidas;
9. cargar o asociar cotizaciones;
10. construir costos/precios;
11. revisar riesgos y pendientes;
12. preparar el expediente final;

sin necesitar conocer:

- OCR;
- chunks;
- hashes;
- versions de engines;
- modelos internos;
- relaciones técnicas;
- conceptos de arquitectura.

---

## 17. North Star del producto

> **LicitIA debe convertir un expediente de licitación complejo en una secuencia clara de decisiones, evidencia, pendientes y acciones, manteniendo trazabilidad completa sin obligar al usuario a entender la tecnología que existe debajo.**

Principio complementario:

> **Evidence and traceability underneath; clarity and action on top.**

---

## 18. Estado del Blueprint

**Product UI Blueprint v0.1:** APROBADO COMO GUÍA DE PRODUCTO.

No implica implementación inmediata.

Siguiente pitstop:

> **Golden Company Pack #001 — Synthetic Enterprise Acceptance Corpus**

Después se diseñarán los prompts para Microsoft 365 Copilot para generar la documentación empresarial sintética y su Ground Truth.
