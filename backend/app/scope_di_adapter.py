"""Opt-in grounded Scope semantic adapter over neutral transcription.

No provider is installed or executed by default. Ownership/obligation semantics
stay in the accepted Scope discovery contract; DI contributes only perception.
"""
from __future__ import annotations
from dataclasses import replace
from typing import Sequence
from sqlalchemy.orm import Session
from app.scope_detail_adapters import ScopeDetailEvidenceArtifact
from app.scope_details import ScopeDetailCandidate
from app.document_intelligence import Quality
from app.scope_semantic_discovery import ScopeSemanticSourceFragment, discover_scope_semantics, map_discovered_obligation_to_scope_detail_candidate, ScopeSemanticDiscoveryProvider


class NeutralScopeSemanticAdapter:
    adapter_name = "NeutralScopeSemanticAdapter"
    adapter_version = "neutral-scope-semantic-001"

    def __init__(self, providers: Sequence[ScopeSemanticDiscoveryProvider]) -> None:
        self.providers = providers

    def supports(self, artifact: ScopeDetailEvidenceArtifact) -> bool:
        return artifact.transcription is not None

    def extract_candidates(self, db: Session, artifact: ScopeDetailEvidenceArtifact) -> Sequence[ScopeDetailCandidate]:
        result = artifact.transcription
        if result is None:
            return ()
        observations = [e for e in result.candidates if e.source_artifact_key == artifact.source_artifact_key
            and e.lineage == "ACTIVE" and e.quality in {Quality.RELIABLE, Quality.REVIEW_REQUIRED} and e.text.strip()]
        candidates = []
        seen = set()
        for observation in observations:
            fragment = ScopeSemanticSourceFragment(tender_id=artifact.tender_id, source_document_id=artifact.source_document_id,
                document_page_id=artifact.document_page_id, page_number=observation.page.page_number,
                source_method=observation.source_method.value, source_artifact_key=observation.source_artifact_key,
                source_locator=observation.source_locator or f"page:{observation.page.page_number}",
                source_text=observation.text, source_contract_version=observation.source_contract_version)
            discovery = discover_scope_semantics(fragment, providers=self.providers)
            if discovery.status == "INVALID_OUTPUT":
                raise ValueError(";".join(discovery.errors))
            for obligation in discovery.candidates:
                candidate = map_discovered_obligation_to_scope_detail_candidate(fragment, obligation)
                candidate = replace(candidate, source_analysis_id=observation.source_analysis_id,
                    source_page_result_id=observation.source_page_result_id,
                    review_required=candidate.review_required or result.status != "RESOLVED")
                key = (candidate.domain, candidate.description, candidate.source_excerpt)
                if key not in seen:
                    seen.add(key)
                    candidates.append(candidate)
        return candidates
