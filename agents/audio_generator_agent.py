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

logger = logging.getLogger("AudioGeneratorAgent")
logger.setLevel(logging.INFO)


# Frases institucionales de cierre elegidas al azar
INSTITUTIONAL_CLOSING_PHRASES = [
    "En Saladillo Vivo. Dale play a la noticia.",
    "No lo leas, escuchálo, en Saladillo Vivo.",
    "Saladillo Vivo le pone voz a las noticias.",
    "Escuchá más, en Saladillo Vivo.",
    "Seguí escuchando, en Saladillo Vivo.",
    "La ciudad se escucha, en Saladillo Vivo.",
    "Enteráte escuchando, en Saladillo Vivo.",
    "Más info, en voz alta, en Saladillo Vivo.",
    "Saladillo Vivo. Menos textos, más audios.",
    "Cerrá los ojos, y escuchá Saladillo Vivo.",
    "Pasáte al audio, en Saladillo Vivo.",
    "Saladillo Vivo. Escuchar es la nueva forma de informarte.",
    "Poné play a tu día, en Saladillo Vivo.",
    "Dejános contarte la noticia, solo en Saladillo Vivo.",
    "Escuchálo ahora, en Saladillo Vivo.",
    "Todo suena mejor, en Saladillo Vivo.",
    "Viví la noticia, en Saladillo Vivo.",
    "Sentí Saladillo, en Saladillo Vivo.",
    "Saladillo Vivo. La voz de la ciudad.",
    "Informáte al instante, en Saladillo Vivo.",
    "Saladillo Vivo. Un paso adelante.",
    "Saladillo Vivo. La evolución de la noticia.",
    "Escuchá el futuro, en Saladillo Vivo.",
    "Saladillo Vivo. Innovación en noticias.",
    "Siempre un paso adelante, en Saladillo Vivo.",
    "Los demás leen, nosotros te lo contamos. Solo en Saladillo Vivo.",
    "Adelantáte a todos escuchando en Saladillo Vivo.",
    "La nueva era de la info, en Saladillo Vivo.",
    "Innovamos para que solo escuches. Solo en Saladillo Vivo.",
    "Saladillo Vivo. Un paso más allá de la lectura.",
    "Saladillo Vivo. Un paso más allá que leer las noticias."
]

# Tag de estilo para Gemini TTS (SOUL.md)
GEMINI_TTS_STYLE_TAG = "[relaxed, colloquial tone, argentinian rioplatense accent]"


def apply_rioplatense_phonetics(text: str) -> str:
    """
    Aplica las reglas fonéticas rioplatenses obligatorias (SOUL.md) para Gemini TTS.
    Gemini TTS lee el texto literalmente, por lo que debemos reescribir:
    1. S ante consonante → h (aspiración)
    2. S final → h (aspiración)
    3. S intervocálica se mantiene (excepción)
    4. Y / LL → sh (yeísmo rehilado)
    """
    if not text:
        return ""

    # Primero, protegemos la S intervocálica marcándola temporalmente
    # Patrón: vocal + s + vocal (case insensitive)
    text = re.sub(r'([aeiouáéíóúAEIOUÁÉÍÓÚ])s([aeiouáéíóúAEIOUÁÉÍÓÚ])',
                  r'\1§S_INTERVOCALICA§\2', text, flags=re.IGNORECASE)

    # 1. S ante consonante → h (aspiración suave)
    # Consonantes: b c d f g h j k l m n ñ p q r s t v w x y z
    text = re.sub(r's(?=[bcdfghjklmnñpqrstvwxyzBCDFGHJKLMNÑPQRSTVWXYZ])', 'h', text)

    # 2. S final de palabra → h
    text = re.sub(r's\b', 'h', text)

    # 3. Restaurar S intervocálica protegida
    text = text.replace('§S_INTERVOCALICA§', 's')

    # 4. Yeísmo rehilado: Y / LL → sh
    # Y como consonante inicial o entre vocales
    text = re.sub(r'\by\b', 'sh', text, flags=re.IGNORECASE)  # "y" sola
    text = re.sub(r'\by(?=[aeiouáéíóúAEIOUÁÉÍÓÚ])', 'sh', text, flags=re.IGNORECASE)  # "ya", "yo", etc.
    text = re.sub(r'll', 'sh', text, flags=re.IGNORECASE)  # "ll" → "sh"

    return text


