import pytest

from membrane_vqc import commands, qc


def test_export_before_analysis_raises_clear_error():
    previous = qc.LAST_REPORT
    qc.LAST_REPORT = None
    try:
        with pytest.raises(RuntimeError, match="Run mvqc_check first"):
            commands.mvqc_export("unused.json")
    finally:
        qc.LAST_REPORT = previous
