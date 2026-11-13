# -*- coding: utf-8 -*-
"""
agents/ara_script_agent.py — Agente Generador de Guión Estilo Ara
=================================================================
Paso 3.5 del ciclo Saladillo Vivo: genera un JSON estructurado "estilo Ara"
para cada noticia ya procesada por AiRewriterAgent.

El JSON se guarda en la columna ara_json (jsonb) de la tabla articles
de Supabase y se marca enviado_a_ara = True al completar exitosamente.

Flujo:
  AiRewriterAgent → AraScriptAgent → AudioGeneratorAgent → ...
"""

import os
import sys
import json
import re
import time
import logging
from typing import Dict, Optional
from datetime import datetime

try:
    import requests as _req
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

logger = logging.getLogger("AraScriptAgent")
logger.setLevel(logging.INFO)

if not logger.handlers:
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s', datefmt='%H:%M:%S'))
    logger.addHandler(sh)

TENOR_VALUES = [
    "alegre_cultural",
    "informativo_servicio",
    "alerta_utilidad",
    "policial_grave",
    "sensible_luto",
]

# EXPRESION_INICIO_VALUES removida: las reglas del prompt ya prohíben diálogos
# y los ejemplos que contenía incluían palabras habladas inválidas.

EXPRESION_desarrollo_VALUES = {
    "alegre_cultural": "gestos naturales con ambas manos, expresión abierta, sonríe moderadamente entre frase y frase",
    "informativo_servicio": "mano visible de forma controlada, expresa datos con seriedad contenida, mantiene contacto visual constante",
    "alerta_utilidad": "expresión seria pero no alarmista, ceño ligeramente fruncido solo cuando menciona riesgos o advertencias",
    "policial_grave": "rostro serio, sin gestos amplios, manos reposadas, mirada intensa que transmita gravedad",
    "sensible_luto": "expresión compasiva, cabeza ligeramente inclinada, mano sobre el pecho en momentos emotivos, silencios respetuosos",
}

EXPRESION_CIERRE_VALUES = [
    "despedida con leve asentimiento, mantiene la mirada al lente unos segundos más antes de cerrar",
    "cierra con mirada serena, baja levemente la vista y termina la locución con naturalidad",
    "agradecimiento sutil con leve inclinación de cabeza, cerrando con serenidad",
]

LENGUAJE_CORPORAL_VALUES = [
    "manos_sueltas_natural",
    "postura_firme_contenida",
    "quietud_respetuosa",
]

AMBIENTE_SONORO_VALUES = [
    "Sonido de calle céntrica de Saladillo acorde al tenor, volumen bajo o muy bajo",
    "Ambiente urbano suave de Saladillo, nivel muy bajo como fondo sutil",
    "Ruido de calles cercanas a la plaza central, apenas perceptible tras el narrador",
]

RITMO_CAMARA_VALUES = [
    "micro_acercamiento_suave",
    "plano_fijo_estable",
]


def _clamp_words(text: str, max_words: int) -> str:
    """Limita un texto a máximo N palabras."""
    words = text.strip().split()
    if len(words) <= max_words:
        return text.strip()
    result = " ".join(words[:max_words])
    # Asegurar que termine en punto si es posible
    if not result.rstrip().endswith("."):
        result += "."
    return result.rstrip().rstrip(".") + "."


