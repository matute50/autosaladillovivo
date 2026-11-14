/**
 * Zustand stores para el panel de Fábrica de Videos
 * Cada store es independiente y no toca los stores existentes del proyecto
 */

import { create } from 'zustand'
import type {
  VideoPresenter,
  InsertVideoPresenter,
  UpdateVideoPresenter,
  VideoLocation,
  InsertVideoLocation,
  UpdateVideoLocation,
  VideoWeatherRule,
  InsertVideoWeatherRule,
  UpdateVideoWeatherRule,
  VideoFactorySettings,
  UpdateVideoFactorySettings,
} from '@/lib/types/video-factory'

// ============================================================
// Factory Settings Store
// ============================================================
interface FactorySettingsState {
  settings: VideoFactorySettings | null
  loading: boolean
  fetchSettings: () => Promise<void>
  updateSettings: (updates: UpdateVideoFactorySettings) => Promise<void>
}

export const useFactorySettingsStore = create<FactorySettingsState>((set) => ({
  settings: null,
  loading: false,
  fetchSettings: async () => {
    set({ loading: true })
    try {
      const res = await fetch('/api/factory/settings')
      if (!res.ok) throw new Error('Failed to fetch settings')
      const data = await res.json()
      set({ settings: data[0] ?? null, loading: false })
    } catch (e) {
      set({ loading: false })
    }
  },
  updateSettings: async (updates) => {
    const res = await fetch('/api/factory/settings', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(updates),
    })
    if (!res.ok) throw new Error('Failed to update settings')
    const data = await res.json()
    set({ settings: data })
  },
}))

// ============================================================
// Presenters Store
// ============================================================
interface PresentersState {
  presenters: VideoPresenter[]
  loading: boolean
  fetchPresenters: () => Promise<void>
  addPresenter: (data: InsertVideoPresenter) => Promise<VideoPresenter>
  updatePresenter: (id: string, data: UpdateVideoPresenter) => Promise<void>
  deletePresenter: (id: string) => Promise<void>
}

export const usePresentersStore = create<PresentersState>((set, get) => ({
  presenters: [],
  loading: false,
  fetchPresenters: async () => {
    set({ loading: true })
    try {
      const res = await fetch('/api/presenters')
      if (!res.ok) throw new Error('Failed to fetch presenters')
      const data = await res.json()
      set({ presenters: data, loading: false })
    } catch (e) {
      set({ loading: false })
    }
  },
  addPresenter: async (data) => {
    const res = await fetch('/api/presenters', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    })
    if (!res.ok) throw new Error('Failed to add presenter')
    const item = await res.json()
    set((state) => ({ presenters: [...state.presenters, item] }))
    return item
  },
  updatePresenter: async (id, data) => {
    const res = await fetch(`/api/presenters/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    })
    if (!res.ok) throw new Error('Failed to update presenter')
    const updated = await res.json()
    set((state) => ({
      presenters: state.presenters.map((p) => (p.id === id ? updated : p)),
    }))
  },
  deletePresenter: async (id) => {
    const res = await fetch(`/api/presenters/${id}`, { method: 'DELETE' })
    if (!res.ok) throw new Error('Failed to delete presenter')
    set((state) => ({ presenters: state.presenters.filter((p) => p.id !== id) }))
  },
}))

// ============================================================
// Locations Store
// ============================================================
interface LocationsState {
  locations: VideoLocation[]
  loading: boolean
  fetchLocations: (presenterId?: string) => Promise<void>
  addLocation: (data: InsertVideoLocation) => Promise<VideoLocation>
  updateLocation: (id: string, data: UpdateVideoLocation) => Promise<void>
  deleteLocation: (id: string) => Promise<void>
}

export const useLocationsStore = create<LocationsState>((set, get) => ({
  locations: [],
  loading: false,
  fetchLocations: async (presenterId?) => {
    set({ loading: true })
    try {
      const params = presenterId ? `?presenter_id=${presenterId}` : ''
      const res = await fetch(`/api/locations${params}`)
      if (!res.ok) throw new Error('Failed to fetch locations')
      const data = await res.json()
      set({ locations: data, loading: false })
    } catch (e) {
      set({ loading: false })
    }
  },
  addLocation: async (data) => {
    const res = await fetch('/api/locations', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    })
    if (!res.ok) throw new Error('Failed to add location')
    const item = await res.json()
    set((state) => ({ locations: [...state.locations, item] }))
    return item
  },
  updateLocation: async (id, data) => {
    const res = await fetch(`/api/locations/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    })
    if (!res.ok) throw new Error('Failed to update location')
    const updated = await res.json()
    set((state) => ({
      locations: state.locations.map((l) => (l.id === id ? updated : l)),
    }))
  },
  deleteLocation: async (id) => {
    const res = await fetch(`/api/locations/${id}`, { method: 'DELETE' })
    if (!res.ok) throw new Error('Failed to delete location')
    set((state) => ({ locations: state.locations.filter((l) => l.id !== id) }))
  },
}))

// ============================================================
// Weather Rules Store
// ============================================================
interface WeatherRulesState {
  rules: VideoWeatherRule[]
  loading: boolean
  fetchRules: () => Promise<void>
  addRule: (data: InsertVideoWeatherRule) => Promise<VideoWeatherRule>
  updateRule: (id: string, data: UpdateVideoWeatherRule) => Promise<void>
  deleteRule: (id: string) => Promise<void>
}

export const useWeatherRulesStore = create<WeatherRulesState>((set) => ({
  rules: [],
  loading: false,
  fetchRules: async () => {
    set({ loading: true })
    try {
      const res = await fetch('/api/weather-rules')
      if (!res.ok) throw new Error('Failed to fetch weather rules')
      const data = await res.json()
      set({ rules: data, loading: false })
    } catch (e) {
      set({ loading: false })
    }
  },
  addRule: async (data) => {
    const res = await fetch('/api/weather-rules', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    })
    if (!res.ok) throw new Error('Failed to add rule')
    const item = await res.json()
    set((state) => ({ rules: [...state.rules, item] }))
    return item
  },
  updateRule: async (id, data) => {
    const res = await fetch(`/api/weather-rules/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    })
    if (!res.ok) throw new Error('Failed to update rule')
    const updated = await res.json()
    set((state) => ({
      rules: state.rules.map((r) => (r.id === id ? updated : r)),
    }))
  },
  deleteRule: async (id) => {
    const res = await fetch(`/api/weather-rules/${id}`, { method: 'DELETE' })
    if (!res.ok) throw new Error('Failed to delete rule')
    set((state) => ({ rules: state.rules.filter((r) => r.id !== id) }))
  },
}))
