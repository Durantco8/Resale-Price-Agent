"""Curated seed list — Pokemon cards tracked proactively from day one.

Two categories: sealed products (booster boxes, ETBs, premium collections)
and graded singles (PSA-graded individual cards). Each entry has a 'query'
(eBay search term), 'display_name' (user-facing label), 'category'
("sealed" or "graded"), and 'ebay_category_id' for eBay Browse API filtering.

eBay category ID: 183454 = CCG Individual Cards / Sealed Products
"""

from resale_price_agent.db import seed_tracked_item

SEED_ITEMS = [
    # ── Sealed Products — Vintage ────────────────────────────────────
    {"query": "Pokemon Base Set 1st Edition Booster Box", "display_name": "Base Set 1st Ed. Booster Box", "category": "sealed", "ebay_category_id": "183454"},
    {"query": "Pokemon Base Set Shadowless Booster Box", "display_name": "Base Set Shadowless Booster Box", "category": "sealed", "ebay_category_id": "183454"},
    {"query": "Pokemon Base Set Unlimited Booster Box", "display_name": "Base Set Unlimited Booster Box", "category": "sealed", "ebay_category_id": "183454"},
    {"query": "Pokemon Neo Genesis Booster Box sealed", "display_name": "Neo Genesis Booster Box", "category": "sealed", "ebay_category_id": "183454"},
    {"query": "Pokemon Neo Discovery Booster Box sealed", "display_name": "Neo Discovery Booster Box", "category": "sealed", "ebay_category_id": "183454"},
    {"query": "Pokemon Jungle 1st Edition Booster Box", "display_name": "Jungle 1st Ed. Booster Box", "category": "sealed", "ebay_category_id": "183454"},
    {"query": "Pokemon Fossil 1st Edition Booster Box", "display_name": "Fossil 1st Ed. Booster Box", "category": "sealed", "ebay_category_id": "183454"},
    {"query": "Pokemon Base Set 1st Edition Booster Pack", "display_name": "Base Set 1st Ed. Booster Pack", "category": "sealed", "ebay_category_id": "183454"},
    {"query": "Pokemon Evolutions Booster Box sealed", "display_name": "Evolutions Booster Box", "category": "sealed", "ebay_category_id": "183454"},
    {"query": "Pokemon Phantom Forces Booster Box sealed", "display_name": "Phantom Forces Booster Box", "category": "sealed", "ebay_category_id": "183454"},

    # ── Sealed Products — Modern Sets ────────────────────────────────
    {"query": "Pokemon Prismatic Evolutions Booster Box", "display_name": "Prismatic Evolutions Booster Box", "category": "sealed", "ebay_category_id": "183454"},
    {"query": "Pokemon Prismatic Evolutions Elite Trainer Box", "display_name": "Prismatic Evolutions ETB", "category": "sealed", "ebay_category_id": "183454"},
    {"query": "Pokemon Surging Sparks Booster Box", "display_name": "Surging Sparks Booster Box", "category": "sealed", "ebay_category_id": "183454"},
    {"query": "Pokemon Surging Sparks Elite Trainer Box", "display_name": "Surging Sparks ETB", "category": "sealed", "ebay_category_id": "183454"},
    {"query": "Pokemon 151 Booster Box", "display_name": "151 Booster Box", "category": "sealed", "ebay_category_id": "183454"},
    {"query": "Pokemon Scarlet Violet Booster Box", "display_name": "Scarlet & Violet Booster Box", "category": "sealed", "ebay_category_id": "183454"},
    {"query": "Pokemon Paldean Fates Booster Box", "display_name": "Paldean Fates Booster Box", "category": "sealed", "ebay_category_id": "183454"},
    {"query": "Pokemon Twilight Masquerade Booster Box", "display_name": "Twilight Masquerade Booster Box", "category": "sealed", "ebay_category_id": "183454"},
    {"query": "Pokemon Obsidian Flames Booster Box", "display_name": "Obsidian Flames Booster Box", "category": "sealed", "ebay_category_id": "183454"},
    {"query": "Pokemon Temporal Forces Booster Box", "display_name": "Temporal Forces Booster Box", "category": "sealed", "ebay_category_id": "183454"},
    {"query": "Pokemon Stellar Crown Booster Box", "display_name": "Stellar Crown Booster Box", "category": "sealed", "ebay_category_id": "183454"},
    {"query": "Pokemon Paradox Rift Booster Box", "display_name": "Paradox Rift Booster Box", "category": "sealed", "ebay_category_id": "183454"},
    {"query": "Pokemon Paldea Evolved Booster Box", "display_name": "Paldea Evolved Booster Box", "category": "sealed", "ebay_category_id": "183454"},
    {"query": "Pokemon Shrouded Fable Booster Box", "display_name": "Shrouded Fable Booster Box", "category": "sealed", "ebay_category_id": "183454"},
    {"query": "Pokemon Vivid Voltage Booster Box sealed", "display_name": "Vivid Voltage Booster Box", "category": "sealed", "ebay_category_id": "183454"},
    {"query": "Pokemon Darkness Ablaze Booster Box sealed", "display_name": "Darkness Ablaze Booster Box", "category": "sealed", "ebay_category_id": "183454"},

    # ── Sealed Products — ETBs & Premium ─────────────────────────────
    {"query": "Pokemon Hidden Fates Elite Trainer Box sealed", "display_name": "Hidden Fates ETB", "category": "sealed", "ebay_category_id": "183454"},
    {"query": "Pokemon Shining Fates Elite Trainer Box sealed", "display_name": "Shining Fates ETB", "category": "sealed", "ebay_category_id": "183454"},
    {"query": "Pokemon Crown Zenith Elite Trainer Box sealed", "display_name": "Crown Zenith ETB", "category": "sealed", "ebay_category_id": "183454"},
    {"query": "Pokemon Celebrations Elite Trainer Box sealed", "display_name": "Celebrations ETB", "category": "sealed", "ebay_category_id": "183454"},
    {"query": "Pokemon Generations Elite Trainer Box sealed", "display_name": "Generations ETB", "category": "sealed", "ebay_category_id": "183454"},
    {"query": "Pokemon 151 Elite Trainer Box", "display_name": "151 ETB", "category": "sealed", "ebay_category_id": "183454"},
    {"query": "Pokemon Evolving Skies Booster Box sealed", "display_name": "Evolving Skies Booster Box", "category": "sealed", "ebay_category_id": "183454"},
    {"query": "Pokemon Champion's Path Elite Trainer Box sealed", "display_name": "Champion's Path ETB", "category": "sealed", "ebay_category_id": "183454"},
    {"query": "Pokemon Ultra Premium Collection Charizard", "display_name": "Ultra Premium Collection Charizard", "category": "sealed", "ebay_category_id": "183454"},
    {"query": "Pokemon Shining Fates Pikachu V Box sealed", "display_name": "Shining Fates Pikachu V Box", "category": "sealed", "ebay_category_id": "183454"},
    {"query": "Pokemon Crown Zenith Premium Figure Collection", "display_name": "Crown Zenith Premium Figure Collection", "category": "sealed", "ebay_category_id": "183454"},
    {"query": "Pokemon Paldean Fates Great Tusk Premium Collection", "display_name": "Paldean Fates Great Tusk Collection", "category": "sealed", "ebay_category_id": "183454"},
    {"query": "Pokemon Celebrations Ultra Premium Collection", "display_name": "Celebrations Ultra Premium Collection", "category": "sealed", "ebay_category_id": "183454"},
    {"query": "Pokemon Evolving Skies Elite Trainer Box sealed", "display_name": "Evolving Skies ETB", "category": "sealed", "ebay_category_id": "183454"},

    # ── Graded Singles — Vintage Icons ───────────────────────────────
    {"query": "Pokemon Base Set Charizard 1st Edition PSA 10", "display_name": "Base Set Charizard 1st Ed. PSA 10", "category": "graded", "ebay_category_id": "183454"},
    {"query": "Pokemon Base Set Charizard Shadowless PSA 10", "display_name": "Base Set Charizard Shadowless PSA 10", "category": "graded", "ebay_category_id": "183454"},
    {"query": "Pokemon Base Set Charizard Unlimited PSA 9", "display_name": "Base Set Charizard Unlimited PSA 9", "category": "graded", "ebay_category_id": "183454"},
    {"query": "Pokemon Base Set Blastoise 1st Edition PSA 10", "display_name": "Base Set Blastoise 1st Ed. PSA 10", "category": "graded", "ebay_category_id": "183454"},
    {"query": "Pokemon Base Set Venusaur 1st Edition PSA 10", "display_name": "Base Set Venusaur 1st Ed. PSA 10", "category": "graded", "ebay_category_id": "183454"},
    {"query": "Pokemon Neo Genesis Lugia 1st Edition PSA 10", "display_name": "Neo Genesis Lugia 1st Ed. PSA 10", "category": "graded", "ebay_category_id": "183454"},
    {"query": "Pokemon Shining Charizard Neo Destiny PSA 9", "display_name": "Shining Charizard Neo Destiny PSA 9", "category": "graded", "ebay_category_id": "183454"},
    {"query": "Pokemon Shining Magikarp Neo Revelation PSA 10", "display_name": "Shining Magikarp PSA 10", "category": "graded", "ebay_category_id": "183454"},
    {"query": "Pokemon Shining Gyarados Neo Revelation PSA 10", "display_name": "Shining Gyarados PSA 10", "category": "graded", "ebay_category_id": "183454"},
    {"query": "Pokemon Gold Star Rayquaza EX PSA 10", "display_name": "Gold Star Rayquaza PSA 10", "category": "graded", "ebay_category_id": "183454"},
    {"query": "Pokemon Gold Star Umbreon EX PSA 10", "display_name": "Gold Star Umbreon PSA 10", "category": "graded", "ebay_category_id": "183454"},
    {"query": "Pokemon Gold Star Charizard PSA 10", "display_name": "Gold Star Charizard PSA 10", "category": "graded", "ebay_category_id": "183454"},
    {"query": "Pokemon Team Rocket Dark Charizard Holo PSA 10", "display_name": "Dark Charizard Holo PSA 10", "category": "graded", "ebay_category_id": "183454"},
    {"query": "Pokemon Expedition Charizard Holo PSA 10", "display_name": "Expedition Charizard Holo PSA 10", "category": "graded", "ebay_category_id": "183454"},
    {"query": "Pokemon Aquapolis Charizard Holo PSA 10", "display_name": "Aquapolis Charizard Holo PSA 10", "category": "graded", "ebay_category_id": "183454"},
    {"query": "Pokemon Skyridge Charizard Holo PSA 10", "display_name": "Skyridge Charizard Holo PSA 10", "category": "graded", "ebay_category_id": "183454"},

    # ── Graded Singles — Modern Alt Arts & SIRs ──────────────────────
    {"query": "Pokemon Umbreon VMAX Alt Art Evolving Skies PSA 10", "display_name": "Umbreon VMAX Alt Art PSA 10", "category": "graded", "ebay_category_id": "183454"},
    {"query": "Pokemon Charizard VMAX Rainbow Darkness Ablaze PSA 10", "display_name": "Charizard VMAX Rainbow PSA 10", "category": "graded", "ebay_category_id": "183454"},
    {"query": "Pokemon Charizard VSTAR Alt Art PSA 10", "display_name": "Charizard VSTAR Alt Art PSA 10", "category": "graded", "ebay_category_id": "183454"},
    {"query": "Pokemon Pikachu VMAX Alt Art PSA 10", "display_name": "Pikachu VMAX Alt Art PSA 10", "category": "graded", "ebay_category_id": "183454"},
    {"query": "Pokemon Gengar VMAX Alt Art PSA 10", "display_name": "Gengar VMAX Alt Art PSA 10", "category": "graded", "ebay_category_id": "183454"},
    {"query": "Pokemon Lugia VSTAR Alt Art Silver Tempest PSA 10", "display_name": "Lugia VSTAR Alt Art PSA 10", "category": "graded", "ebay_category_id": "183454"},
    {"query": "Pokemon Giratina VSTAR Alt Art PSA 10", "display_name": "Giratina VSTAR Alt Art PSA 10", "category": "graded", "ebay_category_id": "183454"},
    {"query": "Pokemon Rayquaza VMAX Alt Art Evolving Skies PSA 10", "display_name": "Rayquaza VMAX Alt Art PSA 10", "category": "graded", "ebay_category_id": "183454"},
    {"query": "Pokemon Mewtwo GX Secret Rare PSA 10", "display_name": "Mewtwo GX Secret Rare PSA 10", "category": "graded", "ebay_category_id": "183454"},
    {"query": "Pokemon Umbreon ex SIR Prismatic Evolutions PSA 10", "display_name": "Umbreon ex SIR PSA 10", "category": "graded", "ebay_category_id": "183454"},
    {"query": "Pokemon Charizard ex SIR Obsidian Flames PSA 10", "display_name": "Charizard ex SIR PSA 10", "category": "graded", "ebay_category_id": "183454"},
    {"query": "Pokemon Pikachu ex SIR Surging Sparks PSA 10", "display_name": "Pikachu ex SIR PSA 10", "category": "graded", "ebay_category_id": "183454"},
    {"query": "Pokemon Mega Gengar ex SIR PSA 10", "display_name": "Mega Gengar ex SIR PSA 10", "category": "graded", "ebay_category_id": "183454"},

    # ── Graded Singles — Modern Chase Cards ──────────────────────────
    {"query": "Pokemon Paldean Fates Charizard ex Shiny PSA 10", "display_name": "Charizard ex Shiny SV PSA 10", "category": "graded", "ebay_category_id": "183454"},
    {"query": "Pokemon Hidden Fates Charizard GX Shiny PSA 10", "display_name": "Charizard GX Shiny SV PSA 10", "category": "graded", "ebay_category_id": "183454"},
    {"query": "Pokemon 151 Charizard ex Full Art PSA 10", "display_name": "151 Charizard ex Full Art PSA 10", "category": "graded", "ebay_category_id": "183454"},
    {"query": "Pokemon 151 Mew ex Full Art PSA 10", "display_name": "151 Mew ex Full Art PSA 10", "category": "graded", "ebay_category_id": "183454"},
    {"query": "Pokemon Obsidian Flames Charizard ex Alt Art PSA 10", "display_name": "Charizard ex Alt Art OF PSA 10", "category": "graded", "ebay_category_id": "183454"},
    {"query": "Pokemon Surging Sparks Pikachu ex SAR PSA 10", "display_name": "Pikachu ex SAR PSA 10", "category": "graded", "ebay_category_id": "183454"},
    {"query": "Pokemon Temporal Forces Terapagos ex Alt Art PSA 10", "display_name": "Terapagos ex Alt Art PSA 10", "category": "graded", "ebay_category_id": "183454"},
    {"query": "Pokemon Crown Zenith Giratina VSTAR Gold PSA 10", "display_name": "Giratina VSTAR Gold PSA 10", "category": "graded", "ebay_category_id": "183454"},
    {"query": "Pokemon Celebrations Charizard Holo Classic PSA 10", "display_name": "Celebrations Charizard Classic PSA 10", "category": "graded", "ebay_category_id": "183454"},
    {"query": "Pokemon Ancient Mew Promo PSA 10", "display_name": "Ancient Mew Promo PSA 10", "category": "graded", "ebay_category_id": "183454"},
    {"query": "Pokemon Van Gogh Pikachu Promo PSA 10", "display_name": "Van Gogh Pikachu Promo PSA 10", "category": "graded", "ebay_category_id": "183454"},
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
            category=entry.get("category"),
        )
        if was_created:
            created += 1
        else:
            existing += 1

    return {"created": created, "existing": existing}
