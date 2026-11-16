# Video Factory Frontend Phase 1 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a mobile-first, Supabase-auth-protected web panel at `/studio-fabrica` inside the existing Next.js 15 App Router project to operate the Video Factory (Ara + Fútbol presenters) from any device.

**Architecture:** Next.js 15 App Router + Server Components + Server Actions + `@supabase/ssr` for auth. RLS policies in Supabase. shadcn/ui (Radix) for components. Zustand for client state. 4 tabs: Piloto/Cola/Salud, Perfiles/Locaciones, Reglas Clima, Inspector/Preview.

**Tech Stack:** Next.js 15, React 19, TypeScript, Tailwind CSS, @supabase/ssr, @supabase/supabase-js, Radix UI (Dialog, Tabs, Select, Switch, Progress, Slider, Toast), lucide-react, zustand, clsx, tailwind-merge.

**Spec:** This plan implements the requirements from the user's Phase 1 specification (auditoría repo, esquema Supabase, 4 vistas, validación técnica).

## Global Constraints

1. **NO modificar/committar/descartar** los 3 archivos locales pendientes: `data/glossary.json`, `saladillo_tts_preprocessor.py`, `utils/ssml_builder.py`
2. **NO ejecutar `git push`** — solo commits locales
3. **NO romper** las 12 páginas actuales de Next.js ni los 54 tests Python existentes
4. **NO ejecutar Google Flow** ni consumir créditos — solo UI + DB + APIs
5. **Mobile-first responsive**: breakpoints `sm` (640px) y `lg` (1024px) only
6. **Paleta CSS existente**: usar variables `--primary`, `--destructive`, `--muted`, `--accent`, `--card`, `--background` de `globals.css`
7. **Build debe pasar**: `npm run build` sin errores nuevos; `npm run lint` sin warnings nuevos en archivos tocados
8. **Tests Python intactos**: 54/54 passing after changes
9. **Auth**: email/password con usuarios ya existentes en Supabase Auth (no signup público)
10. **Middleware**: excluir `/studio-fabrica` del redirect a subdominio `m.`

## Review Focus

| Input / Condition | Expected Behavior | Owner Task |
|-------------------|-------------------|------------|
| Usuario sin sesión accede a `/studio-fabrica` | Redirect a `/studio-fabrica/login` con `next` param | Task 3 |
| Usuario con sesión expirada (cookie stale) | Refresh automático via `@supabase/ssr` o redirect limpio | Task 3 |
| Worker heartbeat > 90s sin actualizar | Badge rojo "Worker desconectado" en barra superior | Task 5 |
| Créditos usados ≥ tope diario | Piloto automático se pausa solo; badge ámbar "Tope alcanzado" | Task 5 |
| Nota con `requiere_aprobacion_sensible=true` | Queda en bandeja "Aprobación Sensible" aunque piloto ON | Task 5 |
| Modo chroma activado en perfil Fútbol | Validador bloquea color verde en vestuario; zócalo FFmpeg off | Task 7 |
| Variante count 2-4 en Inspector | Calculadora muestra `costo × bloques × variantes` con warning visible | Task 10 |
| Imagen maestra generada (URL) | Preview muestra overlay zona segura 20% inferior (no-chroma) | Task 10 |

---

### Task 1: Supabase Schema + Storage Bucket (SQL File)

**Files:**
- Create: `docs/superpowers/specs/video-factory-schema.sql`
- Create: `docs/superpowers/specs/storage-bucket-setup.md`

**Interfaces:**
- Produces: SQL DDL for 5 tables + RLS policies + bucket config; types for TypeScript

- [ ] **Step 1.1: Write SQL for `public.video_presenters`**
- [ ] **Step 1.2: Write SQL for `public.video_locations`**
- [ ] **Step 1.3: Write SQL for `public.video_weather_rules`**
- [ ] **Step 1.4: Write SQL for `public.video_factory_settings`**
- [ ] **Step 1.5: Write SQL for `ALTER TABLE public.ara_video_jobs` (extension columns)**
- [ ] **Step 1.6: Write RLS policies for all tables (service_role bypass, anon read where needed)**
- [ ] **Step 1.7: Document Storage bucket `video-factory-assets` with folders: `locations/`, `master-images/`, `final-videos/`**
- [ ] **Step 1.8: Generate TypeScript types from SQL → `src/lib/types/video-factory.ts`**

