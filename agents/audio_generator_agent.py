# -*- coding: utf-8 -*-
"""
agents/audio_generator_agent.py — Agente de Generación y Optimización de Audio
==============================================================================
Paso 4 del ciclo: Transforma el texto periodístico enriquecido en un archivo de audio MP3
narrado con locución natural, lo optimiza y normaliza sonoramente (LUFS/dBFS),
y lo aloja en el bucket público 'audios' de Supabase Storage.

Características:
- Locución en Español con acento rioplatense auténtico (Gemini TTS + reescritura fonética SOUL.md).
- Normalización automática de volumen con Pydub y AudioSegment.
- Compresión a MP3 128 kbps optimizada para streaming web y móvil.
- Subida directa al bucket 'audios' en Supabase Storage con headers públicos.
- Fallback tolerante a fallos: Si falla la optimización o el TTS, preserva la integridad del pipeline.
"""

import os
import sys
import io
import re
import time
import random
import itertools
import hashlib
import logging
import asyncio
import base64
import wave
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, List, Union

try:
    import edge_tts
    HAS_EDGE_TTS = True
except ImportError:
    HAS_EDGE_TTS = False

try:
    from gtts import gTTS
    HAS_GTTS = True
except ImportError:
    HAS_GTTS = False

try:
    from pydub import AudioSegment
    HAS_PYDUB = True
except ImportError:
    HAS_PYDUB = False

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

try:
    from google import genai
    from google.genai import types
    HAS_GEMINI_TTS = True
except ImportError:
    HAS_GEMINI_TTS = False

from .storage_agent import StorageAgent, load_env_credentials
from .ai_rewriter_agent import load_env_variables
from .constants import INSTITUTIONAL_CLOSING_PHRASES
from utils.gemini_tts_rotator import gemini_rotator, GEMINI_VOICE
from utils.ssml_builder import build_ssml, apply_rioplatense_phonetics, STYLE_TAG
try:
    from utils.tts_phonetic_adapter import adapt_text_for_tts
except ImportError:
    def adapt_text_for_tts(text: str, final_pause: bool = True) -> str:
        return text

logger = logging.getLogger("AudioGeneratorAgent")
logger.setLevel(logging.INFO)


# Frases institucionales de cierre elegidas al azar (reimportadas de constants para compatibilidad)
from .constants import INSTITUTIONAL_CLOSING_PHRASES  # noqa: F401

# Tag de estilo para Gemini TTS — se reusa el STYLE_TAG canónico de ssml_builder
# para garantizar coherencia total con SOUL.md (incluye mild s-aspiration).
GEMINI_TTS_STYLE_TAG = STYLE_TAG

def build_ssml(text: str) -> str:
    """Construye el prompt completo para Gemini TTS con tag de estilo y reescritura fonética."""
    phonetic_text = apply_rioplatense_phonetics(text)
    return f"{GEMINI_TTS_STYLE_TAG} {phonetic_text}"


