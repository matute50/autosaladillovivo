'use client'

import { useEffect, useState } from 'react'
import { usePresentersStore, useLocationsStore } from '@/lib/stores/video-factory'
import type { VideoPresenter } from '@/lib/types/video-factory'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input, Label } from '@/components/ui/forms'
import { Badge } from '@/components/ui/forms'
import { Switch } from '@/components/studio/Switch'
import { Loader2, Plus, Eye, Trash2, Camera } from 'lucide-react'
import { toast } from '@/components/ui/use-toast'

export default function PresentadoresPage() {
  const { presenters, loading, fetchPresenters, updatePresenter } = usePresentersStore()
  const { locations, fetchLocations } = useLocationsStore()
  const [selectedSlug, setSelectedSlug] = useState<string>('ara')

  useEffect(() => {
    fetchPresenters()
  }, [fetchPresenters])

  const selectedPresenter = presenters.find((p) => p.slug === selectedSlug)
  const presenterLocations = locations.filter((l) => l.presenter_id === selectedPresenter?.id)

  if (loading && presenters.length === 0) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="w-8 h-8 animate-spin" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">Perfiles de Presentadores y Galería de Locaciones</h2>

      {/* Selector de presentador */}
      <div className="flex gap-2 flex-wrap">
        {presenters.map((p) => (
          <Button
            key={p.id}
            variant={selectedSlug === p.slug ? 'default' : 'outline'}
            onClick={() => { setSelectedSlug(p.slug); fetchLocations(p.id) }}
            className="gap-2"
          >
            {p.slug.toUpperCase()} · {p.destino === 'redes' ? '📱 Redes' : '🎬 vMix'}
            {p.activo && <span className="w-2 h-2 rounded-full bg-green-500" />}
            {!p.activo && <span className="w-2 h-2 rounded-full bg-muted-foreground" />}
          </Button>
        ))}
        <Button variant="ghost" size="sm" onClick={() => toast({ title: 'Agregar presentador', description: 'Funcionalidad en desarrollo' })}>
          <Plus className="w-4 h-4 mr-1" /> Nuevo
        </Button>
      </div>

      {selectedPresenter && (
        <div className="grid gap-6 lg:grid-cols-2">
          {/* Editor del presentador */}
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-3">
              <CardTitle className="text-base">{selectedPresenter.nombre}</CardTitle>
              <Badge variant={selectedPresenter.activo ? 'default' : 'secondary'}>
                {selectedPresenter.activo ? 'Activo' : 'Inactivo'}
              </Badge>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="space-y-1.5">
                  <Label>Alias Google Flow</Label>
                  <Input
                    value={selectedPresenter.flow_character_alias ?? ''}
                    onChange={(e) => updatePresenter(selectedPresenter.id, { flow_character_alias: e.target.value || null })}
                    placeholder="Ej: @Ara"
                  />
                </div>

                <div className="space-y-1.5">
                  <Label>Descripción vocal fija</Label>
                  <textarea
                    rows={3}
                    className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm resize-none"
                    value={selectedPresenter.voz_descripcion_fija ?? ''}
                    onChange={(e) => updatePresenter(selectedPresenter.id, { voz_descripcion_fija: e.target.value || null })}
                  />
                  <p className="text-xs text-muted-foreground">Texto base que se repite en cada clip (acento rioplatense, timbre, etc.)</p>
                </div>

                <div className="space-y-1.5">
                  <Label>Prompt visual manual (look a gusto)</Label>
                  <textarea
                    rows={2}
                    className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm resize-none"
                    value={selectedPresenter.look_manual_prompt ?? ''}
                    onChange={(e) => updatePresenter(selectedPresenter.id, { look_manual_prompt: e.target.value || null })}
                    placeholder="Vestuario, peinado y maquillaje personalizados..."
                  />
                </div>

                <div className="space-y-3 pt-2 border-t">
                  <ToggleRow
                    checked={selectedPresenter.usar_clima_auto}
                    label="Clima automático (Saladillo)"
                    onCheckedChange={(v) => updatePresenter(selectedPresenter.id, { usar_clima_auto: v })}
                  />
                  <ToggleRow
                    checked={selectedPresenter.modo_chroma_key}
                    label="Chroma Key (fondo verde uniforme, bloquea verdes en vestuario)"
                    onCheckedChange={(v) => updatePresenter(selectedPresenter.id, { modo_chroma_key: v })}
                  />
                  <ToggleRow
                    checked={selectedPresenter.quemar_zocalo_ffmpeg}
                    label="Quemar zócalo con FFmpeg"
                    onCheckedChange={(v) => updatePresenter(selectedPresenter.id, { quemar_zocalo_ffmpeg: v })}
                  />
                </div>

                <div className="grid grid-cols-2 gap-3 pt-2 border-t">
                  <div className="space-y-1.5">
                    <Label>Formato</Label>
                    <select
                      className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm"
                      value={selectedPresenter.aspect_ratio_default}
                      onChange={(e) => updatePresenter(selectedPresenter.id, { aspect_ratio_default: e.target.value as any })}
                    >
                      <option value="9:16">9:16 Vertical</option>
                      <option value="16:9">16:9 Horizontal</option>
                    </select>
                  </div>
                  <div className="space-y-1.5">
                    <Label>Modelo por defecto</Label>
                    <select
                      className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm"
                      value={selectedPresenter.modelo_default}
                      onChange={(e) => updatePresenter(selectedPresenter.id, { modelo_default: e.target.value as any })}
                    >
                      <option value="Veo 3.1 - Lite">Veo 3.1 - Lite</option>
                      <option value="Veo 3.1 - Fast">Veo 3.1 - Fast</option>
                      <option value="Veo 3.1 - Standard">Veo 3.1 - Standard</option>
                    </select>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Galería de locaciones */}
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-3">
              <CardTitle className="text-base">Locaciones — {selectedPresenter.nombre}</CardTitle>
              <Button variant="outline" size="sm" onClick={() => toast({ title: 'Subir locación', description: 'Arrastra una imagen o video al bucket de Storage' })}>
                <Camera className="w-4 h-4 mr-1" /> Subir
              </Button>
            </CardHeader>
            <CardContent>
              {presenterLocations.length === 0 ? (
                <div className="border border-dashed rounded-lg p-8 text-center text-sm text-muted-foreground">
                  No hay locaciones cargadas para este presentador.
                </div>
              ) : (
                <div className="grid grid-cols-2 gap-3">
                  {presenterLocations.map((loc) => (
                    <div key={loc.id} className="relative group rounded-lg overflow-hidden border">
                      {loc.public_url ? (
                        <img src={loc.public_url} alt={loc.nombre} className="w-full h-28 object-cover" />
                      ) : (
                        <div className="w-full h-28 bg-muted flex items-center justify-center text-xs text-muted-foreground">
                          Sin preview
                        </div>
                      )}
                      <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-2">
                        <Button variant="secondary" size="icon" className="h-7 w-7">
                          <Eye className="w-3 h-3" />
                        </Button>
                        <Button variant="destructive" size="icon" className="h-7 w-7">
                          <Trash2 className="w-3 h-3" />
                        </Button>
                      </div>
                      <div className="p-2 bg-card text-xs">
                        <p className="font-medium truncate">{loc.nombre}</p>
                        <span className="text-muted-foreground capitalize">{loc.tipo.replace('_', ' ')}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  )
}

function ToggleRow({ checked, label, onCheckedChange }: {
  checked: boolean
  label: string
  onCheckedChange: (v: boolean) => void
}) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-sm">{label}</span>
      <Switch checked={checked} onCheckedChange={onCheckedChange} />
    </div>
  )
}
