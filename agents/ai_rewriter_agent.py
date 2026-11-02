# -*- coding: utf-8 -*-
"""
agents/ai_rewriter_agent.py — Agente de Reescritura Periodística con IA (Free-First)
======================================================================================
Paso 3 del ciclo: Reestructura títulos, textos y metadatos de noticias scrapedas
bajo estricto estilo periodístico rioplatense bonaerense para Saladillo Vivo.

Características:
- Enfoque Free-First: prioriza proveedores gratuitos (GLM → Groq → Gemini → OpenRouter → OpenAI).
- Fallback heurístico local funcional sin APIs externas.
- Directivas editoriales para noticiero radial (TTS) y gancho de imagen (máx 6 palabras).
- Compatibilidad total con JSON estricto y respuestas flexibles de LLM.
"""

import os
import sys
import json
import re
import unicodedata
import logging
from datetime import datetime
from typing import Dict, Optional, List, Union

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

logger = logging.getLogger("AiRewriterAgent")
logger.setLevel(logging.INFO)


def load_env_variables():
    """Carga variables dando máxima prioridad al .env.local y .env del proyecto sobre el entorno."""
    env = dict(os.environ)
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    for filename in ['.env', '.env.local']:
        filepath = os.path.join(base_dir, filename)
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            k, v = line.split('=', 1)
                            env[k.strip()] = v.strip().strip('"\'')
            except Exception:
                pass

    return env


