from __future__ import annotations

import json
import importlib.util
from pathlib import Path

_RUNNER_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_scope_attribute_golden.py"
_RUNNER_SPEC = importlib.util.spec_from_file_location("run_scope_attribute_golden", _RUNNER_PATH)
assert _RUNNER_SPEC is not None and _RUNNER_SPEC.loader is not None
runner = importlib.util.module_from_spec(_RUNNER_SPEC)
_RUNNER_SPEC.loader.exec_module(runner)


class _FakeProvider:
    provider_name = "fake"
    provider_version = "fake-1"
    contract_version = "fake-contract"

    def __init__(self, *, responses: dict[str, list[dict]]) -> None:
        self._responses = responses

    def supports(self, fragment):
        return True

    def discover(self, fragment):
        from app.scope_attribute_semantic_discovery import DiscoveredScopeAttribute

        payload = self._responses.get(fragment.source_locator, [])
        return [DiscoveredScopeAttribute(**item) for item in payload]


def _write_golden(tmp_path: Path, *, mode: str, expected_attributes: list[dict], status: str = "APPROVED") -> str:
    source_text = "MÓDULO DE ENTRADAS ANALÓGICAS, MARCA: YOKOGAWA, MODELO: AA143-H50/K4400"
    payload = {
        "golden_version": "technical-attribute-golden-2026-09-08-001",
        "generated_at": "2026-09-08T00:00:00Z",
        "notes": "test",
        "cases": [
            {
                "case_id": "case-1",
                "golden_version": "technical-attribute-golden-2026-09-08-001",
                "tender_id": "tender-1",
                "scope_detail_id": "scope-1",
                "source_document_id": "doc-1",
                "document_page_id": "page-1",
                "page_number": 1,
                "source_method": "VISION",
                "source_artifact_key": "vision-page-result:1",
                "source_locator": "page:1|detail_row:1",
                "source_text": source_text,
                "source_text_sha256": "a2af11c55f4d526e38de72eac205809fe67f95ca60d0f8ce4cbfddb8be4e167a",
                "evaluation_mode": mode,
                "human_label_status": status,
                "candidate_reason": "test",
                "expected_attributes": expected_attributes,
                "source_contract_version": "v1",
            }
        ],
    }
    path = tmp_path / "golden.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return str(path)


def test_runner_strict_pass(monkeypatch, tmp_path: Path) -> None:
    expected = [
        {
            "golden_attribute_id": "ga-1",
            "attribute_name": "brand",
            "value_raw": "YOKOGAWA",
            "evidence_excerpt": "MARCA: YOKOGAWA",
            "attribute_label_raw": "MARCA",
            "relation": "UNSPECIFIED",
        }
    ]
    path = _write_golden(tmp_path, mode="STRICT", expected_attributes=expected)

    monkeypatch.setattr(
        runner,
        "validate_technical_attribute_golden",
        lambda dataset, parent_resolver=None: type(
            "Validation",
            (),
            {"is_valid": True, "pending_count": 0, "errors": ()},
        )(),
    )

    exit_code = runner.run_golden(
        golden_path=path,
        model_name="fake-model",
        provider_factory=lambda model_name: _FakeProvider(
            responses={
                "page:1|detail_row:1": [
                    {
                        "attribute_name": "brand",
                        "value_raw": "YOKOGAWA",
                        "evidence_excerpt": "MARCA: YOKOGAWA",
                        "attribute_label_raw": "MARCA",
                        "unit_raw": None,
                        "relation": "UNSPECIFIED",
                        "confidence": None,
                    }
                ]
            }
        ),
    )

    assert exit_code == 0


def test_runner_no_attributes_false_positive_fails(monkeypatch, tmp_path: Path) -> None:
    path = _write_golden(tmp_path, mode="NO_ATTRIBUTES", expected_attributes=[])

    monkeypatch.setattr(
        runner,
        "validate_technical_attribute_golden",
        lambda dataset, parent_resolver=None: type(
            "Validation",
            (),
            {"is_valid": True, "pending_count": 0, "errors": ()},
        )(),
    )

    exit_code = runner.run_golden(
        golden_path=path,
        model_name="fake-model",
        provider_factory=lambda model_name: _FakeProvider(
            responses={
                "page:1|detail_row:1": [
                    {
                        "attribute_name": "brand",
                        "value_raw": "YOKOGAWA",
                        "evidence_excerpt": "MARCA: YOKOGAWA",
                        "attribute_label_raw": "MARCA",
                        "unit_raw": None,
                        "relation": "UNSPECIFIED",
                        "confidence": None,
                    }
                ]
            }
        ),
    )

    assert exit_code == 5


def test_runner_invalid_output_propagates(monkeypatch, tmp_path: Path) -> None:
    expected = [
        {
            "golden_attribute_id": "ga-1",
            "attribute_name": "brand",
            "value_raw": "YOKOGAWA",
            "evidence_excerpt": "MARCA: YOKOGAWA",
            "relation": "UNSPECIFIED",
        }
    ]
    path = _write_golden(tmp_path, mode="STRICT", expected_attributes=expected)

    monkeypatch.setattr(
        runner,
        "validate_technical_attribute_golden",
        lambda dataset, parent_resolver=None: type(
            "Validation",
            (),
            {"is_valid": True, "pending_count": 0, "errors": ()},
        )(),
    )

    class _InvalidProvider(_FakeProvider):
        def discover(self, fragment):
            raise ValueError("synthetic invalid output")

    exit_code = runner.run_golden(
        golden_path=path,
        model_name="fake-model",
        provider_factory=lambda model_name: _InvalidProvider(responses={}),
    )

    assert exit_code == 4


def test_runner_pending_labels_stop_with_code_3(monkeypatch, tmp_path: Path) -> None:
    expected = [
        {
            "golden_attribute_id": "ga-1",
            "attribute_name": "brand",
            "value_raw": "YOKOGAWA",
            "evidence_excerpt": "MARCA: YOKOGAWA",
            "relation": "UNSPECIFIED",
        }
    ]
    path = _write_golden(tmp_path, mode="STRICT", expected_attributes=expected, status="PENDING")

    monkeypatch.setattr(
        runner,
        "validate_technical_attribute_golden",
        lambda dataset, parent_resolver=None: type(
            "Validation",
            (),
            {"is_valid": True, "pending_count": 1, "errors": ()},
        )(),
    )

    exit_code = runner.run_golden(
        golden_path=path,
        model_name="fake-model",
        provider_factory=lambda model_name: _FakeProvider(responses={}),
    )

    assert exit_code == 3


def test_build_fragment_preserves_source_method() -> None:
    from app.scope_attribute_golden import GoldenExpectedAttribute

    case = runner.GoldenCase(
        case_id="x",
        golden_version="v",
        tender_id="t",
        scope_detail_id="s",
        source_document_id="d",
        document_page_id="p",
        page_number=4,
        source_method="OCR",
        source_artifact_key="k",
        source_locator="page:4|detail_row:0",
        source_text="TXT",
        source_text_sha256="c6f4d8969f9f77955100514edc4ad43f73a822c4868d8beac959664f6b1f4ef5",
        evaluation_mode="NO_ATTRIBUTES",
        human_label_status="APPROVED",
        expected_attributes=(
            GoldenExpectedAttribute(
                golden_attribute_id="ga-1",
                attribute_name="brand",
                value_raw="ACME",
                evidence_excerpt="ACME",
            ),
        ),
        candidate_reason="reason",
        source_contract_version="v1",
    )

    fragment = runner.build_fragment(case)

    assert fragment.source_method == "OCR"
    assert fragment.scope_detail_id == "s"
