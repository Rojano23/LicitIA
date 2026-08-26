# LicitIA — Domain Model v0.1

## 1. Objetivo

Definir el vocabulario común y las entidades centrales de LicitIA sin acoplar el dominio a una institución específica.

El dominio debe modelar una licitación como un sistema de documentos, eventos, reglas, requisitos, evidencias, partidas, decisiones técnicas y decisiones económicas.

## 2. Agregados principales

### 2.1 Tender

Raíz del procedimiento.

Campos mínimos:

```text
Tender
  id
  external_reference
  title
  institution_profile
  procurement_type
  procedure_type
  status
  publication_date
  submission_deadline
  current_state_version
  analysis_integrity
  created_at
  updated_at
```

Responsabilidades:

- agrupar expediente;
- mantener estado vigente;
- contener eventos;
- contener requisitos y partidas;
- referenciar perfil institucional;
- mostrar integridad del análisis.

### 2.2 TenderDocument

Representa un archivo del expediente.

```text
TenderDocument
  id
  tender_id
  original_filename
  mime_type
  sha256
  page_count
  source_type
  document_role
  processing_status
  current_version_id
```

`document_role` inicial:

- GOVERNING
- PROCEDURAL
- EVALUATION_CRITERIA
- TECHNICAL_SCOPE
- COMMERCIAL_SCOPE
- ECONOMIC_SCOPE
- SUBMISSION_FORM
- EVIDENCE_TEMPLATE
- CONTRACTUAL
- POLICY_REFERENCE
- PROCEDURAL_GUIDE
- INFORMATIVE
- UNKNOWN

### 2.3 DocumentVersion

Un documento puede evolucionar.

```text
DocumentVersion
  id
  document_id
  version_label
  effective_from
  superseded_at
  source_event_id
  is_current
```

### 2.4 DocumentSection

Unidad semántica interna.

```text
DocumentSection
  id
  document_version_id
  heading
  normalized_heading
  page_start
  page_end
  section_type
  extracted_text
```

### 2.5 DocumentReference

Representa una referencia explícita o inferida entre fuentes.

```text
DocumentReference
  id
  source_document_version_id
  source_locator
  target_reference_text
  target_document_id?
  target_section_id?
  relation_type
  resolution_status
  confidence
```

`relation_type`:

- REFERENCES
- MODIFIES
- SUPERSEDES
- COMPLEMENTS
- DEFINES
- IMPLEMENTS
- SUPPORTS

## 3. Procedimiento y estado

### 3.1 TenderEvent

```text
TenderEvent
  id
  tender_id
  event_type
  scheduled_at
  occurred_at
  source_document_id
  status
```

Eventos iniciales:

- PUBLICATION
- INTEREST_REGISTRATION
- SITE_VISIT
- QUESTION_SUBMISSION
- CLARIFICATION_RESPONSE
- AMENDMENT
- PROPOSAL_SUBMISSION
- PROPOSAL_OPENING
- EVALUATION
- AWARD
- CONTRACT_FORMALIZATION

### 3.2 TenderStateSnapshot

Representa el estado vigente reconstruido en un punto del tiempo.

```text
TenderStateSnapshot
  id
  tender_id
  generated_at
  effective_at
  source_event_ids[]
  unresolved_references
  ambiguous_requirements
  missing_documents
  integrity_score
```

## 4. Evaluación y requisitos

### 4.1 EvaluationCriterion

```text
EvaluationCriterion
  id
  tender_id
  domain
  method
  description
  source_locator
  mandatory
```

`domain`:

- ELIGIBILITY
- LEGAL
- COMMERCIAL
- TECHNICAL
- FINANCIAL
- ECONOMIC
- ETHICS_DD
- SSPA
- CONTRACTUAL

`method` inicial:

- BINARY
- PASS_FAIL
- PRICE_BASED
- CUSTOM

### 4.2 Requirement

```text
Requirement
  id
  tender_id
  stable_key
  category
  title
  description
  mandatory
  applicability
  evaluation_method
  criticality
  current_version_id
  review_status
```

### 4.3 RequirementVersion

```text
RequirementVersion
  id
  requirement_id
  normalized_payload
  source_locator
  effective_from
  superseded_at
  origin_event_id
  confidence
```

La versión permite representar cambios por aclaraciones o modificaciones.

### 4.4 Applicability

Estados:

- APPLIES
- DOES_NOT_APPLY
- CONDITIONAL
- UNKNOWN

## 5. Evidencia y cumplimiento

### 5.1 CompanyDocument

Documento reutilizable de la empresa.

```text
CompanyDocument
  id
  company_id
  document_type
  title
  file_reference
  issue_date
  expiration_date
  issuer
  status
```

### 5.2 Evidence

Vincula una fuente a un requisito.

```text
Evidence
  id
  requirement_id
  source_kind
  source_id
  source_locator
  evidence_type
  proposed_by
  confidence
```

`source_kind` puede ser:

- TENDER_DOCUMENT
- COMPANY_DOCUMENT
- PRODUCT_DATASHEET
- SUPPLIER_QUOTE
- CONTRACT
- USER_NOTE

### 5.3 EvidenceAssessment

```text
EvidenceAssessment
  id
  evidence_id
  requirement_id
  assessment_origin
  result
  rationale_summary
  rule_id?
  model_id?
  created_at
```

`assessment_origin`:

- AI
- RULE
- HUMAN

`result`:

- CONFIRMED
- PROBABLE
- INSUFFICIENT
- MISSING
- REJECTED
- REVIEW_REQUIRED

### 5.4 HumanDecision

```text
HumanDecision
  id
  entity_type
  entity_id
  decision_type
  value
  comment
  user_id
  created_at
```

