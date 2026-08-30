# Golden Company 001 Fixture Manifest

Purpose: deterministic acceptance corpus for MVP-05.7 integrated acceptance.
Nature: fully fictional test data; not production data and not tied to any real legal entity.

## Company Identity
- Name: GOLDEN INDUSTRIAL SERVICES, S.A. DE C.V.
- RFC: GIS260101AB1

## Fixture Files and Intended Evidence Families
- GC001_01_CORPORATE_EXISTENCE_BASE.txt -> CORPORATE_EXISTENCE
- GC001_02_LEGAL_AUTHORITY_BASE.txt -> LEGAL_AUTHORITY
- GC001_03_TAX_REGISTRATION_BASE.txt -> TAX_REGISTRATION
- GC001_04_TAX_COMPLIANCE_BASE.txt -> TAX_COMPLIANCE
- GC001_05_SOCIAL_SECURITY_BASE.txt -> SOCIAL_SECURITY_COMPLIANCE
- GC001_06_HIIP_REGISTRATION_BASE.txt -> REGISTRATION
- GC001_07_ISO9001_BASE.txt -> CERTIFICATION (ISO 9001:2015)
- GC001_08_PERSONNEL_CV_BASE.txt -> PERSONNEL_QUALIFICATION
- GC001_09_PERSONNEL_MANUFACTURER_CERT_BASE.txt -> PERSONNEL_QUALIFICATION
- GC001_10_EXPERIENCE_SERVICE_01_BASE.txt -> EXPERIENCE
- GC001_11_EXPERIENCE_SERVICE_02_BASE.txt -> EXPERIENCE

## Intentional Omissions
- No manufacturer support-letter fixture is included on purpose.
- This omission is used to validate missing-evidence behavior in the compliance matrix.

## Golden Tender Controls Exercised
- Positive controls: ISO 9001, HIIP registration, personnel, and experience evidence.
- Mixed-state controls: direct verification requirements and conditional applicability requirements.
- Negative control: manufacturer support letter remains without company evidence by design.

## How To Run Automated Acceptance
- Run: `DATABASE_URL='postgresql+psycopg://ceciliavalencia@localhost:5432/licitia_test' LICITIA_DATA_DIR='/Users/ceciliavalencia/LiticIA/backend/.licitia-data-test' /Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m pytest backend/tests/test_mvp05_integrated_acceptance.py -q`

## How To Seed Dev Acceptance Data
- Run: `cd /Users/ceciliavalencia/LiticIA/backend && DATABASE_URL='postgresql+psycopg://ceciliavalencia@localhost:5432/licitia_dev' LICITIA_DATA_DIR='/Users/ceciliavalencia/LiticIA/backend/.licitia-data' /Users/ceciliavalencia/LiticIA/backend/.venv/bin/python scripts/seed_golden_company_001.py`
- Optional evidence analysis only: add `--analyze-evidence`.
- The seed script never approves evidence, never confirms matches, and never creates compliance decisions.
