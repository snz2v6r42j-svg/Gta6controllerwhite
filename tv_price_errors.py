#!/usr/bin/env python3
"""Category-wide Amazon.de TV price-drop monitor using Keepa Browsing Deals.

No ASIN watchlist. Requires a paid Keepa API key (KEEPA_API_KEY).
This code does not crawl Amazon, defeat bot protections, or place orders.
"""
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from tracker import send_telegram

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / "tv_price_errors_config.json"
STATE = ROOT / "tv_price_state.json"
KEEPA_DEALS = "https://api.keepa.com/deal"
KEEPA_EPOCH = datetime(2011, 1, 1, tzinfo=timezone.utc)

TV_PATTERN = re.compile(
    r"\bfernseher\b|\bsmart[\s-]?tv\b|\b(?:q|o)led[\s-]?(?:tv|fernseher)\b|"
    r"\btelevision\b|\b\d{2,3}\s*(?:zoll|inch|inches)\b",
    re.IGNORECASE,
)
ACCESSORY_PATTERN = re.compile(
    r"wandhalterung|halterung|fernbedienung|remote control|tv[\s-]?stick|"
    r"tv[\s-]?box|soundbar|tv[\s-]?bank|tv[\s-]?schrank|kabel|schutzfolie|"
    r"bildschirmreiniger|antennenkabel|staubschutzhülle|tv[\s-]?standfuß",
    re.IGNORECASE,
)


def euro(cents):
    return f"€{cents // 100:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def positive_int(value):
    return type(value) is int and value > 0


def config_from_file(path=CONFIG):
    cfg = json.loads(path.read_text(encoding="utf-8"))
    if cfg.get("country") != "DE":
        raise ValueError("This scanner supports Amazon.de only")
    min_prev = cfg.get("minimum_previous_eur", 500)
    drop = cfg.get("minimum_drop_percent", 80)
    max_age = cfg.get("maximum_change_age_hours", 24)
    if not isinstance(min_prev, (int, float)) or isinstance(min_prev, bool) or min_prev < 1:
        raise ValueError("minimum_previous_eur must be positive")
    if not isinstance(drop, (int, float)) or isinstance(drop, bool) or not (1 <= drop <= 99):
        raise ValueError("minimum_drop_percent must be 1..99")
    if type(max_age) is not int or not (1 <= max_age <= 48):
        raise ValueError("maximum_change_age_hours must be between 1 and 48")
    if not isinstance(cfg.get("queries"), list) or not cfg["queries"]:
        raise ValueError("queries must be a non-empty list")
    if len(cfg["queries"]) > 4:
        raise ValueError("Limit queries to 4 to control API tokens")
    max_pages = cfg.get("pages_per_query", 2)
    if type(max_pages) is not int or not (1 <= max_pages <= 3):
        raise ValueError("pages_per_query must be 1..3")
    for q in cfg["queries"]:
        if not isinstance(q, dict) or any(k not in {"categories", "titleSearch"} for k in q):
            raise ValueError("Each query needs categories and/or titleSearch")
        categories = q.get("categories")
        keyword = q.get("titleSearch")
        if categories is not None and (not isinstance(categories, list) or
                                       not categories or not all(positive_int(i) for i in categories)):
            raise ValueError("categories must be a non-empty list of category IDs")
        if keyword is not None and (not isinstance(keyword, str) or len(keyword) > 70 or not keyword.strip()):
            raise ValueError("titleSearch must be nonempty and <=70 chars")
        if not categories and not keyword:
            raise ValueError("Refusing an unfiltered Amazon-wide deal query")
    return cfg


def keepa_time(minutes):
    if type(minutes) is not int or minutes < 0:
        return None
    return KEEPA_EPOCH + timedelta(minutes=minutes)


def extract_avg90(deal, idx):
    """Read Keepa deal's 90-day average; supports documented and SDK layouts.

    Documentation describes [date interval][price type]; the public Java
    struct's comments also mention [price type][date interval]. Real
    responses usually have many price types and four intervals.
    """
    arr = deal.get("avg")
    if not isinstance(arr, list):
        return None
    if len(arr) > 4:            # price type major; four intervals per price type
        if idx < len(arr) and isinstance(arr[idx], list) and len(arr[idx]) > 3:
            value = arr[idx][3]
            return value if positive_int(value) else None
    elif len(arr) == 4:         # date interval major; price types per interval
        row = arr[3]
        if isinstance(row, list) and idx < len(row):
            value = row[idx]
            return value if positive_int(value) else None
    return None


