# LicitIA Backend — Codex Instructions

These instructions supplement the repository-root AGENTS.md for backend work.

## Backend environment

Repository:

/Users/ceciliavalencia/LiticIA

Backend:

/Users/ceciliavalencia/LiticIA/backend

MANDATORY Python interpreter:

/Users/ceciliavalencia/LiticIA/backend/.venv/bin/python

DO NOT use:

/Users/ceciliavalencia/LiticIA/.venv/bin/python

Do not rely on whichever virtual environment happens to be activated in the
VS Code terminal.

For reproducible validation, prefer the absolute backend interpreter path.

Do not substitute bare:

python
pytest
.venv/bin/python
.venv/bin/pytest

when the task provides or requires the mandatory absolute interpreter.

## Databases

Development database:

postgresql+psycopg://ceciliavalencia@localhost:5432/licitia_dev

Test database:

postgresql+psycopg://ceciliavalencia@localhost:5432/licitia_test

Use licitia_test for automated tests, controlled Golden fixtures and synthetic
validation unless the task explicitly specifies otherwise.

Never run test fixtures against licitia_dev.

Real Golden/model experiments may use licitia_dev only when explicitly
specified by the task.

## Schema management

Alembic is the schema authority.

Never use SQLAlchemy create_all as a substitute for migrations.

Do not create a migration unless the requested schema change actually requires
one.

When migrations are relevant, verify Alembic state with the mandatory backend
Python interpreter.

Current accepted migration head may change over time; inspect Alembic rather
than assuming an old value unless the task provides an expected revision.

## Python / backend stack

Primary backend stack:

- FastAPI
- SQLAlchemy 2
- Pydantic 2
- PostgreSQL
- Alembic

Follow existing repository conventions before introducing a new abstraction.

Reuse existing public contracts and helpers when possible.

Do not duplicate resolver, normalization, materialization or projection logic
inside test/Golden evaluators.

## Persistence and provenance

Do not store document binaries as database blobs unless explicitly required by
architecture.

Preserve source-document/page/artifact/locator provenance according to the
existing domain contracts.

A deterministic or semantic candidate is not automatically a trusted
contractual fact.

Respect review_required and equivalent fail-closed states.

## Source Effect rules

Resolution and projection engines are deterministic decision layers.

Provider/discovery code may propose evidence-backed candidates but must not
silently establish contractual precedence.

Later document date, filename, upload order or revision wording alone must not
be treated as precedence unless explicitly supported by the accepted domain
contract.

Trusted resolution must continue to respect:

- document-wide versus partial scope
- conflict detection
- cycles
- superseded acting sources
- no-revival behavior
- unresolved targets
- review propagation
- traceability of supporting/blocking effects

Do not weaken these rules to improve test or Golden pass rates.

## Source Effect semantic provider policy

The Qwen/Ollama Source Effect provider is experimental and is NOT part of the
automatic MVP runtime path.

Do not automatically call it from production materialization/discovery.

Do not remove the bounded-provider implementation unless explicitly requested.

## Real Ollama/model runs

DO NOT run real Ollama or real qwen models from Codex / VS Code unless the user
explicitly authorizes that exact run.

For real model Golden/calibration runs, the established preferred workflow is
for the user to execute the exact command from the normal macOS Terminal.

If a task requires a real-model run and it has not explicitly authorized Codex
to execute it:

STOP after deterministic/mock validation and provide the exact macOS Terminal
command for the user.

Do not substitute mocks as evidence of real-model quality.

## Tests

Use the mandatory interpreter:

/Users/ceciliavalencia/LiticIA/backend/.venv/bin/python -m pytest

Start with the smallest relevant tests.

Run cross-domain regressions only when the production surface can affect those
domains, unless the task explicitly requires broader validation.

If only new evaluation/runner/test files are added and no shared production
module changes, do not automatically rerun unrelated Requirements or Scope
families.

If shared resolver/projection/domain behavior changes, expand regression
coverage accordingly.

Never replace an explicitly requested test list with a glob unless the task
allows it.

## Golden datasets

Human/Frozen Golden datasets are read-only unless the task explicitly
authorizes modification.

Do not tune implementation against blind validation data.

Controlled synthetic contract Goldens must clearly identify themselves as
synthetic/contract validation and must not be presented as real-world recall
certification.

Golden evaluators should:

- use real public production APIs;
- avoid duplicating business logic;
- normalize only unstable incidental identifiers;
- preserve meaningful conflicts and diagnostics;
- be deterministic and idempotent;
- leave production resolvers read-only.

## Compile / quality

When backend Python code changes, a typical compile check is:

/Users/ceciliavalencia/LiticIA/backend/.venv/bin/python \
-m compileall -q \
/Users/ceciliavalencia/LiticIA/backend/app \
/Users/ceciliavalencia/LiticIA/backend/scripts \
/Users/ceciliavalencia/LiticIA/backend/tests

Use git diff --check before handoff.

## Handoff

At completion, report:

- exact files created/modified;
- production behavior changed or not;
- tests and exact counts;
- Alembic status when relevant;
- compile result when relevant;
- git diff --check;
- any unexecuted real-model validation;
- blockers.

Do not commit or push unless explicitly instructed.