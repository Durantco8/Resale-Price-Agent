"""Curated seed list — popular items tracked proactively from day one.

Spans multiple categories so the site reads as general-purpose, not niche.
Each entry is a dict with 'query' (eBay search term) and 'display_name'
(user-facing label for the homepage/trending section).

Items are grouped by category for readability. Categories are stored
alongside each item so tests and UI can verify diversity.
"""

from resale_price_agent.db import seed_tracked_item

SEED_ITEMS = [
    # ── Sneakers ──────────────────────────────────────────────────────
    {"query": "Jordan 4 Retro Military Black", "display_name": "Jordan 4 Retro Military Black", "category": "sneakers"},
    {"query": "Nike Dunk Low Panda", "display_name": "Nike Dunk Low Panda", "category": "sneakers"},
    {"query": "New Balance 550 White Green", "display_name": "New Balance 550 White Green", "category": "sneakers"},
    {"query": "Yeezy Boost 350 V2 Beluga", "display_name": "Yeezy Boost 350 V2 Beluga", "category": "sneakers"},
    {"query": "Air Jordan 1 Retro High OG Chicago", "display_name": "Air Jordan 1 Retro High OG Chicago", "category": "sneakers"},
    {"query": "Nike Air Max 90", "display_name": "Nike Air Max 90", "category": "sneakers"},
    {"query": "New Balance 2002R Protection Pack", "display_name": "New Balance 2002R Protection Pack", "category": "sneakers"},
    {"query": "Nike Air Force 1 Low White", "display_name": "Nike Air Force 1 Low White", "category": "sneakers"},
    {"query": "Adidas Samba OG White", "display_name": "Adidas Samba OG White", "category": "sneakers"},
    {"query": "Jordan 11 Retro Cool Grey", "display_name": "Jordan 11 Retro Cool Grey", "category": "sneakers"},

    # ── Gaming ────────────────────────────────────────────────────────
    {"query": "PlayStation 5 Console", "display_name": "PlayStation 5 Console", "category": "gaming"},
    {"query": "Nintendo Switch OLED", "display_name": "Nintendo Switch OLED", "category": "gaming"},
    {"query": "Xbox Series X Console", "display_name": "Xbox Series X Console", "category": "gaming"},
    {"query": "Steam Deck OLED 512GB", "display_name": "Steam Deck OLED 512GB", "category": "gaming"},
    {"query": "PlayStation VR2", "display_name": "PlayStation VR2", "category": "gaming"},
    {"query": "Nintendo Game Boy Color", "display_name": "Nintendo Game Boy Color", "category": "gaming"},
    {"query": "Nintendo 64 Console", "display_name": "Nintendo 64 Console", "category": "gaming"},
    {"query": "Meta Quest 3 128GB", "display_name": "Meta Quest 3 128GB", "category": "gaming"},

    # ── Phones & Tablets ──────────────────────────────────────────────
    {"query": "iPhone 15 Pro Max 256GB", "display_name": "iPhone 15 Pro Max 256GB", "category": "phones"},
    {"query": "iPhone 14 Pro 128GB", "display_name": "iPhone 14 Pro 128GB", "category": "phones"},
    {"query": "Samsung Galaxy S24 Ultra", "display_name": "Samsung Galaxy S24 Ultra", "category": "phones"},
    {"query": "iPad Pro M4 11 inch", "display_name": "iPad Pro M4 11-inch", "category": "phones"},
    {"query": "Google Pixel 8 Pro", "display_name": "Google Pixel 8 Pro", "category": "phones"},
    {"query": "iPad Air M2", "display_name": "iPad Air M2", "category": "phones"},
    {"query": "Samsung Galaxy Z Flip 5", "display_name": "Samsung Galaxy Z Flip 5", "category": "phones"},
    {"query": "iPhone 13 128GB", "display_name": "iPhone 13 128GB", "category": "phones"},

    # ── Audio ─────────────────────────────────────────────────────────
    {"query": "Apple AirPods Pro 2", "display_name": "Apple AirPods Pro 2", "category": "audio"},
    {"query": "Sony WH-1000XM5", "display_name": "Sony WH-1000XM5", "category": "audio"},
    {"query": "Bose QuietComfort Ultra Headphones", "display_name": "Bose QuietComfort Ultra", "category": "audio"},
    {"query": "Apple AirPods Max", "display_name": "Apple AirPods Max", "category": "audio"},
    {"query": "Sonos Era 300", "display_name": "Sonos Era 300", "category": "audio"},
    {"query": "Sennheiser HD 600", "display_name": "Sennheiser HD 600", "category": "audio"},

    # ── Trading Cards ─────────────────────────────────────────────────
    {"query": "Pokemon Base Set Booster Pack", "display_name": "Pokémon Base Set Booster Pack", "category": "trading_cards"},
    {"query": "Pokemon 151 Elite Trainer Box", "display_name": "Pokémon 151 Elite Trainer Box", "category": "trading_cards"},
    {"query": "Topps Chrome Baseball Hobby Box 2024", "display_name": "Topps Chrome Baseball Hobby Box 2024", "category": "trading_cards"},
    {"query": "Panini Prizm Basketball Hobby Box", "display_name": "Panini Prizm Basketball Hobby Box", "category": "trading_cards"},
    {"query": "Magic The Gathering Modern Horizons 3 Collector Box", "display_name": "MTG Modern Horizons 3 Collector Box", "category": "trading_cards"},
    {"query": "Pokemon Scarlet Violet Booster Box", "display_name": "Pokémon Scarlet & Violet Booster Box", "category": "trading_cards"},
    {"query": "Yu-Gi-Oh 25th Anniversary Rarity Collection Box", "display_name": "Yu-Gi-Oh! 25th Anniversary Rarity Collection", "category": "trading_cards"},
    {"query": "Topps UEFA Champions League Chrome Hobby Box", "display_name": "Topps UEFA Champions League Chrome Hobby", "category": "trading_cards"},

    # ── LEGO ──────────────────────────────────────────────────────────
    {"query": "Lego Star Wars Millennium Falcon 75192", "display_name": "LEGO Star Wars Millennium Falcon 75192", "category": "lego"},
    {"query": "Lego Titanic 10294", "display_name": "LEGO Titanic 10294", "category": "lego"},
    {"query": "Lego Haunted Mansion 40521", "display_name": "LEGO Haunted Mansion 40521", "category": "lego"},
    {"query": "Lego Rivendell Lord of the Rings 10316", "display_name": "LEGO Rivendell 10316", "category": "lego"},
    {"query": "Lego Technic Lamborghini Sian 42115", "display_name": "LEGO Technic Lamborghini Sian 42115", "category": "lego"},
    {"query": "Lego Icons Orchid 10311", "display_name": "LEGO Icons Orchid 10311", "category": "lego"},
    {"query": "Lego Star Wars AT-AT 75313", "display_name": "LEGO Star Wars AT-AT 75313", "category": "lego"},

    # ── Watches ───────────────────────────────────────────────────────
    {"query": "Casio G-Shock GA-2100 CasiOak", "display_name": "Casio G-Shock CasiOak GA-2100", "category": "watches"},
    {"query": "Seiko Presage Cocktail Time", "display_name": "Seiko Presage Cocktail Time", "category": "watches"},
    {"query": "Omega Swatch MoonSwatch", "display_name": "Omega x Swatch MoonSwatch", "category": "watches"},
    {"query": "Casio A168WA-1 Digital Watch", "display_name": "Casio A168WA-1 Vintage Digital", "category": "watches"},
    {"query": "Seiko SKX007", "display_name": "Seiko SKX007", "category": "watches"},
    {"query": "Garmin Fenix 7X", "display_name": "Garmin Fenix 7X", "category": "watches"},
    {"query": "Apple Watch Ultra 2", "display_name": "Apple Watch Ultra 2", "category": "watches"},

    # ── Cameras & Vintage Tech ────────────────────────────────────────
    {"query": "Contax T2 Film Camera", "display_name": "Contax T2 Film Camera", "category": "cameras"},
    {"query": "Canon AE-1 Program", "display_name": "Canon AE-1 Program", "category": "cameras"},
    {"query": "Fujifilm X100VI", "display_name": "Fujifilm X100VI", "category": "cameras"},
    {"query": "Apple iPod Classic 160GB", "display_name": "Apple iPod Classic 160GB", "category": "cameras"},
    {"query": "Sony Walkman WM-F2015", "display_name": "Sony Walkman WM-F2015", "category": "cameras"},
    {"query": "Polaroid SX-70 Camera", "display_name": "Polaroid SX-70", "category": "cameras"},
    {"query": "GoPro Hero 12 Black", "display_name": "GoPro Hero 12 Black", "category": "cameras"},

    # ── Streetwear & Fashion ──────────────────────────────────────────
    {"query": "Supreme Box Logo Hoodie", "display_name": "Supreme Box Logo Hoodie", "category": "streetwear"},
    {"query": "Fear of God Essentials Hoodie", "display_name": "Fear of God Essentials Hoodie", "category": "streetwear"},
    {"query": "Stussy Basic Logo Tee", "display_name": "Stussy Basic Logo Tee", "category": "streetwear"},
    {"query": "The North Face Nuptse 1996", "display_name": "The North Face Nuptse 1996", "category": "streetwear"},
    {"query": "Carhartt WIP Active Jacket", "display_name": "Carhartt WIP Active Jacket", "category": "streetwear"},
    {"query": "Vintage Grateful Dead T-Shirt", "display_name": "Vintage Grateful Dead Tee", "category": "streetwear"},
    {"query": "Chrome Hearts Trucker Hat", "display_name": "Chrome Hearts Trucker Hat", "category": "streetwear"},

    # ── Home & Outdoor ────────────────────────────────────────────────
    {"query": "Dyson V15 Detect Vacuum", "display_name": "Dyson V15 Detect", "category": "home"},
    {"query": "Stanley Quencher H2.0 Tumbler 40oz", "display_name": "Stanley Quencher H2.0 40oz", "category": "home"},
    {"query": "Vitamix A3500 Blender", "display_name": "Vitamix A3500 Blender", "category": "home"},
    {"query": "Le Creuset Dutch Oven 5.5 Qt", "display_name": "Le Creuset Dutch Oven 5.5 Qt", "category": "home"},
    {"query": "YETI Tundra 45 Cooler", "display_name": "YETI Tundra 45 Cooler", "category": "home"},
    {"query": "KitchenAid Artisan Stand Mixer", "display_name": "KitchenAid Artisan Stand Mixer", "category": "home"},
    {"query": "Dyson Airwrap Complete", "display_name": "Dyson Airwrap Complete", "category": "home"},
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
        )
        if was_created:
            created += 1
        else:
            existing += 1

    return {"created": created, "existing": existing}
