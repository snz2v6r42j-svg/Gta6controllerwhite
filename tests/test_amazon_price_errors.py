import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from amazon_price_errors import (
    KEEPA_EPOCH, as_cents, evaluate, format_alert, get_prices,
    load_watchlist, should_alert,
)

NOW = datetime(2026, 11, 11, 12, tzinfo=timezone.utc)

def sample(price=7999, avg=29999, source_idx=0, minutes_old=10):
    keepa_time = int((NOW - KEEPA_EPOCH).total_seconds() / 60) - minutes_old
    current = [-1, -1]
    averages = [-1, -1]
    current[source_idx] = price
    averages[source_idx] = avg
    return {
        "asin": "B0TEST1234",
        "productType": 0, "title": "Sony DualSense White",
        "lastUpdate": keepa_time, "stats": {
            "current": current, "avg90": averages,
        },
    }

def watch(**overrides):
    base = {
        "asin": "B0TEST1234", "name": "Controller",
        "source": "amazon", "target_cents": None,
        "drop_pct_90d": 55, "min_savings_cents": 2000,
        "required_title_terms": ["dualsense"],
    }
    base.update(overrides)
    return base

class AmazonPriceErrorTests(unittest.TestCase):
    def test_prices_valid(self):
        self.assertEqual(as_cents(84.99), 8499)
        self.assertIsNone(as_cents(0))
        self.assertIsNone(as_cents(-10))
        self.assertIsNone(as_cents("not a price"))

    def test_anomaly_uses_90_day_average(self):
        obs, status = evaluate(watch(), sample(), now=NOW)
        self.assertEqual(status, "OK")
        self.assertEqual(obs["price"], 7999)
        self.assertTrue(any("90-daags" in x for x in obs["reasons"]))

    def test_not_a_real_price_error_claim(self):
        obs, _ = evaluate(watch(), sample(), now=NOW)
        self.assertIn("MOGELIJKE PRIJSAFWIJKING", format_alert(obs))
        self.assertIn("GEEN bevestigde prijsfout", format_alert(obs))

    def test_no_alert_without_benchmark(self):
        obs, _ = evaluate(watch(), sample(avg=-1), now=NOW)
        self.assertEqual(obs["reasons"], [])

    def test_target_without_history(self):
        obs, _ = evaluate(watch(drop_pct_90d=None, target_cents=8499), sample(avg=-1), now=NOW)
        self.assertEqual(len(obs["reasons"]), 1)

    def test_not_enough_discount(self):
        obs, _ = evaluate(watch(), sample(price=22000), now=NOW)
        self.assertEqual(obs["reasons"], [])

    def test_stale_data(self):
        current, avg, reason = get_prices(sample(minutes_old=900), "amazon", now=NOW)
        self.assertIsNone(current)
        self.assertIn("ouder", reason)

    def test_missing_amazon_offer(self):
        current, avg, reason = get_prices(sample(price=-1), "amazon", now=NOW)
        self.assertIsNone(current)

    def test_wrong_product_title(self):
        obs, reason = evaluate(watch(required_title_terms=["iphone"]), sample(), now=NOW)
        self.assertIsNone(obs)
        self.assertIn("Titel", reason)

    def test_marketplace_is_explicit_opt_in(self):
        obs, _ = evaluate(watch(source="marketplace_new"), sample(source_idx=1), now=NOW)
        self.assertTrue(obs["reasons"])

    def test_deduplicate_same_price(self):
        obs, _ = evaluate(watch(), sample(), now=NOW)
        self.assertFalse(should_alert(obs, {"active": True, "last_alerted_cents": 7999}))
        self.assertTrue(should_alert(obs, {"active": False, "last_alerted_cents": 7999}))

    def test_only_alert_for_further_drop(self):
        obs, _ = evaluate(watch(), sample(), now=NOW)
        self.assertTrue(should_alert(obs, {"active": True, "last_alerted_cents": 10000}))
        self.assertFalse(should_alert(obs, {"active": True, "last_alerted_cents": 8100}))

    def test_load_watchlist(self):
        with tempfile.TemporaryDirectory() as folder:
            file = Path(folder) / "watchlist.json"
            file.write_text(json.dumps({"products": [
                {"asin": "B0TEST1234", "name": "Controller",
                 "drop_pct_90d": 55, "enabled": True},
                {"asin": "B0TEST9999", "name": "Disabled", "enabled": False},
            ]}), encoding="utf-8")
            items = load_watchlist(file)
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0]["asin"], "B0TEST1234")
            self.assertEqual(items[0]["min_savings_cents"], 2000)

    def test_invalid_watchlist(self):
        with tempfile.TemporaryDirectory() as folder:
            file = Path(folder) / "watchlist.json"
            file.write_text(json.dumps({"products": [
                {"asin": "not_an_asin", "drop_pct_90d": 60}
            ]}), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_watchlist(file)

if __name__ == "__main__":
    unittest.main()
