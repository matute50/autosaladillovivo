# -*- coding: utf-8 -*-
"""
agents/ai_rewriter_agent.py — Agente de Reescritura Periodística con IA (Free-First)
======================================================================================
Paso 3 del ciclo: Reestructura títulos, textos y metadatos de noticias scrapedas
bajo estricto estilo periodístico rioplatense bonaerense para Saladillo Vivo.

Características:
- Enfoque Free-First: prioriza proveedores gratuitos (GLM → Groq → Gemini → OpenRouter → OpenAI).
- Fallback heurístico local funcional sin APIs externas.
- Directivas editoriales para noticiero radial (TTS) y gancho de imagen (máx 8 palabras).
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

# Medios de origen del scraping: sus menciones NUNCA deben aparecer en títulos ni textos
# (regla editorial Saladillo Vivo — skill saladillo-news-editorial-filter, sección 7.2)
MEDIA_MENTION_RE = re.compile(
    r'\s*[-–—|:–]*\s*(?:https?://)?(?:www\.)?(?:'
    r'abcsaladillo\.com\.ar'
    r'|ahorasaladillo[-\s]*(?:diario[-\s]*)?digital(?:\.com\.ar)?'
    r'|infosaladillo\.com\.ar'
    r'|ABC\s*Saladillo(?:\.com\.ar)?'
    r'|Ahora Saladillo Diario Digital(?:\.com\.ar)?'
    r'|Info\s?Saladillo'
    r')',
    re.IGNORECASE
)

# "Ahora Saladillo" a secas es el nombre del medio; el "ahora Saladillo" de una frase
# ("...y ahora Saladillo suma obras") es referencia temporal y NO debe tocarse.
# Por eso este patrón es case-sensitive (con A mayúscula) sin IGNORECASE.
MEDIA_MENTION_BARE_RE = re.compile(r'\s*[-–—|:–]*\s*Ahora Saladillo(?!\s+Diario)')


def strip_media_mentions(text):
    """Elimina toda mención a los medios de origen (ABC Saladillo / Ahora Saladillo / InfoSaladillo)."""
    if not text:
        return ""
    clean = MEDIA_MENTION_RE.sub(' ', str(text))
    clean = MEDIA_MENTION_BARE_RE.sub(' ', clean)
    clean = re.sub(r'\(\s*\)', ' ', clean)
    clean = re.sub(r'\[\s*\]', ' ', clean)
    clean = re.sub(r'\s{2,}', ' ', clean)
    # Limpiar restos de puntuación colgantes dejados al remover las menciones
    clean = re.sub(r'[\s]*[-–—|:]+(?=[\.\,\!\?])', ' ', clean)
    clean = re.sub(r'\s*\.{2,}\s*$', '', clean)
    clean = re.sub(r'\s+([,.;:!?])', r'\1', clean)
    return clean.strip(' -–—|:.').strip()


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
        return f"""Eres el redactor principal y locutor estrella de "Saladillo Vivo", portal de noticias y radio de Saladillo, Provincia de Buenos Aires. Tu objetivo es transformar noticias frías de agencias o scraping en relatos humanos, cercanos y con perfecto acento rioplatense bonaerense, manteniendo fidelidad absoluta a los hechos, nombres, fechas y citas.

TÍTULO ORIGINAL:
{title}

CONTENIDO ORIGINAL:
{content}

FILTRO EDITORIAL REGIONAL ESTRICTO:
"Saladillo Vivo" publica ÚNICAMENTE noticias locales (Saladillo, Del Carril, Cazón, Polvaredas, Álvarez de Toledo) y regionales (partidos vecinos: Roque Pérez, 25 de Mayo, General Alvear, Las Flores, Lobos, Tapalqué, interior bonaerense).
Si el despacho corresponde a una noticia de orden NACIONAL o INTERNACIONAL sin anclaje local (ejemplos: política exterior o conflictos de otros países, inflación o economía nacional macro sin impacto local, fútbol de Primera División/AFA como Boca/River sin jugador local, lanzamientos comerciales de autos, farándula/espectáculos nacionales), DEBES RECHAZARLA respondiendo exactamente:
{{"es_local_regional": false, "motivo_rechazo": "Noticia nacional/internacional sin anclaje local"}}

