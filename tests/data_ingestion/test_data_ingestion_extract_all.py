"""Test cases for the data ingestion service."""

import os
from unittest.mock import MagicMock

os.environ["GOOGLE_API_KEY"] = "fake-api-key-for-tests"
os.environ["GEMINI_API_KEY"] = "fake-api-key-for-tests"

from data_ingestion import handler
from data_ingestion.extractor import PropertyData


def test_extract_all(tmp_path, monkeypatch):
    # Evitamos que use el checkpoint real del proyecto
    monkeypatch.setattr(handler, "EXTRACT_CHECKPOINT", tmp_path / "extract-checkpoint.json")

    # Creamos un HTML falso porque extract_all busca *.html
    html_file = tmp_path / "property.html"
    html_file.write_text("<html></html>", encoding="utf-8")

    # Mockeamos PropertyExtractor
    mock_extractor_class = MagicMock()
    mock_extractor_instance = MagicMock()

    mock_extractor_instance.extract.return_value = PropertyData(id="123", description="A nice property.")

    mock_extractor_class.return_value = mock_extractor_instance

    monkeypatch.setattr(handler, "PropertyExtractor", mock_extractor_class)

    properties = handler.extract_all(tmp_path, force=True)

    assert len(properties) == 1
    assert properties[0].id == "123"
    assert properties[0].description == "A nice property."

    mock_extractor_class.assert_called_once_with(html_file.as_posix())
    mock_extractor_instance.extract.assert_called_once()