Nunca sobrescribir silenciosamente la salida de IA/regla; la decisión humana se almacena como capa separada.

## 6. Personas, experiencia y certificaciones

### 6.1 CompanyPerson

```text
CompanyPerson
  id
  company_id
  name
  role
  profession
  license_or_id
```

### 6.2 CompanyExperience

```text
CompanyExperience
  id
  company_id
  client
  description
  start_date
  end_date
  technologies[]
  contract_document_id?
  completion_document_id?
```

### 6.3 CompanyCertification

```text
CompanyCertification
  id
  company_id
  certification_type
  certificate_number
  issuer
  issue_date
  expiration_date
  scope
  source_document_id
```

## 7. Partidas y alcance

### 7.1 TenderItem

No depende de que exista un archivo llamado “Anexo C”.

```text
TenderItem
  id
  tender_id
  item_number
  description
  unit
  quantity
  source_locator
  technical_status
  commercial_status
```

### 7.2 TenderItemScope

Una partida puede estar definida en múltiples documentos.

```text
TenderItemScope
  id
  tender_item_id
  scope_type
  description
  source_locator
  mandatory
  applicability
```

`scope_type` ejemplo:

- SERVICE_ACTIVITY
- MATERIAL
- EQUIPMENT
- TOOLING
- LABOR
- ENGINEERING
- DOCUMENTATION
- SSPA
- LOGISTICS
- TESTING
- TRAINING
- OTHER

### 7.3 TechnicalProposal

Permite múltiples alternativas.

```text
TechnicalProposal
  id
  tender_item_id
  alternative_name
  brand
  model
  supplier_id?
  is_primary
  compliance_status
  user_approved
```

## 8. Proveedores y cotizaciones

### 8.1 Supplier

```text
Supplier
  id
  company_name
  contact_name
  currency_preferences
  notes
```

### 8.2 SupplierQuote

```text
SupplierQuote
  id
  supplier_id
  quote_number
  quote_date
  expiration_date
  currency
  source_document_id
  status
```

### 8.3 SupplierQuoteLine

```text
SupplierQuoteLine
  id
  supplier_quote_id
  line_number
  description
  brand
  model
  quantity
  unit
  unit_cost
  total_cost
  lead_time
```

Una línea puede asociarse a una o varias partidas mediante una entidad de matching revisable.

## 9. Costos y precios

### 9.1 CostComponent

```text
CostComponent
  id
  tender_item_id
  scenario_id
  category
  description
  amount
  currency
  source_type
  source_reference_id?
  is_user_override
  note
```

`source_type`:

- CONFIRMED_QUOTE
- HISTORICAL_COST
- SYSTEM_ESTIMATE
- MANUAL_INPUT

### 9.2 PriceScenario

```text
PriceScenario
  id
  tender_id
  name
  scenario_type
  is_active
  is_selected_for_bid
```

`scenario_type`:

- BASE
- AGGRESSIVE
- TARGET
- CONSERVATIVE
- CUSTOM

### 9.3 BidPrice

```text
BidPrice
  id
  tender_item_id
  scenario_id
  unit_price
  total_price
  currency
  pricing_mode
  user_override
```

`pricing_mode`:

- DIRECT_PRICE
- TARGET_MARGIN
- TARGET_MARKUP

### 9.4 Fórmulas

```text
Profit = SellingPrice - Cost
MarginPct = Profit / SellingPrice * 100
MarkupPct = Profit / Cost * 100
```

Los cálculos son deterministas. El valor final ofertado puede ser manual.

## 10. Auditoría

### AuditEvent

```text
AuditEvent
  id
  user_id
  entity_type
  entity_id
  action
  old_value
  new_value
  origin
  reason?
  created_at
```

`origin`:

- HUMAN
- AI
- RULE
- SYSTEM

## 11. Invariantes del dominio

1. Un requisito extraído automáticamente debe tener `SourceLocator`.
2. Un precio estimado no puede etiquetarse como cotización confirmada.
3. Un override humano no elimina el valor previo; lo versiona o audita.
4. El estado final visible debe distinguir evaluación IA, evaluación por reglas y decisión humana.
5. Una partida puede tener múltiples componentes de alcance y múltiples alternativas técnicas.
6. Una cotización no determina por sí sola el precio de venta.
7. El precio final puede ser modificado manualmente en cualquier momento previo al cierre.
8. El porcentaje global de cumplimiento no debe mostrarse sin indicador de integridad del análisis.
9. Una referencia documental no resuelta debe mantenerse como pendiente explícito.
10. Una modificación o aclaración debe poder superseder un requisito anterior sin borrar su historia.

## 12. Relaciones resumidas

```text
Tender
 ├── TenderDocument ── DocumentVersion ── DocumentSection
 │        └── DocumentReference
 ├── TenderEvent
 ├── EvaluationCriterion
 ├── Requirement ── RequirementVersion
 │        └── Evidence ── EvidenceAssessment
 │                       └── HumanDecision
 ├── TenderItem ── TenderItemScope
 │        ├── TechnicalProposal
 │        ├── CostComponent
 │        └── BidPrice
 └── PriceScenario

Company
 ├── CompanyDocument
 ├── CompanyPerson
 ├── CompanyExperience
 └── CompanyCertification

Supplier
 └── SupplierQuote
          └── SupplierQuoteLine
```

## 13. Pendientes para v0.2

No definir todavía sin evidencia de implementación/casos reales:

- taxonomía completa de `Requirement.category`;
- modelo de consorcios;
- contenido nacional detallado;
- reglas de DD por nivel de riesgo;
- unidades y conversión dimensional avanzada;
- asignación de costos comunes a múltiples partidas;
- multiusuario/roles;
- firma y exportaciones finales.
