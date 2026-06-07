import { Star } from 'lucide-react'

export default function StarRating({ value = 0, size = 15 }) {
  const rounded = Math.round(value)
  return (
    <span className="stars" title={`${value} out of 5`}>
      {[1, 2, 3, 4, 5].map((i) => (
        <Star
          key={i}
          size={size}
          strokeWidth={2}
          className={i <= rounded ? 'star star--on' : 'star'}
        />
      ))}
    </span>
  )
}
