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
    from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageOps
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False
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
    def estimate_audio_duration(self, text: str) -> float:
        """
        Calcula una estimación precisa de la duración del audio en segundos
        basada en la tasa de elocución estándar rioplatense (~125 palabras/min)
        más 1 segundo de silencio y 3 segundos de frase institucional.
        """
        words = len(text.strip().split()) if text else 0
        duration = (words / 2.08) + 1.0 + 3.0
        return max(20.0, min(round(duration, 1), 120.0))

    def detect_attention_center(self, image_bytes: bytes):
        """
        Determina el centro de atención de la imagen utilizando visión por computadora:
        - Si hay 1 persona: rostro de la persona (altura de los ojos).
        - Si hay más de 1 persona: punto medio equidistante entre todos los rostros.
        - Si es un objeto, vehículo o animal: centroide del cuerpo u objeto principal por saliencia.
        - Fallback editorial: (50.0, 45.0) proporción áurea.
        Retorna (focal_x_pct, focal_y_pct, method_desc).
        """
        if not HAS_CV2 or not HAS_NUMPY:
            return 50.0, 45.0, "fallback_sin_cv"

        try:
            nparr = np.frombuffer(image_bytes, np.uint8)
            img_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img_bgr is None:
                return 50.0, 45.0, "error_decodificacion"

            h, w = img_bgr.shape[:2]
            gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

            # 1. Detección de rostros humanos (frontal)
            face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
            faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(28, 28))

            if len(faces) == 1:
                x, y, fw, fh = faces[0]
                cx = (x + fw / 2.0) / w * 100.0
                cy = (y + fh * 0.45) / h * 100.0
                self.logger.info(f"Centro de atención: 1 rostro en ({cx:.1f}%, {cy:.1f}%)")
                return round(float(cx), 1), round(float(cy), 1), "rostro_persona"

            elif len(faces) > 1:
                # Punto medio equidistante entre todos los rostros detectados
                avg_x = sum((x + fw / 2.0) for (x, y, fw, fh) in faces) / len(faces)
                avg_y = sum((y + fh * 0.45) for (x, y, fw, fh) in faces) / len(faces)
                cx = (avg_x / w) * 100.0
                cy = (avg_y / h) * 100.0
                self.logger.info(f"Centro de atención: {len(faces)} rostros equidistante en ({cx:.1f}%, {cy:.1f}%)")
                return round(float(cx), 1), round(float(cy), 1), f"equidistante_{len(faces)}_personas"

            # 2. Detección de objeto / animal / sujeto principal mediante saliencia y contornos
            blurred = cv2.bilateralFilter(gray, 9, 75, 75)
            edges = cv2.Canny(blurred, 45, 140)
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
            dilated = cv2.dilate(edges, kernel, iterations=2)
            contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            if contours:
                min_area = 0.025 * w * h
                valid = [c for c in contours if cv2.contourArea(c) > min_area]
                if valid:
                    largest = max(valid, key=cv2.contourArea)
                    M = cv2.moments(largest)
                    if M["m00"] != 0:
                        obj_x = (M["m10"] / M["m00"]) / w * 100.0
                        obj_y = (M["m01"] / M["m00"]) / h * 100.0
                        self.logger.info(f"Centro de atención: objeto/animal saliente en ({obj_x:.1f}%, {obj_y:.1f}%)")
                        return round(float(obj_x), 1), round(float(obj_y), 1), "objeto_animal_saliencia"

        except Exception as e:
            self.logger.warning(f"Excepción detectando centro de atención: {e}")

        return 50.0, 45.0, "centro_editorial"

    def enhance_image_ai(self, image_bytes: bytes) -> bytes:
        """
        Mejora automáticamente brillo, contraste e intensidad (saturación) con perfil cinematográfico TV.
        """
        if not HAS_PIL:
            return image_bytes

        try:
            img = Image.open(io.BytesIO(image_bytes))
            if img.mode != 'RGB':
                img = img.convert('RGB')

            # 1. Autocontraste suave para estirar el rango dinámico
            img = ImageOps.autocontrast(img, cutoff=0.3)

            # 2. Brillo adaptativo basado en luminancia media
            if HAS_NUMPY:
                gray = img.convert('L')
                mean_lum = float(np.mean(np.array(gray)))
                if mean_lum < 85:
                    b_factor = 1.18  # Foto oscura: realce limpio
                elif mean_lum < 115:
                    b_factor = 1.08  # Foto algo apagada
                elif mean_lum > 185:
                    b_factor = 0.96  # Foto sobreexpuesta
                else:
                    b_factor = 1.03
            else:
                b_factor = 1.05

            img = ImageEnhance.Brightness(img).enhance(b_factor)

            # 3. Contraste cinematográfico (+10%)
            img = ImageEnhance.Contrast(img).enhance(1.10)

            # 4. Intensidad de color / saturación (+18% para impacto visual en pantallas)
            img = ImageEnhance.Color(img).enhance(1.18)

            # 5. Nitidez sutil para contornos definidos (+12%)
            img = ImageEnhance.Sharpness(img).enhance(1.12)

            buf = io.BytesIO()
            img.save(buf, format='JPEG', quality=88, optimize=True)
            return buf.getvalue()

        except Exception as e:
            self.logger.warning(f"Error en mejora de imagen: {e}")
            return image_bytes

    def upload_image_to_supabase(self, image_bytes: bytes, filename: str) -> Optional[str]:
        """Sube una imagen optimizada al bucket 'slides' de Supabase Storage."""
        if not HAS_REQUESTS or not self.supabase_key:
            return None
        try:
            upload_url = f"{self.supabase_url}/storage/v1/object/{self.bucket_name}/{filename}"
            headers = self._get_storage_headers("image/jpeg")
            resp = requests.post(upload_url, headers=headers, data=image_bytes, timeout=25)
            if resp.status_code in (200, 201):
                return f"{self.supabase_url}/storage/v1/object/public/{self.bucket_name}/{filename}"
        except Exception as e:
            self.logger.warning(f"No se pudo subir imagen optimizada {filename}: {e}")
        return None

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

    def process_images_for_slide(self, article_id: Union[int, str], image_urls: List[str]) -> List[Dict]:
        """
        Procesa, analiza y optimiza imágenes para el slide:
        1. Determina centro de atención (rostro único, punto medio de rostros, o cuerpo/objeto).
        2. Aplica mejora automática de brillo, contraste e intensidad de color.
        3. Aloja la versión optimizada en Supabase Storage.
        Retorna una lista de diccionarios con URL, coordenadas focales (focal_x, focal_y) y método.
        """
        processed_images: List[Dict] = []

        if not image_urls:
            return [{"url": "https://saladillovivo.vercel.app/default-og-image.png", "focal_x": 50.0, "focal_y": 45.0, "method": "default"}]

        for i, image_url in enumerate(image_urls):
            if not image_url:
                continue

            if image_url.startswith("http://") or image_url.startswith("https://"):
                try:
                    if HAS_REQUESTS:
                        resp = requests.get(image_url, timeout=12, headers={'User-Agent': 'Mozilla/5.0'})
                        if resp.status_code == 200:
                            raw_bytes = resp.content

                            # 1. Determinar centro de atención con visión artificial
                            focal_x, focal_y, method = self.detect_attention_center(raw_bytes)

                            # 2. Mejorar brillo, contraste e intensidad automáticamente
                            enhanced_bytes = self.enhance_image_ai(raw_bytes)

                            # 3. Subir imagen mejorada a Supabase Storage
                            img_hash = hashlib.md5(f"{article_id}_{i}_{focal_x}".encode()).hexdigest()[:8]
                            filename = f"img_opt_{article_id}_{i}_{img_hash}.jpg"
                            uploaded_url = self.upload_image_to_supabase(enhanced_bytes, filename)
                            final_url = uploaded_url or image_url

                            processed_images.append({
                                "url": final_url,
                                "focal_x": focal_x,
                                "focal_y": focal_y,
                                "method": method
                            })
                            continue

                except Exception as e:
                    self.logger.warning(f"Error procesando imagen {i} para artículo {article_id}: {e}")

            processed_images.append({
                "url": image_url,
                "focal_x": 50.0,
                "focal_y": 45.0,
                "method": "fallback"
            })

        return processed_images if processed_images else [{"url": "https://saladillovivo.vercel.app/default-og-image.png", "focal_x": 50.0, "focal_y": 45.0, "method": "default"}]

    def create_slide_html(self, article_id: Union[int, str], title: str, text: str,
                          audio_url: str, images: List[str], audio_duration: Optional[float] = None) -> str:
        """
        Genera el documento HTML del slide interactivo con diseño profesional TV-Grade.
        La animación Ken Burns se sincroniza para realizar 2 ciclos completos de zoom in/out
        durante la duración del audio del slide, con un zoom in 50% más profundo.
        En slides con múltiples fotos (galería), se adecua el tiempo de visualización de cada foto
        de acuerdo al tiempo total del slide determinado por la duración del audio generado.
        """
        if not audio_duration:
            audio_duration = self.estimate_audio_duration(text)

        total_photos = len(images) if images else 1
        photo_duration = round(audio_duration / total_photos, 1) if total_photos > 1 else audio_duration

        template_str = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }}</title>
    <style>
        :root {
            --slide-audio-duration: {{ (audio_duration | round(1)) if audio_duration else 36 }}s;
            --slide-photo-duration: {{ (photo_duration | round(1)) if photo_duration else 15 }}s;
        }

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

        /* Foto principal nítida con animación Ken Burns centrada en el punto de atención */
        .photo-main {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            object-fit: cover;
            will-change: transform;
            animation: {% if images and images | length > 1 %}kenBurnsPhoto var(--slide-photo-duration, 15s){% else %}kenBurnsZoom var(--slide-audio-duration, 36s){% endif %} ease-in-out infinite;
        }

        /*
           Animación Ken Burns para múltiples fotos (galería):
           Cada foto en pantalla realiza un acercamiento +50% más profundo (scale 1.27)
           directo a su centro de atención durante el tiempo proporcional
           asignado de acuerdo a la duración del audio.
        */
        @keyframes kenBurnsPhoto {
            0% {
                transform: scale(1.0);
            }
            50% {
                transform: scale(1.27);
            }
            100% {
                transform: scale(1.0);
            }
        }

        /*
           Animación Ken Burns para foto única:
           Efectúa exactamente 2 ciclos completos de Zoom In y Zoom Out
           durante el tiempo total de reproducción del audio.
           - Zoom In 50% más profundo: scale(1.0) -> scale(1.27) (aumento de delta de +18% a +27%)
           - Ciclo 1: 0% a 25% (Zoom In) -> 25% a 50% (Zoom Out)
           - Ciclo 2: 50% a 75% (Zoom In) -> 75% a 100% (Zoom Out)
        */
        @keyframes kenBurnsZoom {
            0% {
                transform: scale(1.0);
            }
            25% {
                transform: scale(1.27);
            }
            50% {
                transform: scale(1.0);
            }
            75% {
                transform: scale(1.27);
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
            <div class="photo-backdrop" style="background-image: url('{{ img.url if img.url is defined else img }}');"></div>
            <img src="{{ img.url if img.url is defined else img }}" alt="" class="photo-main"
                 style="transform-origin: {{ img.focal_x if img.focal_x is defined else 50 }}% {{ img.focal_y if img.focal_y is defined else 45 }}%; object-position: {{ img.focal_x if img.focal_x is defined else 50 }}% {{ img.focal_y if img.focal_y is defined else 45 }}%;"
                 onerror="this.src='https://saladillovivo.vercel.app/default-og-image.png'">
        </div>
        {% endfor %}
    </div>

    {% if audio_url %}
    <audio id="slideAudio" src="{{ audio_url }}" preload="auto" playsinline style="display:none;"></audio>
    {% endif %}

    <script>
        (function() {
            var audio = document.getElementById('slideAudio');
            var slides = document.querySelectorAll('.photo-slide');
            var slideInterval = null;

            function applyDuration(durSec) {
                if (!durSec || !isFinite(durSec) || durSec <= 0) return;
                var dur = Math.round(durSec * 10) / 10;
                document.documentElement.style.setProperty('--slide-audio-duration', dur + 's');

                // En slides con múltiples fotos, adecuar el tiempo de cada foto proporcionalmente al tiempo total del audio
                if (slides && slides.length > 1) {
                    var photoDur = Math.round((dur / slides.length) * 10) / 10;
                    document.documentElement.style.setProperty('--slide-photo-duration', photoDur + 's');

                    if (slideInterval) clearInterval(slideInterval);
                    var durationPerSlideMs = Math.round(photoDur * 1000);
                    var currentIndex = 0;
                    slideInterval = setInterval(function() {
                        slides[currentIndex].classList.remove('active');
                        currentIndex = (currentIndex + 1) % slides.length;
                        slides[currentIndex].classList.add('active');
                    }, durationPerSlideMs);
                } else {
                    document.documentElement.style.setProperty('--slide-photo-duration', dur + 's');
                }
            }

            // 1. Escuchar metadata del audio embebido
            if (audio) {
                var syncFromAudio = function() {
                    if (audio.duration && isFinite(audio.duration) && audio.duration > 0) {
                        applyDuration(audio.duration);
                    }
                };
                audio.addEventListener('loadedmetadata', syncFromAudio);
                audio.addEventListener('durationchange', syncFromAudio);
                audio.addEventListener('canplay', syncFromAudio);
                if (audio.readyState >= 1) {
                    syncFromAudio();
                }
            }

            // 2. Escuchar postMessage enviado desde el reproductor padre (VideoSection / NewsSlidePlayer)
            window.addEventListener('message', function(e) {
                if (e.data && (e.data.type === 'SET_AUDIO_DURATION' || e.data.action === 'SET_AUDIO_DURATION')) {
                    if (e.data.duration) {
                        applyDuration(e.data.duration);
                    }
                }
            });

            // Inicialización de rotación proporcional si hay múltiples fotos
            if (slides && slides.length > 1 && !slideInterval) {
                var initialPhotoDur = Math.round(({{ (photo_duration | round(1)) if photo_duration else 15 }}) * 1000);
                var currentIndex = 0;
                slideInterval = setInterval(function() {
                    slides[currentIndex].classList.remove('active');
                    currentIndex = (currentIndex + 1) % slides.length;
                    slides[currentIndex].classList.add('active');
                }, Math.max(2500, initialPhotoDur));
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
                images=images or [],
                audio_duration=audio_duration,
                photo_duration=photo_duration
            )
        else:
            # Fallback simple sin jinja2
            first_img = images[0] if images else {"url": "https://saladillovivo.vercel.app/default-og-image.png", "focal_x": 50, "focal_y": 45}
            img_url = first_img.get("url", first_img) if isinstance(first_img, dict) else first_img
            fx = first_img.get("focal_x", 50) if isinstance(first_img, dict) else 50
            fy = first_img.get("focal_y", 45) if isinstance(first_img, dict) else 45
            dur_str = str(round(audio_duration, 1) if audio_duration else 36)
            photo_dur_str = str(round(photo_duration, 1) if photo_duration else 15)
            html = template_str.replace("{{ title }}", title).replace("{{ text }}", text).replace("{{ audio_url }}", audio_url or "")
            html = html.replace("{{ (audio_duration | round(1)) if audio_duration else 36 }}", dur_str)
            html = html.replace("{{ (photo_duration | round(1)) if photo_duration else 15 }}", photo_dur_str)
            html = html.replace("{{ img.url if img.url is defined else img }}", img_url).replace("{{ img.focal_x if img.focal_x is defined else 50 }}", str(fx)).replace("{{ img.focal_y if img.focal_y is defined else 45 }}", str(fy))
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
                              audio_url: str = "", image_urls: Optional[List[str]] = None,
                              audio_duration: Optional[float] = None) -> Optional[str]:
        """
        Procesa el ciclo completo para un artículo:
        1. Optimización de imágenes
        2. Renderizado del template HTML con voz y diseño (Ken Burns 2 ciclos adaptados al audio)
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
                images=images,
                audio_duration=audio_duration
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
                    audio_dur = article.get('audio_duration')

                    slide_url = self.process_article_slide(
                        article_id=article_id,
                        title=article.get('title') or 'Sin título',
                        text=article.get('text') or '',
                        audio_url=audio_url,
                        image_urls=img_list,
                        audio_duration=audio_dur
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