**Verification:**
```bash
# Manual: paste SQL into Supabase SQL Editor → Run
# Verify: SELECT * FROM public.video_presenters; should return seed rows
# Verify: bucket exists in Supabase Dashboard → Storage
```

---

### Task 2: Install Dependencies + Supabase SSR Setup

**Files:**
- Modify: `package.json` (add `@supabase/ssr`)
- Create: `src/lib/supabase/server.ts` (Server Component client)
- Create: `src/lib/supabase/middleware.ts` (Middleware client)
- Create: `src/lib/supabase/client.ts` (Client Component client — browser only)

**Interfaces:**
- Consumes: existing `src/lib/supabaseClient.ts` (anon client for public reads)
- Produces: 3 typed Supabase clients for RSC, Middleware, Client Components

- [ ] **Step 2.1: `npm install @supabase/ssr@latest`**
- [ ] **Step 2.2: Create `src/lib/supabase/server.ts` with `createServerClient` using `cookies()` from `next/headers`**
- [ ] **Step 2.3: Create `src/lib/supabase/middleware.ts` with `createServerClient` for middleware**
- [ ] **Step 2.4: Create `src/lib/supabase/client.ts` with `createBrowserClient` (lazy singleton)**
- [ ] **Step 2.5: Verify types export from each**

**Verification:**
```bash
npm run typecheck 2>&1 | head -30  # Should pass (or only pre-existing errors)
```

---

### Task 3: Auth Guard + Login Page + Middleware Exclusion

**Files:**
- Create: `src/app/studio-fabrica/layout.tsx` (Server Component — auth check)
- Create: `src/app/studio-fabrica/login/page.tsx` (Client Component — signin form)
- Create: `src/app/studio-fabrica/login/actions.ts` (Server Action: `signIn`)
- Modify: `src/middleware.ts` (add `/studio-fabrica` exclusion from mobile redirect)
- Create: `src/components/auth/AuthGuard.tsx` (reusable client guard for nested routes)

**Interfaces:**
- Consumes: `src/lib/supabase/server.ts`, `src/lib/supabase/client.ts`
- Produces: Protected route tree under `/studio-fabrica/*`

- [ ] **Step 3.1: Update `src/middleware.ts` — add `/studio-fabrica` to matcher exclusion**
- [ ] **Step 3.2: Write failing test for middleware exclusion (optional — manual verify)**
- [ ] **Step 3.3: Create `src/app/studio-fabrica/login/actions.ts` with `signIn(formData)` Server Action**
- [ ] **Step 3.4: Create `src/app/studio-fabrica/login/page.tsx` — email/password form, `useActionState`, toast on error, redirect on success**
- [ ] **Step 3.5: Create `src/app/studio-fabrica/layout.tsx` — `getUser()` via server client; if null → redirect to `/studio-fabrica/login?next=...`**
- [ ] **Step 3.6: Create `src/components/auth/AuthGuard.tsx` for Client Components needing session**
- [ ] **Step 3.7: Test manually: visit `/studio-fabrica` → login → access granted**

**Verification:**
```bash
npm run dev  # Visit http://localhost:3000/studio-fabrica → should redirect to login
# Login with existing Supabase Auth user → should land on /studio-fabrica (tabs shell)
```

---

### Task 4: Main Shell — Tabs Layout + Navigation + Shared Stores

**Files:**
- Create: `src/app/studio-fabrica/page.tsx` (Server Component — renders tabs shell)
- Create: `src/components/video-factory/StudioTabs.tsx` (Client Component — Tabs + TabContent)
- Create: `src/store/useVideoFactoryStore.ts` (Zustand: activeTab, presenter filter, job filters)
- Create: `src/store/useAuthStore.ts` (Zustand: user, signOut action)
- Create: `src/components/video-factory/TopBar.tsx` (Client: user avatar, signOut, pilot master switch — reads from settings)

**Interfaces:**
- Consumes: `src/lib/supabase/client.ts`, `useAuthStore`, `useVideoFactoryStore`
- Produces: Layout with 4 tabs: `piloto`, `perfiles`, `clima`, `inspector`

