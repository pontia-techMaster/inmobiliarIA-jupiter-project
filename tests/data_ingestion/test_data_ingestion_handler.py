from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from data_ingestion import handler
from data_ingestion.extractor import PropertyData
from shared.schemas import IngestJob


@pytest.fixture
def fake_extract_checkpoint(tmp_path, monkeypatch):
    checkpoint = tmp_path / "extract-checkpoint.json"
    monkeypatch.setattr(handler, "EXTRACT_CHECKPOINT", checkpoint)
    return checkpoint


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


@pytest.fixture
def html_source_dir(tmp_path):
    html_file = tmp_path / "property.html"
    html_file.write_text("<html></html>", encoding="utf-8")
    return tmp_path


@pytest.fixture
def fake_property():
    return PropertyData(
        id="123",
        price=150000,
        description="A nice property.",
    )


def test_extract_all_success(
    html_source_dir,
    fake_extract_checkpoint,
    fake_property,
    monkeypatch,
):
    mock_extractor_class = MagicMock()
    mock_extractor_instance = MagicMock()
    mock_extractor_instance.extract.return_value = fake_property
    mock_extractor_class.return_value = mock_extractor_instance

    monkeypatch.setattr(handler, "PropertyExtractor", mock_extractor_class)

    properties = handler.extract_all(html_source_dir, force=True)

    assert len(properties) == 1
    assert properties[0].id == "123"
    assert properties[0].description == "A nice property."

    expected_html = html_source_dir / "property.html"
    mock_extractor_class.assert_called_once_with(expected_html.as_posix())
    mock_extractor_instance.extract.assert_called_once()

    assert fake_extract_checkpoint.exists()


def test_extract_all_loads_from_checkpoint(
    tmp_path,
    fake_extract_checkpoint,
    monkeypatch,
):
    fake_extract_checkpoint.write_text(
        '[{"id": "123", "description": "Loaded from checkpoint"}]',
        encoding="utf-8",
    )

    mock_extractor_class = MagicMock()
    monkeypatch.setattr(handler, "PropertyExtractor", mock_extractor_class)

    properties = handler.extract_all(tmp_path, force=False)

    assert len(properties) == 1
    assert properties[0].id == "123"
    assert properties[0].description == "Loaded from checkpoint"

    mock_extractor_class.assert_not_called()


def test_extract_all_without_html_files(
    tmp_path,
    fake_extract_checkpoint,
    monkeypatch,
):
    mock_extractor_class = MagicMock()
    monkeypatch.setattr(handler, "PropertyExtractor", mock_extractor_class)

    properties = handler.extract_all(tmp_path, force=True)

    assert properties == []
    mock_extractor_class.assert_not_called()
    assert fake_extract_checkpoint.exists()
    assert fake_extract_checkpoint.read_text() == "[]"


def test_extract_all_skips_failed_html(
    html_source_dir,
    fake_extract_checkpoint,
    monkeypatch,
):
    mock_extractor_class = MagicMock()
    mock_extractor_class.return_value.extract.side_effect = Exception("Boom")

    monkeypatch.setattr(handler, "PropertyExtractor", mock_extractor_class)

    properties = handler.extract_all(html_source_dir, force=True)

    assert properties == []
    mock_extractor_class.assert_called_once()
    assert fake_extract_checkpoint.exists()
    assert fake_extract_checkpoint.read_text() == "[]"


def test_normalize_all_success(
    fake_normalize_checkpoint,
    monkeypatch,
):
    mock_normalize = MagicMock(return_value=["normalized description"])

    monkeypatch.setattr(handler, "normalize_descriptions", mock_normalize)

    result = handler.normalize_all(["raw description"], force=True)

    assert result == ["normalized description"]
    mock_normalize.assert_called_once_with(["raw description"])
    assert fake_normalize_checkpoint.exists()


def test_normalize_all_loads_from_checkpoint(
    fake_normalize_checkpoint,
    monkeypatch,
):
    fake_normalize_checkpoint.write_text(
        '["checkpoint normalized description"]',
        encoding="utf-8",
    )

    mock_normalize = MagicMock()
    monkeypatch.setattr(handler, "normalize_descriptions", mock_normalize)

    result = handler.normalize_all(["raw description"], force=False)

    assert result == ["checkpoint normalized description"]
    mock_normalize.assert_not_called()


