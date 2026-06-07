"""
build_dataset.py
-----------------
Builds a cached dataset of Kenyan hotels using the Google Places API (New).

Run this ONCE. It produces:
  - data/hotels.json   (the dataset your recommender + API will use)
  - data/photos/*.jpg  (downloaded hotel photos, unless --no-photos)

After this runs, the rest of the app never needs to call Google again,
which keeps it fast, cheap, and easy to deploy.

Usage:
  python build_dataset.py                      # full pull with photos
  python build_dataset.py --no-photos          # skip photo downloads
  python build_dataset.py --max-per-query 40   # pull more hotels per city
"""

import os
import json
import time
import argparse
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"

# Kenyan destinations we want coverage across.
# Add/remove freely — each becomes one or more API searches.
QUERIES = [
    "hotels in Nairobi Kenya",
    "hotels in Mombasa Kenya",
    "hotels in Diani Beach Kenya",
    "hotels in Nakuru Kenya",
    "hotels in Kisumu Kenya",
    "hotels in Naivasha Kenya",
    "safari lodges Maasai Mara Kenya",
    "hotels in Eldoret Kenya",
    "hotels in Malindi Kenya",
    "resorts in Watamu Kenya",
    "hotels in Nanyuki Kenya",
    "lodges in Amboseli Kenya",
]

# Only request the fields we actually use — this controls API cost.
FIELD_MASK = ",".join([
    "places.id",
    "places.displayName",
    "places.formattedAddress",
    "places.location",
    "places.rating",
    "places.userRatingCount",
    "places.priceLevel",
    "places.types",
    "places.editorialSummary",
    "places.websiteUri",
    "places.photos",
    "places.reviews",
    "places.priceRange",
    "nextPageToken",
])

# Google returns price level as an enum string; map to a 0-4 integer.
PRICE_MAP = {
    "PRICE_LEVEL_FREE": 0,
    "PRICE_LEVEL_INEXPENSIVE": 1,
    "PRICE_LEVEL_MODERATE": 2,
    "PRICE_LEVEL_EXPENSIVE": 3,
    "PRICE_LEVEL_VERY_EXPENSIVE": 4,
}

# Amenity detection. The public Places API does not expose clean
# pool/gym booleans for lodging, so we infer amenities from the
# editorial summary + review text + place types. Good enough for a
# content-based recommender; can be enriched later.
AMENITY_KEYWORDS = {
    "pool": ["pool", "swimming"],
    "gym": ["gym", "fitness", "workout"],
    "spa": ["spa", "massage", "sauna", "jacuzzi"],
    "restaurant": ["restaurant", "dining", "buffet"],
    "bar": ["bar", "lounge", "cocktail"],
    "wifi": ["wifi", "wi-fi", "internet"],
    "parking": ["parking", "car park"],
    "airport_shuttle": ["shuttle", "airport transfer", "airport pickup"],
    "beach": ["beach", "beachfront", "ocean view"],
    "breakfast": ["breakfast"],
    "conference": ["conference", "meeting room", "business center", "boardroom"],
    "air_conditioning": ["air conditioning", "air-conditioned", "aircon", "a/c"],
}


def search_places(query, max_results, session):
    """Run a Text Search, paginating (20/page) up to max_results."""
    results = []
    page_token = None
    while len(results) < max_results:
        body = {"textQuery": query, "pageSize": 20}
        if page_token:
            body["pageToken"] = page_token
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": API_KEY,
            "X-Goog-FieldMask": FIELD_MASK,
        }
        resp = session.post(SEARCH_URL, headers=headers, json=body, timeout=30)
        if resp.status_code != 200:
            print(f"  ! HTTP {resp.status_code} for '{query}': {resp.text[:200]}")
            break
        data = resp.json()
        results.extend(data.get("places", []))
        page_token = data.get("nextPageToken")
        if not page_token:
            break
        time.sleep(2)  # next-page token needs a moment to activate
    return results[:max_results]


def infer_amenities(text_blob):
    blob = text_blob.lower()
    return [a for a, kws in AMENITY_KEYWORDS.items() if any(k in blob for k in kws)]


