"""Curated seed list — Pokemon cards tracked proactively from day one.

Two categories: graded (PSA-graded cards) and raw (ungraded singles).
Each entry has a 'query' (eBay search term with card number for precision),
'display_name' (user-facing label), 'category' ("graded" or "raw"),
and 'ebay_category_id' for eBay Browse API filtering.

Query strategy:
  - Graded: "Pokemon [Card] [Number] [Set] PSA [Grade]" — PSA filters naturally
  - Raw: "Pokemon [Card] [Number] [Set]" — card number is the most precise ID

eBay category ID: 183454 = CCG Individual Cards / Sealed Products
"""

from resale_price_agent.db import seed_tracked_item

SEED_ITEMS = [
    # ── Graded — Vintage Icons ───────────────────────────────────────
    {"query": "Pokemon Charizard 4/102 Base Set PSA 10", "display_name": "Charizard 4/102 Base Set PSA 10", "category": "graded", "ebay_category_id": "183454"},
    {"query": "Pokemon Charizard 4/102 Base Set PSA 9", "display_name": "Charizard 4/102 Base Set PSA 9", "category": "graded", "ebay_category_id": "183454"},
    {"query": "Pokemon Charizard 4/102 Base Set 1st Edition PSA 9", "display_name": "Charizard 1st Ed. Base Set PSA 9", "category": "graded", "ebay_category_id": "183454"},
    {"query": "Pokemon Blastoise 2/102 Base Set PSA 10", "display_name": "Blastoise 2/102 Base Set PSA 10", "category": "graded", "ebay_category_id": "183454"},
    {"query": "Pokemon Venusaur 15/102 Base Set PSA 10", "display_name": "Venusaur 15/102 Base Set PSA 10", "category": "graded", "ebay_category_id": "183454"},
    {"query": "Pokemon Lugia 9/111 Neo Genesis 1st Edition PSA 10", "display_name": "Lugia 1st Ed. Neo Genesis PSA 10", "category": "graded", "ebay_category_id": "183454"},
    {"query": "Pokemon Shining Charizard 107/105 Neo Destiny PSA 9", "display_name": "Shining Charizard Neo Destiny PSA 9", "category": "graded", "ebay_category_id": "183454"},
    {"query": "Pokemon Shining Magikarp 66/64 Neo Revelation PSA 10", "display_name": "Shining Magikarp PSA 10", "category": "graded", "ebay_category_id": "183454"},
    {"query": "Pokemon Shining Gyarados 65/64 Neo Revelation PSA 10", "display_name": "Shining Gyarados PSA 10", "category": "graded", "ebay_category_id": "183454"},
    {"query": "Pokemon Dark Charizard 4/82 Team Rocket PSA 10", "display_name": "Dark Charizard Team Rocket PSA 10", "category": "graded", "ebay_category_id": "183454"},
    {"query": "Pokemon Charizard 6/165 Expedition PSA 10", "display_name": "Charizard Expedition PSA 10", "category": "graded", "ebay_category_id": "183454"},
    {"query": "Pokemon Charizard H28 Skyridge PSA 10", "display_name": "Charizard Skyridge PSA 10", "category": "graded", "ebay_category_id": "183454"},
    {"query": "Pokemon Charizard H28 Aquapolis PSA 10", "display_name": "Charizard Aquapolis PSA 10", "category": "graded", "ebay_category_id": "183454"},
    {"query": "Pokemon Gold Star Charizard 100/101 PSA 10", "display_name": "Gold Star Charizard PSA 10", "category": "graded", "ebay_category_id": "183454"},
    {"query": "Pokemon Gold Star Umbreon 17/17 POP Series 5 PSA 10", "display_name": "Gold Star Umbreon PSA 10", "category": "graded", "ebay_category_id": "183454"},
    {"query": "Pokemon Gold Star Rayquaza 107/107 PSA 10", "display_name": "Gold Star Rayquaza PSA 10", "category": "graded", "ebay_category_id": "183454"},

    # ── Graded — Modern Alt Arts & SIRs ──────────────────────────────
    {"query": "Pokemon Umbreon VMAX 215/203 Evolving Skies PSA 10", "display_name": "Umbreon VMAX Alt Art PSA 10", "category": "graded", "ebay_category_id": "183454"},
    {"query": "Pokemon Charizard VSTAR 174/172 Brilliant Stars PSA 10", "display_name": "Charizard VSTAR Alt Art PSA 10", "category": "graded", "ebay_category_id": "183454"},
    {"query": "Pokemon Pikachu VMAX 279/264 Vivid Voltage PSA 10", "display_name": "Pikachu VMAX Alt Art PSA 10", "category": "graded", "ebay_category_id": "183454"},
    {"query": "Pokemon Gengar VMAX 271/264 Fusion Strike PSA 10", "display_name": "Gengar VMAX Alt Art PSA 10", "category": "graded", "ebay_category_id": "183454"},
    {"query": "Pokemon Lugia VSTAR 202/195 Silver Tempest PSA 10", "display_name": "Lugia VSTAR Alt Art PSA 10", "category": "graded", "ebay_category_id": "183454"},
    {"query": "Pokemon Giratina VSTAR 261/196 Lost Origin PSA 10", "display_name": "Giratina VSTAR Alt Art PSA 10", "category": "graded", "ebay_category_id": "183454"},
    {"query": "Pokemon Rayquaza VMAX 218/203 Evolving Skies PSA 10", "display_name": "Rayquaza VMAX Alt Art PSA 10", "category": "graded", "ebay_category_id": "183454"},
    {"query": "Pokemon Umbreon ex 236/198 Prismatic Evolutions PSA 10", "display_name": "Umbreon ex SIR PSA 10", "category": "graded", "ebay_category_id": "183454"},
    {"query": "Pokemon Charizard ex 223/197 Obsidian Flames PSA 10", "display_name": "Charizard ex SIR PSA 10", "category": "graded", "ebay_category_id": "183454"},
    {"query": "Pokemon Pikachu ex 237/182 Surging Sparks PSA 10", "display_name": "Pikachu ex SIR PSA 10", "category": "graded", "ebay_category_id": "183454"},
    {"query": "Pokemon Charizard ex 199/165 151 PSA 10", "display_name": "Charizard ex 151 Full Art PSA 10", "category": "graded", "ebay_category_id": "183454"},
    {"query": "Pokemon Mew ex 205/165 151 PSA 10", "display_name": "Mew ex 151 Full Art PSA 10", "category": "graded", "ebay_category_id": "183454"},
    {"query": "Pokemon Mewtwo GX 158/156 Shining Legends PSA 10", "display_name": "Mewtwo GX Secret Rare PSA 10", "category": "graded", "ebay_category_id": "183454"},

    # ── Graded — Modern Chase ────────────────────────────────────────
    {"query": "Pokemon Charizard GX SV49 Hidden Fates PSA 10", "display_name": "Charizard GX Shiny SV PSA 10", "category": "graded", "ebay_category_id": "183454"},
    {"query": "Pokemon Charizard VMAX 74/73 Champions Path PSA 10", "display_name": "Charizard VMAX Rainbow PSA 10", "category": "graded", "ebay_category_id": "183454"},
    {"query": "Pokemon Charizard ex 234/091 Paldean Fates PSA 10", "display_name": "Charizard ex Shiny SV PSA 10", "category": "graded", "ebay_category_id": "183454"},
    {"query": "Pokemon Ancient Mew Promo PSA 10", "display_name": "Ancient Mew Promo PSA 10", "category": "graded", "ebay_category_id": "183454"},
    {"query": "Pokemon Pikachu Illustrator Promo PSA 9", "display_name": "Pikachu Illustrator PSA 9", "category": "graded", "ebay_category_id": "183454"},
    {"query": "Pokemon Celebrations Charizard 4/102 Classic PSA 10", "display_name": "Celebrations Charizard Classic PSA 10", "category": "graded", "ebay_category_id": "183454"},
    {"query": "Pokemon Van Gogh Pikachu Promo PSA 10", "display_name": "Van Gogh Pikachu PSA 10", "category": "graded", "ebay_category_id": "183454"},
    {"query": "Pokemon Giratina VSTAR 183/172 Crown Zenith PSA 10", "display_name": "Giratina VSTAR Gold PSA 10", "category": "graded", "ebay_category_id": "183454"},
    {"query": "Pokemon Espeon VMAX 270/264 Fusion Strike PSA 10", "display_name": "Espeon VMAX Alt Art PSA 10", "category": "graded", "ebay_category_id": "183454"},
    {"query": "Pokemon Sylveon VMAX 212/203 Evolving Skies PSA 10", "display_name": "Sylveon VMAX Alt Art PSA 10", "category": "graded", "ebay_category_id": "183454"},
    {"query": "Pokemon Moonbreon VMAX 215/203 Evolving Skies PSA 10", "display_name": "Moonbreon VMAX PSA 10", "category": "graded", "ebay_category_id": "183454"},

    # ── Raw — Vintage Holos ──────────────────────────────────────────
    {"query": "Pokemon Charizard 4/102 Base Set holo", "display_name": "Charizard 4/102 Base Set Holo", "category": "raw", "ebay_category_id": "183454"},
    {"query": "Pokemon Blastoise 2/102 Base Set holo", "display_name": "Blastoise 2/102 Base Set Holo", "category": "raw", "ebay_category_id": "183454"},
    {"query": "Pokemon Venusaur 15/102 Base Set holo", "display_name": "Venusaur 15/102 Base Set Holo", "category": "raw", "ebay_category_id": "183454"},
    {"query": "Pokemon Lugia 9/111 Neo Genesis holo", "display_name": "Lugia 9/111 Neo Genesis Holo", "category": "raw", "ebay_category_id": "183454"},
    {"query": "Pokemon Dark Charizard 4/82 Team Rocket holo", "display_name": "Dark Charizard 4/82 Holo", "category": "raw", "ebay_category_id": "183454"},
    {"query": "Pokemon Shining Charizard 107/105 Neo Destiny", "display_name": "Shining Charizard 107/105 Raw", "category": "raw", "ebay_category_id": "183454"},
    {"query": "Pokemon Mewtwo 10/102 Base Set holo", "display_name": "Mewtwo 10/102 Base Set Holo", "category": "raw", "ebay_category_id": "183454"},
    {"query": "Pokemon Dragonite 4/62 Fossil holo", "display_name": "Dragonite 4/62 Fossil Holo", "category": "raw", "ebay_category_id": "183454"},
    {"query": "Pokemon Gengar 5/62 Fossil holo", "display_name": "Gengar 5/62 Fossil Holo", "category": "raw", "ebay_category_id": "183454"},
    {"query": "Pokemon Alakazam 1/102 Base Set holo", "display_name": "Alakazam 1/102 Base Set Holo", "category": "raw", "ebay_category_id": "183454"},

    # ── Raw — Modern Alt Arts & SIRs ─────────────────────────────────
    {"query": "Pokemon Umbreon VMAX 215/203 Evolving Skies alt art", "display_name": "Umbreon VMAX 215/203 Alt Art", "category": "raw", "ebay_category_id": "183454"},
    {"query": "Pokemon Charizard VSTAR 174/172 Brilliant Stars", "display_name": "Charizard VSTAR 174/172", "category": "raw", "ebay_category_id": "183454"},
    {"query": "Pokemon Pikachu VMAX 279/264 Vivid Voltage", "display_name": "Pikachu VMAX 279/264", "category": "raw", "ebay_category_id": "183454"},
    {"query": "Pokemon Gengar VMAX 271/264 Fusion Strike alt art", "display_name": "Gengar VMAX 271/264 Alt Art", "category": "raw", "ebay_category_id": "183454"},
    {"query": "Pokemon Lugia VSTAR 202/195 Silver Tempest alt art", "display_name": "Lugia VSTAR 202/195 Alt Art", "category": "raw", "ebay_category_id": "183454"},
    {"query": "Pokemon Giratina VSTAR 261/196 Lost Origin alt art", "display_name": "Giratina VSTAR 261/196 Alt Art", "category": "raw", "ebay_category_id": "183454"},
    {"query": "Pokemon Rayquaza VMAX 218/203 Evolving Skies alt art", "display_name": "Rayquaza VMAX 218/203 Alt Art", "category": "raw", "ebay_category_id": "183454"},
    {"query": "Pokemon Umbreon ex 236/198 Prismatic Evolutions", "display_name": "Umbreon ex 236/198 SIR", "category": "raw", "ebay_category_id": "183454"},
    {"query": "Pokemon Charizard ex 223/197 Obsidian Flames", "display_name": "Charizard ex 223/197 SIR", "category": "raw", "ebay_category_id": "183454"},
    {"query": "Pokemon Pikachu ex 237/182 Surging Sparks", "display_name": "Pikachu ex 237/182 SIR", "category": "raw", "ebay_category_id": "183454"},

    # ── Raw — Modern Chase Cards ─────────────────────────────────────
    {"query": "Pokemon Charizard ex 199/165 151", "display_name": "Charizard ex 199/165 151", "category": "raw", "ebay_category_id": "183454"},
    {"query": "Pokemon Mew ex 205/165 151", "display_name": "Mew ex 205/165 151", "category": "raw", "ebay_category_id": "183454"},
    {"query": "Pokemon Charizard GX SV49 Hidden Fates shiny", "display_name": "Charizard GX SV49 Shiny", "category": "raw", "ebay_category_id": "183454"},
    {"query": "Pokemon Charizard VMAX 74/73 Champions Path", "display_name": "Charizard VMAX 74/73 Rainbow", "category": "raw", "ebay_category_id": "183454"},
    {"query": "Pokemon Charizard ex 234/091 Paldean Fates shiny", "display_name": "Charizard ex 234/091 Shiny SV", "category": "raw", "ebay_category_id": "183454"},
    {"query": "Pokemon Eevee 133/165 151 full art", "display_name": "Eevee 133/165 151 Full Art", "category": "raw", "ebay_category_id": "183454"},
    {"query": "Pokemon Miraidon ex 227/198 Scarlet Violet", "display_name": "Miraidon ex 227/198 SIR", "category": "raw", "ebay_category_id": "183454"},
    {"query": "Pokemon Koraidon ex 231/198 Scarlet Violet", "display_name": "Koraidon ex 231/198 SIR", "category": "raw", "ebay_category_id": "183454"},
    {"query": "Pokemon Gardevoir ex 245/198 Paldea Evolved", "display_name": "Gardevoir ex 245/198 SIR", "category": "raw", "ebay_category_id": "183454"},
    {"query": "Pokemon Arceus VSTAR 176/172 Brilliant Stars", "display_name": "Arceus VSTAR 176/172", "category": "raw", "ebay_category_id": "183454"},

    # ── Raw — Promos & Specials ──────────────────────────────────────
    {"query": "Pokemon Ancient Mew promo card", "display_name": "Ancient Mew Promo Raw", "category": "raw", "ebay_category_id": "183454"},
    {"query": "Pokemon Van Gogh Pikachu promo", "display_name": "Van Gogh Pikachu Promo Raw", "category": "raw", "ebay_category_id": "183454"},
    {"query": "Pokemon Celebrations Charizard 4/102 classic", "display_name": "Celebrations Charizard Classic", "category": "raw", "ebay_category_id": "183454"},
    {"query": "Pokemon Radiant Charizard 11/078 Pokemon GO", "display_name": "Radiant Charizard 11/078", "category": "raw", "ebay_category_id": "183454"},
    {"query": "Pokemon Pikachu 25/25 Celebrations", "display_name": "Pikachu 25/25 Celebrations", "category": "raw", "ebay_category_id": "183454"},
    {"query": "Pokemon Umbreon 1/25 Celebrations", "display_name": "Umbreon 1/25 Celebrations", "category": "raw", "ebay_category_id": "183454"},
    {"query": "Pokemon Charizard 4/25 Celebrations", "display_name": "Charizard 4/25 Celebrations", "category": "raw", "ebay_category_id": "183454"},
    {"query": "Pokemon Zoroark GX 77a/73 Shining Legends", "display_name": "Zoroark GX 77a/73 Secret", "category": "raw", "ebay_category_id": "183454"},
    {"query": "Pokemon Rayquaza GX 177a/168 Celestial Storm", "display_name": "Rayquaza GX 177a/168 Secret", "category": "raw", "ebay_category_id": "183454"},
    {"query": "Pokemon Mew 8 promo holo", "display_name": "Mew Promo Holo", "category": "raw", "ebay_category_id": "183454"},
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
