# analyze.py

"""
LLM-powered listing analysis using OpenRouter API (supports Claude and other models).
Fetches listings from the database, scores them using a fixed rubric,
and outputs ranked results.
"""

import os
import json
import time
import re
import psycopg
from openai import OpenAI

from rubric import SCORING_RUBRIC, format_rubric_for_prompt, get_total_weight
from db import save_analysis, get_analyzed_listing_ids

# API Configuration - OpenRouter
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
MODEL = os.environ.get(
    "OPENROUTER_MODEL", "anthropic/claude-sonnet-4"
)  # Can be changed via env
RATE_LIMIT_DELAY = 1.0  # seconds between API calls

# Database
DB_URL = os.environ.get("DATABASE_URL")

# Prompt template
SYSTEM_PROMPT = """You are an expert real estate analyst specializing in the Estonian property market.
Your task is to analyze property listings and score them based on investment potential and value.
Be objective and analytical. Base your assessment only on the information provided."""

USER_PROMPT_TEMPLATE = """Analyze this Estonian real estate listing and score it from 0-100.

SCORING RUBRIC (total {total_weight} points):
{rubric}

LISTING DETAILS:
- Title: {title}
- Price: {price_eur} EUR ({eur_per_m2} EUR/m2)
- Rooms: {rooms}
- Bedrooms: {bedrooms}
- Total Area: {total_area} m2
- Floors: {floors}
- Year Built: {year_built}
- Condition: {condition}
- Energy Class: {energy_class}
- Features: {additional_info}
- Description: {description}

Respond with ONLY valid JSON in this exact format (no markdown, no extra text):
{{"score": <0-100>, "breakdown": {{"price_value": <0-25>, "location": <0-20>, "condition": <0-20>, "size_layout": <0-15>, "investment_potential": <0-20>}}, "summary": "<2-3 sentence analysis>"}}"""


def fetch_listings_from_db() -> list[dict]:
    """Fetch all listings from the database."""
    if not DB_URL:
        raise RuntimeError("DATABASE_URL environment variable is not set.")

    query = """
    SELECT 
        listing_id, url, title, price_eur, eur_per_m2, rooms, bedrooms,
        total_area, floors, year_built, condition, ownership, plot_area,
        cadastral_nr, energy_class, additional_info, description
    FROM kv_listings
    WHERE is_owner_direct = true
    ORDER BY last_seen_at DESC
    """

    listings = []
    with psycopg.connect(DB_URL, connect_timeout=10) as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            columns = [desc[0] for desc in cur.description]
            for row in cur.fetchall():
                listings.append(dict(zip(columns, row)))

    return listings


def build_prompt(listing: dict) -> str:
    """Build the analysis prompt for a listing."""

    # Handle None values gracefully
    def safe_str(val):
        if val is None:
            return "Not specified"
        if isinstance(val, list):
            return ", ".join(str(v) for v in val) if val else "None"
        return str(val)

    return USER_PROMPT_TEMPLATE.format(
        total_weight=get_total_weight(),
        rubric=format_rubric_for_prompt(),
        title=safe_str(listing.get("title")),
        price_eur=safe_str(listing.get("price_eur")),
        eur_per_m2=safe_str(listing.get("eur_per_m2")),
        rooms=safe_str(listing.get("rooms")),
        bedrooms=safe_str(listing.get("bedrooms")),
        total_area=safe_str(listing.get("total_area")),
        floors=safe_str(listing.get("floors")),
        year_built=safe_str(listing.get("year_built")),
        condition=safe_str(listing.get("condition")),
        energy_class=safe_str(listing.get("energy_class")),
        additional_info=safe_str(listing.get("additional_info")),
        description=safe_str(listing.get("description"))[
            :1000
        ],  # Truncate long descriptions
    )


