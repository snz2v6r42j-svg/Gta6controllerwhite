#!/usr/bin/env python3
"""Amazon.de price anomaly and target-price alerts via the official Keepa API.

Requires a paid Keepa API plan. Does not scrape Amazon pages, attempt CAPTCHA
bypasses or claim that a discount is an actual retailer pricing mistake.
"""
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

import requests

from tracker import send_telegram

ROOT = Path(__file__).resolve().parent
WATCHLIST = ROOT / "amazon_watchlist.json"
STATE = ROOT / "amazon_price_state.json"
KEEPA_URL = "https://api.keepa.com/product"
KEEPA_EPOCH = datetime(2011, 1, 1, tzinfo=timezone.utc)
PRICE_INDEX = {"amazon": 0, "marketplace_new": 1}
MAX_STALE_HOURS = 12


def as_cents(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        number = Decimal(str(value))
        if not number.is_finite() or number <= 0:
            return None
        return int((number * 100).quantize(Decimal("1")))
    except (ValueError, TypeError, InvalidOperation):
        return None


def valid_price(cents):
    return isinstance(cents, int) and not isinstance(cents, bool) and cents > 0


def euro(cents):
    return f"€{cents // 100},{cents % 100:02d}"


def load_watchlist(path=WATCHLIST):
    config = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(config, dict) or not isinstance(config.get("products"), list):
        raise ValueError("amazon_watchlist.json must be an object with a 'products' list")
    output = []
    seen = set()
    for item in config["products"]:
        if not isinstance(item, dict) or not item.get("enabled", True):
            continue
        asin = str(item.get("asin", "")).upper().strip()
        if not re.fullmatch(r"[A-Z0-9]{10}", asin):
            raise ValueError("Each enabled Amazon product needs a 10-character ASIN")
        if asin in seen:
            raise ValueError(f"Duplicate Amazon ASIN: {asin}")
        seen.add(asin)
        source = item.get("source", "amazon")
        if source not in PRICE_INDEX:
            raise ValueError(f"Invalid source for {asin}: choose amazon or marketplace_new")
        target = as_cents(item.get("target_eur"))
        pct = item.get("drop_pct_90d")
        if pct is not None and (isinstance(pct, bool) or not isinstance(pct, (float, int)) or not 0 < pct < 100):
            raise ValueError(f"drop_pct_90d for {asin} must be between 0 and 100")
        if target is None and pct is None:
            raise ValueError(f"{asin}: set target_eur and/or drop_pct_90d")
        terms = item.get("required_title_terms", [])
        if not isinstance(terms, list) or not all(isinstance(x, str) for x in terms):
            raise ValueError(f"{asin}: required_title_terms must be a list of strings")
        output.append({
            "asin": asin, "name": str(item.get("name", asin)).strip()[:100],
            "source": source, "target_cents": target,
            "drop_pct_90d": pct,
            "min_savings_cents": as_cents(item.get("min_savings_eur", 20)) or 2000,
            "required_title_terms": [term.casefold() for term in terms if term.strip()],
        })
    if len(output) > 50:
        raise ValueError("Track at most 50 ASINs per run")
    return output


def get_keepa_products(api_key, watchlist):
    if not api_key:
        raise RuntimeError("KEEPA_API_KEY repository secret is missing")
    asins = ",".join(item["asin"] for item in watchlist)
    # stats=90 yields current and avg90 price arrays; update=1 requests refresh
    # of old cached data. 1 token/ASIN and possibly more for forced updates.
    try:
        response = requests.get(
            KEEPA_URL,
            params={"key": api_key, "domain": 3, "asin": asins,
                    "stats": 90, "history": 0, "update": 1},
            headers={"Accept-Encoding": "gzip", "User-Agent": "GTA6-PriceWatch/1.0"},
            timeout=50,
        )
    except requests.RequestException as err:
        raise RuntimeError(f"Keepa connection error: {type(err).__name__}") from None
    # Never log the API URL: it includes the private key.
    if response.status_code != 200:
        raise RuntimeError(f"Keepa returned HTTP {response.status_code}; check subscription/key/tokens")
    try:
        data = response.json()
    except ValueError:
        raise RuntimeError("Keepa returned invalid JSON") from None
    if "error" in data:
        raise RuntimeError(f"Keepa API error code {data.get('error', {}).get('code', 'unknown')}")
    products = data.get("products")
    if not isinstance(products, list):
        raise RuntimeError("Keepa response has no product list (key, tokens, or API issue)")
    return {str(p.get("asin", "")).upper(): p for p in products if isinstance(p, dict)}


def get_prices(product, source, now=None):
    """Return current, 90d average, reason. All prices are euro cents."""
    now = now or datetime.now(timezone.utc)
    if not isinstance(product, dict) or product.get("productType") != 0:
        return None, None, "Geen standaardproduct of productgegevens"
    keepa_time = product.get("lastUpdate")
    if not isinstance(keepa_time, int) or keepa_time < 0:
        return None, None, "Geen actuele tijdstempel"
    updated = KEEPA_EPOCH + timedelta(minutes=keepa_time)
    if now - updated > timedelta(hours=MAX_STALE_HOURS) or updated > now + timedelta(hours=1):
        return None, None, "Keepa-gegevens ouder dan 12 uur"
    stats = product.get("stats") or {}
    idx = PRICE_INDEX[source]
    current = stats.get("current", [])
    averages = stats.get("avg90", [])
    if not isinstance(current, list) or len(current) <= idx or not valid_price(current[idx]):
        return None, None, "Geen actuele prijs voor gekozen verkoperstype"
    avg = averages[idx] if isinstance(averages, list) and len(averages) > idx else None
    return current[idx], avg if valid_price(avg) else None, "Prijs gevonden"


def evaluate(item, product, now=None):
    if not isinstance(product, dict):
        return None, "Geen Keepa-productgegevens"
    title = str(product.get("title", "")).casefold()
    if not all(term in title for term in item["required_title_terms"]):
        return None, "Titel komt niet overeen met het gezochte product"
    current, average, reason = get_prices(product, item["source"], now=now)
    if current is None:
        return None, reason
    reasons = []
    target = item["target_cents"]
    if target is not None and current <= target:
        reasons.append(f"Doelprijs {euro(target)} bereikt")
    if average is not None and item["drop_pct_90d"] is not None:
        savings = average - current
        pct = (savings / average) * 100
        if pct >= item["drop_pct_90d"] and savings >= item["min_savings_cents"]:
            reasons.append(f"{pct:.0f}% onder 90-daags gemiddelde ({euro(average)})")
    return {
        "asin": item["asin"], "price": current, "avg90": average,
        "source": item["source"], "title": product.get("title") or item["name"],
        "reasons": reasons,
    }, "OK"


def should_alert(observation, old_state):
    reasons = observation["reasons"]
    if not reasons:
        return False
    if not old_state.get("active"):
        return True
    previous = old_state.get("last_alerted_cents")
    if not valid_price(previous):
        return True
    # Notify again only on a further >= 5% fall; rising prices never retrigger.
    return observation["price"] <= int(previous * 0.95)


def format_alert(observation):
    price = observation["price"]
    asin = observation["asin"]
    source = "Amazon zelf" if observation["source"] == "amazon" else "Laagste nieuwe marketplace-aanbod"
    return (
        "AMAZON.DE — MOGELIJKE PRIJSAFWIJKING\n\n"
        f"{str(observation['title'])[:130]}\n"
        f"Nu: {euro(price)}\n"
        f"Verkoperstype: {source}\n"
        f"Signaal: {'; '.join(observation['reasons'])}\n\n"
        "Dit is GEEN bevestigde prijsfout. Controleer aanbieder, "
        "verzendkosten, coupon, productvariant en prijs op de betaalpagina.\n\n"
        f"https://www.amazon.de/dp/{asin}"
    )


def write_summary(lines):
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as out:
            out.write("\n".join(["## Amazon.de Price Error Alert", *lines, ""]) + "\n")


def run():
    watchlist = load_watchlist()
    if not watchlist:
        message = "Geen actieve Amazon-producten. Voeg ASINs toe aan amazon_watchlist.json."
        print(message)
        write_summary([message])
        return
    api_key = os.environ.get("KEEPA_API_KEY", "").strip()
    if not api_key:
        message = "NIET ACTIEF: KEEPA_API_KEY ontbreekt. Geen Amazon-prijscontrole uitgevoerd."
        print(message)
        write_summary([message])
        return
    data = get_keepa_products(api_key, watchlist)
    try:
        state = json.loads(STATE.read_text(encoding="utf-8"))
        if not isinstance(state, dict):
            state = {}
    except (FileNotFoundError, json.JSONDecodeError):
        state = {}
    now = datetime.now(timezone.utc)
    lines = [
        f"Controle (UTC): {now.isoformat(timespec='seconds')}",
        "| ASIN | Status | Prijs |",
        "|---|---|---|",
    ]
    problems = 0
    for item in watchlist:
        asin = item["asin"]
        obs, reason = evaluate(item, data.get(asin), now=now)
        if obs is None:
            print(f"{asin}: unknown ({reason})")
            lines.append(f"| {asin} | unknown — {reason} | — |")
            continue
        old = state.get(asin, {})
        active = bool(obs["reasons"])
        print(f"{asin}: {euro(obs['price'])}, alert={active}")
        lines.append(f"| {asin} | {'trigger' if active else 'geen trigger'} | {euro(obs['price'])} |")
        if active and should_alert(obs, old):
            try:
                send_telegram(format_alert(obs), f"https://www.amazon.de/dp/{asin}")
            except (RuntimeError, requests.RequestException) as error:
                # Keep state unchanged so the next scan can retry.
                problems += 1
                print(f"{asin}: Telegram kon niet afleveren ({type(error).__name__})", file=sys.stderr)
                continue
            state[asin] = {"active": True, "last_alerted_cents": obs["price"]}
        elif not active:
            state[asin] = {"active": False, "last_alerted_cents": old.get("last_alerted_cents")}
        elif old.get("active"):
            state[asin] = old
        else:
            # Invalid state; leave as is if unable to confirm a new alert.
            state[asin] = old
    STATE.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_summary(lines + ["Prijzen kunnen vertraagd zijn; aanbiedingen zijn niet gegarandeerd bestelbaar."])
    if problems:
        raise RuntimeError(f"{problems} Telegram-prijsalerts konden niet worden afgeleverd")


if __name__ == "__main__":
    run()