class AiRewriterAgent:
    """
    Agente de IA especializado en reescritura periodística local para Saladillo Vivo.
    Transforma noticias scrapedas en formatos listos para TTS (locución radial)
    y gancho de imagen (máx 6 palabras), con estilo rioplatense bonaerense.
    """
    def __init__(self):
        self.env = load_env_variables()
        self.providers = {
            'gemini': {
                'name': 'Google Gemini',
                'url': 'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent',
                'fallback_url': 'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent',
                'key': self.env.get('GEMINI_API_KEY') or self.env.get('GOOGLE_API_KEY') or self.env.get('NEXT_PUBLIC_GEMINI_API_KEY'),
                'priority': 1
            },
            'groq': {
                'name': 'Groq (GPT-OSS 20B)',
                'url': 'https://api.groq.com/openai/v1/chat/completions',
                'key': self.env.get('GROQ_API_KEY'),
                'model': self.env.get('GROQ_MODEL', 'openai/gpt-oss-20b'),
                'priority': 2
            },
            'glm': {
                'name': 'GLM (Zhipu AI)',
                'url': 'https://open.bigmodel.cn/api/paas/v4/chat/completions',
                'key': self.env.get('GLM_API_KEY') or self.env.get('ZHIPU_API_KEY'),
                'model': self.env.get('GLM_MODEL', 'glm-4.5-flash'),
                'priority': 3
            },
            'openrouter': {
                'name': 'OpenRouter Free Tier',
                'url': 'https://openrouter.ai/api/v1/chat/completions',
                'key': self.env.get('OPENROUTER_API_KEY'),
                'model': self.env.get('OPENROUTER_MODEL', 'nvidia/nemotron-3-ultra-550b-a55b:free'),
                'priority': 4
            },
            'openai': {
                'name': 'OpenAI',
                'url': 'https://api.openai.com/v1/chat/completions',
                'key': self.env.get('OPENAI_API_KEY'),
                'model': self.env.get('OPENAI_MODEL', 'gpt-4o-mini'),
                'priority': 5
            },
        }

    def _clamp_title_to_max_words(self, title: str, max_words: int = 8) -> str:
        """Limita un título al número máximo de palabras permitidas."""
        words = title.strip().split()
        if len(words) <= max_words:
            return title.strip()
        return " ".join(words[:max_words]).rstrip(' ,.:;')

    def create_prompt(self, title, content):
        """Genera el prompt periodístico estricto para estructurar la noticia."""
        return f"""Eres un periodista profesional y redactor jefe de "Saladillo Vivo", portal de noticias de Saladillo, Provincia de Buenos Aires.
Reestructura el siguiente despacho manteniendo fidelidad absoluta a los hechos, nombres, fechas y citas:

TÍTULO ORIGINAL:
{title}

CONTENIDO ORIGINAL:
{content}

FILTRO EDITORIAL REGIONAL ESTRICTO:
"Saladillo Vivo" publica ÚNICAMENTE noticias locales (Saladillo, Del Carril, Cazón, Polvaredas, Álvarez de Toledo) y regionales (partidos vecinos: Roque Pérez, 25 de Mayo, General Alvear, Las Flores, Lobos, Tapalqué, interior bonaerense).
Si el despacho corresponde a una noticia de orden NACIONAL o INTERNACIONAL sin anclaje local (ejemplos: política exterior o conflictos de otros países, inflación o economía nacional macro sin impacto local, fútbol de Primera División/AFA como Boca/River sin jugador local, lanzamientos comerciales de autos, farándula/espectáculos nacionales), DEBES RECHAZARLA respondiendo exactamente:
{{"es_local_regional": false, "motivo_rechazo": "Noticia nacional/internacional sin anclaje local"}}

Si la noticia SÍ es local o regional, incluye "es_local_regional": true y cumple las siguientes:

DIRECTIVAS DE REDACCIÓN PARA NOTICIERO RADIAL Y LOCUCIÓN GOOGLE TTS:

1. TITULAR RADIAL (GANCHO DIRECTO DE HASTA 12 PALABRAS):
   - El titular cumple función de gancho para el oyente: resume la esencia de la noticia de forma impactante y muy rápida.
   - Longitud: Debe leerse en menos de 3 o 4 segundos (MÁXIMO 12 PALABRAS, típicamente de 5 a 10 palabras).
   - Estructura fuerte en tiempo PRESENTE: Dale actualidad y urgencia (ej. "el intendente anuncia", "la policía detiene", "comienzan las obras"), incluso si el hecho ocurrió ayer.
   - Cero misterio ("sin gancho ciego"): No uses frases vacías tipo "Mirá lo que pasó". El oyente necesita saber de qué se trata inmediatamente.
   - Ejemplos:
     * Diario: "El Gobierno nacional anunció un nuevo paquete de medidas económicas tras la reunión de gabinete de ayer."
     * Radial correcto: "Nuevo ajuste: el Gobierno anuncia medidas económicas."
     * Local: "Obras viales: Saladillo repavimenta los accesos principales."

2. CUERPO DE LA NOTICIA RADIAL (35 A 45 SEGUNDOS DE LOCUCIÓN):
   - EXTENSIÓN EXACTA: Redacta un despacho condensado de estrictamente entre 80 y 110 palabras. A la velocidad normal de Google TTS (140 palabras/minuto), garantiza exactamente entre 35 y 45 segundos de audio completo.
   - BREVEDAD Y CONCISIÓN: Oraciones cortas. Una sola idea por oración. Evita subordinadas largas que dejen sin aire al oyente.
   - ESTILO DIRECTO Y COLOQUIAL: Escribe como se habla en la radio bonaerense/rioplatense, cercano y natural, pero con rigor periodístico.
   - VOZ ACTIVA OBLIGATORIA: Siempre voz activa ("El municipio licitó la obra...", nunca "La obra fue licitada por el municipio..."). Aporta dinamismo y contundencia.
   - SIN CIFRAS COMPLEJAS: Redondea números para el oído (en vez de "1.428.390 pesos", decir "casi un millón y medio de pesos"; en vez de "3.284 metros", decir "más de tres kilómetros").
   - PUNTUACIÓN RADIAL: Usa únicamente puntos y comas. Prohibido usar punto y coma (;), paréntesis () o guiones largos. Si necesitas acotar algo, hazlo en una oración corta independiente.
   - CERO REPETICIÓN: Cada frase debe sumar un dato nuevo. No repitas palabras ni ideas entre el inicio y el cierre.
   - FONÉTICA Y ACENTUACIÓN RIOPLATENSE: Cuida la correcta acentuación en verbos y términos locales (llegó, anunció, inauguró, continuará).

3. TÍTULO GANCHO PARA IMAGEN (MÁXIMO 8 PALABRAS - OBLIGATORIO):
   - Este título se superpone sobre la foto en portada, slides y tarjetas de noticia.
   - DEBE TENER ENTRE 3 Y 8 PALABRAS EXACTAMENTE (prohibido exceder las 8).
   - Potente, directo y enérgico: provoca intriga e impacto inmediato en quien ve la imagen.
   - Sin palabras vacías ni misterio: el lector entiende el tema al instante.
   - Ejemplos:
     * "Corte de luz en Saladillo"
     * "Inauguran nuevo polideportivo municipal"
     * "Alerta por tormentas fuertes"
     * "Homenaje a Aída Friggieri"
     * "Gran festejo por el aniversario"

4. META DESCRIPCIÓN Y ETIQUETAS:
   - Meta descripción SEO concisa de máximo 155 caracteres.
   - 4 a 6 palabras clave locales ("Saladillo", etc.).

RESPONDE EXCLUSIVAMENTE CON UN OBJETO JSON VÁLIDO CON ESTA ESTRUCTURA EXACTA:
{{
  "es_local_regional": true,
  "titulo_radial": "Titular radial corto y directo en presente (máximo 12 palabras)",
  "titulo_gancho_imagen": "Gancho imagen máx 6 palabras",
  "contenido_optimizado": "Texto radial breve de 80 a 110 palabras en voz activa...",
  "meta_description": "Resumen conciso para SEO...",
  "palabras_clave": ["Saladillo", "tema1", "tema2"]
}}"""

    def _call_glm(self, prompt, provider):
        """Llamada a la API de GLM (Zhipu AI)."""
        headers = {
            'Authorization': f'Bearer {provider["key"]}',
            'Content-Type': 'application/json'
        }
        data = {
            'model': provider['model'],
            'messages': [{'role': 'user', 'content': prompt}],
            'temperature': 0.65,
            'max_tokens': 1500
        }
        resp = requests.post(provider['url'], headers=headers, json=data, timeout=35)
        if resp.status_code == 200:
            content = resp.json()['choices'][0]['message']['content']
            return self._extract_json(content)
        return None

    def _call_gemini(self, prompt, provider):
        """Llamada a la API de Google Gemini (2.0 / 1.5 Flash)."""
        url = f"{provider['url']}?key={provider['key']}"
        data = {
            'contents': [{'parts': [{'text': prompt}]}],
            'generationConfig': {
                'temperature': 0.65,
                'maxOutputTokens': 2048,
                'thinkingConfig': {'thinkingBudget': 0},
                'responseMimeType': 'application/json'
            }
        }
        resp = requests.post(url, json=data, timeout=35)
        if resp.status_code == 200:
            candidates = resp.json().get('candidates', [])
            if candidates:
                raw_text = candidates[0]['content']['parts'][0]['text']
                return self._extract_json(raw_text)
        elif provider.get('fallback_url'):
            fallback_url = f"{provider['fallback_url']}?key={provider['key']}"
            resp_fb = requests.post(fallback_url, json=data, timeout=35)
            if resp_fb.status_code == 200:
                candidates = resp_fb.json().get('candidates', [])
                if candidates:
                    raw_text = candidates[0]['content']['parts'][0]['text']
                    return self._extract_json(raw_text)
        return None

    def _call_groq(self, prompt, provider):
        """Llamada a la API de Groq (GPT-OSS 20B / Llama)."""
        if not HAS_REQUESTS:
            return None
        headers = {
            'Authorization': f'Bearer {provider["key"]}',
            'Content-Type': 'application/json'
        }
        data = {
            'model': provider['model'],
            'messages': [{'role': 'user', 'content': prompt}],
            'temperature': 0.65,
            'max_tokens': 1500,
            'response_format': {'type': 'json_object'}
        }
        # Agregar system prompt implícito o fallback si el modelo rechaza json_object estricto
        resp = requests.post(provider['url'], headers=headers, json=data, timeout=30)
        if resp.status_code == 200:
            try:
                content = resp.json()['choices'][0]['message']['content']
                return self._extract_json(content)
            except Exception:
                pass
        # Segundo intento sin response_format estricto por si el modelo es nativo libre
        data.pop('response_format', None)
        resp2 = requests.post(provider['url'], headers=headers, json=data, timeout=30)
        if resp2.status_code == 200:
            content = resp2.json()['choices'][0]['message']['content']
            return self._extract_json(content)
        return None

    def _call_openrouter(self, prompt, provider):
        """Llamada a OpenRouter (Modelos Free Tier)."""
        headers = {
            'Authorization': f'Bearer {provider["key"]}',
            'Content-Type': 'application/json',
            'HTTP-Referer': 'https://saladillovivo.com.ar',
            'X-Title': 'Saladillo Vivo Pro'
        }
        data = {
            'model': provider['model'],
            'messages': [{'role': 'user', 'content': prompt}],
            'temperature': 0.65,
            'max_tokens': 1500
        }
        resp = requests.post(provider['url'], headers=headers, json=data, timeout=35)
        if resp.status_code == 200:
            content = resp.json()['choices'][0]['message']['content']
            return self._extract_json(content)
        return None

    def _call_openai(self, prompt, provider):
        """Llamada a la API de OpenAI."""
        headers = {
            'Authorization': f'Bearer {provider["key"]}',
            'Content-Type': 'application/json'
        }
        data = {
            'model': provider['model'],
            'messages': [{'role': 'user', 'content': prompt}],
            'temperature': 0.65,
            'max_tokens': 1500
        }
        resp = requests.post(provider['url'], headers=headers, json=data, timeout=35)
        if resp.status_code == 200:
            content = resp.json()['choices'][0]['message']['content']
            return self._extract_json(content)
        return None

    def _extract_json(self, text):
        """Extrae de manera segura el JSON dentro de bloques markdown o texto libre."""
        try:
            return json.loads(text.strip())
        except Exception:
            match = re.search(r'\{.*\}', text, flags=re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except Exception:
                    pass
        return None

    def local_heuristic_fallback(self, title, content):
        """
        Fallback editorial algorítmico local en caso de ausencia de API Keys o error de red.
        Reestructura el texto con reglas de estilo periodístico radial de Saladillo Vivo
        y título gancho de MÁXIMO 8 PALABRAS (para gancho sobre imagen).
        """
        # Limpiar y condensar a título gancho de MÁXIMO 8 PALABRAS
        clean_title = re.sub(r'[\r\n]+', ' ', title).strip()
        hook_title = self._clamp_title_to_max_words(clean_title, max_words=8)

        paragraphs = [p.strip() for p in content.split('\n') if len(p.strip()) > 30]
        if not paragraphs:
            paragraphs = [content.strip() or clean_title]

        lead = paragraphs[0]
        # Acotar desarrollo para duración óptima en locución (80 a 110 palabras ~35-45s)
        full_text = f"{lead} " + " ".join(paragraphs[1:])
        text_words = full_text.split()
        if len(text_words) > 105:
            condensed_body = " ".join(text_words[:105]).rstrip(' ,;:') + "."
        else:
            condensed_body = full_text

        meta_desc = (lead[:150] + "...") if len(lead) > 150 else lead

        # Keywords locales
        keywords = ["Saladillo", "Saladillo Vivo", "Noticias Locales", "Provincia de Buenos Aires"]
        words_found = re.findall(r'\b[A-ZÁÉÍÓÚ][a-záéíóú]{4,}\b', content)
        for w in words_found[:4]:
            if w not in keywords:
                keywords.append(w)

        return {
            'titulo_optimizado': hook_title,
            'contenido_optimizado': condensed_body.strip(),
            'meta_description': meta_desc,
            'palabras_clave': keywords
        }

    def calculate_priority_score(self, title, content, image_url=None):
        """
        Calcula la puntuación editorial:
        - featured (destacada): score >= 5
        - secondary (secundaria): score >= 3
        - tertiary (terciaria): score < 3
        """
        score = 0
        text_lower = f"{title} {content}".lower()

        # Relevancia Saladillo
        if 'saladillo' in text_lower:
            score += 2

        # Palabras de alto impacto
        keywords_impact = ['inversión', 'millones', 'urgente', 'alerta', 'salud', 'hospital', 'inauguración', 'oro', 'campeón', 'provincial', 'obras', 'seguridad']
        if any(w in text_lower for w in keywords_impact):
            score += 2

        # Imagen presente
        if image_url and not 'default' in image_url:
            score += 1

        # Extensión suficiente
        if len(content) > 400:
            score += 1

        if score >= 5:
            return 'featured'
        elif score >= 3:
            return 'secondary'
        return 'tertiary'

    def rewrite_article(self, article_data):
        """
        Paso 3: Procesa un artículo con IA (Free-First) y devuelve los campos modificados.
        """
        title = article_data.get('original_title') or article_data.get('title') or ''
        content = article_data.get('original_text') or article_data.get('text') or ''
        image_url = article_data.get('image_url')

        print(f"  [AiRewriterAgent] [Paso 3: Modificación con IA] Procesando: \"{title[:50]}...\"")

        prompt = self.create_prompt(title, content)
        ai_result = None
        used_provider = None

        # Intentar según prioridad Free-First: Gemini -> Groq -> GLM -> OpenRouter -> OpenAI
        priorities = ['gemini', 'groq', 'glm', 'openrouter', 'openai']
        for prov_key in priorities:
            prov = self.providers.get(prov_key)
            if not prov or not prov.get('key'):
                continue

            try:
                if prov_key == 'gemini':
                    ai_result = self._call_gemini(prompt, prov)
                elif prov_key == 'groq':
                    ai_result = self._call_groq(prompt, prov)
                elif prov_key == 'glm':
                    ai_result = self._call_glm(prompt, prov)
                elif prov_key == 'openrouter':
                    ai_result = self._call_openrouter(prompt, prov)
                elif prov_key == 'openai':
                    ai_result = self._call_openai(prompt, prov)

                if ai_result:
                    # Mapeo flexible de nombres de claves devueltos por el LLM
                    if 'titulo_radial' not in ai_result:
                        for alt in ['titulo', 'title', 'TITULAR RADIAL', 'titular_radial', 'titular', 'titulo_radial', 'titulo_optimizado']:
                            if alt in ai_result and ai_result[alt]:
                                ai_result['titulo_radial'] = str(ai_result[alt]).strip()
                                break
                    if 'titulo_gancho_imagen' not in ai_result:
                        for alt in ['titulo_gancho_imagen', 'titulo_gancho', 'gancho_imagen', 'image_hook', 'gancho']:
                            if alt in ai_result and ai_result[alt]:
                                ai_result['titulo_gancho_imagen'] = str(ai_result[alt]).strip()
                                break
                    if 'contenido_optimizado' not in ai_result:
                        for alt in ['contenido', 'content', 'CUERPO', 'cuerpo', 'cuerpo_noticia', 'texto', 'despacho']:
                            if alt in ai_result and ai_result[alt]:
                                ai_result['contenido_optimizado'] = str(ai_result[alt]).strip()
                                break

                if ai_result and ai_result.get('titulo_radial'):
                    used_provider = prov['name']
                    print(f"    -> IA exitosa con {used_provider}")
                    break
            except Exception as e:
                print(f"    [!] Error con {prov['name']}: {e}")

        # Si la IA determinó que es noticia nacional/internacional, descartar
        if ai_result and ai_result.get('es_local_regional') is False:
            print(f"    [AiRewriterAgent] Rechazado por orden nacional/internacional: \"{title[:50]}...\"")
            return {
                'es_local_regional': False,
                'rejected': True,
                'titulo_ia': None,
                'contenido_ia': None,
                'ai_provider': used_provider or 'IA Filter',
                'modified_at': datetime.now().isoformat()
            }

        # Si ningún proveedor externo funcionó, aplicar fallback local
        if not ai_result or not ai_result.get('titulo_radial'):
            print("    -> Aplicando Fallback Heurístico Local Periodístico")
            ai_result = self.local_heuristic_fallback(title, content)
            used_provider = 'Fallback Heurístico Local'

        # Construir titulo_gancho_imagen si no vino (clamp a 6 palabras del radial o título original)
        if 'titulo_gancho_imagen' not in ai_result or not ai_result.get('titulo_gancho_imagen'):
            source_for_hook = ai_result.get('titulo_radial') or ai_result.get('titulo_optimizado') or title
            ai_result['titulo_gancho_imagen'] = self._clamp_title_to_max_words(source_for_hook, max_words=6)

        # Limitar meta_description estrictamente a <= 155 caracteres para SEO
        raw_meta = ai_result.get('meta_description') or title[:150]
        meta_desc = raw_meta.strip()
        if len(meta_desc) > 155:
            meta_desc = meta_desc[:152].rsplit(' ', 1)[0] + '...'

        feature_status = self.calculate_priority_score(
            ai_result.get('titulo_radial', title),
            ai_result.get('contenido_optimizado', content),
            image_url
        )

        return {
            'titulo_ia': ai_result.get('titulo_radial', title),          # Título radial (hasta 12 palabras)
            'titulo_gancho_imagen': ai_result.get('titulo_gancho_imagen', ''),  # Gancho imagen (máx 6 palabras)
            'contenido_ia': ai_result.get('contenido_optimizado', content),
            'meta_description': meta_desc,
            'meta_keywords': ai_result.get('palabras_clave', ['Saladillo']),
            'featureStatus': feature_status,
            'ai_provider': used_provider,
            'modified_at': datetime.now().isoformat()
        }