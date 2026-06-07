"""
app.py
------
FastAPI backend for the Kenya hotel recommender.

It loads the cached dataset once at startup (via recommender.py) and exposes:

  GET  /                       - basic info
  GET  /health                 - liveness check + hotel count
  GET  /meta                   - available cities + amenity vocabulary (for UI dropdowns)
  POST /recommend              - ranked hotels for a set of preferences
  GET  /hotels                 - list hotels (optional ?city= and ?limit=)
  GET  /hotels/{id}            - one hotel's full detail
  GET  /hotels/{id}/similar    - "more like this"
  /photos/...                  - the cached hotel photos, served as static files

Run locally:
  uvicorn app:app --reload
Then open http://127.0.0.1:8000/docs for interactive API docs.
"""

from pathlib import Path
from typing import List, Optional
import os

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from recommender import HotelRecommender

DATA_PATH = "data/hotels.json"
PHOTO_DIR = Path("data/photos")

# Load the model once. This is cheap (a few hundred rows) and keeps every
# request fast since nothing is recomputed from scratch per call.
rec = HotelRecommender(DATA_PATH)

app = FastAPI(
    title="Kenya Hotel Recommender API",
    description="Content-based hotel recommendations for destinations across Kenya.",
    version="1.0.0",
)

# Allow the frontend to call this API. By default this is open ("*") so it
# works out of the box; in production set ALLOWED_ORIGINS to your frontend URL
# (comma-separated for several) to lock it down — no code change needed.
_origins = os.getenv("ALLOWED_ORIGINS", "*").strip()
allow_origins = ["https://kenya-hotel-recommender.vercel.app"] if _origins == "*" else [o.strip() for o in _origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve the cached photos. A stored photo path like "photos/<id>_0.jpg" becomes
# the URL "/photos/<id>_0.jpg". The frontend prepends the API base URL to these.
if PHOTO_DIR.exists():
    app.mount("/photos", StaticFiles(directory=str(PHOTO_DIR)), name="photos")


# --------------------------------------------------------------------------- #
# Response / request models
# --------------------------------------------------------------------------- #
class Review(BaseModel):
    author: Optional[str] = None
    rating: Optional[float] = None
    text: str = ""
    time: Optional[str] = None


class Location(BaseModel):
    latitude: float
    longitude: float


class Hotel(BaseModel):
    id: str
    name: str
    city: str
    address: Optional[str] = None
    rating: float
    review_count: int
    amenities: List[str] = []
    matched_amenities: List[str] = []
    photos: List[str] = []
    reviews: List[Review] = []
    website: Optional[str] = None
    editorial_summary: Optional[str] = None
    location: Optional[Location] = None
    score: Optional[float] = None        # set on /recommend results
    similarity: Optional[float] = None   # set on /similar results


class RecommendRequest(BaseModel):
    amenities: Optional[List[str]] = Field(
        default=None, description='Desired amenities, e.g. ["pool", "gym"]'
    )
    city: Optional[str] = Field(default=None, description="Restrict to one destination")
    min_rating: Optional[float] = Field(default=None, ge=0, le=5)
    top_n: int = Field(default=10, ge=1, le=50)


class Meta(BaseModel):
    cities: List[str]
    amenities: List[str]
    hotel_count: int


# --------------------------------------------------------------------------- #
# Helpers: build a Hotel from either a recommender result dict or a df row
# --------------------------------------------------------------------------- #
def _photo_urls(photos):
    return ["/" + p for p in (photos or [])]


def _clean(v):
    """pandas stores missing strings as NaN (a float); turn those into None."""
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        return v
    return v


def _location(loc):
    if (isinstance(loc, dict)
            and loc.get("latitude") is not None
            and loc.get("longitude") is not None):
        return Location(latitude=loc["latitude"], longitude=loc["longitude"])
    return None


def _dict_to_hotel(d) -> Hotel:
    """Adapt a recommend() result dict into a Hotel response."""
    return Hotel(
        id=d["id"],
        name=d["name"],
        city=d.get("city", "Unknown"),
        address=_clean(d.get("address")),
        rating=float(d.get("rating") or 0.0),
        review_count=int(d.get("review_count") or 0),
        amenities=d.get("amenities") or [],
        matched_amenities=d.get("matched_amenities") or [],
        photos=_photo_urls(d.get("photos")),
        reviews=[Review(**r) for r in (d.get("reviews") or [])],
        website=_clean(d.get("website")),
        editorial_summary=_clean(d.get("editorial_summary")),
        location=_location(d.get("location")),
        score=d.get("score"),
    )


def _row_to_hotel(row, similarity=None) -> Hotel:
    """Adapt a row of rec.df (a dict) into a Hotel response."""
    rating = row.get("rating")
    return Hotel(
        id=row["id"],
        name=row["name"],
        city=row.get("city", "Unknown"),
        address=_clean(row.get("address")),
        rating=float(rating) if pd.notna(rating) else 0.0,
        review_count=int(row.get("review_count") or 0),
        amenities=row.get("amenities") or [],
        photos=_photo_urls(row.get("photos")),
        reviews=[Review(**r) for r in (row.get("reviews") or [])],
        website=_clean(row.get("website")),
        editorial_summary=_clean(row.get("editorial_summary")),
        location=_location(row.get("location")),
        similarity=similarity,
    )


def _record_by_id(hotel_id):
    hits = rec.df.index[rec.df["id"] == hotel_id].tolist()
    if not hits:
        return None
    return rec.df.iloc[hits[0]].to_dict()


# --------------------------------------------------------------------------- #
# Endpoints
# --------------------------------------------------------------------------- #
@app.get("/")
def root():
    return {
        "name": "Kenya Hotel Recommender API",
        "docs": "/docs",
        "hotels": len(rec.df),
    }


@app.get("/health")
def health():
    return {"status": "ok", "hotels": len(rec.df)}


@app.get("/meta", response_model=Meta)
def meta():
    cities = sorted(c for c in rec.df["city"].unique() if c and c != "Unknown")
    return Meta(cities=cities, amenities=rec.vocab, hotel_count=len(rec.df))


@app.post("/recommend", response_model=List[Hotel])
def recommend(req: RecommendRequest):
    results = rec.recommend(
        amenities=req.amenities,
        city=req.city,
        min_rating=req.min_rating,
        top_n=req.top_n,
    )
    return [_dict_to_hotel(d) for d in results]


@app.get("/hotels", response_model=List[Hotel])
def list_hotels(
    city: Optional[str] = Query(default=None, description="Filter by city"),
    limit: int = Query(default=50, ge=1, le=240),
):
    df = rec.df
    if city:
        df = df[df["city"].str.lower() == city.lower()]
    return [_row_to_hotel(r) for r in df.head(limit).to_dict("records")]


@app.get("/hotels/{hotel_id}", response_model=Hotel)
def get_hotel(hotel_id: str):
    record = _record_by_id(hotel_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Hotel not found")
    return _row_to_hotel(record)


@app.get("/hotels/{hotel_id}/similar", response_model=List[Hotel])
def similar_hotels(hotel_id: str, top_n: int = Query(default=5, ge=1, le=20)):
    if _record_by_id(hotel_id) is None:
        raise HTTPException(status_code=404, detail="Hotel not found")
    out = []
    for s in rec.similar_to(hotel_id, top_n=top_n):
        record = _record_by_id(s["id"])
        if record:
            out.append(_row_to_hotel(record, similarity=s["similarity"]))
    return out
