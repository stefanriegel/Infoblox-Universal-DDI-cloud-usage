"""Microsoft AD collector — WinRM/PowerShell-based DNS, DHCP, and User collection.

winrm (pywinrm) is lazy-imported via importlib to keep the module importable
even when pywinrm is not installed. A ModuleNotFoundError is raised at
collection time if pywinrm is absent.
"""

from __future__ import annotations

import importlib
import json
import logging
import time
from typing import Any, Optional

from .constants import SUPPORTED_DNS_RECORD_TYPES
from .options import AdOptions

log = logging.getLogger(__name__)


class WinRMError(RuntimeError):
    """Raised when a WinRM connection or command fails after all retries."""


class MicrosoftAdCollector:
    """Collects DNS zones/records, DHCP scopes/leases, and AD users from DCs.

    WinRM sessions are built lazily per server. All collection methods accept
    an already-built session object so they can be unit-tested without a live DC.
    """

    def __init__(self, options: AdOptions) -> None:
        self.options = options

    # ------------------------------------------------------------------
    # Low-level WinRM helpers
    # ------------------------------------------------------------------

    def _import_winrm(self) -> Any:
        """Lazy-import pywinrm so the module stays importable without it."""
        try:
            return importlib.import_module("winrm")
        except ModuleNotFoundError as exc:
            raise ModuleNotFoundError(
                "pywinrm is required for AD collection. "
                "Install it with: pip install pywinrm"
            ) from exc

    def _build_session(self, server: str) -> Any:
        """Build and return a WinRM session for *server*.

        Uses the auth, port, SSL, and timeout settings from self.options.
        winrm is imported lazily so the module can be imported without pywinrm.
        """
        winrm = self._import_winrm()
        opts = self.options
        scheme = "https" if opts.winrm_ssl else "http"
        endpoint = f"{scheme}://{server}:{opts.winrm_port}/wsman"
        kwargs: dict[str, Any] = {
            "transport": opts.auth_mode,
            "server_cert_validation": opts.cert_validation,
        }
        if opts.username and opts.password:
            kwargs["auth"] = (opts.username, opts.password)
        try:
            kwargs["operation_timeout_sec"] = opts.timeout_seconds
            kwargs["read_timeout_sec"] = opts.timeout_seconds + 5
            return winrm.Session(endpoint, **kwargs)
        except TypeError:
            # Older pywinrm versions do not accept timeout kwargs.
            kwargs.pop("operation_timeout_sec", None)
            kwargs.pop("read_timeout_sec", None)
            return winrm.Session(endpoint, **kwargs)

    @staticmethod
    def _decode_output(value: Any) -> str:
        """Decode bytes/bytearray to UTF-8 string, or coerce other types to str."""
        if isinstance(value, (bytes, bytearray)):
            return value.decode("utf-8", errors="replace")
        return str(value).strip()

    def _run_ps_text(self, session: Any, script: str) -> str:
        """Run *script* on *session* with retry/backoff; return decoded stdout.

        Raises WinRMError after all retries are exhausted.
        """
        opts = self.options
        last_exc: Optional[Exception] = None
        for attempt in range(1, opts.max_retries + 1):
            try:
                response = session.run_ps(script)
                if response.status_code != 0:
                    stderr = self._decode_output(response.std_err)
                    stdout = self._decode_output(response.std_out)
                    raise WinRMError(stderr or stdout or "WinRM command failed")
                return self._decode_output(response.std_out)
            except WinRMError:
                raise
            except Exception as exc:
                last_exc = exc
                if attempt == opts.max_retries:
                    break
                sleep_time = opts.backoff_seconds * (2 ** (attempt - 1))
                log.debug(
                    "WinRM attempt %d/%d failed: %s — retrying in %.1fs",
                    attempt,
                    opts.max_retries,
                    exc,
                    sleep_time,
                )
                time.sleep(sleep_time)
        raise WinRMError(f"WinRM command failed after {opts.max_retries} attempts") from last_exc

    def _run_ps_json(self, session: Any, script: str) -> Any:
        """Run *script* and parse the JSON output.

        Returns None for empty output. Raises WinRMError on bad JSON.
        """
        text = self._run_ps_text(session, script).strip()
        if not text:
            return None
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise WinRMError(f"Invalid JSON from PowerShell: {exc}") from exc

    # ------------------------------------------------------------------
    # Static helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _object_list(payload: Any) -> list[dict]:
        """Coerce a JSON payload to a list of dicts."""
        if payload is None:
            return []
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict):
            return [payload]
        return []

    @staticmethod
    def _string_list(payload: Any) -> list[str]:
        """Coerce a JSON payload to a list of strings."""
        if payload is None:
            return []
        if isinstance(payload, list):
            return [str(item) for item in payload]
        return [str(payload)]

    @staticmethod
    def _ps_single_quote(value: str) -> str:
        """Escape single quotes in *value* for PowerShell single-quoted strings."""
        return value.replace("'", "''")

    # ------------------------------------------------------------------
    # DNS collection
    # ------------------------------------------------------------------

    def _collect_dns(self, session: Any) -> dict:
        """Collect DNS zones and records from a DC.

        Returns a dict with:
            zone_keys: set[str]          — zone name keys
            record_keys: set[str]        — dedup keys for supported DNS records
            ip_addresses: list[str]      — IPs extracted from A/AAAA records
            unsupported_record_keys: set[str]  — records outside SUPPORTED_DNS_RECORD_TYPES
        """
        zones_ps = (
            "Get-DnsServerZone -ErrorAction Stop | "
            "Select-Object @{Name='ZoneName';Expression={$_.ZoneName}} | "
            "ConvertTo-Json -Compress"
        )
        zones_payload = self._run_ps_json(session, zones_ps)
        zones = self._object_list(zones_payload)

        zone_keys: set[str] = set()
        record_keys: set[str] = set()
        unsupported_record_keys: set[str] = set()
        ip_addresses: list[str] = []
        seen_ips: set[str] = set()

        for zone in zones:
            zone_name = (zone.get("ZoneName") or "").strip()
            if not zone_name:
                continue
            zone_keys.add(zone_name)

            records_ps = (
                f"Get-DnsServerResourceRecord -ZoneName '{self._ps_single_quote(zone_name)}' "
                f"-ErrorAction Stop | "
                "Select-Object "
                "@{Name='HostName';Expression={$_.HostName}},"
                "@{Name='RecordType';Expression={($_.RecordType).ToString()}},"
                "@{Name='RecordData';Expression={($_.RecordData | ConvertTo-Json -Compress -Depth 6)}} | "
                "ConvertTo-Json -Compress -Depth 8"
            )
            try:
                records_payload = self._run_ps_json(session, records_ps)
            except WinRMError as exc:
                log.warning("DNS zone %r record fetch failed: %s", zone_name, exc)
                continue

            records = self._object_list(records_payload)
            for rec in records:
                owner = (rec.get("HostName") or "").strip()
                record_type = (rec.get("RecordType") or "").strip()
                record_data_raw = rec.get("RecordData")

                # Normalize RecordData to a JSON string for dedup key
                if isinstance(record_data_raw, str):
                    # Already a JSON string from PowerShell expression
                    try:
                        rd_obj = json.loads(record_data_raw)
                        record_data_norm = json.dumps(rd_obj, sort_keys=True)
                    except (json.JSONDecodeError, TypeError):
                        record_data_norm = record_data_raw
                elif isinstance(record_data_raw, dict):
                    record_data_norm = json.dumps(record_data_raw, sort_keys=True)
                else:
                    record_data_norm = str(record_data_raw)

                dedup_key = f"{zone_name}|{owner}|{record_type}|{record_data_norm}"

                if record_type not in SUPPORTED_DNS_RECORD_TYPES:
                    unsupported_record_keys.add(dedup_key)
                    continue

                record_keys.add(dedup_key)

                # Extract IP from A/AAAA records
                if isinstance(record_data_raw, str):
                    try:
                        rd_obj = json.loads(record_data_raw)
                    except (json.JSONDecodeError, TypeError):
                        rd_obj = {}
                elif isinstance(record_data_raw, dict):
                    rd_obj = record_data_raw
                else:
                    rd_obj = {}

                ip_str: str = ""
                if record_type == "A":
                    ip_str = str(rd_obj.get("IPv4Address") or "").strip()
                elif record_type == "AAAA":
                    ip_str = str(rd_obj.get("IPv6Address") or "").strip()

                if ip_str and ip_str not in seen_ips:
                    seen_ips.add(ip_str)
                    ip_addresses.append(ip_str)

        return {
            "zone_keys": zone_keys,
            "record_keys": record_keys,
            "ip_addresses": ip_addresses,
            "unsupported_record_keys": unsupported_record_keys,
        }

    # ------------------------------------------------------------------
    # DHCP collection
    # ------------------------------------------------------------------

    def _collect_dhcp(self, session: Any) -> dict:
        """Collect DHCP scopes, leases, and reservations from a DC.

        Returns a dict with:
            scope_keys: set[str]
            lease_keys: set[str]
            reservation_keys: set[str]
        """
        scopes_ps = (
            "Get-DhcpServerv4Scope -ErrorAction Stop | "
            "Select-Object @{Name='ScopeId';Expression={$_.ScopeId.IPAddressToString}} | "
            "ConvertTo-Json -Compress"
        )
        scopes_payload = self._run_ps_json(session, scopes_ps)
        scopes = self._object_list(scopes_payload)

        scope_keys: set[str] = set()
        lease_keys: set[str] = set()
        reservation_keys: set[str] = set()

        for scope in scopes:
            scope_id = (scope.get("ScopeId") or "").strip()
            if not scope_id:
                continue
            scope_keys.add(scope_id)

            # Leases
            leases_ps = (
                f"Get-DhcpServerv4Lease -ScopeId '{self._ps_single_quote(scope_id)}' "
                f"-ErrorAction Stop | "
                "Select-Object @{Name='IPAddress';Expression={$_.IPAddress.IPAddressToString}} | "
                "ConvertTo-Json -Compress"
            )
            try:
                leases_payload = self._run_ps_json(session, leases_ps)
                for lease in self._object_list(leases_payload):
                    ip = (lease.get("IPAddress") or "").strip()
                    if ip:
                        lease_keys.add(f"{scope_id}|{ip}")
            except WinRMError as exc:
                log.warning("DHCP lease fetch failed for scope %r: %s", scope_id, exc)

            # Reservations
            reservations_ps = (
                f"Get-DhcpServerv4Reservation -ScopeId '{self._ps_single_quote(scope_id)}' "
                f"-ErrorAction Stop | "
                "Select-Object @{Name='IPAddress';Expression={$_.IPAddress.IPAddressToString}} | "
                "ConvertTo-Json -Compress"
            )
            try:
                reservations_payload = self._run_ps_json(session, reservations_ps)
                for res in self._object_list(reservations_payload):
                    ip = (res.get("IPAddress") or "").strip()
                    if ip:
                        reservation_keys.add(f"{scope_id}|{ip}")
            except WinRMError as exc:
                log.warning(
                    "DHCP reservation fetch failed for scope %r: %s", scope_id, exc
                )

        return {
            "scope_keys": scope_keys,
            "lease_keys": lease_keys,
            "reservation_keys": reservation_keys,
        }

    # ------------------------------------------------------------------
    # User collection
    # ------------------------------------------------------------------

    def _collect_users(self, session: Any) -> dict:
        """Collect AD users from a DC.

        Returns a dict with:
            user_keys: set[str]          — dedup keys (sid:/upn:/sam: prefixed)
            sid_map: dict[str, str]      — user_key → raw SID string
        """
        users_ps = (
            "Get-ADUser -Filter * -ErrorAction Stop | "
            "Select-Object "
            "@{Name='SID';Expression={if ($_.SID) { $_.SID.Value } else { $null }}},"
            "@{Name='UserPrincipalName';Expression={$_.UserPrincipalName}},"
            "@{Name='SamAccountName';Expression={$_.SamAccountName}} | "
            "ConvertTo-Json -Compress -Depth 6"
        )
        users_payload = self._run_ps_json(session, users_ps)
        users = self._object_list(users_payload)

        user_keys: set[str] = set()
        sid_map: dict[str, str] = {}

        for user in users:
            # SID may be a string or a dict with a "Value" key (PowerShell serialization)
            sid_raw = user.get("SID")
            if isinstance(sid_raw, dict):
                sid_str = (sid_raw.get("Value") or "").strip()
            else:
                sid_str = (str(sid_raw) if sid_raw else "").strip()

            upn = (user.get("UserPrincipalName") or "").strip()
            sam = (user.get("SamAccountName") or "").strip()

            if sid_str:
                key = f"sid:{sid_str}"
            elif upn:
                key = f"upn:{upn}"
            elif sam:
                key = f"sam:{sam}"
            else:
                continue  # Skip users with no derivable key

            user_keys.add(key)
            if sid_str:
                sid_map[key] = sid_str

        return {"user_keys": user_keys, "sid_map": sid_map}

    # ------------------------------------------------------------------
    # Autodiscovery
    # ------------------------------------------------------------------

    def _discover_domains(self, session: Any) -> list[str]:
        """Discover domains in the forest via Get-ADForest."""
        ps = "(Get-ADForest -ErrorAction Stop).Domains | ConvertTo-Json -Compress"
        payload = self._run_ps_json(session, ps)
        items = self._string_list(payload) if payload is not None else []
        result: list[str] = []
        for item in items:
            if isinstance(item, dict):
                name = (item.get("Name") or "").strip().lower()
            else:
                name = str(item).strip().lower()
            if name:
                result.append(name)
        return result

    def _discover_dns_servers(self, session: Any, domain: str) -> list[str]:
        """Discover DNS-capable DCs in *domain* via Get-ADDomainController."""
        escaped = self._ps_single_quote(domain)
        ps = (
            f"Get-ADDomainController -Filter * -Server '{escaped}' -ErrorAction Stop | "
            "Where-Object { $_.HostName -and $_.IsDnsServer } | "
            "Select-Object -ExpandProperty HostName | "
            "ConvertTo-Json -Compress"
        )
        payload = self._run_ps_json(session, ps)
        items = self._string_list(payload) if payload is not None else []
        result: list[str] = []
        for item in items:
            if isinstance(item, dict):
                hostname = (item.get("HostName") or "").strip().lower()
            else:
                hostname = str(item).strip().lower()
            if hostname:
                result.append(hostname)
        return result

    def _resolve_targets(self) -> list[dict]:
        """Resolve the list of server-service targets for this collection run.

        Returns a list of dicts: [{"server": str, "services": set[str]}, ...]

        If autodiscover=False, builds targets from self.options.servers.
        If autodiscover=True, queries Get-ADForest then Get-ADDomainController
        via the discovery_server to find DCs.
        """
        opts = self.options
        targets: list[dict] = []

        if not opts.autodiscover:
            for server in opts.servers:
                targets.append({"server": server, "services": set(opts.services)})
            return targets

        # Autodiscovery path
        seed = opts.discovery_server or (opts.servers[0] if opts.servers else None)
        if not seed:
            raise ValueError(
                "autodiscover=True requires either discovery_server or at least one server."
            )
        session = self._build_session(seed)
        try:
            domains_payload = self._run_ps_json(
                session,
                "(Get-ADForest -ErrorAction Stop).Domains | ConvertTo-Json -Compress",
            )
        except Exception as exc:
            raise WinRMError(f"Autodiscovery failed on {seed}: {exc}") from exc

        # domains_payload may be a list of strings or list of dicts with Name key
        raw_domains = self._object_list(domains_payload) if isinstance(domains_payload, list) and domains_payload and isinstance(domains_payload[0], dict) else []
        if not raw_domains and isinstance(domains_payload, list):
            # list of strings
            domain_names = [str(d).strip().lower() for d in domains_payload if str(d).strip()]
        else:
            domain_names = [(d.get("Name") or "").strip().lower() for d in raw_domains if d.get("Name")]

        seen_servers: set[str] = set()
        for domain in domain_names:
            escaped = self._ps_single_quote(domain)
            dc_ps = (
                f"Get-ADDomainController -Filter * -Server '{escaped}' -ErrorAction Stop | "
                "Where-Object { $_.HostName -and $_.IsDnsServer } | "
                "Select-Object -ExpandProperty HostName | "
                "ConvertTo-Json -Compress"
            )
            try:
                dc_payload = self._run_ps_json(session, dc_ps)
            except WinRMError as exc:
                log.warning("DC discovery failed for domain %r: %s", domain, exc)
                continue

            dc_items = self._object_list(dc_payload) if isinstance(dc_payload, list) and dc_payload and isinstance(dc_payload[0], dict) else []
            if not dc_items and isinstance(dc_payload, list):
                dc_hostnames = [str(h).strip().lower() for h in dc_payload if str(h).strip()]
            else:
                dc_hostnames = [(d.get("HostName") or "").strip().lower() for d in dc_items if d.get("HostName")]

            for hostname in dc_hostnames:
                if hostname and hostname not in seen_servers:
                    seen_servers.add(hostname)
                    # DCs always get dns + user; dhcp only if requested
                    services: set[str] = {"dns", "user"}
                    if "dhcp" in opts.services:
                        services.add("dhcp")
                    targets.append({"server": hostname, "services": services})

        return targets

    # ------------------------------------------------------------------
    # Per-server collection
    # ------------------------------------------------------------------

    def _collect_server(self, server: str, session: Any) -> dict:
        """Run all requested service collections on *server* via *session*.

        Returns a result dict:
            {"server": str, "status": "ok"|"error", "dns": {...}|None,
             "dhcp": {...}|None, "users": {...}|None}
        """
        opts = self.options
        result: dict[str, Any] = {
            "server": server,
            "status": "ok",
            "dns": None,
            "dhcp": None,
            "users": None,
        }

        if "dns" in opts.services:
            try:
                result["dns"] = self._collect_dns(session)
            except Exception as exc:
                log.warning("DNS collection failed on %r: %s", server, exc)
                result["dns"] = None

        if "dhcp" in opts.services:
            try:
                result["dhcp"] = self._collect_dhcp(session)
            except Exception as exc:
                log.warning("DHCP collection failed on %r: %s", server, exc)
                result["dhcp"] = None

        if "user" in opts.services:
            try:
                result["users"] = self._collect_users(session)
            except Exception as exc:
                log.warning("User collection failed on %r: %s", server, exc)
                result["users"] = None

        return result

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def collect_all(self) -> list[dict]:
        """Collect data from all target DCs.

        Resolves targets, then iterates over servers calling _collect_server.
        DC-level failures are caught and recorded as error entries — collection
        continues for remaining DCs.

        Returns a list of per-DC result dicts:
            [{"server": str, "status": "ok"|"error", ...}, ...]
        """
        targets = self._resolve_targets()
        results: list[dict] = []

        for target_info in targets:
            server = target_info["server"]
            try:
                session = self._build_session(server)
                server_result = self._collect_server(server, session)
                # Ensure the result always carries the server name
                if "server" not in server_result:
                    server_result = {"server": server, **server_result}
                results.append(server_result)
            except WinRMError as exc:
                log.warning("DC %r unreachable: %s", server, exc)
                results.append(
                    {"server": server, "status": "error", "error": str(exc)}
                )
            except Exception as exc:
                log.warning("Unexpected error collecting from %r: %s", server, exc)
                results.append(
                    {"server": server, "status": "error", "error": str(exc)}
                )

        return results
