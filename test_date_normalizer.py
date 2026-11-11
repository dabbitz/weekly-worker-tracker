from datetime import datetime, timezone, date

from app.services.date_normalizer import (
    normalize_eta_date,
    EtaResolutionStatus,
)


# Example Telegram message timestamp:
# Wednesday, November 11, 2026, 17:00 in Istanbul.
REFERENCE_DATETIME = datetime(
    2026, 11, 11, 14, 0,
    tzinfo=timezone.utc
)


TEST_CASES = [
    ("cuma gününe kadar", date(2026, 11, 13)),
    ("cuma", date(2026, 11, 13)),
    ("yarın", date(2026, 11, 12)),
    ("bugün", date(2026, 11, 11)),
    ("öbür gün", date(2026, 11, 13)),
    ("haftaya cuma", date(2026, 11, 20)),
    ("13.11.2026", date(2026, 11, 13)),
    ("2026-11-18", date(2026, 11, 18)),
    ("3 gün içinde", date(2026, 11, 14)),
]


def main():

    print("Testing Turkish ETA normalization...\n")

    all_passed = True

    for expression, expected_date in TEST_CASES:

        result = normalize_eta_date(
            expression,
            REFERENCE_DATETIME
        )

        passed = (
            result.status == EtaResolutionStatus.RESOLVED
            and result.normalized_date == expected_date
        )

        if not passed:
            all_passed = False

        print(
            f"{'PASS' if passed else 'FAIL'} | "
            f"{expression:25} | "
            f"Expected: {expected_date} | "
            f"Actual: {result.normalized_date} | "
            f"Status: {result.status.value}"
        )

    # Ambiguous expression test

    ambiguous_result = normalize_eta_date(
        "gelecek cuma",
        REFERENCE_DATETIME
    )

    ambiguous_passed = (
        ambiguous_result.status
        == EtaResolutionStatus.AMBIGUOUS
        and ambiguous_result.normalized_date is None
    )

    if not ambiguous_passed:
        all_passed = False

    print(
        f"\n{'PASS' if ambiguous_passed else 'FAIL'} | "
        f"{'gelecek cuma':25} | "
        f"Expected: ambiguous | "
        f"Actual: {ambiguous_result.status.value}"
    )

    # Missing expression test

    missing_result = normalize_eta_date(
        None,
        REFERENCE_DATETIME
    )

    missing_passed = (
        missing_result.status
        == EtaResolutionStatus.MISSING
    )

    if not missing_passed:
        all_passed = False

    print(
        f"{'PASS' if missing_passed else 'FAIL'} | "
        f"{'No ETA provided':25} | "
        f"Expected: missing | "
        f"Actual: {missing_result.status.value}"
    )

    print("\n--------------------------------")

    if all_passed:
        print("SUCCESS: All date normalization tests passed!")
    else:
        print("FAILED: Some tests need attention.")


if __name__ == "__main__":
    main()