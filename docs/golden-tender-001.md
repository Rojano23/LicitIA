# Golden Tender #001 — SNR-CAD-265-CA-S-2026

## 1. Propósito

Golden Tender #001 es el primer expediente real de referencia para validar LicitIA.

No es una plantilla rígida ni una fuente de excepciones hardcodeadas. Se utiliza para:

- validar el modelo de dominio;
- probar Engines;
- crear expectativas funcionales;
- detectar regresiones;
- descubrir qué conocimiento pertenece al Core, al PEMEX Profile o al Domain Playbook.

## 2. Procedimiento

**Referencia:** `SNR-CAD-265-CA-S-2026`  
**Objeto:** servicios de mantenimiento preventivo a sistemas de control distribuido Yokogawa instalados en MTBE 1 y Planta de Asfaltos de Refinería Cadereyta.

## 3. Familias documentales observadas

El expediente de referencia contiene:

- convocatoria;
- bases;
- paquete de anexos/formularios/criterios;
- anexos técnicos;
- anexos de seguridad;
- catálogo de conceptos;
- programa;
- maquinaria/equipo;
- materiales;
- políticas y guías complementarias.

## 4. Capacidades que debe probar

### 4.1 Clasificación

LicitIA debe poder distinguir al menos:

- reglas del procedimiento;
- criterios de evaluación;
- formatos de presentación;
- alcance técnico;
- catálogo de partidas;
- SSPA;
- documentos informativos/procedurales.

### 4.2 Referencias

Debe poder resolver referencias semánticas como:

- Anexo B;
- B-1;
- B-4;
- B-5;
- Anexo C;
- DT-4;
- Sección VIII.1;
- D-1/D-3/D-4/D-5;
- Formato 4.

### 4.3 Evaluación

Debe reconocer que existen criterios separados de evaluación comercial, técnica y económica, y que varios utilizan lógica binaria o cumple/no cumple.

### 4.4 Requisitos técnicos de ejemplo

El expediente contiene requisitos sobre:

- experiencia en sistemas Centum VP / ProSafe RS;
- cantidad mínima de servicios/contratos;
- antigüedad máxima de experiencia;
- personal y perfiles;
- certificados de capacitación/fabricante;
- ISO 9001:2015;
- carta de respaldo del fabricante;
- maquinaria/equipo;
- materiales;
- SSPA.

### 4.5 Partidas

El catálogo contiene partidas que no deben interpretarse como alcance completo por sí solas.

LicitIA debe demostrar que una partida puede requerir componentes de alcance distribuidos en otros anexos.

### 4.6 Economía

Debe mantener separados:

- estructura oficial de propuesta económica;
- costos internos;
- cotizaciones;
- precio final decidido por usuario.

## 5. Golden Assertions

Estas expectativas se convertirán gradualmente en fixtures de prueba. No fijar números definitivos hasta ejecutar la primera fase de extracción real.

### Assertions iniciales

1. El expediente contiene más de una familia documental.
2. Existen criterios explícitos de evaluación comercial, técnica y económica.
3. Existen requisitos que requieren evidencia documental de la empresa.
4. Existen referencias cruzadas entre bases, formatos y anexos.
5. Existe al menos un catálogo de partidas/conceptos.
6. El alcance de una partida depende de documentos adicionales.
7. Existen documentos complementarios que no deben convertirse íntegramente en requisitos.
8. La aplicabilidad de obligaciones SSPA requiere interpretación contextual.
9. La propuesta económica debe poder construirse sin que el sistema decida el precio final.
10. Las salidas deben conservar fuente documental.

## 6. Estrategia de regresión

Para cada versión del Engine registrar:

```text
Input fixture version
Engine version
Model/provider version
Extraction metrics
Document classifications
Resolved references
Unresolved references
Requirements extracted
Ambiguous requirements
Tender items detected
Human-reviewed corrections
```

La meta no es que un modelo produzca siempre idéntico texto, sino que preserve resultados estructurales y trazabilidad dentro de tolerancias definidas.

## 7. Regla anti-hardcode

Está prohibido:

```text
if filename == "ANEXO C.pdf": treat_as_tender_item_catalog
```

Permitido:

```text
classify document by semantic role
+ use PEMEX Profile hints
+ require evidence/source
```

Golden Tender debe validar generalidad, no provocar excepciones específicas.

## 8. Evolución

Cuando LicitIA Core + PEMEX Profile v1 funcionen con este expediente, incorporar un segundo Golden Tender PEMEX de objeto distinto antes de declarar estable el Profile.

Después, probar una licitación CFE **sin adaptación previa** para medir qué parte del Core generaliza y qué requiere `CFE Profile v1`.
