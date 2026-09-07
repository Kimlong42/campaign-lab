import pytest

from campaign_lab import analysis as a
from campaign_lab import generate as g


def test_conversion_rates_match_planted(df):
    rates = a.conversion_by_arm(df)["rate"]
    assert rates.loc[0] == pytest.approx(0.100)
    assert rates.loc[1] == pytest.approx(0.132)


def test_ate_is_exact(df):
    assert a.ate(df) == pytest.approx(0.032)


def test_ate_is_significant(df):
    z, p = a.two_proportion_ztest(df)
    assert z > 0
    assert p < 0.01


def test_uplift_by_segment_matches_planted(df):
    tab = a.uplift_by_segment(df)
    for seg, rates in g.CONV_RATE.items():
        assert tab.loc[seg, "control"] == pytest.approx(rates[0])
        assert tab.loc[seg, "treatment"] == pytest.approx(rates[1])
    assert tab.loc["VIP", "uplift"] == pytest.approx(0.0)


def test_randomization_balanced(df):
    mix = a.check_randomization(df)
    assert (mix[0] - mix[1]).abs().max() < 1e-9


def test_refund_feedback_count(df):
    assert a.count_keyword(df, "refund") == g.N_REFUND_FEEDBACK


def test_rfm_scores_are_valid(df):
    rfm = a.rfm_scores(df)
    assert len(rfm) == len(df)
    for col in ("R", "F", "M"):
        assert rfm[col].between(1, 5).all()
    assert rfm["rfm_score"].between(3, 15).all()
