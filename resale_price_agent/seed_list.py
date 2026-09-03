"""Curated seed list — popular items tracked proactively from day one.

Spans multiple categories so the site reads as general-purpose, not niche.
Each entry is a dict with 'query' (eBay search term) and 'display_name'
(user-facing label for the homepage/trending section).

Items are grouped by category for readability. Categories are stored
alongside each item so tests and UI can verify diversity.

ebay_category_id restricts the Browse API search to the correct eBay
leaf/branch category, preventing accessories, cases, and replacement
parts from contaminating price data.

Key eBay category IDs used:
  9355   — Cell Phones & Smartphones
  171485 — Tablets & eReaders
  112529 — Headphones
  148581 — Portable Speakers
  139971 — Video Game Consoles
  183068 — VR Headsets
  93427  — Athletic Shoes (Men)
  11450  — Men's Clothing (hoodies/tees/jackets)
  52137  — Hats
  57988  — Coats, Jackets & Vests (Men)
  31387  — Wristwatches
  31388  — Digital Cameras (also GoPro)
  73839  — iPods & MP3 Players
  38230  — Portable Cassette Players
  183454 — CCG Sealed Packs (Pokemon, MTG, Yu-Gi-Oh)
  212    — Sports Trading Cards (Topps, Panini)
  19006  — LEGO Complete Sets & Packs
  20614  — Vacuums
  20321  — Water Bottles
  64136  — Blenders (Countertop)
  25526  — Cookware (Dutch ovens)
  159042 — Camping Ice Boxes & Coolers
  38261  — Stand Mixers
  11658  — Hair Dryers
"""

from resale_price_agent.db import seed_tracked_item

