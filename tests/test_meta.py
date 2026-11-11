"""Known-answer tests for the meta-analysis module, all worked by hand."""
import numpy as np
import pandas as pd
import pytest

from src import meta


class TestLogRR:
    def test_by_hand(self):
        # RR = .15/.10 = 1.5; var = 1/30 - 1/200 + 1/20 - 1/200 = 0.0733333
        log_rr, var = meta.log_risk_ratio(30, 200, 20, 200)
        assert log_rr == pytest.approx(np.log(1.5), abs=1e-9)
        assert var == pytest.approx(0.0733333, abs=1e-6)

    def test_zero_cell_continuity_correction(self):
        log_rr, var = meta.log_risk_ratio(0, 100, 5, 100)
        assert np.isfinite(log_rr) and np.isfinite(var)
        assert log_rr < 0  # treated had fewer events


class TestFixedEffect:
    def test_equal_weights_is_plain_mean(self):
        fe = meta.fixed_effect(np.array([0.1, 0.3]), np.array([0.04, 0.04]))
        assert fe["estimate"] == pytest.approx(0.2)
        assert fe["se"] == pytest.approx(np.sqrt(0.02), abs=1e-9)

    def test_precision_weighting(self):
        # weights 100 and 1: estimate pulled almost entirely to the first study
        fe = meta.fixed_effect(np.array([0.0, 1.0]), np.array([0.01, 1.0]))
        assert fe["estimate"] == pytest.approx(1 / 101, abs=1e-9)


class TestHeterogeneityAndDL:
    def test_agreeing_studies(self):
        # effects .1/.3, var .04 each: Q = 25*(.01+.01) = 0.5 < df -> I2 = 0, tau2 = 0
        het = meta.heterogeneity(np.array([0.1, 0.3]), np.array([0.04, 0.04]))
        assert het["Q"] == pytest.approx(0.5)
        assert het["I2"] == 0.0
        re = meta.dersimonian_laird(np.array([0.1, 0.3]), np.array([0.04, 0.04]))
        assert re["tau2"] == 0.0
        assert re["estimate"] == pytest.approx(0.2)  # falls back to fixed effect

    def test_disagreeing_studies_by_hand(self):
        # effects 0/.5, var .01: Q = 100*(.0625+.0625) = 12.5, I2 = 11.5/12.5 = .92
        # c = 200 - 20000/200 = 100 -> tau2 = 11.5/100 = 0.115
        # w* = 1/.125 = 8 each -> est = .25, se = sqrt(1/16) = .25
        re = meta.dersimonian_laird(np.array([0.0, 0.5]), np.array([0.01, 0.01]))
        assert re["Q"] == pytest.approx(12.5)
        assert re["I2"] == pytest.approx(0.92)
        assert re["tau2"] == pytest.approx(0.115)
        assert re["estimate"] == pytest.approx(0.25)
        assert re["se"] == pytest.approx(0.25)

    def test_random_interval_never_narrower_than_fixed(self):
        eff = np.array([0.0, 0.2, 0.6])
        var = np.array([0.01, 0.02, 0.01])
        fe = meta.fixed_effect(eff, var)
        re = meta.dersimonian_laird(eff, var)
        assert re["se"] >= fe["se"]


class TestLeaveOneOut:
    def test_dominant_study_moves_the_pool(self):
        studies = pd.DataFrame({
            "study": ["huge", "small_a", "small_b"],
            "log_rr": [0.05, 0.60, 0.55],
            "var": [0.0001, 0.04, 0.04],
        })
        loo = meta.leave_one_out(studies)
        dropped_huge = loo[loo["dropped"] == "huge"]["fixed_rr"].iloc[0]
        dropped_small = loo[loo["dropped"] == "small_a"]["fixed_rr"].iloc[0]
        # dropping the huge study frees the pooled estimate to jump up
        assert dropped_huge > 1.5
        assert dropped_small < 1.1
        assert len(loo) == 3
