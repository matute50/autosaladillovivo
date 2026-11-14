'use client'

import { useEffect, useState } from 'react'
import { useWeatherRulesStore } from '@/lib/stores/video-factory'
import type { VideoWeatherRule } from '@/lib/types/video-factory'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input, Label } from '@/components/ui/forms'
import { Loader2, Plus, Trash2, Save, Pencil } from 'lucide-react'
import { toast } from '@/components/ui/use-toast'

type Condicion = 'despejado' | 'nublado' | 'lluvia' | 'viento'
type FranjaHoraria = 'amanecer' | 'dia' | 'atardecer' | 'noche'

export default function ClimaPage() {
  const { rules, loading, fetchRules, addRule, updateRule, deleteRule } = useWeatherRulesStore()
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editForm, setEditForm] = useState<Partial<VideoWeatherRule>>({})

  useEffect(() => {
    fetchRules()
  }, [fetchRules])

  const startEdit = (rule: VideoWeatherRule) => {
    setEditingId(rule.id)
    setEditForm({ ...rule })
  }

  const handleSave = async () => {
    if (!editingId) return
    try {
      await updateRule(editingId, editForm as any)
      toast({ title: 'Regla actualizada', description: `${editForm.condicion} / ${editForm.franja_horaria}` })
      setEditingId(null)
      setEditForm({})
    } catch {
      toast({ variant: 'destructive', title: 'Error al guardar' })
    }
  }

  const handleCancel = () => {
    setEditingId(null)
    setEditForm({})
  }

  const handleDelete = async (id: string) => {
    try {
      await deleteRule(id)
      toast({ title: 'Regla eliminada' })
    } catch {
      toast({ variant: 'destructive', title: 'Error al eliminar' })
    }
  }

  const handleAdd = async () => {
    try {
      await addRule({
        temp_min: 15,
        temp_max: 30,
        condicion: 'despejado',
        franja_horaria: 'dia',
        vestuario_sugerido: null,
        peinado_sugerido: null,
        luz_prompt_sugerida: null,
        override_luto_oscuro: false,
      })
    } catch {
      toast({ variant: 'destructive', title: 'Error al crear regla' })
    }
  }

  const updateField = (field: keyof VideoWeatherRule, value: unknown) => {
    setEditForm(prev => ({ ...prev, [field]: value }))
  }

  if (loading && rules.length === 0) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="w-8 h-8 animate-spin" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h2 className="text-2xl font-bold">Reglas de Clima — Saladillo</h2>
          <p className="text-sm text-muted-foreground mt-1">
            Vestuario, peinado e iluminación automática según temperatura, cielo y hora del día en Saladillo, BA.
          </p>
        </div>
        <Button onClick={handleAdd} className="gap-2">
          <Plus className="w-4 h-4" /> Nueva Regla
        </Button>
      </div>

      <Card>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-muted/40">
                  <th className="text-left px-4 py-3 font-medium w-24">Temp.</th>
                  <th className="text-left px-4 py-3 font-medium w-28">Cielo</th>
                  <th className="text-left px-4 py-3 font-medium w-28">Hora</th>
                  <th className="text-left px-4 py-3 font-medium hidden md:table-cell">Vestuario</th>
                  <th className="text-left px-4 py-3 font-medium hidden md:table-cell">Peinado</th>
                  <th className="text-right px-4 py-3 font-medium w-24">Acciones</th>
                </tr>
              </thead>
              <tbody>
                {rules.map((rule) => {
                  const isEditing = editingId === rule.id
                  return (
                    <tr key={rule.id} className="border-b hover:bg-muted/20 last:border-0 transition-colors">
                      <td className="px-4 py-3">
                        {isEditing ? (
                          <div className="flex items-center gap-1">
                            <Input type="number" className="w-14 h-7 text-xs"
                              value={editForm.temp_min ?? ''} onChange={(e) => updateField('temp_min', Number(e.target.value))} />
                            <span className="text-muted-foreground">–</span>
                            <Input type="number" className="w-14 h-7 text-xs"
                              value={editForm.temp_max ?? ''} onChange={(e) => updateField('temp_max', Number(e.target.value))} />
                          </div>
                        ) : (
                          <span>{rule.temp_min}°–{rule.temp_max}°C</span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        {isEditing ? (
                          <select className="h-7 rounded border border-input bg-background px-2 text-xs w-full"
                            value={editForm.condicion ?? 'despejado'} onChange={(e) => updateField('condicion', e.target.value as Condicion)}>
                            {(['despejado','nublado','lluvia','viento'] as const).map(c => <option key={c} value={c}>{c}</option>)}
                          </select>
                        ) : (
                          <span className="capitalize text-muted-foreground">{rule.condicion}</span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        {isEditing ? (
                          <select className="h-7 rounded border border-input bg-background px-2 text-xs w-full"
                            value={editForm.franja_horaria ?? 'dia'} onChange={(e) => updateField('franja_horaria', e.target.value as FranjaHoraria)}>
                            {(['amanecer','dia','atardecer','noche'] as const).map(f => <option key={f} value={f}>{f}</option>)}
                          </select>
                        ) : (
                          <span className="capitalize">{rule.franja_horaria}</span>
                        )}
                      </td>
                      <td className="px-4 py-3 hidden md:table-cell max-w-[220px]">
                        {isEditing ? (
                          <Input value={editForm.vestuario_sugerido ?? ''} onChange={(e) => updateField('vestuario_sugerido', e.target.value || null)} placeholder="Vestuario sugerido..." />
                        ) : (
                          <span className="text-muted-foreground truncate block">{rule.vestuario_sugerido || '—'}</span>
                        )}
                      </td>
                      <td className="px-4 py-3 hidden md:table-cell max-w-[220px]">
                        {isEditing ? (
                          <Input value={editForm.peinado_sugerido ?? ''} onChange={(e) => updateField('peinado_sugerido', e.target.value || null)} placeholder="Peinado sugerido..." />
                        ) : (
                          <span className="text-muted-foreground truncate block">{rule.peinado_sugerido || '—'}</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <div className="flex justify-end gap-1">
                          {isEditing ? (
                            <>
                              <Button size="sm" variant="ghost" className="h-7 text-green-600 hover:text-green-700" onClick={handleSave}>
                                <Save className="w-3.5 h-3.5" />
                              </Button>
                              <Button size="sm" variant="ghost" className="h-7" onClick={handleCancel}>✕</Button>
                            </>
                          ) : (
                            <>
                              <Button size="sm" variant="ghost" className="h-7" onClick={() => startEdit(rule)}>
                                <Pencil className="w-3.5 h-3.5" />
                              </Button>
                              <Button size="sm" variant="ghost" className="h-7 text-destructive hover:text-red-700" onClick={() => handleDelete(rule.id)}>
                                <Trash2 className="w-3.5 h-3.5" />
                              </Button>
                            </>
                          )}
                        </div>
                      </td>
                    </tr>
                  )
                })}
                {rules.length === 0 && (
                  <tr>
                    <td colSpan={6} className="text-center py-12 text-muted-foreground">
                      No hay reglas configuradas. Agregá una nueva con el botón &quot;Nueva Regla&quot;.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
