from __future__ import annotations

import sys
from unittest.mock import patch

import pytest

sys.path.append("services/ranking_and_rendering/src")
from ranking_and_rendering.ranker import _compute_score, rank
from shared.schemas import PromptField

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_field(name: str, values: list, strength: str = "soft") -> PromptField:
    return PromptField(
        name=name,
        value=values,
        strength=strength,
        extraction_context="test context",
    )


def _make_doc(doc_id: str, score: float, **payload_kwargs) -> dict:
    return {"id": doc_id, "score": score, "payload": payload_kwargs, "computed_score": score}


# ---------------------------------------------------------------------------
# _compute_score: campos desconocidos
# ---------------------------------------------------------------------------


class TestComputeScoreUnknownFields:

    def test_no_active_fields_returns_only_semantic(self):
        # Simula que ningún campo del input está en el mapping
        payload = {"rooms": 3}
        with patch("ranking_and_rendering.ranker._FIELD_SCORE_MAPPING", {}):
            score = _compute_score(payload, [_make_field("rooms", [3])], semantic_score=0.8)
        assert score == pytest.approx(0.8 * 0.10, abs=1e-4)

    def test_empty_fields_returns_only_semantic(self):
        payload = {"rooms": 3}
        score = _compute_score(payload, [], semantic_score=0.9)
        assert score == pytest.approx(0.9 * 0.10, abs=1e-4)


# ---------------------------------------------------------------------------
# _compute_score: hard siempre devuelve score pleno por campo
# ---------------------------------------------------------------------------


class TestComputeScoreHardFields:

    def test_hard_field_contributes_full_score(self):
        payload = {"rooms": 3, "price": 150_000}
        fields = [
            _make_field("rooms", [3], "hard"),
            _make_field("price", [200_000], "hard"),
        ]
        score = _compute_score(payload, fields, semantic_score=1.0)
        # Todos los scores son 1.0 → score final debe ser 1.0
        assert score == pytest.approx(1.0, abs=1e-4)


# ---------------------------------------------------------------------------
# _compute_score: penalizaciones soft
# ---------------------------------------------------------------------------


class TestComputeScoreSoftPenalties:

    def test_soft_rooms_below_requested_penalizes(self):
        # Pedidas 3, tiene 2 (zona relajada) → score < 1.0 para ese campo
        payload_exact = {"rooms": 3}
        payload_relaxed = {"rooms": 2}
        fields = [_make_field("rooms", [3], "soft")]

        score_exact = _compute_score(payload_exact, fields, semantic_score=0.5)
        score_relaxed = _compute_score(payload_relaxed, fields, semantic_score=0.5)

        assert score_exact > score_relaxed

    def test_soft_price_above_requested_penalizes(self):
        # Precio dentro vs. precio en zona relajada
        payload_within = {"price": 190_000}
        payload_over = {"price": 210_000}
        fields = [_make_field("price", [200_000], "soft")]

        score_within = _compute_score(payload_within, fields, semantic_score=0.5)
        score_over = _compute_score(payload_over, fields, semantic_score=0.5)

        assert score_within > score_over

    def test_soft_surface_below_requested_penalizes(self):
        payload_exact = {"surface": 80}
        payload_short = {"surface": 70}
        fields = [_make_field("surface", [80], "soft")]

        score_exact = _compute_score(payload_exact, fields, semantic_score=0.5)
        score_short = _compute_score(payload_short, fields, semantic_score=0.5)

        assert score_exact > score_short


# ---------------------------------------------------------------------------
# _compute_score: el semántico siempre contribuye
# ---------------------------------------------------------------------------


class TestSemanticContribution:

    def test_higher_semantic_score_yields_higher_final(self):
        payload = {"rooms": 3}
        fields = [_make_field("rooms", [3], "hard")]

        score_low = _compute_score(payload, fields, semantic_score=0.2)
        score_high = _compute_score(payload, fields, semantic_score=0.9)

        assert score_high > score_low

    def test_semantic_weight_is_bounded(self):
        # Con score semántico perfecto y campos perfectos → máximo 1.0
        payload = {"rooms": 3}
        fields = [_make_field("rooms", [3], "hard")]
        score = _compute_score(payload, fields, semantic_score=1.0)
        assert score <= 1.0


# ---------------------------------------------------------------------------
# rank: ordenación correcta
# ---------------------------------------------------------------------------


class TestRank:

    def test_returns_sorted_descending(self):
        docs = [
            _make_doc("a", 0.9, rooms=2, price=210_000),  # penalizado en rooms y price
            _make_doc("b", 0.7, rooms=3, price=180_000),  # cumple todo
            _make_doc("c", 0.5, rooms=3, price=200_000),  # cumple todo, menor semántico
        ]
        fields = [
            _make_field("rooms", [3], "soft"),
            _make_field("price", [200_000], "soft"),
        ]
        result = rank(docs, fields)
        scores = [r["computed_score"] for r in result]
        assert scores == sorted(scores, reverse=True)

    def test_rank_returns_all_documents(self):
        docs = [_make_doc(str(i), 0.5, rooms=3) for i in range(5)]
        fields = [_make_field("rooms", [3], "soft")]
        result = rank(docs, fields)
        assert len(result) == 5

    def test_rank_overwrites_score_with_final_score(self):
        # El score original (semántico) debe ser reemplazado por el score final
        docs = [_make_doc("x", 0.99, rooms=3)]
        fields = [_make_field("rooms", [3], "hard")]
        result = rank(docs, fields)
        # El score final no debe ser 0.99 exacto porque incluye la ponderación
        assert result[0]["computed_score"] != 0.99

    def test_rank_preserves_other_document_fields(self):
        docs = [{"id": "z", "score": 0.8, "payload": {"rooms": 3}, "extra": "metadata"}]
        fields = [_make_field("rooms", [3], "soft")]
        result = rank(docs, fields)
        assert result[0]["extra"] == "metadata"
        assert result[0]["id"] == "z"

    def test_empty_documents_returns_empty(self):
        result = rank([], [_make_field("rooms", [3])])
        assert result == []

    def test_empty_fields_ranks_by_semantic_only(self):
        docs = [
            _make_doc("high", 0.9, rooms=3),
            _make_doc("low", 0.2, rooms=3),
        ]
        result = rank(docs, fields=[])
        assert result[0]["id"] == "high"
