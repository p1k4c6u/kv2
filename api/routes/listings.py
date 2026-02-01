# routes/listings.py
"""
Listing routes - view and query listings.
"""

import sys
from pathlib import Path

# Add kv module to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "kv"))

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..auth import verify_token
from ..schemas import (
    ListingSummary,
    ListingDetail,
    ListingsResponse,
    StatsResponse,
)

router = APIRouter(prefix="/listings", tags=["listings"])


@router.get("", response_model=ListingsResponse)
async def get_listings(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    sort_by: str = Query("score", regex="^(score|price|date|eur_per_m2)$"),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
    min_score: int | None = Query(None, ge=0, le=100),
    max_price: int | None = Query(None, ge=0),
    min_rooms: int | None = Query(None, ge=1),
    only_analyzed: bool = Query(False),
    _: bool = Depends(verify_token),
):
    """
    Get paginated list of listings with optional filters.
    """
    from db import get_listings_with_analysis

    offset = (page - 1) * per_page

    listings = get_listings_with_analysis(
        limit=per_page,
        offset=offset,
        min_score=min_score,
        max_price=max_price,
        min_rooms=min_rooms,
        only_analyzed=only_analyzed,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    # Convert to summary format
    summaries = []
    for l in listings:
        summaries.append(
            ListingSummary(
                listing_id=l["listing_id"],
                url=l.get("url"),
                title=l.get("title"),
                price_eur=l.get("price_eur"),
                eur_per_m2=l.get("eur_per_m2"),
                rooms=l.get("rooms"),
                total_area=l.get("total_area"),
                last_seen_at=l.get("last_seen_at"),
                score=l.get("score"),
                summary=l.get("summary"),
            )
        )

    # Get total count (simplified - could be optimized with a separate count query)
    from db import get_stats

    stats = get_stats()
    total = (
        stats.get("total_listings", 0)
        if not only_analyzed
        else stats.get("analyzed_count", 0)
    )

    return ListingsResponse(
        listings=summaries,
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/stats", response_model=StatsResponse)
async def get_listing_stats(
    _: bool = Depends(verify_token),
):
    """
    Get dashboard statistics.
    """
    from db import get_stats

    stats = get_stats()

    return StatsResponse(
        total_listings=stats.get("total_listings") or 0,
        analyzed_count=stats.get("analyzed_count") or 0,
        avg_score=round(stats.get("avg_score") or 0, 1)
        if stats.get("avg_score")
        else None,
        min_score=stats.get("min_score"),
        max_score=stats.get("max_score"),
        avg_price=round(stats.get("avg_price") or 0)
        if stats.get("avg_price")
        else None,
        min_price=stats.get("min_price"),
        max_price=stats.get("max_price"),
    )


@router.get("/debug-owner")
async def debug_owner_status(
    _: bool = Depends(verify_token),
):
    """
    Temporary debug endpoint — shows is_owner_direct distribution
    and a sample of seller_info / raw text so we can see what kv.ee
    actually returns. DELETE THIS after the detection is confirmed working.
    """
    import psycopg
    import json
    from db import DB_URL

    with psycopg.connect(DB_URL, connect_timeout=10) as conn:
        with conn.cursor() as cur:
            # Counts by is_owner_direct value
            cur.execute("""
                SELECT
                    is_owner_direct,
                    COUNT(*) as cnt
                FROM kv_listings
                GROUP BY is_owner_direct
                ORDER BY is_owner_direct
            """)
            counts = [
                {"is_owner_direct": row[0], "count": row[1]} for row in cur.fetchall()
            ]

            # 5 sample rows: id, is_owner_direct, seller_info, first 500 chars of raw
            cur.execute("""
                SELECT listing_id, is_owner_direct, seller_info, raw
                FROM kv_listings
                ORDER BY last_seen_at DESC
                LIMIT 5
            """)
            samples = []
            for row in cur.fetchall():
                raw = row[3]
                if isinstance(raw, str):
                    raw = json.loads(raw)
                # Pull description from raw so we can search for owner-related text
                desc = (raw or {}).get("description", "") or ""
                samples.append(
                    {
                        "listing_id": row[0],
                        "is_owner_direct": row[1],
                        "seller_info": row[2],
                        "description_snippet": desc[:500],
                    }
                )

    return {"counts": counts, "samples": samples}


@router.get("/{listing_id}", response_model=ListingDetail)
async def get_listing(
    listing_id: str,
    _: bool = Depends(verify_token),
):
    """
    Get detailed information for a single listing.
    """
    from db import get_listing_by_id

    listing = get_listing_by_id(listing_id)

    if not listing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Listing {listing_id} not found",
        )

    return ListingDetail(
        listing_id=listing["listing_id"],
        url=listing.get("url"),
        title=listing.get("title"),
        price_eur=listing.get("price_eur"),
        eur_per_m2=listing.get("eur_per_m2"),
        rooms=listing.get("rooms"),
        bedrooms=listing.get("bedrooms"),
        total_area=listing.get("total_area"),
        floors=listing.get("floors"),
        year_built=listing.get("year_built"),
        condition=listing.get("condition"),
        energy_class=listing.get("energy_class"),
        description=listing.get("description"),
        last_seen_at=listing.get("last_seen_at"),
        score=listing.get("score"),
        breakdown=listing.get("breakdown"),
        summary=listing.get("summary"),
        model=listing.get("model"),
        analyzed_at=listing.get("analyzed_at"),
    )
