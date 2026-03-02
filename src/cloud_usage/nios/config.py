"""NIOS Grid analysis configuration module.

Provides NiosConfig — a frozen dataclass that bundles FilterConfig and
optional MigrationSplitConfig for the NIOS analysis pipeline.

NiosConfig.from_yaml() reads a YAML file with 'filter:' and 'migration_split:'
sections and constructs the appropriate typed dataclasses.

YAML structure:
    filter:                        # optional
      whitelist: [patterns...]     # default: []
      blacklist: [patterns...]     # default: []
      lease_states: [states...]    # default: [active]
    migration_split:               # optional; omit for no hybrid scenario
      niosx_members: [names...]    # default: []
      default_group: nios          # default: "nios"
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import yaml

from cloud_usage.nios.filter import FilterConfig
from cloud_usage.nios.scenarios import MigrationSplitConfig


@dataclass(frozen=True)
class NiosConfig:
    """Bundled configuration for a NIOS analysis run.

    Args:
        filter_config: Member whitelist/blacklist and lease state configuration.
            Defaults to no filtering with active-only lease states.
        split_config: Optional migration split assigning members to NIOS/NIOSX
            groups. None disables the hybrid UDDI scenario.
    """

    filter_config: FilterConfig = FilterConfig()
    split_config: Optional[MigrationSplitConfig] = None

    @classmethod
    def from_yaml(cls, path: str) -> "NiosConfig":
        """Load NiosConfig from a YAML file.

        Reads 'filter:' and 'migration_split:' sections from the YAML file.
        Missing sections use default dataclass values. Lists in YAML are
        converted to tuples for frozen dataclass compatibility.

        Args:
            path: Path to the YAML configuration file.

        Returns:
            NiosConfig with populated FilterConfig and optional MigrationSplitConfig.

        Raises:
            FileNotFoundError: If path does not exist.
            yaml.YAMLError: If the file contains invalid YAML.
        """
        with open(path, "r") as fh:
            data = yaml.safe_load(fh) or {}

        filter_section = data.get("filter") or {}
        filter_config = FilterConfig(
            whitelist=tuple(filter_section.get("whitelist") or []),
            blacklist=tuple(filter_section.get("blacklist") or []),
            lease_states=tuple(
                filter_section.get("lease_states") or ["active"]
            ),
        )

        split_section = data.get("migration_split") or {}
        split_config: Optional[MigrationSplitConfig] = None
        if split_section:
            split_config = MigrationSplitConfig(
                niosx_members=tuple(split_section.get("niosx_members") or []),
                default_group=split_section.get("default_group") or "nios",
                assignment_source="yaml",
            )

        return cls(filter_config=filter_config, split_config=split_config)