def build_gemini_tts_prompt(text: str) -> str:
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

        # Resolver API key de Gemini
        self.gemini_api_key = (
            self.env.get('GEMINI_API_KEY') or
            self.env.get('GOOGLE_API_KEY') or
            os.environ.get('GEMINI_API_KEY') or
            os.environ.get('GOOGLE_API_KEY')
        )

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
        clean = re.sub(r'[^\w\s\.,;:¡!¿?\-\'\"áéíóúÁÉÍÓÚñÑ]', '', clean)
        return clean.strip()

    def get_random_closing_phrase(self) -> str:
        """Selecciona al azar una frase de cierre institucional para la noticia."""
        return random.choice(INSTITUTIONAL_CLOSING_PHRASES)

    def generate_audio_filename(self, article_id: Union[int, str], title: str) -> str:
        """Genera un nombre de archivo único y predecible para el audio."""
        clean_title = re.sub(r'[^\w\-]', '_', title)[:40].strip('_')
        hash_input = f"{article_id}_{clean_title}_{datetime.now().strftime('%Y%m')}"
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
            prompt = build_gemini_tts_prompt(text)

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

    def text_to_speech(self, text: str, language: str = 'es', institutional_tone: bool = False) -> Optional[bytes]:
        """
        Convierte texto a audio con máxima fidelidad rioplatense.
        Prioridad:
        1. Gemini TTS con reescritura fonética rioplatense (SOUL.md) — motor principal.
        2. Edge TTS con voz rioplatense (es-AR-TomasNeural) — respaldo nativo.
        3. Google TTS (gTTS) con tld='com.ar' — respaldo genérico.
        """
        # 1. Prioridad Principal: Gemini TTS con reescritura fonética rioplatense
        gemini_audio = self.text_to_speech_gemini(text)
        if gemini_audio:
            return gemini_audio

        # 2. Respaldo: Edge TTS con voz rioplatense (es-AR-TomasNeural)
        if HAS_EDGE_TTS:
            try:
                async def _synthesize():
                    rate_param = "-4%" if institutional_tone else "+0%"
                    comm = edge_tts.Communicate(text, "es-AR-TomasNeural", rate=rate_param)
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
                            audio_bytes = executor.submit(asyncio.run, _synthesize()).result(timeout=30)
                    else:
                        audio_bytes = loop.run_until_complete(_synthesize())
                except RuntimeError:
                    audio_bytes = asyncio.run(_synthesize())

                if audio_bytes and len(audio_bytes) > 1000:
                    logger.info(f"Audio sintetizado con éxito con Edge TTS (es-AR-TomasNeural - Respaldo): {len(audio_bytes)} bytes")
                    return audio_bytes
            except Exception as e:
                logger.warning(f"Error en Edge TTS de respaldo: {e}")

        # 3. Respaldo: Google TTS (gTTS) con tld='com.ar'
        if HAS_GTTS:
            for tld_option in ['com.ar', 'com']:
                try:
                    tts = gTTS(text=text, lang='es', tld=tld_option, slow=False)
                    fp = io.BytesIO()
                    tts.write_to_fp(fp)
                    fp.seek(0)
                    data = fp.getvalue()
                    if len(data) > 1000:
                        logger.info(f"Audio sintetizado con éxito con Google TTS (gTTS tld={tld_option} - Argentina)")
                        return data
                except Exception as e:
                    logger.warning(f"Intento Google TTS (tld={tld_option}) falló, probando alternativa: {e}")

        # 4. API Externa personalizada (si está configurada en .env)
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

    def process_article_audio(self, article_id: Union[int, str], title: str, text: str, description: str = "") -> Optional[str]:
        """
        Proceso completo: limpia texto, genera audio con TTS, optimiza, sube a Storage.
        Retorna la URL pública del audio o None si falla.
        """
        # Construir texto completo para locución
        clean_title = self.clean_text_for_speech(title)
        clean_text = self.clean_text_for_speech(text)
        clean_desc = self.clean_text_for_speech(description) if description else ""

        # Estructura: Título + Descripción + Texto completo + Frase de cierre
        speech_parts = []
        if clean_title:
            speech_parts.append(clean_title)
        if clean_desc:
            speech_parts.append(clean_desc)
        if clean_text:
            speech_parts.append(clean_text)

        closing_phrase = self.get_random_closing_phrase()
        speech_parts.append(closing_phrase)

        full_speech = ". ".join(speech_parts)

        logger.info(f"  [AudioGeneratorAgent] [Paso 4: Generando Audio] ID: {article_id} | Caracteres: {len(full_speech)}")
        logger.info(f"  [AudioGeneratorAgent] Frase institucional de cierre: \"{closing_phrase}\"")

        # Generar audio con TTS
        audio_bytes = self.text_to_speech(full_speech)
        if not audio_bytes:
            return None

        # Optimizar audio (normalizar, filtrar, MP3 128kbps)
        audio_bytes = self.optimize_audio(audio_bytes)

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
            time.sleep(1.5)  # Cortesía entre llamadas de TTS

        return results