class AraScriptAgent:
    """
    Agente generador de guiones estilo Ara para noticias locales de Saladillo Vivo.

    Toma los campos título radial (titulo_radial), contenido optimizado
    (contenido_ia) y tono (tono), y produce un JSON de estructura Ara
    mediante Gemini 2.5 Flash. El resultado se valida localmente antes
    de guardarse en Supabase.
    """

    def __init__(self):
        self.providers = self._load_providers()

    def _load_providers(self) -> dict:
        """Carga proveedores de IA (free-first: Gemini → Groq → GLM → OpenRouter).

        Las keys GEMINI_API_KEY_01.._N en .env pueden ser formato AQ.Ab...
        (OAuth nuevo) que NO funcionan con el SDK google-genai pero sí
        con la API REST directa via ?key=. Se prueban secuencialmente hasta
        encontrar una activa.
        """
        env = {}
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        for filename in ('.env.local', '.env'):
            filepath = os.path.join(base_dir, filename)
            if os.path.exists(filepath):
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        for line in f:
                            line = line.strip()
                            if line and not line.startswith('#') and '=' in line:
                                k, v = line.split('=', 1)
                                env[k.strip()] = v.strip().strip("\"'")
                except Exception:
                    pass
        # Heredar variables de entorno del sistema
        env.update(os.environ)

        providers = {}

        # ------------------------------------------------------------------
        # Gemini — probar cada key contra el endpoint real para encontrar una activa.
        # Las keys formato AQ.Ab... son OAuth-style; muchas pueden estar expiradas (401)
        # o ser de modelos descontinuados (404). Se hace un probe ligero con cada una.
        # ------------------------------------------------------------------
        gemini_url = 'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent'
        gemini_key = env.get('GEMINI_API_KEY') or env.get('GOOGLE_API_KEY') or ''

        def _probe_gemini_key(key: str) -> bool:
            try:
                resp = _req.post(
                    f"{gemini_url}?key={key}",
                    json={'contents': [{'parts': [{'text': '{"v":"1"}'}]}],
                          'generationConfig': {'maxOutputTokens': 5}},
                    timeout=10,
                )
                return resp.status_code == 200
            except Exception:
                return False

        if gemini_key and _probe_gemini_key(gemini_key):
            providers['gemini'] = {
                'name': 'Google Gemini Flash',
                'url': gemini_url,
                'key': gemini_key,
                'priority': 1,
            }
        else:
            # Probar claves secuenciales GEMINI_API_KEY_01 .. _N hasta encontrar activa
            for idx in range(1, 20):
                alt_key = env.get(f'GEMINI_API_KEY_{idx:02d}') or env.get(f'GEMINI_API_KEY_{idx}')
                if alt_key and _probe_gemini_key(alt_key):
                    providers['gemini'] = {
                        'name': f'Google Gemini Flash (key_{idx:02d})',
                        'url': gemini_url,
                        'key': alt_key,
                        'priority': 1,
                    }
                    break

        groq_key = env.get('GROQ_API_KEY', '')
        if groq_key:
            providers['groq'] = {
                'name': 'Groq',
                'url': 'https://api.groq.com/openai/v1/chat/completions',
                'key': groq_key,
                'model': env.get('GROQ_MODEL', 'openai/gpt-oss-20b'),
                'priority': 2,
            }

        glm_key = env.get('GLM_API_KEY') or env.get('ZHIPU_API_KEY', '')
        if glm_key:
            providers['glm'] = {
                'name': 'GLM (Zhipu AI)',
                'url': 'https://open.bigmodel.cn/api/paas/v4/chat/completions',
                'key': glm_key,
                'model': env.get('GLM_MODEL', 'glm-4.5-flash'),
                'priority': 3,
            }

        openrouter_key = (env.get('OPENROUTER_API_KEY') 
                        or env.get('HERMES_OPENROUTER_FREE_API_KEY', ''))
        if openrouter_key:
            # Preferir Gemini 2.5 Flash via OpenRouter (más capaz que el modelo free por defecto)
            model = env.get('OPENROUTER_MODEL', 'google/gemini-2.5-flash')
            providers['openrouter'] = {
                'name': 'OpenRouter Free Tier',
                'url': 'https://openrouter.ai/api/v1/chat/completions',
                'key': openrouter_key,
                'model': model,
                'priority': 4,
            }

        return providers

    # ------------------------------------------------------------------
    # PROMPT GENERADOR ARA
    # ------------------------------------------------------------------
    @staticmethod
    def _build_prompt(title_radial: str, content: str, tono: str) -> str:
        """Construye el prompt instructivo para generar el JSON Ara."""
        tono_map = {
            'SOLEMNE': 'sensible_luto',
            'ALEGRE': 'alegre_cultural',
            'NEUTRAL': 'informativo_servicio',
        }
        tenor = tono_map.get(str(tono).upper(), 'informativo_servicio')
        # Determinar permitir_sonrisa a partir del tenor
        sonriente = tenor in ('alegre_cultural', 'informativo_servicio')

        TEMPLATE = """Eres el director creativo de "Ara", espacio periodístico televisivo femenino profesional de Saladillo Vivo. Transforma esta noticia local en un guión ESTRUCTURADO para presentación televisiva.

NOTICIA — TÍTULO RADIAL:
__TITLE_RADIAL__

CONTENIDO OPTIMIZADO:
__CONTENT__

TONO GENERAL DE LA NOTICIA: __TENOR__

Debes generar UN SOLO OBJETO JSON VÁLIDO con esta estructura EXACTA:

{
  "version": "1.0",
  "contenido": {
    "guion_ara": "__EXAMPLE_GUION__",
    "volanta_zocalo": "__EXAMPLE_VOLANTA__",
    "titulo_zocalo": "__EXAMPLE_TITULO__"
  },
  "meta_ara": {
    "tenor": "__TENOR__",
    "permitir_sonrisa": __SONRIENTE__,
    "tono_vocal": "__EXAMPLE_TONO__",
    "expresion_inicio": "__EXAMPLE_EXPRESION_INICIO__",
    "expresion_desarrollo": "__EXAMPLE_EXPRESION_DESC__",
    "expresion_cierre": "__EXAMPLE_EXPRESION_CIERRE__",
    "lenguaje_corporal": "__EXAMPLE_LENG_CORP__",
    "ambiente_sonoro": "__EXAMPLE_AMBIENTE__",
    "ritmo_camara": "__EXAMPLE_RITMO__",
    "requiere_aprobacion_sensible": __REQUIERE__
  }
}

REGLAS ESTRICTAS PARA CADA CAMPO:

GUION_ARA:
- Es el texto que ARA dice ON-CAMERA, NO es el artículo completo.
- Extensión MÁXIMA ABSOLUTA: exactamente 20 palabras (rango aceptable 18 a 22). Si el borrador tiene más de 22, reducilo SIN cortar oraciones hasta llegar a 20. Contá las palabras antes de enviar.
- NUNCA cortes la última palabra ni dejes una oración incompleta (prohibido terminar con "…para el." o similares). La última oración debe cerrar con punto final y sentido completo.
- La última oración SIEMPRE debe ser una invitación breve que mencione «Saladillo Vivo» acorde al tenor: cálida ("Mirá toda la información en Saladillo Vivo") en alegre/informativo; sobria y respetuosa ("Toda la información, en Saladillo Vivo.") en policial/luto.
- En español argentino rioplatense, estilo directo, cercano y profesional.
- No incluir título ni repetición de palabras del gancho.
- Debe contener: titular directo + dato concreto + invitación breve a entrar a Saladillo Vivo acorde al tenor.
- PROHIBIDO usar siglas alfanuméricas impronunciables como códigos (ej. evita "ASTRAN25"); escribe los números con letras (ej. "tres a dos" en lugar de "3-2").
- Ejemplo correcto (22 palabras): "Una jornada que dejó saldo positivo en el deporte local. El equipo de Saladillo se impuso tres a uno y ahora lidera el torneo regional con cinco puntos de ventaja."

VOLANTA_ZOCALO:
- Máximo 3 palabras. Sustantivo o verbo en infinitivo con sentido completo. Ej: "VIDA ÚTIL", "DEPORTES", "OBRAS".

TITULO_ZOCALO:
- Hasta 7 u 8 palabras. Frase declarativa completa, nunca truncada por cantidad de caracteres. Ej: "Nuevo horario para el transporte municipal".

TONO_VOCAL (meta_ara):
- Siempre describe voz FEMENINA joven, clara, cálido/expresiva cuando se permite sonrisa, sobria/serena cuando no.
- Incluir siempre "español argentino rioplatense".
- Ejemplo alegre: "Femenina joven, tono claro cálido y expresivo, español argentino rioplatense"
- Ejemplo sobrio: "Femenina joven, tono sereno y sobrio, español argentino rioplatense"

EXPRESION_INICIO:
- DESCRIPCIÓN PURAMENTE VISUAL del gesto facial/mirada. PROHIBIDO incluir cualquier palabra hablada, diálogo,引述 o expresión entre comillas/negrita.
- Mal ejemplo (incorrecto): "Saluda mientras dice «Buenas»" ← NUNCA poner esto.
- Bien ejemplo (correcto): "Mirá fija al lente con leve asentimiento inicial, tono cálido pero contenido"
- La locución va exclusiva en guion_ara; este campo solo describe GESTOS Y MIRADAS.

EXPRESION_DESARROLLO / EXPRESION_CIERRE:
- Descripciones en tercera persona, estilo director de casting. Sin diálogos spoken.

LENGUAJE_CORPORAL:
- Uno de: manos_sueltas_natural | postura_firme_contenida | quietud_respetuosa

AMBIENTE_SONORO:
|- Descripción REALISTA del sonido ambiental callejero de Saladillo acorde al tenor. Volumen SIEMPRE bajo o muy bajo.
|- PROHIBIDO mencionar música, instrumental, estudio o corrientes de producción. Ara está en la vía pública; solo se permite sonido urbano ambiental (tráfico lejano, murmullo, viento, pájaros).
|- Si no hay suficiente contenido para generar ambiente sonoro realista, usar: "Silencio urbano mínimo, sin música ni ruido destacado".

RITMO_CAMARA:
- Uno de: micro_acercamiento_suave | plano_fijo_estable

REQUIERE_APROBACION_SENSIBLE:
- true si la noticia trata luto, fallecimientos, accidentes graves, violencia extrema.
- false en todos los demás casos.

RESPONDE ÚNICAMENTE CON EL JSON VÁLIDO. Sin explicaciones, sin markdown, sin comentarios."""

        # Reemplazar marcadores por valores reales
        result = TEMPLATE
        result = result.replace('__TITLE_RADIAL__', title_radial)
        result = result.replace('__CONTENT__', content)
        result = result.replace('__TENOR__', tenor)
        result = result.replace('__SONRIENTE__', 'true' if sonriente else 'false')
        result = result.replace('__REQUIERE__', 'true' if not sonriente else 'false')
        return result

    def _call_gemini(self, prompt: str, provider: dict) -> Optional[Dict]:
        """Llama a Gemini Flash y extrae el JSON del response."""
        import requests as req
        url = f"{provider['url']}?key={provider['key']}"
        data = {
            'contents': [{'parts': [{'text': prompt}]}],
            'generationConfig': {
                'temperature': 0.4,
                'maxOutputTokens': 1024,
                'responseMimeType': 'application/json',
            },
        }
        try:
            resp = req.post(url, json=data, timeout=45)
            if resp.status_code == 200:
                candidates = resp.json().get('candidates', [])
                if candidates:
                    raw = candidates[0]['content']['parts'][0]['text']
                    return self._extract_json(raw)
            elif provider.get('fallback_url'):
                fb_resp = req.post(provider['fallback_url'], json=data, timeout=45)
                if fb_resp.status_code == 200:
                    candidates = fb_resp.json().get('candidates', [])
                    if candidates:
                        raw = candidates[0]['content']['parts'][0]['text']
                        return self._extract_json(raw)
        except Exception as e:
            logger.warning(f"[AraScript] Error con Gemini: {e}")
        return None

    def _call_groq(self, prompt: str, provider: dict) -> Optional[Dict]:
        """Fallback a Groq si Gemini falla."""
        import requests as req
        headers = {'Authorization': f"Bearer {provider['key']}", 'Content-Type': 'application/json'}
        data = {
            'model': provider['model'],
            'messages': [{'role': 'user', 'content': prompt}],
            'temperature': 0.4,
            'max_tokens': 1024,
            'response_format': {'type': 'json_object'},
        }
        try:
            resp = req.post(provider['url'], headers=headers, json=data, timeout=35)
            if resp.status_code == 200:
                content = resp.json()['choices'][0]['message']['content']
                return self._extract_json(content)
        except Exception as e:
            logger.warning(f"[AraScript] Error con Groq: {e}")
        return None

    def _call_openrouter(self, prompt: str, provider: dict) -> Optional[Dict]:
        """Fallback a OpenRouter Free Tier."""
        import requests as req
        headers = {
            'Authorization': f"Bearer {provider['key']}",
            'Content-Type': 'application/json',
            'HTTP-Referer': 'https://saladillovivo.com.ar',
            'X-Title': 'Saladillo Vivo - Ara Script',
        }
        data = {
            'model': provider['model'],
            'messages': [{'role': 'user', 'content': prompt}],
            'temperature': 0.4,
            'max_tokens': 1024,
        }
        try:
            resp = req.post(provider['url'], headers=headers, json=data, timeout=45)
            if resp.status_code == 200:
                content = resp.json()['choices'][0]['message']['content']
                result = self._extract_json(content)
                # Post-procesamiento: asegurar que guion no exceda 25 palabras
                if result and 'contenido' in result:
                    guion = result['contenido'].get('guion_ara', '')
                    guion = self._sanitize_acronyms(guion)
                    if len(guion.split()) > 25:
                        result['contenido']['guion_ara'] = self._truncate_to_sentence_limit(guion, max_words=25)
                return result
        except Exception as e:
            logger.warning(f"[AraScript] Error con OpenRouter: {e}")
        return None

    @staticmethod
    def _sanitize_acronyms(text: str) -> str:
        """Reemplaza siglas alfanuméricas y entre paréntesis por texto legible."""
        import re as _re
        # Patrón: letras seguidas de dígitos (case-insensitive), ej: ASTRAN25, astran25
        def _replace_code(m):
            word = m.group(0)
            letters = ''.join(c for c in word if c.isalpha()).lower()
            digits = ''.join(c for c in word if c.isdigit())
            return f"{letters}" + (f" {digits}" if digits else "")
        sanitized = _re.sub(r'[A-Za-z]{2,}\d+', _replace_code, text)
        # Eliminar siglas entre paréntesis que son TODO MAYÚSCULAS (ej: (ISITRANS) → quitar)
        # El nombre expandido ya está en el texto circundante
        sanitized = _re.sub(r'\s*\([A-Z]{3,}\)\s*', ' ', sanitized)
        # También reemplazar números por letras en contextos deportivos (3-2 → tres a dos)
        sanitized = _re.sub(r'\b(\d+)\s*[-–]\s*(\d+)\b', lambda m: f'{m.group(1)} a {m.group(2)}', sanitized)
        return sanitized

    @staticmethod
    def sanitize_content_for_llm(text: str) -> str:
        """Pre-sanitizes article content BEFORE sending to LLM so acronyms don't leak."""
        import re as _re
        # Eliminar siglas alfanuméricas enteras (ej: ASTRAN25 → astran 25)
        text = _re.sub(r'[A-Za-z]{2,}\d+', lambda m: ''.join(c.lower() for c in m.group(0) if c.isalpha()) + (' ' + ''.join(c for c in m.group(0) if c.isdigit()) if any(c.isdigit() for c in m.group(0)) else ''), text)
        # Números con punto como miles: mantener tal cual (el LLM debería escribirlos en palabras)
        # Pero eliminar códigos tipo AASTRAN o similares sin espacio
        return text.strip()

    @staticmethod
    def _truncate_to_sentence_limit(text: str, max_words: int) -> str:
        """Trunca texto respetando límites de palabras y cortes por frases completas."""
        words = text.split()
        if len(words) <= max_words:
            # Asegurar mención de Saladillo Vivo si falta
            if 'saladillo vivo' not in text.lower():
                cierre = 'Toda la información en Saladillo Vivo.'
                total = len(words) + len(cierre.split())
                if total <= max_words:
                    return f'{text.strip()} {cierre}'
                else:
                    # Reemplazar última oración
                    last_dot = text.rfind('.')
                    before = text[:last_dot + 1] if last_dot > 0 else ''
                    after = text[last_dot + 1:].strip()
                    candidate = f'{before} {cierre}'.strip()
                    cw = candidate.split()
                    return ' '.join(cw[:max_words]) + '.' if len(cw) > max_words else candidate
            return text
        # Cortar por oraciones completas dentro del límite
        truncated = ' '.join(words[:max_words])
        # Encontrar último punto seguido de espacio para cortar limpio
        last_period = truncated.rfind('. ')
        if last_period > len(truncated) * 0.6:
            truncated = truncated[:last_period + 1]
        else:
            truncated = truncated.rstrip() + '.'
        return truncated.strip()

    @staticmethod
    def _extract_json(text: str) -> Optional[Dict]:
        """Extrae JSON válido de texto suelto o bloques markdown."""
        text = text.strip()
        # Si ya es JSON directo
        try:
            obj = json.loads(text)
            if isinstance(obj, dict):
                return obj
        except Exception:
            pass
        # Buscar bloque JSON dentro del texto
        match = re.search(r'\{[\s\S]*\}', text, flags=re.DOTALL)
        if match:
            try:
                obj = json.loads(match.group(0))
                if isinstance(obj, dict):
                    return obj
            except Exception:
                pass
        return None

    # ------------------------------------------------------------------
    # VALIDACIÓN LOCAL
    # ------------------------------------------------------------------
    @staticmethod
    def _validate_persona_and_style(data: Dict) -> tuple[bool, list[str]]:
        """Validaciones adicionales de persona (femenina) y estilo (sin diálogos en expresiones)."""
        errors = []
        meta = data.get('meta_ara', {})
        contenido = data.get('contenido', {})

        # ---- 1. Tono vocal: prohibido masculino ----
        tono_vocal = (meta.get('tono_vocal') or '').lower()
        MASCULINE_MARKERS = ['varonil', 'masculino', 'hombre', 'grave profundo', 'barítono']
        for marker in MASCULINE_MARKERS:
            if marker in tono_vocal:
                errors.append(f"'tono_vocal' contiene término masculino: '{marker}'")
        if 'femenina' not in tono_vocal and 'mujer' not in tono_vocal:
            errors.append("'tono_vocal' debe describir voz femenina; faltan 'femenina' o 'mujer'")

        # ---- 2. Expresión inicio: prohibido diálogo spoken ----
        exp_inicio = (meta.get('expresion_inicio') or '')
        DIALOGUE_MARKERS = ['dice', 'dice «', 'dice "', 'refiriéndose a', 'mientras dice',
                            'saluda', 'pregunta', 'responde', 'exclama']
        for marker in DIALOGUE_MARKERS:
            if marker in exp_inicio.lower():
                errors.append(
                    f"'expresion_inicio' contiene palabra hablada ('{marker}'). "
                    "Solo se permiten descripciones visuales de gestos/miradas."
                )
                break

        # ---- 3. Guion completo: última oración no truncada ----
        guion = contenido.get('guion_ara', '')
        if guion:
            last_word = guion.strip().split()[-1] if guion.strip().split() else ''
            if last_word.startswith('...') or last_word.endswith('.') is False and not any(
                last_word.endswith(c) for c in '.!¿?') :
                pass  # ok
            # Check for obvious truncation patterns
            truncation_patterns = [
                '... para', '... y ', '... al ', '... del ', '... los ', '... las ',
                '... un ', '... una ', '... el ', '... la ', '... en ',
            ]
            for pat in truncation_patterns:
                if guion.rstrip().endswith(pat.rstrip()):
                    errors.append(f"'guion_ara' parece truncado al final: '{pat}'")
                    break
            # Must end with proper punctuation
            if guion.strip() and not any(guion.rstrip().endswith(c) for c in '.!¡?'):
                errors.append("'guion_ara' no termina con puntuación final")

        # ---- 4. Sin siglas alfanuméricas impronunciables ----
        import re as _re
        alphanumeric_code = _re.search(r'[A-Z]{2,}\d+', guion)
        if alphanumeric_code:
            errors.append(f"'guion_ara' contiene sigla alfanumérica impronunciable: '{alphanumeric_code.group()}'")

        # ---- 5. Guion DEBE mencionar 'Saladillo Vivo' ----
        if guion:
            guion_lower = guion.lower()
            if 'saladillo vivo' not in guion_lower:
                errors.append("'guion_ara' debe mencionar 'Saladillo Vivo' al menos una vez (invitación de cierre)")

        # ---- 6. Ambiente sonoro: PROHIBIDO música/instrumental ----
        ambiente = (meta.get('ambiente_sonoro') or '').lower()
        MUSIC_MARKERS = ['música', 'musical', 'melodía', 'instrumental', 'cortina sonora']
        for marker in MUSIC_MARKERS:
            if marker in ambiente:
                errors.append(
                    f"'ambiente_sonoro' contiene término prohibido ('{marker}'). "
                    "Solo se permite sonido ambiental callejero o silencio urbano mínimo."
                )
                break

        return len(errors) == 0, errors

    # ------------------------------------------------------------------
    # VALIDACIÓN ESTRUCTURAL COMPLETA
    # ------------------------------------------------------------------
    @staticmethod
    def validate_ara_json(data: Dict) -> tuple[bool, list[str]]:
        """Valida estructura + persona + estilo del JSON Ara."""
        all_errors: list[str] = []

        if not isinstance(data, dict):
            return False, ["El resultado no es un objeto JSON"]

        if data.get('version') != '1.0':
            all_errors.append("'version' debe ser '1.0'")

        contenido = data.get('contenido')
        if not isinstance(contenido, dict):
            all_errors.append("'contenido' es requerido y debe ser un objeto")
        else:
            guion = contenido.get('guion_ara', '')
            palabras = guion.split() if guion else []
            if not guion or len(guion) < 10:
                all_errors.append("'guion_ara' vacío o demasiado corto")
            elif len(palabras) > 25:
                all_errors.append(f"'guion_ara' excede 25 palabras ({len(palabras)})")
            elif len(palabras) < 15:
                all_errors.append(f"'guion_ara' tiene solo {len(palabras)} palabras (ideal 18-22)")

            volanta = contenido.get('volanta_zocalo', '')
            if not volanta:
                all_errors.append("'volanta_zocalo' vacío")
            elif len(volanta.split()) > 3:
                all_errors.append(f"'volanta_zocalo' excede 3 palabras ({len(volanta.split())})")

            titulo_z = contenido.get('titulo_zocalo', '')
            if not titulo_z:
                all_errors.append("'titulo_zocalo' vacío")
            elif len(titulo_z.split()) > 8:
                all_errors.append(f"'titulo_zocalo' excede 8 palabras ({len(titulo_z.split())})")

        meta = data.get('meta_ara')
        if not isinstance(meta, dict):
            all_errors.append("'meta_ara' es requerido y debe ser un objeto")
        else:
            tenor = meta.get('tenor', '')
            if tenor not in TENOR_VALUES:
                all_errors.append(f"'tenor' inválido: '{tenor}'. Valores permitidos: {TENOR_VALUES}")

            permitir = meta.get('permitir_sonrisa')
            if not isinstance(permitir, bool):
                all_errors.append("'permitir_sonrisa' debe ser booleano")

            lenguaje = meta.get('lenguaje_corporal', '')
            if lenguaje not in LENGUAJE_CORPORAL_VALUES:
                all_errors.append(f"'lenguaje_corporal' inválido: '{lenguaje}'")

            ritmo = meta.get('ritmo_camara', '')
            if ritmo not in RITMO_CAMARA_VALUES:
                all_errors.append(f"'ritmo_camara' inválido: '{ritmo}'")

            if permitir is False:
                PROHIBITED_WORDS = ['sonrisa', 'sonriendo', 'sonriente', 'alegre',
                                    'entusiasta', 'divertido', 'jovial', 'risas']
                text_fields_to_check = []
                checked_keys = ('expresion_inicio', 'expresion_desarrollo',
                                'expresion_cierre', 'tono_vocal', 'lenguaje_corporal',
                                'guion_ara')
                for key in checked_keys:
                    val = ''
                    if key in contenido and isinstance(contenido.get(key), str):
                        val = contenido[key]
                    elif not val and meta.get(key) and isinstance(meta.get(key), str):
                        val = meta[key]
                    if val:
                        text_fields_to_check.append(str(val).lower())
                combined = ' '.join(text_fields_to_check)
                found = [w for w in PROHIBITED_WORDS if w in combined]
                if found:
                    all_errors.append(
                        f"'permitir_sonrisa=False' pero se encontraron palabras "
                        f"incompatibles en campos descriptivos: {found}"
                    )

        # ---- Validación de persona y estilo (femenina, sin diálogos) ----
        persona_ok, persona_err = AraScriptAgent._validate_persona_and_style(data)
        all_errors.extend(persona_err)

        return len(all_errors) == 0, all_errors

    @staticmethod
    def apply_heuristic_fallback(title: str, content: str, tono: str) -> Dict:
        """
        Fallback heurístico cuando falla la API. Produce un JSON Ara mínimo
        pero válido para que el pipeline no se detenga.
        """
        tenor_map = {
            'SOLEMNE': 'sensible_luto',
            'ALEGRE': 'alegre_cultural',
            'NEUTRAL': 'informativo_servicio',
        }
        tenor = tenor_map.get(str(tono).upper(), 'informativo_servicio')
        permitir_sonrisa = tenor in ('alegre_cultural', 'informativo_servicio')

        # Extraer idea principal del título para volanta
        title_words = title.split()[:3]
        volanta = ' '.join(title_words)

        # Titulo zócalo derivado del primer párrafo — máx 8 palabras
        first_sentence = re.split(r'[.\n]', content)[0].strip() if content else title
        titulo_words = first_sentence.split()[:8]
        titulo_z = ' '.join(titulo_words) if titulo_words else title[:40]

        # Guion heurístico: condensar contenido a ~20 palabras mínimo 18
        sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', content) if s.strip()]
        acc = []
        wc = 0
        for s in sentences:
            parts = s.split()
            # Acortar cada oración si excede para llegar a 18-22 palabras
            if wc + len(parts) > 22:
                extra = 22 - wc
                if extra >= 3:
                    acc.append(' '.join(parts[:extra]))
                break
            acc.append(s)
            wc += len(parts)
        guion = ' '.join(acc).strip()
        if not guion.endswith('.'):
            guion += '.'
        # Si aún está corto (<18), repetir idea clave del título
        while len(guion.split()) < 18 and title:
            guion += f' {title}.'
            # Recortar si pasamos de 25
            too_long_words = guion.split()
            if len(too_long_words) > 25:
                guion = ' '.join(too_long_words[:24]) + '.'
        if not guion.endswith('.'):
            guion += '.'
        # Asegurar que SIEMPRE se menciona Saladillo Vivo al cierre
        if 'saladillo vivo' not in guion.lower():
            cierre = 'Toda la información en Saladillo Vivo.'
            current_words = guion.split()
            # Dejar espacio para el cierre (restando palabras del final)
            gap = len(cierre.split()) + 1
            while len(current_words) + gap > 25 and len(current_words) > gap:
                current_words.pop()
            guion = ' '.join(current_words).rstrip()
            if guion.endswith('.'):
                guion += f' {cierre}'
            else:
                guion = f'{guion}. {cierre}'

        return {
            "version": "1.0",
            "contenido": {
                "guion_ara": guion,
                "volanta_zocalo": volanta,
                "titulo_zocalo": titulo_z,
            },
            "meta_ara": {
                "tenor": tenor,
                "permitir_sonrisa": permitir_sonrisa,
                "tono_vocal": ("Femenina joven, tono claro cálido y expresivo, español argentino rioplatense"
                               if permitir_sonrisa else "Femenina joven, tono sereno y sobrio, español argentino rioplatense"),
                "expresion_inicio": (
                    "Mirá fija al lente con leve asentimiento inicial, expresión abierta y cercana"
                    if permitir_sonrisa else
                    "Mirada seria al lente, leve inclinación de cabeza, expresión compasiva y contenida"
                ),
                "expresion_desarrollo": EXPRESION_desarrollo_VALUES.get(tenor, "gestos naturales, mantiene contacto visual constante"),
                "expresion_cierre": "Despedida con leve asentimiento sereno, mantiene la mirada al lente antes de cerrar",
                "lenguaje_corporal": "postura_firme_contenida",
                "ambiente_sonoro": AMBIENTE_SONORO_VALUES[0],
                "ritmo_camara": "micro_acercamiento_suave",
                "requiere_aprobacion_sensible": tenor == 'sensible_luto',
            },
        }

    # ------------------------------------------------------------------
    # MÉTODO PRINCIPAL
    # ------------------------------------------------------------------
    def generate_ara_json(self, article_data: Dict) -> Optional[Dict]:
        """
        Genera el JSON estilo Ara a partir de los datos del artículo ya
        procesados por AiRewriterAgent.

        Parámetros article_data (dict con keys comunes del pipeline):
          - titulo_radial: título radial corto (IA)
          - contenido_ia: cuerpo optimizado
          - tono: SOLEMNE | NEUTRAL | ALEGRE
          - id: ID del artículo en Supabase

        Retorna el dict Ara validado, o None si falló todo.
        """
        title_radial = article_data.get('titulo_radial') or article_data.get('title') or ''
        content = self.sanitize_content_for_llm(
            (article_data.get('contenido_ia') or article_data.get('text') or '')
        )
        tono = article_data.get('tono') or 'NEUTRAL'
        art_id = article_data.get('id', '?')

        logger.info(f"[AraScriptAgent] [Paso 3.5: Generando guión Ara] ID: {art_id} | Ton: {tono}")

        prompt = self._build_prompt(title_radial, content, tono)

        ara_result = None
        used_provider = None

        # Orden de proveedores: Gemini → Groq → OpenRouter
        priorities = ['gemini', 'groq', 'openrouter']
        for prov_key in priorities:
            prov = self.providers.get(prov_key)
            if not prov or not prov.get('key'):
                continue
            logger.info(f"[AraScriptAgent] Intentando con {prov['name']}...")
            try:
                if prov_key == 'gemini':
                    ara_result = self._call_gemini(prompt, prov)
                elif prov_key == 'groq':
                    ara_result = self._call_groq(prompt, prov)
                elif prov_key == 'openrouter':
                    ara_result = self._call_openrouter(prompt, prov)
            except Exception as e:
                logger.warning(f"[AraScriptAgent] Excepción con {prov['name']}: {e}")

            if ara_result:
                used_provider = prov['name']
                break

        # Validar resultados
        # Fail-open: si NO hay ningún proveedor configurado, retornar None
        # para que el pipeline deje ara_json=NULL y reintente después.
        has_providers = any(self.providers.get(k) and self.providers[k].get('key')
                            for k in ['gemini', 'groq', 'openrouter'])
        if not has_providers:
            logger.warning("[AraScriptAgent] Ningún proveedor de IA configurado — fail-open (no guarda)")
            return None

        if ara_result:
            ok, errs = self.validate_ara_json(ara_result)
            if not ok:
                logger.warning(f"[AraScriptAgent] Validación falló ({errs}), aplicando fallback heurístico")
                ara_result = self.apply_heuristic_fallback(title_radial, content, tono)
                used_provider = f"{used_provider} (con fallback heurístico)"
        else:
            logger.warning("[AraScriptAgent] Ningún proveedor devolvió resultado, usando fallback heurístico")
            ara_result = self.apply_heuristic_fallback(title_radial, content, tono)
            used_provider = 'Fallback Heurístico'

        # REVALIDAR después de cualquier fallback — fail-open si sigue fallando
        if ara_result:
            ok2, errs2 = self.validate_ara_json(ara_result)
            if not ok2:
                logger.error(f"[AraScriptAgent] Fallback también falló ({errs2}) — guardando NULL")
                return None

        # Clamp duras post-validación (garantizar límites absolutos)
        if ara_result:
            contenido = ara_result.setdefault('contenido', {})
            guion = contenido.get('guion_ara', '')
            if len(guion.split()) > 25:
                guion = ' '.join(guion.split()[:25]) + '.'
                contenido['guion_ara'] = guion

            volanta = contenido.get('volanta_zocalo', '')
            if len(volanta.split()) > 3:
                contenido['volanta_zocalo'] = ' '.join(volanta.split()[:3])

            titulo_z = contenido.get('titulo_zocalo', '')
            if len(titulo_z.split()) > 8:
                contenido['titulo_zocalo'] = ' '.join(titulo_z.split()[:8])

            meta = ara_result.setdefault('meta_ara', {})
            if meta.get('tenor') not in TENOR_VALUES:
                meta['tenor'] = 'informativo_servicio'
            if meta.get('lenguaje_corporal') not in LENGUAJE_CORPORAL_VALUES:
                meta['lenguaje_corporal'] = 'postura_firme_contenida'
            if meta.get('ritmo_camara') not in RITMO_CAMARA_VALUES:
                meta['ritmo_camara'] = 'plano_fijo_estable'

            ara_result['generated_at'] = datetime.now().isoformat()
            ara_result['provider_used'] = used_provider

            words_count = len(ara_result['contenido']['guion_ara'].split())
            logger.info(f"  [AraScriptAgent] Genérico exitoso con {used_provider} — "
                        f"guion: {words_count} palabras, tenor: {meta.get('tenor')}")
            return ara_result

        return None
