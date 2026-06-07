// Single place that knows how to talk to the FastAPI backend.
// Override the base URL by creating a .env file (see .env.example).

export const API_BASE =
  import.meta.env.VITE_API_BASE_URL || "https://kenya-hotel-recommender.onrender.com"

// Backend returns photo paths like "/photos/abc_0.jpg"; turn them absolute.
export const photoUrl = (p) => (p ? `${API_BASE}${p}` : null)

async function jsonFetch(path, options) {
  const res = await fetch(`${API_BASE}${path}`, options)
  if (!res.ok) {
    throw new Error(`Request failed (${res.status})`)
  }
  return res.json()
}

export const getMeta = () => jsonFetch('/meta')

export const recommend = (body) =>
  jsonFetch('/recommend', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })

export const getSimilar = (id, topN = 6) =>
  jsonFetch(`/hotels/${encodeURIComponent(id)}/similar?top_n=${topN}`)
