"""
Tests for error taxonomy classification, error records, and audit logger.
"""

from __future__ import annotations

import logging
import os
import sys
import tempfile
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cloud_usage.errors.taxonomy import (
    CATEGORY_STRATEGIES,
    ErrorCategory,
    ErrorRecord,
    classify_error,
    create_error_record,
)
from cloud_usage.logging.audit import setup_audit_logger


# -- Custom exception classes for testing classification --


class CredentialError(Exception):
    """Simulates an auth credential error."""


class AccessDeniedException(Exception):
    """Simulates an access denied error."""


class PermissionError(Exception):
    """Simulates a permission error."""


class ThrottlingException(Exception):
    """Simulates a rate limit/throttling error."""


class TimeoutError(Exception):
    """Simulates a network timeout error."""


class ConnectionError(Exception):
    """Simulates a network connection error."""


class SocketError(Exception):
    """Simulates a socket error."""


class NotSupportedException(Exception):
    """Simulates an unsupported API error."""


class TestClassifyErrorAuth:
    """Test classify_error returns AUTH for authentication-related exceptions."""

    def test_credential_error_by_type_name(self):
        """CredentialError classified as AUTH based on type name."""
        exc = CredentialError("credentials expired")
        assert classify_error("aws", exc) == ErrorCategory.AUTH

    def test_access_denied_by_type_name(self):
        """AccessDeniedException classified as AUTH based on type name."""
        exc = AccessDeniedException("access denied to resource")
        assert classify_error("azure", exc) == ErrorCategory.AUTH

    def test_permission_error_by_type_name(self):
        """PermissionError classified as AUTH based on type name."""
        exc = PermissionError("insufficient permissions")
        assert classify_error("gcp", exc) == ErrorCategory.AUTH

    def test_forbidden_in_message(self):
        """Generic exception with 'forbidden' in message classified as AUTH."""
        exc = Exception("HTTP 403 Forbidden: access to this resource is forbidden")
        assert classify_error("aws", exc) == ErrorCategory.AUTH

    def test_unauthorized_in_message(self):
        """Generic exception with 'unauthorized' in message classified as AUTH."""
        exc = Exception("Request unauthorized: invalid token")
        assert classify_error("azure", exc) == ErrorCategory.AUTH

    def test_access_denied_in_message(self):
        """Generic exception with 'AccessDenied' in message classified as AUTH."""
        exc = Exception("An error occurred (AccessDenied) when calling ListBuckets")
        assert classify_error("aws", exc) == ErrorCategory.AUTH

    def test_403_in_message(self):
        """Generic exception with '403' in message classified as AUTH."""
        exc = Exception("HTTP Error 403: Forbidden")
        assert classify_error("gcp", exc) == ErrorCategory.AUTH


class TestClassifyErrorRateLimit:
    """Test classify_error returns RATE_LIMIT for throttling exceptions."""

    def test_throttling_by_type_name(self):
        """ThrottlingException classified as RATE_LIMIT based on type name."""
        exc = ThrottlingException("request rate exceeded")
        assert classify_error("aws", exc) == ErrorCategory.RATE_LIMIT

    def test_429_in_message(self):
        """Exception with '429' in message classified as RATE_LIMIT."""
        exc = Exception("HTTP 429: Too Many Requests")
        assert classify_error("azure", exc) == ErrorCategory.RATE_LIMIT

    def test_too_many_requests_in_message(self):
        """Exception with 'too many requests' in message classified as RATE_LIMIT."""
        exc = Exception("too many requests, please retry after 5 seconds")
        assert classify_error("gcp", exc) == ErrorCategory.RATE_LIMIT

    def test_retry_after_in_message(self):
        """Exception with 'retry-after' in message classified as RATE_LIMIT."""
        exc = Exception("Rate limited. Retry-After: 30")
        assert classify_error("aws", exc) == ErrorCategory.RATE_LIMIT

    def test_rate_in_message(self):
        """Exception with 'rate' in message classified as RATE_LIMIT."""
        exc = Exception("API rate limit exceeded for account 123")
        assert classify_error("aws", exc) == ErrorCategory.RATE_LIMIT