def safe_array_value(deal, key, idx):
    row = deal.get(key)
    return row[idx] if isinstance(row, list) and 0 <= idx < len(row) else None


def classify(deal, cfg, source_idx=0, now=None):
    """Return qualifying observation or None.

    deltaLast = current - previous: signed negative on a fall.
    Both *previous* and the 90-day average must be >= EUR 500,
    current must be <= 20% of BOTH, and the decrease must be recent.
    """
    now = now or datetime.now(timezone.utc)
    asin = str(deal.get("asin", "")).upper().strip()
    if not re.fullmatch(r"[A-Z0-9]{10}", asin):
        return None
    title = re.sub("<[^>]*>", "", str(deal.get("title", ""))).strip()
    if not TV_PATTERN.search(title) or ACCESSORY_PATTERN.search(title):
        return None
    current = safe_array_value(deal, "current", source_idx)
    delta_last = safe_array_value(deal, "deltaLast", source_idx)
    if not positive_int(current) or type(delta_last) is not int or delta_last >= 0:
        return None
    previous = current - delta_last
    avg90 = extract_avg90(deal, source_idx)
    min_price = round(float(cfg["minimum_previous_eur"]) * 100)
    drop = float(cfg["minimum_drop_percent"])
    if not positive_int(previous) or not positive_int(avg90):
        return None
    if min(previous, avg90) < min_price:
        return None
    pct_prev = 100 * (previous - current) / previous
    pct_avg = 100 * (avg90 - current) / avg90
    if pct_prev + 1e-6 < drop or pct_avg + 1e-6 < drop:
        return None
    updated = keepa_time(deal.get("lastUpdate"))
    changed = keepa_time(deal.get("currentSince", [None])[source_idx]
                         if isinstance(deal.get("currentSince"), list) and
                         len(deal["currentSince"]) > source_idx else deal.get("creationDate"))
    # A valid lastUpdate does not imply the price changed recently.
    if not updated or not changed:
        return None
    if not timedelta(0) <= now - updated <= timedelta(hours=12):
        return None
    if not timedelta(0) <= now - changed <= timedelta(hours=cfg["maximum_change_age_hours"]):
        return None
    return {
        "asin": asin,
        "title": title[:180],
        "current": current,
        "previous": previous,
        "avg90": avg90,
        "percent_vs_previous": pct_prev,
        "percent_vs_average": pct_avg,
        "source": source_idx,
        "changed_at": changed.isoformat(timespec="minutes"),
    }


def deal_query(q, page=0):
    selection = {
        "page": page,
        "domainId": 3,               # amazon.de
        "priceTypes": [0],           # price sold by Amazon itself
        "dateRange": 0,              # day/rapid declines
        "sortType": 4,               # largest relative drops first
        "isRangeEnabled": True,
        # Broad prefilter. We independently check >=80% drop to the last
        # price and the 90d average; Keepa's % filter is vs a recent average.
        "deltaPercentRange": [10, 100],
        "isFilterEnabled": True,
        "isOutOfStock": False,
        "singleVariation": False,
        "filterErotic": True,
    }
    if q.get("categories"):
        selection["includeCategories"] = q["categories"]
    if q.get("titleSearch"):
        selection["titleSearch"] = q["titleSearch"]
    return selection


def fetch_deals(api_key, cfg):
    if not api_key:
        raise RuntimeError("KEEPA_API_KEY missing")
    output = {}
    used_tokens = 0
    for q in cfg["queries"]:
        for page in range(cfg["pages_per_query"]):
            try:
                response = requests.post(
                    KEEPA_DEALS,
                    params={"key": api_key},
                    json=deal_query(q, page),
                    timeout=45,
                    headers={"User-Agent": "TVPriceErrorWatch/1.0", "Accept-Encoding": "gzip"},
                )
            except requests.RequestException as err:
                raise RuntimeError(f"Keepa connection failed ({type(err).__name__})") from None
            if response.status_code != 200:
                raise RuntimeError(f"Keepa HTTP {response.status_code}. Check API plan and token credits.")
            try:
                data = response.json()
            except ValueError:
                raise RuntimeError("Invalid Keepa JSON") from None
            if data.get("error"):
                raise RuntimeError("Keepa returned API error; check plan, key and token credits")
            deals = data.get("deals")
            if not isinstance(deals, dict) or not isinstance(deals.get("dr"), list):
                raise RuntimeError("Keepa returned no valid deals.dr list")
            used_tokens += data.get("tokensConsumed", 0) if type(data.get("tokensConsumed")) is int else 0
            items = deals["dr"]
            for item in items:
                if isinstance(item, dict) and re.fullmatch(r"[A-Z0-9]{10}", str(item.get("asin", ""))):
                    output[item["asin"]] = item
            # End pagination when fewer than 150 products in response.
            if len(items) < 150:
                break
    return list(output.values()), used_tokens