- [ ] **Step 4.1: Create `useAuthStore` with `user`, `setUser`, `signOut` (calls Supabase auth.signOut)**
- [ ] **Step 4.2: Create `useVideoFactoryStore` with `activeTab`, `setActiveTab`, `presenterFilter`, `jobFilters`**
- [ ] **Step 4.3: Create `TopBar.tsx` — reads `video_factory_settings` via Server Action, shows pilot toggle, worker health, credit bar**
- [ ] **Step 4.4: Create `StudioTabs.tsx` — shadcn Tabs with 4 TabTriggers, lazy-load TabContent per tab**
- [ ] **Step 4.5: Create `src/app/studio-fabrica/page.tsx` — Server Component fetches `video_factory_settings`, passes to `TopBar` and `StudioTabs`**

**Verification:**
```bash
npm run dev → /studio-fabrica → 4 tabs render, TopBar shows settings, signOut works
```

---

### Task 5: Tab 1 — Piloto Automático, Cola y Salud (Core Dashboard)

**Files:**
- Create: `src/components/video-factory/tabs/PilotoTab.tsx` (Client — main dashboard)
- Create: `src/components/video-factory/PilotStatusBar.tsx` (Client — live status bar)
- Create: `src/components/video-factory/SensitiveApprovalQueue.tsx` (Client — cards for `requiere_aprobacion_sensible`)
- Create: `src/components/video-factory/JobQueue.tsx` (Client — filterable job cards)
- Create: `src/components/video-factory/JobCard.tsx` (Client — master image, clip progress, video player, retry)
- Create: `src/actions/video-factory/pilot.ts` (Server Actions: `togglePilot`, `approveSensitiveJob`, `rejectSensitiveJob`, `retryJob`, `retryJobBlock`)

**Interfaces:**
- Consumes: `useVideoFactoryStore` (filters), `pilot.ts` actions, `ara_video_jobs` + `articles` joins
- Produces: Real-time-ish dashboard (SW polling or manual refresh)

- [ ] **Step 5.1: Write Server Actions in `actions/video-factory/pilot.ts`**
- [ ] **Step 5.2: Create `PilotStatusBar.tsx` — pilot toggle (optimistic UI), worker heartbeat badge, credit progress bar**
- [ ] **Step 5.3: Create `SensitiveApprovalQueue.tsx` — fetches jobs with `requiere_aprobacion_sensible=true` + `status=pending_approval`; shows tenor, blocks, zócalo, clima snapshot; big ✅/❌ buttons**
- [ ] **Step 5.4: Create `JobCard.tsx` — displays master image (if URL), clip badges (1/2, 2/2), video player (HTML5 `<video>`), retry button per block**
- [ ] **Step 5.5: Create `JobQueue.tsx` — filter chips (Ara/Fútbol, status), maps to `JobCard` list**
- [ ] **Step 5.6: Compose `PilotoTab.tsx` — status bar + sensitive queue (priority) + job queue**
- [ ] **Step 5.7: Add SWR-style polling (30s) or manual refresh button for live feel**

**Verification:**
```bash
# In Supabase: insert test rows in ara_video_jobs with various statuses + sensitive flag
# Visit /studio-fabrica → Piloto tab → all sections render, actions work
```

---

### Task 6: Tab 2 — Perfiles de Presentadores + Galería de Locaciones

**Files:**
- Create: `src/components/video-factory/tabs/PerfilesTab.tsx`
- Create: `src/components/video-factory/PresenterForm.tsx` (Client — full form per presenter)
- Create: `src/components/video-factory/LocationsGallery.tsx` (Client — upload + grid)
- Create: `src/components/video-factory/LocationUploader.tsx` (Client — drag-drop → Supabase Storage)
- Create: `src/actions/video-factory/presenters.ts` (Server Actions: CRUD presenters, locations, upload signed URLs)

**Interfaces:**
- Consumes: `presenters.ts` actions, `video_presenters`, `video_locations`, Storage bucket
- Produces: Editable presenter cards + location grid with upload

