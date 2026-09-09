from __future__ import annotations

import json
from contextlib import nullcontext
from dataclasses import dataclass
from pathlib import Path

from app.source_effect_semantic_discovery import (
    DiscoveredSourceEffect,
    SourceEffectSemanticDiscoveryResult,
)
from scripts.run_source_effect_semantic_golden import run_semantic_golden


@dataclass(frozen=True, slots=True)
class _FakeRun:
    provider_name: str
    provider_version: str
    contract_version: str
    raw_model_json: str | None
    elapsed_time_ms: int
    result: SourceEffectSemanticDiscoveryResult


class _FakeProvider:
    provider_name = "Fake Source Effect Provider"
    provider_version = "fake-source-effect-001"
    contract_version = "fake-source-effect-contract-001"

    def __init__(self, *, model_name: str) -> None:
        self.model_name = model_name


def _backend_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _result(
    *,
    status: str,
    effects: tuple[DiscoveredSourceEffect, ...] = (),
    diagnostics: tuple[str, ...] = (),
    errors: tuple[str, ...] = (),
) -> SourceEffectSemanticDiscoveryResult:
    return SourceEffectSemanticDiscoveryResult(
        provider_name="Fake Source Effect Provider",
        provider_version="fake-source-effect-001",
        contract_version="fake-source-effect-contract-001",
        status=status,
        candidate_count=len(effects),
        review_required_count=len(effects) if status == "REVIEW_REQUIRED" else 0,
        candidates=(),
        discovered_effects=effects,
        diagnostics=diagnostics,
        errors=errors,
    )


def _effect(
    *,
    effect_type: str,
    effect_scope: str,
    affected_document_ref_raw: str | None,
    affected_locator_raw: str | None,
    evidence_excerpt: str,
) -> DiscoveredSourceEffect:
    return DiscoveredSourceEffect(
        effect_type=effect_type,
        effect_scope=effect_scope,
        affected_document_ref_raw=affected_document_ref_raw,
        affected_locator_raw=affected_locator_raw,
        effective_date_raw=None,
        evidence_excerpt=evidence_excerpt,
        confidence=0.9,
    )


def test_frozen_golden_is_accepted_for_certification_mode() -> None:
    backend_root = _backend_root()

    def discovery_runner(db, fragment, *, provider):
        status = "REVIEW_REQUIRED" if "ciso i. Se modifica el inciso" in fragment.source_text else "NO_EFFECTS"
        return _FakeRun(
            provider_name=provider.provider_name,
            provider_version=provider.provider_version,
            contract_version=provider.contract_version,
            raw_model_json=None,
            elapsed_time_ms=5,
            result=_result(status=status),
        )

    code, report = run_semantic_golden(
        golden_path=str(backend_root / "evals/source_effect_golden_v1.json"),
        model_name="qwen3:8b",
        provider_factory=_FakeProvider,
        discovery_runner=discovery_runner,
        session_factory=lambda: nullcontext(object()),
    )

    assert code == 0
    assert report is not None
    assert report["dataset"]["dataset_status"] == "FROZEN_LIMITED_COVERAGE"
    assert report["dataset"]["label_status"] == "HUMAN_APPROVED"


def test_proposed_candidate_dataset_is_rejected_in_certification_mode() -> None:
    backend_root = _backend_root()

    def discovery_runner(db, fragment, *, provider):
        return _FakeRun(
            provider_name=provider.provider_name,
            provider_version=provider.provider_version,
            contract_version=provider.contract_version,
            raw_model_json=None,
            elapsed_time_ms=5,
            result=_result(status="NO_EFFECTS"),
        )

    code, report = run_semantic_golden(
        golden_path=str(backend_root / "evals/source_effect_golden_candidate_t001_v1.json"),
        model_name="qwen3:8b",
        provider_factory=_FakeProvider,
        discovery_runner=discovery_runner,
        session_factory=lambda: nullcontext(object()),
    )

    assert code == 2
    assert report is None


