import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd
from streamlit.testing.v1 import AppTest

from finops import (
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

ROOT = Path(__file__).parent
HEADER = "ProviderName,ServiceName,BillingCurrency,BilledCost"
PERIODS = ",BillingPeriodStart,BillingPeriodEnd"
TWO_MONTHS = (
    HEADER + PERIODS + "\n"
    "AWS,Compute,USD,200,2024-09-01,2024-10-01\n"
    "AWS,Storage,USD,100,2024-09-01,2024-10-01\n"
    "AWS,Credits,USD,-10,2024-09-01,2024-10-01\n"
    "AWS,Compute,USD,300,2024-10-01,2024-11-01\n"
    "AWS,Storage,USD,135,2024-10-01,2024-11-01\n"
    "AWS,Credits,USD,80,2024-10-01,2024-11-01\n"
    "AWS,New service,USD,80,2024-10-01,2024-11-01\n"
).encode()


class BillingTests(unittest.TestCase):
    def test_official_sample_reconciles(self):
        frame, duplicates = read_billing_csv((ROOT / "data" / "focus_sample.csv").read_bytes())
        self.assertEqual((len(frame), duplicates), (1000, 0))
        self.assertAlmostEqual(frame["BilledCost"].sum(), 20.520226729, places=8)
        for summary in (provider_totals(frame), service_totals(frame, SERVICE), daily_totals(frame)):
            self.assertAlmostEqual(summary["BilledCost"].sum(), frame["BilledCost"].sum())
        self.assertEqual(set(frame["ProviderName"]), {"AWS", "Microsoft", "Oracle"})

    def test_currency_credits_and_duplicates(self):
        content = (HEADER + "\nAWS,Compute,usd,100\nAWS,Compute,USD,-20\n, ,EUR,5\n, ,EUR,5\n").encode()
        full, duplicates = read_billing_csv(content)
        deduped, _ = read_billing_csv(content, drop_duplicates=True)
        self.assertEqual(duplicates, 1)
        self.assertEqual(full.groupby("BillingCurrency")["BilledCost"].sum().to_dict(), {"USD": 80, "EUR": 10})
        self.assertEqual(deduped.loc[deduped["BillingCurrency"].eq("EUR"), "BilledCost"].sum(), 5)
        self.assertEqual(deduped.iloc[-1]["ServiceName"], "Unknown")

    def test_bad_csv_is_rejected(self):
        for row in ("AWS,Compute,USD,invalid", "AWS,Compute,USD,inf", "AWS,Compute,,5", "AWS,Compute,USD,5,extra"):
            with self.subTest(row=row), self.assertRaises(ValueError):
                read_billing_csv((HEADER + "\n" + row).encode())
        with self.assertRaisesRegex(ValueError, "Missing required columns"):
            read_billing_csv(b"BilledCost\n10\n")

    def test_daily_and_billing_period_validation(self):
        content = (HEADER + PERIODS + ",ChargePeriodStart\n"
                   "AWS,Compute,USD,15,2024-09-01,2024-10-01,2024-09-01T23:30:00-04:00\n"
                   "AWS,Compute,USD,20,2024-10-01,2024-10-20,invalid\n").encode()
        frame, _ = read_billing_csv(content)
        self.assertEqual(calendar_months(frame), [pd.Timestamp("2024-09-01", tz="UTC")])
        self.assertEqual(daily_totals(frame).to_dict("records"), [{
            "Charge date": pd.Timestamp("2024-09-02", tz="UTC"), "BilledCost": 15,
        }])

    def test_spend_increases_require_both_thresholds_and_prior_cost(self):
        frame, _ = read_billing_csv(TWO_MONTHS)
        prior, current = calendar_months(frame)
        flags = spend_increases(frame.loc[frame["BillingPeriodStart"].eq(prior)], frame.loc[frame["BillingPeriodStart"].eq(current)])
        self.assertEqual(flags["ServiceName"].tolist(), ["Overall", "Compute"])
        self.assertEqual(flags.iloc[1]["Increase (%)"], 50)
        self.assertEqual(flags.iloc[1]["Increase"], 100)

    def test_savings_and_concentration(self):
        self.assertEqual(savings(1000, 20), (800, 200))
        self.assertEqual(savings(1000, 0), (1000, 0))
        self.assertEqual(savings(1000, 100), (0, 1000))
        with self.assertRaises(ValueError):
            savings(0, 20)
        with self.assertRaises(ValueError):
            savings(1000, 101)
        self.assertEqual(leading_service_share(pd.DataFrame({"BilledCost": [80, 20, -50]})), 0.8)
        self.assertIsNone(leading_service_share(pd.DataFrame({"BilledCost": [-1, 0]})))


class DashboardTests(unittest.TestCase):
    def test_default_dashboard_and_slider(self):
        app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=15).run()
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(any("Sample data loaded" in item.value for item in app.success))
        self.assertEqual(app.expander[0].label, "Use your own billing CSV (optional)")
        self.assertEqual(app.metric[0].value, "USD 20.52")
        self.assertTrue(any("primarily September" in item.value for item in app.info))
        app.slider[0].set_value(100).run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(next(item.value for item in app.metric if item.label == "Hypothetical cost"), "USD 0.00")

    def test_uploaded_months_allow_flags_and_annualizing(self):
        with patch("streamlit.file_uploader") as upload:
            upload.return_value.getvalue.return_value = TWO_MONTHS
            app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=15).run()
            self.assertEqual(len(app.exception), 0)
            app.checkbox[0].check().run()
            self.assertEqual(len(app.exception), 0)
            self.assertEqual(app.dataframe[-1].value["Service"].tolist(), ["Overall", "Compute"])
            period = next(box for box in app.selectbox if box.label == "Baseline period")
            period.set_value(pd.Timestamp("2024-10-01", tz="UTC")).run()
            self.assertEqual(len(app.exception), 0)
            app.checkbox[1].check().run()
            app.checkbox[2].check().run()
            self.assertEqual(len(app.exception), 0)
            metrics = {item.label: item.value for item in app.metric}
            self.assertEqual(metrics["Monthly savings"], "USD 60.00")
            self.assertEqual(metrics["Hypothetical annualized savings"], "USD 720.00")


if __name__ == "__main__":
    unittest.main()
