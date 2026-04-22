"""Ranking logic.

Intentionally empty. Will rerank candidate docs using the similarity scores
from Qdrant combined with the filters on the input job (e.g. boost exact
matches on city, downweight out-of-range prices).
"""
