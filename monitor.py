import json
import logging
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

from config import (
    PAGE_SIZE,
    POKEMON_TCG_KEYWORD,
    SELLER_ID,
    STORE_API_URL,
    STORE_PAGE_URL,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger(__name__)

SGT = timezone(timedelta(hours=8))
STATE_FILE = Path("state.json")

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/17.0 Mobile/15E148 Safari/604.1"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-SG,en;q=0.9",
    "Referer": STORE_PAGE_URL,
    "X-Requested-With": "XMLHttpRequest",
})


# ── Fetching ──────────────────────────────────────────────────────────────────

def fetch_products_api():
    """Call the Lazada seller store JSON API with pagination."""
    all_items = []
    page = 1
    while True:
        params = {
            "sellerId": SELLER_ID,
            "pageNumber": page,
            "pageSize": PAGE_SIZE,
            "sort": "pop",
            "langFlag": "en",
        }
        resp = SESSION.get(STORE_API_URL, params=params, timeout=20)
        resp.raise_for_status()
        data = resp.json()

        # Adjust these key paths after confirming the real JSON structure
        # in DevTools (see README.md Step 2).
        items = data.get("data", {}).get("items", [])
        if not items:
            break
        all_items.extend(items)

        total = data.get("data", {}).get("totalResults", len(all_items))
        if len(all_items) >= total:
            break
        page += 1

    return all_items


def fetch_products_nextdata():
    """Fallback: parse product data from the __NEXT_DATA__ JSON in the store page HTML."""
    resp = SESSION.get(STORE_PAGE_URL, timeout=20)
    resp.raise_for_status()

    match = re.search(
        r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
        resp.text,
        re.DOTALL,
    )
    if not match:
        raise ValueError("__NEXT_DATA__ not found in page HTML")

    payload = json.loads(match.group(1))

    # Navigate the nested structure — exact path depends on Lazada's version.
    # Common paths to try if this one fails:
    #   payload["props"]["pageProps"]["initialData"]["data"]["items"]
    #   payload["props"]["initialProps"]["pageData"]["mainInfo"]["items"]
    items = (
        payload
        .get("props", {})
        .get("pageProps", {})
        .get("initialData", {})
        .get("data", {})
        .get("items", [])
    )
    return items


def fetch_products():
    """Try the API endpoint first; fall back to __NEXT_DATA__ parsing."""
    if SELLER_ID == "REPLACE_ME":
        log.warning(
            "SELLER_ID is not set in config.py — falling back to __NEXT_DATA__ parser. "
            "Complete the DevTools step in README.md to use the faster API path."
        )
        return fetch_products_nextdata()

    try:
        items = fetch_products_api()
        log.info(f"Fetched {len(items)} products via API")
        return items
    except Exception as exc:
        log.warning(f"API fetch failed ({exc}), trying __NEXT_DATA__ fallback")
        items = fetch_products_nextdata()
        log.info(f"Fetched {len(items)} products via __NEXT_DATA__")
        return items


# ── Normalisation ─────────────────────────────────────────────────────────────

def normalise_product(raw):
    """
    Convert a raw Lazada item dict into a consistent internal format.

    Field names below are the most common ones seen in Lazada responses.
    After the DevTools step you may need to adjust one or two of these paths.
    """
    product_id = str(raw.get("itemId") or raw.get("productId") or raw.get("id", ""))
    name = raw.get("name") or raw.get("title", "")
    url = raw.get("productUrl") or raw.get("itemUrl") or raw.get("url", "")

    # Ensure URL is absolute
    if url.startswith("//"):
        url = "https:" + url
    elif url.startswith("/"):
        url = "https://www.lazada.sg" + url

    # Stock status — Lazada uses different fields depending on page/API version
    in_stock = bool(
        raw.get("inStock")
        or raw.get("sellable")
        or (raw.get("stock", 0) > 0)
        or raw.get("available")
    )

    # Nested fallback: priceInfo.inStock
    if not in_stock and isinstance(raw.get("priceInfo"), dict):
        in_stock = bool(raw["priceInfo"].get("inStock"))

    return {"id": product_id, "name": name, "url": url, "in_stock": in_stock}


# ── Filtering ─────────────────────────────────────────────────────────────────

def is_pokemon_tcg(product):
    return POKEMON_TCG_KEYWORD in product["name"]


# ── State persistence ─────────────────────────────────────────────────────────

def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {"products": {}}


def save_state(products):
    state = {
        "last_updated": datetime.now(SGT).isoformat(),
        "products": {p["id"]: p for p in products},
    }
    STATE_FILE.write_text(
        json.dumps(state, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


# ── Restock detection ─────────────────────────────────────────────────────────

def detect_restocks(current_products, previous_state):
    prev = previous_state.get("products", {})
    restocked = []

    for product in current_products:
        pid = product["id"]
        was_out_of_stock = not prev.get(pid, {}).get("in_stock", True)
        is_new = pid not in prev

        if product["in_stock"] and (was_out_of_stock or is_new):
            restocked.append(product)

    return restocked


# ── Notifications ─────────────────────────────────────────────────────────────

def send_notification(product):
    topic = os.environ.get("NTFY_TOPIC", "")
    if not topic:
        log.warning("NTFY_TOPIC not set — skipping notification")
        return

    try:
        requests.post(
            f"https://ntfy.sh/{topic}",
            headers={
                "Title": "Pokemon TCG Restock!",
                "Priority": "high",
                "Tags": "rotating_light",
                "Click": product["url"],
                "Content-Type": "text/plain; charset=utf-8",
            },
            data=f"{product['name']}\nTap to buy now on Lazada".encode("utf-8"),
            timeout=10,
        )
        log.info(f"Notification sent: {product['name']}")
    except Exception as exc:
        log.error(f"Notification failed: {exc}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    log.info("Starting Pokemon TCG restock monitor")
    previous_state = load_state()

    try:
        raw_items = fetch_products()
    except Exception as exc:
        log.error(f"Failed to fetch products: {exc}")
        sys.exit(1)

    normalised = [normalise_product(item) for item in raw_items]
    tcg_products = [p for p in normalised if is_pokemon_tcg(p)]
    log.info(f"Found {len(tcg_products)} Pokémon Trading Card Game products")

    restocked = detect_restocks(tcg_products, previous_state)
    log.info(f"Detected {len(restocked)} restock event(s)")

    for product in restocked:
        send_notification(product)
        time.sleep(1)

    save_state(tcg_products)
    log.info("State saved — run complete")


if __name__ == "__main__":
    main()