class TestClassifyErrorNetwork:
    """Test classify_error returns NETWORK for connectivity exceptions."""

    def test_timeout_by_type_name(self):
        """TimeoutError classified as NETWORK based on type name."""
        exc = TimeoutError("connection timed out after 30s")
        assert classify_error("aws", exc) == ErrorCategory.NETWORK

    def test_connection_by_type_name(self):
        """ConnectionError classified as NETWORK based on type name."""
        exc = ConnectionError("could not connect to endpoint")
        assert classify_error("azure", exc) == ErrorCategory.NETWORK

    def test_socket_by_type_name(self):
        """SocketError classified as NETWORK based on type name."""
        exc = SocketError("socket connection reset")
        assert classify_error("gcp", exc) == ErrorCategory.NETWORK

    def test_timeout_in_message(self):
        """Generic exception with 'timeout' in message classified as NETWORK."""
        exc = Exception("Connection timeout after 30 seconds")
        assert classify_error("aws", exc) == ErrorCategory.NETWORK

    def test_dns_resolve_in_message(self):
        """Generic exception with 'resolve' in message classified as NETWORK."""
        exc = Exception("Failed to resolve hostname ec2.us-east-1.amazonaws.com")
        assert classify_error("aws", exc) == ErrorCategory.NETWORK


class TestClassifyErrorApi:
    """Test classify_error returns API for unsupported operation exceptions."""

    def test_not_supported_by_type_name(self):
        """NotSupportedException classified as API based on type name."""
        exc = NotSupportedException("operation not available in this region")
        assert classify_error("aws", exc) == ErrorCategory.API

    def test_not_found_in_message(self):
        """Exception with 'not found' in message classified as API."""
        exc = Exception("Resource not found in region eu-west-1")
        assert classify_error("azure", exc) == ErrorCategory.API

    def test_404_in_message(self):
        """Exception with '404' in message classified as API."""
        exc = Exception("HTTP 404: endpoint does not exist")
        assert classify_error("gcp", exc) == ErrorCategory.API

    def test_invalid_in_message(self):
        """Exception with 'invalid' in message classified as API."""
        exc = Exception("Invalid parameter: region 'mars-1' is not valid")
        assert classify_error("aws", exc) == ErrorCategory.API


class TestClassifyErrorUnknown:
    """Test classify_error returns UNKNOWN for unrecognized exceptions."""

    def test_generic_exception(self):
        """Plain Exception with no matching keywords classified as UNKNOWN."""
        exc = Exception("something went wrong")
        assert classify_error("aws", exc) == ErrorCategory.UNKNOWN

    def test_runtime_error(self):
        """RuntimeError with no matching keywords classified as UNKNOWN."""
        exc = RuntimeError("unexpected internal state")
        assert classify_error("azure", exc) == ErrorCategory.UNKNOWN

    def test_value_error(self):
        """ValueError with no matching keywords classified as UNKNOWN."""
        exc = ValueError("bad data format")
        assert classify_error("gcp", exc) == ErrorCategory.UNKNOWN


class TestCreateErrorRecord:
    """Test create_error_record builds complete ErrorRecord with correct suggestion."""

    def test_auth_error_record(self):
        """Auth error record has correct suggestion and retryable=False."""
        exc = CredentialError("AWS SSO token expired")
        record = create_error_record("aws", "123456789012", exc)
        assert record.provider == "aws"
        assert record.account_id == "123456789012"
        assert record.category == ErrorCategory.AUTH
        assert record.retryable is False
        assert "credentials" in record.suggestion.lower()
        assert "AWS SSO token expired" in record.message

    def test_rate_limit_error_record(self):
        """Rate limit error record has correct suggestion and retryable=True."""
        exc = ThrottlingException("too many requests")
        record = create_error_record("azure", "sub-abc-123", exc)
        assert record.category == ErrorCategory.RATE_LIMIT
        assert record.retryable is True
        assert "retry" in record.suggestion.lower()

    def test_network_error_record(self):
        """Network error record has correct suggestion and retryable=True."""
        exc = ConnectionError("connection refused")
        record = create_error_record("gcp", "project-1", exc)
        assert record.category == ErrorCategory.NETWORK
        assert record.retryable is True
        assert "network" in record.suggestion.lower()

    def test_api_error_record(self):
        """API error record has correct suggestion and retryable=False."""
        exc = NotSupportedException("not available in region")
        record = create_error_record("aws", "123456", exc)
        assert record.category == ErrorCategory.API
        assert record.retryable is False
        assert "region" in record.suggestion.lower()

    def test_unknown_error_record(self):
        """Unknown error record has correct suggestion and retryable=False."""
        exc = RuntimeError("unexpected failure")
        record = create_error_record("aws", "123456", exc)
        assert record.category == ErrorCategory.UNKNOWN
        assert record.retryable is False
        assert "log file" in record.suggestion.lower()

    def test_error_record_has_raw_exception(self):
        """ErrorRecord captures repr() of the original exception."""
        exc = CredentialError("token expired")
        record = create_error_record("aws", "123456", exc)
        assert "CredentialError" in record.raw_exception
        assert "token expired" in record.raw_exception


