from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path

_RUNNER_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_scope_quantity_golden.py"
_RUNNER_SPEC = importlib.util.spec_from_file_location("run_scope_quantity_golden", _RUNNER_PATH)
assert _RUNNER_SPEC is not None and _RUNNER_SPEC.loader is not None
runner = importlib.util.module_from_spec(_RUNNER_SPEC)
_RUNNER_SPEC.loader.exec_module(runner)


class _FakeProvider:
    provider_name = "fake"
    provider_version = "fake-v1"
    contract_version = "fake-contract"

    def __init__(self, *, responses: dict[str, list[dict]]) -> None:
        self.responses = responses

    def supports(self, fragment):
        return True

    def discover(self, fragment):
        from app.scope_quantity_semantic_discovery import DiscoveredScopeQuantity, ScopeQuantityProviderDiscoveryPayload

        payload = [DiscoveredScopeQuantity(**item) for item in self.responses.get(fragment.source_locator, [])]
        status = "DISCOVERED" if payload else "NO_QUANTITIES"
        return ScopeQuantityProviderDiscoveryPayload(status=status, quantities=tuple(payload), errors=())


def _write_golden(tmp_path: Path, *, mode: str, pending: bool, expected: list[dict]) -> str:
    source_text = "• MÓDULO X, MODELO: PW481-50 (1 PIEZA), ENTRADA 100-120VCA"
    payload = {
        "golden_version": "scope-quantity-golden-2026-09-08-001",
        "generated_at": "2026-09-08T00:00:00Z",
        "notes": "test",
        "cases": [
            {
                "case_id": "sq_case_001",
                "golden_version": "scope-quantity-golden-2026-09-08-001",
                "human_label_status": "PENDING" if pending else "APPROVED",
                "evaluation_mode": mode,
                "tender_id": "tender-1",
                "scope_detail_id": "scope-1",
                "source_document_id": "doc-1",
                "document_page_id": "page-1",
                "page_number": 4,
                "source_method": "VISION",
                "source_artifact_key": "vision-page-result:1",
                "source_locator": "page:4|detail_row:0",
                "source_text": source_text,
                "source_text_sha256": "689d88e603a69d8a762166cfb24d5dcb10ef8f95f2552ae35a06cbca84ac7b43",
                "source_contract_version": "vision-detail-transcription-2026-08-31-001",
                "source_analysis_id": "analysis-1",
                "source_page_result_id": "page-result-1",
                "expected_quantities": expected,
                "forbidden_quantity_literals": ["100-120VCA", "PW481-50"],
                "coverage_tags": ["COUNT", "MIXED_TECHNICAL_NUMBER"],
                "candidate_reason": "test",
            }
        ],
    }
    path = tmp_path / "scope_quantity_golden.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return str(path)


def test_runner_pending_labels_block_execution(monkeypatch, tmp_path: Path) -> None:
    path = _write_golden(
        tmp_path,
        mode="STRICT",
        pending=True,
        expected=[
            {
                "golden_quantity_id": "gq-001",
                "quantity_raw": "1",
                "unit_raw": "PIEZA",
                "measure_kind": "COUNT",
                "relation": "EXACT",
                "quantity_value_raw": "1",
                "quantity_min_raw": None,
                "quantity_max_raw": None,
                "evidence_excerpt": "(1 PIEZA)",
            }
        ],
    )

    monkeypatch.setattr(
        runner,
        "validate_scope_quantity_golden",
        lambda dataset, parent_resolver=None: type(
            "Validation", (), {"is_valid": True, "pending_count": 1, "approved_count": 0, "errors": ()}
        )(),
    )

    exit_code = runner.run_golden(golden_path=path, model_name="fake-model", provider_factory=lambda **_: _FakeProvider(responses={}))
    assert exit_code == 3


def test_runner_all_approved_fake_discovered_pass(monkeypatch, tmp_path: Path) -> None:
    path = _write_golden(
        tmp_path,
        mode="STRICT",
        pending=False,
        expected=[
            {
                "golden_quantity_id": "gq-001",
                "quantity_raw": "1",
                "unit_raw": "PIEZA",
                "measure_kind": "COUNT",
                "relation": "EXACT",
                "quantity_value_raw": "1",
                "quantity_min_raw": None,
                "quantity_max_raw": None,
                "evidence_excerpt": "(1 PIEZA)",
            }
        ],
    )

    monkeypatch.setattr(
        runner,
        "validate_scope_quantity_golden",
        lambda dataset, parent_resolver=None: type(
            "Validation", (), {"is_valid": True, "pending_count": 0, "approved_count": 1, "errors": ()}
        )(),
    )

    fake = _FakeProvider(
        responses={
            "page:4|detail_row:0": [
                {
                    "quantity_raw": "1",
                    "unit_raw": "PIEZA",
                    "measure_kind": "COUNT",
                    "relation": "EXACT",
                    "quantity_value_raw": "1",
                    "quantity_min_raw": None,
                    "quantity_max_raw": None,
                    "evidence_excerpt": "(1 PIEZA)",
                    "confidence": 0.9,
                }
            ]
        }
    )

    exit_code = runner.run_golden(golden_path=path, model_name="fake-model", provider_factory=lambda **_: fake)
    assert exit_code == 0


def test_runner_invalid_golden_blocks(monkeypatch, tmp_path: Path) -> None:
    path = _write_golden(tmp_path, mode="STRICT", pending=False, expected=[])

    monkeypatch.setattr(
        runner,
        "validate_scope_quantity_golden",
        lambda dataset, parent_resolver=None: type(
            "Validation", (), {"is_valid": False, "pending_count": 0, "approved_count": 0, "errors": ("x",)}
        )(),
    )

    exit_code = runner.run_golden(golden_path=path, model_name="fake-model", provider_factory=lambda **_: _FakeProvider(responses={}))
    assert exit_code == 2


def test_runner_parent_recovery_failure_blocks(monkeypatch, tmp_path: Path) -> None:
    path = _write_golden(tmp_path, mode="STRICT", pending=False, expected=[])

    monkeypatch.setattr(
        runner,
        "validate_scope_quantity_golden",
        lambda dataset, parent_resolver=None: type(
            "Validation",
            (),
            {"is_valid": False, "pending_count": 0, "approved_count": 0, "errors": ("scope_detail not found",)},
        )(),
    )

    exit_code = runner.run_golden(golden_path=path, model_name="fake-model", provider_factory=lambda **_: _FakeProvider(responses={}))
    assert exit_code == 2


def test_runner_fake_no_quantities_pass(monkeypatch, tmp_path: Path) -> None:
    path = _write_golden(tmp_path, mode="NO_QUANTITIES", pending=False, expected=[])

    monkeypatch.setattr(
        runner,
        "validate_scope_quantity_golden",
        lambda dataset, parent_resolver=None: type(
            "Validation", (), {"is_valid": True, "pending_count": 0, "approved_count": 1, "errors": ()}
        )(),
    )

    exit_code = runner.run_golden(golden_path=path, model_name="fake-model", provider_factory=lambda **_: _FakeProvider(responses={}))
    assert exit_code == 0


def test_runner_help_via_module_execution() -> None:
    backend_dir = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [
            str(backend_dir / ".venv" / "bin" / "python"),
            "-m",
            "scripts.run_scope_quantity_golden",
            "--help",
        ],
        cwd=str(backend_dir),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "Run deterministic scope quantity Golden evaluation" in result.stdout
