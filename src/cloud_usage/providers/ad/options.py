"""AdOptions dataclass and normalization helpers for the Microsoft AD provider."""

from __future__ import annotations

import dataclasses
from typing import Optional, Sequence, Union

from .constants import AD_SERVICES


def _normalize_host(value: str) -> str:
    """Strip whitespace, strip trailing dots, lowercase a hostname."""
    return value.strip().rstrip(".").lower()


def _coerce_to_csv(value: Union[str, list, None]) -> list[str]:
    """Normalize str/list/None to a list of non-empty string tokens."""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value if str(v).strip()]
    # str path — split on comma
    return [tok for tok in str(value).split(",") if tok.strip()]


def normalize_ad_servers(value: Union[str, list, None]) -> list[str]:
    """Return a lowercased, deduplicated list of AD server hostnames.

    Preserves first-occurrence order when deduplicating.
    """
    tokens = _coerce_to_csv(value)
    seen: dict[str, None] = {}
    for tok in tokens:
        normalized = _normalize_host(tok)
        if normalized:
            seen.setdefault(normalized, None)
    return list(seen.keys())


def normalize_ad_services(value: Union[str, None]) -> tuple[str, ...]:
    """Parse and validate a comma-separated service list string.

    Returns a tuple of validated service names.

    Raises:
        ValueError: if the input is empty or contains an invalid service token.
    """
    tokens = [tok.strip().lower() for tok in (value or "").split(",") if tok.strip()]
    if not tokens:
        raise ValueError(
            f"--ad-services must not be empty. Valid values: {', '.join(AD_SERVICES)}"
        )
    invalid = [t for t in tokens if t not in AD_SERVICES]
    if invalid:
        raise ValueError(
            f"Invalid AD service(s): {', '.join(invalid)}. "
            f"Valid values: {', '.join(AD_SERVICES)}"
        )
    return tuple(tokens)


@dataclasses.dataclass(frozen=True)
class AdOptions:
    """Configuration for a Microsoft AD collection run.

    All fields are validated in __post_init__. Create with keyword arguments.

    Attributes:
        servers: List of DC hostnames to connect to.
        services: Tuple of services to collect: "dns", "dhcp", and/or "user".
        auth_mode: WinRM authentication mode — "kerberos" or "ntlm".
        username: Domain username for NTLM auth (optional for Kerberos).
        password: Password for NTLM auth (optional for Kerberos).
        winrm_port: WinRM port (default 5985 for HTTP, 5986 for HTTPS).
        winrm_ssl: Whether to use HTTPS for the WinRM connection.
        skip_cert_validation: Skip WinRM SSL certificate validation.
        max_retries: Number of PS command retries on transient failures.
        timeout_seconds: WinRM operation timeout in seconds.
        backoff_seconds: Base sleep duration between retries (exponential).
        autodiscover: If True, discover DCs via Get-ADForest/Get-ADDomainController.
        discovery_server: Seed server for autodiscovery (required when autodiscover=True).
    """

    servers: list[str] = dataclasses.field(default_factory=list)
    services: tuple[str, ...] = ("dns", "dhcp", "user")
    auth_mode: str = "kerberos"
    username: Optional[str] = None
    password: Optional[str] = None
    winrm_port: int = 5985
    winrm_ssl: bool = False
    skip_cert_validation: bool = False
    max_retries: int = 3
    timeout_seconds: int = 60
    backoff_seconds: float = 2.0
    autodiscover: bool = False
    discovery_server: Optional[str] = None

    def __post_init__(self) -> None:
        # Validate auth_mode
        if self.auth_mode not in {"kerberos", "ntlm"}:
            raise ValueError(
                f"auth_mode must be 'kerberos' or 'ntlm', got: {self.auth_mode!r}"
            )

        # NTLM requires explicit credentials
        if self.auth_mode == "ntlm" and (not self.username or not self.password):
            raise ValueError(
                "auth_mode='ntlm' requires both username and password to be set."
            )

        # winrm_port range
        if not (1 <= self.winrm_port <= 65535):
            raise ValueError(
                f"winrm_port must be between 1 and 65535, got: {self.winrm_port}"
            )

        # max_retries >= 1
        if self.max_retries < 1:
            raise ValueError(
                f"max_retries must be >= 1, got: {self.max_retries}"
            )

        # backoff_seconds >= 0
        if self.backoff_seconds < 0:
            raise ValueError(
                f"backoff_seconds must be >= 0, got: {self.backoff_seconds}"
            )

    @property
    def cert_validation(self) -> str:
        """Return WinRM server_cert_validation value."""
        return "ignore" if self.skip_cert_validation else "validate"
