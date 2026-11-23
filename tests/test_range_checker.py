"""Unit tests for the deterministic range comparison logic.

Run from the project root:  python -m pytest tests -v
"""

from analysis import range_checker as rc
from extraction.models import BloodTest, ReferenceInterval


def interval(minimum=None, maximum=None, unit=None, condition=None):
    return ReferenceInterval(
        minimum=minimum, maximum=maximum, unit=unit, condition=condition
    )


def blood_test(value=None, value_text=None, unit=None, intervals=None):
    return BloodTest(
        test_name="Demo Test",
        value=value,
        value_text=value_text,
        unit=unit,
        reference_intervals=intervals or [],
    )


# --------------------------------------------------------------------------- #
# Core LOW / NORMAL / HIGH classification
# --------------------------------------------------------------------------- #
def test_value_below_minimum_is_low():
    result = rc.check_test(blood_test(value=10.5, intervals=[interval(12.0, 16.0)]))
    assert result.status == rc.STATUS_LOW


def test_value_above_maximum_is_high():
    result = rc.check_test(blood_test(value=13.8, intervals=[interval(4.0, 11.0)]))
    assert result.status == rc.STATUS_HIGH


def test_value_inside_range_is_normal():
    result = rc.check_test(blood_test(value=92, intervals=[interval(70, 100)]))
    assert result.status == rc.STATUS_NORMAL


def test_value_equal_to_minimum_boundary_is_normal():
    result = rc.check_test(blood_test(value=12.0, intervals=[interval(12.0, 16.0)]))
    assert result.status == rc.STATUS_NORMAL


def test_value_equal_to_maximum_boundary_is_normal():
    result = rc.check_test(blood_test(value=100.0, intervals=[interval(70.0, 100.0)]))
    assert result.status == rc.STATUS_NORMAL


# --------------------------------------------------------------------------- #
# Open-ended reference ranges
# --------------------------------------------------------------------------- #
def test_open_ended_maximum_only_high():
    result = rc.check_test(blood_test(value=216, intervals=[interval(None, 200)]))
    assert result.status == rc.STATUS_HIGH


def test_open_ended_maximum_only_normal():
    result = rc.check_test(blood_test(value=150, intervals=[interval(None, 200)]))
    assert result.status == rc.STATUS_NORMAL


def test_open_ended_minimum_only_low():
    result = rc.check_test(blood_test(value=45, intervals=[interval(60, None)]))
    assert result.status == rc.STATUS_LOW


def test_open_ended_minimum_only_normal():
    result = rc.check_test(blood_test(value=75, intervals=[interval(60, None)]))
    assert result.status == rc.STATUS_NORMAL


# --------------------------------------------------------------------------- #
# Missing / qualitative / invalid values
# --------------------------------------------------------------------------- #
def test_no_reference_range_is_not_evaluated():
    result = rc.check_test(blood_test(value=22.4))
    assert result.status == rc.STATUS_NOT_EVALUATED
    assert "no reference range" in result.reason


def test_missing_value_is_not_evaluated():
    result = rc.check_test(blood_test(intervals=[interval(1, 2)]))
    assert result.status == rc.STATUS_NOT_EVALUATED


def test_qualitative_result_is_not_evaluated():
    result = rc.check_test(blood_test(value_text="Negative"))
    assert result.status == rc.STATUS_NOT_EVALUATED
    assert "qualitative" in result.reason


def test_nan_value_is_not_evaluated():
    result = rc.check_test(
        blood_test(value=float("nan"), intervals=[interval(1, 2)])
    )
    assert result.status == rc.STATUS_NOT_EVALUATED


def test_interval_with_no_bounds_counts_as_missing_range():
    result = rc.check_test(blood_test(value=5.0, intervals=[interval(None, None)]))
    assert result.status == rc.STATUS_NOT_EVALUATED


# --------------------------------------------------------------------------- #
# Units
# --------------------------------------------------------------------------- #
def test_incompatible_units_need_review():
    result = rc.check_test(
        blood_test(value=10.5, unit="g/dL", intervals=[interval(12, 16, unit="mg/dL")])
    )
    assert result.status == rc.STATUS_NEEDS_REVIEW


def test_same_units_different_spelling_are_compatible():
    result = rc.check_test(
        blood_test(value=10.5, unit="G/DL", intervals=[interval(12, 16, unit="g/dL")])
    )
    assert result.status == rc.STATUS_LOW


def test_micro_symbol_unit_normalisation():
    assert rc.units_compatible("x10^3/µL", "x10^3/uL")


def test_reference_without_unit_is_assumed_compatible():
    result = rc.check_test(
        blood_test(value=10.5, unit="g/dL", intervals=[interval(12, 16)])
    )
    assert result.status == rc.STATUS_LOW


# --------------------------------------------------------------------------- #
# Multiple / conditional / inverted intervals
# --------------------------------------------------------------------------- #
def test_multiple_intervals_need_review():
    result = rc.check_test(
        blood_test(
            value=1.0,
            intervals=[
                interval(0.7, 1.3, condition="male"),
                interval(0.6, 1.1, condition="female"),
            ],
        )
    )
    assert result.status == rc.STATUS_NEEDS_REVIEW
    assert "multiple" in result.reason


def test_single_conditional_interval_is_used_and_condition_preserved():
    result = rc.check_test(
        blood_test(value=10.5, intervals=[interval(12, 16, condition="adult female")])
    )
    assert result.status == rc.STATUS_LOW
    assert "adult female" in result.reason


def test_inverted_range_needs_review():
    result = rc.check_test(blood_test(value=5.0, intervals=[interval(16.0, 12.0)]))
    assert result.status == rc.STATUS_NEEDS_REVIEW


def test_unusable_intervals_are_ignored_when_one_is_usable():
    chosen, _ = rc.choose_interval([interval(None, None), interval(1.0, 2.0)])
    assert chosen is not None and chosen.minimum == 1.0


# --------------------------------------------------------------------------- #
# classify_value directly (the reusable comparison function)
# --------------------------------------------------------------------------- #
def test_classify_value_rules():
    assert rc.classify_value(9.9, 10, 20) == rc.STATUS_LOW
    assert rc.classify_value(20.1, 10, 20) == rc.STATUS_HIGH
    assert rc.classify_value(15, 10, 20) == rc.STATUS_NORMAL
    assert rc.classify_value(10, 10, 20) == rc.STATUS_NORMAL  # boundary = NORMAL
    assert rc.classify_value(20, 10, 20) == rc.STATUS_NORMAL  # boundary = NORMAL
