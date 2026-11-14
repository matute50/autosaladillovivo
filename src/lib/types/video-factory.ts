/**
 * Tipos TypeScript para la Fábrica de Videos — Fase 1
 * Generados a partir de docs/superpowers/specs/video-factory-schema.sql
 */

// ============================================================
// VideoPresenter
// ============================================================
export type PresenterSlug = 'ara' | 'futbol';
export type PresenterDestino = 'redes' | 'vmix';
export type PresenterAspectRatio = '9:16' | '16:9';
export type PresenterModelo = 'Veo 3.1 - Lite' | 'Veo 3.1 - Fast' | 'Veo 3.1 - Standard';
export type PresenterLookModo = 'auto' | 'manual';

export interface VideoPresenter {
  id: string;
  slug: PresenterSlug;
  nombre: string;
  flow_character_alias: string | null;
  activo: boolean;
  destino: PresenterDestino;
  aspect_ratio_default: PresenterAspectRatio;
  max_duracion_clip_seg: number;
  permite_multiclip: boolean;
  modelo_default: PresenterModelo;
  variantes_default: number;
  usar_clima_auto: boolean;
  modo_chroma_key: boolean;
  quemar_zocalo_ffmpeg: boolean;
  voz_descripcion_fija: string | null;
  look_modo: PresenterLookModo;
  look_manual_prompt: string | null;
  default_location_id: string | null;
  created_at: string;
  updated_at: string;
}

export type InsertVideoPresenter = Omit<VideoPresenter, 'id' | 'created_at' | 'updated_at'>;
export type UpdateVideoPresenter = Partial<InsertVideoPresenter>;

// ============================================================
// VideoLocation
// ============================================================
export type LocationTipo = 'foto_diurna' | 'foto_nocturna' | 'video_fondo' | 'estudio_chroma';

export interface VideoLocation {
  id: string;
  presenter_id: string | null;
  nombre: string;
  tipo: LocationTipo;
  storage_path: string | null;
  public_url: string | null;
  descripcion_ambiente_sonoro: string | null;
  activa: boolean;
  created_at: string;
}

export type InsertVideoLocation = Omit<VideoLocation, 'id' | 'created_at'>;
export type UpdateVideoLocation = Partial<InsertVideoLocation>;

// ============================================================
// VideoWeatherRule
// ============================================================
export type WeatherCondicion = 'despejado' | 'nublado' | 'lluvia' | 'viento';
export type WeatherFranjaHoraria = 'amanecer' | 'dia' | 'atardecer' | 'noche';

export interface VideoWeatherRule {
  id: string;
  temp_min: number;
  temp_max: number;
  condicion: WeatherCondicion;
  franja_horaria: WeatherFranjaHoraria;
  vestuario_sugerido: string | null;
  peinado_sugerido: string | null;
  luz_prompt_sugerida: string | null;
  override_luto_oscuro: boolean;
}

export type InsertVideoWeatherRule = Omit<VideoWeatherRule, 'id'>;
export type UpdateVideoWeatherRule = Partial<InsertVideoWeatherRule>;

// ============================================================
// VideoFactorySettings
// ============================================================
export interface VideoFactorySettings {
  id: string;
  piloto_automatico_activo: boolean;
  tope_diario_creditos: number;
  creditos_usados_hoy: number;
  cooldown_segundos: number;
  pausado_por_error: boolean;
  motivo_pausa: string | null;
  worker_last_heartbeat_at: string | null;
  worker_session_ok: boolean | null;
}

export type UpdateVideoFactorySettings = Partial<Omit<VideoFactorySettings, 'id'>>;

// ============================================================
// AraVideoJobs (extensión de ara_video_jobs)
// ============================================================
export type JobEstado = 'pending_approval' | 'esperando_qc' | 'generando' | 'listo' | 'error_reintentable' | 'cancelado';

export interface AraVideoJobExtended {
  // Columns from existing ara_video_jobs table (subset we care about)
  id: string;
  article_id: string | null;
  status: string;
  required_approval?: boolean;
  requires_sensitive_approval?: boolean;
  tenor?: string;
  blocks_json?: string | null;
  master_image_prompt?: string | null;
  video_prompts?: string[] | null;
  imagen_maestra_url: string | null;
  video_final_url: string | null;
  drive_upload_ok?: boolean | null;
  drive_remote_url?: string | null;
  created_at: string;
  updated_at: string;

  // NEW columns from this schema
  presenter_id: string | null;
  location_id: string | null;
  aspect_ratio: '9:16' | '16:9' | null;
  modelo_video: PresenterModelo | null;
  variantes: number;
  modo_chroma: boolean;
  clima_snapshot_json: Record<string, unknown> | null;
  look_override_text: string | null;
  bloques_override_json: Record<string, unknown>[] | null;
  creditos_estimados: number | null;
}

export type InsertAraVideoJob = Pick<AraVideoJobExtended,
  | 'article_id'
  | 'presenter_id'
  | 'location_id'
  | 'aspect_ratio'
  | 'modelo_video'
  | 'variantes'
  | 'modo_chroma'
  | 'clima_snapshot_json'
  | 'look_override_text'
  | 'bloques_override_json'
  | 'creditos_estimados'
>;
