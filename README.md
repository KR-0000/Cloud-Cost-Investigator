# Cloud Cost Investigator

A local Streamlit dashboard for exploring cloud bills, finding large cost drivers, and modeling a service cost reduction. It opens with an official FOCUS sample and accepts your own CSV. The app runs without cloud credentials, a database server, or API keys.

## Run locally

Install Python 3.11 or newer. In PowerShell, from the repository root, run these commands.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address localhost
```

Open [the local dashboard](http://localhost:8501). The dashboard can run offline once dependencies are installed. Run the tests from the same directory.

```powershell
.\.venv\Scripts\python.exe -m unittest -v
```

## Try it in one minute

The sample opens automatically. Start with **Overview**, open **Investigate** to see the biggest cost driver, then move the slider in **Savings scenario**. To analyze another bill, expand **Use your own billing CSV (optional)** below the dashboard.

Read the [three-minute interview walkthrough](INTERVIEW_PREP.md#start-here-if-you-have-three-minutes) for the three ideas worth practicing first.

<details>
<summary>Dashboard calculations and CSV format</summary>

## What the dashboard shows

- **Overview** sums invoice-basis `BilledCost` by provider and service, keeping signed credits and adjustments. The top five are ranked by net billed cost for each provider–service pair. Dates show daily totals grouped by the start of each charge in UTC. A charge spanning multiple days is assigned to its start date.
- **Investigate** shows the largest pair’s share of all positive net pair totals. For adjacent, complete, comparable billing months, the app also flags increases of at least 30% and 50 units of the selected currency. A flag gives an engineer a starting point for checking usage, rates, commitments, and billing changes.
- **Savings scenario** applies a chosen percentage to a positive net billed-cost baseline. The monthly label requires a confirmed complete billing month. The annualized estimate assumes that the same monthly savings repeat 12 times.

## CSV inputs and assumptions

Use a UTF-8, comma-separated file with `BilledCost`, `BillingCurrency`, `ProviderName`, and `ServiceName`. `ChargePeriodStart` enables the daily chart. `BillingPeriodStart` and `BillingPeriodEnd` enable month-based features when rows use UTC calendar-month bounds. The dates describe the billing window. Completeness and comparable account coverage need confirmation from the person who exported the data.

The app analyzes one file and one currency at a time. Blank provider or service labels become `Unknown`. Invalid costs and blank or malformed currency codes produce an error. Exact copies across all original columns trigger a choice before analysis. Identical rows can be legitimate, so check the export before deciding to count them once. Use one non-overlapping export per account and period if you assemble a combined CSV. The app uses binary floating-point arithmetic and rounds displayed amounts to two decimal places. Use fixed-point arithmetic and currency-specific rounding for invoice reconciliation.

The scenario assumes a uniform reduction to the selected baseline. A bill shows charges and credits. An actionable rightsizing proposal also needs resource telemetry, service-level requirements, and pricing or commitment details. Migration ROI additionally needs transition costs and a time horizon.

</details>

## Sample data attribution

`data/focus_sample.csv` is redistributed unchanged from the FinOps Foundation’s [FOCUS 1.0 Sample Data repository](https://github.com/FinOps-Open-Cost-and-Usage-Spec/FOCUS-Sample-Data/blob/main/FOCUS-1.0/focus_sample.csv) under [CC BY 4.0](https://github.com/FinOps-Open-Cost-and-Usage-Spec/FOCUS-Sample-Data/blob/main/license.md). The source describes the records as anonymized real-world billing data. The bundled file has 1,000 USD records from AWS, Microsoft, and Oracle. Most rows have a September 2024 billing period. Its USD 20.52 total applies to the sampled rows. The [FOCUS 1.0 Billed Cost definition](https://focus.finops.org/docs/specification/v1-0/columns/cost-and-usage/billed-cost/) describes the invoice-basis metric used throughout the app.