def download_photo(photo_name, dest_path, session, max_width=800):
    """Fetch one photo's media bytes and save to dest_path."""
    url = f"https://places.googleapis.com/v1/{photo_name}/media"
    params = {"maxWidthPx": max_width, "key": API_KEY}
    try:
        r = session.get(url, params=params, timeout=30)
    except requests.RequestException as e:
        print(f"    photo error: {e}")
        return False
    if r.status_code == 200 and r.content:
        dest_path.write_bytes(r.content)
        return True
    return False


def parse_place(place, photo_dir, session, photos_per_hotel):
    pid = place.get("id")
    name = place.get("displayName", {}).get("text", "Unknown")

    reviews = []
    for rv in place.get("reviews", [])[:5]:
        reviews.append({
            "author": rv.get("authorAttribution", {}).get("displayName"),
            "rating": rv.get("rating"),
            "text": rv.get("text", {}).get("text", ""),
            "time": rv.get("relativePublishTimeDescription"),
        })

    editorial = place.get("editorialSummary", {}).get("text", "")
    review_blob = " ".join(r["text"] for r in reviews)
    type_blob = " ".join(place.get("types", []))
    amenities = infer_amenities(f"{editorial} {review_blob} {type_blob}")

    # priceRange is a newer, separate field from priceLevel. Structure:
    # {"startPrice": {"currencyCode": "KES", "units": "5000"}, "endPrice": {...}}
    pr = place.get("priceRange")
    price_range = None
    if pr:
        def _money(m):
            if not m:
                return None
            units = m.get("units")
            return {"amount": int(units) if units is not None else None,
                    "currency": m.get("currencyCode")}
        price_range = {"start": _money(pr.get("startPrice")),
                       "end": _money(pr.get("endPrice"))}

    photo_paths = []
    if photo_dir is not None:
        for i, ph in enumerate(place.get("photos", [])[:photos_per_hotel]):
            dest = photo_dir / f"{pid}_{i}.jpg"
            if dest.exists() or download_photo(ph["name"], dest, session):
                photo_paths.append(f"photos/{dest.name}")

    return {
        "id": pid,
        "name": name,
        "address": place.get("formattedAddress"),
        "location": place.get("location"),       # {latitude, longitude}
        "rating": place.get("rating"),            # 0.0 - 5.0
        "review_count": place.get("userRatingCount", 0),
        "price_level": PRICE_MAP.get(place.get("priceLevel")),  # 0-4 or None
        "price_range": price_range,               # {start, end} or None
        "website": place.get("websiteUri"),
        "editorial_summary": editorial,
        "amenities": amenities,
        "reviews": reviews,
        "photos": photo_paths,
        "types": place.get("types", []),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-per-query", type=int, default=20,
                        help="Max hotels to pull per destination (20 = 1 page).")
    parser.add_argument("--photos-per-hotel", type=int, default=2)
    parser.add_argument("--no-photos", action="store_true",
                        help="Skip downloading photos (faster, cheaper).")
    parser.add_argument("--out", default="data/hotels.json")
    args = parser.parse_args()

    if not API_KEY:
        raise SystemExit(
            "GOOGLE_MAPS_API_KEY not set.\n"
            "Copy .env.example to .env and paste your key, then re-run."
        )

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    photo_dir = None if args.no_photos else out_path.parent / "photos"
    if photo_dir:
        photo_dir.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    hotels = {}
    for q in QUERIES:
        print(f"Searching: {q}")
        places = search_places(q, args.max_per_query, session)
        print(f"  found {len(places)}")
        for p in places:
            pid = p.get("id")
            if pid and pid not in hotels:
                hotels[pid] = parse_place(p, photo_dir, session, args.photos_per_hotel)

    records = list(hotels.values())
    out_path.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nSaved {len(records)} unique hotels -> {out_path}")
    if photo_dir:
        print(f"Photos saved -> {photo_dir} "
              f"({len(list(photo_dir.glob('*.jpg')))} files)")

    # Price-data coverage: the whole point of this re-run.
    with_range = sum(1 for r in records if r.get("price_range"))
    with_level = sum(1 for r in records if r.get("price_level") is not None)
    print(f"\nPrice coverage:")
    print(f"  price_range present: {with_range}/{len(records)}")
    print(f"  price_level present: {with_level}/{len(records)}")


if __name__ == "__main__":
    main()
