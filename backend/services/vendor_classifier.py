"""Keyword-based merchant category classifier.

Deliberately simple and dependency-free: maps merchant names to the spend
categories the Reward Router understands. A model-based classifier can replace
this behind the same function signature later.
"""

from backend.models import SpendCategory

_KEYWORDS: dict[SpendCategory, tuple[str, ...]] = {
    SpendCategory.FUEL: (
        "shell", "chevron", "exxon", "mobil", "bp ", "sunoco", "citgo",
        "marathon", "speedway", "pilot", "loves travel", "fuel", "gas station",
        "petro", "76 ", "arco", "wawa",
    ),
    SpendCategory.LODGING: (
        "hotel", "motel", "inn ", "marriott", "hilton", "hyatt", "holiday inn",
        "best western", "la quinta", "comfort", "airbnb", "extended stay",
        "lodge", "suites",
    ),
    SpendCategory.MATERIALS: (
        "home depot", "lowes", "lowe's", "menards", "ace hardware", "grainger",
        "fastenal", "ferguson", "lumber", "supply", "hardware", "white cap",
        "sherwin", "builders", "electric supply", "plumbing",
    ),
    SpendCategory.FOOD: (
        "restaurant", "cafe", "coffee", "pizza", "grill", "deli", "diner",
        "mcdonald", "subway", "chipotle", "chick-fil-a", "taco", "burger",
        "starbucks", "dunkin", "bbq", "kitchen", "food",
    ),
    SpendCategory.TRAVEL: (
        "airline", "airways", "united", "delta air", "american air",
        "southwest", "alaska air", "jetblue", "uber", "lyft", "rental car",
        "hertz", "enterprise rent", "avis", "budget rent", "amtrak", "parking",
        "toll",
    ),
}


def classify_merchant(merchant_name: str) -> SpendCategory:
    """Classify a merchant name into a spend category (case-insensitive)."""
    normalized = f"{merchant_name.strip().lower()} "
    for category, keywords in _KEYWORDS.items():
        if any(keyword in normalized for keyword in keywords):
            return category
    return SpendCategory.OTHER
