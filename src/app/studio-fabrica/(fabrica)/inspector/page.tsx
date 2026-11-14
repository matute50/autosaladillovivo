'use client'

import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input, Label } from '@/components/ui/forms'
import { Badge } from '@/components/ui/forms'
import { Switch } from '@/components/studio/Switch'
import { AlertTriangle, CheckCircle2, XCircle, Video, Image as ImageIcon, FileText } from 'lucide-react'

export default function InspectorPage() {
  const [articleId] = useState('')
  const [wordCount, setWordCount] = useState(0)
  const [hasSmile, setHasSmile] = useState(false)
  const [hasGreen, setHasGreen] = useState(false)
  const [creditsUsed, setCreditsUsed] = useState(1)
  const [modeChroma] = useState(false)

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">Inspector y Previsualizador por Noticia</h2>

      {/* Search by article */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Buscar Noticia</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex gap-2">
            <Input placeholder="ID o slug de la noticia..." className="max-w-xs" />
            <Button variant="outline">Buscar</Button>
          </div>
        </CardContent>
      </Card>

      {/* Two-column layout when article is selected */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Left: Controls */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <FileText className="w-4 h-4" /> Controles
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-1.5">
              <Label>Presentador</Label>
              <select className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm">
                <option>Ara (Redes · 9:16)</option>
                <option>Presentador Fútbol (vMix · 16:9)</option>
              </select>
            </div>

            <div className="space-y-1.5">
              <Label>Locación (fondo)</Label>
              <select className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm">
                <option>[Auto — usar reglas de clima]</option>
                <option>Oficina Saladillo (Foto diurna)</option>
                <option>Plaza Belgrano (Video fondo)</option>
                <option>Estudio Chroma Verde</option>
              </select>
            </div>

            <div className="space-y-1.5">
              <Label>Vestuario/Peinado/Maquillaje</Label>
              <div className="flex gap-2">
                <Badge variant="default">Auto (clima)</Badge>
                <span className="text-xs text-muted-foreground self-center">o escribir manualmente</span>
              </div>
            </div>

            <div className="space-y-1.5">
              <Label>Clima / Luz</Label>
              <div className="flex gap-2">
                <Badge variant="outline">Auto Saladillo congelado</Badge>
                <Button variant="ghost" size="sm" className="h-6 text-xs">Cambiar</Button>
              </div>
            </div>

            <div className="space-y-1.5">
              <Label>Modelo de video</Label>
              <select className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm">
                <option>Veo 3.1 - Lite (1 crédito)</option>
                <option>Veo 3.1 - Fast (2 créditos)</option>
                <option>Veo 3.1 - Standard (3 créditos)</option>
              </select>
            </div>

            <div className="space-y-1.5">
              <Label>Variantes</Label>
              <div className="flex items-center gap-3">
                <Input type="range" min={1} max={4} value={creditsUsed} onChange={(e) => setWordCount(Number(e.target.value))} className="w-full" />
                <span className="text-sm font-mono w-6">{creditsUsed}</span>
              </div>
              <p className="text-xs text-muted-foreground">Créditos estimados: {creditsUsed * 3} (bloque × variantes)</p>
            </div>
          </CardContent>
        </Card>

        {/* Right: Preview + Prompt Inspector */}
        <div className="space-y-4">
          {/* Image preview with safe zone overlay */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <ImageIcon className="w-4 h-4" /> Previsualización
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="relative aspect-[9/16] bg-muted rounded-lg overflow-hidden max-w-[280px] mx-auto">
                <div className="absolute inset-0 flex items-center justify-center text-muted-foreground text-sm">
                  Imagen maestra aún no generada
                </div>
                {!modeChroma && (
                  <div className="absolute bottom-0 left-0 right-0 h-[20%] bg-black/30 flex items-end p-2">
                    <span className="text-white text-xs font-medium drop-shadow">Zona segura del zócalo (20% inferior)</span>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>

          {/* Prompt inspector */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Inspector de Prompts</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-xs font-mono">
              <div>
                <p className="font-semibold text-muted-foreground mb-1">Prompt imagen maestra:</p>
                <code className="block p-2 bg-muted rounded text-wrap break-all">
                  Woman journalist in navy blazer, white blouse, black hair low ponytail...
                </code>
              </div>
              <div>
                <p className="font-semibold text-muted-foreground mb-1">Prompt bloque 1 (8s):</p>
                <code className="block p-2 bg-muted rounded text-wrap break-all">
                  [The character says &quot;Según datos del INDEC...&quot;] [Background: office in Saladillo, morning light]
                </code>
              </div>
            </CardContent>
          </Card>

          {/* Validation semaphore */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Semáforo de Validación</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                <ValidationItem
                  icon={wordCount >= 120 ? <XCircle className="w-4 h-4 text-destructive" /> : <CheckCircle2 className="w-4 h-4 text-green-500" />}
                  label={`Palabras en bloque: ${wordCount}`}
                  ok={wordCount < 120}
                />
                <ValidationItem
                  icon={hasSmile ? <XCircle className="w-4 h-4 text-destructive" /> : <CheckCircle2 className="w-4 h-4 text-green-500" />}
                  label="Sin sonrisa en nota sensible"
                  ok={!hasSmile}
                />
                <ValidationItem
                  icon={hasGreen ? <XCircle className="w-4 h-4 text-destructive" /> : <CheckCircle2 className="w-4 h-4 text-green-500" />}
                  label="Sin color verde en vestuario (chroma)"
                  ok={!hasGreen || modeChroma}
                />
                <ValidationItem
                  icon={<CheckCircle2 className="w-4 h-4 text-green-500" />}
                  label={`Créditos estimados: ${creditsUsed * 3}`}
                  ok={true}
                />
              </div>
              <div className="mt-4 flex gap-2">
                <Button size="sm" className="gap-2">
                  <ImageIcon className="w-3.5 h-3.5" /> Regenerar imagen maestra (gratis)
                </Button>
                <Button size="sm" variant="outline" className="gap-2">
                  <Video className="w-3.5 h-3.5" /> Re-renderizar video
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}

function ValidationItem({ icon, label, ok }: { icon: React.ReactNode; label: string; ok: boolean }) {
  return (
    <div className={`flex items-center gap-3 p-2 rounded-md ${ok ? 'bg-green-50 dark:bg-green-950/20' : 'bg-red-50 dark:bg-red-950/20'}`}>
      {icon}
      <span className="text-sm">{label}</span>
    </div>
  )
}
