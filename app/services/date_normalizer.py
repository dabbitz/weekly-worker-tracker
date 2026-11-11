import re

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from zoneinfo import ZoneInfo


TIMEZONE = ZoneInfo("Europe/Istanbul")


class EtaResolutionStatus(str, Enum):
    RESOLVED = "resolved"
    MISSING = "missing"
    AMBIGUOUS = "ambiguous"
    UNSUPPORTED = "unsupported"
    INVALID = "invalid"


@dataclass(frozen=True)
class EtaNormalizationResult:
    normalized_date: date | None
    status: EtaResolutionStatus
    reason: str | None = None


WEEKDAYS = {
    "pazartesi": 0,
    "salı": 1,
    "çarşamba": 2,
    "perşembe": 3,
    "cuma": 4,
    "cumartesi": 5,
    "pazar": 6,
}

WEEKDAY_FORMS = {
    "pazartesi": ["pazartesi", "pazartesiye"],
    "salı": ["salı", "salıya"],
    "çarşamba": ["çarşamba", "çarşambaya"],
    "perşembe": ["perşembe", "perşembeye"],
    "cuma": ["cuma", "cumaya"],
    "cumartesi": ["cumartesi", "cumartesiye"],
    "pazar": ["pazar", "pazara"],
}


def _result(
    normalized_date: date | None,
    status: EtaResolutionStatus,
    reason: str | None = None,
) -> EtaNormalizationResult:

    return EtaNormalizationResult(
        normalized_date=normalized_date,
        status=status,
        reason=reason,
    )


def _get_reference_date(reference_datetime: datetime) -> date:
    """
    Convert Telegram's message timestamp to Istanbul time.

    Telegram timestamps represent UTC time. If a naive
    datetime is supplied, it is interpreted as UTC.
    """

    if reference_datetime.tzinfo is None:
        reference_datetime = reference_datetime.replace(
            tzinfo=timezone.utc
        )

    return reference_datetime.astimezone(TIMEZONE).date()


def _parse_explicit_date(value: str) -> date | None:
    """
    Parse explicitly provided calendar dates.
    Supported formats:
    YYYY-MM-DD
    DD.MM.YYYY
    DD/MM/YYYY
    DD-MM-YYYY
    """

    value = value.strip()

    formats = [
        "%Y-%m-%d",
        "%d.%m.%Y",
        "%d/%m/%Y",
        "%d-%m-%Y",
    ]

    for date_format in formats:
        try:
            return datetime.strptime(
                value,
                date_format
            ).date()
        except ValueError:
            continue

    return None


