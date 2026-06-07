import { useEffect, useState } from 'react'
import { X, MapPin, ExternalLink, Globe } from 'lucide-react'
import StarRating from './StarRating'
import { amenityIcon, amenityLabel } from '../amenities'
import { photoUrl, getSimilar } from '../api'

export default function HotelModal({ hotel, onClose, onOpen }) {
  const [similar, setSimilar] = useState([])
  const [loadingSim, setLoadingSim] = useState(true)
  const [activePhoto, setActivePhoto] = useState(0)

  useEffect(() => {
    setActivePhoto(0)
    let alive = true
    setLoadingSim(true)
    getSimilar(hotel.id, 6)
      .then((d) => alive && setSimilar(d))
      .catch(() => alive && setSimilar([]))
      .finally(() => alive && setLoadingSim(false))
    return () => { alive = false }
  }, [hotel.id])

  useEffect(() => {
    const onKey = (e) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const photos = (hotel.photos || []).map(photoUrl)
  const reviews = (hotel.reviews || []).filter((r) => r.text).slice(0, 4)
  const loc = hotel.location
  const mapSrc = loc
    ? `https://www.openstreetmap.org/export/embed.html?bbox=${loc.longitude - 0.02}%2C${loc.latitude - 0.02}%2C${loc.longitude + 0.02}%2C${loc.latitude + 0.02}&layer=mapnik&marker=${loc.latitude}%2C${loc.longitude}`
    : null

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <button className="modal__close" onClick={onClose} aria-label="Close">
          <X size={20} />
        </button>

        <div className="modal__hero">
          {photos[activePhoto]
            ? <img src={photos[activePhoto]} alt={hotel.name} />
            : <div className="modal__noimg">{hotel.name?.[0]}</div>}
        </div>

        {photos.length > 1 && (
          <div className="gallery">
            {photos.map((p, i) => (
              <button
                key={i}
                className={i === activePhoto ? 'gallery__thumb gallery__thumb--on' : 'gallery__thumb'}
                onClick={() => setActivePhoto(i)}
                aria-label={`View photo ${i + 1}`}
              >
                <img src={p} alt={`${hotel.name} ${i + 1}`} loading="lazy" />
              </button>
            ))}
          </div>
        )}

        <div className="modal__content">
          <h2 className="modal__name">{hotel.name}</h2>
          <div className="modal__meta">
            <span className="modal__city"><MapPin size={15} /> {hotel.city}</span>
            <span className="modal__rate">
              <StarRating value={hotel.rating} />
              <strong>{hotel.rating?.toFixed(1)}</strong>
              <span className="muted">({hotel.review_count?.toLocaleString()})</span>
            </span>
          </div>

          {hotel.address && <p className="modal__address">{hotel.address}</p>}
          {hotel.editorial_summary && <p className="modal__summary">{hotel.editorial_summary}</p>}

          <div className="modal__amenities">
            {(hotel.amenities || []).map((a) => {
              const Icon = amenityIcon(a)
              return <span key={a} className="tag"><Icon size={13} /> {amenityLabel(a)}</span>
            })}
          </div>

          {hotel.website && (
            <a className="modal__link" href={hotel.website} target="_blank" rel="noreferrer">
              <Globe size={15} /> Visit website <ExternalLink size={13} />
            </a>
          )}

          {mapSrc && (
            <div className="modal__section">
              <h4>Where it is</h4>
              <div className="map">
                <iframe title={`Map of ${hotel.name}`} src={mapSrc} loading="lazy" />
              </div>
              <a
                className="map__link"
                href={`https://www.openstreetmap.org/?mlat=${loc.latitude}&mlon=${loc.longitude}#map=15/${loc.latitude}/${loc.longitude}`}
                target="_blank"
                rel="noreferrer"
              >
                View larger map <ExternalLink size={12} />
              </a>
            </div>
          )}

          {reviews.length > 0 && (
            <div className="modal__section">
              <h4>What guests say</h4>
              {reviews.map((r, i) => (
                <blockquote key={i} className="quote">
                  <p>“{r.text}”</p>
                  <cite>{r.author || 'Guest'} · {r.time || ''}</cite>
                </blockquote>
              ))}
            </div>
          )}

          <div className="modal__section">
            <h4>Similar stays</h4>
            {loadingSim ? (
              <p className="muted">Finding similar places…</p>
            ) : similar.length === 0 ? (
              <p className="muted">No close matches found.</p>
            ) : (
              <div className="similar">
                {similar.map((s) => {
                  const sp = s.photos && s.photos[0] ? photoUrl(s.photos[0]) : null
                  return (
                    <button key={s.id} className="similar__item" onClick={() => onOpen(s)}>
                      <div className="similar__media">
                        {sp ? <img src={sp} alt={s.name} loading="lazy" />
                            : <div className="similar__noimg">{s.name?.[0]}</div>}
                      </div>
                      <div className="similar__info">
                        <span className="similar__name">{s.name}</span>
                        <span className="muted">{s.city} · {s.rating?.toFixed(1)}★</span>
                      </div>
                    </button>
                  )
                })}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
