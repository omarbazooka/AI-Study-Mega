import pytest
import os
import sys

def test_report_fails_on_missing_results():
    # Attempting to run report generation when results do not exist should raise SystemExit (exit code 1)
    # We patch sys.exit to verify it behaves correctly
    with pytest.raises(SystemExit) as exc_info:
        # Import and run report compiler function
        from evaluation.reporting.generate_evaluation_report import generate_report
        generate_report()
        
    assert exc_info.value.code == 1
