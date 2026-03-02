"""NIOS Grid backup analysis package.

Public API:
- NiosConfig: Configuration dataclass for filter + migration split settings
- run_nios_analysis(): Full analysis pipeline (parse -> filter -> count -> scenarios -> output)
"""

from cloud_usage.nios.config import NiosConfig
from cloud_usage.nios.output import run_nios_analysis

__all__ = ["NiosConfig", "run_nios_analysis"]
