"""Resource name helper.

All cloud resources are prefixed ``inmo-<env>-`` so dev / prod stacks of
the same project can coexist in one AWS account without colliding.
"""

from __future__ import annotations

import pulumi

PROJECT = "inmo"


def env() -> str:
    """The current Pulumi stack name (``dev``, ``prod``, ...)."""
    return pulumi.get_stack()


def name(suffix: str) -> str:
    """``"queue-search-requests"`` → ``"inmo-dev-queue-search-requests"``."""
    return f"{PROJECT}-{env()}-{suffix}"