def normalize_eta_date(
    eta_text: str | None,
    reference_datetime: datetime,
) -> EtaNormalizationResult:
    """
    Convert a supported Turkish ETA expression into
    a calendar date using the original message timestamp.

    Unsupported or ambiguous expressions are not guessed.
    """

    if eta_text is None or not eta_text.strip():
        return _result(
            None,
            EtaResolutionStatus.MISSING,
            "No expected completion time was provided."
        )

    reference_date = _get_reference_date(reference_datetime)
    normalized_text = eta_text.casefold().strip()

    # --------------------------------------
    # 1. Explicit calendar dates
    # --------------------------------------

    iso_match = re.search(
        r"\b\d{4}-\d{2}-\d{2}\b",
        normalized_text
    )

    if iso_match:
        parsed = _parse_explicit_date(iso_match.group())

        if parsed:
            return _result(parsed, EtaResolutionStatus.RESOLVED)

        return _result(
            None,
            EtaResolutionStatus.INVALID,
            "The supplied calendar date is invalid."
        )

    local_match = re.search(
        r"\b\d{1,2}[./-]\d{1,2}[./-]\d{4}\b",
        normalized_text
    )

    if local_match:
        parsed = _parse_explicit_date(local_match.group())

        if parsed:
            return _result(parsed, EtaResolutionStatus.RESOLVED)

        return _result(
            None,
            EtaResolutionStatus.INVALID,
            "The supplied calendar date is invalid."
        )

    # --------------------------------------
    # 2. Relative day expressions
    # --------------------------------------

    relative_days = [
        (r"\bbugün\b", 0),
        (r"\byarın\b", 1),
        (r"\böbür gün\b", 2),
        (r"\bertesi gün\b", 1),
    ]

    relative_matches = [
        days
        for pattern, days in relative_days
        if re.search(pattern, normalized_text)
    ]

    # Also check if a weekday is mentioned.
    weekday_matches = []

    for weekday_name, forms in WEEKDAY_FORMS.items():
        for form in forms:
            if re.search(
                rf"(?<!\w){re.escape(form)}(?!\w)",
                normalized_text
            ):
                weekday_matches.append(weekday_name)
                break

    # Multiple different date expressions can be ambiguous.
    if relative_matches and weekday_matches:
        return _result(
            None,
            EtaResolutionStatus.AMBIGUOUS,
            "Multiple different date expressions were found."
        )

    if len(set(relative_matches)) > 1:
        return _result(
            None,
            EtaResolutionStatus.AMBIGUOUS,
            "Multiple relative day expressions were found."
        )

    if relative_matches:
        return _result(
            reference_date + timedelta(days=relative_matches[0]),
            EtaResolutionStatus.RESOLVED
        )

    # --------------------------------------
    # 3. Relative duration expressions
    # --------------------------------------

    duration_match = re.search(
        r"\b(\d{1,3})\s+gün\s+"
        r"(?:sonra|içinde|içerisinde|güne kadar)\b",
        normalized_text
    )

    if duration_match:
        days = int(duration_match.group(1))

        return _result(
            reference_date + timedelta(days=days),
            EtaResolutionStatus.RESOLVED
        )

    # --------------------------------------
    # 4. End of month expressions
    # --------------------------------------

    if re.search(
        r"\bayın\s+sonunda\b|\bay\s+sonuna\s+kadar\b",
        normalized_text
    ):
        import calendar

        year = reference_date.year
        month = reference_date.month

        if re.search(r"\bgelecek ay\b", normalized_text):
            if month == 12:
                year += 1
                month = 1
            else:
                month += 1

        last_day = calendar.monthrange(year, month)[1]

        return _result(
            date(year, month, last_day),
            EtaResolutionStatus.RESOLVED
        )

    # --------------------------------------
    # 5. Weekday expressions
    # --------------------------------------

    unique_weekdays = set(weekday_matches)

    if len(unique_weekdays) > 1:
        return _result(
            None,
            EtaResolutionStatus.AMBIGUOUS,
            "More than one weekday was mentioned."
        )

    if len(unique_weekdays) == 1:

        weekday_name = next(iter(unique_weekdays))
        target_weekday = WEEKDAYS[weekday_name]

        # "Gelecek cuma" / "önümüzdeki cuma" may
        # refer to different weeks depending on context.
        ambiguous_next_week = re.search(
            r"\b(gelecek|önümüzdeki)\s+"
            r"(pazartesi|salı|çarşamba|perşembe|cuma|cumartesi|pazar)\b",
            normalized_text
        )

        explicit_next_week = re.search(
            r"\b(haftaya|gelecek hafta|önümüzdeki hafta)\b",
            normalized_text
        )

        if ambiguous_next_week and not explicit_next_week:
            return _result(
                None,
                EtaResolutionStatus.AMBIGUOUS,
                "The phrase may refer to different weeks."
            )

        # Explicitly referring to next week.
        if explicit_next_week:

            current_week_monday = (
                reference_date
                - timedelta(days=reference_date.weekday())
            )

            next_week_monday = (
                current_week_monday
                + timedelta(days=7)
            )

            target_date = (
                next_week_monday
                + timedelta(days=target_weekday)
            )

            return _result(
                target_date,
                EtaResolutionStatus.RESOLVED
            )

        # Explicitly referring to this week.
        if re.search(r"\bb(u|ü)\s+hafta\b", normalized_text):

            current_week_monday = (
                reference_date
                - timedelta(days=reference_date.weekday())
            )

            target_date = (
                current_week_monday
                + timedelta(days=target_weekday)
            )

            if target_date < reference_date:
                return _result(
                    None,
                    EtaResolutionStatus.AMBIGUOUS,
                    "The mentioned weekday has already passed this week."
                )

            return _result(
                target_date,
                EtaResolutionStatus.RESOLVED
            )

        # Otherwise, use the nearest occurrence of
        # the specified weekday, including today.
        days_ahead = (
            target_weekday - reference_date.weekday()
        ) % 7

        return _result(
            reference_date + timedelta(days=days_ahead),
            EtaResolutionStatus.RESOLVED
        )

    return _result(
        None,
        EtaResolutionStatus.UNSUPPORTED,
        "The expected completion expression is not supported yet."
    )