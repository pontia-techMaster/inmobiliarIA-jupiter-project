"""Per-service embedding entry point.

Thin re-export of :func:`embeddings.embed_query` from the shared workspace
package. Kept as a separate module so this service has a clear local seam
where embedding-specific concerns (caching, batching, alternate models)
could land without touching the shared package.
"""

from embeddings import embed_query

__all__ = ["embed_query"]
