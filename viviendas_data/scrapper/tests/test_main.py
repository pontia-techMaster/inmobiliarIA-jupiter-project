def test_scrapper_import():
    """Test simple que verifica que el scrapper se puede importar"""
    try:
        # Intentar importar las clases principales
        from viviendas_data.scrapper.main import PropertyExtractor, BatchExtractor, PropertyData
        print("OK - Scrapper modules imported successfully")

        # Verificar que las clases existen
        assert PropertyExtractor is not None
        assert BatchExtractor is not None
        assert PropertyData is not None

    except ImportError as e:
        assert False, f"Failed to import scrapper modules: {e}"