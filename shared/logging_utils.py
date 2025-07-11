"""
Logging utilities for Infoblox Universal DDI Resource Counter.
"""

import logging
import sys
from typing import Optional

from .constants import LOGGING_CONFIG


def setup_logging(
    level: str = "WARNING",
    format_string: Optional[str] = None,
    suppress_modules: Optional[list] = None,
) -> logging.Logger:
    """
    Set up logging configuration for the application.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format_string: Custom format string for log messages
        suppress_modules: List of module names to suppress logging for
        
    Returns:
        Configured logger instance
    """
    # Use default config if not provided
    if format_string is None:
        format_string = LOGGING_CONFIG["format"]
    
    if suppress_modules is None:
        suppress_modules = LOGGING_CONFIG["suppress_modules"]
    
    # Ensure format_string is not None
    if format_string is None:
        format_string = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # Ensure suppress_modules is not None
    if suppress_modules is None:
        suppress_modules = []
    
    # Configure basic logging
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format=format_string,
        stream=sys.stdout,
    )
    
    # Suppress noisy modules
    for module in suppress_modules:
        logging.getLogger(module).setLevel(logging.ERROR)
    
    return logging.getLogger(__name__)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a specific module.
    
    Args:
        name: Logger name (usually __name__)
        
    Returns:
        Logger instance
    """
    return logging.getLogger(name)


class DiscoveryLogger:
    """Context manager for discovery logging."""
    
    def __init__(self, logger: logging.Logger, operation: str):
        """
        Initialize the discovery logger.
        
        Args:
            logger: Logger instance
            operation: Operation being performed
        """
        self.logger = logger
        self.operation = operation
    
    def __enter__(self):
        """Log start of operation."""
        self.logger.info("Starting %s", self.operation)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Log completion or error of operation."""
        if exc_type is None:
            self.logger.info("Completed %s successfully", self.operation)
        else:
            self.logger.error("Failed %s: %s", self.operation, exc_val)
    
    def log_progress(self, current: int, total: int, description: str = "Progress"):
        """Log progress information."""
        percentage = (current / total) * 100 if total > 0 else 0
        self.logger.info("%s: %d/%d (%.1f%%)", description, current, total, percentage)
    
    def log_discovery_result(self, resource_type: str, count: int, region: str = "unknown"):
        """Log discovery results for a specific resource type."""
        self.logger.info(
            "Discovered %d %s resources in %s", count, resource_type, region
        )
    
    def log_token_calculation(self, ddi_tokens: int, ip_tokens: int, asset_tokens: int, total_tokens: int):
        """Log token calculation results."""
        self.logger.info(
            "Token calculation: DDI=%d, IPs=%d, Assets=%d, Total=%d",
            ddi_tokens, ip_tokens, asset_tokens, total_tokens
        ) 