- [ ] **Step 6.1: Write Server Actions in `actions/video-factory/presenters.ts`**
- [ ] **Step 6.2: Create `PresenterForm.tsx` — two modes (Ara / Fútbol) with all fields: alias, voz_descripcion_fija, look_modo, look_manual_prompt, modelo_default, variantes_default, aspect_ratio_default, max_duracion_clip_seg, permite_multiclip, destino, modo_chroma_key, quemar_zocalo_ffmpeg, usar_clima_auto, default_location_id**
- [ ] **Step 6.3: Create `LocationUploader.tsx` — drag-drop, tipo select, descripcion_ambiente_sonoro (validate no "música"), upload to `video-factory-assets/locations/` via signed URL**
- [ ] **Step 6.4: Create `LocationsGallery.tsx` — grid of cards with thumbnail, tipo badge, active toggle, delete**
- [ ] **Step 6.4: Compose `PerfilesTab.tsx` — presenter selector (tabs Ara/Fútbol) + form + locations gallery**

**Verification:**
```bash
# Edit Ara presenter → change modelo_default → save → verify in Supabase
# Upload location photo → appears in gallery → public_url accessible
# Toggle modo_chroma_key on Fútbol → validates green blocking in Inspector (Task 10)
```

---

### Task 7: Tab 3 — Reglas Automáticas de Clima (Saladillo)

**Files:**
- Create: `src/components/video-factory/tabs/ClimaTab.tsx`
- Create: `src/components/video-factory/WeatherRulesTable.tsx` (Client — editable table)
- Create: `src/actions/video-factory/weather-rules.ts` (Server Actions: CRUD weather rules)

**Interfaces:**
- Consumes: `weather-rules.ts` actions, `video_weather_rules`
- Produces: Editable rule rows with inline save

- [ ] **Step 7.1: Write Server Actions in `actions/video-factory/weather-rules.ts`**
- [ ] **Step 7.2: Create `WeatherRulesTable.tsx` — TanStack Table or native `<table>` with inline editing: temp_min, temp_max, condicion, franja_horaria, vestuario_sugerido, peinado_sugerido, luz_prompt_sugerida, override_luto_oscuro**
- [ ] **Step 7.3: Add seed notice banner: "En notas sensibles se impone paleta sobria/oscura"**
- [ ] **Step 7.4: Compose `ClimaTab.tsx` — table + add rule button + save all**

**Verification:**
```bash
# Add rule: temp 15-22, despejado, dia → vestuario "blazer claro", luz "natural frontal"
# Verify in Supabase table
```

---

### Task 8: Tab 4 — Inspector y Previsualizador por Noticia

**Files:**
- Create: `src/components/video-factory/tabs/InspectorTab.tsx`
- Create: `src/components/video-factory/InspectorLayout.tsx` (Client — two-pane: controls | preview)
- Create: `src/components/video-factory/InspectorControls.tsx` (Client — left pane: all overrides)
- Create: `src/components/video-factory/InspectorPreview.tsx` (Client — right pane: master image + safe zone overlay + prompt inspector)
- Create: `src/components/video-factory/PromptInspector.tsx` (Client — shows master prompt + per-block video prompts)
- Create: `src/components/video-factory/ValidationSemaphore.tsx` (Client — word count, smile block, green block, credit calc)
- Create: `src/actions/video-factory/inspector.ts` (Server Actions: `saveJobOverrides`, `regenerateMasterImage`, `rerenderVideo`)

**Interfaces:**
- Consumes: `inspector.ts` actions, `ara_video_jobs` + joined `articles` + `video_presenters` + `video_locations`
- Produces: Full per-job override editor with live validation

- [ ] **Step 8.1: Write Server Actions in `actions/video-factory/inspector.ts`**
- [ ] **Step 8.2: Create `InspectorControls.tsx` — presenter override select, location picker (photo/video), vestuario/peinado/maquillaje (Auto/A gusto + text), clima/luz (Auto/Manual), per-block textareas (volanta, zócalo, bloque 1, bloque 2...), modelo + variantes select**
- [ ] **Step 8.3: Create `ValidationSemaphore.tsx` — word count per block (green <120, red ≥120), smile word detection if `permitir_sonrisa=false`, green color detection if `modo_chroma_key=true`, credit calculator (`modelo_cost × blocks × variantes`)**
- [ ] **Step 8.4: Create `PromptInspector.tsx` — two panels: "Prompt Imagen Maestra" (absorbe ropa, peinado, maquillaje, luz, clima) + "Prompts Video por Bloque" (each with `[El personaje dice "..."]` + `[Fondo: ...]`)**
- [ ] **Step 8.5: Create `InspectorPreview.tsx` — master image `<img>` + overlay `div` (20% bottom, semi-transparent red) when NOT modo_chroma; shows "Zona Segura — Zócalo cubre marca de agua"**
- [ ] **Step 8.6: Compose `InspectorLayout.tsx` — responsive: stacked on mobile (`lg:grid-cols-2`), side-by-side on desktop**
- [ ] **Step 8.7: Compose `InspectorTab.tsx` — job selector (dropdown from queue) + `InspectorLayout`**