class TestCategoryStrategies:
    """Test CATEGORY_STRATEGIES completeness and structure."""

    def test_strategy_for_every_category(self):
        """CATEGORY_STRATEGIES has an entry for every ErrorCategory value."""
        for category in ErrorCategory:
            assert category in CATEGORY_STRATEGIES, f"Missing strategy for {category}"

    def test_strategy_keys(self):
        """Each strategy has retryable, max_retries, and description keys."""
        for category, strategy in CATEGORY_STRATEGIES.items():
            assert "retryable" in strategy, f"Missing 'retryable' for {category}"
            assert "max_retries" in strategy, f"Missing 'max_retries' for {category}"
            assert "description" in strategy, f"Missing 'description' for {category}"

    def test_retryable_types(self):
        """Retryable field is boolean for all strategies."""
        for category, strategy in CATEGORY_STRATEGIES.items():
            assert isinstance(strategy["retryable"], bool), f"retryable not bool for {category}"

    def test_max_retries_types(self):
        """max_retries field is int for all strategies."""
        for category, strategy in CATEGORY_STRATEGIES.items():
            assert isinstance(strategy["max_retries"], int), f"max_retries not int for {category}"


class TestErrorRecordTimestamp:
    """Test ErrorRecord timestamp auto-population."""

    def test_timestamp_auto_populated(self):
        """ErrorRecord timestamp is automatically set when not provided."""
        record = ErrorRecord(
            provider="aws",
            account_id="123456",
            category=ErrorCategory.UNKNOWN,
            message="test error",
            raw_exception="Exception('test')",
            retryable=False,
            suggestion="test suggestion",
        )
        assert record.timestamp is not None
        assert len(record.timestamp) > 0
        assert "T" in record.timestamp

    def test_timestamp_can_be_overridden(self):
        """ErrorRecord timestamp can be explicitly set."""
        record = ErrorRecord(
            provider="aws",
            account_id="123456",
            category=ErrorCategory.UNKNOWN,
            message="test error",
            raw_exception="Exception('test')",
            retryable=False,
            suggestion="test suggestion",
            timestamp="2026-01-01T00:00:00",
        )
        assert record.timestamp == "2026-01-01T00:00:00"


class TestAuditLogger:
    """Test audit logger setup and file creation."""

    def test_creates_output_directory(self):
        """setup_audit_logger creates the output directory if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            nested_dir = os.path.join(tmpdir, "logs", "audit")
            logger = setup_audit_logger(nested_dir)
            assert os.path.isdir(nested_dir)

    def test_creates_log_file_without_scan_id(self):
        """Log file is created with timestamp-only name when no scan_id."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = setup_audit_logger(tmpdir)
            log_files = list(Path(tmpdir).glob("scan_*.log"))
            assert len(log_files) == 1
            assert "scan_" in log_files[0].name

    def test_creates_log_file_with_scan_id(self):
        """Log file includes scan_id in filename when provided."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = setup_audit_logger(tmpdir, scan_id="test-run-001")
            log_files = list(Path(tmpdir).glob("scan_test-run-001_*.log"))
            assert len(log_files) == 1

    def test_logger_writes_debug_messages(self):
        """Logger writes DEBUG-level messages to the log file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = setup_audit_logger(tmpdir, scan_id="debug-test")
            logger.debug("Test debug message for audit trail")
            logger.info("Test info message for audit trail")

            # Flush handlers to ensure writing
            for handler in logger.handlers:
                handler.flush()

            log_files = list(Path(tmpdir).glob("scan_debug-test_*.log"))
            assert len(log_files) == 1
            content = log_files[0].read_text()
            assert "Test debug message for audit trail" in content
            assert "Test info message for audit trail" in content

    def test_logger_format(self):
        """Logger output follows the expected format with timestamp and level."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = setup_audit_logger(tmpdir, scan_id="format-test")
            logger.info("Format check message")

            for handler in logger.handlers:
                handler.flush()

            log_files = list(Path(tmpdir).glob("scan_format-test_*.log"))
            content = log_files[0].read_text()
            # Format: "YYYY-MM-DD HH:MM:SS [LEVEL] name: message"
            assert "[INFO]" in content
            assert "Format check message" in content

    def test_suppresses_noisy_loggers(self):
        """Noisy third-party loggers are set to WARNING level."""
        with tempfile.TemporaryDirectory() as tmpdir:
            setup_audit_logger(tmpdir)
            assert logging.getLogger("boto3").level == logging.WARNING
            assert logging.getLogger("botocore").level == logging.WARNING
            assert logging.getLogger("azure").level == logging.WARNING
            assert logging.getLogger("google").level == logging.WARNING

    def test_logger_level_is_debug(self):
        """Audit logger is configured at DEBUG level."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = setup_audit_logger(tmpdir)
            assert logger.level == logging.DEBUG
