# schemas.py
"""
Pydantic models for request/response validation.
"""

from pydantic import BaseModel
from datetime import datetime


# Auth schemas
class LoginRequest(BaseModel):
    password: str


class LoginResponse(BaseModel):
    token: str
    expires_in_days: int = 7


# Listing schemas
class AnalysisBreakdown(BaseModel):
    price_value: int | None = None
    location: int | None = None
    condition: int | None = None
    size_layout: int | None = None
    investment_potential: int | None = None


class ListingSummary(BaseModel):
    listing_id: str
    url: str | None
    title: str | None
    price_eur: int | None
    eur_per_m2: int | None
    rooms: str | None
    total_area: str | None
    last_seen_at: datetime | None

    # Analysis fields (optional, may be None if not analyzed)
    score: int | None = None
    summary: str | None = None

    class Config:
        from_attributes = True


class ListingDetail(BaseModel):
    listing_id: str
    url: str | None
    title: str | None
    price_eur: int | None
    eur_per_m2: int | None
    rooms: str | None
    bedrooms: str | None
    total_area: str | None
    floors: str | None
    year_built: str | None
    condition: str | None
    energy_class: str | None
    description: str | None
    last_seen_at: datetime | None

    # Analysis fields
    score: int | None = None
    breakdown: AnalysisBreakdown | dict | None = None
    summary: str | None = None
    model: str | None = None
    analyzed_at: datetime | None = None

    class Config:
        from_attributes = True


class ListingsResponse(BaseModel):
    listings: list[ListingSummary]
    total: int
    page: int
    per_page: int


class ListingsQueryParams(BaseModel):
    """Query parameters for listing filters."""

    page: int = 1
    per_page: int = 50
    sort_by: str = "score"  # score, price, date, eur_per_m2
    sort_order: str = "desc"  # asc, desc
    min_score: int | None = None
    max_price: int | None = None
    min_rooms: int | None = None
    only_analyzed: bool = False


# Stats schema
class StatsResponse(BaseModel):
    total_listings: int
    analyzed_count: int
    avg_score: float | None
    min_score: int | None
    max_score: int | None
    avg_price: float | None
    min_price: int | None
    max_price: int | None


# Scrape/Analyze schemas
class ScrapeRequest(BaseModel):
    area: str  # e.g., "tallinn", "tartu", "harjumaa"


class ScrapeResponse(BaseModel):
    status: str
    message: str
    listings_found: int = 0


class AnalyzeRequest(BaseModel):
    limit: int | None = None  # Limit number of listings to analyze


class AnalyzeResponse(BaseModel):
    status: str
    message: str
    analyzed_count: int = 0
    skipped_count: int = 0
