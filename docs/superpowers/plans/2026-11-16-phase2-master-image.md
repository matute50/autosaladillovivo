# Fase 2 — Imagen Maestra desde Inspector — Plan de Implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que el botón "Regenerar imagen maestra" del Inspector genere una imagen real (Nano Banana 2 Lite) vía el worker Python y la muestre en el panel.

**Architecture:** Cola en Supabase (`ara_video_jobs`). El panel crea un job `tipo='imagen'`; el worker hace *polling*, corre `flow.py batch` con un único job de imagen, sube el PNG al bucket y actualiza estado/URL; el panel hace *polling* y muestra la imagen.

**Tech Stack:** Python 3 (worker, flow_bridge), Playwright/flow.py skill, Supabase (PostgREST + Storage), Next.js 15 + `@supabase/ssr` + `createSupabaseAdminClient`.

**Spec:** `docs/superpowers/specs/2026-11-16-phase2-master-image-design.md`

## Global Constraints
- Modelo de imagen maestra: `Nano Banana 2 Lite` (default; env `FLOW_IMAGE_MODEL`).
- Ratio `9:16`; bucket `video-factory-assets`; carpeta `master-images/`.
- `ara_video_jobs` usa la tabla real de Supabase (`otwvfihzaznyjvjtkvvd.supabase.co`).
- El panel usa `createSupabaseAdminClient()` para acceder a Supabase (patrón de `weather-rules`).
- No tocar el flujo automático de artículos del worker; solo añadir el modo imagen.

## Review Focus
1. `tipo` no puede ser `null`/invalido → migración da default `'video'` y POST fuerza `'imagen'`.
2. La URL pública de la imagen debe ser la URL de Storage `/object/public/`, no la ruta local.
3. El worker no debe procesar dos veces el mismo job (estado transicional `generando_imagen` evita re-toma).
4. Si `flow.py batch` falla, el job debe quedar en `error_reintentable` con `ultimo_error`, nunca colgarse en `pendiente`.
5. El Inspector debe poder mostrar la imagen aunque el artículo aún no tenga job previo.

---

### Task 1: Migración SQL 003 — columnas `tipo` y `master_image_url`

**Files:**
- Create: `docs/superpowers/specs/migration-003-master-image.sql` (en `ara-video-factory/migrations/`)

**Interfaces:**
- Produces: SQL a ejecutar en Supabase SQL Editor; agrega a `ara_video_jobs` `tipo TEXT NOT NULL DEFAULT 'video'` y `master_image_url TEXT`.

- [ ] **Step 1:** Escribir el archivo de migración
```sql
ALTER TABLE public.ara_video_jobs
  ADD COLUMN IF NOT EXISTS tipo TEXT NOT NULL DEFAULT 'video',
  ADD COLUMN IF NOT EXISTS master_image_url TEXT;
COMMENT ON COLUMN public.ara_video_jobs.tipo IS 'imagen | video';
COMMENT ON COLUMN public.ara_video_jobs.master_image_url IS 'URL pública en Storage de la imagen maestra';
```
- [ ] **Step 2:** Verificar que el SQL es válido (revisión manual)
- [ ] **Step 3:** Commit
```bash
git add migrations/003_add_master_image_fields.sql
git commit -m "feat(factory): migration 003 — tipo + master_image_url en ara_video_jobs"
```

---

### Task 2: `flow_bridge.py` — modelo de imagen configurable (Nano Banana 2 Lite)

**Files:**
- Modify: `src/flow_bridge.py:26-27` (añadir `IMAGE_MODEL`), `src/flow_bridge.py:97` (usarlo en `defaults`)

**Interfaces:**
- Produces: constante `IMAGE_MODEL: str` (default `"Nano Banana 2 Lite"`) usada en `generate_batch_json(...)['defaults']['image_model']`.

- [ ] **Step 1:** Añadir constante
```python
IMAGE_MODEL: str = os.environ.get("FLOW_IMAGE_MODEL", "Nano Banana 2 Lite")
```
- [ ] **Step 2:** Cambiar `"image_model": "Nano Banana Pro"` → `"image_model": IMAGE_MODEL` en `generate_batch_json`
- [ ] **Step 3:** Verificación manual: ejecutar `python src/flow_bridge.py --mode dry-run --job-id 1` y confirmar que el payload muestra `image_model: "Nano Banana 2 Lite"`
- [ ] **Step 4:** Commit
```bash
git add src/flow_bridge.py
git commit -m "feat(factory): imagen maestra usa Nano Banana 2 Lite por defecto"
```

---

### Task 3: Worker — helpers de Storage (subir PNG al bucket)

**Files:**
- Modify: `src/worker.py` (añadir `upload_to_bucket` y `public_bucket_url`)

**Interfaces:**
- Produces:
  - `upload_to_bucket(storage, bucket: str, path: str, file_bytes: bytes, content_type: str = "image/png") -> bool`
  - `public_bucket_url(bucket: str, path: str) -> str`