def compose_alert(obs):
    return (
        "AMAZON.DE TV — VERMOEDELIJKE PRIJSFOUT!\n\n"
        f"{obs['title']}\n\n"
        f"Vorige prijs: {euro(obs['previous'])}\n"
        f"Prijs nu: {euro(obs['current'])}\n"
        f"90-daags gemiddelde: {euro(obs['avg90'])}\n"
        f"Plotselinge daling: {obs['percent_vs_previous']:.1f}%\n"
        f"Bijgewerkt: {obs['changed_at']} UTC\n\n"
        "Let op: dit is géén bevestigde prijsfout of bestelbare voorraad. "
        "Controleer exact model, Amazon als verkoper, verzendkosten en prijs bij het afrekenen.\n"
        f"https://www.amazon.de/dp/{obs['asin']}"
    )


def summary(lines):
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as file:
            file.write("\n".join(["## Amazon.de TV prijsfoutscanner", *lines, ""]) + "\n")


def run():
    cfg = config_from_file()
    api_key = os.environ.get("KEEPA_API_KEY", "").strip()
    if not api_key:
        print("INACTIEF: KEEPA_API_KEY is niet ingesteld. Geen Deals API-aanvraag uitgevoerd.")
        summary(["**NIET ACTIEF**: voeg een betaalde Keepa API-sleutel toe als repository secret.",
                 "Geen Amazon-tv's gecontroleerd; de negen-winkel voorraadtracker blijft gescheiden."])
        return
    deals, tokens = fetch_deals(api_key, cfg)
    try:
        state = json.loads(STATE.read_text(encoding="utf-8"))
        if not isinstance(state, dict):
            state = {}
    except (OSError, json.JSONDecodeError):
        state = {}
    now = datetime.now(timezone.utc)
    found = []
    for deal in deals:
        obs = classify(deal, cfg, now=now)
        if obs:
            found.append(obs)
    failed = 0
    sent = 0
    for obs in sorted(found, key=lambda x: x["percent_vs_previous"], reverse=True):
        key = obs["asin"] + ":amazon"
        old = state.get(key, {})
        last = old.get("last_price")
        # Re-alert only on an additional >= 5% fall compared with last alert.
        if type(last) is int and obs["current"] > last * 0.95:
            continue
        try:
            send_telegram(compose_alert(obs), f"https://www.amazon.de/dp/{obs['asin']}")
        except (requests.RequestException, RuntimeError) as exc:
            failed += 1
            print(f"Telegram for {key} failed: {type(exc).__name__}", file=sys.stderr)
            continue
        state[key] = {"last_price": obs["current"], "last_alerted": now.isoformat(timespec="seconds")}
        sent += 1
    # Prune state older than 30 days to keep repository small.
    cutoff = now - timedelta(days=30)
    state = {
        key: value for key, value in state.items()
        if isinstance(value, dict) and isinstance(value.get("last_alerted"), str)
        and value["last_alerted"] >= cutoff.isoformat(timespec="seconds")
    }
    STATE.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Keepa deals checked: {len(deals)}; qualified TVs: {len(found)}; alerts sent: {sent}; tokens used: {tokens}")
    summary([f"Datum (UTC): {now.isoformat(timespec='seconds')}",
             f"Keepa-deals bekeken: {len(deals)}",
             f"TV-prijsdalingen >= {cfg['minimum_drop_percent']}% vanaf eerder én 90d-gemiddelde >= €{cfg['minimum_previous_eur']}: {len(found)}",
             f"Verzonden Telegram-alerts: {sent}",
             f"Verbruikte API-tokens: {tokens}",
             "Beperking: Keepa is geen realtime Amazon-checkout; gemiste of vertraagde deals zijn mogelijk."])
    if failed:
        raise RuntimeError(f"{failed} TV alerts could not be delivered")


if __name__ == "__main__":
    run()
