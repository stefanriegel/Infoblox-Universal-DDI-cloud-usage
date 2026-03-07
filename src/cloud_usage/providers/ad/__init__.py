"""Microsoft Active Directory provider package.

Public API:
- AdOptions: configuration dataclass for AD scan
- run_ad_analysis(): full AD scan pipeline

All names are re-exported at package level so tests can patch them
at the `cloud_usage.providers.ad` namespace.
"""

from cloud_usage.providers.ad.options import AdOptions
from cloud_usage.providers.ad.collector import MicrosoftAdCollector
from cloud_usage.output.xlsx_report import write_xlsx_report
from cloud_usage.providers.ad.runner import run_ad_analysis

__all__ = [
    "AdOptions",
    "MicrosoftAdCollector",
    "run_ad_analysis",
    "write_xlsx_report",
]
