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
from datetime import datetime
from typing import Dict, Optional

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

EXPRESION_INICIO_VALUES = [
    "mirá fija al lente con leve asentimiento inicial mientras dice «Buenas», tono cálido",
    "entra con mano en el corazón y sonrisa genuina, mirada directa al lente",
    "saluda con leve saludo de cabeza y postura firme pero cercana",
]

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
        """Carga proveedores de IA (free-first: Gemini → Groq → GLM → OpenRouter)."""
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
        for prefix, url in [
            ('gemini', 'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent'),
            ('gemini_fallback', 'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent'),
        ]:
            key = env.get('GEMINI_API_KEY') or env.get('GOOGLE_API_KEY') or ''
            if not key:
                # Intentar con claves múltiples (GEMINI_API_KEY_02, etc.)
                for idx in range(2, 20):
                    alt_key = env.get(f'GEMINI_API_KEY_{idx:02d}')
                    if alt_key:
                        key = alt_key
                        break
            if key and key not in providers:
                providers['gemini'] = {
                    'name': 'Google Gemini Flash',
                    'url': url,
                    'key': key,
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

        openrouter_key = env.get('OPENROUTER_API_KEY', '')
        if openrouter_key:
            providers['openrouter'] = {
                'name': 'OpenRouter Free Tier',
                'url': 'https://openrouter.ai/api/v1/chat/completions',
                'key': openrouter_key,
                'model': env.get('OPENROUTER_MODEL', 'nvidia/nemotron-3-ultra-550b-a55b:free'),
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

        TEMPLATE = r"""Eres el director creativo de "Ara", el espacio periodístico televisivo más prestigioso de Argentina. Tu tarea es transformar esta noticia local de Saladillo en un guión ESTRUCTURADO para presentación televisiva profesional.

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
    "permitir_sonrisa": __EXAMPLE_PERMITIR__,
    "tono_vocal": "__EXAMPLE_TONO__",
    "expresion_inicio": "__EXAMPLE_EXPRESION_INICIO__",
    "expresion_desarrollo": "__EXAMPLE_EXPRESION_DESC__",
    "expresion_cierre": "__EXAMPLE_EXPRESION_CIERRE__",
    "lenguaje_corporal": "__EXAMPLE_LENG_CORP__",
    "ambiente_sonoro": "__EXAMPLE_AMBIENTE__",
    "ritmo_camara": "__EXAMPLE_RITMO__",
    "requiere_aprobacion_sensible": __EXAMPLE_REQUiere__
  }
}

REGLAS ESTRICTAS PARA CADA CAMPO:

GUION_ARA:
- Es el texto que EL LOCUTOR dice ON-CAMERA, NO es el artículo completo.
- Extensión máxima absoluta: 22 palabras (tolerancia ±3 palabras; nunca exceder 25).
- En español argentino rioplatense, estilo directo, cercano y profesional.
- No incluir título ni repetición de palabras del gancho.
- Debe contener: dato principal + contexto breve + cierre natural.
- Ejemplo correcto (22 palabras): "Una jornada que dejó saldo positivo en el deporte local. El equipo de Saladillo se impuso 3 a 1 y ahora lidera el torneo regional con cinco puntos de ventaja."

VOLANTA_ZOCALO:
- Máximo 3 palabras. Sustantivo o verbo en infinitivo. Ej: "VIDA ÚTIL", "DEPORTES", "OBRAS".

TITULO_ZOCALO:
- Hasta 7 u 8 palabras. Frase declarativa o imperativa potente. Ej: "Nuevo horario para el transporte municipal".

TONO (meta_ara):
- Valor uno de: alegre_cultural | informativo_servicio | alerta_utilidad | policial_grave | sensible_luto
- Derivarlo del tono general de la noticia. Para noticias deportivas, fiestas, cultura → alegre_cultural. Para servicios, horarios, anuncios → informativo_servicio.

PERMITIR_SONRISA:
- true si el tenor lo permite (cultural, deportivo, festejos, servicio útil).
- false si es sensible (luto, tragedia, accidente grave, policial grave con víctimas).

TONO_VOCAL:
- Descripción concisa del tipo de voz. Incluir "español argentino rioplatense" siempre.
- Ej: "Varonil media edad, tono claro y pausado, español argentino rioplatense con modulación cálida"
- Ej: "Femenina joven, tono dinámico y luminoso, español argentino rioplatense porteño-bonaerense"

EXPRESION_INICIO / DESARROLLO / CIERRE:
- Descripciones en tercera persona, estilo director de casting.
- Inicio: qué hace el locutor en los primeros segundos antes/durante hablar.
- Desarrollo: cómo se comporta durante toda la lectura.
- Cierre: gesto final que no contradiga el tenor.

LENGUAJE_CORPORAL:
- Uno de: manos_sueltas_natural | postura_firme_contenida | quietud_respetuosa

AMBIENTE_SONORO:
- Descripción realista del sonido ambiental de Saladillo acorde al tenor.
- Volumen siempre bajo o muy bajo.
- Ej: "Sonido de calle céntrica de Saladillo acorde al tenor, volumen bajo o muy bajo"

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
        result = result.replace('__EXAMPLE_PERMITIR__', 'true' if tenor in ('alegre_cultural', 'informativo_servicio') else 'false')
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
                return self._extract_json(content)
        except Exception as e:
            logger.warning(f"[AraScript] Error con OpenRouter: {e}")
        return None

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
    def validate_ara_json(data: Dict) -> tuple[bool, list[str]]:
        """Valida que el JSON Ara cumpla las reglas contractuales. Retorna (ok, errores)."""
        errors = []

        if not isinstance(data, dict):
            return False, ["El resultado no es un objeto JSON"]

        # version
        if data.get('version') != '1.0':
            errors.append("'version' debe ser '1.0'")

        # contenido
        contenido = data.get('contenido')
        if not isinstance(contenido, dict):
            errors.append("'contenido' es requerido y debe ser un objeto")
        else:
            guion = contenido.get('guion_ara', '')
            words = guion.split()
            if not guion or len(guion) < 10:
                errors.append("'guion_ara' vacío o demasiado corto")
            elif len(words) > 25:
                errors.append(f"'guion_ara' excede 25 palabras ({len(words)})")
            elif len(words) < 15:
                # Advertencia, no error crítico — se puede arreglar con fallback
                errors.append(f"'guion_ara' tiene solo {len(words)} palabras (ideal 18-22)")

            volanta = contenido.get('volanta_zocalo', '')
            if not volanta:
                errors.append("'volanta_zocalo' vacío")
            elif len(volanta.split()) > 3:
                errors.append(f"'volanta_zocalo' excede 3 palabras ({len(volanta.split())})")

            titulo_z = contenido.get('titulo_zocalo', '')
            if not titulo_z:
                errors.append("'titulo_zocalo' vacío")
            elif len(titulo_z.split()) > 8:
                errors.append(f"'titulo_zocalo' excede 8 palabras ({len(titulo_z.split())})")

        # meta_ara
        meta = data.get('meta_ara')
        if not isinstance(meta, dict):
            errors.append("'meta_ara' es requerido y debe ser un objeto")
        else:
            tenor = meta.get('tenor', '')
            if tenor not in TENOR_VALUES:
                errors.append(f"'tenor' inválido: '{tenor}'. Valores permitidos: {TENOR_VALUES}")

            permitir = meta.get('permitir_sonrisa')
            if not isinstance(permitir, bool):
                errors.append("'permitir_sonrisa' debe ser booleano")

            # Bloquear palabras incompatibles cuando不允许 sonrisa
            if permitir is False:
                PROHIBITED_WORDS = ['sonrisa', 'sonriendo', 'sonriente', 'alegre',
                                    'entusiasta', 'divertido', 'jovial', 'risas']
                text_fields_to_check = []
                checked_keys = ('expresion_inicio', 'expresion_desarrollo',
                                'expresion_cierre', 'tono_vocal', 'lenguaje_corporal',
                                'guion_ara')
                for key in checked_keys:
                    val = ''
                    if key in contenido and isinstance(contenido[key], str):
                        val = contenido[key]
                    elif not val and meta.get(key) and isinstance(meta.get(key), str):
                        val = meta[key]
                    if val:
                        text_fields_to_check.append(str(val).lower())
                combined = ' '.join(text_fields_to_check)
                found = [w for w in PROHIBITED_WORDS if w in combined]
                if found:
                    errors.append(
                        f"'permitir_sonrisa=False' pero se encontraron palabras "
                        f"incompatibles en campos descriptivos: {found}"
                    )

            lenguaje = meta.get('lenguaje_corporal', '')
            if lenguaje not in LENGUAJE_CORPORAL_VALUES:
                errors.append(f"'lenguaje_corporal' inválido: '{lenguaje}'")

            ritmo = meta.get('ritmo_camara', '')
            if ritmo not in RITMO_CAMARA_VALUES:
                errors.append(f"'ritmo_camara' inválido: '{ritmo}'")

        return len(errors) == 0, errors

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
                "tono_vocal": "Varonil media edad, tono claro y pausado, español argentino rioplatense",
                "expresion_inicio": "Mirá fija al lente con leve asentimiento inicial mientras dice «Buenas», tono cálido",
                "expresion_desarrollo": EXPRESION_desarrollo_VALUES.get(tenor, "gestos naturales, mantiene contacto visual constante"),
                "expresion_cierre": "Despedida con leve asentimiento, mantiene la mirada al lente antes de cerrar",
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
        content = article_data.get('contenido_ia') or article_data.get('text') or ''
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