def test_integrity_mismatch_is_rejected(tmp_path: Path) -> None:
    backend_root = _backend_root()
    payload = json.loads((backend_root / "evals/source_effect_golden_v1.json").read_text(encoding="utf-8"))
    payload["integrity_sha256"] = "mismatch"

    golden_with_mismatch = tmp_path / "source_effect_integrity_mismatch.json"
    golden_with_mismatch.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def discovery_runner(db, fragment, *, provider):
        return _FakeRun(
            provider_name=provider.provider_name,
            provider_version=provider.provider_version,
            contract_version=provider.contract_version,
            raw_model_json=None,
            elapsed_time_ms=5,
            result=_result(status="NO_EFFECTS"),
        )

    code, report = run_semantic_golden(
        golden_path=str(golden_with_mismatch),
        model_name="qwen3:8b",
        provider_factory=_FakeProvider,
        discovery_runner=discovery_runner,
        session_factory=lambda: nullcontext(object()),
    )

    assert code == 2
    assert report is None


def test_expected_answers_are_not_leaked_to_provider_input() -> None:
    backend_root = _backend_root()
    observed_fragments: list[object] = []

    def discovery_runner(db, fragment, *, provider):
        observed_fragments.append(fragment)
        assert not hasattr(fragment, "expected_effects")
        assert not hasattr(fragment, "human_note")
        assert not hasattr(fragment, "category")
        return _FakeRun(
            provider_name=provider.provider_name,
            provider_version=provider.provider_version,
            contract_version=provider.contract_version,
            raw_model_json=None,
            elapsed_time_ms=5,
            result=_result(status="NO_EFFECTS"),
        )

    code, report = run_semantic_golden(
        golden_path=str(backend_root / "evals/source_effect_golden_v1.json"),
        model_name="qwen3:8b",
        provider_factory=_FakeProvider,
        discovery_runner=discovery_runner,
        session_factory=lambda: nullcontext(object()),
    )

    assert code == 0
    assert report is not None
    assert observed_fragments


def test_review_required_positive_cases_are_scored_as_semantic_positives() -> None:
    backend_root = _backend_root()

    def discovery_runner(db, fragment, *, provider):
        if "ciso i. Se modifica el inciso" in fragment.source_text:
            return _FakeRun(
                provider_name=provider.provider_name,
                provider_version=provider.provider_version,
                contract_version=provider.contract_version,
                raw_model_json=None,
                elapsed_time_ms=10,
                result=_result(
                    status="REVIEW_REQUIRED",
                    effects=(
                        _effect(
                            effect_type="AMENDS",
                            effect_scope="PARTIAL",
                            affected_document_ref_raw=None,
                            affected_locator_raw="inciso i",
                            evidence_excerpt="ciso i. Se modifica el inciso, para precisar los alcances y responsabilidades del Area",
                        ),
                    ),
                ),
            )
        if "Apartado 3.1.5. Aplicación y Desarrollo de la Debida Diligencia" in fragment.source_text:
            return _FakeRun(
                provider_name=provider.provider_name,
                provider_version=provider.provider_version,
                contract_version=provider.contract_version,
                raw_model_json=None,
                elapsed_time_ms=12,
                result=_result(
                    status="REVIEW_REQUIRED",
                    effects=(
                        _effect(
                            effect_type="AMENDS",
                            effect_scope="PARTIAL",
                            affected_document_ref_raw=None,
                            affected_locator_raw="Apartado 3.1.5",
                            evidence_excerpt="Apartado 3.1.5. Aplicación y Desarrollo de la Debida Diligencia a los",
                        ),
                        _effect(
                            effect_type="CLARIFIES",
                            effect_scope="PARTIAL",
                            affected_document_ref_raw=None,
                            affected_locator_raw="Disposiciones Transitorias",
                            evidence_excerpt="Disposiciones Transitorias. Se precisa la entrada en vigor y se",
                        ),
                    ),
                ),
            )

        return _FakeRun(
            provider_name=provider.provider_name,
            provider_version=provider.provider_version,
            contract_version=provider.contract_version,
            raw_model_json=None,
            elapsed_time_ms=4,
            result=_result(status="NO_EFFECTS"),
        )

    code, report = run_semantic_golden(
        golden_path=str(backend_root / "evals/source_effect_golden_v1.json"),
        model_name="qwen3:8b",
        provider_factory=_FakeProvider,
        discovery_runner=discovery_runner,
        session_factory=lambda: nullcontext(object()),
    )

    assert code == 0
    assert report is not None
    aggregate = report["aggregate_metrics"]
    assert aggregate["positive_case_count"] == 2
    assert aggregate["expected_effect_count"] == 3
    assert aggregate["matched_effect_count"] == 3
    assert aggregate["review_expected"] == 2
    assert aggregate["review_correctly_surfaced"] == 2
    assert aggregate["review_missed"] == 0

    case_011 = next(item for item in report["cases"] if item["case_id"] == "se_gc_011")
    assert case_011["expected_effect_count"] == 2
    assert case_011["matched_effect_count"] == 2
    assert len(case_011["matched_effects"]) == 2


