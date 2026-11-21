"""Launch with python -m streamlit run app.py."""

from hashlib import sha256
from pathlib import Path

import pandas as pd
import streamlit as st

from finops import (
    AMOUNT_THRESHOLD,
    PERCENT_THRESHOLD,
    SERVICE,
    calendar_months,
    daily_totals,
    leading_service_share,
    provider_totals,
    read_billing_csv,
    savings,
    service_totals,
    spend_increases,
)

SAMPLE_PATH = Path(__file__).parent / "data" / "focus_sample.csv"
SAMPLE_SOURCE = "https://github.com/FinOps-Open-Cost-and-Usage-Spec/FOCUS-Sample-Data/tree/main/FOCUS-1.0"


def money(value, currency):
    return f"{currency} {value:,.2f}"


def show_cost_table(data, labels, currency):
    display = data.rename(columns={**labels, "BilledCost": f"Billed cost ({currency})"})
    st.dataframe(display.round(2), hide_index=True, width="stretch")


def show_overview(charges, pairs, currency):
    cards = st.columns(3)
    cards[0].metric("Billed cost in file", money(charges["BilledCost"].sum(), currency))
    cards[1].metric("Providers", charges["ProviderName"].nunique())
    cards[2].metric("Billing records", f"{len(charges):,}")

    trend = daily_totals(charges)
    if trend.empty:
        st.caption("A daily chart requires a valid ChargePeriodStart column.")
    else:
        trend = trend.rename(columns={"BilledCost": f"Billed cost ({currency})"})
        st.subheader("Billed cost by charge start date")
        trend["Charge date"] = trend["Charge date"].dt.strftime("%Y-%m-%d")
        st.bar_chart(trend, x="Charge date", y=f"Billed cost ({currency})")
        omitted = int(charges["ChargePeriodStart"].isna().sum())
        st.caption(f"UTC dates, grouped by charge start. Rows without valid dates excluded from this chart: {omitted}.")

    provider_column, service_column = st.columns(2)
    with provider_column:
        st.subheader("By provider")
        show_cost_table(provider_totals(charges), {"ProviderName": "Provider"}, currency)
    with service_column:
        st.subheader("By service")
        show_cost_table(service_totals(charges, ["ServiceName"]), {"ServiceName": "Service"}, currency)
    st.subheader("Top five provider–service pairs")
    show_cost_table(pairs.head(5), {"ProviderName": "Provider", "ServiceName": "Service"}, currency)


def show_investigation(charges, pairs, months, currency, data_key, sample):
    st.subheader("Spend concentration")
    share = leading_service_share(pairs)
    if share is None:
        st.info("This selection has no provider–service pair with positive net billed cost.")
    else:
        leader = pairs.iloc[0]
        st.metric(f"{leader['ProviderName']} / {leader['ServiceName']}", f"{share:.1%}")
        st.caption("Share of positive net billed costs across provider–service pairs. A high share identifies a cost driver.")

    st.subheader("Month-over-month increases")
    if sample:
        st.info("The sample covers primarily September 2024 and contains sampled records. Upload two complete, comparable months to investigate increases.")
        return
    consecutive = [month for month in months if month - pd.offsets.MonthBegin(1) in months]
    if not consecutive:
        st.info("This file has no adjacent calendar billing months with valid start and end bounds.")
        return
    current_month = st.selectbox(
        "Later billing month", consecutive, index=len(consecutive) - 1,
        format_func=lambda month: month.strftime("%B %Y"), key=f"compare-{data_key}",
    )
    prior_month = current_month - pd.offsets.MonthBegin(1)
    confirmed = st.checkbox(
        f"I confirm {prior_month:%B %Y} and {current_month:%B %Y} contain complete exports with comparable account and provider coverage.",
        key=f"compare-confirm-{data_key}-{current_month:%Y-%m}",
    )
    if confirmed:
        periods = charges["BillingPeriodStart"]
        flags = spend_increases(charges.loc[periods.eq(prior_month)], charges.loc[periods.eq(current_month)])
        st.caption(f"Flags require a positive prior cost and an increase of at least {PERCENT_THRESHOLD}% and {money(AMOUNT_THRESHOLD, currency)}. Investigate usage, price, and billing changes to explain each flag.")
        if flags.empty:
            st.info("No increases meet both thresholds.")
        else:
            st.dataframe(flags.rename(columns={
                "ProviderName": "Provider", "ServiceName": "Service", "Prior": f"Prior ({currency})",
                "Current": f"Current ({currency})", "Increase": f"Increase ({currency})",
            }).round(2), hide_index=True, width="stretch")


