import {
  Waves, Dumbbell, Sparkles, Utensils, Wine, Wifi, Car, Plane,
  Sun, Coffee, Users, Snowflake, Check,
} from 'lucide-react'

const ICONS = {
  pool: Waves,
  gym: Dumbbell,
  spa: Sparkles,
  restaurant: Utensils,
  bar: Wine,
  wifi: Wifi,
  parking: Car,
  airport_shuttle: Plane,
  beach: Sun,
  breakfast: Coffee,
  conference: Users,
  air_conditioning: Snowflake,
}

const LABELS = {
  wifi: 'Wi-Fi',
  airport_shuttle: 'Airport shuttle',
  air_conditioning: 'Air conditioning',
}

export const amenityIcon = (name) => ICONS[name] || Check

export const amenityLabel = (name) =>
  LABELS[name] ||
  name.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
