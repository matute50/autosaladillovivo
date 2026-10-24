# -*- coding: utf-8 -*-
"""
agents/audio_generator_agent.py — Agente de Generación y Optimización de Audio
==============================================================================
Paso 4 del ciclo: Transforma el texto periodístico enriquecido en un archivo de audio MP3
narrado con locución natural, lo optimiza y normaliza sonoramente (LUFS/dBFS),
y lo aloja en el bucket público 'audios' de Supabase Storage.

Características:
- Locución en Español (acento rioplatense/argentino con gTTS tld='com.ar' y fallback a 'es').
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
import hashlib
import logging
import asyncio
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

from .storage_agent import StorageAgent, load_env_credentials

logger = logging.getLogger("AudioGeneratorAgent")
logger.setLevel(logging.INFO)


class AudioGeneratorAgent:
    """
    Agente de generación y publicación de audios para noticias de Saladillo Vivo.
    """
    def __init__(self, supabase_url: Optional[str] = None, supabase_key: Optional[str] = None, storage_path: str = "data/audios", voice: str = "es-AR-ElenaNeural"):
        env_url, env_key = load_env_credentials()
        self.supabase_url = (supabase_url or env_url).rstrip('/')
        self.supabase_key = supabase_key or env_key
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.bucket_name = "audios"
        self.voice = voice  # es-AR-ElenaNeural o es-AR-TomasNeural (Español rioplatense argentino auténtico)

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
        # Remover caracteres no legibles
        clean = re.sub(r'[^\w\s\.,;:¡!¿?\-\'\"áéíóúÁÉÍÓÚñÑ]', '', clean)
        return clean.strip()

    def generate_audio_filename(self, article_id: Union[int, str], title: str) -> str:
        """Genera un nombre de archivo único y predecible para el audio."""
        clean_title = re.sub(r'[^\w\-]', '_', title)[:40].strip('_')
        hash_input = f"{article_id}_{clean_title}_{datetime.now().strftime('%Y%m')}"
        file_hash = hashlib.md5(hash_input.encode('utf-8')).hexdigest()[:8]
        return f"article_{article_id}_{file_hash}.mp3"

    def text_to_speech(self, text: str, language: str = 'es') -> Optional[bytes]:
        """Convierte texto a audio con auténtico acento rioplatense (es-AR) usando Edge TTS (o fallback gTTS)."""
        # 1. Prioridad: Edge TTS con voz rioplatense (es-AR-ElenaNeural o es-AR-TomasNeural)
        if HAS_EDGE_TTS:
            try:
                async def _synthesize():
                    comm = edge_tts.Communicate(text, self.voice)
                    audio_data = bytearray()
                    async for chunk in comm.stream():
                        if chunk.get("type") == "audio":
                            audio_data.extend(chunk["data"])
                    return bytes(audio_data)

                # Ejecutar de forma segura según el contexto de bucle de eventos
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
                    logger.info(f"Audio sintetizado con éxito con Edge TTS ({self.voice} - Rioplatense): {len(audio_bytes)} bytes")
                    return audio_bytes
            except Exception as e:
                logger.warning(f"Error en Edge TTS rioplatense ({self.voice}), activando fallback: {e}")

        # 2. Fallback secundario: gTTS con tld='com.ar'
        if HAS_GTTS:
            for tld_option in ['com.ar', None]:
                try:
                    if tld_option:
                        tts = gTTS(text=text, lang=language, tld=tld_option, slow=False)
                    else:
                        tts = gTTS(text=text, lang=language, slow=False)

                    fp = io.BytesIO()
                    tts.write_to_fp(fp)
                    fp.seek(0)
                    data = fp.getvalue()
                    if len(data) > 1000:
                        return data
                except Exception as e:
                    logger.warning(f"Intento gTTS fallback (tld={tld_option}) falló: {e}")

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

            # Exportar a MP3 a 128kbps constante
            buf_out = io.BytesIO()
            final_audio.export(buf_out, format="mp3", bitrate="128k")
            return buf_out.getvalue()
        except Exception as e:
            logger.warning(f"Optimización con pydub omitida por excepción: {e}")
            return audio_bytes

    def upload_to_supabase_storage(self, audio_bytes: bytes, filename: str) -> Optional[str]:
        """Sube el archivo de audio al bucket 'audios' de Supabase y obtiene su URL pública."""
        if not HAS_REQUESTS:
            return None

        # 1. Guardar copia local de respaldo
        local_filepath = self.storage_path / filename
        try:
            with open(local_filepath, 'wb') as f:
                f.write(audio_bytes)
        except Exception as e:
            logger.warning(f"No se pudo guardar copia local de {filename}: {e}")

        # 2. Subir a Supabase Storage REST API
        upload_url = f"{self.supabase_url}/storage/v1/object/{self.bucket_name}/{filename}"
        headers = self._get_storage_headers("audio/mpeg")

        try:
            resp = requests.post(upload_url, headers=headers, data=audio_bytes, timeout=30)
            if resp.status_code in (200, 201):
                public_url = f"{self.supabase_url}/storage/v1/object/public/{self.bucket_name}/{filename}"
                logger.info(f"Audio subido exitosamente a Supabase Storage: {public_url}")
                return public_url
            else:
                logger.error(f"Error subiendo audio a Supabase Storage ({resp.status_code}): {resp.text}")
                return None
        except Exception as e:
            logger.error(f"Excepción subiendo audio a Supabase Storage: {e}")
            return None

    def process_article_audio(self, article_id: Union[int, str], title: str, text: str, description: str = "") -> Optional[str]:
        """
        Procesa el ciclo completo para un artículo:
        1. Limpieza de texto (Título + Bajada + Contenido)
        2. Text-To-Speech (gTTS)
        3. Optimización acústica (Pydub / FFmpeg)
        4. Subida a Supabase Storage
        5. Retorna la URL pública del audio
        """
        clean_title = self.clean_text_for_speech(title)
        clean_desc = self.clean_text_for_speech(description)
        clean_text = self.clean_text_for_speech(text)

        # Estructurar la locución: Título... Copete... Desarrollo de la noticia
        parts = [clean_title]
        if clean_desc and clean_desc not in clean_title:
            parts.append(clean_desc)
        if clean_text:
            parts.append(clean_text)

        full_speech = ". ".join(parts)

        # Límite seguro para no exceder cuotas de gTTS y garantizar audios ágiles
        if len(full_speech) > 4500:
            full_speech = full_speech[:4500].rsplit('.', 1)[0] + ". Para más información, visitá saladillovivo.com.ar."

        if len(full_speech) < 20:
            logger.warning(f"Artículo {article_id} sin contenido suficiente para audio.")
            return None

        print(f"  [AudioGeneratorAgent] [Paso 4: Generando Audio] ID: {article_id} | Caracteres: {len(full_speech)}")

        # 1. Síntesis de voz
        audio_bytes = self.text_to_speech(full_speech)
        if not audio_bytes:
            logger.error(f"Fallo al generar TTS para artículo {article_id}.")
            return None

        # 2. Optimización acústica
        optimized_audio = self.optimize_audio(audio_bytes)

        # 3. Nombre de archivo único
        filename = self.generate_audio_filename(article_id, title)

        # 4. Subida a Supabase Storage
        audio_url = self.upload_to_supabase_storage(optimized_audio, filename)
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
