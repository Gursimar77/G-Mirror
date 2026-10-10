"""
Tests for G-Mirror diagnostics (non-network, unit-testable parts).
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from gmirror.diagnostics.network_checker import DiagnosticReport, DiagCheck, CheckResult


def test_report_summary_empty():
    report = DiagnosticReport()
    assert "0 passed" in report.summary()
    assert "0 warnings" in report.summary()
    assert "0 failed" in report.summary()


def test_report_summary_counts():
    report = DiagnosticReport(checks=[
        DiagCheck("A", CheckResult.OK, "OK"),
        DiagCheck("B", CheckResult.WARNING, "Warn"),
        DiagCheck("C", CheckResult.FAIL, "Fail"),
    ])
    s = report.summary()
    assert "1 passed" in s
    assert "1 warnings" in s
    assert "1 failed" in s


def test_report_to_text_no_sensitive_data():
    report = DiagnosticReport(checks=[
        DiagCheck("mDNS", CheckResult.OK, "Port available"),
    ])
    text = report.to_text()
    assert "password" not in text.lower()
    assert "private key" not in text.lower()
    assert "✓" in text
    assert "mDNS" in text


def test_check_result_enum_values():
    assert CheckResult.OK.value == "ok"
    assert CheckResult.WARNING.value == "warning"
    assert CheckResult.FAIL.value == "fail"
