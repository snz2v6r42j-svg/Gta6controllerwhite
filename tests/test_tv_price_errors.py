import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from tv_price_errors import (
    KEEPA_EPOCH, classify, compose_alert, config_from_file,
    deal_query, extract_avg90, positive_int,
)

NOW = datetime(2026, 11, 11, 12, 0, tzinfo=timezone.utc)
CONFIG = {
    "country": "DE", "minimum_previous_eur": 500,
    "minimum_drop_percent": 80, "maximum_change_age_hours": 24,
    "pages_per_query": 2, "queries": [{"categories": [1197292]}]
}


def keepa_minutes(when):
    return int((when - KEEPA_EPOCH).total_seconds() // 60)


def deal(current=9999, previous=60000, average=59000, title="Samsung 65 Zoll Smart TV",
         age_minutes=20, updated_minutes=10, price_type_layout=False):
    avg = [[-1] * 35 for _ in range(4)]
    if price_type_layout:
        avg = [[-1] * 4 for _ in range(35)]
        avg[0][3] = average
    else:
        avg[3][0] = average
    return {
        "asin": "B0TEST1234",
        "title": title,
        "current": [current, -1],
        "deltaLast": [current - previous, 0],
        "avg": avg,
        "currentSince": [keepa_minutes(NOW - timedelta(minutes=age_minutes)), -1],
        "lastUpdate": keepa_minutes(NOW - timedelta(minutes=updated_minutes)),
        "creationDate": keepa_minutes(NOW - timedelta(minutes=age_minutes)),
    }


class TVPriceErrorTests(unittest.TestCase):
    def test_80_percent_drop_from_500_to_100(self):
        obs = classify(deal(current=10000, previous=50000, average=50000), CONFIG, now=NOW)
        self.assertIsNotNone(obs)
        self.assertAlmostEqual(obs["percent_vs_previous"], 80.0)

    def test_83_percent_drop(self):
        obs = classify(deal(), CONFIG, now=NOW)
        self.assertIsNotNone(obs)
        self.assertIn("MOGELIJKE", compose_alert(obs))

    def test_average_below_500_rejected(self):
        self.assertIsNone(classify(deal(average=40000), CONFIG, now=NOW))

    def test_previous_below_500_rejected(self):
        self.assertIsNone(classify(deal(previous=45000), CONFIG, now=NOW))

    def test_less_than_80_percent_rejected(self):
        self.assertIsNone(classify(deal(current=20000), CONFIG, now=NOW))

    def test_out_of_stock_price_rejected(self):
        self.assertIsNone(classify(deal(current=-1), CONFIG, now=NOW))

    def test_no_last_price_change_rejected(self):
        self.assertIsNone(classify(deal(current=40000, previous=40000), CONFIG, now=NOW))

    def test_accessory_instead_of_tv_rejected(self):
        self.assertIsNone(classify(deal(title="TV Wandhalterung für Fernseher 65 Zoll"), CONFIG, now=NOW))

    def test_old_update_rejected(self):
        self.assertIsNone(classify(deal(updated_minutes=800), CONFIG, now=NOW))

    def test_old_price_change_rejected(self):
        self.assertIsNone(classify(deal(age_minutes=3000), CONFIG, now=NOW))

    def test_keepa_two_avg_shapes(self):
        self.assertEqual(extract_avg90(deal()["avg"] if False else deal(), 0), 59000)
        self.assertEqual(extract_avg90(deal(price_type_layout=True), 0), 59000)

    def test_no_price_average(self):
        self.assertIsNone(classify(deal(average=-1), CONFIG, now=NOW))

    def test_amazon_de_only(self):
        q = deal_query(CONFIG["queries"][0])
        self.assertEqual(q["domainId"], 3)
        self.assertEqual(q["priceTypes"], [0])
        self.assertIn(1197292, q["includeCategories"])

    def test_query_does_not_use_specific_asins(self):
        self.assertNotIn("asin", deal_query(CONFIG["queries"][0]))
        self.assertEqual(deal_query({"titleSearch": "Fernseher"})["titleSearch"], "Fernseher")

    def test_config(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "config.json"
            path.write_text(json.dumps(CONFIG), encoding="utf-8")
            self.assertEqual(config_from_file(path)["minimum_drop_percent"], 80)

    def test_reject_unfiltered_query(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "config.json"
            cfg = dict(CONFIG)
            cfg["queries"] = [{}]
            path.write_text(json.dumps(cfg), encoding="utf-8")
            with self.assertRaises(ValueError):
                config_from_file(path)

    def test_reject_bad_80_percent(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "config.json"
            cfg = dict(CONFIG)
            cfg["minimum_drop_percent"] = 101
            path.write_text(json.dumps(cfg), encoding="utf-8")
            with self.assertRaises(ValueError):
                config_from_file(path)

    def test_no_bool_prices(self):
        self.assertFalse(positive_int(True))
        self.assertTrue(positive_int(50000))


if __name__ == "__main__":
    unittest.main()
