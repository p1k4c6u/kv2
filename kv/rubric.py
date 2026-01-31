# rubric.py

"""
Scoring rubric for LLM-based listing analysis.
Total weight: 100 points
"""

SCORING_RUBRIC = {
    "price_value": {
        "weight": 25,
        "criteria": (
            "Price per m2 value assessment. Lower price/m2 is generally better. "
            "Estonian market reference: Tallinn center ~3000-5000 EUR/m2, "
            "suburbs ~2000-3000 EUR/m2, other cities ~1000-2000 EUR/m2. "
            "Score higher if price seems below market rate for the area/condition."
        ),
    },
    "location": {
        "weight": 20,
        "criteria": (
            "Location quality inferred from title, address, and description. "
            "Consider: proximity to city center, public transport access, "
            "nearby amenities (schools, shops, parks), neighborhood reputation. "
            "Urban centers score higher than remote areas."
        ),
    },
    "condition": {
        "weight": 20,
        "criteria": (
            "Property condition based on renovation status, year built, and energy class. "
            "Recently renovated (2020+) scores high. Energy class A/B scores higher than C-G. "
            "New construction (2015+) preferred. Poor condition or 'needs renovation' scores low."
        ),
    },
    "size_layout": {
        "weight": 15,
        "criteria": (
            "Size and layout practicality. Good room-to-area ratio, "
            "adequate bedroom count for the size, functional layout. "
            "Studios/1-room apartments score lower unless very well-priced. "
            "3+ bedrooms with good total area scores higher."
        ),
    },
    "investment_potential": {
        "weight": 20,
        "criteria": (
            "Investment and rental potential. Consider: "
            "rental demand in the area, property type appeal to tenants, "
            "potential for value appreciation, versatility of the property. "
            "Central locations with good transport links score higher."
        ),
    },
}


def format_rubric_for_prompt() -> str:
    """Format the rubric as a string for the LLM prompt."""
    lines = []
    for category, details in SCORING_RUBRIC.items():
        name = category.replace("_", " ").title()
        lines.append(f"- {name} (0-{details['weight']} points): {details['criteria']}")
    return "\n".join(lines)


def get_total_weight() -> int:
    """Return the total possible score."""
    return sum(d["weight"] for d in SCORING_RUBRIC.values())
