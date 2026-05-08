"""Typed wrappers around ``pulumi.StackReference``.

Each ``XxxRef`` exposes the outputs we publish from a foundation stack
as named attributes, so consumer stacks don't have to remember exact
output keys (and get a clear error when one is missing).
"""

from __future__ import annotations

import pulumi

from _shared.naming import env

_ORG = "organization"  # Pulumi self-hosted backend uses this fixed org name


def _ref(stack_name: str) -> pulumi.StackReference:
    return pulumi.StackReference(f"{_ORG}/{stack_name}/{env()}")


class PlatformRef:
    """Outputs of the ``platform`` stack."""

    def __init__(self) -> None:
        self._r = _ref("platform")

    def queue_url(self, queue: str) -> pulumi.Output[str]:
        return self._r.require_output(f"queue_{queue}_url")

    def queue_arn(self, queue: str) -> pulumi.Output[str]:
        return self._r.require_output(f"queue_{queue}_arn")

    def ecr_repo_url(self, service: str) -> pulumi.Output[str]:
        return self._r.require_output(f"ecr_{service}_repo_url")

    def log_group_name(self, service: str) -> pulumi.Output[str]:
        return self._r.require_output(f"log_group_{service}_name")

    def ssm_gemini_api_key_arn(self) -> pulumi.Output[str]:
        return self._r.require_output("ssm_gemini_api_key_arn")

    def ssm_gemini_api_key_name(self) -> pulumi.Output[str]:
        return self._r.require_output("ssm_gemini_api_key_name")


class ApiGatewayRef:
    """Outputs of the ``api-gateway`` stack."""

    def __init__(self) -> None:
        self._r = _ref("api-gateway")

    @property
    def endpoint(self) -> pulumi.Output[str]:
        return self._r.require_output("endpoint")