**Verification:**
```bash
# Select a job → edit block 1 text → word count turns red at 120
# Toggle modo_chroma → green color validation activates
# Change variantes 1→3 → credit calc updates with warning
# Click "Regenerar imagen maestra" → calls action, shows loading
```

---

### Task 9: Shared UI Components + Utilities

**Files:**
- Create: `src/components/ui/video-factory/*` (specialized: `CreditBadge.tsx`, `StatusBadge.tsx`, `ClipProgress.tsx`, `VideoPlayer.tsx`, `SafeZoneOverlay.tsx`)
- Create: `src/lib/video-factory/utils.ts` (credit costs per model, validation helpers, prompt builders)
- Create: `src/lib/video-factory/constants.ts` (model costs, aspect ratios, tenor values, clima conditions)

**Interfaces:**
- Consumed by: Tasks 5-8

- [ ] **Step 9.1: Create constants: `MODEL_CREDITS = { 'Veo 3.1 - Lite': 1, 'Veo 3.1 - Fast': 2, 'Veo 3.1 - Standard': 4 }`**
- [ ] **Step 9.2: Create `buildMasterPrompt()`, `buildVideoPrompt(block)` in `utils.ts`**
- [ ] **Step 9.3: Create `validateBlockText(text, permitirSonrisa, modoChroma)` → `{ wordCount, smileViolation, greenViolation }`**
- [ ] **Step 9.4: Create shared UI components with shadcn patterns**

**Verification:**
```bash
npm run typecheck  # All new types resolve
```

---

### Task 10: TypeScript Types Generation + Integration Test

**Files:**
- Modify: `src/lib/types/video-factory.ts` (generated from SQL in Task 1.8)
- Modify: `src/lib/types/index.ts` (re-export)
- Run: Full build + lint

**Interfaces:**
- Consumes: All previous tasks
- Produces: Compile-time safety across the panel

- [ ] **Step 10.1: Generate/Write `video-factory.ts` with all table Row/Insert/Update types**
- [ ] **Step 10.2: Run `npm run build` — must pass (ignoreBuildErrors=true but no NEW errors)**
- [ ] **Step 10.3: Run `npm run lint` — no NEW warnings in touched files**
- [ ] **Step 10.4: Run Python tests: `cd /home/matias/saladillo-vivo-pro && python -m pytest tests/ -v` — 54/54 pass**

**Verification:**
```bash
npm run build 2>&1 | tail -30
npm run lint 2>&1 | grep -E "(video-factory|studio-fabrica)" || echo "No new lint warnings"
cd /home/matias/saladillo-vivo-pro && python -m pytest tests/ -v --tb=short 2>&1 | tail -20
```

---

### Task 11: Documentation + Handoff

**Files:**
- Create: `docs/superpowers/specs/VIDEO_FACTORY_FRONTEND_PHASE1.md` (user-facing spec)
- Create: `docs/superpowers/specs/SUPABASE_SETUP_INSTRUCTIONS.md` (SQL + bucket steps)

**Interfaces:**
- Consumes: All tasks
- Produces: Docs for user to apply SQL and verify

- [ ] **Step 11.1: Write user-facing spec with screenshots (text sketches) of 4 tabs**
- [ ] **Step 11.2: Write Supabase setup instructions (SQL file path, bucket name, RLS note)**
- [ ] **Step 11.3: Summary of files created/modified + build confirmation**

---

## Execution Handoff

**Plan complete and saved to** `docs/superpowers/plans/2026-11-14-video-factory-frontend-phase1.md`.

**Recommended execution approach: Subagent-driven** — because:
- 11 tasks with clear interfaces between them
- Each task produces independently testable deliverable
- Reviewer gate after each task catches integration issues early
- Spec is large enough that fresh context per task pays off

**Alternative: Native** — if you prefer single-session implementation with one final review.

**Please confirm:** Does the plan capture what you want, and which approach should we use?