- Consumes: `storage.url`, `storage.get_headers(True)`.

- [ ] **Step 1:** Escribir test `tests/test_worker_storage.py` que verifique que `public_bucket_url("video-factory-assets","master-images/3.png")` devuelve `f"{storage.url}/storage/v1/object/public/video-factory-assets/master-images/3.png"` (usando un `StorageAgent` real pero solo para leer `url`).
- [ ] **Step 2:** Correr test → falla (función no existe)
- [ ] **Step 3:** Implementar `upload_to_bucket` (POST `{storage.url}/storage/v1/object/{bucket}/{path}` con headers `get_headers(False)` + `Content-Type`, body=bytes; aceptar 200/201) y `public_bucket_url` (formatear URL pública).
- [ ] **Step 4:** Correr test → pasa
- [ ] **Step 5:** Commit
```bash
git add src/worker.py tests/test_worker_storage.py
git commit -m "feat(factory): helpers de subida a Supabase Storage"
```

---

### Task 4: Worker — modo generación de imagen maestra (job `tipo='imagen'`)

**Files:**
- Modify: `src/worker.py` (nueva función `process_image_only_job`), `src/flow_bridge.py` (nuevo `generate_image_only_json`)

**Interfaces:**
- Consumes: `fetch_article(storage, article_id)`, `assemble_prompts(...)`, `get_or_create_job`, `update_job_status`, `upload_to_bucket`, `public_bucket_url`, `generate_image_only_json`, `run_live_batch`, `batch_report.json`.
- Produces:
  - `generate_image_only_json(article_id: int, prompt_imagen: str) -> dict` (payload con un solo job de imagen).
  - `process_image_only_job(storage, article_id: int, dry_run: bool) -> dict`.

- [ ] **Step 1:** Escribir test `tests/test_worker_image_only.py` que verifique que `generate_image_only_json` produce exactamente un job `type=="image"` y ninguno de video.
- [ ] **Step 2:** Correr test → falla
- [ ] **Step 3:** Implementar `generate_image_only_json` en `flow_bridge.py` (payload: `{"project": PROJECT_NAME, "defaults": {"ratio":"9:16","image_model": IMAGE_MODEL}, "jobs":[{"type":"image","name":f"img_{article_id}_frame","prompt": prompt_imagen}]}`).
- [ ] **Step 4:** Correr test → pasa
- [ ] **Step 5:** Escribir test `tests/test_worker_image_only.py` que verifique que `process_image_only_job` con un mock de `run_live_batch` que devuelve `ok` y un `batch_report.json` con un entry de imagen, llama a `upload_to_bucket` con `master-images/{job_id}.png` y setea estado `'imagen_lista'` (usar monkeypatch de `run_live_batch` y `upload_to_bucket`).
- [ ] **Step 6:** Correr test → falla
- [ ] **Step 7:** Implementar `process_image_only_job`:
  1. `article = fetch_article(storage, article_id)`; leer `ara_json`.
  2. `prompts = assemble_prompts(ara_json, ...)`; si no válido → error.
  3. `job = get_or_create_job(storage, article_id)`; `job_id = job['id']`.
  4. `update_job_status(job_id, estado="generando_imagen", prompt_imagen=prompts["prompt_imagen"], tipo="imagen")`.
  5. Si `dry_run`: leer `prompts["prompt_imagen"]` y devolver `{"ok": True, "dry_run": True, ...}` sin gastar.
  6. Escribir `batch_file`, `run_live_batch(batch_file)`; si no ok → `estado="error_reintentable"`, `ultimo_error=str(result)`.
  7. Leer `batch_report.json` del proyecto, extraer el path de salida del job de imagen.
  8. Subir PNG a `video-factory-assets/master-images/{job_id}.png`; si ok, `master_image_url=public_bucket_url(...)`.
  9. `update_job_status(job_id, estado="imagen_lista", master_image_url=..., imagen_compuesta_path=<path local>, batch_report_json=...)`.
- [ ] **Step 8:** Correr test → pasa
- [ ] **Step 9:** Commit
```bash
git add src/flow_bridge.py src/worker.py tests/test_worker_image_only.py
git commit -m "feat(factory): worker genera imagen maestra (job tipo imagen)"
```

---

### Task 5: Worker — polling de jobs `pendiente_imagen`

**Files:**
- Modify: `src/worker.py` (nueva `fetch_pending_image_jobs`, y en el loop `--poll` procesarlas)

**Interfaces:**
- Consumes: `process_image_only_job`, `wait_cooldown`.
- Produces: `fetch_pending_image_jobs(storage, limit=5) -> list[dict]` (GET `ara_video_jobs?estado=eq.pendiente_imagen&order=created_at.asc&limit=N`).