def test_negative_false_positive_is_counted() -> None:
    backend_root = _backend_root()

    def discovery_runner(db, fragment, *, provider):
        if "MODIFICACIONES CONTRACTUALES" in fragment.source_text:
            return _FakeRun(
                provider_name=provider.provider_name,
                provider_version=provider.provider_version,
                contract_version=provider.contract_version,
                raw_model_json=None,
                elapsed_time_ms=7,
                result=_result(
                    status="DISCOVERED",
                    effects=(
                        _effect(
                            effect_type="AMENDS",
                            effect_scope="PARTIAL",
                            affected_document_ref_raw="Anexo 1",
                            affected_locator_raw=None,
                            evidence_excerpt="MODIFICACIONES CONTRACTUALES",
                        ),
                    ),
                ),
            )
        status = "REVIEW_REQUIRED" if "ciso i. Se modifica el inciso" in fragment.source_text else "NO_EFFECTS"
        return _FakeRun(
            provider_name=provider.provider_name,
            provider_version=provider.provider_version,
            contract_version=provider.contract_version,
            raw_model_json=None,
            elapsed_time_ms=5,
            result=_result(status=status),
        )

    code, report = run_semantic_golden(
        golden_path=str(backend_root / "evals/source_effect_golden_v1.json"),
        model_name="qwen3:8b",
        provider_factory=_FakeProvider,
        discovery_runner=discovery_runner,
        session_factory=lambda: nullcontext(object()),
    )

    assert code == 0
    assert report is not None
    assert report["aggregate_metrics"]["false_positive_effect_count"] >= 1


def test_grounding_and_contract_failures_are_counted() -> None:
    backend_root = _backend_root()

    def discovery_runner(db, fragment, *, provider):
        if "ciso i. Se modifica el inciso" in fragment.source_text:
            return _FakeRun(
                provider_name=provider.provider_name,
                provider_version=provider.provider_version,
                contract_version=provider.contract_version,
                raw_model_json=None,
                elapsed_time_ms=5,
                result=_result(
                    status="REVIEW_REQUIRED",
                    effects=(
                        _effect(
                            effect_type="AMENDS",
                            effect_scope="PARTIAL",
                            affected_document_ref_raw=None,
                            affected_locator_raw="inciso i",
                            evidence_excerpt="texto no presente en el source excerpt",
                        ),
                    ),
                ),
            )
        if "Apartado 3.1.5. Aplicación y Desarrollo de la Debida Diligencia" in fragment.source_text:
            return _FakeRun(
                provider_name=provider.provider_name,
                provider_version=provider.provider_version,
                contract_version=provider.contract_version,
                raw_model_json=None,
                elapsed_time_ms=5,
                result=_result(status="BROKEN_STATUS"),
            )
        status = "NO_EFFECTS"
        return _FakeRun(
            provider_name=provider.provider_name,
            provider_version=provider.provider_version,
            contract_version=provider.contract_version,
            raw_model_json=None,
            elapsed_time_ms=3,
            result=_result(status=status),
        )

    code, report = run_semantic_golden(
        golden_path=str(backend_root / "evals/source_effect_golden_v1.json"),
        model_name="qwen3:8b",
        provider_factory=_FakeProvider,
        discovery_runner=discovery_runner,
        session_factory=lambda: nullcontext(object()),
    )

    assert code == 0
    assert report is not None
    assert report["aggregate_metrics"]["grounding_failure_count"] >= 1
    assert report["aggregate_metrics"]["contract_shape_failure_count"] >= 1