SEED_ITEMS = [
    # ── Sneakers ──────────────────────────────────────────────────────
    # 93427 = Athletic Shoes (Men's)
    {"query": "Jordan 4 Retro Military Black", "display_name": "Jordan 4 Retro Military Black", "category": "sneakers", "ebay_category_id": "93427"},
    {"query": "Nike Dunk Low Panda", "display_name": "Nike Dunk Low Panda", "category": "sneakers", "ebay_category_id": "93427"},
    {"query": "New Balance 550 White Green", "display_name": "New Balance 550 White Green", "category": "sneakers", "ebay_category_id": "93427"},
    {"query": "Yeezy Boost 350 V2 Beluga", "display_name": "Yeezy Boost 350 V2 Beluga", "category": "sneakers", "ebay_category_id": "93427"},
    {"query": "Air Jordan 1 Retro High OG Chicago", "display_name": "Air Jordan 1 Retro High OG Chicago", "category": "sneakers", "ebay_category_id": "93427"},
    {"query": "Nike Air Max 90", "display_name": "Nike Air Max 90", "category": "sneakers", "ebay_category_id": "93427"},
    {"query": "New Balance 2002R Protection Pack", "display_name": "New Balance 2002R Protection Pack", "category": "sneakers", "ebay_category_id": "93427"},
    {"query": "Nike Air Force 1 Low White", "display_name": "Nike Air Force 1 Low White", "category": "sneakers", "ebay_category_id": "93427"},
    {"query": "Adidas Samba OG White", "display_name": "Adidas Samba OG White", "category": "sneakers", "ebay_category_id": "93427"},
    {"query": "Jordan 11 Retro Cool Grey", "display_name": "Jordan 11 Retro Cool Grey", "category": "sneakers", "ebay_category_id": "93427"},

    # ── Gaming ────────────────────────────────────────────────────────
    # 139971 = Video Game Consoles, 183068 = VR Headsets
    {"query": "PlayStation 5 Console", "display_name": "PlayStation 5 Console", "category": "gaming", "ebay_category_id": "139971"},
    {"query": "Nintendo Switch OLED", "display_name": "Nintendo Switch OLED", "category": "gaming", "ebay_category_id": "139971"},
    {"query": "Xbox Series X Console", "display_name": "Xbox Series X Console", "category": "gaming", "ebay_category_id": "139971"},
    {"query": "Steam Deck OLED 512GB", "display_name": "Steam Deck OLED 512GB", "category": "gaming", "ebay_category_id": "139971"},
    {"query": "PlayStation VR2", "display_name": "PlayStation VR2", "category": "gaming", "ebay_category_id": "183068"},
    {"query": "Nintendo Game Boy Color", "display_name": "Nintendo Game Boy Color", "category": "gaming", "ebay_category_id": "139971"},
    {"query": "Nintendo 64 Console", "display_name": "Nintendo 64 Console", "category": "gaming", "ebay_category_id": "139971"},
    {"query": "Meta Quest 3 128GB", "display_name": "Meta Quest 3 128GB", "category": "gaming", "ebay_category_id": "183068"},

    # ── Phones & Tablets ──────────────────────────────────────────────
    # 9355 = Cell Phones & Smartphones, 171485 = Tablets & eReaders
    {"query": "iPhone 15 Pro Max 256GB", "display_name": "iPhone 15 Pro Max 256GB", "category": "phones", "ebay_category_id": "9355"},
    {"query": "iPhone 14 Pro 128GB", "display_name": "iPhone 14 Pro 128GB", "category": "phones", "ebay_category_id": "9355"},
    {"query": "Samsung Galaxy S24 Ultra", "display_name": "Samsung Galaxy S24 Ultra", "category": "phones", "ebay_category_id": "9355"},
    {"query": "iPad Pro M4 11 inch", "display_name": "iPad Pro M4 11-inch", "category": "phones", "ebay_category_id": "171485"},
    {"query": "Google Pixel 8 Pro", "display_name": "Google Pixel 8 Pro", "category": "phones", "ebay_category_id": "9355"},
    {"query": "iPad Air M2", "display_name": "iPad Air M2", "category": "phones", "ebay_category_id": "171485"},
    {"query": "Samsung Galaxy Z Flip 5", "display_name": "Samsung Galaxy Z Flip 5", "category": "phones", "ebay_category_id": "9355"},
    {"query": "iPhone 13 128GB", "display_name": "iPhone 13 128GB", "category": "phones", "ebay_category_id": "9355"},

    # ── Audio ─────────────────────────────────────────────────────────
    # 112529 = Headphones, 148581 = Portable Speakers
    {"query": "Apple AirPods Pro 2", "display_name": "Apple AirPods Pro 2", "category": "audio", "ebay_category_id": "112529"},
    {"query": "Sony WH-1000XM5", "display_name": "Sony WH-1000XM5", "category": "audio", "ebay_category_id": "112529"},
    {"query": "Bose QuietComfort Ultra Headphones", "display_name": "Bose QuietComfort Ultra", "category": "audio", "ebay_category_id": "112529"},
    {"query": "Apple AirPods Max", "display_name": "Apple AirPods Max", "category": "audio", "ebay_category_id": "112529"},
    {"query": "Sonos Era 300", "display_name": "Sonos Era 300", "category": "audio", "ebay_category_id": "148581"},
    {"query": "Sennheiser HD 600", "display_name": "Sennheiser HD 600", "category": "audio", "ebay_category_id": "112529"},

    # ── Trading Cards ─────────────────────────────────────────────────
    # 183454 = CCG Sealed Packs (Pokemon, MTG, Yu-Gi-Oh)
    # 212    = Sports Trading Cards (Topps, Panini)
    {"query": "Pokemon Base Set Booster Pack", "display_name": "Pokémon Base Set Booster Pack", "category": "trading_cards", "ebay_category_id": "183454"},
    {"query": "Pokemon 151 Elite Trainer Box", "display_name": "Pokémon 151 Elite Trainer Box", "category": "trading_cards", "ebay_category_id": "183454"},
    {"query": "Topps Chrome Baseball Hobby Box 2024", "display_name": "Topps Chrome Baseball Hobby Box 2024", "category": "trading_cards", "ebay_category_id": "212"},
    {"query": "Panini Prizm Basketball Hobby Box", "display_name": "Panini Prizm Basketball Hobby Box", "category": "trading_cards", "ebay_category_id": "212"},
    {"query": "Magic The Gathering Modern Horizons 3 Collector Box", "display_name": "MTG Modern Horizons 3 Collector Box", "category": "trading_cards", "ebay_category_id": "183454"},
    {"query": "Pokemon Scarlet Violet Booster Box", "display_name": "Pokémon Scarlet & Violet Booster Box", "category": "trading_cards", "ebay_category_id": "183454"},
    {"query": "Yu-Gi-Oh 25th Anniversary Rarity Collection Box", "display_name": "Yu-Gi-Oh! 25th Anniversary Rarity Collection", "category": "trading_cards", "ebay_category_id": "183454"},
    {"query": "Topps UEFA Champions League Chrome Hobby Box", "display_name": "Topps UEFA Champions League Chrome Hobby", "category": "trading_cards", "ebay_category_id": "212"},

    # ── LEGO ──────────────────────────────────────────────────────────
    # 19006 = LEGO Complete Sets & Packs
    {"query": "Lego Star Wars Millennium Falcon 75192", "display_name": "LEGO Star Wars Millennium Falcon 75192", "category": "lego", "ebay_category_id": "19006"},
    {"query": "Lego Titanic 10294", "display_name": "LEGO Titanic 10294", "category": "lego", "ebay_category_id": "19006"},
    {"query": "Lego Haunted Mansion 40521", "display_name": "LEGO Haunted Mansion 40521", "category": "lego", "ebay_category_id": "19006"},
    {"query": "Lego Rivendell Lord of the Rings 10316", "display_name": "LEGO Rivendell 10316", "category": "lego", "ebay_category_id": "19006"},
    {"query": "Lego Technic Lamborghini Sian 42115", "display_name": "LEGO Technic Lamborghini Sian 42115", "category": "lego", "ebay_category_id": "19006"},
    {"query": "Lego Icons Orchid 10311", "display_name": "LEGO Icons Orchid 10311", "category": "lego", "ebay_category_id": "19006"},
    {"query": "Lego Star Wars AT-AT 75313", "display_name": "LEGO Star Wars AT-AT 75313", "category": "lego", "ebay_category_id": "19006"},

    # ── Watches ───────────────────────────────────────────────────────
    # 31387 = Wristwatches
    {"query": "Casio G-Shock GA-2100 CasiOak", "display_name": "Casio G-Shock CasiOak GA-2100", "category": "watches", "ebay_category_id": "31387"},
    {"query": "Seiko Presage Cocktail Time", "display_name": "Seiko Presage Cocktail Time", "category": "watches", "ebay_category_id": "31387"},
    {"query": "Omega Swatch MoonSwatch", "display_name": "Omega x Swatch MoonSwatch", "category": "watches", "ebay_category_id": "31387"},
    {"query": "Casio A168WA-1 Digital Watch", "display_name": "Casio A168WA-1 Vintage Digital", "category": "watches", "ebay_category_id": "31387"},
    {"query": "Seiko SKX007", "display_name": "Seiko SKX007", "category": "watches", "ebay_category_id": "31387"},
    {"query": "Garmin Fenix 7X", "display_name": "Garmin Fenix 7X", "category": "watches", "ebay_category_id": "31387"},
    {"query": "Apple Watch Ultra 2", "display_name": "Apple Watch Ultra 2", "category": "watches", "ebay_category_id": "31387"},

    # ── Cameras & Vintage Tech ────────────────────────────────────────
    # 31388 = Film Cameras, 31388 = Digital Cameras, 73839 = iPods,
    # 48458 = Portable Audio, 182964 = Action Cameras
    {"query": "Contax T2 Film Camera", "display_name": "Contax T2 Film Camera", "category": "cameras", "ebay_category_id": "31388"},
    {"query": "Canon AE-1 Program", "display_name": "Canon AE-1 Program", "category": "cameras", "ebay_category_id": "31388"},
    {"query": "Fujifilm X100VI", "display_name": "Fujifilm X100VI", "category": "cameras", "ebay_category_id": "31388"},
    {"query": "Apple iPod Classic 160GB", "display_name": "Apple iPod Classic 160GB", "category": "cameras", "ebay_category_id": "73839"},
    {"query": "Sony Walkman WM-F2015", "display_name": "Sony Walkman WM-F2015", "category": "cameras", "ebay_category_id": "38230"},
    {"query": "Polaroid SX-70 Camera", "display_name": "Polaroid SX-70", "category": "cameras", "ebay_category_id": "31388"},
    {"query": "GoPro Hero 12 Black", "display_name": "GoPro Hero 12 Black", "category": "cameras", "ebay_category_id": "31388"},

    # ── Streetwear & Fashion ──────────────────────────────────────────
    # 11450 = Men's Clothing, 52137 = Hats, 183446 = Down & Puffer Jackets
    {"query": "Supreme Box Logo Hoodie", "display_name": "Supreme Box Logo Hoodie", "category": "streetwear", "ebay_category_id": "11450"},
    {"query": "Fear of God Essentials Hoodie", "display_name": "Fear of God Essentials Hoodie", "category": "streetwear", "ebay_category_id": "11450"},
    {"query": "Stussy Basic Logo Tee", "display_name": "Stussy Basic Logo Tee", "category": "streetwear", "ebay_category_id": "11450"},
    {"query": "The North Face Nuptse 1996", "display_name": "The North Face Nuptse 1996", "category": "streetwear", "ebay_category_id": "57988"},
    {"query": "Carhartt WIP Active Jacket", "display_name": "Carhartt WIP Active Jacket", "category": "streetwear", "ebay_category_id": "11450"},
    {"query": "Vintage Grateful Dead T-Shirt", "display_name": "Vintage Grateful Dead Tee", "category": "streetwear", "ebay_category_id": "11450"},
    {"query": "Chrome Hearts Trucker Hat", "display_name": "Chrome Hearts Trucker Hat", "category": "streetwear", "ebay_category_id": "52137"},

    # ── Home & Outdoor ────────────────────────────────────────────────
    {"query": "Dyson V15 Detect Vacuum", "display_name": "Dyson V15 Detect", "category": "home", "ebay_category_id": "20614"},
    {"query": "Stanley Quencher H2.0 Tumbler 40oz", "display_name": "Stanley Quencher H2.0 40oz", "category": "home", "ebay_category_id": "20321"},
    {"query": "Vitamix A3500 Blender", "display_name": "Vitamix A3500 Blender", "category": "home", "ebay_category_id": "64136"},
    {"query": "Le Creuset Dutch Oven 5.5 Qt", "display_name": "Le Creuset Dutch Oven 5.5 Qt", "category": "home", "ebay_category_id": "25526"},
    {"query": "YETI Tundra 45 Cooler", "display_name": "YETI Tundra 45 Cooler", "category": "home", "ebay_category_id": "159042"},
    {"query": "KitchenAid Artisan Stand Mixer", "display_name": "KitchenAid Artisan Stand Mixer", "category": "home", "ebay_category_id": "38261"},
    {"query": "Dyson Airwrap Complete", "display_name": "Dyson Airwrap Complete", "category": "home", "ebay_category_id": "11658"},
]

CATEGORIES = sorted({item["category"] for item in SEED_ITEMS})


def seed_all(engine) -> dict:
    """Create tracked_item rows for every seed item. Safe to call repeatedly.

    Returns ``{"created": N, "existing": N}``.
    """
    created = 0
    existing = 0

    for entry in SEED_ITEMS:
        _, was_created = seed_tracked_item(
            engine,
            entry["query"],
            display_name=entry["display_name"],
            ebay_category_id=entry.get("ebay_category_id"),
        )
        if was_created:
            created += 1
        else:
            existing += 1

    return {"created": created, "existing": existing}
