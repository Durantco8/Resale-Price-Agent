"""eBay condition normalization and per-listing labeling."""

# Maps lowercased eBay API condition strings → official tier names.
# Every recognized string must appear here; anything missing falls to "Other".
CONDITION_MAP = {
    # New
    "new": "New",
    "new with box": "New",
    "new without box": "New",
    "new with tags": "New",
    "new without tags": "New",
    # Open Box
    "new other / open box": "Open Box",
    "new other": "Open Box",
    "open box": "Open Box",
    # New with Defects
    "new with imperfections": "New with Defects",
    "new with defects": "New with Defects",
    # Refurbished
    "certified - refurbished": "Refurbished",
    "excellent - refurbished": "Refurbished",
    "very good - refurbished": "Refurbished",
    "good - refurbished": "Refurbished",
    "certified / professionally refurbished": "Refurbished",
    # Pre-owned - Excellent
    "pre-owned - excellent": "Pre-owned - Excellent",
    # Pre-owned - Good
    "pre-owned - good": "Pre-owned - Good",
    "pre-owned": "Pre-owned - Good",
    "used": "Pre-owned - Good",
    # Pre-owned - Fair
    "pre-owned - fair": "Pre-owned - Fair",
    # For Parts
    "for parts or not working": "For Parts",
    "for parts or not working": "For Parts",
}


def normalize_condition(raw: str | None) -> str:
    """Map a raw eBay condition string to an official tier name."""
    if not raw:
        return "Other"
    return CONDITION_MAP.get(raw.strip().lower(), "Other")


def get_condition_groups(snapshots: list[dict]) -> list[str]:
    """Return sorted list of unique condition tiers present in snapshots."""
    tiers = {normalize_condition(s.get("condition")) for s in snapshots}
    return sorted(tiers)


def label_listings(
    snapshots: list[dict],
    signals_by_condition: dict,
) -> list[dict]:
    """Label each snapshot relative to its condition group's median price.

    Returns a list of dicts with: snapshot_id, ebay_item_id, label,
    vs_median_pct, condition_group.  Snapshots whose condition group
    has insufficient data are skipped.
    """
    labels = []
    for snap in snapshots:
        group = normalize_condition(snap.get("condition"))
        signals = signals_by_condition.get(group)
        if not signals or not signals.sufficient_data:
            continue
        median = signals.latest_batch_median
        if not median:
            continue

        price = float(snap["price"])
        pct = round(((price - median) / median) * 100, 2)

        if pct < -10:
            label = "Good Buy"
        elif pct > 10:
            label = "Overpriced"
        else:
            label = "Fair Price"

        labels.append({
            "snapshot_id": snap.get("id"),
            "ebay_item_id": snap.get("ebay_item_id"),
            "label": label,
            "vs_median_pct": pct,
            "condition_group": group,
        })

    return labels
