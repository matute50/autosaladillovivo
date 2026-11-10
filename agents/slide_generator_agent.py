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
import re
import json
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

    def generate_default_visuals(self, title: str, text: str) -> Dict:
        """
        Genera metadatos estructurados para lower thirds y placa central TV-Grade
        en caso de que no hayan sido provistos por el modelo de IA.
        """
        t_lower = f"{title} {text}".lower()

        # Determinar Kicker / Categoría según temática local
        if any(k in t_lower for k in ['obras', 'paviment', 'asfalto', 'cordón', 'vial', 'iluminaci', 'bacheo']):
            kicker = "OBRAS PÚBLICAS"
        elif any(k in t_lower for k in ['polic', 'comisar', 'detuv', 'rob', 'aprehend', 'allanamiento', 'delit']):
            kicker = "POLICIALES"
        elif any(k in t_lower for k in ['salud', 'hospital', 'médic', 'caps', 'enferm', 'vacun']):
            kicker = "SALUD"
        elif any(k in t_lower for k in ['deport', 'fútbol', 'básquet', 'campeón', 'ciclism', 'automovilism']):
            kicker = "DEPORTES"
        elif any(k in t_lower for k in ['cultur', 'teatro', 'músic', 'cine', 'taller', 'fiesta']):
            kicker = "CULTURA"
        elif any(k in t_lower for k in ['educac', 'escuel', 'alumn', 'docent', 'jardín']):
            kicker = "EDUCACIÓN"
        elif any(k in t_lower for k in ['agro', 'rural', 'camp', 'cosech', 'ganad']):
            kicker = "AGRO Y PRODUCCIÓN"
        elif any(k in t_lower for k in ['municip', 'intendente', 'concej', 'salomón']):
            kicker = "MUNICIPIO"
        else:
            kicker = "SALADILLO VIVO"

        clean_title = re.sub(r'[\r\n]+', ' ', title).strip()
        words = clean_title.split()
        titular_apertura = " ".join(words[:10]).rstrip(' ,.:;')
        full_context = f"{clean_title}. {text}"

        quote_match = re.search(r'["“]([^"”]{12,140})["”]', full_context)
        stat_match = re.search(r'(\$\s*\d+[\d\.,]*\s*(?:millones?|mil|pesos|dólares)?|\b\d+[\d\.,]*\s*(?:millones?|cuadras?|viviendas?|hectáreas?|alumnos?|casos|efectivos|%|km)\b)', full_context, re.IGNORECASE)

        if quote_match:
            tipo_placa = "CITA"
            author = "DECLARACIÓN EN SALADILLO VIVO"
            if re.search(r'salom[oó]n|intendente', full_context, re.I):
                author = "JOSÉ LUIS SALOMÓN | INTENDENTE"
            elif re.search(r'comisar|polic', full_context, re.I):
                author = "AUTORIDADES POLICIALES"
            elif re.search(r'hospital|salud|director|m[eé]dic', full_context, re.I):
                author = "AUTORIDADES DE SALUD"

            placa = {
                "titulo": "DECLARACIÓN DESTACADA",
                "destacado": f'"{quote_match.group(1).strip()}"',
                "bajada": author
            }
        elif stat_match:
            tipo_placa = "DATO_NUMERICO"
            bajada_stat = clean_title
            if len(bajada_stat) > 75:
                bajada_stat = bajada_stat[:72].rsplit(' ', 1)[0] + '...'

            placa = {
                "titulo": "CIFRA DESTACADA",
                "destacado": stat_match.group(1).upper().strip(),
                "bajada": bajada_stat
            }
        else:
            tipo_placa = "RESUMEN"
            sentences = [s.strip() for s in re.split(r'[\.\n]+', text) if len(s.strip()) > 25]
            summary_text = sentences[0] if sentences else clean_title
            if len(summary_text) > 85:
                summary_text = summary_text[:82].rsplit(' ', 1)[0] + '...'
            placa = {
                "titulo": "SÍNTESIS DE LA NOTICIA",
                "destacado": clean_title,
                "bajada": summary_text
            }

        remate = "Más detalles en saladillovivo.com.ar"
        sentences = [s.strip() for s in re.split(r'[\.\n]+', text) if len(s.strip()) > 20]
        if len(sentences) >= 2:
            last_s = sentences[-1]
            last_words = last_s.split()
            if 3 <= len(last_words) <= 12:
                remate = " ".join(last_words).rstrip(' ,.:;')

        return {
            "kicker": kicker,
            "titular_apertura": titular_apertura,
            "tipo_placa": tipo_placa,
            "placa": placa,
            "remate": remate
        }

    def detect_banner_or_sign_title(self, gray, w, h):
        """
        Detecta el título principal dentro de un cartel, banner o fotografía de letrero:
        Identifica la línea de texto con mayor tamaño tipográfico (altura de caracteres),
        mayor extensión horizontal y ponderación de ubicación en el tercio/mitad superior.
        Retorna (title_x, title_y, found_title).
        """
        total_area = float(w * h)

        # Gradiente morfológico para aislar los trazos de caracteres tipográficos
        grad = cv2.morphologyEx(gray, cv2.MORPH_GRADIENT, cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)))
        _, thresh = cv2.threshold(grad, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)

        # Conectar caracteres horizontales para agrupar palabras en líneas de titular
        kernel_line = cv2.getStructuringElement(cv2.MORPH_RECT, (25, 4))
        connected = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel_line)
        contours, _ = cv2.findContours(connected, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

        candidates = []
        for c in contours:
            x, y, bw, bh = cv2.boundingRect(c)
            area = bw * bh
            # Descartar marcos exteriores gigantes (área > 35% del total o ancho > 95%)
            if area > 0.35 * total_area or bw > 0.95 * w or bh > 0.90 * h:
                continue

            ratio = bw / float(bh) if bh > 0 else 0
            # Bloque de texto válido para titular: ratio horizontal >= 1.3 y altura mínima apreciable
            if ratio >= 1.3 and (0.015 * h <= bh <= 0.25 * h) and (0.001 * total_area <= area <= 0.22 * total_area):
                y_center_pct = (y + bh / 2.0) / float(h)
                # Bonificación para la mitad superior y media donde se ubican los títulos principales
                pos_bonus = 1.40 if (0.10 <= y_center_pct <= 0.58) else 0.85
                # La altura del texto al cuadrado da prioridad exponencial al tamaño tipográfico del titular
                importance = (bh ** 2) * bw * pos_bonus
                candidates.append((importance, x, y, bw, bh))

        if candidates:
            # Agrupar fragmentos de la misma línea de titular (mismo nivel Y)
            candidates.sort(key=lambda item: item[0], reverse=True)
            best_imp, tx, ty, tbw, tbh = candidates[0]

            same_line = [c for c in candidates if abs((c[2] + c[4]/2.0) - (ty + tbh/2.0)) < (tbh * 0.75)]
            if same_line:
                min_x = min(c[1] for c in same_line)
                max_x = max(c[1] + c[3] for c in same_line)
                avg_y = sum(c[2] + c[4]/2.0 for c in same_line) / len(same_line)
                cx = ((min_x + max_x) / 2.0) / float(w) * 100.0
                cy = avg_y / float(h) * 100.0
            else:
                cx = (tx + tbw / 2.0) / float(w) * 100.0
                cy = (ty + tbh / 2.0) / float(h) * 100.0

            # Clampeo de seguridad para que el título no quede pegado a bordes extremos
            cx = max(18.0, min(cx, 82.0))
            cy = max(18.0, min(cy, 75.0))
            return round(cx, 1), round(cy, 1), True

        return 50.0, 38.0, False

    def detect_attention_center(self, image_bytes: bytes, image_url: str = ""):
        """
        Determina con IA y visión por computadora el punto de atención, encuadre y tipo de composición:

        1. PERSONAS / ROSTROS (Prioridad Absoluta):
           - Si hay una o varias personas, el foco siempre son las personas por sobre otros objetos.
           - Calcula el centro del grupo/persona y aplica control de Headroom visual:
             evita "techo" excesivo anclando el foco vertical entre el 33% y 46% (tercio superior cinematográfico),
             garantizando equilibrio visual entre la imagen original y el zoom in.

        2. BANNERS, AFICHES O FOTOGRAFÍAS A CARTELES/BANNERS:
           - Si se trata de un banner digital o de una FOTOGRAFÍA TOMADA A UN CARTEL O BANNER:
             detecta el TÍTULO PRINCIPAL del cartel/banner y lo establece como centro de atención.
             Aplica la regla de contención del 100% de superficie para que la información permanezca
             completamente visible sin recortes en la animación Ken Burns.

        3. EDIFICIOS / FACHADAS:
           - Detecta carteles o leyendas en la fachada y centra el zoom in sobre la leyenda.
           - Si no hay cartel, encuadra con equilibrio visual arquitectónico en la fachada.

        Retorna: (focal_x_pct, focal_y_pct, is_banner, method_desc)
        """
        if not HAS_CV2 or not HAS_NUMPY:
            return 50.0, 45.0, False, "fallback_sin_cv"

        try:
            nparr = np.frombuffer(image_bytes, np.uint8)
            img_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img_bgr is None:
                return 50.0, 45.0, False, "error_decodificacion"

            h, w = img_bgr.shape[:2]
            gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
            total_area = float(w * h)

            # ==================================================================
            # 1. PERSONAS / ROSTROS (PRIORIDAD ABSOLUTA SOBRE CUALQUIER OTRO OBJETO)
            # ==================================================================
            face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
            profile_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_profileface.xml')
            upperbody_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_upperbody.xml')

            faces = list(face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(28, 28)))
            if not faces and not profile_cascade.empty():
                profiles = profile_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(28, 28))
                if len(profiles) > 0:
                    faces = list(profiles)

            if faces:
                # Centro horizontal ponderado de todos los rostros del grupo
                min_x = min(f[0] for f in faces)
                max_x = max(f[0] + f[2] for f in faces)
                group_center_x = (min_x + max_x) / 2.0
                focal_x = (group_center_x / w) * 100.0

                # Headroom visual cinematográfico inteligente:
                # Evita dejar excesivo espacio de 'techo' arriba de las cabezas al hacer zoom in.
                # Se toma el tope del rostro más alto y se desciende hacia la línea clavicular/pecho
                # para que al hacer zoom la cabeza quede en el tercio superior armónico (33% - 46%)
                highest_face_top = min(f[1] for f in faces)
                avg_face_height = sum(f[3] for f in faces) / len(faces)
                target_y = highest_face_top + (avg_face_height * 0.90)
                focal_y = (target_y / h) * 100.0

                # Clampeo de equilibrio visual para evitar techos excesivos
                focal_y = max(33.0, min(focal_y, 46.0))
                focal_x = max(20.0, min(focal_x, 80.0))

                desc = f"personas_{len(faces)}_rostros_headroom_balance"
                self.logger.info(f"Centro de atención: {desc} en ({focal_x:.1f}%, {focal_y:.1f}%)")
                return round(float(focal_x), 1), round(float(focal_y), 1), False, desc

            # Detección de personas mediante torso superior si los rostros no son frontales
            if not upperbody_cascade.empty():
                bodies = upperbody_cascade.detectMultiScale(gray, scaleFactor=1.15, minNeighbors=3, minSize=(60, 60))
                if len(bodies) > 0:
                    b = max(bodies, key=lambda x: x[2] * x[3])
                    bx = (b[0] + b[2] / 2.0) / w * 100.0
                    by = (b[1] + b[3] * 0.35) / h * 100.0
                    by = max(33.0, min(by, 46.0))
                    bx = max(20.0, min(bx, 80.0))
                    self.logger.info(f"Centro de atención: persona torso en ({bx:.1f}%, {by:.1f}%)")
                    return round(float(bx), 1), round(float(by), 1), False, "persona_cuerpo_superior"

            # ==================================================================
            # 2. BANNERS, AFICHES O FOTOGRAFÍAS A CARTELES / BANNERS
            # ==================================================================
            # Detección de densidad morfológica de texto y caracteres
            grad = cv2.morphologyEx(gray, cv2.MORPH_GRADIENT, cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)))
            _, thresh = cv2.threshold(grad, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
            kernel_text = cv2.getStructuringElement(cv2.MORPH_RECT, (17, 3))
            text_blobs = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel_text)
            contours, _ = cv2.findContours(text_blobs, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            text_area_sum = 0
            candidate_signs = []
            for c in contours:
                area = cv2.contourArea(c)
                if area > 0.002 * total_area:
                    text_area_sum += area
                    x_c, y_c, w_c, h_c = cv2.boundingRect(c)
                    ratio = w_c / float(h_c)
                    # Signboard / Cartel típico de fachada: ancho > alto (ratio 1.8 a 8.5)
                    if 1.8 <= ratio <= 8.5 and (0.008 * total_area < area < 0.22 * total_area):
                        candidate_signs.append((area, x_c, y_c, w_c, h_c))

            text_coverage = text_area_sum / total_area
            aspect_ratio = w / float(h)
            url_lower = image_url.lower()

            is_banner_keyword = any(k in url_lower for k in [
                'banner', 'flyer', 'afiche', 'cartel', 'promo', 'sorteo', 'programa',
                'taller', 'inscripcion', 'necrolo', 'farmacia', 'cuadro', 'comunicado', 'aviso',
                'letrero', 'pasacalle', 'folleto'
            ])

            # Detectar si es un banner/afiche directo O una fotografía tomada a un cartel/banner
            is_direct_banner = is_banner_keyword or text_coverage > 0.07 or (aspect_ratio < 1.15 and text_coverage > 0.035)

            # Buscar si existe una estructura rectangular dominante correspondiente a un cartel fotografiado
            is_photo_of_banner = False
            if not is_direct_banner and text_coverage > 0.025:
                # Buscar paneles rectangulares grandes
                thresh_inv = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2)
                panel_contours, _ = cv2.findContours(thresh_inv, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
                for pc in panel_contours:
                    pa = cv2.contourArea(pc)
                    if 0.15 * total_area < pa < 0.85 * total_area:
                        peri = cv2.arcLength(pc, True)
                        approx = cv2.approxPolyDP(pc, 0.04 * peri, True)
                        if len(approx) == 4:  # Cuadrilátero / Cartel fotografiado
                            is_photo_of_banner = True
                            break

            if is_direct_banner or is_photo_of_banner:
                # Detectar con IA el TÍTULO PRINCIPAL del cartel/banner para fijarlo como centro de atención
                title_x, title_y, found_title = self.detect_banner_or_sign_title(gray, w, h)
                focal_x = title_x if found_title else 50.0
                focal_y = title_y if found_title else 38.0

                desc = "foto_a_cartel_titulo_principal" if is_photo_of_banner else "banner_afiche_titulo_principal"
                self.logger.info(f"Centro de atención: {desc} en ({focal_x:.1f}%, {focal_y:.1f}%). Criterio banner 100% visible.")
                # Si es banner digital directo o el cartel ocupa casi todo el plano, activar contención 100%
                return focal_x, focal_y, True, desc

            # ==================================================================
            # 3. EDIFICIOS / FACHADAS (Búsqueda de cartel, letrero o leyenda)
            # ==================================================================
            if candidate_signs:
                # Seleccionar el cartel más prominente y centrado en la fachada
                candidate_signs.sort(key=lambda s: s[0], reverse=True)
                _, sx, sy, sw, sh = candidate_signs[0]
                sign_x = (sx + sw / 2.0) / w * 100.0
                sign_y = (sy + sh / 2.0) / h * 100.0
                # Clampeo para mantener encuadre armónico de la fachada
                sign_x = max(25.0, min(sign_x, 75.0))
                sign_y = max(25.0, min(sign_y, 65.0))
                self.logger.info(f"Centro de atención: cartel/leyenda en fachada en ({sign_x:.1f}%, {sign_y:.1f}%)")
                return round(float(sign_x), 1), round(float(sign_y), 1), False, "edificio_cartel_leyenda"

            # ==================================================================
            # 4. FACHADA SIN CARTEL o PAISAJE / GENERAL: Equilibrio visual armónico
            # ==================================================================
            # Saliencia suave si hay un objeto claramente dominante
            blurred = cv2.bilateralFilter(gray, 9, 75, 75)
            edges = cv2.Canny(blurred, 45, 140)
            dilated = cv2.dilate(edges, cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5)), iterations=2)
            salient_contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            if salient_contours:
                valid = [c for c in salient_contours if cv2.contourArea(c) > 0.04 * total_area]
                if valid:
                    largest = max(valid, key=cv2.contourArea)
                    M = cv2.moments(largest)
                    if M["m00"] != 0:
                        obj_x = (M["m10"] / M["m00"]) / w * 100.0
                        obj_y = (M["m01"] / M["m00"]) / h * 100.0
                        obj_x = max(25.0, min(obj_x, 75.0))
                        obj_y = max(35.0, min(obj_y, 55.0))
                        self.logger.info(f"Centro de atención: objeto saliente en ({obj_x:.1f}%, {obj_y:.1f}%)")
                        return round(float(obj_x), 1), round(float(obj_y), 1), False, "fachada_objeto_saliencia"

        except Exception as e:
            self.logger.warning(f"Excepción detectando centro de atención: {e}")

        return 50.0, 48.0, False, "fachada_equilibrio_visual"

    def enhance_image_ai(self, image_bytes: bytes) -> bytes:
        """
        Mejora automáticamente brillo, contraste e intensidad (saturación) con perfil cinematográfico TV
        y garantiza alta resolución Full HD sin artefactos de compresión.
        """
        if not HAS_PIL:
            return image_bytes

        try:
            img = Image.open(io.BytesIO(image_bytes))
            if img.mode != 'RGB':
                img = img.convert('RGB')

            # Si la imagen posee dimensiones bajas (< 1200px de ancho y < 800px de alto),
            # reescalarla a Full HD cinematográfico con interpolación Lanczos de alta fidelidad
            orig_w, orig_h = img.size
            if orig_w < 1200 and orig_h < 800 and orig_w > 0 and orig_h > 0:
                scale = min(1920 / orig_w, 1080 / orig_h)
                if scale > 1.0:
                    new_w = int(orig_w * scale)
                    new_h = int(orig_h * scale)
                    resampling = getattr(getattr(Image, 'Resampling', Image), 'LANCZOS', Image.BICUBIC)
                    img = img.resize((new_w, new_h), resample=resampling)

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
            # CALIDAD CINEMATOGRÁFICA MÁXIMA Full HD (quality=95, subsampling=0 para cero artefactos en TV)
            img.save(buf, format='JPEG', quality=95, optimize=True, subsampling=0)
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
        Convierte texto a audio con acento rioplatense auténtico.
        Motor EXCLUSIVO: Voxtral TTS (voz femenina Elena voice_483) + preprocesamiento
        fonético (SOUL.md + skill tts-rioplatense-phonetics).
        Prohibido: Edge TTS / gTTS / Gemini TTS (directiva del usuario).
        """
        if not text:
            return None

        clean_text = text.replace('\n', ' ').strip()
        if len(clean_text) > 4000:
            clean_text = clean_text[:4000].rsplit('.', 1)[0] + "."

        try:
            from saladillo_tts_preprocessor import generate_audio
            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp_file:
                temp_output = tmp_file.name
            try:
                generate_audio(clean_text, temp_output)
                if os.path.exists(temp_output) and os.path.getsize(temp_output) > 1000:
                    with open(temp_output, 'rb') as f:
                        audio_bytes = f.read()
                    self.logger.info(f"Voz rioplatense Voxtral (Elena, femenina) sintetizada: {len(audio_bytes)} bytes")
                    return audio_bytes
            finally:
                if os.path.exists(temp_output):
                    try:
                        os.unlink(temp_output)
                    except Exception:
                        pass
        except Exception as e:
            self.logger.error(f"Voxtral TTS en slides falló: {e}")
        return None

    def upload_audio_to_supabase(self, audio_bytes: bytes, filename: str) -> Optional[str]:
        """Sube un archivo de audio MP3 al bucket 'audios' de Supabase Storage."""
        if not HAS_REQUESTS or not self.supabase_key or not audio_bytes:
            return None
        try:
            if self.supabase:
                try:
                    storage_obj = self.supabase.storage.from_("audios")
                    try:
                        storage_obj.upload(
                            path=filename,
                            file=audio_bytes,
                            file_options={"content-type": "audio/mpeg", "upsert": "true"}
                        )
                    except Exception:
                        storage_obj.upload(path=filename, file=audio_bytes)
                    public_url = storage_obj.get_public_url(filename)
                    if public_url:
                        return public_url
                except Exception as e:
                    self.logger.warning(f"Fallo upload audio vía SDK: {e}")

            upload_url = f"{self.supabase_url}/storage/v1/object/audios/{filename}"
            headers = self._get_storage_headers("audio/mpeg")
            resp = requests.post(upload_url, headers=headers, data=audio_bytes, timeout=25)
            if resp.status_code in (200, 201):
                return f"{self.supabase_url}/storage/v1/object/public/audios/{filename}"
        except Exception as e:
            self.logger.warning(f"Error subiendo audio a Supabase Storage: {e}")
        return None

    def process_images_for_slide(self, article_id: Union[int, str], image_urls: List[str]) -> List[Dict]:
        """
        Procesa, analiza y optimiza imágenes para el slide garantizando MÁXIMA RESOLUCIÓN FULL HD:
        1. Desescala URLs de WordPress a la versión original limpia sin sufijos de recorte (-80x80, etc.).
        2. Determina centro de atención con visión artificial (rostro, equidistante o saliente).
        3. Aplica reescalado inteligente Lanczos a Full HD y realce de imagen cinematográfico TV.
        4. Aloja la versión optimizada en Supabase Storage (JPEG Q95 subsampling=0).
        Retorna una lista de diccionarios con URL, coordenadas focales (focal_x, focal_y) y método.
        """
        processed_images: List[Dict] = []

        if not image_urls:
            return [{"url": "https://saladillovivo.vercel.app/default-og-image.png", "focal_x": 50.0, "focal_y": 45.0, "method": "default", "enable_ken_burns": True}]

        for i, image_url in enumerate(image_urls):
            if not image_url or not isinstance(image_url, str):
                continue

            # Descartar avatares, logos o miniaturas explícitas que no sean contenido del artículo
            lower_url = image_url.lower()
            if any(k in lower_url for k in ['gravatar', 'avatar', 'logo', 'icon', 'pixel', 'banner']):
                continue

            if image_url.startswith("http://") or image_url.startswith("https://"):
                try:
                    # Desescalar a URL nativa Full HD sin sufijos de recorte de WordPress
                    clean_hd_url = re.sub(r'-\d+x\d+(\.(?:webp|jpg|jpeg|png))(?:\?.*)?$', r'\1', image_url, flags=re.I)
                    # Quitar params de resize en Jetpack/Photon
                    if '?' in clean_hd_url:
                        base_u, q_u = clean_hd_url.split('?', 1)
                        kept = [p for p in q_u.split('&') if not p.lower().startswith(('resize=', 'fit=', 'w=', 'h=', 'strip='))]
                        clean_hd_url = base_u + ('?' + '&'.join(kept) if kept else '')

                    # Intentar descargar la versión Full HD primero, luego fallback a la original
                    candidate_urls = [clean_hd_url] if clean_hd_url != image_url else [image_url]
                    if clean_hd_url != image_url:
                        candidate_urls.append(image_url)

                    resp = None
                    downloaded_url = image_url
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
                        'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8'
                    }

                    if HAS_REQUESTS:
                        for cand in candidate_urls:
                            try:
                                r = requests.get(cand, timeout=14, headers=headers)
                                if r.status_code == 200 and len(r.content) > 1500:
                                    resp = r
                                    downloaded_url = cand
                                    break
                            except Exception:
                                pass

                    if resp and resp.status_code == 200:
                        raw_bytes = resp.content

                        # 0. Ken Burns habilitado siempre: la imagen es mejorada y reescalada a Full HD con Lanczos
                        enable_kb = True

                        # 1. Determinar centro de atención, encuadre y tipo con IA / visión por computadora
                        focal_x, focal_y, is_banner, method = self.detect_attention_center(raw_bytes, downloaded_url)

                        # 2. Mejorar brillo, contraste e intensidad en resolución Full HD
                        enhanced_bytes = self.enhance_image_ai(raw_bytes)

                        # 3. Subir imagen Full HD optimizada a Supabase Storage
                        img_hash = hashlib.md5(f"{article_id}_{i}_{focal_x}_{is_banner}".encode()).hexdigest()[:8]
                        filename = f"img_opt_{article_id}_{i}_{img_hash}.jpg"
                        uploaded_url = self.upload_image_to_supabase(enhanced_bytes, filename)
                        final_url = uploaded_url or downloaded_url

                        processed_images.append({
                            "url": final_url,
                            "focal_x": focal_x,
                            "focal_y": focal_y,
                            "is_banner": is_banner,
                            "method": method,
                            "enable_ken_burns": enable_kb
                        })
                        continue

                except Exception as e:
                    self.logger.warning(f"Error procesando imagen {i} para artículo {article_id}: {e}")

            # Fallback seguro con desescalado a Full HD
            fallback_url = re.sub(r'-\d+x\d+(\.(?:webp|jpg|jpeg|png))(?:\?.*)?$', r'\1', image_url, flags=re.I)
            is_fallback_banner = any(k in image_url.lower() for k in ['banner', 'flyer', 'afiche', 'sorteo', 'promo'])
            processed_images.append({
                "url": fallback_url,
                "focal_x": 50.0,
                "focal_y": 48.0,
                "is_banner": is_fallback_banner,
                "method": "fallback",
                "enable_ken_burns": True
            })

        return processed_images if processed_images else [{"url": "https://saladillovivo.vercel.app/default-og-image.png", "focal_x": 50.0, "focal_y": 45.0, "is_banner": False, "method": "default", "enable_ken_burns": True}]

    def create_slide_html(self, article_id: Union[int, str], title: str, text: str,
                          audio_url: str, images: List[str], audio_duration: Optional[float] = None,
                          visuals: Optional[Dict] = None) -> str:
        """
        Genera el documento HTML del slide interactivo con diseño profesional TV-Grade.
        La animación Ken Burns se sincroniza para realizar 2 ciclos completos de zoom in/out
        durante la duración del audio del slide, con un zoom in cinematográfico continuo.
        Incluye Lower Thirds flotantes dinámicos de apertura y remate, y Placa Central con efecto
        Rack Focus generados por IA, adaptándose en 3 actos (>8.5s) o modo flash directo (<=8.5s).
        """
        if not audio_duration or audio_duration <= 0:
            audio_duration = self.estimate_audio_duration(text)

        default_v = self.generate_default_visuals(title, text)
        if not visuals or not isinstance(visuals, dict):
            visuals = default_v
        else:
            for k, v in default_v.items():
                if k not in visuals or not visuals[k]:
                    visuals[k] = v
            if isinstance(visuals.get('placa'), dict) and isinstance(default_v.get('placa'), dict):
                for pk, pv in default_v['placa'].items():
                    if pk not in visuals['placa'] or not visuals['placa'][pk]:
                        visuals['placa'][pk] = pv

        total_photos = len(images) if images else 1
        photo_duration = round(audio_duration / total_photos, 1) if total_photos > 1 else audio_duration

        template_str = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }}</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Montserrat:ital,wght@0,500;0,700;0,800;0,900;1,600&display=swap" rel="stylesheet">
    <style>
        :root {
            --slide-audio-duration: {{ (audio_duration | round(1)) if audio_duration else 36 }}s;
            --slide-photo-duration: {{ (photo_duration | round(1)) if photo_duration else 15 }}s;
            --color-primary: #003399;
            --color-primary-light: #0055ff;
            --color-accent-sky: #38bdf8;
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
            font-family: 'Century Gothic', 'Montserrat', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            -webkit-font-smoothing: antialiased;
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
            image-rendering: high-quality;
            image-rendering: -webkit-optimize-contrast;
            backface-visibility: hidden;
            transform: translateZ(0);
            will-change: transform;
            animation: {% if images and images | length > 1 %}kenBurnsPhoto var(--slide-photo-duration, 15s){% else %}kenBurnsZoom var(--slide-audio-duration, 36s){% endif %} ease-in-out infinite;
        }

        /* BANNERS / AFICHES (Contenidos con zoom elegante continuo) */
        .photo-slide.is-banner .photo-main {
            object-fit: contain !important;
            animation: kenBurnsBanner {% if images and images | length > 1 %}var(--slide-photo-duration, 15s){% else %}var(--slide-audio-duration, 36s){% endif %} ease-in-out infinite alternate !important;
        }

        @keyframes kenBurnsBanner {
            0% { transform: scale(1.0); }
            50% { transform: scale(1.06); }
            100% { transform: scale(1.0); }
        }

        @keyframes kenBurnsPhoto {
            0% { transform: scale(1.0); }
            50% { transform: scale(1.22); }
            100% { transform: scale(1.0); }
        }

        /*
           Animación Ken Burns adaptada a la duración exacta del audio
           Efectúa exactamente 2 ciclos completos de Zoom In y Zoom Out
           durante el tiempo de reproducción del audio.
        */
        @keyframes kenBurnsZoom {
            0% { transform: scale(1.0); }
            25% { transform: scale(1.22); }
            50% { transform: scale(1.0); }
            75% { transform: scale(1.22); }
            100% { transform: scale(1.0); }
        }

        /* ==========================================================================
           LOWER THIRD FLOTANTE (Acto 1 & 3: Apertura y Remate)
           ========================================================================== */
        .floating-lower-third {
            position: absolute;
            bottom: 5.5%;
            left: 4.5%;
            max-width: 88%;
            min-width: 260px;
            z-index: 20;
            background: rgba(6, 12, 28, 0.90);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            border: 1px solid rgba(255, 255, 255, 0.14);
            border-left: 4px solid var(--color-primary);
            border-radius: 12px;
            padding: 10px 18px 10px 18px;
            box-shadow: 0 12px 32px rgba(0, 0, 0, 0.75), 0 0 0 1px rgba(0, 51, 153, 0.35);
            transition: opacity 0.6s cubic-bezier(0.16, 1, 0.3, 1),
                        transform 0.6s cubic-bezier(0.16, 1, 0.3, 1);
            will-change: opacity, transform;
        }

        .floating-lower-third.hidden-stage {
            opacity: 0;
            transform: translateY(14px) scale(0.97);
            pointer-events: none;
        }

        .lt-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 12px;
            margin-bottom: 6px;
        }

        .lt-badge {
            display: inline-flex;
            align-items: center;
            background: var(--color-primary);
            color: #ffffff;
            font-size: clamp(0.65rem, 1.2vw, 0.78rem);
            font-weight: 700;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            padding: 3px 8px;
            border-radius: 4px;
            box-shadow: 0 2px 8px rgba(0, 51, 153, 0.45);
        }

        .lt-brand {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            color: rgba(255, 255, 255, 0.92);
            font-size: clamp(0.65rem, 1.2vw, 0.76rem);
            font-weight: 800;
            letter-spacing: 0.1em;
        }

        .lt-live-dot {
            width: 7px;
            height: 7px;
            border-radius: 50%;
            background-color: #ef4444;
            box-shadow: 0 0 6px #ef4444;
            animation: pulseDot 2s infinite ease-in-out;
        }

        @keyframes pulseDot {
            0%, 100% { opacity: 1; transform: scale(1); }
            50% { opacity: 0.4; transform: scale(0.85); }
        }

        .lt-content-wrap {
            margin-bottom: 8px;
        }

        .lt-headline {
            color: #ffffff;
            font-size: clamp(0.95rem, 2.2vw, 1.4rem);
            font-weight: 700;
            line-height: 1.25;
            text-shadow: 0 2px 8px rgba(0, 0, 0, 0.8);
            transition: opacity 0.35s ease;
        }

        .lt-progress-track {
            width: 100%;
            height: 3px;
            background: rgba(255, 255, 255, 0.16);
            border-radius: 2px;
            overflow: hidden;
        }

        .lt-progress-bar {
            width: 0%;
            height: 100%;
            background: linear-gradient(90deg, var(--color-primary-light), var(--color-accent-sky));
            box-shadow: 0 0 8px rgba(56, 189, 248, 0.6);
            transition: width 0.1s linear;
        }

        /* ==========================================================================
           RACK FOCUS LAYER (Desenfoque cinemático sobre la foto sin frenar Ken Burns)
           ========================================================================== */
        .rack-focus-layer {
            position: absolute;
            inset: 0;
            z-index: 10;
            pointer-events: none;
            opacity: 0;
            background: rgba(3, 7, 18, 0);
            backdrop-filter: blur(0px);
            -webkit-backdrop-filter: blur(0px);
            transition: opacity 0.75s cubic-bezier(0.16, 1, 0.3, 1),
                        backdrop-filter 0.75s cubic-bezier(0.16, 1, 0.3, 1),
                        -webkit-backdrop-filter 0.75s cubic-bezier(0.16, 1, 0.3, 1),
                        background 0.75s cubic-bezier(0.16, 1, 0.3, 1);
            will-change: opacity, backdrop-filter, background;
        }

        .rack-focus-layer.active {
            opacity: 1;
            background: rgba(3, 7, 18, 0.72);
            backdrop-filter: blur(18px);
            -webkit-backdrop-filter: blur(18px);
        }

        /* ==========================================================================
           PLACA CENTRAL DE IMPACTO (Acto 2: Citas, Cifras o Síntesis)
           ========================================================================== */
        .central-card {
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%) scale(0.95);
            width: min(88%, 760px);
            max-height: 86%;
            z-index: 15;
            opacity: 0;
            pointer-events: none;
            background: rgba(6, 12, 28, 0.94);
            backdrop-filter: blur(28px);
            -webkit-backdrop-filter: blur(28px);
            border: 1px solid rgba(0, 85, 255, 0.4);
            border-top: 4px solid var(--color-primary);
            border-radius: 20px;
            padding: clamp(20px, 3.8vw, 36px) clamp(22px, 4.5vw, 44px);
            box-shadow: 0 24px 60px rgba(0, 0, 0, 0.85), 0 0 50px rgba(0, 51, 153, 0.35);
            text-align: center;
            transition: opacity 0.65s cubic-bezier(0.16, 1, 0.3, 1),
                        transform 0.65s cubic-bezier(0.16, 1, 0.3, 1);
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            will-change: opacity, transform;
        }

        .central-card.visible-stage {
            opacity: 1;
            pointer-events: auto;
            transform: translate(-50%, -50%) scale(1.0);
        }

        .card-top-bar {
            width: 100%;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 16px;
            margin-bottom: 16px;
            padding-bottom: 12px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.12);
        }

        .card-brand {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            color: #ffffff;
            font-size: clamp(0.7rem, 1.3vw, 0.85rem);
            font-weight: 800;
            letter-spacing: 0.12em;
        }

        .card-live-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background-color: #ef4444;
            box-shadow: 0 0 8px #ef4444;
            animation: pulseDot 2s infinite ease-in-out;
        }

        .card-badge {
            background: var(--color-primary);
            color: #ffffff;
            font-size: clamp(0.65rem, 1.2vw, 0.8rem);
            font-weight: 800;
            letter-spacing: 0.1em;
            text-transform: uppercase;
            padding: 4px 10px;
            border-radius: 4px;
            box-shadow: 0 2px 10px rgba(0, 51, 153, 0.5);
        }

        .card-context-title {
            color: var(--color-accent-sky);
            font-size: clamp(0.75rem, 1.4vw, 0.9rem);
            font-weight: 700;
            letter-spacing: 0.12em;
            text-transform: uppercase;
            margin-bottom: 12px;
        }

        .card-quote-icon {
            font-size: clamp(2.8rem, 6vw, 4.2rem);
            line-height: 0.6;
            color: var(--color-primary-light);
            margin-bottom: 10px;
            font-family: Georgia, serif;
            text-shadow: 0 2px 16px rgba(0, 85, 255, 0.6);
        }

        .card-quote-text {
            color: #ffffff;
            font-size: clamp(1.1rem, 2.5vw, 1.65rem);
            font-weight: 600;
            font-style: italic;
            line-height: 1.35;
            margin-bottom: 16px;
            text-shadow: 0 2px 10px rgba(0, 0, 0, 0.7);
        }

        .card-author-line {
            color: var(--color-accent-sky);
            font-size: clamp(0.8rem, 1.5vw, 1.05rem);
            font-weight: 800;
            letter-spacing: 0.08em;
            text-transform: uppercase;
        }

        .card-stat-number {
            color: #ffffff;
            font-size: clamp(2.4rem, 6vw, 4.5rem);
            font-weight: 900;
            letter-spacing: -0.02em;
            line-height: 1.05;
            margin-bottom: 14px;
            text-shadow: 0 4px 24px rgba(0, 85, 255, 0.7);
        }

        .card-stat-desc {
            color: rgba(255, 255, 255, 0.95);
            font-size: clamp(0.95rem, 2vw, 1.35rem);
            font-weight: 600;
            line-height: 1.35;
        }

        .card-headline-strong {
            color: #ffffff;
            font-size: clamp(1.15rem, 2.6vw, 1.7rem);
            font-weight: 800;
            line-height: 1.25;
            margin-bottom: 12px;
            text-shadow: 0 2px 10px rgba(0, 0, 0, 0.7);
        }

        .card-summary-desc {
            color: rgba(255, 255, 255, 0.92);
            font-size: clamp(0.9rem, 2vw, 1.25rem);
            font-weight: 500;
            line-height: 1.4;
        }

        .card-progress-track {
            width: 100%;
            height: 3px;
            background: rgba(255, 255, 255, 0.16);
            border-radius: 2px;
            margin-top: 22px;
            overflow: hidden;
        }

        .card-progress-bar {
            width: 0%;
            height: 100%;
            background: linear-gradient(90deg, var(--color-primary-light), var(--color-accent-sky));
            box-shadow: 0 0 10px rgba(56, 189, 248, 0.7);
            transition: width 0.1s linear;
        }
    </style>
</head>
<body>
    <div class="fullscreen-container" id="slideshowContainer">
        {% for img in images %}
        <div class="photo-slide {% if loop.first %}active{% endif %} {% if img.is_banner %}is-banner{% endif %}">
            <div class="photo-backdrop" style="background-image: url('{{ img.url if img.url is defined else img }}');"></div>
            <img src="{{ img.url if img.url is defined else img }}" alt="" class="photo-main"
                 style="transform-origin: {{ img.focal_x if img.focal_x is defined else 50 }}% {{ img.focal_y if img.focal_y is defined else 45 }}%; object-position: {{ img.focal_x if img.focal_x is defined else 50 }}% {{ img.focal_y if img.focal_y is defined else 45 }}%;"
                 onerror="this.src='https://saladillovivo.vercel.app/default-og-image.png'">
        </div>
        {% endfor %}
    </div>

    <!-- CAPA RACK FOCUS (DESENFOQUE CINEMÁTICO SOBRE LA FOTO) -->
    <div class="rack-focus-layer" id="rackFocusLayer"></div>

    <!-- PLACA CENTRAL DE IMPACTO (ACTO 2: Citas, Cifras o Síntesis) -->
    <div class="central-card" id="centralCard">
        <div class="card-top-bar">
            <div class="card-brand">
                <span class="card-live-dot"></span>
                SALADILLO VIVO
            </div>
            <div class="card-badge">{{ visuals.kicker }}</div>
        </div>

        {% if visuals.tipo_placa == 'CITA' %}
        <div class="card-quote-icon">“</div>
        <div class="card-quote-text">{{ visuals.placa.destacado }}</div>
        <div class="card-author-line">— {{ visuals.placa.bajada }}</div>
        {% elif visuals.tipo_placa == 'DATO_NUMERICO' %}
        <div class="card-context-title">{{ visuals.placa.titulo }}</div>
        <div class="card-stat-number">{{ visuals.placa.destacado }}</div>
        <div class="card-stat-desc">{{ visuals.placa.bajada }}</div>
        {% elif visuals.tipo_placa == 'PUNTOS_CLAVE' %}
        <div class="card-context-title">{{ visuals.placa.titulo }}</div>
        <div class="card-headline-strong">{{ visuals.placa.destacado }}</div>
        <div class="card-stat-desc">{{ visuals.placa.bajada }}</div>
        {% else %}
        <!-- RESUMEN EDITORIAL -->
        <div class="card-context-title">{{ visuals.placa.titulo }}</div>
        <div class="card-headline-strong">{{ visuals.placa.destacado }}</div>
        <div class="card-summary-desc">{{ visuals.placa.bajada }}</div>
        {% endif %}

        <div class="card-progress-track">
            <div class="card-progress-bar" id="cardProgressBar"></div>
        </div>
    </div>

    <!-- LOWER THIRD FLOTANTE (ACTO 1 Y ACTO 3) -->
    <div class="floating-lower-third" id="floatingLowerThird">
        <div class="lt-header">
            <span class="lt-badge" id="ltKicker">{{ visuals.kicker }}</span>
            <span class="lt-brand">
                <span class="lt-live-dot"></span>
                SALADILLO VIVO
            </span>
        </div>
        <div class="lt-content-wrap">
            <h2 class="lt-headline" id="ltHeadline">{{ visuals.titular_apertura }}</h2>
        </div>
        <div class="lt-progress-track">
            <div class="lt-progress-bar" id="ltProgressBar"></div>
        </div>
    </div>

    {% if audio_url %}
    <audio id="slideAudio" src="{{ audio_url }}" preload="auto" autoplay playsinline style="display:none;"></audio>
    {% endif %}

    <script>
        (function() {
            var audio = document.getElementById('slideAudio');
            var slides = document.querySelectorAll('.photo-slide');
            var rackFocus = document.getElementById('rackFocusLayer');
            var centralCard = document.getElementById('centralCard');
            var lowerThird = document.getElementById('floatingLowerThird');
            var ltHeadline = document.getElementById('ltHeadline');
            var ltProgressBar = document.getElementById('ltProgressBar');
            var cardProgressBar = document.getElementById('cardProgressBar');

            var titularApertura = {{ visuals.titular_apertura | tojson }};
            var remateCierre = {{ visuals.remate | tojson }};
            var estimatedDuration = {{ (audio_duration | round(1)) if audio_duration else 36 }};
            var activeDuration = estimatedDuration;
            var isShortMode = (activeDuration <= 8.5);
            var currentStage = 0; // 1: Apertura (Lower Third), 2: Placa Central, 3: Remate (Lower Third)
            var slideInterval = null;
            var hasParentUpdates = false;
            var startTime = performance.now();

            function updateTimeline(currentTime, totalDuration) {
                if (!totalDuration || totalDuration <= 0) return;
                var ratio = Math.max(0, Math.min(1.0, currentTime / totalDuration));

                if (isShortMode) {
                    // Modo Flash Directo (<= 8.5s): Lower third permanente, foto limpia con Ken Burns
                    if (currentStage !== 1) {
                        currentStage = 1;
                        if (lowerThird) lowerThird.classList.remove('hidden-stage');
                        if (ltHeadline) ltHeadline.textContent = titularApertura;
                        if (rackFocus) rackFocus.classList.remove('active');
                        if (centralCard) centralCard.classList.remove('visible-stage');
                    }
                    if (ltProgressBar) {
                        ltProgressBar.style.width = Math.min(100, Math.round(ratio * 100)) + '%';
                    }
                    return;
                }

                // Modo 3 Actos TV-Grade (> 8.5s)
                // ACTO 1 (0% a 28%): Foto nítida con Ken Burns + LOWER THIRD de apertura
                if (ratio < 0.28) {
                    if (currentStage !== 1) {
                        currentStage = 1;
                        if (rackFocus) rackFocus.classList.remove('active');
                        if (centralCard) centralCard.classList.remove('visible-stage');
                        if (lowerThird) lowerThird.classList.remove('hidden-stage');
                        if (ltHeadline) ltHeadline.textContent = titularApertura;
                    }
                    var actProgress = ratio / 0.28;
                    if (ltProgressBar) {
                        ltProgressBar.style.width = Math.min(100, Math.round(actProgress * 100)) + '%';
                    }
                }
                // ACTO 2 (28% a 72%): RACK FOCUS sobre la foto + PLACA CENTRAL EDITORIAL
                else if (ratio < 0.72) {
                    if (currentStage !== 2) {
                        currentStage = 2;
                        if (lowerThird) lowerThird.classList.add('hidden-stage');
                        if (rackFocus) rackFocus.classList.add('active');
                        if (centralCard) centralCard.classList.add('visible-stage');
                    }
                    var phaseRatio = (ratio - 0.28) / (0.72 - 0.28);
                    if (cardProgressBar) {
                        cardProgressBar.style.width = Math.min(100, Math.round(phaseRatio * 100)) + '%';
                    }
                }
                // ACTO 3 (72% a 100%): Retorno a foto nítida + LOWER THIRD con remate final
                else {
                    if (currentStage !== 3) {
                        currentStage = 3;
                        if (rackFocus) rackFocus.classList.remove('active');
                        if (centralCard) centralCard.classList.remove('visible-stage');
                        if (lowerThird) lowerThird.classList.remove('hidden-stage');
                        if (ltHeadline) ltHeadline.textContent = remateCierre;
                    }
                    var actProgress = (ratio - 0.72) / (1.0 - 0.72);
                    if (ltProgressBar) {
                        ltProgressBar.style.width = Math.min(100, Math.round(actProgress * 100)) + '%';
                    }
                }
            }

            function applyDuration(durSec) {
                if (!durSec || !isFinite(durSec) || durSec <= 0) return;
                activeDuration = Math.round(durSec * 10) / 10;
                isShortMode = (activeDuration <= 8.5);
                document.documentElement.style.setProperty('--slide-audio-duration', activeDuration + 's');

                if (slides && slides.length > 1) {
                    var photoDur = Math.round((activeDuration / slides.length) * 10) / 10;
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
                    document.documentElement.style.setProperty('--slide-photo-duration', activeDuration + 's');
                }
            }

            // 1. Reproducción de Audio Interno y Fallback de Autoplay
            if (audio) {
                audio.addEventListener('loadedmetadata', function() {
                    if (audio.duration && isFinite(audio.duration) && audio.duration > 0) {
                        applyDuration(audio.duration);
                    }
                });

                audio.addEventListener('timeupdate', function() {
                    if (!hasParentUpdates && audio.duration > 0) {
                        updateTimeline(audio.currentTime, audio.duration);
                    }
                });

                // Intentar reproducción automática
                var playPromise = audio.play();
                if (playPromise !== undefined) {
                    playPromise.then(function() {
                        console.log("Audio de slide reproduciendo exitosamente.");
                    }).catch(function(err) {
                        console.warn("Autoplay restringido por el navegador. Habilitando al interactuar:", err);
                        var unlockAudio = function() {
                            if (!hasParentUpdates) {
                                audio.play();
                            }
                            document.removeEventListener('click', unlockAudio);
                            document.removeEventListener('touchstart', unlockAudio);
                        };
                        document.addEventListener('click', unlockAudio, { once: true });
                        document.addEventListener('touchstart', unlockAudio, { once: true });
                    });
                }
            }

            // 2. Escuchar mensajes del reproductor padre (VideoSection / NewsSlidePlayer)
            window.addEventListener('message', function(e) {
                if (!e.data) return;
                if ((e.data.type === 'SET_AUDIO_DURATION' || e.data.action === 'SET_AUDIO_DURATION') && e.data.duration) {
                    applyDuration(e.data.duration);
                }
                if (e.data.type === 'AUDIO_TIME_UPDATE') {
                    hasParentUpdates = true;
                    // Si el reproductor padre ya está emitiendo el audio, silenciar audio interno para evitar eco
                    if (audio && !audio.muted) {
                        audio.muted = true;
                        audio.pause();
                    }
                    if (e.data.duration && isFinite(e.data.duration) && e.data.duration > 0) {
                        applyDuration(e.data.duration);
                    }
                    var cur = (typeof e.data.currentTime === 'number') ? e.data.currentTime : 0;
                    updateTimeline(cur, activeDuration);
                }
            });

            // 3. Reloj autónomo infalible de respaldo (garantiza que NUNCA se congele)
            function autonomousLoop(now) {
                if (!hasParentUpdates) {
                    if (audio && !audio.paused && audio.duration > 0) {
                        updateTimeline(audio.currentTime, audio.duration);
                    } else {
                        var elapsed = (now - startTime) / 1000;
                        updateTimeline(elapsed % (activeDuration + 0.1), activeDuration);
                    }
                }
                requestAnimationFrame(autonomousLoop);
            }
            requestAnimationFrame(autonomousLoop);

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
                photo_duration=photo_duration,
                visuals=visuals
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
            html = html.replace("{{ visuals.titular_apertura | tojson }}", json.dumps(visuals.get("titular_apertura", title)))
            html = html.replace("{{ visuals.remate | tojson }}", json.dumps(visuals.get("remate", "Más detalles en saladillovivo.com.ar")))
            html = html.replace("{{ visuals.kicker }}", visuals.get("kicker", "SALADILLO VIVO"))
            html = html.replace("{{ visuals.titular_apertura }}", visuals.get("titular_apertura", title))
            html = html.replace("{{ visuals.placa.destacado }}", str(visuals.get("placa", {}).get("destacado", title)))
            html = html.replace("{{ visuals.placa.bajada }}", str(visuals.get("placa", {}).get("bajada", "")))
            html = html.replace("{{ visuals.placa.titulo }}", str(visuals.get("placa", {}).get("titulo", "INFORMACIÓN")))
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
                              audio_duration: Optional[float] = None,
                              visuals: Optional[Dict] = None) -> Optional[str]:
        """
        Procesa el ciclo completo para un artículo:
        1. Verificación o generación de audio rioplatense (si falta audio_url)
        2. Optimización y análisis visual de imágenes (Ken Burns + IA focal point)
        3. Renderizado del template HTML con voz y diseño TV-Grade (Lower Thirds + Placa Central)
        4. Generación de nombre único de archivo
        5. Subida al bucket 'slides' de Supabase Storage
        6. Retorna la URL pública del slide
        """
        self.logger.info(f"Generando slide para artículo {article_id}: \"{title[:40]}...\"")

        try:
            # Si no viene audio_url, intentar sintetizarlo y subirlo a Storage
            if not audio_url:
                self.logger.info(f"Slide sin audio_url para artículo {article_id}. Generando voz rioplatense...")
                audio_bytes = self.text_to_speech_rioplatense(text)
                if audio_bytes:
                    audio_fn = f"audio_{article_id}_{hashlib.md5(text.encode()).hexdigest()[:8]}.mp3"
                    uploaded_audio = self.upload_audio_to_supabase(audio_bytes, audio_fn)
                    if uploaded_audio:
                        audio_url = uploaded_audio
                        self.logger.info(f"Audio generado y alojado para slide {article_id}: {audio_url}")

            if not audio_duration or audio_duration <= 0:
                audio_duration = self.estimate_audio_duration(text)

            images = self.process_images_for_slide(article_id, image_urls or [])

            html_content = self.create_slide_html(
                article_id=article_id,
                title=title,
                text=text,
                audio_url=audio_url or "",
                images=images,
                audio_duration=audio_duration,
                visuals=visuals
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
                        audio_duration=audio_dur,
                        visuals=article.get('slide_visuals')
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