Si la noticia SÍ es local o regional, incluye "es_local_regional": true y cumple las siguientes 5 directivas:

1. TÍTULO VISUAL / GANCHO PARA IMAGEN (titulo_gancho_imagen — MÁXIMO 8 PALABRAS, OBLIGATORIO):
   - Objetivo: superponer sobre la foto de portada, slides y tarjetas: va centrado y debe componerse para ocupar como máximo 3 líneas de texto.
   - Regla: ENTRE 3 Y 8 PALABRAS EXACTAMENTE. Prohibido exceder las 8.
   - Estilo: Potente, directo y enérgico. Genera clic sin palabras vacías: el lector entiende el tema al instante.
   - Ejemplos: "Corte de luz en Saladillo" | "Inauguran nuevo polideportivo municipal" | "Alerta por tormentas fuertes" | "Homenaje a Aída Friggieri" | "Gran festejo por el aniversario".

2. TÍTULO RADIAL / AUDIO (titulo_radial — MÁXIMO 12 PALABRAS):
   - Objetivo: resumen directo para los primeros 4 segundos del audio: el oyente debe saber qué pasó apenas empieza.
   - Regla: Una sola oración, máximo 12 palabras (ideal 5 a 10). Cero misterio ("sin gancho ciego"): prohibido "Mirá lo que pasó".
   - Estilo: Tiempo PRESENTE con actualidad y urgencia (aunque el hecho ocurrió ayer).
   - Ejemplos: "Nuevo ajuste: el Gobierno anuncia medidas económicas." | "Obras viales: Saladillo repavimenta los accesos principales."

3. CUERPO NARRATIVO Y HUMANIZACIÓN (contenido_optimizado — LOCUCIÓN TOTAL MÁXIMO 45 SEGUNDOS):
   - Extensión: estrictamente entre 80 y 110 palabras (el motor locuta a 160-180 palabras por minuto: título + cuerpo + promo quedan por debajo de los 45 segundos).
   - ESTRUCTURA DE STORYTELLING (OBLIGATORIA, renuncá a la pirámide invertida):
     * Arranque: entrá con el dato más fuerte, una imagen visual o el impacto directo al vecino. No amontones todos los datos de golpe.
     * Desarrollo: contá el por qué o el cómo afecta esto a la comunidad, con intensidad constante.
     * Cierre: terminá con una frase conclusiva ("Ahora, restará esperar...", "El próximo paso será...", "De esta manera..."). PROHIBIDO terminar con un dato suelto.
   - SINTAXIS HABLADA: Oraciones cortas de 15 a 20 palabras. Sujeto + Verbo (voz activa obligatoria) + Complemento. Una idea por oración. Prohibidos los incisos largos, los paréntesis, las comillas y el punto y coma.
   - ADAPTACIÓN AUDITIVA DE CIFRAS: Redondeá los números extensos para el oído ("casi medio millón" en vez de "478.610"; "casi un millón y medio de pesos" en vez de "1.428.390 pesos"). Traducí medidas a referencias locales asimilables al escuchar ("una superficie como la plaza principal", "como cuatro canchas de fútbol").
   - CERO REPETICIÓN: Cada frase debe sumar un dato nuevo. No repitas palabras ni ideas entre el inicio y el cierre.
   - ESTILO: Como se habla en la radio bonaerense/rioplatense: cercano, natural, empático y con rigor periodístico. Cuidá la correcta acentuación (llegó, anunció, inauguró, continuará).

4. ADAPTACIÓN FONÉTICA RIOPLATENSE (APLICACIÓN DE SOUL.md):
   - El texto será locutado por motores TTS (Gemini, Rime Coda o Edge). Para que suene a locutor local del interior bonaerense, aplicá las reglas de pronunciación y modismos de SOUL.md sobre texto ortográficamente correcto (el motor ya aplica el sheísmo y la aspiración de la s).
   - PUNTUACIÓN ESTRATÉGICA (RESPIRACIÓN): los motores TTS modernos se guían por la puntuación para la emotividad:
     * Comas , para pausas breves y naturales.
     * Puntos seguidos . para bajar el tono y separar ideas.
     * Puntos suspensivos ... para generar expectativa o transición suave (por ejemplo entre el título y el desarrollo).
   - NÚMEROS EN LETRAS: Escribí los números enteros en letras ("mil novecientos noventa" en lugar de "1990") para evitar lecturas erróneas del TTS.

