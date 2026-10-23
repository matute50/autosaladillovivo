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
            'glm': {
                'name': 'GLM (Zhipu AI)',
                'url': 'https://open.bigmodel.cn/api/paas/v4/chat/completions',
                'key': self.env.get('GLM_API_KEY') or self.env.get('ZHIPU_API_KEY'),
                'model': self.env.get('GLM_MODEL', 'glm-4-flash'),
                'priority': 1
            },
            'gemini': {
                'name': 'Google Gemini',
                'url': 'https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent',
                'fallback_url': 'https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent',
                'key': self.env.get('GEMINI_API_KEY') or self.env.get('GOOGLE_API_KEY') or self.env.get('NEXT_PUBLIC_GEMINI_API_KEY'),
                'priority': 2
            },
            'openai': {
                'name': 'OpenAI',
                'url': 'https://api.openai.com/v1/chat/completions',
                'key': self.env.get('OPENAI_API_KEY'),
                'model': self.env.get('OPENAI_MODEL', 'gpt-4o-mini'),
                'priority': 3
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

DIRECTIVAS EDITORIALES:
1. Redacta un título periodístico atractivo, claro, directo y optimizado para lectores digitales de Saladillo.
2. Reestructura el cuerpo de la noticia: añade un primer párrafo de entrada (lead) potente con el qué, quién, cuándo y dónde. Organiza el desarrollo en párrafos legibles y fluidos.
3. No inventes declaraciones ni datos ausentes en el original.
4. Genera una meta descripción SEO atractiva de máximo 155 caracteres.
5. Selecciona 4 a 6 palabras clave o etiquetas (keywords) relevantes incluyendo términos locales ("Saladillo", etc.).

RESPONDE EXCLUSIVAMENTE CON UN OBJETO JSON VÁLIDO CON ESTA ESTRUCTURA EXACTA:
{{
  "titulo_optimizado": "Título profesional aquí",
  "contenido_optimizado": "Cuerpo completo de la noticia reestructurada en párrafos...",
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
        """Llamada a la API de Google Gemini."""
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
        Reestructura el texto con reglas de estilo periodístico de Saladillo Vivo.
        """
        # Limpiar y jerarquizar título
        clean_title = re.sub(r'[\r\n]+', ' ', title).strip()
        if not clean_title.lower().startswith(('en saladillo', 'saladillo:')):
            if 'saladillo' not in clean_title.lower():
                clean_title = f"Saladillo: {clean_title}"

        paragraphs = [p.strip() for p in content.split('\n') if len(p.strip()) > 30]
        if not paragraphs:
            paragraphs = [content.strip() or clean_title]

        lead = paragraphs[0]
        body = "\n\n".join(paragraphs[1:]) if len(paragraphs) > 1 else lead

        meta_desc = (lead[:150] + "...") if len(lead) > 150 else lead

        # Keywords locales
        keywords = ["Saladillo", "Saladillo Vivo", "Noticias Locales", "Provincia de Buenos Aires"]
        words = re.findall(r'\b[A-ZÁÉÍÓÚ][a-záéíóú]{4,}\b', content)
        for w in words[:4]:
            if w not in keywords:
                keywords.append(w)

        return {
            'titulo_optimizado': clean_title,
            'contenido_optimizado': f"{lead}\n\n{body}".strip(),
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

        # Intentar según prioridad: GLM -> Gemini -> OpenAI
        for prov_key in ['glm', 'gemini', 'openai']:
            prov = self.providers[prov_key]
            if not prov['key']:
                continue

            try:
                if prov_key == 'glm':
                    ai_result = self._call_glm(prompt, prov)
                elif prov_key == 'gemini':
                    ai_result = self._call_gemini(prompt, prov)
                elif prov_key == 'openai':
                    ai_result = self._call_openai(prompt, prov)

                if ai_result and ai_result.get('titulo_optimizado'):
                    used_provider = prov['name']
                    print(f"    -> IA exitosa con {used_provider}")
                    break
            except Exception as e:
                print(f"    [!] Error con {prov['name']}: {e}")

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