def show_scenario(charges, pairs, months, currency, data_key, sample):
    st.subheader("Simulate a cost reduction")
    monthly = False
    if not sample and months:
        period = st.selectbox(
            "Baseline period", [None, *months], key=f"baseline-period-{data_key}",
            format_func=lambda month: "All rows in the file" if month is None else month.strftime("%B %Y"),
        )
        if period is not None:
            period_charges = charges.loc[charges["BillingPeriodStart"].eq(period)]
            pairs = service_totals(period_charges, SERVICE)
            monthly = st.checkbox(f"The export is complete for {period:%B %Y}.", key=f"baseline-confirm-{data_key}-{period:%Y-%m}")

    eligible = pairs.loc[pairs["BilledCost"] > 0].set_index(SERVICE)["BilledCost"]
    if eligible.empty:
        st.info("A scenario requires a provider–service pair with positive net billed cost.")
        return
    selection = st.selectbox("Provider and service", eligible.index.tolist(), format_func=lambda pair: " / ".join(pair))
    reduction = st.slider("Hypothetical cost reduction (%)", 0, 100, 20)
    baseline = float(eligible.at[selection])
    optimized, saved = savings(baseline, reduction)
    columns = st.columns(3)
    columns[0].metric("Baseline cost", money(baseline, currency))
    columns[1].metric("Hypothetical cost", money(optimized, currency))
    columns[2].metric("Monthly savings" if monthly else "Savings on selected rows", money(saved, currency))
    if monthly and st.checkbox("Assume this baseline and reduction repeat for 12 months.", key=f"annual-{data_key}-{period:%Y-%m}-{selection}"):
        st.metric("Hypothetical annualized savings", money(saved * 12, currency))
    st.caption("Savings are a what-if estimate based on billed cost. Validate resource utilization, pricing commitments, and migration costs before acting.")


def main():
    st.set_page_config(page_title="Cloud Cost Investigator", page_icon="📊", layout="wide")
    st.title("Cloud Cost Investigator")
    intro = st.container()
    dashboard = st.container()

    with st.expander("Use your own billing CSV (optional)"):
        st.caption(f"The app comes with the [FOCUS 1.0 sample]({SAMPLE_SOURCE}), which contains anonymized billing records.")
        upload = st.file_uploader("Choose a FOCUS billing CSV", type="csv")
        sample = upload is None
        try:
            content = SAMPLE_PATH.read_bytes() if sample else upload.getvalue()
            data_hash = sha256(content).hexdigest()[:16]
            charges, duplicates = read_billing_csv(content)
            duplicate_mode = None
            if duplicates:
                intro.warning(f"Found {duplicates:,} exact repeated rows. Open the CSV options below to choose how to count them.")
                duplicate_mode = st.radio(
                    "Repeated rows", ["Keep all rows", "Count exact rows once"],
                    index=None, key=f"duplicates-{data_hash}",
                )
                if duplicate_mode is None:
                    st.stop()
                if duplicate_mode == "Count exact rows once":
                    charges, _ = read_billing_csv(content, drop_duplicates=True)
        except (ValueError, OSError) as error:
            intro.error(f"{error} Open the CSV options below to replace the file or return to the sample.")
            st.stop()

        currencies = sorted(charges["BillingCurrency"].unique())
        currency = currencies[0]
        if len(currencies) > 1:
            currency = st.selectbox("Billing currency", currencies, key=f"currency-{data_hash}")

    with intro:
        if sample:
            st.success("Sample data loaded. You're ready to explore.")
        else:
            st.success(f"Your billing CSV is loaded. Showing {currency}.")
        st.markdown(
            "**Try it now.** Start in **Overview** to see what was billed. Open **Investigate** "
            "to find the biggest cost driver, then move the slider in **Savings scenario**."
        )

    data_key = f"{data_hash}-{currency}-{duplicate_mode}"
    charges = charges.loc[charges["BillingCurrency"].eq(currency)]
    pairs = service_totals(charges, SERVICE)
    months = [] if sample else calendar_months(charges)
    with dashboard:
        overview, investigation, scenarios = st.tabs(["Overview", "Investigate", "Savings scenario"])
        with overview:
            show_overview(charges, pairs, currency)
        with investigation:
            show_investigation(charges, pairs, months, currency, data_key, sample)
        with scenarios:
            show_scenario(charges, pairs, months, currency, data_key, sample)


if __name__ == "__main__":
    main()
