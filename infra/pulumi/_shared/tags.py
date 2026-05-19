"""Default tags applied to every taggable resource."""

from __future__ import annotations

import pulumi


def default_tags() -> dict[str, str]:
    return {
        "Project": "inmobiliarIA-jupiter",
        "Env": pulumi.get_stack(),
        "ManagedBy": "pulumi",
    }
