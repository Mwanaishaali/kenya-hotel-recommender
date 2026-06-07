import { Search, ChevronDown } from 'lucide-react'
import { amenityIcon, amenityLabel } from '../amenities'

const RATING_OPTIONS = [
  { label: 'Any rating', value: 0 },
  { label: '3.5+', value: 3.5 },
  { label: '4.0+', value: 4.0 },
  { label: '4.5+', value: 4.5 },
]

export default function SearchPanel({
  cities, amenities, selCity, setSelCity,
  selAmenities, toggleAmenity, minRating, setMinRating,
  onSearch, loading,
}) {
  return (
    <section className="panel">
      <div className="panel__row">
        <label className="field">
          <span className="field__label">Destination</span>
          <div className="select-wrap">
            <select
              value={selCity}
              onChange={(e) => setSelCity(e.target.value)}
            >
              <option value="">Anywhere in Kenya</option>
              {cities.map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
            <ChevronDown size={16} className="select-wrap__icon" />
          </div>
        </label>

        <div className="field">
          <span className="field__label">Minimum rating</span>
          <div className="segmented">
            {RATING_OPTIONS.map((o) => (
              <button
                key={o.value}
                type="button"
                className={minRating === o.value ? 'seg seg--on' : 'seg'}
                onClick={() => setMinRating(o.value)}
              >
                {o.label}
              </button>
            ))}
          </div>
        </div>

        <button className="search-btn" onClick={onSearch} disabled={loading}>
          <Search size={18} />
          {loading ? 'Searching…' : 'Find stays'}
        </button>
      </div>

      <div className="field">
        <span className="field__label">Must-have amenities</span>
        <div className="chips">
          {amenities.map((a) => {
            const Icon = amenityIcon(a)
            const on = selAmenities.has(a)
            return (
              <button
                key={a}
                type="button"
                className={on ? 'chip chip--on' : 'chip'}
                onClick={() => toggleAmenity(a)}
              >
                <Icon size={15} />
                {amenityLabel(a)}
              </button>
            )
          })}
        </div>
      </div>
    </section>
  )
}
