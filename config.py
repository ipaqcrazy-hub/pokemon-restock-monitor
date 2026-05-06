# Confirmed via live browser Network tab inspection on 2026-05-06
STORE_API_URL = "https://www.lazada.sg/pokemon-store-online-singapore/"
SHOP_ID = "2056827"
SHOP_CATEGORY_ID = "762252"  # Pokemon TCG category
PAGE_SIZE = 40

# Full params from the TCG category page URL + ajax=true to get JSON response
STORE_PARAMS_BASE = {
    "ajax": "true",
    "q": "All-Products",
    "shopId": SHOP_ID,
    "shop_category_ids": SHOP_CATEGORY_ID,
    "sc": "KVUG",
    "search_scenario": "store",
    "src": "store_sections",
    "from": "wangpu",
    "hideSectionHeader": "true",
    "langFlag": "en",
}

# Safety-net keyword filter (server already filters by category, but belt-and-suspenders)
POKEMON_TCG_KEYWORDS = ["Trading Card Game", "TCG"]
