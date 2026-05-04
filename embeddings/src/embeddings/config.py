"""Embedding model constants — single source of truth for both producers and consumers.

Both ``vector_query`` (which embeds the query) and ``data_ingestion`` (which
embeds property descriptions) must use the same ``MODEL`` and ``DIMENSIONS``
to produce vectors in a comparable space. They differ only in ``TASK_TYPE``
because Gemini emits slightly different embeddings depending on whether the
text is a search query or a document being indexed.
"""

MODEL = "gemini-embedding-001"

# gemini-embedding-001 natively returns 3072 dims but supports Matryoshka
# truncation via output_dimensionality. Truncated vectors live in the same
# space, so the model + this constant together define the contract that
# vector_query and data_ingestion must share.
DIMENSIONS = 768

QUERY_TASK_TYPE = "retrieval_query"
DOCUMENT_TASK_TYPE = "retrieval_document"