def parse_llm_response(response_text: str) -> dict | None:
    """Parse the JSON response from the LLM."""
    try:
        # Try direct JSON parse
        return json.loads(response_text)
    except json.JSONDecodeError:
        # Try to extract JSON from markdown code blocks
        json_match = re.search(
            r"```(?:json)?\s*(\{.*?\})\s*```", response_text, re.DOTALL
        )
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # Try to find raw JSON object
        json_match = re.search(r'\{[^{}]*"score"[^{}]*\}', response_text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass

    return None


def analyze_listing(client: OpenAI, listing: dict) -> dict:
    """Analyze a single listing using OpenRouter API."""
    prompt = build_prompt(listing)

    try:
        response = client.chat.completions.create(
            model=MODEL,
            max_tokens=500,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
        )

        response_text = response.choices[0].message.content
        parsed = parse_llm_response(response_text)

        if parsed and "score" in parsed:
            return {
                "listing_id": listing["listing_id"],
                "url": listing.get("url"),
                "title": listing.get("title"),
                "price_eur": listing.get("price_eur"),
                "eur_per_m2": listing.get("eur_per_m2"),
                "rooms": listing.get("rooms"),
                "total_area": listing.get("total_area"),
                "score": parsed["score"],
                "breakdown": parsed.get("breakdown", {}),
                "summary": parsed.get("summary", ""),
                "error": None,
            }
        else:
            return {
                "listing_id": listing["listing_id"],
                "url": listing.get("url"),
                "title": listing.get("title"),
                "score": 0,
                "breakdown": {},
                "summary": "",
                "error": f"Failed to parse response: {response_text[:200]}",
            }

    except Exception as e:
        return {
            "listing_id": listing["listing_id"],
            "url": listing.get("url"),
            "title": listing.get("title"),
            "score": 0,
            "breakdown": {},
            "summary": "",
            "error": str(e),
        }


def analyze_all(
    listings: list[dict], save_to_db: bool = True, skip_analyzed: bool = True
) -> list[dict]:
    """
    Analyze all listings with rate limiting.

    Args:
        listings: List of listing dicts to analyze
        save_to_db: Whether to save results to database
        skip_analyzed: Whether to skip already analyzed listings
    """
    if not OPENROUTER_API_KEY:
        raise RuntimeError(
            "OPENROUTER_API_KEY environment variable is not set. "
            "Please set it to your OpenRouter API key."
        )

    # Filter out already analyzed listings if requested
    if skip_analyzed:
        analyzed_ids = get_analyzed_listing_ids()
        original_count = len(listings)
        listings = [l for l in listings if l["listing_id"] not in analyzed_ids]
        skipped = original_count - len(listings)
        if skipped > 0:
            print(f"Skipping {skipped} already analyzed listings")

    if not listings:
        print("No new listings to analyze.")
        return []

    client = OpenAI(
        api_key=OPENROUTER_API_KEY,
        base_url=OPENROUTER_BASE_URL,
    )
    results = []
    total = len(listings)

    print(f"Analyzing {total} listings with {MODEL}...")

    for i, listing in enumerate(listings, 1):
        title = listing.get("title", "Unknown")[:50]
        print(f"  [{i}/{total}] {title}...")

        result = analyze_listing(client, listing)
        results.append(result)

        if result.get("error"):
            print(f"    Error: {result['error'][:100]}")
        else:
            print(f"    Score: {result['score']}/100")

            # Save to database
            if save_to_db and not result.get("error"):
                save_analysis(
                    listing_id=result["listing_id"],
                    score=result["score"],
                    breakdown=result.get("breakdown", {}),
                    summary=result.get("summary", ""),
                    model=MODEL,
                )

        # Rate limiting (skip delay on last item)
        if i < total:
            time.sleep(RATE_LIMIT_DELAY)

    return results


def print_results(results: list[dict], top_n: int = 10):
    """Print ranked results to console."""
    # Sort by score descending
    ranked = sorted(results, key=lambda x: x.get("score", 0), reverse=True)

    # Filter out errors for top results
    valid_results = [r for r in ranked if not r.get("error")]
    error_count = len(ranked) - len(valid_results)

    print("\n" + "=" * 60)
    print(f"  TOP {min(top_n, len(valid_results))} LISTINGS")
    print("=" * 60 + "\n")

    for i, result in enumerate(valid_results[:top_n], 1):
        score = result.get("score", 0)
        title = result.get("title", "Unknown")[:60]
        price = result.get("price_eur")
        eur_m2 = result.get("eur_per_m2")
        rooms = result.get("rooms", "?")
        area = result.get("total_area", "?")
        url = result.get("url", "")
        summary = result.get("summary", "")
        breakdown = result.get("breakdown", {})

        # Score bar visualization
        bar_len = int(score / 5)  # 20 chars max
        bar = "#" * bar_len + "-" * (20 - bar_len)

        print(f"{i}. [{score:3d}/100] [{bar}]")
        print(f"   {title}")

        if price:
            price_str = f"{price:,} EUR"
            if eur_m2:
                price_str += f" ({eur_m2} EUR/m2)"
            print(f"   Price: {price_str}")

        print(f"   Rooms: {rooms} | Area: {area} m2")

        if breakdown:
            bd = breakdown
            print(
                f"   Scores: Price:{bd.get('price_value', '?')}/25 | "
                f"Location:{bd.get('location', '?')}/20 | "
                f"Condition:{bd.get('condition', '?')}/20 | "
                f"Size:{bd.get('size_layout', '?')}/15 | "
                f"Investment:{bd.get('investment_potential', '?')}/20"
            )

        if summary:
            print(f"   Summary: {summary}")

        if url:
            print(f"   URL: {url}")

        print()

    # Summary stats
    if valid_results:
        scores = [r["score"] for r in valid_results]
        avg_score = sum(scores) / len(scores)
        print("-" * 60)
        print(f"Total analyzed: {len(valid_results)} | Errors: {error_count}")
        print(f"Average score: {avg_score:.1f}/100")
        print(f"Score range: {min(scores)}-{max(scores)}")
        print("-" * 60)


def save_results_to_file(results: list[dict], filepath: str):
    """Save results to a JSON file."""
    from datetime import datetime

    output = {
        "analyzed_at": datetime.now().isoformat(),
        "total_listings": len(results),
        "results": sorted(results, key=lambda x: x.get("score", 0), reverse=True),
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\nResults saved to: {filepath}")


# CLI entry point
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Analyze KV listings with AI")
    parser.add_argument("--output", "-o", help="Save results to JSON file")
    parser.add_argument("--top", "-n", type=int, default=10, help="Show top N results")
    args = parser.parse_args()

    listings = fetch_listings_from_db()
    print(f"Found {len(listings)} listings in database")

    if not listings:
        print("No listings to analyze.")
        exit(0)

    results = analyze_all(listings)
    print_results(results, top_n=args.top)

    if args.output:
        save_results_to_file(results, args.output)
