# Reporte de Desviación de Especificaciones (EGM Drift Report)
**Fecha:** 2026-11-10  
**Módulo auditado:** Reproducción Multimedia y Pipeline de Slides Interactivas (`VideoSection.tsx`, `SlideGeneratorAgent`, `complete_automation.py`)  
**Auditor:** EGM Technical Quality Auditor (`egm-codebase-details`)  
**Estado:** Todos los módulos alineados al 100% (Drift completamente resuelto).

---

## 1. saladillo-news-pipeline/SKILL.md
* **Alineación:** 100% (No drift detected).
* **Verificaciones:**
  - Ciclo de 5 pasos coordinado por `complete_automation.py` y `OrchestratorAgent`.
  - Extracción, reescritura IA, síntesis fonética rioplatense (Voxtral TTS Elena), generación de slides Full HD con subida a Supabase Storage y publicación oficial.
  - Parámetros CLI (`--once`, `--limit`, `--json-output`, `--no-audio`, `--no-slides`) operativos y alineados.

---

## 2. logica-de-reproduccion-de-videos/SKILL.md
* **Alineación:** 100% (No drift detected).
* **Verificaciones:**
  - Integración de noticias `.html`: pausa del video base, montaje en iframe con hidratación segura vía `srcDoc` (bypass CSP Supabase Storage), sincronización de audio y reanudación al terminar (`onEnded`).
  - Capas de anti-branding y reproducción continua operativas.

---

## 3. video-playback-mastery/SKILL.md
* **Smart Slot System (v18.0) [RESUELTO]**: Doble slot A/B permanente con alternancia de `z-index` y preservación de instancias para cero parpadeos negros.
* **Superposición de Barras Cinematográficas vs. Lower Thirds [RESUELTO]**:
  - *Desviación previa*: Las barras cinematográficas inferiores de `VideoSection.tsx` (`cinematic-bar-bottom-solid` y `cinematic-bar-bottom-gradient` con `z-[45]`) no estaban excluidas durante la visualización de noticias interactivas, tapando el Lower Third flotante (`bottom: 5.5%`, `z-40`).
  - *Corrección*: Se agregó la guarda condicional `!isNewsContent` a ambas barras inferiores en `VideoSection.tsx`.
* **Normalización de Audio (`volumen_extra`) [RESUELTO]**: Multiplicador `TargetVolume = Math.min(1, (volume || 1) * extra)` aplicado al canal central de audio.

---

## 4. slide_generator_agent.py (Arquitectura TV-Grade)
* **Animación Ken Burns [RESUELTO]**:
  - Zoom dinámico y suave (`1.0` $\rightarrow$ `1.22` $\rightarrow$ `1.0`) centrado en coordenadas focales detectadas por IA (`focal_x`, `focal_y`) con control de headroom para rostros humanos.
  - Contención 100% de banners/afiches con fondo ambiental difuminado (`.photo-backdrop`) y animación continua `kenBurnsBanner` (`scale(1.0)` $\rightarrow$ `scale(1.06)`).
  - Eliminación de la desactivación por baja resolución gracias al reescalado inteligente Full HD con Lanczos en `enhance_image_ai`.
* **Lower Thirds Flotantes y Placas Centrales [RESUELTO]**:
  - Implementación fluida en 3 actos:
    1. Acto 1 (0% a 28%): Foto nítida con Ken Burns + Floating Lower Third con badge de sección (`kicker`), branding `SALADILLO VIVO` (dot LIVE pulsante) y titular de apertura.
    2. Acto 2 (28% a 72%): Retiro suave del lower third, activación de Rack Focus cinematográfico sobre la foto y entrada de la Placa Central (Citas, Cifras o Resumen).
    3. Acto 3 (72% a 100%): Retorno a nitidez fotográfica y reaparición del Lower Third con la frase de remate y progreso al 100%.
  - Modo Flash directo para notas ultra-cortas ($\le 8.5$s).
* **Audio Rioplatense y Sincronización Dual [RESUELTO]**:
  - Subida y verificación de audio en bucket `audios` de Supabase Storage mediante `upload_audio_to_supabase()`.
  - Elemento `<audio id="slideAudio">` con atributo `autoplay` y desbloqueo por interacción `{ once: true }` ante políticas restrictivas del navegador.
  - Detección de mensajes del reproductor padre (`AUDIO_TIME_UPDATE`): silencia el audio interno para impedir eco y sincroniza milimétricamente el timeline. En modo standalone/modal, el audio interno se reproduce a volumen normal.
  - Sincronización del docstring y constructor por defecto con la tecnología vigente (Voxtral TTS / Elena `voice_483`).
