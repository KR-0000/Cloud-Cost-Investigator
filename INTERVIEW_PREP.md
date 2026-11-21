# Cloud Cost Investigator interview prep

## Start here if you have three minutes

**Minute 1. Try the app.** It opens with the sample already loaded. In **Overview**, find the USD 20.52 total. In **Investigate**, see which provider and service account for the largest share of spending. In **Savings scenario**, move the slider from 20% to 40% and watch the estimated savings change.

**Minute 2. Learn three ideas.**

- **FOCUS** gives different cloud bills common column names. The app adds up what was billed in one currency, including credits.
- **A large cost is a place to look.** The app needs two comparable months to tell whether spending jumped. The sample mainly covers one month, so it shows where costs are concentrated.
- **The slider is a what-if.** A 20% reduction on a USD 100 baseline saves USD 20 and leaves USD 80. To decide if the reduction is realistic, check usage, prices, and performance requirements.

**Minute 3. Say it aloud.** “I used AI to help build a local dashboard that turns cloud billing rows into cost totals by provider and service. Then I used those totals to see where spending is concentrated and model a possible reduction. For a migration, I’d use this to decide what to investigate first.”

If you have one more minute, answer this without reading. “Why can’t you recommend downsizing just because a service is expensive?” A strong answer mentions CPU or memory usage, performance targets, and pricing commitments.

<details>
<summary>Optional practice and technical details</summary>

## Follow one bill through the app

1. **Read the CSV.** `app.py` gets bytes from the uploader or the bundled FOCUS sample. `read_billing_csv` checks the header and each record’s field count, then parses finite costs and UTC timestamps. It counts exact repeats using all original columns before retaining the fields the dashboard uses.
2. **Select one currency.** The app passes only rows in that billing currency to the calculations. Signed credits and adjustments stay in the data. Blank service or provider names fall into `Unknown` so their costs still reconcile with the total.
3. **Group and sum.** Pandas produces service and provider–service totals and a charge-start trend. `provider_totals` demonstrates the same grouping in a single SQLite query against an in-memory table. For the official sample, the provider totals sum to the overall total.
4. **Investigate.** `leading_service_share` surfaces concentration. `calendar_months` checks the timestamp bounds, and `spend_increases` joins adjacent months by provider and service after the user confirms export completeness and comparable coverage. Streamlit displays the prior amount, current amount, and change for each flag.
5. **Model an option.** `savings` applies a percentage to one selected pair’s positive billed-cost baseline. Streamlit reevaluates the calculation as the slider changes and labels the units and baseline period.

## Work three examples by hand

1. **Billed cost and concentration.** The bundled sample has about USD 18.00664 for AWS, USD 1.97651 for Microsoft, and USD 0.53707 for Oracle. Sum the unrounded costs, then display **USD 20.52**. For a separate concentration example, suppose three provider–service pairs net USD 80, USD 20, and USD −50. The file total is USD 50. The leading pair’s concentration is `80 / (80 + 20) = 80%` because the denominator includes only pairs with positive net cost. Credits still affect the billed-cost total.
2. **Month-over-month flag.** An uploaded compute service goes from USD 200 in September to USD 300 in October. The increase is `300 − 200 = USD 100`. The relative change is `100 / 200 × 100 = 50%`. Both thresholds are met. A storage increase from USD 100 to USD 135 passes the percentage threshold and falls below the USD 50 threshold. A positive baseline is required for a meaningful relative increase.
3. **Savings scenario.** For a complete monthly baseline of USD 1,000 and a hypothetical 20% reduction, savings equal `1,000 × 0.20 = USD 200/month`. Projected cost equals `1,000 − 200 = USD 800/month`. If the same baseline and reduction repeat 12 times, simple annualized savings equal `200 × 12 = USD 2,400`. If a migration also costs USD 900 upfront, a separate payback estimate would be `900 / 200 = 4.5 months` under those same assumptions. The app reports savings. Migration payback and ROI also require a transition-cost model.

## Python, Pandas, and SQL review

- `pd.to_numeric(..., errors="coerce")` turns failed conversions into missing values, which validation rejects. `pd.to_datetime(..., utc=True)` gives dates a common time basis. `Series.eq` builds the Boolean mask used for selecting a currency or one period.
- `groupby(...)["BilledCost"].sum()` combines line items at the selected grain. A two-column group keeps the AWS and Microsoft versions of the same service label distinct. The inner `merge` on provider and service pairs only produces comparisons with observations in both months.
- `SELECT ProviderName, SUM(BilledCost) AS BilledCost FROM charges GROUP BY ProviderName ORDER BY BilledCost DESC, ProviderName` returns one row per provider and sorts largest first. The app loads the currency-filtered rows into SQLite before the query.

Try these without AI. Predict the output before running anything.

1. Write Pandas code that calculates USD spend by service for `[100, -20]` in Compute and `[30]` in Storage. Add a EUR Compute row and verify it stays out of the USD totals.
2. Write a SQL query for the top five provider–service pairs. Which fields must you add to the current SQLite table, and which columns belong in `GROUP BY`?
3. Change a fixture so compute increases from 200 to 250. Which threshold does it pass? Then try 200 to 260 and explain the result.

## Cloud and FinOps concepts

