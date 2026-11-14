-- ============================================================
-- VIDEO FACTORY SCHEMA - Saladillo Vivo Pro
-- Fase 1: Base de datos para el panel web /studio-fabrica
-- Ejecutar en Supabase SQL Editor
-- ============================================================

-- ============================================================
-- 1. video_presenters
-- Perfiles independientes de presentadores (Ara, Fútbol, etc.)
-- ============================================================
CREATE TABLE IF NOT EXISTS public.video_presenters (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  slug text UNIQUE NOT NULL,          -- 'ara', 'futbol'
  nombre text NOT NULL,
  flow_character_alias text,          -- ej. '@Ara', '@Futbol'
  activo boolean NOT NULL DEFAULT true,
  destino text NOT NULL CHECK (destino IN ('redes', 'vmix')),
  aspect_ratio_default text NOT NULL CHECK (aspect_ratio_default IN ('9:16', '16:9')),
  max_duracion_clip_seg integer NOT NULL DEFAULT 8,
  permite_multiclip boolean NOT NULL DEFAULT false,
  modelo_default text NOT NULL CHECK (modelo_default IN (
    'Veo 3.1 - Lite',
    'Veo 3.1 - Fast',
    'Veo 3.1 - Standard'
  )),
  variantes_default integer NOT NULL DEFAULT 1,
  usar_clima_auto boolean NOT NULL DEFAULT false,
  modo_chroma_key boolean NOT NULL DEFAULT false,
  quemar_zocalo_ffmpeg boolean NOT NULL DEFAULT true,
  voz_descripcion_fija text,
  look_modo text NOT NULL DEFAULT 'auto' CHECK (look_modo IN ('auto', 'manual')),
  look_manual_prompt text,
  default_location_id uuid REFERENCES public.video_locations(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.video_presenters IS 'Perfiles de presentadores de la fabrica de video';

-- ============================================================
-- 2. video_locations
-- Banco de fotos y videos de fondo
-- ============================================================
CREATE TABLE IF NOT EXISTS public.video_locations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  presenter_id uuid REFERENCES public.video_presenters(id) ON DELETE SET NULL,
  nombre text NOT NULL,
  tipo text NOT NULL CHECK (tipo IN ('foto_diurna', 'foto_nocturna', 'video_fondo', 'estudio_chroma')),
  storage_path text,
  public_url text,
  descripcion_ambiente_sonoro text,   -- sin musica
  activa boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.video_locations IS 'Banco de locaciones (fotos/videos) para fondos de video';

-- ============================================================
-- 3. video_weather_rules
-- Reglas editables para el motor automático de clima en Saladillo
-- ============================================================
CREATE TABLE IF NOT EXISTS public.video_weather_rules (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  temp_min numeric NOT NULL,
  temp_max numeric NOT NULL,
  condicion text NOT NULL CHECK (condicion IN ('despejado', 'nublado', 'lluvia', 'viento')),
  franja_horaria text NOT NULL CHECK (franja_horaria IN ('amanecer', 'dia', 'atardecer', 'noche')),
  vestuario_sugerido text,
  peinado_sugerido text,
  luz_prompt_sugerida text,
  override_luto_oscuro boolean NOT NULL DEFAULT false
);

COMMENT ON TABLE public.video_weather_rules IS 'Reglas automaticas de vestuario/luz segun clima/horario en Saladillo';

-- ============================================================
-- 4. video_factory_settings
-- Configuración global del piloto automático
-- ============================================================
CREATE TABLE IF NOT EXISTS public.video_factory_settings (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  piloto_automatico_activo boolean NOT NULL DEFAULT true,
  tope_diario_creditos integer NOT NULL DEFAULT 100,
  creditos_usados_hoy integer NOT NULL DEFAULT 0,
  cooldown_segundos integer NOT NULL DEFAULT 90,
  pausado_por_error boolean NOT NULL DEFAULT false,
  motivo_pausa text,
  worker_last_heartbeat_at timestamptz,
  worker_session_ok boolean
);

-- Solo una fila permitida
ALTER TABLE public.video_factory_settings
  ADD CONSTRAINT video_factory_settings_single_row CHECK (id = (SELECT id FROM public.video_factory_settings LIMIT 1));

COMMENT ON TABLE public.video_factory_settings IS 'Configuracion global del piloto automatico de la fabrica';

-- ============================================================
-- 5. Extender ara_video_jobs con columnas de fábrica
-- ============================================================
ALTER TABLE IF EXISTS public.ara_video_jobs
  ADD COLUMN IF NOT EXISTS presenter_id uuid REFERENCES public.video_presenters(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS location_id uuid REFERENCES public.video_locations(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS aspect_ratio text CHECK (aspect_ratio IN ('9:16', '16:9')),
  ADD COLUMN IF NOT EXISTS modelo_video text CHECK (modelo_video IN ('Veo 3.1 - Lite', 'Veo 3.1 - Fast', 'Veo 3.1 - Standard')),
  ADD COLUMN IF NOT EXISTS variantes integer DEFAULT 1 CHECK (variantes >= 1 AND variantes <= 4),
  ADD COLUMN IF NOT EXISTS modo_chroma boolean DEFAULT false,
  ADD COLUMN IF NOT EXISTS clima_snapshot_json jsonb,
  ADD COLUMN IF NOT EXISTS look_override_text text,
  ADD COLUMN IF NOT EXISTS imagen_maestra_url text,
  ADD COLUMN IF NOT EXISTS video_final_url text,
  ADD COLUMN IF NOT EXISTS bloques_override_json jsonb,
  ADD COLUMN IF NOT EXISTS creditos_estimados integer;

COMMENT ON COLUMN public.ara_video_jobs.presenter_id IS 'Presentador asignado a este job';
COMMENT ON COLUMN public.ara_video_jobs.location_id IS 'Locacion de fondo seleccionada';
COMMENT ON COLUMN public.ara_video_jobs.clima_snapshot_json IS 'Foto congelada de temperatura/hora/cielo de Saladillo';
COMMENT ON COLUMN public.ara_video_jobs.bloques_override_json IS 'Overrides por bloque de texto de 8s';

-- ============================================================
-- 6. SEED DATA
-- ============================================================

-- Presentadores semilla
INSERT INTO public.video_presenters (slug, nombre, flow_character_alias, destino, aspect_ratio_default,
  permite_multiclip, modelo_default, variantes_default, usar_clima_auto, modo_chroma_key,
  quemar_zocalo_ffmpeg, voz_descripcion_fija, look_modo, look_manual_prompt)
VALUES
  ('ara', 'Ara', '@Ara', 'redes', '9:16', true, 'Veo 3.1 - Lite', 1, true, false, true,
   'Mujer joven, tez clara, cabello negro largo recogido en cola baja, blazer azul marino sobre blusa blanca, maquillaje natural y profesional, acento rioplatense porteño suave, expresión cercana y expresiva',
   'auto', NULL),
  ('futbol', 'Presentador Fútbol', '@Futbol', 'vmix', '16:9', false, 'Veo 3.1 - Lite', 1, false, true, false,
   'Hombre adulto, traje formal oscuro, camisa blanca, corbata azul, acento rioplatense neutro, expresión seria y profesional',
   'auto', NULL)
ON CONFLICT (slug) DO NOTHING;

-- Reglas de clima semilla (Saladillo, Buenos Aires)
INSERT INTO public.video_weather_rules (temp_min, temp_max, condicion, franja_horaria,
  vestuario_sugerido, peinado_sugerido, luz_prompt_sugerida, override_luto_oscuro)
VALUES
  (0, 12, 'despejado', 'amanecer', 'Abrigo ligero claro, bufanda neutra', 'Cabello recogido', 'Luz suave dorada temprana, dirección lateral izquierda', false),
  (12, 22, 'despejado', 'dia', 'Blazer claro o camisa ligera', 'Cabello suelto o medio recogido', 'Luz natural frontal difusa, rebote suave', false),
  (22, 35, 'despejado', 'dia', 'Camisa fresca, colores claros', 'Cabello recogido para mayor frescura', 'Luz natural moderada, evitar sobreexposición', false),
  (0, 25, 'nublado', 'dia', 'Capa media, colores tierra', 'Sin cambios especiales', 'Luz difusa uniforme, ideal para retrato', false),
  (0, 35, 'lluvia', 'dia', 'Abrigo impermeable oscuro, sombrero si es necesario', 'Cabello protegido del agua', 'Luz grisácea difusa, ambiente tenso', true),
  (0, 35, 'viento', 'dia', 'Prenda ajustada, capa ligera', 'Cabello sujeto firmemente', 'Luz natural, sombras movidas por viento', false),
  (0, 15, 'despejado', 'noche', 'Abrigo oscuro formal', 'Cabello recogido', 'Iluminación artificial cálida, contraste medio', false),
  (15, 35, 'despejado', 'atardecer', 'Tonos cálidos, textura ligera', 'Libre o recogido bajo', 'Luz dorada lateral, silhouette suave', false)
ON CONFLICT DO NOTHING;

-- Config global del piloto automático
INSERT INTO public.video_factory_settings (
  piloto_automatico_activo, tope_diario_creditos, creditos_usados_hoy,
  cooldown_segundos, pausado_por_error, worker_last_heartbeat_at, worker_session_ok
) VALUES (true, 100, 0, 90, false, NULL, NULL)
ON CONFLICT DO NOTHING;

-- ============================================================
-- 7. RLS POLICIES
-- ============================================================
ALTER TABLE public.video_presenters ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.video_locations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.video_weather_rules ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.video_factory_settings ENABLE ROW LEVEL SECURITY;

-- video_presenters policies
CREATE POLICY "Authenticated read video_presenters" ON public.video_presenters
  FOR SELECT TO authenticated USING (true);
CREATE POLICY "Authenticated insert video_presenters" ON public.video_presenters
  FOR INSERT TO authenticated WITH CHECK (true);
CREATE POLICY "Authenticated update video_presenters" ON public.video_presenters
  FOR UPDATE TO authenticated USING (true) WITH CHECK (true);
CREATE POLICY "Authenticated delete video_presenters" ON public.video_presenters
  FOR DELETE TO authenticated USING (true);

-- video_locations policies
CREATE POLICY "Authenticated read video_locations" ON public.video_locations
  FOR SELECT TO authenticated USING (true);
CREATE POLICY "Authenticated insert video_locations" ON public.video_locations
  FOR INSERT TO authenticated WITH CHECK (true);
CREATE POLICY "Authenticated update video_locations" ON public.video_locations
  FOR UPDATE TO authenticated USING (true) WITH CHECK (true);
CREATE POLICY "Authenticated delete video_locations" ON public.video_locations
  FOR DELETE TO authenticated USING (true);

-- video_weather_rules policies
CREATE POLICY "Authenticated read video_weather_rules" ON public.video_weather_rules
  FOR SELECT TO authenticated USING (true);
CREATE POLICY "Authenticated insert video_weather_rules" ON public.video_weather_rules
  FOR INSERT TO authenticated WITH CHECK (true);
CREATE POLICY "Authenticated update video_weather_rules" ON public.video_weather_rules
  FOR UPDATE TO authenticated USING (true) WITH CHECK (true);
CREATE POLICY "Authenticated delete video_weather_rules" ON public.video_weather_rules
  FOR DELETE TO authenticated USING (true);

-- video_factory_settings policies (solo lectura/escritura para usuario autenticado)
CREATE POLICY "Authenticated read video_factory_settings" ON public.video_factory_settings
  FOR SELECT TO authenticated USING (true);
CREATE POLICY "Authenticated update video_factory_settings" ON public.video_factory_settings
  FOR UPDATE TO authenticated USING (true) WITH CHECK (true);

-- ============================================================
-- 8. TRIGGER para actualizar updated_at en video_presenters
-- ============================================================
CREATE OR REPLACE FUNCTION public.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_video_presenters_updated_at
  BEFORE UPDATE ON public.video_presenters
  FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();
