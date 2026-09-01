"""Curated seed list — popular items tracked proactively from day one.

Spans multiple categories so the site reads as general-purpose, not niche.
Each entry is a dict with 'query' (eBay search term) and 'display_name'
(user-facing label for the homepage/trending section).
"""

from resale_price_agent.db import seed_tracked_item

SEED_ITEMS = [
    # Sneakers
    {
        "query": "Jordan 4 Retro Military Black",
        "display_name": "Jordan 4 Retro Military Black",
    },
    {
        "query": "Nike Dunk Low Panda",
        "display_name": "Nike Dunk Low Panda",
    },
    {
        "query": "New Balance 550 White Green",
        "display_name": "New Balance 550 White Green",
    },
    # Electronics
    {
        "query": "PlayStation 5 Console",
        "display_name": "PlayStation 5 Console",
    },
    {
        "query": "Apple AirPods Pro 2",
        "display_name": "Apple AirPods Pro 2",
    },
    {
        "query": "Nintendo Switch OLED",
        "display_name": "Nintendo Switch OLED",
    },
    # Collectibles
    {
        "query": "Pokemon Base Set Booster Pack",
        "display_name": "Pokémon Base Set Booster Pack",
    },
    {
        "query": "Lego Star Wars Millennium Falcon 75192",
        "display_name": "LEGO Star Wars Millennium Falcon 75192",
    },
]


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
