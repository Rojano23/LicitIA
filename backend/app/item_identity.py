from __future__ import annotations

import re
from collections import OrderedDict
from dataclasses import dataclass
from typing import Iterable

ITEM_IDENTITY_DETERMINED = "DETERMINED"
ITEM_IDENTITY_UNKNOWN = "UNKNOWN"
ITEM_IDENTITY_REVIEW_REQUIRED = "REVIEW_REQUIRED"

SAFE_ITEM_IDENTITY_RE = re.compile(r"^\d+(?:\.\d+)*\.?$")


@dataclass(frozen=True, slots=True)
class NormalizedItemIdentity:
    raw_label: str
    normalized_key: str | None
    components: tuple[str, ...]
    depth: int
    parent_key: str | None
    state: str


@dataclass(frozen=True, slots=True)
class ItemIdentityCollision:
    normalized_key: str
    raw_labels: tuple[str, ...]
    identities: tuple[NormalizedItemIdentity, ...]
    state: str = ITEM_IDENTITY_REVIEW_REQUIRED


def _normalize_component(component: str) -> str:
    return str(int(component))


def normalize_item_identity(raw_label: str) -> NormalizedItemIdentity:
    compact = raw_label.strip()
    if not compact or not SAFE_ITEM_IDENTITY_RE.match(compact):
        return NormalizedItemIdentity(
            raw_label=raw_label,
            normalized_key=None,
            components=(),
            depth=0,
            parent_key=None,
            state=ITEM_IDENTITY_UNKNOWN,
        )

    if compact.endswith("."):
        compact = compact[:-1]

    components = tuple(_normalize_component(part) for part in compact.split(".") if part)
    normalized_key = ".".join(components)
    parent_key = ".".join(components[:-1]) if len(components) > 1 else None

    return NormalizedItemIdentity(
        raw_label=raw_label,
        normalized_key=normalized_key,
        components=components,
        depth=len(components),
        parent_key=parent_key,
        state=ITEM_IDENTITY_DETERMINED,
    )


def detect_item_identity_collisions(identities: Iterable[NormalizedItemIdentity]) -> list[ItemIdentityCollision]:
    grouped: dict[str, list[NormalizedItemIdentity]] = {}
    for identity in identities:
        if identity.normalized_key is None:
            continue
        grouped.setdefault(identity.normalized_key, []).append(identity)

    collisions: list[ItemIdentityCollision] = []
    for normalized_key in sorted(grouped):
        group = grouped[normalized_key]
        distinct_raw_labels = tuple(OrderedDict((identity.raw_label, None) for identity in group).keys())
        if len(distinct_raw_labels) < 2:
            continue
        collisions.append(
            ItemIdentityCollision(
                normalized_key=normalized_key,
                raw_labels=distinct_raw_labels,
                identities=tuple(group),
            )
        )
    return collisions