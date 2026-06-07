import { useEffect, useState, useCallback } from 'react'
import { getMeta, recommend } from './api'
import SearchPanel from './components/SearchPanel'
import HotelCard from './components/HotelCard'
import HotelModal from './components/HotelModal'

export default function App() {
  const [cities, setCities] = useState([])
  const [amenities, setAmenities] = useState([])

  const [selCity, setSelCity] = useState('')
  const [selAmenities, setSelAmenities] = useState(new Set())
  const [minRating, setMinRating] = useState(0)

  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [active, setActive] = useState(null) // hotel open in modal

  const toggleAmenity = (a) =>
    setSelAmenities((prev) => {
      const next = new Set(prev)
      next.has(a) ? next.delete(a) : next.add(a)
      return next
    })

  const runSearch = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const body = {
        amenities: selAmenities.size ? [...selAmenities] : null,
        city: selCity || null,
        min_rating: minRating || null,
        top_n: 12,
      }
      const data = await recommend(body)
      setResults(data)
    } catch (e) {
      setError(
        'Could not reach the API. Make sure the backend is running ' +
          '(uvicorn app:app --reload).',
      )
      setResults([])
    } finally {
      setLoading(false)
    }
  }, [selAmenities, selCity, minRating])

  // Load metadata + an initial set of top stays on first render.
  useEffect(() => {
    let alive = true
    getMeta()
      .then((m) => {
        if (!alive) return
        setCities(m.cities || [])
        setAmenities(m.amenities || [])
      })
      .catch(() =>
        setError(
          'Could not reach the API. Make sure the backend is running ' +
            '(uvicorn app:app --reload).',
        ),
      )
    // initial results
    recommend({ top_n: 12 })
      .then((d) => alive && setResults(d))
      .catch(() => {})
    return () => { alive = false }
  }, [])

  const activeFilters = [
    selCity && selCity,
    minRating ? `${minRating}+ rating` : null,
    ...[...selAmenities],
  ].filter(Boolean)

  return (
    <div className="app">
      <header className="hero">
        <div className="hero__inner">
          <span className="hero__kicker">Karibu — welcome</span>
          <h1 className="hero__title">
            Find your place<br /><em>in Kenya</em>
          </h1>
          <p className="hero__sub">
            From the reefs of Diani to the plains of the Mara — hotels matched to
            what you care about, ranked by what other travellers loved.
          </p>
        </div>
        <div className="hero__glow" aria-hidden="true" />
      </header>

      <main className="container">
        <SearchPanel
          cities={cities}
          amenities={amenities}
          selCity={selCity}
          setSelCity={setSelCity}
          selAmenities={selAmenities}
          toggleAmenity={toggleAmenity}
          minRating={minRating}
          setMinRating={setMinRating}
          onSearch={runSearch}
          loading={loading}
        />

        <div className="results-head">
          <h2>
            {results.length
              ? `${results.length} stays for you`
              : loading ? 'Searching…' : 'No stays found'}
          </h2>
          {activeFilters.length > 0 && (
            <p className="results-head__filters">
              {activeFilters.join(' · ')}
            </p>
          )}
        </div>

        {error && <div className="error">{error}</div>}

        <div className="grid">
          {results.map((h, i) => (
            <HotelCard key={h.id} hotel={h} index={i} onOpen={setActive} />
          ))}
        </div>
      </main>

      <footer className="foot">
        <span>Built on Google Places data · content-based recommender</span>
      </footer>

      {active && (
        <HotelModal
          hotel={active}
          onClose={() => setActive(null)}
          onOpen={setActive}
        />
      )}
    </div>
  )
}