class AudioGeneratorAgent:
    """
    Agente de generación y publicación de audios para noticias de Saladillo Vivo.
    """
    def __init__(self, supabase_url: Optional[str] = None, supabase_key: Optional[str] = None, storage_path: str = "data/audios", voice: str = "Aoede"):
        self.env = load_env_variables() if 'load_env_variables' in globals() else {}
        env_url, env_key = load_env_credentials()
        self.supabase_url = (supabase_url or env_url).rstrip('/')
        self.supabase_key = supabase_key or env_key
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.bucket_name = "audios"
        self.voice = voice  # Gemini TTS voice: Aoede, Charon, Fenrir, Kore, Puck, etc.
        self.tts_api_key = self.env.get('TTS_API_KEY') or self.env.get('ELEVENLABS_API_KEY')
        self.tts_voice_id = self.env.get('TTS_VOICE_ID')
        self.tts_api_url = self.env.get('TTS_API_URL', 'https://api.elevenlabs.io/v1/text-to-speech')

        # Directiva editorial definitiva: alternar por noticia entre las dos voces
        # argentinas de Edge/Azure TTS (es-AR-TomasNeural / es-AR-ElenaNeural).
        self._voice_cycle = itertools.cycle(["es-AR-TomasNeural", "es-AR-ElenaNeural"])

        # Resolver API key de Gemini
        self.gemini_api_key = (
            self.env.get('GEMINI_API_KEY') or
            self.env.get('GOOGLE_API_KEY') or
            os.environ.get('GEMINI_API_KEY') or
            os.environ.get('GOOGLE_API_KEY')
        )

        # Config Rime TTS — voces argentinas Coda (prioridad 2 del pipeline)
        self.rime_api_key = (
            self.env.get('RIME_API_KEY') or
            os.environ.get('RIME_API_KEY', '').strip()
        )
        self.rime_default_voice = self.env.get('RIME_VOICE') or 'cielo'
        self.rime_model_id = self.env.get('RIME_MODEL_ID') or 'coda'
        # Ciclo round-robin de las 3 voces argentinas de Coda: cielo / abril / solsticio
        self._rime_voice_cycle = itertools.cycle(['cielo', 'abril', 'solsticio'])

        self._ensure_storage_bucket()

    def _get_storage_headers(self, content_type: str = "audio/mpeg") -> Dict[str, str]:
        return {
            'Authorization': f'Bearer {self.supabase_key}',
            'apikey': self.supabase_key,
            'Content-Type': content_type,
            'x-upsert': 'true'
        }

    def _ensure_storage_bucket(self):
        """Verifica que el bucket 'audios' exista en Supabase Storage y sea público."""
        if not HAS_REQUESTS or not self.supabase_key:
            return

        try:
            url = f"{self.supabase_url}/storage/v1/bucket/{self.bucket_name}"
            headers = self._get_storage_headers("application/json")
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code == 404:
                # Crear bucket público si no existe
                create_url = f"{self.supabase_url}/storage/v1/bucket"
                payload = {
                    'id': self.bucket_name,
                    'name': self.bucket_name,
                    'public': True,
                    'file_size_limit': 52428800,
                    'allowed_mime_types': ['audio/mpeg', 'audio/mp3']
                }
                requests.post(create_url, headers=headers, json=payload, timeout=15)
        except Exception as e:
            logger.warning(f"No se pudo verificar el bucket '{self.bucket_name}': {e}")

    def clean_text_for_speech(self, text: str) -> str:
        """Limpia el texto removiendo etiquetas HTML, URLs y símbolos que degradan la síntesis."""
        if not text:
            return ""
        # Remover HTML tags
        clean = re.sub(r'<[^>]+>', ' ', text)
        # Remover URLs
        clean = re.sub(r'http\S+', '', clean)
        # Normalizar espacios y saltos de línea
        clean = re.sub(r'[\r\n]+', '. ', clean)
        clean = re.sub(r'\s+', ' ', clean)
        # Remover caracteres no legibles (permitir acentos y ñ)
        clean = re.sub(r'[^\w\s\.,;:¡!¿?\-\'"áéíóúÁÉÍÓÚñÑ]', '', clean)
        # Aplicar Glosario Fonético de Audio (data/glossary.json)
        try:
            from utils.glossary_manager import apply_audio_glossary
            clean = apply_audio_glossary(clean)
        except Exception:
            pass
        return clean.strip()

    def next_voice(self) -> str:
        """Devuelve la siguiente voz alternada (Tomas/Elena) para la locución."""
        return next(self._voice_cycle)

    def get_random_closing_phrase(self, article_id: Union[int, str] = None) -> str:
        """Selecciona la frase de cierre institucional para la noticia.

        Si se pasa article_id, la selección es DETERMINÍSTICA (semilla basada en el id),
        de modo que AudioGeneratorAgent y SlideGeneratorAgent elijan SIEMPRE la misma
        frase para el mismo artículo y el subtitulado coincida con el audio.
        """
        if article_id is not None:
            rng = random.Random(f"saladillo-{article_id}")
            return rng.choice(INSTITUTIONAL_CLOSING_PHRASES)
        return random.choice(INSTITUTIONAL_CLOSING_PHRASES)

    def generate_audio_filename(self, article_id: Union[int, str], title: str) -> str:
        """Genera un nombre de archivo único y predecible para el audio.

        Incluye timestamp con segundos para forzar cache-busting en Supabase/CDN
        (un filename distinto por generación evita que se sirva el audio viejo).
        """
        clean_title = re.sub(r'[^\w\-]', '_', title)[:40].strip('_')
        hash_input = f"{article_id}_{clean_title}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        file_hash = hashlib.md5(hash_input.encode('utf-8')).hexdigest()[:8]
        return f"article_{article_id}_{file_hash}.mp3"

    def text_to_speech_gemini(self, text: str) -> Optional[bytes]:
        """Genera audio con Gemini TTS aplicando reescritura fonética rioplatense (SOUL.md)."""
        if not HAS_GEMINI_TTS:
            logger.warning("Gemini TTS no disponible: falta google-genai")
            return None

        if not self.gemini_api_key:
            logger.warning("Gemini TTS: GEMINI_API_KEY / GOOGLE_API_KEY no configurada")
            return None

        try:
            client = genai.Client(api_key=self.gemini_api_key)
            prompt = build_ssml(text)

            logger.info(f"Gemini TTS: generando audio con voz '{self.voice}' (reescritura fonética aplicada)")

            response = client.models.generate_content(
                model="gemini-2.5-flash-preview-tts",
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=types.SpeechConfig(
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=self.voice)
                        )
                    )
                )
            )

            # Extraer audio PCM (puede venir base64 o binario crudo)
            for part in response.candidates[0].content.parts:
                if part.inline_data and part.inline_data.data:
                    raw = part.inline_data.data
                    # Detectar si es base64 (solo caracteres ASCII válidos) o PCM crudo
                    if isinstance(raw, str):
                        pcm_b64 = raw
                    elif isinstance(raw, bytes):
                        # Intentar decodificar como base64; si falla, es PCM crudo
                        try:
                            pcm_b64 = raw.decode('ascii')
                            # Validar que sea base64 real
                            import base64
                            base64.b64decode(pcm_b64, validate=True)
                            # Es base64 válido
                        except Exception:
                            # No es base64, es PCM crudo directo
                            logger.info("Gemini TTS: recibido PCM crudo directo, envolviendo...")
                            wav_bytes = self._pcm_to_wav(raw, sample_rate=24000)
                            mp3_bytes = self._wav_to_mp3(wav_bytes)
                            logger.info(f"Gemini TTS: audio generado exitosamente ({len(mp3_bytes)} bytes MP3)")
                            return mp3_bytes
                    else:
                        logger.error(f"Gemini TTS: tipo de datos inesperado: {type(raw)}")
                        continue

                    # Fix padding si es necesario
                    missing_padding = len(pcm_b64) % 4
                    if missing_padding:
                        pcm_b64 += '=' * (4 - missing_padding)
                    pcm_bytes = base64.b64decode(pcm_b64)

                    # Convertir PCM 24kHz mono 16-bit a WAV y luego a MP3 con ffmpeg
                    wav_bytes = self._pcm_to_wav(pcm_bytes, sample_rate=24000)
                    mp3_bytes = self._wav_to_mp3(wav_bytes)

                    logger.info(f"Gemini TTS: audio generado exitosamente ({len(mp3_bytes)} bytes MP3)")
                    return mp3_bytes

            logger.error("Gemini TTS: no se recibió datos de audio en la respuesta")
            return None

        except Exception as e:
            logger.error(f"Gemini TTS error: {e}")
            return None

    def _pcm_to_wav(self, pcm_bytes: bytes, sample_rate: int = 24000, channels: int = 1, sample_width: int = 2) -> bytes:
        """Envuelve PCM crudo en contenedor WAV."""
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, 'wb') as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(sample_width)
            wf.setframerate(sample_rate)
            wf.writeframes(pcm_bytes)
        wav_buffer.seek(0)
        return wav_buffer.read()

    def _wav_to_mp3(self, wav_bytes: bytes, bitrate: str = "128k") -> bytes:
        """Convierte WAV a MP3 usando ffmpeg."""
        try:
            import subprocess
            proc = subprocess.run(
                ['ffmpeg', '-y', '-i', 'pipe:0', '-c:a', 'libmp3lame', '-b:a', bitrate, '-f', 'mp3', 'pipe:1'],
                input=wav_bytes,
                capture_output=True,
                timeout=30
            )
            if proc.returncode == 0 and proc.stdout:
                return proc.stdout
            else:
                logger.warning(f"ffmpeg falló: {proc.stderr.decode()[:200]}")
                return wav_bytes  # fallback a WAV si ffmpeg falla
        except Exception as e:
            logger.warning(f"ffmpeg no disponible o error: {e}")
            return wav_bytes

    def _rime_next_voice(self) -> str:
        """Rotación round-robin de voces argentinas Coda."""
        return next(self._rime_voice_cycle)

    def text_to_speech_rime(self, text: str, voice: Optional[str] = None) -> Optional[bytes]:
        """
        TTS vía Rime Coda REST API — prioridad 2 del pipeline.
        Usa voces argentinas específicas (cielo / abril / solsticio).
        Retorna MP3 bytes o None en caso de fallo.
        """
        if not self.rime_api_key or not HAS_REQUESTS:
            logger.warning("⚠️ RIME_API_KEY no configurada; omitiendo Rime TTS")
            return None

        rime_voice = voice or self.rime_default_voice

        payload = {
            "text": text,
            "speaker": rime_voice,
            "modelId": self.rime_model_id,
            "lang": "es"
        }
        headers = {
            "Authorization": f"Bearer {self.rime_api_key}",
            "Accept": "audio/wav",
            "Content-Type": "application/json"
        }

        try:
            resp = requests.post(
                "https://coda.api.rime.ai/",
                headers=headers,
                json=payload,
                timeout=60
            )
            if resp.status_code == 200 and len(resp.content) > 1000:
                # Coda retorna WAV → convertir a MP3 para consistencia con el pipeline
                mp3_bytes = self._wav_to_mp3(resp.content, bitrate="128k")
                logger.info(
                    f"✅ Rime Coda TTS: {len(mp3_bytes)} bytes | VOZ: {rime_voice} | modelo: {self.rime_model_id}"
                )
                return mp3_bytes
            else:
                logger.warning(
                    f"⚠️ Rime TTS falló ({resp.status_code}): {resp.text[:200]}"
                )
                return None
        except Exception as e:
            logger.warning(f"⚠️ Rime TTS excepción: {type(e).__name__}: {e}")
            return None

    def text_to_speech(self, text: str, language: str = 'es', institutional_tone: bool = False, voice: Optional[str] = None,
                       prefer_engine: Optional[str] = None) -> Optional[bytes]:
        """
        Convierte texto a audio con máxima fidelidad rioplatense.
        Orden de prioridad:
        1. Gemini TTP (multi-key rotativo, SSML + SOUL.md) — motor principal.
        2. Rime Coda TTS (voces argentinas: cielo / abril / solsticio, $50/mes free tier).
        3. Edge TTP (voces neurales argentinas de Microsoft Azure, alternando
           es-AR-TomasNeural / es-AR-ElenaNeural por noticia) — respaldo.
        4. Google TTS (gTTS) con tld='com.ar' — respaldo genérico.

        prefer_engine: si se pasa ('gemini'|'rime'|'edge'|'gtts'), ese motor se intenta
        PRIMERO. Se usa para que la frase institucional de cierre suene con la MISMA
        voz/motor que el cuerpo de la noticia cuando hay que sintetizarlos por separado.
        """
        # ─── 1° PRIORIDAD: Gemini TTS (rotador multi-key REST) + SOUL.md ───
        # Orden pedido por el usuario: mientras las cuentas de Google funcionen,
        # se usa Gemini; Rime Coda (voces AR) y Edge TTS quedan como respaldo.
        if prefer_engine in (None, 'gemini'):
            try:
                prompt = build_ssml(text)
                audio_bytes = gemini_rotator.synthesize(prompt)
                if audio_bytes and len(audio_bytes) > 1000:
                    self._last_engine = 'gemini'
                    logger.info(f"✅ Gemini TTS (principal): {len(audio_bytes)} bytes | VOZ: {GEMINI_VOICE} | SOUL.md aplicado")
                    return audio_bytes
                logger.warning("⚠️ Gemini TTS sin audio, intentando fallback Rime Coda...")
            except Exception as e:
                logger.warning(f"⚠️ Gemini TTS falló ({type(e).__name__}: {e}), probando fallback Rime Coda...")

        # ─── 2° PRIORIDAD: Rime Coda TTS (voces argentinas, $50/mes free tier) ───
        if prefer_engine in (None, 'rime', 'gemini'):
            rime_bytes = self.text_to_speech_rime(text, voice=voice)
            if rime_bytes and len(rime_bytes) > 1000:
                self._last_engine = 'rime'
                return rime_bytes
            if rime_bytes is not None:
                logger.warning("⚠️ Rime Coda TTS generó audio muy pequeño, intentando fallback Edge TTS...")

        # ─── 3° PRIORIDAD: Edge TTS (Azure neural, voces AR alternadas) ───
        if HAS_EDGE_TTS:
            try:
                tts_voice = voice or self.next_voice()
                async def _synthesize():
                    # Parámetros de máxima expresividad soportados por el motor:
                    # rate: tempo de noticiero ágil; pitch: realce tonal (+2Hz).
                    rate_param = "-4%" if institutional_tone else "+0%"
                    comm = edge_tts.Communicate(text, tts_voice, rate=rate_param, volume="+0%", pitch="+2Hz")
                    audio_data = bytearray()
                    async for chunk in comm.stream():
                        if chunk.get("type") == "audio":
                            audio_data.extend(chunk["data"])
                    return bytes(audio_data)

                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        import concurrent.futures
                        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                            audio_bytes = executor.submit(asyncio.run, _synthesize()).result(timeout=60)
                    else:
                        audio_bytes = loop.run_until_complete(_synthesize())
                except RuntimeError:
                    audio_bytes = asyncio.run(_synthesize())

                if audio_bytes and len(audio_bytes) > 1000:
                    self._last_engine = 'edge'
                    logger.info(f"✅ Edge TTS (principal): {len(audio_bytes)} bytes | VOZ: {tts_voice}")
                    return audio_bytes
                logger.warning("⚠️ Edge TTS generó audio muy pequeño, intentando fallback Gemini...")
            except Exception as e:
                logger.warning(f"⚠️ Edge TTS principal falló ({type(e).__name__}: {e}), probando fallback Gemini TTS...")

        # 4. Respaldo: Google TTS (gTTS) con tld='com.ar'
        if HAS_GTTS:
            for tld_option in ['com.ar', 'com']:
                try:
                    tts = gTTS(text=text, lang='es', tld=tld_option, slow=False)
                    fp = io.BytesIO()
                    tts.write_to_fp(fp)
                    fp.seek(0)
                    data = fp.getvalue()
                    if len(data) > 1000:
                        self._last_engine = 'gtts'
                        logger.info(f"Audio sintetizado con éxito con Google TTS (gTTS tld={tld_option} - Argentina)")
                        return data
                except Exception as e:
                    logger.warning(f"Intento Google TTS (tld={tld_option}) falló, probando alternativa: {e}")

        # 5. API Externa personalizada (si está configurada en .env)
        if self.tts_api_key and self.tts_voice_id and HAS_REQUESTS:
            try:
                headers = {
                    "xi-api-key": self.tts_api_key,
                    "Content-Type": "application/json"
                }
                url = f"{self.tts_api_url}/{self.tts_voice_id}"
                data = {
                    "text": text,
                    "model_id": "eleven_multilingual_v2",
                    "voice_settings": {
                        "stability": 0.5,
                        "similarity_boost": 0.75
                    }
                }
                resp = requests.post(url, headers=headers, json=data, timeout=30)
                if resp.status_code == 200 and len(resp.content) > 1000:
                    logger.info("Audio sintetizado con éxito con API Externa TTS")
                    return resp.content
            except Exception as e:
                logger.warning(f"Error en API Externa TTS: {e}")

        logger.error("No hay motor TTS disponible para síntesis.")
        return None

    def optimize_audio(self, audio_bytes: bytes) -> bytes:
        """Normaliza volumen, equilibra dBFS y exporta a MP3 128 kbps usando Pydub/FFmpeg."""
        if not HAS_PYDUB:
            return audio_bytes

        try:
            buf_in = io.BytesIO(audio_bytes)
            audio = AudioSegment.from_file(buf_in, format="mp3")

            # Normalizar sonoridad
            normalized = audio.normalize()

            # Filtro pasa-bajos suave para eliminar siseos si el audio supera 30 segundos
            if len(normalized) > 30000:
                try:
                    final_audio = normalized.low_pass_filter(3500)
                except Exception:
                    final_audio = normalized
            else:
                final_audio = normalized

            # Exportar a MP3 128 kbps
            buf_out = io.BytesIO()
            final_audio.export(buf_out, format="mp3", bitrate="128k")
            buf_out.seek(0)
            return buf_out.getvalue()

        except Exception as e:
            logger.warning(f"Error optimizando audio con Pydub: {e}")
            return audio_bytes

    def upload_audio(self, article_id: Union[int, str], audio_bytes: bytes, title: str) -> Optional[str]:
        """Sube el audio MP3 al bucket 'audios' de Supabase Storage y retorna la URL pública."""
        if not HAS_REQUESTS or not self.supabase_key or not audio_bytes:
            return None

        filename = self.generate_audio_filename(article_id, title)
        url = f"{self.supabase_url}/storage/v1/object/{self.bucket_name}/{filename}"
        headers = self._get_storage_headers("audio/mpeg")

        try:
            resp = requests.post(url, headers=headers, data=audio_bytes, timeout=30)
            if resp.status_code in (200, 201):
                public_url = f"{self.supabase_url}/storage/v1/object/public/{self.bucket_name}/{filename}"
                logger.info(f"Audio subido a Supabase Storage: {public_url}")
                return public_url
            else:
                logger.error(f"Error subiendo audio a Supabase: HTTP {resp.status_code} - {resp.text[:200]}")
        except Exception as e:
            logger.error(f"Excepción subiendo audio: {e}")
        return None

    def _bytes_to_segment(self, audio_bytes: bytes):
        """Decodifica bytes de audio (mp3/wav) a AudioSegment, o None."""
        for fmt in ("mp3", "wav"):
            try:
                return AudioSegment.from_file(io.BytesIO(audio_bytes), format=fmt)
            except Exception:
                continue
        return None

    @staticmethod
    def _leading_silence_ms(seg) -> int:
        from pydub.silence import detect_leading_silence
        return detect_leading_silence(seg, silence_threshold=seg.dBFS - 16, chunk_size=10)

    @staticmethod
    def _trailing_silence_ms(seg) -> int:
        from pydub.silence import detect_leading_silence
        rev = seg.reverse()
        return detect_leading_silence(rev, silence_threshold=seg.dBFS - 16, chunk_size=10)

    def _find_seam_silence(self, seg):
        """
        Ubica el silencio que separa la noticia de la promo dentro de una síntesis CONTINUA.
        La promo institucional se ubica estrictamente al final y dura entre 1.3s y 5.0s.
        Para proteger la integridad del cuerpo de la noticia y evitar que se corte antes
        de tiempo, selecciona el ÚLTIMO silencio previo al tramo final de la promo.
        Devuelve (gap_start_ms, gap_end_ms) o None si no es fiable.
        """
        from pydub.silence import detect_nonsilent
        total = len(seg)
        try:
            blocks = detect_nonsilent(seg, min_silence_len=120,
                                      silence_thresh=seg.dBFS - 16, seek_step=10)
        except Exception:
            return None
        if len(blocks) < 2:
            return None

        # La promo institucional dura típicamente entre 1.3s y 5.0s
        prev_end = blocks[0][1]
        gaps = []
        for (a, b) in blocks[1:]:
            gap_start, gap_end = prev_end, a
            gap = gap_end - gap_start
            promo_len = total - gap_end
            if 1300 <= promo_len <= 5000 and gap >= 120:
                gaps.append((gap_start, gap_end, gap, promo_len))
            prev_end = b

        if not gaps:
            return None

        # Tomamos el último gap (el más cercano al final), asegurando que todo el cuerpo
        # anterior quede completo e intacto.
        last_gap = gaps[-1]
        return (last_gap[0], last_gap[1])

    def _splice_exact_pause(self, combined_bytes: bytes, pause_ms: int = 1000) -> Optional[bytes]:
        """
        Recorta la promo de una sintesis continua y reinserta un silencio EXACTO
        (pause_ms) entre el final de la noticia y el comienzo de la frase.
        Devuelve mp3 bytes o None si no puede localizar el empalme.
        """
        if not HAS_PYDUB:
            return None
        try:
            seg = self._bytes_to_segment(combined_bytes)
            if seg is None:
                return None
            seam = self._find_seam_silence(seg)
            if seam is None:
                logger.warning("  [AudioGeneratorAgent] No localice el empalme noticia/promo; descarto el splice continuo.")
                return None
            g_start, g_end = seam
            news = seg[:g_start]
            promo = seg[g_end:]
            # quitar silencios sobrantes a cada lado para que la pausa sea exactamente pause_ms
            lead = self._leading_silence_ms(promo)
            if lead > 0:
                promo = promo[lead:]
            trail = self._trailing_silence_ms(news)
            if trail > 0:
                news = news[:len(news) - trail]
            joined = news + AudioSegment.silent(duration=pause_ms, frame_rate=seg.frame_rate) + promo
            buf = io.BytesIO()
            joined.export(buf, format="mp3")
            buf.seek(0)
            logger.info(
                f"  [AudioGeneratorAgent] Splice OK: noticia {len(news)}ms + pausa exacta {pause_ms}ms + promo {len(promo)}ms"
            )
            return buf.read()
        except Exception as e:
            logger.warning(f"  [AudioGeneratorAgent] Splice de pausa exacta fallo: {e}")
            return None

    def _join_with_pause(self, body_bytes: bytes, closing_bytes: bytes, pause_ms: int = 1000) -> Optional[bytes]:
        """Une dos audios separados con un silencio exacto (fallback de doble sintesis)."""
        if not HAS_PYDUB or not body_bytes or not closing_bytes:
            return None
        try:
            body_seg = self._bytes_to_segment(body_bytes)
            closing_seg = self._bytes_to_segment(closing_bytes)
            if body_seg is None or closing_seg is None:
                return None
            lead = self._leading_silence_ms(closing_seg)
            if lead > 0:
                closing_seg = closing_seg[lead:]
            joined = body_seg + AudioSegment.silent(duration=pause_ms, frame_rate=body_seg.frame_rate) + closing_seg
            buf = io.BytesIO()
            joined.export(buf, format="mp3")
            buf.seek(0)
            return buf.read()
        except Exception:
            return None

    def process_article_audio(self, article_id: Union[int, str], title: str, text: str, description: str = "") -> Optional[str]:
        """
        Proceso completo: limpia texto, genera audio con TTS (voz alternada por
        noticia), ensambla 1 segundo de silencio + frase institucional al azar,
        optimiza y sube a Storage.
        Regla editorial 7.1: la meta_description es exclusiva de SEO y NUNCA se locuta.
        Retorna la URL pública del audio o None si falla.
        """
        clean_title = self.clean_text_for_speech(title)
        clean_text = self.clean_text_for_speech(text)

        # Estructura de locución: SOLO Cuerpo radial (Título NO se lee), + 1s silencio + promo
        body_parts = [clean_text] if clean_text else []
        body_speech = ". ".join(body_parts)
        # Adaptador fonético determinista para Edge TTS (respiración, números en
        # palabras, siglas desglosadas, extranjerismos rioplatenses)
        body_speech = adapt_text_for_tts(body_speech, final_pause=True)

        # Voz alternada por noticia (directiva editorial): Tomas / Elena
        voice = self.next_voice()
        # Selección determinística por article_id: audio y slide eligen la MISMA frase
        closing_phrase = self.get_random_closing_phrase(article_id)

        logger.info(f"  [AudioGeneratorAgent] [Paso 4: Generando Audio] ID: {article_id} | Caracteres: {len(body_speech)} | VOZ: {voice}")
        logger.info(f'  [AudioGeneratorAgent] Frase institucional de cierre: "{closing_phrase}"')

        # Sintesis CONTINUA noticia + promo en UNA sola corrida del motor: esto
        # garantiza que la MISMA voz, con el mismo tono, ritmo, enfasis y energia
        # diga la frase institucional (evita que cuerpo y promo caigan en motores
        # o voces distintas). Luego se normaliza el silencio del empalme a 1,000 ms.
        closing_text = closing_phrase
        combined_speech = f"{body_speech} {closing_text}"
        audio_bytes = None
        combined_audio = self.text_to_speech(combined_speech, voice=voice)
        if combined_audio:
            audio_bytes = self._splice_exact_pause(combined_audio, pause_ms=1000)
            if audio_bytes is None:
                logger.info("  [AudioGeneratorAgent] Splice continuo no disponible; armo con doble sintesis de respaldo.")

        # Fallback: si la sintesis continua o el splice fallaron, generar por separado
        # con la MISMA voz y SIN tono institucional (para no despegar la promo).
        if audio_bytes is None:
            body_audio = self.text_to_speech(body_speech, voice=voice)
            if not body_audio:
                return None
            # Forzar en la promo el MISMO motor que funcionó para el cuerpo: así
            # la voz de la frase institucional no cambia aunque el rotador de keys
            # haya agotado Gemini justo en la segunda llamada.
            engine_cuerpo = getattr(self, '_last_engine', None)
            closing_audio = self.text_to_speech(closing_text, voice=voice, prefer_engine=engine_cuerpo)
            if closing_audio:
                audio_bytes = self._join_with_pause(body_audio, closing_audio, pause_ms=1000)
            if audio_bytes is None:
                audio_bytes = body_audio
                logger.warning("  [AudioGeneratorAgent] No se pudo anexar la frase de cierre; se publica solo el cuerpo.")

        # Optimizar audio (normalizar, filtrar, MP3 128kbps)
        audio_bytes = self.optimize_audio(audio_bytes)

        # Duración REAL del audio final (incluye pausa de 1s + frase institucional).
        # El orquestador la usa para que el slide dure exactamente lo que dura
        # la locución, y así suene siempre completa hasta el final.
        try:
            _seg = self._bytes_to_segment(audio_bytes)
            self.last_audio_duration = len(_seg) / 1000.0
            logger.info(f"  [AudioGeneratorAgent] Duración final del audio: {self.last_audio_duration:.1f}s")
        except Exception as e:
            logger.warning(f"  [AudioGeneratorAgent] No se pudo medir duración: {e}")
            self.last_audio_duration = None

        # Subir a Supabase Storage
        audio_url = self.upload_audio(article_id, audio_bytes, title)
        return audio_url

    def process_articles_batch(self, articles: List[Dict]) -> Dict[Union[int, str], Optional[str]]:
        """
        Procesa un lote de artículos en memoria o consultados.
        Retorna un diccionario {article_id: audio_url}.
        """
        results = {}
        for art in articles:
            art_id = art.get('id')
            if not art_id:
                continue

            title = art.get('titulo_ia') or art.get('title') or ''
            text = art.get('contenido_ia') or art.get('text') or ''
            desc = art.get('meta_description') or art.get('description') or ''

            audio_url = self.process_article_audio(
                article_id=art_id,
                title=title,
                text=text,
                description=desc
            )
            results[art_id] = audio_url
            art['audio_url'] = audio_url
            _dur = getattr(self, 'last_audio_duration', None)
            if _dur:
                art['audio_duration'] = round(_dur, 1)
            time.sleep(1.5)  # Cortesía entre llamadas de TTS

        return results