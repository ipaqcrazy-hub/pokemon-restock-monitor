import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

from config import PAGE_SIZE, POKEMON_TCG_KEYWORDS, STORE_API_URL, STORE_PARAMS_BASE

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
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
    "Referer": "https://www.lazada.sg/pokemon-store-online-singapore/",
    "X-Requested-With": "XMLHttpRequest",
})


def fetch_products_api():
    all_items = []
    page = 1
    while True:
        params = {**STORE_PARAMS_BASE, "page": page}
        resp = SESSION.get(STORE_API_URL, params=params, timeout=20)
        resp.raise_for_status()
        text = resp.text
        log.info(f"Response status={resp.status_code} content-type={resp.headers.get('content-type')} first300={text[:300]!r}")
        start = text.find("{")
        if start == -1:
            raise ValueError(f"No JSON object in response")
        data = json.loads(text[start:])

        items = data.get("mods", {}).get("listItems", [])
        if not items:
            break
        all_items.extend(items)

        total = int(data.get("mainInfo", {}).get("totalResults", 0))
        if len(all_items) >= total:
            break
        page += 1

    log.info(f"Fetched {len(all_items)} products from store")
    return all_items


def normalise_product(raw):
    url = raw.get("itemUrl", "")
    if url.startswith("//"):
        url = "https:" + url
    return {
        "id": str(raw["itemId"]),
        "name": raw.get("name", ""),
        "url": url,
        "in_stock": bool(raw.get("inStock", False)),
    }


def is_pokemon_tcg(product):
    return any(kw in product["name"] for kw in POKEMON_TCG_KEYWORDS)


def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {"products": {}}


def save_state(products):
    state = {
        "last_updated": datetime.now(SGT).isoformat(),
        "products": {p["id"]: p for p in products},
    }
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


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


def main():
    log.info("Starting Pokemon TCG restock monitor")
    previous_state = load_state()

    try:
        raw_items = fetch_products_api()
    except Exception as exc:
        log.error(f"Failed to fetch products: {exc}")
        sys.exit(1)

    normalised = [normalise_product(item) for item in raw_items]
    tcg_products = [p for p in normalised if is_pokemon_tcg(p)]
    log.info(f"Found {len(tcg_products)} Pokemon TCG products")

    restocked = detect_restocks(tcg_products, previous_state)
    log.info(f"Detected {len(restocked)} restock event(s)")

    for product in restocked:
        send_notification(product)
        time.sleep(1)

    save_state(tcg_products)
    log.info("State saved — run complete")


if __name__ == "__main__":
    main()
