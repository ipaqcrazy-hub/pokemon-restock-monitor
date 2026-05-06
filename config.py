# ─────────────────────────────────────────────────────────────────────────────
# Fill in STORE_API_URL and SELLER_ID after the browser DevTools step.
# See README.md for instructions.
# ─────────────────────────────────────────────────────────────────────────────

# Step 1 placeholder — replace with the XHR URL you capture in DevTools
STORE_API_URL = "https://www.lazada.sg/store/v2/listItems"

# Step 1 placeholder — replace with the sellerId param value from DevTools
SELLER_ID = "REPLACE_ME"

PAGE_SIZE = 40

# Fallback: the store page URL used when the API endpoint fails
STORE_PAGE_URL = (
    "https://www.lazada.sg/shop/pokemon-store-online-singapore/"
    "?q=All-Products&from=wangpu&langFlag=en&pageTypeId=2"
)

# Only products whose name contains this string are monitored
POKEMON_TCG_KEYWORD = "Pokémon Trading Card Game"
