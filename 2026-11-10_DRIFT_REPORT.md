# Reporte de Auditoría Técnica de Desviación de Especificaciones (EGM Drift Report)

**Auditor:** EGM Technical Quality Auditor (`egm-codebase-details`)  
**Modo:** REVIEW  
**Estado General:** ✅ **0% DRIFT (100% de Alineación Técnica con las Especificaciones)**  
**Fecha de Inspección:** 10 de Noviembre de 2026  

---

## 1. Resumen Ejecutivo por Módulo

| Módulo Auditado | Archivos Analizados | Alineación | Estado |
| :--- | :--- | :---: | :---: |
| **Pipeline de Audio y Locución TTS** | [`agents/audio_generator_agent.py`](agents/audio_generator_agent.py)<br>[`agents/ai_rewriter_agent.py`](agents/ai_rewriter_agent.py)<br>[`scripts/regenerate_recent_audio.py`](scripts/regenerate_recent_audio.py) | **100%** | Conforme |
| **Glosario Centralizado** | [`utils/glossary_manager.py`](utils/glossary_manager.py)<br>[`scripts/manage_glossary.py`](scripts/manage_glossary.py)<br>[`data/glossary.json`](data/glossary.json) | **100%** | Conforme |
| **Frontend de Presentación de Noticias** | [`src/components/NewsCard.tsx`](src/components/NewsCard.tsx)<br>[`src/lib/utils.ts`](src/lib/utils.ts)<br>[`src/components/layout/ExclusiveVideoCarousel.tsx`](src/components/layout/ExclusiveVideoCarousel.tsx) | **100%** | Conforme |
| **Pipeline de Slides y Reproductor TV-Grade** | [`agents/slide_generator_agent.py`](agents/slide_generator_agent.py)<br>[`src/components/layout/VideoSection.tsx`](src/components/layout/VideoSection.tsx) | **100%** | Conforme |

---

## 2. Auditoría Detallada de Requerimientos

### Requerimiento A: Lectura completa del cuerpo de la noticia antes de la frase institucional
- **Implementación en Código**:
  - En `agents/audio_generator_agent.py` (`process_article_audio`), el cuerpo completo de la noticia (`clean_text`) y el título se unifican mediante `body_speech = ". ".join(body_parts)`.
  - La síntesis continua unifica el relato y la promo institucional (`combined_speech = f"{body_speech} {closing_text}"`). En la función `_find_seam_silence`, se evalúa la duración de la promo (entre 1.3s y 5.0s) y se selecciona estrictamente el *último* silencio antes de la promo (`last_gap = gaps[-1]`), garantizando que la totalidad de las oraciones del cuerpo se preserven intactas antes del splice del silencio de 1,000 ms.
  - En `src/components/layout/VideoSection.tsx`, se eliminó el fade-out prematuro cuando existe audio conocido (`hasKnownAudio ? null : setTimeout(...)`), impidiendo que se atenúe o corte la última sílaba de la frase institucional. Asimismo, el slide se cierra de forma determinista mediante el evento `onEnded` de la etiqueta `<audio>` centralizada.
- **Resultado**: ✅ Cumplimiento total. Cero truncamiento de audio o silenciamiento prematuro.

---

### Requerimiento B: Preservación íntegra de oraciones (eliminación de `.split()[:105]` y frases truncas)
- **Implementación en Código**:
  - En `agents/ai_rewriter_agent.py`, se implementó el método `_condense_body_cleanly`:
    1. Segmenta el texto respetando los límites oracionales sintácticos (`re.split(r'(?<=[.!?])\s+', full_text)`).
    2. Acumula oraciones completas hasta alcanzar una extensión periodística balanceada (80 a 115 palabras).
    3. Descarta oraciones huérfanas si el texto fuente original carecía de punto final.
    4. Implementa una guarda activa contra conectores o verbos declarativos colgantes (`dangling_endings = ('que', 'y', 'de', 'informó', 'dijo', 'afirmó', 'aseguró', 'señaló', 'manifestó', 'destacó', 'agregó', ...)`), removiéndolos y forzando cierre oracional con punto.
  - En `scripts/regenerate_recent_audio.py`, la regeneración utiliza directamente `rewriter._condense_body_cleanly(raw_text, target_words=105)` antes de la locución y generación de slides, parcheando también el texto corregido en Supabase (`patch["text"] = text`).
