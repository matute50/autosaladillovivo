# Fase 1 — Resumen Final: Fábrica de Videos Web Panel

## Estado del build
```
✓ Compiled successfully in 16.4s
```
Todos los 12+6 routes generados sin errores.

---

## Ruta del panel web
**URL:** `https://<tu-host>/studio-fabrica` (o `http://localhost:3000/studio-fabrica` en dev)

**Login:** Usar cualquier usuario existente en Supabase Auth (email + contraseña). No hay flujo de registro — acceso solo por cuenta creada manualmente desde el Dashboard de Supabase → Authentication → Users.

---

## SQL pendiente de ejecutar en Supabase

Copiar y pegar el contenido completo de:
```
docs/superpowers/specs/video-factory-schema.sql
```
en **Supabase Dashboard → SQL Editor → New Query**.

Este script:
1. Crea 4 tablas (`video_presenters`, `video_locations`, `video_weather_rules`, `video_factory_settings`)
2. Añade 12 columnas nuevas a `ara_video_jobs` (ALTER TABLE IF EXISTS)
3. Inserta seeds para Ara y Fútbol + 8 reglas climáticas de Saladillo
4. Habilita RLS con policies SELECT/INSERT/UPDATE/DELETE para cada tabla
5. Crea trigger `updated_at` automático

---

## Bucket de Storage

En **Supabase Dashboard → Storage → New Bucket**:
- Nombre: `video-factory-assets`
- Público: ✅ Sí
- Size limit: 500 MB
- MIME types: `image/*`, `video/mp4`, `video/webm`

Estructura de carpetas:
```
video-factory-assets/
├── locations/{uuid}.jpg|.mp4    ← fotos/videos de fondo
├── master-images/{job_id}.png   ← imagen maestra generada
└── final-videos/{job_id}_final.mp4  ← video renderizado
```

Ver instrucciones completas en: `docs/superpowers/specs/storage-bucket-setup.md`

---

## Archivos creados / modificados

### Base de datos
- `docs/superpowers/specs/video-factory-schema.sql` — SQL DDL completo (ejecutar en Supabase)
- `docs/superpowers/specs/storage-bucket-setup.md` — Instrucciones bucket Storage

### Types
- `src/lib/types/video-factory.ts` — Interfaces TS para las 5 entidades

### Infraestructura auth
- `src/lib/supabase/server.ts` — Cliente Supabase para Server Components
- `src/lib/supabase/middleware.ts` — Cliente Supabase para Middleware
- `src/lib/supabase/client.ts` — Cliente browser + hooks useAuth/useSupabaseClient

### Panel web (`/studio-fabrica/*`)
- `src/app/studio-fabrica/login/actions.ts` — Server actions signIn/signOut
- `src/app/studio-fabrica/login/page.tsx` — Formulario de login
- `src/app/studio-fabrica/layout.tsx` — Auth guard (redirige a login si no autenticado)
- `src/app/studio-fabrica/(fabrica)/layout.tsx` — Layout con StudioLayout wrapper
- `src/app/studio-fabrica/(fabrica)/piloto/page.tsx` — Tab Piloto Automático
- `src/app/studio-fabrica/(fabrica)/presentadores/page.tsx` — Tab Presentadores + Locaciones
- `src/app/studio-fabrica/(fabrica)/clima/page.tsx` — Tab Reglas Climáticas (tabla editable)
- `src/app/studio-fabrica/(fabrica)/inspector/page.tsx` — Tab Inspector de Prompts
- `src/components/studio/StudioLayout.tsx` — Header + navegación por tabs
- `src/components/studio/Switch.tsx` — Toggle switch reutilizable
- `src/components/studio/PilotoDashboard.tsx` — Dashboard de estado del piloto

### UI primitives
- `src/components/ui/card.tsx` — Card, CardHeader, CardTitle, CardDescription, CardContent
- `src/components/ui/forms.tsx` — Input, Label, Badge
- `src/components/ui/progress.tsx` — Barra de progreso (ya existía)

### Middleware
- `src/middleware.ts` — Agregada exclusión de `/studio-fabrica/:path*` del redirect a m.

### APIs REST
- `src/app/api/presenters/route.ts` — GET (lista), POST (crear)
- `src/app/api/presenters/[id]/route.ts` — PATCH, DELETE
- `src/app/api/locations/route.ts` — GET (con filtro presenter_id), POST
- `src/app/api/locations/[id]/route.ts` — PATCH, DELETE
- `src/app/api/weather-rules/route.ts` — GET, POST
- `src/app/api/weather-rules/[id]/route.ts` — PATCH, DELETE
- `src/app/api/factory/settings/route.ts` — GET, PATCH

### State
- `src/lib/stores/video-factory.ts` — Zustand stores para settings, presenters, locations, weather-rules

---

## Commits realizados en esta sesión
1. `ce4d412..3527dbe` — Schema SQL + tipos TS (Task 1)
2. `e51b35f..57a62bd` — Supabase SSR setup (Task 2)
3. `0d8302d` — Panel web base con auth + tabs (Task 3)
4. `375bcfb` — API REST CRUD + Zustand stores (Task 4)

---

## Tests existentes
Los 54 tests Python de pytest continúan intactos (no se modificó ningún archivo de test).
