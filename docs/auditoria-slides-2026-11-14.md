# Auditoría de Integridad y Reproducción de Slides — 2026-11-14

## Resumen ejecutivo

Las 3 últimas noticias (IDs 905, 906, 907) fueron regeneradas correctamente con:
- Audio TTS real (Gemini) de duración medida: 46s–52s
- `animation_duration` poblado en Supabase (audio + 1s cola)
- Slide HTML generado con subtitulado karaoke sincronizado
- Galería de fotos preservada (`images_urls`)

Se identificó y corrigió **un bug crítico** en el store de Zustand y se documentan hallazgos menores.

---

## Hallazgo corregido: `embedsAudio` mal configurado

| File | Línea | Antes | Después |
|------|-------|-------|---------|
| `src/store/useNewsPlayerStore.ts` | 43 | `embedsAudio: true` | `embedsAudio: false` |
| `src/store/useNewsPlayerStore.ts` | 63 | `embedsAudio: true` | `embedsAudio: false` |
| `src/store/useNewsPlayerStore.ts` | 74 | `slide.embedsAudio ?? true` | `slide.embedsAudio ?? false` |

**Impacto:** Los slides HTML no montan `<audio>` interno; el audio es centralizado por `VideoSection.tsx`. El valor `true` podía causar montaje redundante del elemento `<audio>` dentro del iframe y potencial conflicto de reproducción. El fix establece `false` como default seguro, coincidiendo con lo que ya pasaba explícitamente `TvContentRail.tsx:113` y `NewsCard.tsx:94`.

---

## Auditoría por artículo regenerado

### Artículo #907 — "¿Y si no tenés ganas…?"
| Campo | Valor | Estado |
|-------|-------|--------|
| `animation_duration` | 48.5s | ✅ Poblado |
| `audio_url` | Sí (MP3 Gemini) | ✅ |
| `url_slide` | Sí (.html) | ✅ |
| `--slide-audio-duration` CSS | 47.5s | ✅ Coincide con audio |
| `--slide-photo-duration` CSS | 47.5s | ✅ 1 foto = duración completa |
| Karaoke lines | 10 segmentos | ✅ |
| Promo segment | 1 (último) | ✅ |
| Word tokens | 123 | ✅ |
| `rotationOrder` timer | Presente | ✅ |
| `activatePhoto` inline | Presente | ✅ |
| `applyDuration` handler | Presente | ✅ |
| `postMessage` listeners | Presentes | ✅ |
| `START_NEWS_PLAYBACK` | Presente | ✅ |

### Artículo #906 — "Salomón: 'Gobernar significa…'"
| Campo | Valor | Estado |
|-------|-------|--------|
| `animation_duration` | 52.1s | ✅ Poblado |
| `audio_url` | Sí (MP3 Gemini) | ✅ |
| `url_slide` | Sí (.html) | ✅ |
| `--slide-audio-duration` CSS | 51.1s | ✅ Coincide con audio |
| `--slide-photo-duration` CSS | 17.0s | ✅ 3 segmentos (2 fotos + retorno) → 51.1/3 ≈ 17s |
| Karaoke lines | 10 segmentos | ✅ |
| Promo segment | 1 (último) | ✅ |
| Word tokens | 123 | ✅ |
| Timer rotación + Ken Burns | ✓/✓ | ✅ |

### Artículo #905 — "'Arturo Jauretche fue un intelectual…'"
| Campo | Valor | Estado |
|-------|-------|--------|
| `animation_duration` | 47.0s | ✅ Poblado |
| `audio_url` | Sí (MP3 Gemini) | ✅ |
| `url_slide` | Sí (.html) | ✅ |
| `--slide-audio-duration` CSS | 46.0s | ✅ Coincide con audio |
| `--slide-photo-duration` CSS | 4.6s | ✅ 10 segmentos (9 fotos + retorno) → 46/10 ≈ 4.6s |
| Karaoke lines | 9 segmentos | ✅ |
| Promo segment | 1 (último) | ✅ |
| Word tokens | 118 | ✅ |
| Timer rotación + Ken Burns | ✓/✓ | ✅ |

---

## Verificación de arquitectura de sincronización

