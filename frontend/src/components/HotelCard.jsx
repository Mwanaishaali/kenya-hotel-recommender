import { useState } from 'react'
import { MapPin, MessageSquareQuote, Globe } from 'lucide-react'
import StarRating from './StarRating'
import { amenityIcon, amenityLabel } from '../amenities'
import { photoUrl } from '../api'

export default function HotelCard({ hotel, index = 0, onOpen }) {
  const [imgOk, setImgOk] = useState(true)
  const photo = hotel.photos && hotel.photos[0] ? photoUrl(hotel.photos[0]) : null
  const matched = new Set(hotel.matched_amenities || [])
  // Show matched amenities first, then the rest.
  const ordered = [...(hotel.amenities || [])].sort(
    (a, b) => (matched.has(b) ? 1 : 0) - (matched.has(a) ? 1 : 0),
  )
  const shown = ordered.slice(0, 5)
  const extra = (hotel.amenities || []).length - shown.length
  const review = (hotel.reviews || []).find((r) => r.text)

  return (
    <article
      className="card"
      style={{ animationDelay: `${Math.min(index, 11) * 60}ms` }}
      onClick={() => onOpen(hotel)}
    >
      <div className="card__media">
        {photo && imgOk ? (
          <img
            src={photo}
            alt={hotel.name}
            loading="lazy"
            onError={() => setImgOk(false)}
          />
        ) : (
          <div className="card__noimg">{hotel.name?.[0] || '?'}</div>
        )}
        <span className="card__city"><MapPin size={13} /> {hotel.city}</span>
      </div>

      <div className="card__body">
        <h3 className="card__name">{hotel.name}</h3>

        <div className="card__rating">
          <StarRating value={hotel.rating} />
          <strong>{hotel.rating?.toFixed(1)}</strong>
          <span className="muted">
            {hotel.review_count?.toLocaleString()} reviews
          </span>
        </div>

        <div className="card__amenities">
          {shown.map((a) => {
            const Icon = amenityIcon(a)
            return (
              <span
                key={a}
                className={matched.has(a) ? 'tag tag--match' : 'tag'}
              >
                <Icon size={13} /> {amenityLabel(a)}
              </span>
            )
          })}
          {extra > 0 && <span className="tag tag--more">+{extra}</span>}
        </div>

        {review && (
          <p className="card__review">
            <MessageSquareQuote size={14} />
            <span>“{review.text.slice(0, 120)}{review.text.length > 120 ? '…' : ''}”</span>
          </p>
        )}

        {hotel.website && (
          <a
            className="card__site"
            href={hotel.website}
            target="_blank"
            rel="noreferrer"
            onClick={(e) => e.stopPropagation()}
          >
            <Globe size={13} /> Visit website
          </a>
        )}
      </div>
    </article>
  )
}
