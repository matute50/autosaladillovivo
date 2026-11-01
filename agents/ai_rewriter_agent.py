# -*- coding: utf-8 -*-
"""
agents/ai_rewriter_agent.py — Agente de Modificación y Enriquecimiento con IA
============================================================================
Paso 3 del ciclo: Modifica y optimiza el título, el cuerpo de la noticia, la bajada SEO
y las etiquetas editoriales con enfoque "Free-First":
1. GLM-4 (Zhipu AI) -> Primario, cuota gratuita amplia y permanente.
2. Google Gemini (1.5-flash) -> Secundario, alta velocidad y gratuito.
3. OpenAI (GPT-4o-mini) -> Terciario, comercial como fallback.
4. Fallback Heurístico Periodístico Local -> Sin dependencia externa ni fallo posible.
"""

import os
import sys
import json
import re
import unicodedata
from datetime import datetime

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    import urllib.request
    import urllib.error


def load_env_variables():
    """Carga variables desde el entorno y desde .env.local / .env."""
    env = {}
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    for filename in ['.env.local', '.env']:
        filepath = os.path.join(base_dir, filename)
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            k, v = line.split('=', 1)
                            k, v = k.strip(), v.strip().strip("'\"")
                            if k not in env:
                                env[k] = v
            except Exception:
                pass

    for k, v in os.environ.items():
        env[k] = v
    return env


class AiRewriterAgent:
    """
    Agente de IA especializado en reescritura periodística local para Saladillo Vivo.
    """
    def __init__(self):
        self.env = load_env_variables()
        self.providers = {
            'gemini': {
                'name': 'Google Gemini',
                'url': 'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent',
                'fallback_url': 'https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent',
                'key': self.env.get('GEMINI_API_KEY') or self.env.get('GOOGLE_API_KEY') or self.env.get('NEXT_PUBLIC_GEMINI_API_KEY'),
                'priority': 1
            },
            'groq': {
                'name': 'Groq (Llama 3.3 70B)',
                'url': 'https://api.groq.com/openai/v1/chat/completions',
                'key': self.env.get('GROQ_API_KEY'),
                'model': self.env.get('GROQ_MODEL', 'llama-3.3-70b-versatile'),
                'priority': 2
            },
            'glm': {
                'name': 'GLM (Zhipu AI)',
                'url': 'https://open.bigmodel.cn/api/paas/v4/chat/completions',
                'key': self.env.get('GLM_API_KEY') or self.env.get('ZHIPU_API_KEY'),
                'model': self.env.get('GLM_MODEL', 'glm-4-flash'),
                'priority': 3
            },
            'openrouter': {
                'name': 'OpenRouter Free Tier',
                'url': 'https://openrouter.ai/api/v1/chat/completions',
                'key': self.env.get('OPENROUTER_API_KEY'),
                'model': self.env.get('OPENROUTER_MODEL', 'meta-llama/llama-3.3-70b-instruct:free'),
                'priority': 4
            },
            'openai': {
                'name': 'OpenAI',
                'url': 'https://api.openai.com/v1/chat/completions',
                'key': self.env.get('OPENAI_API_KEY'),
                'model': self.env.get('OPENAI_MODEL', 'gpt-4o-mini'),
                'priority': 5
            }
        }

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
{"es_local_regional": false, "motivo_rechazo": "Noticia nacional/internacional sin anclaje local"}

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

3. META DESCRIPCIÓN Y ETIQUETAS:
   - Meta descripción SEO concisa de máximo 155 caracteres.
   - 4 a 6 palabras clave locales ("Saladillo", etc.).

RESPONDE EXCLUSIVAMENTE CON UN OBJETO JSON VÁLIDO CON ESTA ESTRUCTURA EXACTA:
{{
  "es_local_regional": true,
  "titulo_optimizado": "Titular radial corto y directo en presente (máximo 12 palabras)",
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
                'maxOutputTokens': 1500,
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
        """Llamada a la API de Groq (Llama 3.3 70B)."""
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
        resp = requests.post(provider['url'], headers=headers, json=data, timeout=30)
        if resp.status_code == 200:
            content = resp.json()['choices'][0]['message']['content']
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
        Reestructura el texto con reglas de estilo periodístico radial de Saladillo Vivo y titular de máx 12 palabras.
        """
        # Limpiar y condensar a titular radial de máximo 12 palabras
        clean_title = re.sub(r'[\r\n]+', ' ', title).strip()
        words = clean_title.split()
        if len(words) > 12:
            hook_title = " ".join(words[:12]).rstrip(' ,.:;')
        else:
            hook_title = clean_title

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

                if ai_result and ai_result.get('titulo_optimizado'):
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
        if not ai_result or not ai_result.get('titulo_optimizado'):
            print("    -> Aplicando Fallback Heurístico Local Periodístico")
            ai_result = self.local_heuristic_fallback(title, content)
            used_provider = 'Fallback Heurístico Local'

        feature_status = self.calculate_priority_score(
            ai_result.get('titulo_optimizado', title),
            ai_result.get('contenido_optimizado', content),
            image_url
        )

        return {
            'titulo_ia': ai_result.get('titulo_optimizado', title),
            'contenido_ia': ai_result.get('contenido_optimizado', content),
            'meta_description': ai_result.get('meta_description', title[:150]),
            'meta_keywords': ai_result.get('palabras_clave', ['Saladillo']),
            'featureStatus': feature_status,
            'ai_provider': used_provider,
            'modified_at': datetime.now().isoformat()
        }
