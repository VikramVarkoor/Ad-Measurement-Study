"""Known-answer tests for the stretch goals: forecast, scoring API,
summary verifier."""
import numpy as np
import pandas as pd
import pytest

from src import paths
from src.forecast import make_features, mean4_forecast, naive_forecast


# ------------------------------------------------------------- forecast
def test_naive_and_mean4_hand_computed():
    s = pd.Series([10.0, 20.0, 30.0, 40.0, 50.0],
                  index=pd.date_range("2024-01-01", periods=5, freq="W"))
    assert naive_forecast(s) == 50.0
    assert mean4_forecast(s) == (20 + 30 + 40 + 50) / 4


def test_features_use_only_the_past():
    s = pd.Series(np.arange(12, dtype=float),
                  index=pd.date_range("2024-01-01", periods=12, freq="W"))
    f = make_features(s)
    # lag1 of week i is the value at week i-1
    assert f["lag1"].iloc[5] == s.iloc[4]
    # roll4 at week i averages weeks i-4..i-1, never week i
    assert f["roll4"].iloc[8] == s.iloc[4:8].mean()
    assert np.isnan(f["lag4"].iloc[3])


def test_backtest_scores_match_hand_computation():
    from src.forecast import score
    bt = pd.DataFrame({
        "actual": [100.0, 200.0],
        "naive": [110.0, 190.0],
        "mean4": [100.0, 200.0],
        "lightgbm": [90.0, 210.0],
        "lightgbm_lo": [80.0, 150.0],
        "lightgbm_hi": [95.0, 260.0],
    })
    sc = score(bt).set_index("model")
    assert sc.loc["naive", "mae"] == 10.0
    assert sc.loc["mean4", "mae"] == 0.0
    assert sc.loc["lightgbm", "mae"] == 10.0
    # actual outside [lo, hi] in week 1, inside in week 2 -> 50%
    assert sc.loc["lightgbm", "interval_coverage_pct"] == 50.0


# ------------------------------------------------------------- API
def test_scoring_api_health_and_score():
    fastapi = pytest.importorskip("fastapi")  # noqa: F841
    from fastapi.testclient import TestClient

    if not (paths.MODELS / "criteo_treated.txt").exists():
        pytest.skip("models not built")
    from api.main import app
    client = TestClient(app)
    assert client.get("/health").json()["status"] == "ok"
    payload = {f"f{i}": 0.0 for i in range(12)}
    out = client.post("/score", json=payload).json()
    assert set(out) >= {"uplift_score", "decile", "in_top_20pct"}
    assert 1 <= out["decile"] <= 10
    assert out["in_top_20pct"] == (out["decile"] <= 2)


# ------------------------------------------------------------- verifier
def test_summary_verifier_catches_a_wrong_number(tmp_path, monkeypatch):
    from src import verify_summary

    reports = tmp_path / "reports"
    results = tmp_path / "results"
    reports.mkdir(); results.mkdir()
    monkeypatch.setattr(paths, "REPORTS", reports)
    monkeypatch.setattr(verify_summary.paths, "REPORTS", reports)
    monkeypatch.setattr(verify_summary.paths, "RESULTS", results)

    pd.DataFrame({"rr": [1.32]}).to_csv(results / "meta_results.csv",
                                        index=False)
    pd.DataFrame([{"text": "1.32", "value": 1.32,
                   "source": "meta_results.csv", "column": "rr"}]
                 ).to_csv(reports / "summary_claims.csv", index=False)

    # correct text passes
    (reports / "findings_summary.md").write_text(
        "The pooled risk ratio is 1.32.")
    report = verify_summary.verify()
    assert (report.status == "PASS").all()

    # a hallucinated number fails the sweep
    (reports / "findings_summary.md").write_text(
        "The pooled risk ratio is 1.45.")
    with pytest.raises(AssertionError):
        verify_summary.verify()