- [ ] **Step 1:** Escribir test que verifique que `fetch_pending_image_jobs` arma la query correcta (monkeypatch de `requests.get` para capturar `params['estado'] == 'eq.pendiente_imagen'`).
- [ ] **Step 2:** Correr test → falla
- [ ] **Step 3:** Implementar `fetch_pending_image_jobs` y, en `main()` bajo `--poll`, un bloque que itere los jobs devueltos y llame `process_image_only_job(storage, j['article_id'], dry_run=dry_run)` + `wait_cooldown()` en live.
- [ ] **Step 4:** Correr test → pasa
- [ ] **Step 5:** Commit
```bash
git add src/worker.py tests/test_worker_poll_image.py
git commit -m "feat(factory): worker sondea jobs de imagen pendientes"
```

---

### Task 6: Panel — rutas API `/api/jobs`

**Files:**
- Create: `src/app/api/jobs/route.ts`
- Create: `src/app/api/jobs/[id]/route.ts`

**Interfaces:**
- Consumes: `createSupabaseAdminClient()`.
- Produces:
  - `GET /api/jobs?article_id=N` → job o `{ prompts }` derivado del artículo si no existe job.
  - `POST /api/jobs` body `{ article_id, tipo }` → crea job (`estado` = `pendiente_imagen` si `tipo==='imagen'`, si no `pendiente_ensamblado`); 400 si `article_id` faltante.
  - `GET /api/jobs/[id]` → job completo (para polling).

- [ ] **Step 1:** Escribir la ruta `route.ts`:
  - GET: si `article_id` presente, query `ara_video_jobs` filter `article_id`; si existe devolver el job; si no, fetch `articles` por id y devolver `{ article, prompts: { prompt_imagen: <default>, prompt_veo: <default> } }`. Si no hay article, 404.
  - POST: insertar `{ article_id, tipo, estado: tipo==='imagen' ? 'pendiente_imagen' : 'pendiente_ensamblado' }`, `.select().single()`, devolver 201.
- [ ] **Step 2:** Escribir la ruta `[id]/route.ts`: GET por `id` → job o 404.
- [ ] **Step 3:** Verificación manual con `curl` local (el dev server ya corre en `:3000`) creando un job de prueba con `tipo='imagen'`.
- [ ] **Step 4:** Commit
```bash
git add src/app/api/jobs/route.ts src/app/api/jobs/[id]/route.ts
git commit -m "feat(factory): API de jobs para Inspector"
```

---

### Task 7: Inspector — cablear búsqueda, generar y mostrar imagen

**Files:**
- Modify: `src/app/studio-fabrica/(fabrica)/inspector/page.tsx`

**Interfaces:**
- Consumes: `GET /api/jobs?article_id=`, `POST /api/jobs`, `GET /api/jobs/[id]`.

- [ ] **Step 1:** Convertir el input en controlado (`articleId` state), "Buscar" llama `GET /api/jobs?article_id=` y guarda `{ job?, prompts?, article }`.
- [ ] **Step 2:** Si hay job con `master_image_url`, renderizar `<img src={master_image_url}>` en el panel de preview; si no, el placeholder.
- [ ] **Step 3:** "Regenerar imagen maestra" → `POST /api/jobs { article_id, tipo:'imagen' }` → guardar `job_id` → arrancar `setInterval` de 3s consultando `GET /api/jobs/[id]`; actualizar badge de estado; al llegar a `imagen_lista`, mostrar la imagen y frenar el intervalo; en `error_reintentable`/`error_fatal`, mostrar el error y frenar.
- [ ] **Step 4:** Ajustar el texto del prompt imagen a `master_image_url`-independiente (mostrar `prompts.prompt_imagen` del job si existe).
- [ ] **Step 5:** Verificación manual: hard refresh, login, abrir Inspector, buscar un artículo con `ara_json`, click "Regenerar imagen maestra", confirmar que aparece el estado y la imagen.
- [ ] **Step 6:** Commit
```bash
git add src/app/studio-fabrica/'(fabrica)'/inspector/page.tsx
git commit -m "feat(factory): Inspector genera y muestra imagen maestra"
```

---

### Task 8: Correr el worker y validar E2E (imagen real)

**Files:** (ninguno)

- [ ] **Step 1:** Verificar login Flow con `python -m src.flow_bridge --mode status` (debe dar `ok`).
- [ ] **Step 2:** Arrancar el worker en live con polling: `python src/worker.py --live --poll` (proceso background, con `notify`). Esperar y confirmar que toma el job `pendiente_imagen` y lo pasa a `imagen_lista`.
- [ ] **Step 3:** Confirmar en Supabase que `ara_video_jobs` tiene `master_image_url` público y descargable.
- [ ] **Step 4:** Confirmar en el Inspector que la imagen aparece.
- [ ] **Step 5:** Reportar resultado real con evidencia (URL de la imagen generada).

---

## Handoff de ejecución

Plan guardado en `docs/superpowers/plans/2026-11-16-phase2-master-image.md`.