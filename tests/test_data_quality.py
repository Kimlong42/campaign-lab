from campaign_lab import analysis as a
from campaign_lab import generate as g


def test_row_count_includes_duplicates(raw):
    assert len(raw) == g.N_CUSTOMERS + g.N_DUPLICATES


def test_duplicates_detected(raw):
    assert len(a.find_duplicates(raw)) == g.N_DUPLICATES


def test_revenue_without_conversion_detected(raw):
    assert len(a.find_revenue_without_conversion(raw)) == g.N_REVENUE_WITHOUT_CONVERSION


def test_clean_removes_both_anomalies(df):
    assert len(df) == g.N_CUSTOMERS
    assert a.find_duplicates(df).empty
    assert a.find_revenue_without_conversion(df).empty


def test_arms_are_balanced(df):
    counts = df["treatment"].value_counts()
    assert counts[0] == counts[1] == g.N_CUSTOMERS // 2
