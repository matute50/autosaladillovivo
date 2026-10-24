# -*- coding: utf-8 -*-
"""
agents/slide_generator_agent.py — Agente Generador de Slides con Voz Rioplatense
================================================================================
Paso 5 del ciclo: Transforma artículos periodísticos en slides dinámicos e interactivos (.html)
con diseño cinematográfico, fotografías optimizadas y locución con acento rioplatense (argentino).
Los slides generados son alojados en el bucket público 'slides' de Supabase Storage.

Características:
- Diseño responsive TV-Grade con logo de Saladillo Vivo y controles ARIA.
- Locución en acento rioplatense usando gTTS con tld='com.ar'.
- Optimización y redimensionado de imágenes con Pillow.
- Plantilla Jinja2 interactiva con reproducción de audio automática y fallback manual.
- Subida a Supabase Storage con headers públicos y mime-type 'text/html; charset=utf-8'.
"""

import os
import io
import sys
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
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    from gtts import gTTS
    HAS_GTTS = True
except ImportError:
    HAS_GTTS = False

try:
    import jinja2
    HAS_JINJA2 = True
except ImportError:
    HAS_JINJA2 = False

try:
    from supabase import create_client, Client
    HAS_SUPABASE = True
except ImportError:
    HAS_SUPABASE = False

from .storage_agent import load_env_credentials

logger = logging.getLogger("SlideGeneratorAgent")
logger.setLevel(logging.INFO)