| Concept | How it applies here |
| --- | --- |
| Cloud cost visibility | Use consistent billing dimensions to show which providers, services, and periods account for spend. |
| Resource utilization | CPU, memory, requests, and throughput describe how a resource is used. Compare these metrics with capacity and service objectives before changing a deployment. |
| Cost optimization | Change resource sizing, scheduling, architecture, or purchasing while preserving the service outcomes the workload needs. |
| Rightsizing | Match capacity to measured demand and headroom. A costly VM is a candidate for investigation, and telemetry helps decide whether a smaller VM is appropriate. |
| On-demand pricing | Pay for metered usage at the applicable rate without committing to a term. For example, VM-hours × price per VM-hour is one component of compute cost. |
| Cost allocation | Attribute direct costs using account or application tags, and choose and document a rule for shared costs. This app groups by provider and service. |
| Forecasting | Estimate future spending from demand, rates, and expected changes over time. The savings slider is a fixed-assumption what-if calculation. |
| ROI and total cost of ownership | Over a chosen horizon, ROI is net benefit divided by investment. TCO includes the relevant one-time and recurring costs of owning or operating a solution, such as migration labor, compute, data transfer, and support. |
| FinOps | Engineering, finance, and business teams work together to understand technology costs and make decisions informed by the value they receive. |
| Multicloud | FOCUS gives multiple providers common billing dimensions. A like-for-like architecture comparison still needs equivalent workload, performance, region, availability, and pricing assumptions. |

## Ten practice questions

1. **Why did you pick FOCUS?** It gives provider billing exports a common vocabulary for cost, currency, and service. The official sample also lets me demonstrate the workflow offline. Its sampled coverage is why the default dashboard emphasizes cost drivers.
2. **How is the total calculated?** I sum signed `BilledCost` within one currency. It reflects invoice-basis charges, including discounts embedded in billed charges. `EffectiveCost` is useful when I want to allocate the cost of commitments over the usage they cover. Adding the two would mix two accounting views of the same activity.
3. **What’s the difference between compute and storage cost?** A VM can incur charges per instance-hour. Storage can incur charges per GB-month, request, or retrieval. Network transfer can add another charge. I would check the SKU, region, quantity, and unit price before explaining a bill change.
4. **Why Streamlit, Pandas, and SQLite?** Streamlit gets a CSV upload and interactive dashboard running locally with little UI code. Pandas makes the validation and groupings easy to inspect. SQLite demonstrates one query without running or persisting a database server.
5. **A manager says October looks expensive. What do you check first?** I confirm both months contain comparable accounts and complete exports. I review absolute and relative changes, then drill into usage quantities, unit rates, credits, and commitment changes. I would connect the increase to a deployment, demand shift, or billing change before calling it a root cause.
6. **How would you handle duplicate-looking charges?** I flag exact copies before computing totals and ask the uploader how to count them. In a production pipeline I would also track source files, deduplicate ingestion, and use stable line-item identifiers when the export provides them.
7. **How would you extend this to Azure and Google Cloud?** I would inspect their FOCUS export versions, map any renamed fields to the app’s input columns, and verify coverage, charge semantics, and currency. I would test with small exports from each provider and reconcile against its invoice totals separately.
8. **Could you recommend downsizing based on these results?** I can identify a service worth investigating. Before recommending a smaller instance, I would use CPU and memory percentiles, peak demand, latency targets, and failover capacity, then test the change and estimate its savings after commitment effects.
9. **How would you compare a VM with serverless for a migration?** Start from the same workload and service targets. Estimate VM-hours and required host capacity. For serverless, estimate requests, duration, and allocated memory. Include transfer, storage, and migration costs where they differ, then vary demand and utilization to see where the cost ranking changes.
10. **What would you improve with another week?** I would start with verified complete exports and reconcile totals by account. Then I would build a two-architecture cost comparison with published regional prices and explicit workload assumptions. I would prioritize validation and sensitivity analysis before adding automated explanations.

## 60–90-second demo

**0–20 seconds.** Open Overview. “I built this AI-assisted prototype to practice turning cloud billing data into a migration decision. I studied the data flow, tested the calculations, and can walk through them. This is the FinOps Foundation’s anonymized FOCUS sample. It shows USD 20.52 in the sampled rows, grouped by provider and service.”

**20–45 seconds.** Open Investigate. “The largest provider–service pair drives this share of positive net costs. That tells me where to look first. The sample has limited period coverage. With two complete, comparable months, the app would flag an increase only if both the dollar and percentage thresholds were met.”

**45–75 seconds.** Open Savings scenario and move the slider. “The slider multiplies the selected baseline by the reduction percentage and subtracts the savings from the baseline. These are hypothetical savings on the selected records. In a real migration, I’d check utilization, service targets, vendor rates, commitments, and transition costs before recommending a change.”

For further reading, use the [FOCUS 1.0 sample notes](https://github.com/FinOps-Open-Cost-and-Usage-Spec/FOCUS-Sample-Data/tree/main/FOCUS-1.0), [Billed Cost definition](https://focus.finops.org/docs/specification/v1-0/columns/cost-and-usage/billed-cost/), and [Effective Cost definition](https://focus.finops.org/docs/specification/v1-0/columns/cost-and-usage/effective-cost/).

</details>