def test_embed_all_success(
    fake_embed_checkpoint,
    monkeypatch,
):
    fake_vectors = [[0.1, 0.2, 0.3]]
    mock_embed_texts = MagicMock(return_value=fake_vectors)

    monkeypatch.setattr(handler, "embed_texts", mock_embed_texts)

    result = handler.embed_all(["normalized description"], force=True)

    assert result == fake_vectors
    mock_embed_texts.assert_called_once_with(["normalized description"])
    assert fake_embed_checkpoint.exists()


def test_embed_all_loads_from_checkpoint(
    fake_embed_checkpoint,
    monkeypatch,
):
    fake_embed_checkpoint.write_text(
        "[[0.1, 0.2, 0.3]]",
        encoding="utf-8",
    )

    mock_embed_texts = MagicMock()
    monkeypatch.setattr(handler, "embed_texts", mock_embed_texts)

    result = handler.embed_all(["normalized description"], force=False)

    assert result == [[0.1, 0.2, 0.3]]
    mock_embed_texts.assert_not_called()


def test_ingest_creates_collection_if_not_exists(
    fake_property,
    monkeypatch,
):
    mock_client = MagicMock()
    mock_client.collection_exists.return_value = False

    mock_qdrant_client_class = MagicMock(return_value=mock_client)

    monkeypatch.setattr(handler, "QdrantClient", mock_qdrant_client_class)
    monkeypatch.setattr(
        handler,
        "settings",
        SimpleNamespace(
            qdrant_url="http://localhost:6333",
            qdrant_api_key=None,
            qdrant_collection_name="properties",
        ),
    )

    embeddings = [[0.1] * handler.EMBEDDINGS_DIMENSIONALITY]

    result = handler.ingest(
        properties=[fake_property],
        descriptions=["normalized description"],
        embeddings=embeddings,
    )

    assert result is None

    mock_qdrant_client_class.assert_called_once_with(url="http://localhost:6333", api_key=None)

    mock_client.collection_exists.assert_called_once_with(collection_name="properties")

    mock_client.create_collection.assert_called_once()
    mock_client.upsert.assert_called_once()

    _, kwargs = mock_client.upsert.call_args
    assert kwargs["collection_name"] == "properties"
    assert kwargs["wait"] is True
    assert len(kwargs["points"]) == 1


def test_ingest_does_not_create_collection_if_exists(
    fake_property,
    monkeypatch,
):
    mock_client = MagicMock()
    mock_client.collection_exists.return_value = True

    mock_qdrant_client_class = MagicMock(return_value=mock_client)

    monkeypatch.setattr(handler, "QdrantClient", mock_qdrant_client_class)
    monkeypatch.setattr(
        handler,
        "settings",
        SimpleNamespace(
            qdrant_url="http://localhost:6333",
            qdrant_api_key=None,
            qdrant_collection_name="properties",
        ),
    )

    embeddings = [[0.1] * handler.EMBEDDINGS_DIMENSIONALITY]

    handler.ingest(
        properties=[fake_property],
        descriptions=["normalized description"],
        embeddings=embeddings,
    )

    mock_client.create_collection.assert_not_called()
    mock_client.upsert.assert_called_once()


def test_handle_orchestrates_full_flow(monkeypatch, fake_property):
    mock_extract_all = MagicMock(return_value=[fake_property])
    mock_normalize_all = MagicMock(return_value=["normalized description"])
    mock_embed_all = MagicMock(return_value=[[0.1, 0.2, 0.3]])
    mock_ingest = MagicMock(return_value=None)

    monkeypatch.setattr(handler, "extract_all", mock_extract_all)
    monkeypatch.setattr(handler, "normalize_all", mock_normalize_all)
    monkeypatch.setattr(handler, "embed_all", mock_embed_all)
    monkeypatch.setattr(handler, "ingest", mock_ingest)

    job = IngestJob(source="/fake/source")

    result = handler.handle(job)

    assert result is None

    mock_extract_all.assert_called_once()
    mock_normalize_all.assert_called_once_with(["A nice property."])
    mock_embed_all.assert_called_once_with(["normalized description"])
    mock_ingest.assert_called_once_with(
        [fake_property],
        ["normalized description"],
        [[0.1, 0.2, 0.3]],
    )