class SlideGeneratorAgent:
    """
    Agente de generación de slides interactivos con voz rioplatense para Saladillo Vivo.
    """
    def __init__(self, supabase_url: Optional[str] = None, supabase_key: Optional[str] = None, storage_path: str = "data/slides", voice: str = "es-AR-ElenaNeural"):
        env_url, env_key = load_env_credentials()
        self.supabase_url = (supabase_url or env_url or "https://otwvfihzaznyjvjtkvvd.supabase.co").rstrip('/')
        self.supabase_key = supabase_key or env_key or ""
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.bucket_name = "slides"
        self.voice = voice  # es-AR-ElenaNeural o es-AR-TomasNeural (Voz neural rioplatense)
        self.logger = logger

        # Cliente Supabase SDK oficial
        self.supabase: Optional[Client] = None
        if HAS_SUPABASE and self.supabase_url and self.supabase_key:
            try:
                self.supabase = create_client(self.supabase_url, self.supabase_key)
            except Exception as e:
                self.logger.warning(f"No se pudo inicializar cliente supabase-py: {e}")

        self._ensure_storage_bucket()

    def _get_storage_headers(self, content_type: str = "text/html; charset=utf-8") -> Dict[str, str]:
        """Headers para comunicación directa con la API REST de Supabase Storage."""
        return {
            'Authorization': f'Bearer {self.supabase_key}',
            'apikey': self.supabase_key,
            'Content-Type': content_type,
            'x-upsert': 'true'
        }

    def _ensure_storage_bucket(self):
        """Verifica que el bucket 'slides' exista en Supabase Storage y sea público."""
        if not HAS_REQUESTS or not self.supabase_key:
            return

        try:
            url = f"{self.supabase_url}/storage/v1/bucket/{self.bucket_name}"
            headers = self._get_storage_headers("application/json")
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code == 404:
                create_url = f"{self.supabase_url}/storage/v1/bucket"
                payload = {
                    'id': self.bucket_name,
                    'name': self.bucket_name,
                    'public': True,
                    'file_size_limit': 10485760,  # 10MB
                    'allowed_mime_types': ['text/html', 'text/html; charset=utf-8']
                }
                requests.post(create_url, headers=headers, json=payload, timeout=15)
                self.logger.info(f"Bucket '{self.bucket_name}' creado en Supabase Storage.")
        except Exception as e:
            self.logger.warning(f"No se pudo verificar el bucket '{self.bucket_name}': {e}")

    def generate_slide_filename(self, article_id: Union[int, str], title: str) -> str:
        """Genera un nombre de archivo único para el slide."""
        clean_title = "".join(c for c in title if c.isalnum() or c in (" ", "-", "_")).rstrip()
        hash_input = f"{article_id}_{clean_title}_{datetime.now().strftime('%Y%m%d')}"
        file_hash = hashlib.md5(hash_input.encode()).hexdigest()[:8]
        return f"slide_{article_id}_{file_hash}.html"

    def text_to_speech_rioplatense(self, text: str, language: str = 'es-ES') -> Optional[bytes]:
        """
        Convierte texto a audio con auténtico acento rioplatense (es-AR) usando Edge TTS (o fallback gTTS).
        """
        if not text:
            return None

        clean_text = text.replace('\n', ' ').strip()
        if len(clean_text) > 4000:
            clean_text = clean_text[:4000].rsplit('.', 1)[0] + "."

        # 1. Edge TTS con voz rioplatense auténtica (Elena / Tomás)
        if HAS_EDGE_TTS:
            try:
                async def _synthesize():
                    comm = edge_tts.Communicate(clean_text, self.voice)
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
                    self.logger.info(f"Voz rioplatense sintetizada exitosamente ({self.voice}): {len(audio_bytes)} bytes")
                    return audio_bytes
            except Exception as e:
                self.logger.warning(f"Error en Edge TTS rioplatense ({self.voice}): {e}")

        # 2. Fallback gTTS
        if HAS_GTTS:
            for tld in ['com.ar', 'com']:
                try:
                    tts = gTTS(text=clean_text, lang=language, slow=False, tld=tld)
                    fp = io.BytesIO()
                    tts.write_to_fp(fp)
                    fp.seek(0)
                    audio_bytes = fp.read()
                    if audio_bytes:
                        return audio_bytes
                except Exception as e:
                    self.logger.warning(f"Intento TTS fallback con tld={tld} falló: {e}")

        return None

    def process_images_for_slide(self, article_id: Union[int, str], image_urls: List[str]) -> List[str]:
        """
        Procesa y optimiza imágenes para el slide.
        Retorna las URLs utilizables en el slide HTML.
        """
        processed_images: List[str] = []

        if not image_urls:
            return ["https://saladillovivo.vercel.app/default-og-image.png"]

        for i, image_url in enumerate(image_urls):
            if not image_url:
                continue

            # Si es una URL web válida
            if image_url.startswith("http://") or image_url.startswith("https://"):
                try:
                    if HAS_PIL and HAS_REQUESTS:
                        # Validar/optimizar imagen
                        resp = requests.get(image_url, timeout=10)
                        if resp.status_code == 200:
                            img = Image.open(io.BytesIO(resp.content))
                            # Convertir a RGB si viene en RGBA o P
                            if img.mode in ('RGBA', 'LA', 'P'):
                                rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                                if img.mode == 'P':
                                    img = img.convert('RGBA')
                                rgb_img.paste(img, mask=img.split()[3] if len(img.split()) > 3 else None)
                                img = rgb_img

                            # Redimensionar para formato web
                            max_width, max_height = 1200, 800
                            img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)

                            # Guardar copia local temporal de respaldo
                            temp_image_path = self.storage_path / f"temp_article_{article_id}_img_{i}.jpg"
                            img.save(temp_image_path, format='JPEG', quality=85, optimize=True)

                    # Añadir la URL accesible para el slide
                    processed_images.append(image_url)
                except Exception as e:
                    self.logger.warning(f"Error procesando imagen {i} para artículo {article_id}: {e}")
                    processed_images.append(image_url)
            else:
                processed_images.append(image_url)

        return processed_images if processed_images else ["https://saladillovivo.vercel.app/default-og-image.png"]

    def create_slide_html(self, article_id: Union[int, str], title: str, text: str,
                          audio_url: str, images: List[str]) -> str:
        """
        Genera el documento HTML del slide interactivo con diseño profesional TV-Grade.
        """
        template_str = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }} - Saladillo Vivo</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 50%, #311042 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            overflow-x: hidden;
            color: #f8fafc;
            padding: 20px;
        }
        
        .slide-container {
            width: 100%;
            max-width: 1200px;
            background: rgba(15, 23, 42, 0.92);
            border: 1px solid rgba(255, 255, 255, 0.12);
            border-radius: 24px;
            box-shadow: 0 25px 60px rgba(0, 0, 0, 0.6);
            backdrop-filter: blur(20px);
            overflow: hidden;
            position: relative;
        }
        
        .slide-header {
            background: linear-gradient(135deg, rgba(30, 41, 59, 0.9) 0%, rgba(51, 65, 85, 0.9) 100%);
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
            color: white;
            padding: 35px 40px 30px 100px;
            position: relative;
        }
        
        .saladillo-logo {
            position: absolute;
            top: 25px;
            left: 30px;
            width: 55px;
            height: 55px;
            background: linear-gradient(135deg, #0284c7 0%, #38bdf8 100%);
            border-radius: 16px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: 800;
            font-size: 1.25rem;
            box-shadow: 0 8px 20px rgba(2, 132, 199, 0.4);
            letter-spacing: -0.5px;
        }
        
        .slide-badge {
            display: inline-block;
            background: rgba(14, 165, 233, 0.2);
            color: #38bdf8;
            border: 1px solid rgba(56, 189, 248, 0.3);
            padding: 4px 12px;
            border-radius: 9999px;
            font-size: 0.75rem;
            font-weight: 700;
            letter-spacing: 1px;
            text-transform: uppercase;
            margin-bottom: 10px;
        }
        
        .slide-title {
            font-size: 2.1rem;
            font-weight: 800;
            margin-bottom: 10px;
            text-shadow: 0 2px 10px rgba(0, 0, 0, 0.5);
            line-height: 1.25;
            color: #ffffff;
        }
        
        .slide-subtitle {
            font-size: 1.05rem;
            color: #94a3b8;
            font-weight: 400;
        }
        
        .slide-content {
            padding: 35px 40px;
        }
        
        @keyframes kenBurnsZoom {
            0% {
                transform: scale(1.0);
            }
            50% {
                transform: scale(1.08);
            }
            100% {
                transform: scale(1.0);
            }
        }
        
        .slide-images {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
            gap: 24px;
            margin-bottom: 30px;
            width: 100%;
        }
        
        .slide-image-wrapper {
            position: relative;
            border-radius: 18px;
            overflow: hidden;
            box-shadow: 0 16px 36px rgba(0, 0, 0, 0.45);
            min-height: 320px;
            max-height: 480px;
            height: auto;
            background: #0f172a;
            display: flex;
            align-items: center;
            justify-content: center;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }
        
        .slide-image {
            width: 100%;
            height: 100%;
            max-height: 480px;
            object-fit: cover;
            object-position: center;
            animation: kenBurnsZoom 16s ease-in-out infinite alternate;
            transform-origin: center center;
            will-change: transform;
            transition: filter 0.4s ease;
        }
        
        .slide-image-wrapper:nth-child(2) .slide-image {
            animation-duration: 20s;
            animation-delay: -5s;
        }
        
        .slide-image-wrapper:nth-child(3) .slide-image {
            animation-duration: 18s;
            animation-delay: -10s;
        }
        
        .slide-text {
            font-size: 1.15rem;
            line-height: 1.85;
            color: #e2e8f0;
            text-align: justify;
            margin-bottom: 25px;
            background: rgba(30, 41, 59, 0.5);
            padding: 25px;
            border-radius: 16px;
            border: 1px solid rgba(255, 255, 255, 0.05);
        }
        
        .audio-controls {
            position: fixed;
            bottom: 30px;
            right: 30px;
            background: rgba(15, 23, 42, 0.92);
            backdrop-filter: blur(16px);
            border: 1px solid rgba(56, 189, 248, 0.3);
            padding: 14px 22px;
            border-radius: 20px;
            box-shadow: 0 15px 35px rgba(0, 0, 0, 0.5);
            display: flex;
            align-items: center;
            gap: 16px;
            z-index: 1000;
            transition: transform 0.2s, box-shadow 0.2s;
        }
        
        .audio-controls:hover {
            transform: translateY(-2px);
            box-shadow: 0 20px 40px rgba(2, 132, 199, 0.25);
        }
        
        .play-button {
            background: linear-gradient(135deg, #0284c7 0%, #0369a1 100%);
            color: white;
            border: none;
            border-radius: 50%;
            width: 48px;
            height: 48px;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            font-size: 1.1rem;
            transition: all 0.25s ease;
            box-shadow: 0 4px 15px rgba(2, 132, 199, 0.4);
        }
        
        .play-button:hover {
            transform: scale(1.08);
            background: linear-gradient(135deg, #38bdf8 0%, #0284c7 100%);
        }
        
        .audio-info {
            color: #f1f5f9;
            font-size: 0.9rem;
            line-height: 1.3;
        }
        
        .audio-info .badge {
            display: flex;
            align-items: center;
            gap: 6px;
            font-weight: 600;
            color: #38bdf8;
        }
        
        .audio-info small {
            color: #94a3b8;
            font-size: 0.78rem;
        }
        
        .slide-footer {
            background: rgba(15, 23, 42, 0.7);
            border-top: 1px solid rgba(255, 255, 255, 0.08);
            padding: 18px 40px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            color: #64748b;
            font-size: 0.85rem;
        }
        
        .pulse-dot {
            width: 8px;
            height: 8px;
            background: #22c55e;
            border-radius: 50%;
            display: inline-block;
            box-shadow: 0 0 10px #22c55e;
            animation: pulse 1.8s infinite;
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; transform: scale(1); }
            50% { opacity: 0.4; transform: scale(0.85); }
        }
        
        @media (max-width: 768px) {
            body { padding: 10px; }
            .slide-header { padding: 25px 20px 20px 80px; }
            .saladillo-logo { top: 20px; left: 18px; width: 48px; height: 48px; font-size: 1.1rem; }
            .slide-title { font-size: 1.5rem; }
            .slide-content { padding: 20px; }
            .slide-text { font-size: 1rem; padding: 18px; line-height: 1.7; }
            .slide-images { grid-template-columns: 1fr; }
            .audio-controls { bottom: 15px; right: 15px; left: 15px; justify-content: center; }
            .slide-footer { flex-direction: column; gap: 8px; text-align: center; }
        }
    </style>
</head>
<body>
    <div class="slide-container">
        <div class="saladillo-logo">SV</div>
        
        <div class="slide-header">
            <span class="slide-badge">Saladillo Vivo • Noticias En Vivo</span>
            <h1 class="slide-title">{{ title }}</h1>
            <p class="slide-subtitle">Portal Hiperlocal de Noticias y Streaming Temático</p>
        </div>
        
        <div class="slide-content">
            {% if images and images|length > 0 %}
            <div class="slide-images">
                {% for image_url in images %}
                <div class="slide-image-wrapper">
                    <img src="{{ image_url }}" alt="Fotografía de la noticia" class="slide-image" loading="lazy" onerror="this.src='https://saladillovivo.vercel.app/default-og-image.png'">
                </div>
                {% endfor %}
            </div>
            {% endif %}
            
            <div class="slide-text">
                {{ text }}
            </div>
        </div>
        
        <div class="slide-footer">
            <div style="display: flex; align-items: center; gap: 8px;">
                <span class="pulse-dot"></span>
                <span>Transmisión Oficial Saladillo Vivo</span>
            </div>
            <p>saladillovivo.com.ar • Sistema de Automatización Periodística</p>
        </div>
    </div>
    
    {% if audio_url %}
    <div class="audio-controls">
        <button class="play-button" id="playButton" aria-label="Reproducir o pausar locución">▶</button>
        <div class="audio-info">
            <div class="badge">🎙️ Voz Rioplatense</div>
            <small id="audioStatusText">Reproducir locución</small>
        </div>
    </div>
    
    <audio id="slideAudio" src="{{ audio_url }}" preload="auto" playsinline></audio>
    
    <script>
        (function() {
            var playButton = document.getElementById('playButton');
            var audio = document.getElementById('slideAudio');
            var statusText = document.getElementById('audioStatusText');
            
            if (!playButton || !audio) return;
            
            function updatePlayState(playing) {
                playButton.textContent = playing ? '⏸' : '▶';
                if (statusText) {
                    statusText.textContent = playing ? 'Reproduciendo...' : 'Pausado (Clic para escuchar)';
                }
            }
            
            playButton.addEventListener('click', function(e) {
                e.stopPropagation();
                if (audio.paused) {
                    audio.play().then(function() {
                        updatePlayState(true);
                    }).catch(function(err) {
                        console.warn('Interacción requerida para reproducción:', err);
                    });
                } else {
                    audio.pause();
                    updatePlayState(false);
                }
            });
            
            audio.addEventListener('play', function() { updatePlayState(true); });
            audio.addEventListener('pause', function() { updatePlayState(false); });
            audio.addEventListener('ended', function() { updatePlayState(false); });
            
            // Intentar auto-reproducir respetando políticas de autoplay
            window.addEventListener('load', function() {
                var playPromise = audio.play();
                if (playPromise !== undefined) {
                    playPromise.then(function() {
                        updatePlayState(true);
                    }).catch(function() {
                        updatePlayState(false);
                    });
                }
            });
        })();
    </script>
    {% endif %}
</body>
</html>"""

        if HAS_JINJA2:
            template = jinja2.Template(template_str)
            return template.render(
                title=title,
                text=text,
                audio_url=audio_url or "",
                images=images or []
            )
        else:
            # Fallback simple sin jinja2
            html = template_str.replace("{{ title }}", title).replace("{{ text }}", text).replace("{{ audio_url }}", audio_url or "")
            return html

    def upload_slide_to_supabase(self, html_content: str, filename: str) -> Optional[str]:
        """
        Sube el slide HTML generado a Supabase Storage (bucket 'slides') y retorna la URL pública.
        """
        # 1. Guardar copia local de respaldo
        local_path = self.storage_path / filename
        try:
            with open(local_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
        except Exception as e:
            self.logger.warning(f"No se pudo guardar copia local de {filename}: {e}")

        # 2. Subida vía cliente oficial Supabase (SDK) si está configurado
        if self.supabase:
            try:
                storage_obj = self.supabase.storage.from_(self.bucket_name)
                # Intentar upload con upsert
                html_bytes = html_content.encode('utf-8')
                try:
                    storage_obj.upload(
                        path=filename,
                        file=html_bytes,
                        file_options={"content-type": "text/html; charset=utf-8", "upsert": "true"}
                    )
                except Exception:
                    # En versiones de supabase-py que no admiten file_options como dict
                    storage_obj.upload(path=filename, file=html_bytes)

                public_url = storage_obj.get_public_url(filename)
                if public_url:
                    self.logger.info(f"Slide subido exitosamente vía SDK: {public_url}")
                    return public_url
            except Exception as e:
                self.logger.warning(f"Fallo upload vía SDK, intentando vía REST API: {e}")

        # 3. Fallback directo a REST API de Supabase Storage
        if HAS_REQUESTS and self.supabase_key:
            try:
                upload_url = f"{self.supabase_url}/storage/v1/object/{self.bucket_name}/{filename}"
                headers = self._get_storage_headers("text/html; charset=utf-8")
                resp = requests.post(upload_url, headers=headers, data=html_content.encode('utf-8'), timeout=25)
                if resp.status_code in (200, 201):
                    public_url = f"{self.supabase_url}/storage/v1/object/public/{self.bucket_name}/{filename}"
                    self.logger.info(f"Slide subido exitosamente vía REST: {public_url}")
                    return public_url
                else:
                    self.logger.error(f"Error subiendo slide a Supabase REST ({resp.status_code}): {resp.text}")
            except Exception as e:
                self.logger.error(f"Excepción en subida REST a Supabase Storage: {e}")

        return None

    def process_article_slide(self, article_id: Union[int, str], title: str, text: str,
                              audio_url: str = "", image_urls: Optional[List[str]] = None) -> Optional[str]:
        """
        Procesa el ciclo completo para un artículo:
        1. Optimización de imágenes
        2. Renderizado del template HTML con voz y diseño
        3. Generación de nombre único de archivo
        4. Subida al bucket 'slides' de Supabase Storage
        5. Retorna la URL pública del slide
        """
        self.logger.info(f"Generando slide para artículo {article_id}: \"{title[:40]}...\"")

        try:
            images = self.process_images_for_slide(article_id, image_urls or [])

            html_content = self.create_slide_html(
                article_id=article_id,
                title=title,
                text=text,
                audio_url=audio_url or "",
                images=images
            )

            filename = self.generate_slide_filename(article_id, title)
            slide_url = self.upload_slide_to_supabase(html_content, filename)

            if slide_url:
                self.logger.info(f"Slide generado exitosamente para artículo {article_id}: {filename}")
                return slide_url
            else:
                self.logger.error(f"No se pudo subir el slide para el artículo {article_id}")
                return None

        except Exception as e:
            self.logger.error(f"Error procesando slide para artículo {article_id}: {e}")
            return None

    def process_articles_batch(self, article_ids: list) -> Dict[Union[int, str], Optional[str]]:
        """
        Procesa un lote de artículos por sus identificadores en Supabase.
        """
        results: Dict[Union[int, str], Optional[str]] = {}

        for article_id in article_ids:
            try:
                article = None
                # Obtener artículo de Supabase
                if self.supabase:
                    try:
                        resp = self.supabase.table('articles').select('*').eq('id', article_id).single().execute()
                        if resp and resp.data:
                            article = resp.data
                    except Exception as e:
                        self.logger.warning(f"Error consultando artículo {article_id} vía SDK: {e}")

                if not article and HAS_REQUESTS:
                    # Fallback REST
                    url = f"{self.supabase_url}/rest/v1/articles"
                    headers = {
                        'Authorization': f'Bearer {self.supabase_key}',
                        'apikey': self.supabase_key
                    }
                    r = requests.get(url, params={'id': f'eq.{article_id}', 'select': '*'}, headers=headers, timeout=15)
                    if r.status_code == 200 and r.json():
                        article = r.json()[0]

                if article:
                    # Recopilar todas las imágenes asociadas a la noticia
                    img_list = []
                    raw_images = article.get('images_urls')
                    if isinstance(raw_images, list):
                        for u in raw_images:
                            if u and isinstance(u, str) and u.startswith('http') and u not in img_list:
                                img_list.append(u)
                    elif isinstance(raw_images, str) and raw_images.startswith('['):
                        try:
                            import json
                            parsed = json.loads(raw_images)
                            if isinstance(parsed, list):
                                for u in parsed:
                                    if u and isinstance(u, str) and u.startswith('http') and u not in img_list:
                                        img_list.append(u)
                        except Exception:
                            pass

                    if article.get('image_url') and article['image_url'] not in img_list:
                        img_list.append(article['image_url'])
                    if article.get('og_image_url') and article['og_image_url'] not in img_list:
                        img_list.append(article['og_image_url'])

                    audio_url = article.get('audio_url') or ''

                    slide_url = self.process_article_slide(
                        article_id=article_id,
                        title=article.get('title') or 'Sin título',
                        text=article.get('text') or '',
                        audio_url=audio_url,
                        image_urls=img_list
                    )
                    results[article_id] = slide_url
                else:
                    self.logger.warning(f"No se encontró artículo {article_id} en la base de datos.")
                    results[article_id] = None

                time.sleep(1.5)

            except Exception as e:
                self.logger.error(f"Error procesando slide en lote para artículo {article_id}: {e}")
                results[article_id] = None

        return results
