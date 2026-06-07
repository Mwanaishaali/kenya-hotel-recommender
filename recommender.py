"""
recommender.py
--------------
Content-based hotel recommender built on the cached dataset (data/hotels.json).

Two capabilities:
  1. recommend(...)  -> rank hotels by how well they match a user's preferences
                        (amenities, city, price ceiling, minimum rating).
  2. similar_to(id)  -> "hotels like this one" via cosine similarity over the
                        full feature vectors.

The matching score blends three signals:
  - amenity_match : cosine similarity between the amenities you asked for and
                    each hotel's amenities (the core content-based signal)
  - rating        : the hotel's star rating, normalised to 0-1
  - popularity    : log of review count, normalised to 0-1 (a tie-breaker so a
                    4.5 with 3,000 reviews outranks a 4.5 with 4 reviews)

Why a blended score instead of one big cosine? Because "rating" isn't something
you want to be *similar* to — higher is simply better. Cosine is the right tool
for the amenity overlap; rating and popularity are better added as quality boosts.
"""

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

# City names we expect from Google's formatted addresses. Used to tag each
# hotel with a city so users can filter by destination.
KNOWN_CITIES = [
    "Nairobi", "Mombasa", "Diani", "Nakuru", "Kisumu", "Naivasha",
    "Maasai Mara", "Masai Mara", "Eldoret", "Malindi", "Watamu",
    "Nanyuki", "Amboseli",
]

DEFAULT_WEIGHTS = {"amenity": 0.5, "rating": 0.35, "popularity": 0.15}

# Approximate centroids (lat, lng) for the coordinate-based city fallback.
# Used when a hotel's address text doesn't contain a recognisable city name.
CITY_COORDS = {
    "Nairobi": (-1.286, 36.817),
    "Mombasa": (-4.043, 39.668),
    "Diani": (-4.279, 39.591),
    "Nakuru": (-0.303, 36.080),
    "Kisumu": (-0.092, 34.768),
    "Naivasha": (-0.717, 36.431),
    "Maasai Mara": (-1.406, 35.143),
    "Eldoret": (0.514, 35.270),
    "Malindi": (-3.219, 40.117),
    "Watamu": (-3.356, 40.026),
    "Nanyuki": (0.012, 37.073),
    "Amboseli": (-2.652, 37.260),
}


def _detect_city(address):
    """Tag a hotel with a city by scanning its address."""
    if not isinstance(address, str):
        return "Unknown"
    low = address.lower()
    for c in KNOWN_CITIES:
        if c.lower() in low:
            # normalise the two Mara spellings to one label
            return "Maasai Mara" if "mara" in c.lower() else c
    return "Unknown"


def _haversine_km(lat1, lon1, lat2, lon2):
    """Great-circle distance between two lat/lng points, in km."""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def _nearest_city(location, max_km=75.0):
    """Assign a hotel to the nearest known city by coordinates.

    Returns 'Unknown' if there are no usable coordinates, or if the nearest
    city is farther than max_km (so a hotel in a town we don't track isn't
    wrongly forced into one of our destinations).
    """
    if not isinstance(location, dict):
        return "Unknown"
    lat, lng = location.get("latitude"), location.get("longitude")
    if lat is None or lng is None:
        return "Unknown"
    best, best_d = "Unknown", float("inf")
    for city, (clat, clng) in CITY_COORDS.items():
        d = _haversine_km(lat, lng, clat, clng)
        if d < best_d:
            best, best_d = city, d
    return best if best_d <= max_km else "Unknown"


def _cosine(a, B):
    """Cosine similarity between vector a (d,) and each row of matrix B (n, d)."""
    a_norm = np.linalg.norm(a)
    b_norms = np.linalg.norm(B, axis=1)
    denom = a_norm * b_norms
    out = np.zeros(B.shape[0])
    nonzero = denom > 0
    out[nonzero] = (B[nonzero] @ a) / denom[nonzero]
    return out


