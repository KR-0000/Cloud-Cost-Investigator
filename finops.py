"""Validation and calculations for a small FOCUS billing dashboard."""

import csv
import io
import math
import sqlite3
from contextlib import closing

import pandas as pd

REQUIRED = ["BilledCost", "BillingCurrency", "ProviderName", "ServiceName"]
DATE_COLUMNS = ["ChargePeriodStart", "BillingPeriodStart", "BillingPeriodEnd"]
SERVICE = ["ProviderName", "ServiceName"]
PERCENT_THRESHOLD = 30
AMOUNT_THRESHOLD = 50


def read_billing_csv(content: bytes, *, drop_duplicates: bool = False):
    """Return normalized analysis rows and the number of exact extra copies."""
    if not content:
        raise ValueError("The CSV is empty.")
    try:
        reader = csv.reader(io.StringIO(content.decode("utf-8-sig")), strict=True)
        header = next(reader, [])
        if not header:
            raise ValueError("The CSV is missing a header.")
        if len(header) != len(set(header)):
            raise ValueError("The CSV contains duplicate column names.")
        if missing := sorted(set(REQUIRED) - set(header)):
            raise ValueError(f"Missing required columns: {', '.join(missing)}.")
        rows = []
        for row in reader:
            if not row:
                continue
            if len(row) != len(header):
                raise ValueError(f"CSV record ending on line {reader.line_num} has the wrong number of fields.")
            rows.append(row)
    except (UnicodeDecodeError, csv.Error) as error:
        raise ValueError("Use a well-formed UTF-8, comma-separated CSV.") from error

    if not rows:
        raise ValueError("The CSV has a header but contains no billing rows.")

    raw = pd.DataFrame(rows, columns=header)
    duplicates = raw.duplicated()
    duplicate_count = int(duplicates.sum())
    if drop_duplicates:
        raw = raw.loc[~duplicates]

    frame = raw.reindex(columns=REQUIRED + DATE_COLUMNS).copy()
    frame["BilledCost"] = pd.to_numeric(frame["BilledCost"], errors="coerce")
    invalid_costs = int((~frame["BilledCost"].map(math.isfinite)).sum())
    if invalid_costs:
        raise ValueError(f"Fix {invalid_costs} blank, non-numeric, or infinite BilledCost values.")
    currency = frame["BillingCurrency"].str.strip().str.upper()
    if not currency.str.fullmatch(r"[A-Z]{3}").all():
        raise ValueError("Each BillingCurrency must have a three-letter currency code, such as USD.")
    frame["BillingCurrency"] = currency
    for column in SERVICE:
        frame[column] = frame[column].str.strip().replace("", "Unknown")
    for column in DATE_COLUMNS:
        frame[column] = pd.to_datetime(frame[column], format="mixed", utc=True, errors="coerce")
    return frame, duplicate_count


def provider_totals(charges: pd.DataFrame) -> pd.DataFrame:
    """Use SQL for one dashboard breakdown without keeping a database on disk."""
    with closing(sqlite3.connect(":memory:")) as connection:
        charges[["ProviderName", "BilledCost"]].to_sql("charges", connection, index=False)
        result = pd.read_sql_query(
            """
            SELECT ProviderName, SUM(BilledCost) AS BilledCost
            FROM charges
            GROUP BY ProviderName
            ORDER BY BilledCost DESC, ProviderName
            """,
            connection,
        )
    return result


def service_totals(charges: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    return (
        charges.groupby(columns, as_index=False)["BilledCost"]
        .sum()
        .sort_values(["BilledCost", *columns], ascending=[False, *([True] * len(columns))])
        .reset_index(drop=True)
    )


def daily_totals(charges: pd.DataFrame) -> pd.DataFrame:
    dated = charges.dropna(subset=["ChargePeriodStart"])
    return (
        dated.groupby(dated["ChargePeriodStart"].dt.floor("D").rename("Charge date"))["BilledCost"]
        .sum()
        .reset_index()
    )


def leading_service_share(totals: pd.DataFrame) -> float | None:
    positive = totals.loc[totals["BilledCost"] > 0, "BilledCost"]
    if positive.empty:
        return None
    return float(positive.max() / positive.sum())


def calendar_months(charges: pd.DataFrame) -> list[pd.Timestamp]:
    """Find months whose export rows all use matching UTC calendar-month bounds."""
    start = charges["BillingPeriodStart"]
    end = charges["BillingPeriodEnd"]
    if start.isna().any():
        return []
    month = start.dt.normalize() - pd.to_timedelta(start.dt.day - 1, unit="D")
    valid_bounds = start.eq(month) & end.eq(month + pd.offsets.MonthBegin(1))
    return month[valid_bounds.groupby(month).transform("all")].drop_duplicates().sort_values().tolist()


def spend_increases(prior: pd.DataFrame, current: pd.DataFrame) -> pd.DataFrame:
    """Flag like-for-like increases across two user-confirmed billing months."""
    previous = service_totals(prior, SERVICE).rename(columns={"BilledCost": "Prior"})
    latest = service_totals(current, SERVICE).rename(columns={"BilledCost": "Current"})
    increases = previous.merge(latest, on=SERVICE)
    overall = pd.DataFrame([{
        "ProviderName": "All providers", "ServiceName": "Overall",
        "Prior": prior["BilledCost"].sum(), "Current": current["BilledCost"].sum(),
    }])
    increases = pd.concat([overall, increases], ignore_index=True)
    increases = increases.loc[increases["Prior"] > 0].copy()
    increases["Increase"] = increases["Current"] - increases["Prior"]
    increases["Increase (%)"] = 100 * increases["Increase"] / increases["Prior"]
    qualifies = (
        (increases["Increase"] >= AMOUNT_THRESHOLD)
        & (increases["Increase (%)"] >= PERCENT_THRESHOLD)
    )
    return increases.loc[qualifies].sort_values("Increase", ascending=False)


def savings(baseline: float, reduction_percent: float) -> tuple[float, float]:
    """Return hypothetical optimized cost and savings for the baseline period."""
    if not math.isfinite(baseline) or baseline <= 0 or not 0 <= reduction_percent <= 100:
        raise ValueError("Use a positive baseline and a reduction between 0% and 100%.")
    saved = baseline * reduction_percent / 100
    return baseline - saved, saved
