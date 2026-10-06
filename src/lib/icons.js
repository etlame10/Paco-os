// Iconos disponibles para los módulos personalizados (se guardan por nombre).
import {
  Archive, Bike, Book, BookOpen, Bot, Briefcase, Camera, Car, Code, Coffee, Cpu, Dumbbell, Film, Flag,
  Flame, Gamepad2, Gift, Globe, GraduationCap, Headphones, Heart, House, Inbox, KeyRound, Leaf,
  Lightbulb, MapPin, Monitor, Mountain, Music, Package, Palette, PawPrint, Plane, Puzzle, Repeat,
  Rocket, Shield, ShoppingCart, Sparkles, Star, StickyNote, Tag, Tv, Utensils, Wallet, Zap,
} from 'lucide-react'

export const ICONS = {
  Puzzle, Sparkles, Star, Heart, Book, BookOpen, GraduationCap, Briefcase, Code, Cpu, Monitor, Gamepad2,
  Film, Tv, Music, Headphones, Camera, Palette, ShoppingCart, Gift, Package, Wallet, Plane, MapPin,
  Mountain, Car, Bike, House, Utensils, Coffee, Dumbbell, Flame, Leaf, PawPrint, Lightbulb, Rocket,
  Zap, Bot, Globe, Shield, KeyRound, Flag, Tag, Inbox, Archive, StickyNote, Repeat,
}

export const getIcon = (name) => ICONS[name] || Puzzle

export const COLORS = [
  '#7c5cff', '#6366f1', '#3b82f6', '#06b6d4', '#14b8a6', '#22c55e', '#84cc16',
  '#eab308', '#f59e0b', '#f97316', '#ef4444', '#f43f5e', '#ec4899', '#a855f7', '#64748b',
]