class HotelRecommender:
    def __init__(self, data_path="data/hotels.json"):
        raw = json.loads(Path(data_path).read_text(encoding="utf-8"))
        self.df = pd.DataFrame(raw)
        self._prepare()

    def _prepare(self):
        df = self.df

        # --- clean / coerce fields ---
        df["city"] = df["address"].apply(_detect_city)
        # For hotels whose address text had no recognisable city, fall back to
        # the nearest known city using their coordinates.
        unknown = df["city"] == "Unknown"
        df.loc[unknown, "city"] = df.loc[unknown, "location"].apply(_nearest_city)
        df["rating"] = pd.to_numeric(df.get("rating"), errors="coerce").fillna(0.0)
        df["review_count"] = (
            pd.to_numeric(df.get("review_count"), errors="coerce").fillna(0).astype(int)
        )
        df["amenities"] = df["amenities"].apply(
            lambda a: a if isinstance(a, list) else []
        )

        # --- amenity vocabulary, learned from the data ---
        self.vocab = sorted({a for lst in df["amenities"] for a in lst})
        self.amenity_matrix = np.array(
            [[1.0 if a in set(lst) else 0.0 for a in self.vocab]
             for lst in df["amenities"]]
        )

        # --- normalised quality signals (all 0-1) ---
        self.rating_norm = (df["rating"] / 5.0).to_numpy()

        log_reviews = np.log1p(df["review_count"].to_numpy().astype(float))
        self.pop_norm = (
            log_reviews / log_reviews.max() if log_reviews.max() > 0 else log_reviews
        )

        # --- full feature matrix for item-to-item similarity ---
        # Price is intentionally excluded: Google supplies usable price data for
        # almost no Kenyan hotels, so including it would just add near-constant
        # noise. The model ranks on amenities, rating and popularity.
        self.feature_matrix = np.hstack([
            self.amenity_matrix,
            self.rating_norm.reshape(-1, 1),
            self.pop_norm.reshape(-1, 1),
        ])

    # ------------------------------------------------------------------ #
    def recommend(self, amenities=None, city=None,
                  min_rating=None, top_n=10, weights=None):
        """Rank hotels against a set of user preferences.

        amenities : list of desired amenities, e.g. ["pool", "gym"]
        city      : restrict to one destination, e.g. "Diani"
        min_rating: keep hotels with rating >= this value
        top_n     : how many to return

        Note: price is deliberately not a filter. Google's Places API returns
        usable price data for almost no Kenyan hotels (0/240 price_range,
        7/240 price_level), so a price filter would mislead more than help.
        """
        df = self.df
        n = len(df)
        mask = np.ones(n, dtype=bool)

        if city:
            mask &= (df["city"].str.lower() == city.lower()).to_numpy()
        if min_rating is not None:
            mask &= (df["rating"] >= min_rating).to_numpy()

        kept = np.where(mask)[0]
        if len(kept) == 0:
            return []

        requested = [a for a in (amenities or []) if a in self.vocab]
        w = dict(weights or DEFAULT_WEIGHTS)

        if requested:
            query_vec = np.array(
                [1.0 if a in set(requested) else 0.0 for a in self.vocab]
            )
            amenity_score = _cosine(query_vec, self.amenity_matrix)
        else:
            # no amenities asked for -> rank purely on quality
            amenity_score = np.zeros(n)
            total = w["rating"] + w["popularity"]
            w = {"amenity": 0.0,
                 "rating": w["rating"] / total,
                 "popularity": w["popularity"] / total}

        score = (w["amenity"] * amenity_score
                 + w["rating"] * self.rating_norm
                 + w["popularity"] * self.pop_norm)

        order = kept[np.argsort(-score[kept])][:top_n]

        results = []
        for i in order:
            row = df.iloc[i]
            matched = [a for a in requested if a in set(row["amenities"])]
            results.append({
                "id": row["id"],
                "name": row["name"],
                "city": row["city"],
                "address": row["address"],
                "rating": float(row["rating"]),
                "review_count": int(row["review_count"]),
                "amenities": row["amenities"],
                "matched_amenities": matched,
                "photos": row.get("photos", []) if "photos" in row else [],
                "reviews": row.get("reviews", []) if "reviews" in row else [],
                "website": row.get("website"),
                "editorial_summary": row.get("editorial_summary"),
                "location": row.get("location"),
                "score": round(float(score[i]), 4),
            })
        return results

    # ------------------------------------------------------------------ #
    def similar_to(self, hotel_id, top_n=5):
        """Return hotels most similar to a given hotel (cosine over all features)."""
        df = self.df
        locs = df.index[df["id"] == hotel_id].tolist()
        if not locs:
            return []
        i = locs[0]
        sims = _cosine(self.feature_matrix[i], self.feature_matrix)
        sims[i] = -1.0  # exclude the hotel itself
        order = np.argsort(-sims)[:top_n]
        return [{
            "id": df.iloc[j]["id"],
            "name": df.iloc[j]["name"],
            "city": df.iloc[j]["city"],
            "rating": float(df.iloc[j]["rating"]),
            "similarity": round(float(sims[j]), 4),
        } for j in order]


if __name__ == "__main__":
    rec = HotelRecommender()
    print(f"Loaded {len(rec.df)} hotels")
    print(f"Cities found: {sorted(rec.df['city'].unique())}")
    print(f"Amenity vocabulary: {rec.vocab}\n")

    print("== Beachfront hotels with a pool in Diani, rating >= 4.0 ==")
    for r in rec.recommend(amenities=["pool", "beach"], city="Diani",
                           min_rating=4.0, top_n=5):
        print(f"  [{r['rating']}*]  {r['name']}  "
              f"matched={r['matched_amenities']}  score={r['score']}")

    print("\n== Top-rated hotels overall (no preferences) ==")
    for r in rec.recommend(top_n=5):
        print(f"  [{r['rating']}*]  {r['name']} ({r['city']})  "
              f"{r['review_count']} reviews")