def test_provider_exception_is_recorded_and_runner_continues() -> None:
    backend_root = _backend_root()

    def discovery_runner(db, fragment, *, provider):
        if "CONSEJO DE GERENTES" in fragment.source_text.upper():
            raise TimeoutError("simulated timeout")
        status = "REVIEW_REQUIRED" if "ciso i. Se modifica el inciso" in fragment.source_text else "NO_EFFECTS"
        return _FakeRun(
            provider_name=provider.provider_name,
            provider_version=provider.provider_version,
            contract_version=provider.contract_version,
            raw_model_json=None,
            elapsed_time_ms=5,
            result=_result(status=status),
        )

    code, report = run_semantic_golden(
        golden_path=str(backend_root / "evals/source_effect_golden_v1.json"),
        model_name="qwen3:8b",
        provider_factory=_FakeProvider,
        discovery_runner=discovery_runner,
        session_factory=lambda: nullcontext(object()),
    )

    assert code == 0
    assert report is not None
    assert report["aggregate_metrics"]["cases_total"] == 15
    timed_out_case = next(item for item in report["cases"] if item["case_id"] == "se_gc_005")
    assert any("provider_exception" in error for error in timed_out_case["errors"])


def test_precision_undefined_when_zero_predictions() -> None:
    backend_root = _backend_root()

    def discovery_runner(db, fragment, *, provider):
        status = "REVIEW_REQUIRED" if "ciso i. Se modifica el inciso" in fragment.source_text or "Apartado 3.1.5" in fragment.source_text else "NO_EFFECTS"
        return _FakeRun(
            provider_name=provider.provider_name,
            provider_version=provider.provider_version,
            contract_version=provider.contract_version,
            raw_model_json=None,
            elapsed_time_ms=2,
            result=_result(status=status),
        )

    code, report = run_semantic_golden(
        golden_path=str(backend_root / "evals/source_effect_golden_v1.json"),
        model_name="qwen3:8b",
        provider_factory=_FakeProvider,
        discovery_runner=discovery_runner,
        session_factory=lambda: nullcontext(object()),
    )

    assert code == 0
    assert report is not None
    assert report["aggregate_metrics"]["discovered_effect_count"] == 0
    assert report["aggregate_metrics"]["precision"] is None
    assert report["aggregate_metrics"]["precision_defined"] is False


def test_limited_coverage_banner_and_machine_json_are_deterministic(tmp_path: Path) -> None:
    backend_root = _backend_root()
    output_one = tmp_path / "out_one.json"
    output_two = tmp_path / "out_two.json"

    def discovery_runner(db, fragment, *, provider):
        status = "REVIEW_REQUIRED" if "ciso i. Se modifica el inciso" in fragment.source_text else "NO_EFFECTS"
        return _FakeRun(
            provider_name=provider.provider_name,
            provider_version=provider.provider_version,
            contract_version=provider.contract_version,
            raw_model_json=None,
            elapsed_time_ms=1,
            result=_result(status=status),
        )

    code_one, report_one = run_semantic_golden(
        golden_path=str(backend_root / "evals/source_effect_golden_v1.json"),
        model_name="qwen3:8b",
        output_json_path=str(output_one),
        provider_factory=_FakeProvider,
        discovery_runner=discovery_runner,
        session_factory=lambda: nullcontext(object()),
        now_utc="2026-09-09T06:00:00+00:00",
    )
    code_two, report_two = run_semantic_golden(
        golden_path=str(backend_root / "evals/source_effect_golden_v1.json"),
        model_name="qwen3:8b",
        output_json_path=str(output_two),
        provider_factory=_FakeProvider,
        discovery_runner=discovery_runner,
        session_factory=lambda: nullcontext(object()),
        now_utc="2026-09-09T06:00:00+00:00",
    )

    assert code_one == 0 and code_two == 0
    assert report_one is not None and report_two is not None
    assert report_one["limited_coverage_declaration"]["banner"] == "FROZEN LIMITED-COVERAGE GOLDEN"

    content_one = output_one.read_text(encoding="utf-8")
    content_two = output_two.read_text(encoding="utf-8")
    assert content_one == content_two
