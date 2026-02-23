"""
Audit trail logger for cloud discovery scans.

Every scan writes a timestamped debug-level log file to the output directory.
The log captures all API calls, responses, timing, errors, and retries.
No redaction is applied -- full account IDs, ARNs, and resource names are
included (this is a local-only tool where data stays on the customer machine).
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path


# Third-party loggers that produce excessive output at DEBUG level.
_NOISY_LOGGERS = (
    "boto3",
    "botocore",
    "urllib3",
    "azure",
    "azure.core",
    "azure.identity",
    "azure.mgmt",
    "google",
    "google.auth",
    "google.api_core",
)


def setup_audit_logger(output_dir: str, scan_id: str | None = None) -> logging.Logger:
    """Configure and return an audit logger that writes to a file.

    Creates the output directory if it doesn't exist, generates a timestamped
    log file, and configures DEBUG-level file logging. Noisy third-party
    loggers (boto3, botocore, azure, google) are suppressed to WARNING level.

    Args:
        output_dir: Directory where the log file will be written.
        scan_id: Optional scan identifier included in the log filename.
            If None, the filename uses only the timestamp.

    Returns:
        A configured logging.Logger instance writing to the audit log file.
    """
    # Ensure output directory exists
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Generate log filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if scan_id:
        log_filename = f"scan_{scan_id}_{timestamp}.log"
    else:
        log_filename = f"scan_{timestamp}.log"

    log_file_path = output_path / log_filename

    # Configure the audit logger with a unique name per scan
    logger_name = f"cloud_usage.audit.{scan_id or timestamp}"
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)

    # Remove any existing handlers to ensure the logger writes to the
    # correct output directory (each scan gets its own log file).
    for handler in logger.handlers[:]:
        handler.close()
        logger.removeHandler(handler)

    file_handler = logging.FileHandler(str(log_file_path), encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Suppress noisy third-party loggers to WARNING
    for noisy_logger_name in _NOISY_LOGGERS:
        logging.getLogger(noisy_logger_name).setLevel(logging.WARNING)

    return logger
