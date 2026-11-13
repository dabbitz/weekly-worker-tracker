from datetime import date, datetime, timezone

import pytest

from app.services.date_normalizer import (
    EtaResolutionStatus,
    normalize_eta_date,
)


# 13.11.2026, 10:00 in Europe/Istanbul (Friday).
REFERENCE_DATETIME = datetime(
    2026,
    11,
    13,
    7,
    0,
    tzinfo=timezone.utc,
)


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("20 Kasım Cuma gününe kadar", date(2026, 11, 20)),
        ("20.11.2026", date(2026, 11, 20)),
        ("16 Kasım Pazartesi", date(2026, 11, 16)),
        ("13 Kasım Cuma", date(2026, 11, 13)),
        ("20 Kasım 2026 Cuma", date(2026, 11, 20)),
        ("20/11/2026", date(2026, 11, 20)),
    ],
)
def test_explicit_calendar_date_wins_over_weekday(expression, expected):
    result = normalize_eta_date(expression, REFERENCE_DATETIME)

    assert result.status is EtaResolutionStatus.RESOLVED
    assert result.normalized_date == expected


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("cuma gününe kadar", date(2026, 11, 13)),
        ("cuma", date(2026, 11, 13)),
        ("pazartesi gününe kadar", date(2026, 11, 16)),
        ("haftaya cuma", date(2026, 11, 20)),
        ("yarın", date(2026, 11, 14)),
    ],
)
def test_weekday_only_expressions_keep_previous_behavior(
    expression,
    expected,
):
    result = normalize_eta_date(expression, REFERENCE_DATETIME)

    assert result.status is EtaResolutionStatus.RESOLVED
    assert result.normalized_date == expected


def test_reported_eta_phrase_from_real_report():
    # The exact expression Gemini extracted from the real Telegram test.
    result = normalize_eta_date(
        "20 Kasım Cuma gününe kadar",
        REFERENCE_DATETIME,
    )

    assert result.normalized_date == date(2026, 11, 20)
    assert result.normalized_date.strftime("%d.%m.%Y") == "20.11.2026"


def test_weekday_that_disagrees_with_explicit_date_is_ambiguous():
    result = normalize_eta_date("20 Kasım Pazartesi", REFERENCE_DATETIME)

    assert result.status is EtaResolutionStatus.AMBIGUOUS
    assert result.normalized_date is None


def test_multiple_explicit_dates_are_ambiguous():
    result = normalize_eta_date(
        "16 Kasım Pazartesi günü teslim, 20 Kasım Cuma gününe kadar bitiş",
        REFERENCE_DATETIME,
    )

    assert result.status is EtaResolutionStatus.AMBIGUOUS
    assert result.normalized_date is None


@pytest.mark.parametrize(
    "expression",
    ["31 Kasım", "31 Şubat 2026", "2026-02-30"],
)
def test_invalid_calendar_dates_are_not_guessed(expression):
    result = normalize_eta_date(expression, REFERENCE_DATETIME)

    assert result.status is EtaResolutionStatus.INVALID
    assert result.normalized_date is None


def test_day_and_month_without_year_use_next_occurrence():
    result = normalize_eta_date("5 Ocak", REFERENCE_DATETIME)

    assert result.status is EtaResolutionStatus.RESOLVED
    assert result.normalized_date == date(2027, 1, 5)


def test_missing_eta_stays_missing():
    result = normalize_eta_date(None, REFERENCE_DATETIME)

    assert result.status is EtaResolutionStatus.MISSING
    assert result.normalized_date is None


def test_reference_date_uses_istanbul_timezone():
    # 12.11.2026 22:30 UTC is already 13.11.2026 in Istanbul.
    result = normalize_eta_date(
        "bugün",
        datetime(2026, 11, 12, 22, 30, tzinfo=timezone.utc),
    )

    assert result.status is EtaResolutionStatus.RESOLVED
    assert result.normalized_date == date(2026, 11, 13)