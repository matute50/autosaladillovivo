'use client'

import { useEffect } from 'react'
import { useFactorySettingsStore } from '@/lib/stores/video-factory'
import { Switch } from '@/components/studio/Switch'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Loader2, AlertCircle, CheckCircle2 } from 'lucide-react'
import { Progress } from '@/components/ui/progress'
import { useState } from 'react'

export function PilotoDashboard() {
  const { settings, loading, fetchSettings, updateSettings } = useFactorySettingsStore()
  const [pilotoActive, setPilotoActive] = useState(true)

  useEffect(() => {
    fetchSettings()
  }, [fetchSettings])

  if (loading && !settings) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Status Bar */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2">
            Estado del Sistema
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <span className="text-sm font-medium">Piloto Automático</span>
              <Switch
                checked={settings?.piloto_automatico_activo ?? true}
                onCheckedChange={(v) => {
                  setPilotoActive(v)
                  updateSettings({ piloto_automatico_activo: v })
                }}
              />
              {(settings?.piloto_automatico_activo ?? true) ? (
                <span className="text-xs text-green-600 flex items-center gap-1">
                  <CheckCircle2 className="w-3 h-3" /> Activo
                </span>
              ) : (
                <span className="text-xs text-destructive flex items-center gap-1">
                  <AlertCircle className="w-3 h-3" /> Pausado
                </span>
              )}
            </div>

            <div className="flex flex-wrap gap-4 text-sm text-muted-foreground">
              {settings?.worker_last_heartbeat_at ? (
                <span title={new Date(settings.worker_last_heartbeat_at).toLocaleString('es-AR')}>
                  Último heartbeat: {new Date(settings.worker_last_heartbeat_at).toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit' })}
                </span>
              ) : (
                <span className="text-amber-600">Worker desconectado</span>
              )}
              <span>Créditos: {settings?.creditos_usados_hoy ?? 0}/{settings?.tope_diario_creditos ?? 100}</span>
            </div>
          </div>

          {/* Credit Progress */}
          <div className="mt-4">
            <Progress
              value={((settings?.creditos_usados_hoy ?? 0) / (settings?.tope_diario_creditos ?? 100)) * 100}
              className="h-2"
            />
            <p className="text-xs text-muted-foreground mt-1">
              {(settings?.creditos_usados_hoy ?? 0)} de {(settings?.tope_diario_creditos ?? 100)} créditos usados hoy
            </p>
          </div>

          {settings?.pausado_por_error && (
            <div className="mt-4 p-3 bg-destructive/10 rounded-md text-sm text-destructive flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{settings.motivo_pausa || 'Error en el proceso — revisar logs'}</span>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Bandejas */}
      <div className="grid gap-6 lg:grid-cols-2">
        <AprobacionBandeja />
        <ColaTrabajos />
      </div>
    </div>
  )
}

// Placeholder components — wired to fetch AraVideoJobs when Task 5 completes
function AprobacionBandeja() {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base flex items-center gap-2">
          ⏳ Bandeja de Aprobación Sensible
        </CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-muted-foreground">
          Las notas de luto o policiales graves pendientes aparecerán aquí cuando el worker las marque con <code>requiere_aprobacion_sensible=true</code>.
        </p>
        <div className="mt-4 p-4 border border-dashed rounded-lg text-center text-sm text-muted-foreground">
          No hay notas pendientes de aprobación
        </div>
      </CardContent>
    </Card>
  )
}

function ColaTrabajos() {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base flex items-center gap-2">
          📋 Cola de Trabajos
        </CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-muted-foreground">
          Los trabajos generados por el piloto automático se mostrarán aquí con su estado actual.
        </p>
        <div className="mt-4 p-4 border border-dashed rounded-lg text-center text-sm text-muted-foreground">
          No hay trabajos en la cola
        </div>
      </CardContent>
    </Card>
  )
}