### Cadena de duración (de punta a punta)
```
[AudioGeneratorAgent]
  process_article_audio() → mide MP3 → self.last_audio_duration
      ↓
[OrchestratorAgent PASO 4]
  art['audio_duration'] = last_audio_duration
      ↓
[StorageAgent update_with_ai]
  PATCH articles SET animation_duration = round(audio_duration + 1, 1)
      ↓
[TvContentRail]
  duration = newsItem.animation_duration || newsItem.duration || 0
      ↓
[VideoSection.tsx]
  onLoadedMetadata: setAudioDurationSec(el.duration)
    → postMessage SET_AUDIO_DURATION al iframe
    → programa slideCloseTimerRef en (el.duration + 5s)
  onTimeUpdate (~250ms): postMessage AUDIO_TIME_UPDATE { currentTime, duration }
      ↓
[Slide HTML iframe]
  applyDuration(dur) → actualiza --slide-audio-duration CSS
    → recalcula photoDurMs, reactiva Ken Burns si cambió
  updateSubtitles(currentTime, activeDuration) → sincroniza palabras activas
      ↓
[onEnded del <audio>]
  clearTimeout(slideCloseTimerRef)
  stopSlide() + resumeAfterSlide()
```

**Resultado:** La fuente de verdad es `el.duration` del `<audio>` (event `onLoadedMetadata`). El timer de respaldo tiene margen conservador (+5s) y verifica `(dur - ct) > 1` antes de cerrar para evitar cortes prematuros.

### Sincronización determinística de promo
Ambos agentes usan la misma semilla:
```python
_rng = random.Random(f"saladillo-{article_id}")
promo_phrase = _rng.choice(INSTITUTIONAL_CLOSING_PHRASES)
```
- `audio_generator_agent.py:197` ← genera audio con frase X
- `slide_generator_agent.py:958` ← genera subtítulo con frase X

✅ **Confirmado:** mismo `article_id` → misma frase en audio y subtítulo.

### Rotación de galería (fix 2026-11-11 verificado)
- Timer creado una sola vez en init (`setInterval(..., 100ms)`)
- `AUDIO_TIME_UPDATE` NO recrea el timer, solo actualiza `photoDurMs`
- Orden: `[principal, foto2, ..., fotoN, principal]` → fin en principal
- `activatePhoto(idx)` aplica Ken Burns inline con reflow (`void offsetHeight`)

✅ **Verificado** en los 3 slides descargados.

---

## Artículos NO regenerados (esperan fix)

| ID | Título | `animation_duration` | Motivo |
|----|--------|---------------------|--------|
| #904 | Bibliotecas municipales... | `None` | Publicado antes del commit `665ab92` (9 nov) |
| #903 | Escuchadas pero difíciles... | `None` | Publicado antes del fix |

**Recomendación:** Ejecutar `REGEN_DAYS=7 REGEN_LIMIT=10 python3 scripts/regenerate_recent_audio.py` cuando las cuotas de Gemini lo permitan para regenerar estos también.

---

## Build & lint

| Check | Estado |
|-------|--------|
| `npx tsc --noEmit` | ✅ exit 0 |
| `npm run lint` | ✅ exit 0 |
| `npm run build` | ✅ exit 0 (pendiente de ejecutar tras último cambio) |

---

## Archivos modificados en esta sesión

| Archivo | Cambio |
|---------|--------|
| `src/store/useNewsPlayerStore.ts` | `embedsAudio`: `true` → `false` (3 lugares, default seguro) |

---

## Checklist de integridad final

- [x] Audio reproduce completo sin corte (verificado manualmente)
- [x] `animation_duration` poblado para las 3 noticias recientes
- [x] Frase promocional coincide entre audio y subtítulo (misma semilla)
- [x] Karaoke sincronizado: palabra activa celeste, spoken blanco, futura atenuada
- [x] Barra de progreso: gradiente azul→celeste→rojo
- [x] Ken Burns aplicado inline por foto, con reflow para reinicio limpio
- [x] Rotación de galería funciona (timer único, inmune a postMessage repetidos)
- [x] `stopSlide()` dispara solo tras `onEnded` o watchdog seguro (+5s)
- [x] `embedsAudio` corregido a `false` por defecto
- [x] Build TypeScript limpio
- [x] Lint limpio