5. ANÁLISIS DE TONO (campo tono) — asigná UNA etiqueta según el carácter de la noticia:
   - "SOLEMNE": necrológicas, accidentes, tragedias (ritmo pausado, tono grave).
   - "NEUTRAL": política, economía, anuncios (ritmo ágil, informativo).
   - "ALEGRE": deportes, festejos, cultura (ritmo dinámico, entusiasta).

6. PROHIBICIÓN ABSOLUTA DE MENCIONAR MEDIOS DE ORIGEN (aplica a titulo_radial, titulo_gancho_imagen y contenido_optimizado):
   - NUNCA mencionar ni atribuir a: "ABC Saladillo", "abcsaladillo.com.ar", "Ahora Saladillo", "Ahora Saladillo Diario Digital", "ahorasaladillo-diariodigital.com.ar", "InfoSaladillo", "infosaladillo.com.ar".
   - Tampoco fórmulas de atribución: "según informó...", "publicado en...", "fuente:...", "como publicó...".
   - Si el texto original trae sufijos o menciones al medio (ej. "... – Ahora Saladillo Diario Digital"), eliminarlas por completo.
   - La noticia debe leerse como producción propia e independiente de Saladillo Vivo.

7. META DESCRIPCIÓN Y ETIQUETAS (exclusivas de SEO):
   - Meta descripción SEO concisa de máximo 155 caracteres.
   - 4 a 6 palabras clave locales ("Saladillo", etc.).
   - IMPORTANTE: la meta descripción es un campo EXCLUSIVO de SEO (resultado de Google y previews). NUNCA se locuta ni se agrega al cuerpo radial.

4. ELEMENTOS VISUALES PARA SLIDE Y LOWER THIRDS DINÁMICOS:
   Analiza el despacho y selecciona el mejor formato visual televisivo según los recursos de la noticia:
   - "kicker": Categoría o localidad en mayúsculas (ej. "OBRAS PÚBLICAS", "SOCIEDAD", "SALADILLO", "POLICIALES", "DEPORTES").
   - "titular_apertura": Titular telegráfico corto de alto impacto para el primer tercio del slide (máximo 8 a 10 palabras).
   - "tipo_placa": Selecciona estrictamente uno entre:
     * "CITA": Si la noticia contiene declaraciones de funcionarios, vecinos o protagonistas ("dijo...", "expresó...").
     * "DATO_NUMERICO": Si contiene cifras, montos de dinero ($), porcentajes (%), cuadras de asfalto, cantidades destacadas.
     * "PUNTOS_CLAVE": Si es agenda, evento, requisitos o cronograma (días, horarios, lugar).
     * "RESUMEN": Si es puramente conceptual o descriptiva sin cifras ni citas.
   - "placa":
     * "titulo": Contexto corto del gráfico (ej. "DECLARACIÓN", "PRESUPUESTO ESTIMADO", "DATOS CLAVE").
     * "destacado": Elemento de máximo impacto. Si es CITA, la frase textual entre comillas. Si es DATO_NUMERICO, el número grande (ej. "$150 MILLONES", "12 CUADRAS"). Si es RESUMEN o PUNTOS_CLAVE, la síntesis principal.
     * "bajada": Quién lo dijo con cargo, o la explicación del número (ej. "José Luis Salomón | Intendente", "Inversión municipal con fondos propios").
   - "remate": Frase corta de cierre para el último tercio del slide (máximo 8 a 10 palabras, ej. "Trabajos previstos para antes de fin de mes").

