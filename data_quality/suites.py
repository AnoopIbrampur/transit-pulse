"""Great Expectations suite definitions for the raw MTA tables.

Suites are declared as data (plain dicts) so they can be both exported to JSON
for the repo and materialized into GE ``ExpectationSuite`` objects at runtime.
Each entry maps a raw table name to its list of expectations.

Percentage-like metrics (OTP, wait assessment, customer journey time) are stored
as 0-1 fractions in the raw layer, so bounds are [0, 1] — not [0, 100].
"""

from __future__ import annotations

# Valid MTA line/route codes, including shuttle and combined designations
# observed live in the data (FS, GS, H, JZ, S 42nd, S Fkln, S Rock).
VALID_LINES: list[str] = [
    "1", "2", "3", "4", "5", "6", "7",
    "A", "B", "C", "D", "E", "F", "FS", "G", "GS", "H",
    "J", "JZ", "L", "M", "N", "Q", "R",
    "S 42nd", "S Fkln", "S Rock", "W",
]

# suite name -> list of (expectation_type, kwargs) tuples.
SUITES: dict[str, list[tuple[str, dict]]] = {
    "terminal_otp": [
        ("expect_column_values_to_not_be_null", {"column": "line"}),
        ("expect_column_values_to_not_be_null", {"column": "month"}),
        ("expect_column_values_to_not_be_null", {"column": "terminal_on_time_performance"}),
        (
            "expect_column_values_to_be_between",
            {"column": "terminal_on_time_performance", "min_value": 0, "max_value": 1},
        ),
        ("expect_column_values_to_be_in_set", {"column": "line", "value_set": VALID_LINES}),
        ("expect_table_row_count_to_be_between", {"min_value": 100, "max_value": 500_000}),
        (
            "expect_column_pair_values_a_to_be_greater_than_b",
            {"column_A": "_loaded_at", "column_B": "month"},
        ),
    ],
    "station_ridership": [
        ("expect_column_values_to_not_be_null", {"column": "station_complex_id"}),
        ("expect_column_values_to_not_be_null", {"column": "month"}),
        ("expect_column_values_to_not_be_null", {"column": "ridership"}),
        (
            "expect_column_values_to_be_between",
            {"column": "ridership", "min_value": 0, "max_value": 10_000_000},
        ),
        ("expect_table_row_count_to_be_between", {"min_value": 100, "max_value": 500_000}),
    ],
    "wait_assessment": [
        ("expect_column_values_to_not_be_null", {"column": "line"}),
        ("expect_column_values_to_not_be_null", {"column": "wait_assessment"}),
        (
            "expect_column_values_to_be_between",
            {"column": "wait_assessment", "min_value": 0, "max_value": 1},
        ),
        ("expect_column_values_to_be_in_set", {"column": "line", "value_set": VALID_LINES}),
    ],
    "customer_journey": [
        ("expect_column_values_to_not_be_null", {"column": "line"}),
        ("expect_column_values_to_not_be_null", {"column": "customer_journey_time"}),
        (
            "expect_column_values_to_be_between",
            {"column": "customer_journey_time", "min_value": 0, "max_value": 1},
        ),
    ],
}