- **Resultado**: ✅ Cumplimiento total. Eliminación completa de cortes arbitrarios por número ciego de palabras.

---

### Requerimiento C: Visualización de títulos de noticias completos en la Home (sin recorte a 8 palabras)
- **Implementación en Código**:
  - En `src/lib/utils.ts`, la función `cleanTitle` realiza una sanitización ortotipográfica (remoción de comillas tipográficas, dobles, diéresis erróneas y pipes), pero **no** aplica ningún corte o limitación de palabras (`.slice()` o `.split()`).
  - En `src/components/NewsCard.tsx`, se utiliza `cleanFull(rawTitle) || cleanFull(ganchoImagen)`, desplegando el título completo. La contención estética se delega a `line-clamp-3` y al sistema de tipografía responsiva fluida (`getResponsiveTypography` con unidades de contenedor `cqw` y `clamp`), asegurando legibilidad sin amputar frases.
  - En `src/components/layout/ExclusiveVideoCarousel.tsx`, el título `video.nombre` se muestra íntegro utilizando `line-clamp-2` y tamaño tipográfico adaptativo.
- **Resultado**: ✅ Cumplimiento total. Se erradicó el recorte artificial de 8 palabras en toda la presentación visual.

---

### Requerimiento D: Consulta obligatoria y aplicación del glosario en redacción y audio
- **Implementación en Código**:
  - **Glosario Centralizado**: `utils/glossary_manager.py` administra `data/glossary.json` con separación estricta en 3 categorías (`redaccion`, `audio`, `ambos`), soporte de recarga en caliente por mtime (`_maybe_reload`) y ordenamiento por longitud descendente para dar prioridad a términos compuestos sobre simples.
  - **Pipeline de Redacción**: `agents/ai_rewriter_agent.py` ejecuta obligatoriamente `apply_text_glossary` sobre `titulo_radial`, `titulo_gancho_imagen`, `contenido_optimizado`, `meta_description`, y sobre todos los campos de `slide_visuals` (`titular_apertura`, `remate`, `destacado`, `bajada`).
  - **Pipeline de Audio TTS**: `agents/audio_generator_agent.py` invoca `apply_audio_glossary` dentro de `clean_text_for_speech`, procesando título y cuerpo antes de la síntesis vocal (reemplazando siglas como `CES` por `C-E-S`, `HCD` por `Ache-Ce-De`, `Cicaré` por `Sicaré`, etc.).
  - **Gestión CLI y Especificación**: `scripts/manage_glossary.py` y `data/glossary.json` coinciden plenamente con la especificación `.hermes/skills/glossary-management/SKILL.md`.
- **Resultado**: ✅ Cumplimiento total.

---

## 3. Verificación de Arquitectura TV-Grade y Skills de Video
- **Smart Slot System (v18.0)**: Verificado en `src/components/layout/VideoSection.tsx`, con Slots A y B permanentemente montados en el DOM (`opacity-100`, conmutación por `z-index` y `pointer-events`) evitando recargas y parpadeos.
- **Node Persistence de Intro (v16.0 / v23.0)**: Elemento `<video>` único en capa superior `z-[999]` con watchdog de seguridad a 20s para prevenir bloqueos de autoplay.
- **Cinematic Shield & Anti-Branding**: Verificado en `src/components/layout/VideoSection.tsx` con `scale(1.20)` durante 5 segundos y barras superior/inferior al 14% sólido y 35% degradé.
- **Slides Ken Burns de 3 Actos**: Verificado en `agents/slide_generator_agent.py` con 2 ciclos completos de zoom sincronizados a `--slide-audio-duration`.

---

## 4. Dictamen Final
Se certifica que el código fuente en todos los módulos auditados se encuentra en **estricto cumplimiento y paridad al 100%** con los requerimientos editoriales, fonéticos y audiovisuales definidos. **Drift: 0%**.
