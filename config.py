# Confirmed via live browser Network tab inspection on 2026-05-06
STORE_API_URL = "https://www.lazada.sg/pokemon-store-online-singapore/"
SHOP_ID = "2056827"
PAGE_SIZE = 40

# Lazada requires these params to return JSON instead of HTML
STORE_PARAMS_BASE = {
    "ajax": "true",
    "q": "All-Products",
    "shopId": SHOP_ID,
    "sc": "KVUG",
    "search_scenario": "store",
    "src": "store_sections",
    "langFlag": "en",
}

# Products must contain at least one of these strings to be monitored.
# "Trading Card Game" catches:  "Pokémon Trading Card Game: ..."
#                               "Pokémon Center Trading Card Game: ..."
# "TCG" catches:                "Pokémon Center Original TCG ..."
POKEMON_TCG_KEYWORDS = ["Trading Card Game", "TCG"]
