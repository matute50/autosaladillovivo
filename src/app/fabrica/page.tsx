'use client'

import React, { useState, useEffect } from 'react'

interface Article {
  id: number
  title: string
  category: string
  video_script: string | null
  video_status: string | null
  video_location_category: string | null
  video_path: string | null
  video_generated_at: string | null
  created_at: string
}

interface ScriptData {
  bloques: string[]
  duracion_segundos: number
  ticker_texto?: string
  categoria_locacion?: string
}

const CATEGORIAS = [
  'municipales',
  'deportes',
  'sociedad',
  'policiales',
  'cultura',
  'politicas',
  'institucionales',
  'regionales',
  'general'
]

export default function FabricaPage() {
  const [articles, setArticles] = useState<Article[]>([])
  const [selectedArticle, setSelectedArticle] = useState<Article | null>(null)
  const [scriptData, setScriptData] = useState<ScriptData | null>(null)
  const [loading, setLoading] = useState<boolean>(true)
  const [filterStatus, setFilterStatus] = useState<string>('todos')
  const [savingLocation, setSavingLocation] = useState<boolean>(false)

  useEffect(() => {
    fetchArticles()
  }, [])

  const fetchArticles = async () => {
    setLoading(true)
    try {
      const res = await fetch('/api/fabrica')
      const data = await res.json()
      if (data.articles) {
        setArticles(data.articles)
        if (data.articles.length > 0 && !selectedArticle) {
          selectArticle(data.articles[0])
        }
      }
    } catch (e) {
      console.error('Error cargando artículos:', e)
    } finally {
      setLoading(false)
    }
  }

  const selectArticle = (art: Article) => {
    setSelectedArticle(art)
    if (art.video_script) {
      try {
        const parsed = JSON.parse(art.video_script)
        if (parsed.bloques) {
          setScriptData(parsed)
          return
        }
      } catch {
        // Formato texto plano delimitado
        const lines = art.video_script.split('\n\n').filter(Boolean)
        setScriptData({
          bloques: lines,
          duracion_segundos: lines.length * 8,
          ticker_texto: art.title,
          categoria_locacion: art.video_location_category || 'general'
        })
        return
      }
    }
    setScriptData(null)
  }

  const handleLocationChange = async (newCategory: string) => {
    if (!selectedArticle) return
    setSavingLocation(true)
    try {
      const res = await fetch('/api/fabrica', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action: 'update_location',
          article_id: selectedArticle.id,
          location_category: newCategory
        })
      })
      if (res.ok) {
        setSelectedArticle({ ...selectedArticle, video_location_category: newCategory })
        setArticles(articles.map(a => a.id === selectedArticle.id ? { ...a, video_location_category: newCategory } : a))
      }
    } catch (e) {
      console.error('Error guardando locación:', e)
    } finally {
      setSavingLocation(false)
    }
  }

  const downloadWorkflowJson = async () => {
    if (!selectedArticle || !scriptData?.bloques) return
    try {
      const res = await fetch('/api/fabrica', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action: 'generate_workflow',
          article_id: selectedArticle.id,
          bloques: scriptData.bloques,
          location_category: selectedArticle.video_location_category || 'general'
        })
      })
      const data = await res.json()
      if (data.workflow) {
        const blob = new Blob([JSON.stringify(data.workflow, null, 2)], { type: 'application/json' })
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `workflow_ara_${selectedArticle.id}.json`
        a.click()
        URL.revokeObjectURL(url)
      }
    } catch (e) {
      console.error('Error descargando workflow:', e)
    }
  }

  const downloadPromptsTxt = () => {
    if (!selectedArticle || !scriptData?.bloques) return
    const content = scriptData.bloques
      .map((b, i) => `Ara hablando a cámara en estudio de noticias: "${b}". Gesto sobrio, plano vertical 9:16.`)
      .join('\n\n')
    const blob = new Blob([content], { type: 'text/plain;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `prompts_ara_${selectedArticle.id}.txt`
    a.click()
    URL.revokeObjectURL(url)
  }

  const filteredArticles = articles.filter(a => {
    if (filterStatus === 'todos') return true
    return a.video_status === filterStatus
  })

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-6 font-sans">
      {/* Header */}
      <div className="max-w-7xl mx-auto mb-8 flex flex-col md:flex-row md:items-center justify-between border-b border-slate-800 pb-5 gap-4">
        <div>
          <div className="flex items-center gap-3">
            <div className="w-4 h-4 rounded-full bg-red-600 animate-pulse" />
            <h1 className="text-2xl font-bold tracking-tight text-white">
              Fábrica de Videos de Ara <span className="text-xs font-semibold px-2.5 py-0.5 rounded bg-blue-900/60 text-blue-300 border border-blue-700">Google Flow 9:16</span>
            </h1>
          </div>
          <p className="text-sm text-slate-400 mt-1">
            Sistema de orquestación televisiva con persistencia de identidad y post-producción FFmpeg.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <select
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value)}
            className="bg-slate-900 border border-slate-700 text-sm rounded-lg px-3 py-2 text-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="todos">Todos los estados</option>
            <option value="pendiente">Pendientes</option>
            <option value="completado">Completados</option>
            <option value="error">Con Error</option>
            <option value="excluido">Excluidos</option>
          </select>
          <button
            onClick={fetchArticles}
            className="bg-slate-800 hover:bg-slate-700 text-slate-200 text-sm font-medium px-4 py-2 rounded-lg border border-slate-700 transition"
          >
            Actualizar
          </button>
        </div>
      </div>

      {/* Main Grid: 4 Etapas */}
      <div className="max-w-7xl mx-auto grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Columna 1: Artículos */}
        <div className="lg:col-span-4 bg-slate-900/70 border border-slate-800 rounded-xl p-4 flex flex-col h-[750px]">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-400 mb-3 flex items-center justify-between">
            <span>1. Artículos Supabase</span>
            <span className="text-xs font-normal text-slate-500">{filteredArticles.length} disponibles</span>
          </h2>

          <div className="flex-1 overflow-y-auto space-y-2.5 pr-1">
            {loading ? (
              <div className="text-center py-12 text-slate-500 text-sm">Cargando noticias...</div>
            ) : filteredArticles.length === 0 ? (
              <div className="text-center py-12 text-slate-500 text-sm">No hay noticias con este filtro.</div>
            ) : (
              filteredArticles.map((art) => {
                const isSelected = selectedArticle?.id === art.id
                return (
                  <div
                    key={art.id}
                    onClick={() => selectArticle(art)}
                    className={`p-3.5 rounded-lg cursor-pointer border transition text-left ${
                      isSelected
                        ? 'bg-blue-950/40 border-blue-600 shadow-md shadow-blue-950/50'
                        : 'bg-slate-900/40 border-slate-800/80 hover:bg-slate-800/50'
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2 mb-1.5">
                      <span className="text-xs font-semibold uppercase text-blue-400">{art.category || 'General'}</span>
                      <span className={`text-[10px] font-bold uppercase px-2 py-0.5 rounded-full ${
                        art.video_status === 'completado' ? 'bg-emerald-950 text-emerald-400 border border-emerald-800' :
                        art.video_status === 'error' ? 'bg-red-950 text-red-400 border border-red-800' :
                        art.video_status === 'excluido' ? 'bg-amber-950 text-amber-400 border border-amber-800' :
                        'bg-slate-800 text-slate-300'
                      }`}>
                        {art.video_status || 'Sin guion'}
                      </span>
                    </div>
                    <p className="text-xs font-medium text-slate-200 line-clamp-2 leading-relaxed">
                      {art.title}
                    </p>
                    <div className="mt-2 flex items-center justify-between text-[11px] text-slate-500">
                      <span>ID: #{art.id}</span>
                      <span>{new Date(art.created_at).toLocaleDateString()}</span>
                    </div>
                  </div>
                )
              })
            )}
          </div>
        </div>

        {/* Columna 2 & 3: Guion de Ara y Exportación */}
        <div className="lg:col-span-5 bg-slate-900/70 border border-slate-800 rounded-xl p-5 flex flex-col h-[750px] overflow-y-auto">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3 mb-4">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-400">
              2. Guion & Locación (Métrica 8s)
            </h2>
            {scriptData && (
              <span className="text-xs bg-indigo-950 text-indigo-300 border border-indigo-800 px-2.5 py-0.5 rounded font-mono">
                {scriptData.duracion_segundos}s • {scriptData.bloques.length} bloques
              </span>
            )}
          </div>

          {selectedArticle ? (
            <div className="space-y-4">
              {/* Selector de Locación Temática */}
              <div className="bg-slate-950/60 p-3.5 rounded-lg border border-slate-800/80">
                <label className="text-xs font-semibold text-slate-300 block mb-1.5 uppercase tracking-wide">
                  Locación Asignada ({savingLocation ? 'Guardando...' : 'assets/locaciones/'})
                </label>
                <div className="flex gap-2">
                  <select
                    value={selectedArticle.video_location_category || 'general'}
                    onChange={(e) => handleLocationChange(e.target.value)}
                    className="flex-1 bg-slate-900 border border-slate-700 text-xs rounded-md px-3 py-2 text-slate-200 focus:outline-none focus:ring-1 focus:ring-blue-500"
                  >
                    {CATEGORIAS.map(cat => (
                      <option key={cat} value={cat}>{cat}</option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Bloques de 8 Segundos */}
              {scriptData?.bloques && scriptData.bloques.length > 0 ? (
                <div className="space-y-3">
                  {scriptData.bloques.map((bloque, idx) => {
                    const wordCount = bloque.trim().split(/\s+/).length
                    const isOptimal = wordCount >= 17 && wordCount <= 20
                    const endsWithDot = bloque.trim().endsWith('.')
                    return (
                      <div key={idx} className="bg-slate-950/80 border border-slate-800 p-3.5 rounded-lg">
                        <div className="flex items-center justify-between text-[11px] font-semibold text-slate-400 mb-2">
                          <span className="flex items-center gap-1.5 text-blue-400">
                            <span className="w-2 h-2 rounded-full bg-blue-500" />
                            Bloque {idx + 1} (8 seg)
                          </span>
                          <span className={`px-2 py-0.5 rounded text-[10px] font-mono ${
                            isOptimal ? 'bg-emerald-950 text-emerald-300 border border-emerald-800' : 'bg-amber-950 text-amber-300 border border-amber-800'
                          }`}>
                            {wordCount} palabras {endsWithDot ? '• Punto OK' : '• Sin punto final'}
                          </span>
                        </div>
                        <p className="text-xs text-slate-200 leading-relaxed font-sans">
                          {bloque}
                        </p>
                      </div>
                    )
                  })}

                  {/* Ticker Inferior Preview */}
                  {scriptData.ticker_texto && (
                    <div className="bg-black/90 border border-slate-800 p-3 rounded-lg mt-4">
                      <span className="text-[10px] uppercase tracking-wider text-slate-500 font-bold block mb-1">
                        Ticker Inferior (Scroll 9:16)
                      </span>
                      <p className="text-xs font-mono text-slate-300 truncate">
                        {scriptData.ticker_texto}
                      </p>
                    </div>
                  )}

                  {/* Botones de Exportación Flow Automation */}
                  <div className="pt-4 border-t border-slate-800 space-y-2">
                    <button
                      onClick={downloadWorkflowJson}
                      className="w-full bg-blue-600 hover:bg-blue-500 text-white font-medium text-xs py-2.5 px-4 rounded-lg shadow-sm transition flex items-center justify-center gap-2"
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                      </svg>
                      Descargar Workflow JSON (Last Frame)
                    </button>
                    <button
                      onClick={downloadPromptsTxt}
                      className="w-full bg-slate-800 hover:bg-slate-700 text-slate-300 font-medium text-xs py-2 px-4 rounded-lg border border-slate-700 transition"
                    >
                      Descargar Prompts TXT (8s Concat)
                    </button>
                  </div>
                </div>
              ) : (
                <div className="text-center py-16 bg-slate-950/40 rounded-lg border border-dashed border-slate-800">
                  <p className="text-xs text-slate-400">Este artículo aún no cuenta con guion adaptado para Ara.</p>
                  <p className="text-[11px] text-slate-500 mt-1">El módulo `ara_script_writer.py` lo generará automáticamente.</p>
                </div>
              )}
            </div>
          ) : (
            <div className="text-center py-20 text-slate-500 text-xs">Selecciona un artículo de la lista.</div>
          )}
        </div>

        {/* Columna 4: Monitor y Auditor de Video TV-Grade */}
        <div className="lg:col-span-3 bg-slate-900/70 border border-slate-800 rounded-xl p-5 flex flex-col h-[750px]">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-400 mb-4 border-b border-slate-800 pb-3">
            3. Post-Producción FFmpeg
          </h2>

          <div className="space-y-4 text-xs">
            {/* Especificaciones de Render */}
            <div className="bg-slate-950/70 p-3.5 rounded-lg border border-slate-800 space-y-2">
              <div className="flex justify-between text-slate-400">
                <span>Formato:</span>
                <span className="font-semibold text-slate-200">Vertical 9:16 (720x1280)</span>
              </div>
              <div className="flex justify-between text-slate-400">
                <span>Zócalo:</span>
                <span className="font-semibold text-slate-200">Negro (+140px Safe Zone)</span>
              </div>
              <div className="flex justify-between text-slate-400">
                <span>Logo:</span>
                <span className="font-semibold text-slate-200">Fijo a la izquierda</span>
              </div>
              <div className="flex justify-between text-slate-400">
                <span>Audio:</span>
                <span className="font-semibold text-slate-200">Voz limpia de Ara</span>
              </div>
            </div>

            {/* Estado del Video Seleccionado */}
            <div className="bg-slate-950/70 p-3.5 rounded-lg border border-slate-800">
              <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wide block mb-2">
                Estado del Archivo
              </span>
              {selectedArticle?.video_path ? (
                <div className="space-y-2">
                  <div className="text-emerald-400 font-semibold flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-emerald-500" />
                    Video Consolidado Listo
                  </div>
                  <p className="text-[11px] font-mono text-slate-400 break-all bg-slate-900 p-2 rounded border border-slate-800">
                    {selectedArticle.video_path}
                  </p>
                  {selectedArticle.video_generated_at && (
                    <span className="text-[10px] text-slate-500 block">
                      Generado: {new Date(selectedArticle.video_generated_at).toLocaleString()}
                    </span>
                  )}
                </div>
              ) : (
                <div className="text-slate-500 italic py-2">
                  Aún no se ha consolidado el video para esta noticia.
                </div>
              )}
            </div>

            {/* Simulación Gráfica de Safe Zone 9:16 */}
            <div className="mt-4 flex-1 flex flex-col items-center justify-center">
              <div className="w-36 h-64 bg-slate-950 border-2 border-slate-800 rounded-xl relative overflow-hidden flex flex-col justify-end p-2 shadow-inner">
                {/* Personaje Placeholder */}
                <div className="absolute inset-0 flex items-center justify-center text-[10px] text-slate-600 font-mono">
                  [Ara 9:16]
                </div>
                {/* Zócalo Negro con Safe Zone */}
                <div className="w-full h-8 bg-black border border-slate-700/80 rounded flex items-center px-1.5 gap-1 mb-4 z-10">
                  <div className="w-4 h-4 rounded bg-red-600 flex-shrink-0" />
                  <div className="text-[7px] text-white font-mono truncate">Ticker noticia...</div>
                </div>
                <div className="text-[8px] text-slate-600 text-center font-mono pb-1">
                  Safe Zone (+140px)
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