RESPONDE EXCLUSIVAMENTE CON UN OBJETO JSON VÁLIDO CON ESTA ESTRUCTURA EXACTA:
{{
  "es_local_regional": true,
  "tono": "NEUTRAL",
  "titulo_radial": "Titular radial corto y directo en presente (máximo 12 palabras)",
  "titulo_gancho_imagen": "Gancho imagen de 3 a 8 palabras",
  "contenido_optimizado": "Texto radial de 80 a 110 palabras: arranque de impacto, desarrollo de impacto comunitario y frase conclusiva de cierre; números en letras; puntuación estratégica...",
  "meta_description": "Resumen conciso para SEO...",
  "palabras_clave": ["Saladillo", "tema1", "tema2"],
  "slide_visuals": {{
    "kicker": "CATEGORÍA O LOCALIDAD",
    "titular_apertura": "Titular corto para apertura",
    "tipo_placa": "CITA | DATO_NUMERICO | PUNTOS_CLAVE | RESUMEN",
    "placa": {{
      "titulo": "Contexto del dato",
      "destacado": "Texto destacado o cifra grande",
      "bajada": "Autor o explicación de la cifra"
    }},
    "remate": "Frase de cierre para el remate final"
  }}
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

    def build_heuristic_slide_visuals(self, title, content):
        """
        Genera metadatos visuales heurísticos para lower thirds y placa central
        cuando la IA no los entrega o en modo fallback.
        """
        text_lower = f"{title} {content}".lower()

        # Determinar Kicker / Categoría
        if any(k in text_lower for k in ['obras', 'paviment', 'asfalto', 'cordón', 'vial', 'iluminaci']):
            kicker = "OBRAS PÚBLICAS"
        elif any(k in text_lower for k in ['polic', 'comisar', 'detuv', 'rob', 'aprehend', 'allanamiento', 'delit']):
            kicker = "POLICIALES"
        elif any(k in text_lower for k in ['salud', 'hospital', 'médic', 'caps', 'enferm', 'vacun']):
            kicker = "SALUD"
        elif any(k in text_lower for k in ['deport', 'fútbol', 'básquet', 'campeón', 'ciclism', 'automovilism']):
            kicker = "DEPORTES"
        elif any(k in text_lower for k in ['cultur', 'teatro', 'músic', 'cine', 'taller', 'fiesta']):
            kicker = "CULTURA"
        elif any(k in text_lower for k in ['educac', 'escuel', 'alumn', 'docent', 'jardín']):
            kicker = "EDUCACIÓN"
        elif any(k in text_lower for k in ['agro', 'rural', 'camp', 'cosech', 'ganad']):
            kicker = "AGRO Y PRODUCCIÓN"
        elif any(k in text_lower for k in ['municip', 'intendente', 'concej', 'salomón']):
            kicker = "MUNICIPIO"
        else:
            kicker = "SALADILLO VIVO"

        # Titular apertura (máx 10 palabras)
        clean_title = re.sub(r'[\r\n]+', ' ', title).strip()
        words = clean_title.split()
        titular_apertura = " ".join(words[:10]).rstrip(' ,.:;')
        full_context = f"{clean_title}. {content}"

        # Buscar si hay citas textuales en título o cuerpo
        quote_match = re.search(r'["“]([^"”]{12,140})["”]', full_context)
        # Buscar si hay cifras o números de impacto con fidelidad monetaria y numérica
        stat_match = re.search(r'(\$\s*\d+[\d\.,]*\s*(?:millones?|mil|pesos|dólares)?|\b\d+[\d\.,]*\s*(?:millones?|cuadras?|viviendas?|hectáreas?|alumnos?|casos|efectivos|%|km)\b)', full_context, re.IGNORECASE)

        if quote_match:
            tipo_placa = "CITA"
            # Identificar posible emisor
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
            # Contexto de bajada fidedigno basado en el título real de la noticia
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
            # Extraer síntesis fiel del primer párrafo relevante
            sentences = [s.strip() for s in re.split(r'[\.\n]+', content) if len(s.strip()) > 25]
            summary_text = sentences[0] if sentences else clean_title
            if len(summary_text) > 85:
                summary_text = summary_text[:82].rsplit(' ', 1)[0] + '...'
            placa = {
                "titulo": "SÍNTESIS DE LA NOTICIA",
                "destacado": clean_title,
                "bajada": summary_text
            }

        # Remate de cierre
        remate = "Más detalles en saladillovivo.com.ar"
        sentences = [s.strip() for s in re.split(r'[\.\n]+', content) if len(s.strip()) > 20]
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

        slide_visuals = self.build_heuristic_slide_visuals(hook_title, condensed_body)

        return {
            'titulo_optimizado': strip_media_mentions(hook_title),
            'contenido_optimizado': strip_media_mentions(condensed_body).strip(),
            'meta_description': meta_desc,
            'palabras_clave': keywords,
            'slide_visuals': slide_visuals
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
                    # Clamp duro: máximo 12 palabras (regla editorial)
                    if ai_result.get('titulo_radial'):
                        ai_result['titulo_radial'] = self._clamp_title_to_max_words(ai_result['titulo_radial'], max_words=12)
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

        # Construir titulo_gancho_imagen si no vino (clamp a 8 palabras del radial o título original)
        if 'titulo_gancho_imagen' not in ai_result or not ai_result.get('titulo_gancho_imagen'):
            source_for_hook = ai_result.get('titulo_radial') or ai_result.get('titulo_optimizado') or title
            ai_result['titulo_gancho_imagen'] = self._clamp_title_to_max_words(source_for_hook, max_words=8)

        # Clamp duro final del título radial a 12 palabras
        if ai_result.get('titulo_radial'):
            ai_result['titulo_radial'] = self._clamp_title_to_max_words(ai_result['titulo_radial'], max_words=12)

        # Barrera dura: eliminar cualquier mención a medios de origen que la IA haya dejado
        # (regla 5 del prompt + skill saladillo-news-editorial-filter sección 7.2)
        for _field in ('titulo_radial', 'titulo_gancho_imagen', 'contenido_optimizado'):
            if ai_result.get(_field):
                ai_result[_field] = strip_media_mentions(ai_result[_field])

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

        # Etiqueta de tono multi-motor (SOLEMNE / NEUTRAL / ALEGRE), normalizada
        _tono_raw = str(ai_result.get('tono', 'NEUTRAL')).strip().upper().strip('[] ')
        if _tono_raw not in ('SOLEMNE', 'NEUTRAL', 'ALEGRE'):
            _tono_raw = 'NEUTRAL'

        # Garantizar presencia y completitud de slide_visuals
        slide_visuals = ai_result.get('slide_visuals')
        if not slide_visuals or not isinstance(slide_visuals, dict) or not slide_visuals.get('placa'):
            slide_visuals = self.build_heuristic_slide_visuals(
                ai_result.get('titulo_optimizado', title),
                ai_result.get('contenido_optimizado', content)
            )

        # Aplicar Glosario Centralizado de Redacción (data/glossary.json)
        try:
            from utils.glossary_manager import apply_text_glossary
            final_titulo = apply_text_glossary(ai_result.get('titulo_radial', title))
            final_gancho = apply_text_glossary(ai_result.get('titulo_gancho_imagen', ''))
            final_contenido = apply_text_glossary(ai_result.get('contenido_optimizado', content))
            final_meta = apply_text_glossary(meta_desc)
            if isinstance(slide_visuals, dict):
                if slide_visuals.get('titular_apertura'):
                    slide_visuals['titular_apertura'] = apply_text_glossary(slide_visuals['titular_apertura'])
                if slide_visuals.get('remate'):
                    slide_visuals['remate'] = apply_text_glossary(slide_visuals['remate'])
                if isinstance(slide_visuals.get('placa'), dict):
                    if slide_visuals['placa'].get('destacado'):
                        slide_visuals['placa']['destacado'] = apply_text_glossary(slide_visuals['placa']['destacado'])
                    if slide_visuals['placa'].get('bajada'):
                        slide_visuals['placa']['bajada'] = apply_text_glossary(slide_visuals['placa']['bajada'])
        except Exception as e:
            print(f"    [AiRewriterAgent] Aviso: no se pudo aplicar glosario de redacción: {e}")
            final_titulo = ai_result.get('titulo_radial', title)
            final_gancho = ai_result.get('titulo_gancho_imagen', '')
            final_contenido = ai_result.get('contenido_optimizado', content)
            final_meta = meta_desc

        return {
            'titulo_ia': final_titulo,          # Título radial (hasta 12 palabras)
            'titulo_gancho_imagen': final_gancho,  # Gancho imagen (máx 6 palabras)
            'contenido_ia': final_contenido,
            'tono': _tono_raw,
            'meta_description': final_meta,
            'meta_keywords': ai_result.get('palabras_clave', ['Saladillo']),
            'slide_visuals': slide_visuals,
            'featureStatus': feature_status,
            'ai_provider': used_provider,
            'modified_at': datetime.now().isoformat()
        }