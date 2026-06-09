from __future__ import annotations

import pytest

from structure.slot_roles import (
    GAP_HYPERFRAMES_PRIMARY_ROLES,
    PACKAGING_ROLES,
    SLOT_ROLE_ENUM,
    SLOT_ROLES,
    default_required_asset_types,
    normalize_slot_role,
)


def test_slot_role_enum_matches_schema_set() -> None:
    assert SLOT_ROLES == frozenset(SLOT_ROLE_ENUM)
    assert "demonstration" not in SLOT_ROLES


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("demonstration", "usage_scene"),
        ("demo", "usage_scene"),
        ("tutorial", "usage_scene"),
        ("solution", "product_closeup"),
        ("hook", "hook_visual"),
        ("unknown_role", "usage_scene"),
    ],
)
def test_normalize_slot_role_aliases(raw: str, expected: str) -> None:
    assert normalize_slot_role(raw) == expected


def test_default_required_asset_types_packaging_vs_visual() -> None:
    assert default_required_asset_types("benefit_card") == ["text", "packaging"]
    assert default_required_asset_types("usage_scene") == ["video", "image"]


def test_proof_in_packaging_but_not_gap_hyperframes_primary() -> None:
    assert "proof" in PACKAGING_ROLES
    assert "proof" not in GAP_HYPERFRAMES_PRIMARY_ROLES
