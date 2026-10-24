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
    def __init__(self, supabase_url: Optional[str] = None, supabase_key: Optional[str] = None, storage_path: str = "data/slides", voice: str = "es-AR-TomasNeural"):
        env_url, env_key = load_env_credentials()
        self.supabase_url = (supabase_url or env_url or "https://otwvfihzaznyjvjtkvvd.supabase.co").rstrip('/')
        self.supabase_key = supabase_key or env_key or ""
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.bucket_name = "slides"
        self.voice = voice  # es-AR-TomasNeural (Voz masculina español rioplatense argentina)
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
    <title>{{ title }}</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        html, body {
            width: 100%;
            height: 100%;
            overflow: hidden;
            background-color: #000000;
        }

        .fullscreen-container {
            position: absolute;
            top: 0;
            left: 0;
            width: 100vw;
            height: 100vh;
            overflow: hidden;
            background: #000000;
        }

        /* Capas de fotos con transición suave de opacidad (Crossfade) */
        .photo-slide {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            opacity: 0;
            transition: opacity 1.5s ease-in-out;
            pointer-events: none;
            overflow: hidden;
        }

        .photo-slide.active {
            opacity: 1;
            pointer-events: auto;
        }

        /* Fondo borroso ambiental para evitar letterboxing y llenar 100% */
        .photo-backdrop {
            position: absolute;
            top: -10%;
            left: -10%;
            width: 120%;
            height: 120%;
            background-size: cover;
            background-position: center;
            filter: blur(28px) brightness(0.4);
            transform: scale(1.15);
        }

        /* Foto principal nítida con animación Ken Burns continua ocupando el 100% */
        .photo-main {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            object-fit: cover;
            object-position: center;
            will-change: transform;
            animation: kenBurnsZoom 16s ease-in-out infinite alternate;
        }

        .photo-slide:nth-child(2) .photo-main {
            animation-duration: 20s;
            animation-delay: -4s;
        }

        .photo-slide:nth-child(3) .photo-main {
            animation-duration: 18s;
            animation-delay: -8s;
        }

        @keyframes kenBurnsZoom {
            0% {
                transform: scale(1.0);
            }
            50% {
                transform: scale(1.09);
            }
            100% {
                transform: scale(1.0);
            }
        }
    </style>
</head>
<body>
    <div class="fullscreen-container" id="slideshowContainer">
        {% for img in images %}
        <div class="photo-slide {% if loop.first %}active{% endif %}">
            <div class="photo-backdrop" style="background-image: url('{{ img }}');"></div>
            <img src="{{ img }}" alt="" class="photo-main" onerror="this.src='https://saladillovivo.vercel.app/default-og-image.png'">
        </div>
        {% endfor %}
    </div>

    {% if audio_url %}
    <audio id="slideAudio" src="{{ audio_url }}" preload="auto" playsinline style="display:none;"></audio>
    {% endif %}

    <script>
        (function() {
            var slides = document.querySelectorAll('.photo-slide');
            if (slides && slides.length > 1) {
                var currentIndex = 0;
                setInterval(function() {
                    slides[currentIndex].classList.remove('active');
                    currentIndex = (currentIndex + 1) % slides.length;
                    slides[currentIndex].classList.add('active');
                }, 5500);
            }
        })();
    </script>
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

                    body_text = (article.get('text') or '') + ' ' + (article.get('description') or '')
                    if '<img' in body_text:
                        import re
                        img_srcs = re.findall(r'<img[^>]+src=["\'](https?://[^"\']+)["\']', body_text, re.IGNORECASE)
                        for s in img_srcs:
                            if s not in img_list and not any(ext in s.lower() for ext in ['.svg', 'avatar', 'logo']):
                                img_list.append(s)

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
