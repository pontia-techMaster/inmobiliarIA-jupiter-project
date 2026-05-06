from langchain_google_genai.embeddings import GoogleGenerativeAIEmbeddings

EMBEDDINGS_MODEL_NAME = "gemini-embedding-001"
EMBEDDINGS_DIMENSIONALITY = 768

_model = GoogleGenerativeAIEmbeddings(model=EMBEDDINGS_MODEL_NAME, output_dimensionality=EMBEDDINGS_DIMENSIONALITY)


def embed_texts(texts: list[str]):
    return _model.embed_documents(texts, task_type="retrieval_document", batch_size=10)


def embed_query(query: str):
    return _model.embed_query(query, task_type="retrieval_query")
