# Kenya Hotel Recommender

A content-based recommendation system for hotels across Kenya. Tell it where you
want to go and what you care about — a pool, a beach, a gym, a minimum rating —
and it ranks the best-matching hotels, each shown with its star rating, reviews,
photos, amenities, a location map, and a link to the hotel's website.


---

## Overview

The system covers **240 hotels across 12 Kenyan destinations** (Nairobi,
Mombasa, Diani, Nakuru, Kisumu, Naivasha, the Maasai Mara, Eldoret, Malindi,
Watamu, Nanyuki, and Amboseli). Hotel data — ratings, reviews, photos, and
amenities — is pulled once from the Google Places API and cached locally, so the
app runs fast and offline at request time.

It uses **content-based filtering**: rather than learning from user behaviour
(which would need a history of bookings we don't have), it matches each hotel's
own attributes to what the user asks for. That means it works from day one with
no user history.

## Features

- **Preference-based search** — filter by destination, minimum rating, and any
  combination of amenities.
- **Transparent ranking** — results are scored on how well their amenities match
  the request, blended with the hotel's rating and popularity.
- **"Similar stays"** — every hotel links to others like it, via item-to-item
  similarity.
- **Rich detail view** — photo gallery, guest reviews, an OpenStreetMap location
  pin, full amenity list, and a website link.
- **Documented end to end** — a CRISP-DM notebook covers the data exploration,
  modelling, and evaluation.

## How it works

```
Google Places API ──> build_dataset.py ──> data/hotels.json + data/photos/
                                                   │
                                                   ▼
                                            recommender.py        (the model)
                                                   │
                                                   ▼
                                               app.py             (FastAPI)
                                                   │
                                                   ▼
                                            frontend/ (React)     (the UI)
```

**The recommender.** Each hotel is turned into a feature vector: a multi-hot
encoding of its amenities, plus a normalised rating and a log-scaled popularity
(review count). A search produces a score for every hotel:

```
score = 0.50 · amenity_match   (cosine similarity to the requested amenities)
      + 0.35 · rating          (normalised 0–1)
      + 0.15 · popularity       (normalised log review count)
```

Cosine similarity does the content matching; rating and popularity are added as
quality boosts. Hard constraints (city, minimum rating) are applied as filters
before scoring. A separate item-to-item mode powers "similar stays" using cosine
similarity over the full feature vectors.

## Tech stack

| Layer      | Tools                                                    |
|------------|----------------------------------------------------------|
| Data       | Google Places API (New), pandas, NumPy                   |
| Model      | Content-based filtering, cosine similarity               |
| Backend    | FastAPI, Uvicorn                                          |
| Frontend   | React, Vite, lucide-react                                |
| Maps       | OpenStreetMap (embedded, no API key)                     |
| Hosting    | Render (backend), Vercel (frontend)                      |

## Project structure

```
kenya-hotel-recommender/
├── build_dataset.py        # one-time data pull from Google Places
├── recommender.py          # the content-based recommender
├── app.py                  # FastAPI backend
├── requirements.txt
├── .env.example
├── data/
│   ├── hotels.json         # cached dataset
│   └── photos/             # cached hotel photos
├── kenya_hotel_recommender.ipynb   # CRISP-DM walkthrough
│
└── frontend/               # React + Vite app
    ├── package.json
    ├── index.html
    └── src/
```

## Methodology

The project follows the **CRISP-DM** process — business understanding, data
understanding, data preparation, modelling, evaluation, and deployment. The full
walkthrough, with the exploratory analysis and evaluation, is in
[`kenya_hotel_recommender.ipynb`](kenya_hotel_recommender.ipynb).

Because there's no record of which hotels users actually booked, there's no
ground truth for precision/recall. Evaluation instead uses offline proxies —
catalogue coverage and intra-list diversity — alongside qualitative checks.

## Notes on the data

A couple of honest data decisions worth flagging:

- **Price was dropped.** Google's Places API returned usable price data for
  almost no Kenyan hotels (0 of 240 for `price_range`, 7 of 240 for
  `price_level`), so a price filter would mislead more than help. In production
  the fix would be a live pricing API (e.g. Amadeus Hotel Offers) keyed by
  check-in/out dates.
- **City detection is two-pass.** The city is first read from the hotel's
  address text; for addresses with no recognisable city, it falls back to the
  nearest known destination by coordinates. This cut "unknown" cities from 30 to 1.

## Running locally

You'll need Python 3.10+, Node.js 18+, and a Google Maps Platform API key with
the **Places API (New)** enabled.

### 1. Backend

```bash
# from the project root
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt

cp .env.example .env               # then add your key:
# GOOGLE_MAPS_API_KEY=your_key_here

python build_dataset.py            # one-time: builds data/hotels.json + photos
uvicorn app:app --reload           # serves http://127.0.0.1:8000
```

Visit `http://127.0.0.1:8000/docs` for the interactive API docs.

### 2. Frontend

```bash
cd frontend
npm install
cp .env.example .env               # set VITE_API_BASE_URL=http://127.0.0.1:8000
npm run dev                        # serves http://localhost:5173
```

Keep both servers running — the frontend pulls all its data and photos from the
backend.

## API reference

| Method | Endpoint                     | Description                              |
|--------|------------------------------|------------------------------------------|
| GET    | `/health`                    | Liveness check + hotel count             |
| GET    | `/meta`                      | Available cities and amenities (for UI)  |
| POST   | `/recommend`                 | Ranked hotels for a set of preferences   |
| GET    | `/hotels`                    | List hotels (optional `?city=`, `?limit=`) |
| GET    | `/hotels/{id}`               | One hotel's full detail                  |
| GET    | `/hotels/{id}/similar`       | "More like this"                         |
| GET    | `/photos/...`                | Cached hotel photos (static)             |

Example `/recommend` request body:

```json
{ "amenities": ["pool", "beach"], "city": "Diani", "min_rating": 4.0, "top_n": 5 }
```

## Deployment

- **Backend** → Render Web Service.
  Build: `pip install -r requirements.txt` · Start:
  `uvicorn app:app --host 0.0.0.0 --port $PORT`.
  Set `ALLOWED_ORIGINS` to the frontend URL to lock down CORS.
- **Frontend** → Vercel. Root directory `frontend`, framework Vite, with
  `VITE_API_BASE_URL` set to the backend URL.

## Possible improvements

- Log clicks/bookings once live, then evaluate with precision@k.
- Add real pricing via a hotel-offers API.
- A hybrid recommender once interaction data exists.
- Free-text search and result sorting.

## Data source

Hotel data is from the [Google Places API](https://developers.google.com/maps/documentation/places/web-service/op-overview).
Maps are rendered with [OpenStreetMap](https://www.openstreetmap.org/).
