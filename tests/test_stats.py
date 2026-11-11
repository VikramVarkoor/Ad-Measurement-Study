"""Known-answer tests: every expected value below was computed by hand first."""
import numpy as np
import pytest

from src import stats as st


class TestTwoProportionLift:
    # 30/200 treated vs 20/200 control, all arithmetic done by hand
    def setup_method(self):
        self.r = st.two_proportion_lift(30, 200, 20, 200)

    def test_rates_and_lift(self):
        assert self.r["rate_treated"] == pytest.approx(0.15)
        assert self.r["rate_control"] == pytest.approx(0.10)
        assert self.r["abs_lift"] == pytest.approx(0.05)
        assert self.r["rel_lift"] == pytest.approx(0.50)
        assert self.r["incremental_conversions"] == pytest.approx(10.0)

    def test_interval_by_hand(self):
        # SE = sqrt(.15*.85/200 + .10*.90/200) = sqrt(0.0010875)
        assert self.r["se"] == pytest.approx(0.0329773, abs=1e-6)
        assert self.r["ci_low"] == pytest.approx(0.05 - 1.959964 * 0.0329773, abs=1e-6)
        assert self.r["ci_high"] == pytest.approx(0.05 + 1.959964 * 0.0329773, abs=1e-6)

    def test_z_and_p_by_hand(self):
        # pooled p = 50/400 = .125; SE = sqrt(.125*.875*(2/200)) = 0.0330719
        assert self.r["z"] == pytest.approx(0.05 / 0.0330719, abs=1e-4)
        assert self.r["p_value"] == pytest.approx(0.1306, abs=1e-3)

    def test_input_validation(self):
        with pytest.raises(ValueError):
            st.two_proportion_lift(5, 0, 1, 10)
        with pytest.raises(ValueError):
            st.two_proportion_lift(11, 10, 1, 10)


class TestBootstrap:
    def test_deterministic_with_seed(self):
        a = st.bootstrap_lift_ci(30, 200, 20, 200, seed=42)
        b = st.bootstrap_lift_ci(30, 200, 20, 200, seed=42)
        assert a == b

    def test_agrees_with_analytic_at_scale(self):
        # With large n the percentile bootstrap must track the Wald interval.
        r = st.two_proportion_lift(3000, 100000, 2500, 100000)
        lo, hi = st.bootstrap_lift_ci(3000, 100000, 2500, 100000, n_boot=4000)
        assert lo == pytest.approx(r["ci_low"], abs=3e-4)
        assert hi == pytest.approx(r["ci_high"], abs=3e-4)


class TestSRM:
    def test_perfect_split(self):
        r = st.srm_check(850, 150, 0.85)
        assert r["chi2"] == pytest.approx(0.0)
        assert r["p_value"] == pytest.approx(1.0)
        assert not r["mismatch"]

    def test_broken_split_by_hand(self):
        # (800-850)^2/850 + (200-150)^2/150 = 2.94118 + 16.66667 = 19.60784
        r = st.srm_check(800, 200, 0.85)
        assert r["chi2"] == pytest.approx(19.60784, abs=1e-4)
        assert r["mismatch"]


class TestMDE:
    def test_by_hand(self):
        # SE = sqrt(.1*.9*(1/1000+1/1000)) = 0.0134164
        # MDE = (1.959964 + 0.841621) * SE = 0.0375877
        assert st.minimum_detectable_effect(1000, 1000, 0.10) == pytest.approx(
            0.0375877, abs=1e-5
        )

    def test_more_users_smaller_mde(self):
        big = st.minimum_detectable_effect(100000, 100000, 0.10)
        small = st.minimum_detectable_effect(1000, 1000, 0.10)
        assert big < small


class TestCUPED:
    def test_recovers_slope_and_cuts_variance(self):
        rng = np.random.default_rng(0)
        x = rng.normal(100, 20, size=20000)
        y = 2.0 * x + rng.normal(0, 5, size=20000)
        adj, theta = st.cuped_adjust(y, x)
        assert theta == pytest.approx(2.0, abs=0.02)
        assert adj.var() < 0.05 * y.var()  # most variance was predictable

    def test_mean_is_preserved(self):
        rng = np.random.default_rng(1)
        x = rng.normal(0, 1, 5000)
        y = x + rng.normal(0, 1, 5000)
        adj, _ = st.cuped_adjust(y, x)
        assert adj.mean() == pytest.approx(y.mean(), abs=1e-9)

    def test_constant_covariate_is_noop(self):
        y = np.array([1.0, 2.0, 3.0])
        adj, theta = st.cuped_adjust(y, np.ones(3))
        assert theta == 0.0
        assert np.allclose(adj, y)


class TestBH:
    def test_constructed_example(self):
        # thresholds at q=.1, m=4: .025 .05 .075 .1 -> first three pass
        sig = st.benjamini_hochberg([0.01, 0.02, 0.03, 0.5], q=0.10)
        assert sig.tolist() == [True, True, True, False]

    def test_nothing_significant(self):
        sig = st.benjamini_hochberg([0.5, 0.8, 0.9], q=0.10)
        assert not sig.any()

    def test_order_independent(self):
        sig = st.benjamini_hochberg([0.5, 0.03, 0.01, 0.02], q=0.10)
        assert sig.tolist() == [False, True, True, True]
