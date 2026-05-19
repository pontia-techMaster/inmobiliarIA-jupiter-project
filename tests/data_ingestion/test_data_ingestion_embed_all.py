import json
from unittest.mock import MagicMock

import pytest
from data_ingestion import handler


@pytest.fixture
def fake_normalize_checkpoint(tmp_path, monkeypatch):
    checkpoint = tmp_path / "normalize-checkpoint.json"
    monkeypatch.setattr(handler, "NORMALIZE_CHECKPOINT", checkpoint)
    return checkpoint


@pytest.fixture
def fake_embed_checkpoint(tmp_path, monkeypatch):
    checkpoint = tmp_path / "embed-checkpoint.json"
    monkeypatch.setattr(handler, "EMBED_CHECKPOINT", checkpoint)
    return checkpoint


def test_normalize_all_success(fake_normalize_checkpoint, monkeypatch):
    descriptions = ["Piso amplio y luminoso."]
    normalized_descriptions = ["Piso amplio, luminoso y bien distribuido."]

    mock_normalize_descriptions = MagicMock(return_value=normalized_descriptions)

    monkeypatch.setattr(
        handler,
        "normalize_descriptions",
        mock_normalize_descriptions,
    )

    result = handler.normalize_all(descriptions, force=True)

    assert result == normalized_descriptions
    mock_normalize_descriptions.assert_called_once_with(descriptions)
    assert fake_normalize_checkpoint.exists()

    checkpoint_content = json.loads(fake_normalize_checkpoint.read_text(encoding="utf-8"))

    assert checkpoint_content == normalized_descriptions


def test_normalize_all_loads_from_checkpoint(
    fake_normalize_checkpoint,
    monkeypatch,
):
    checkpoint_data = ["Descripción cargada desde checkpoint."]

    fake_normalize_checkpoint.write_text(
        json.dumps(checkpoint_data),
        encoding="utf-8",
    )

    mock_normalize_descriptions = MagicMock()

    monkeypatch.setattr(
        handler,
        "normalize_descriptions",
        mock_normalize_descriptions,
    )

    result = handler.normalize_all(
        ["Esta descripción no debería procesarse."],
        force=False,
    )

    assert result == checkpoint_data
    mock_normalize_descriptions.assert_not_called()


def test_normalize_all_raises_error_when_normalizer_fails(
    fake_normalize_checkpoint,
    monkeypatch,
):
    descriptions = ["Descripción que provocará error."]

    mock_normalize_descriptions = MagicMock(side_effect=RuntimeError("LLM normalization failed"))

    monkeypatch.setattr(
        handler,
        "normalize_descriptions",
        mock_normalize_descriptions,
    )

    with pytest.raises(RuntimeError, match="LLM normalization failed"):
        handler.normalize_all(descriptions, force=True)

    mock_normalize_descriptions.assert_called_once_with(descriptions)
    assert not fake_normalize_checkpoint.exists()


def test_embed_all_success(fake_embed_checkpoint, monkeypatch):
    descriptions = ["Piso amplio, luminoso y bien distribuido."]
    vectors = [[0.1, 0.2, 0.3]]

    mock_embed_texts = MagicMock(return_value=vectors)

    monkeypatch.setattr(
        handler,
        "embed_texts",
        mock_embed_texts,
    )

    result = handler.embed_all(descriptions, force=True)

    assert result == vectors
    mock_embed_texts.assert_called_once_with(descriptions)
    assert fake_embed_checkpoint.exists()

    checkpoint_content = json.loads(fake_embed_checkpoint.read_text(encoding="utf-8"))

    assert checkpoint_content == vectors


def test_embed_all_loads_from_checkpoint(
    fake_embed_checkpoint,
    monkeypatch,
):
    checkpoint_vectors = [[0.1, 0.2, 0.3]]

    fake_embed_checkpoint.write_text(
        json.dumps(checkpoint_vectors),
        encoding="utf-8",
    )

    mock_embed_texts = MagicMock()

    monkeypatch.setattr(
        handler,
        "embed_texts",
        mock_embed_texts,
    )

    result = handler.embed_all(
        ["Este texto no debería enviarse a embeddings."],
        force=False,
    )

    assert result == checkpoint_vectors
    mock_embed_texts.assert_not_called()


def test_embed_all_raises_error_when_embedding_fails(
    fake_embed_checkpoint,
    monkeypatch,
):
    descriptions = ["Texto que provocará error."]

    mock_embed_texts = MagicMock(side_effect=RuntimeError("Embedding generation failed"))

    monkeypatch.setattr(
        handler,
        "embed_texts",
        mock_embed_texts,
    )

    with pytest.raises(RuntimeError, match="Embedding generation failed"):
        handler.embed_all(descriptions, force=True)

    mock_embed_texts.assert_called_once_with(descriptions)
    assert not fake_embed_checkpoint.exists()
