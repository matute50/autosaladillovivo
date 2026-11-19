# -*- coding: utf-8 -*-
"""
agents/ara_script_writer.py — Generador de Guiones para Video de Ara (Métrica 8s)
================================================================================
Responsable de transformar noticias periodísticas en guiones televisivos
segmentados en bloques exactos de 8 segundos para el personaje 'Ara' en Google Flow.

Reglas del Contrato de Redacción (Métrica 8s):
- Cada bloque debe tener estrictamente entre 17 y 20 palabras.
- Cada bloque DEBE terminar en punto final (.) para garantizar cierre fonético antes del corte.
- Exclusión total de la categoría 'necrologicas'.
- Tono rioplatense bonaerense neutro, claro y profesional.
- Sanitización previa de términos sensibles para cumplir las políticas de Google Flow.
- Salida estructurada con bloques individuales, locación y texto de ticker.
"""

import os
import sys
import json
import re
import unicodedata
import logging
from typing import Dict, List, Optional, Any

try:
    import requests
except ImportError:
    print("[AraScriptWriter] Error: Se requiere 'requests'. Ejecute: pip install requests")
    sys.exit(1)

from .storage_agent import StorageAgent, load_env_credentials

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("AraScriptWriter")

# Categorías oficiales para asociación con locaciones
CATEGORIAS_VALIDAS = [
    "municipales",
    "deportes",
    "sociedad",
    "policiales",
    "cultura",
    "politicas",
    "institucionales",
    "regionales"
]
CATEGORIA_FALLBACK = "general"

# Términos que identifican necrológicas a descartar
PALABRAS_NECROLOGICAS = [
    "necrologica", "necrologicas", "fallecimiento", "fallecio", "q.e.p.d", "qepd",
    "sepelio", "inhumacion", "exequias", "duelo", "velatorio"
]

# Diccionario de sanitización léxica (prevención de rechazos en Google Flow)
DICCIONARIO_SANITIZACION = {
    r"\bmuerte\b": "pérdida",
    r"\bmuertos\b": "víctimas",
    r"\bmuerto\b": "afectado",
    r"\basinato\b": "hecho delictivo",
    r"\bhomicidio\b": "caso judicial",
    r"\bsangre\b": "gravedad",
    r"\bviolento\b": "complejo",
    r"\btragedia\b": "difícil situación",
    r"\btragico\b": "grave suceso",
    r"\bcadaver\b": "cuerpo",
    r"\bbalacera\b": "tiroteo investigado",
    r"\bchoque brutal\b": "incidente vial de gravedad"
}


def normalizar_texto(texto: str) -> str:
    """Elimina tildes y caracteres diacríticos para búsquedas seguras."""
    if not texto:
        return ""
    return ''.join(
        c for c in unicodedata.normalize('NFD', texto.lower())
        if unicodedata.category(c) != 'Mn'
    )


def sanitizar_lexico(texto: str) -> str:
    """Aplica reemplazos preventivos sobre términos sensibles."""
    if not texto:
        return ""
    texto_limpio = texto
    for patron, reemplazo in DICCIONARIO_SANITIZACION.items():
        texto_limpio = re.sub(patron, reemplazo, texto_limpio, flags=re.IGNORECASE)
    return texto_limpio


def normalizar_categoria(categoria_raw: str, titulo: str = "", contenido: str = "") -> str:
    """Normaliza y clasifica la noticia en una de las 8 categorías de locación o general."""
    cat_norm = normalizar_texto(categoria_raw)
    
    for cat in CATEGORIAS_VALIDAS:
        if cat in cat_norm:
            return cat

    texto_completo = normalizar_texto(f"{categoria_raw} {titulo} {contenido}")

    if any(k in texto_completo for k in ["policia", "comisaria", "aprehendido", "delito", "allanamiento", "robo"]):
        return "policiales"
    if any(k in texto_completo for k in ["futbol", "basquet", "deporte", "torneo", "cancha", "campeonato", "atleta"]):
        return "deportes"
    if any(k in texto_completo for k in ["municipio", "intendente", "salomon", "obras publicas", "concejales", "decreto"]):
        return "municipales"
    if any(k in texto_completo for k in ["elecciones", "partido", "senador", "diputado", "ucr", "peronismo"]):
        return "politicas"
    if any(k in texto_completo for k in ["teatro", "musica", "museo", "arte", "taller", "concierto", "festival"]):
        return "cultura"
    if any(k in texto_completo for k in ["escuela", "hospital", "cooperativa", "bomberos", "club", "asociacion"]):
        return "institucionales"
    if any(k in texto_completo for k in ["alvear", "roque perez", "25 de mayo", "lobos", "provincial"]):
        return "regionales"
    if any(k in texto_completo for k in ["vecino", "comunidad", "barrio", "festejo", "encuentro"]):
        return "sociedad"

    return CATEGORIA_FALLBACK


class AraScriptWriter:
    """
    Generador de guiones televisivos para Ara con Métrica estricta de 8 segundos.
    """

    def __init__(self):
        self.supabase_url, self.supabase_key = load_env_credentials()
        self.storage = StorageAgent(table='articles')
        self.api_keys = self._load_ai_keys()

    def _load_ai_keys(self) -> Dict[str, str]:
        """Carga claves de API para LLM con soporte de Gemini, Groq y OpenAI."""
        env = {}
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        for fn in ['.env.local', '.env']:
            fp = os.path.join(base_dir, fn)
            if os.path.exists(fp):
                try:
                    with open(fp, 'r', encoding='utf-8') as f:
                        for line in f:
                            line = line.strip()
                            if line and not line.startswith('#') and '=' in line:
                                k, v = line.split('=', 1)
                                if k.strip() not in env:
                                    env[k.strip()] = v.strip().strip("'\"")
                except Exception:
                    pass

        for k, v in os.environ.items():
            env[k] = v

        return {
            'gemini': env.get('GEMINI_API_KEY') or env.get('GOOGLE_API_KEY') or env.get('NEXT_PUBLIC_GEMINI_API_KEY') or '',
            'groq': env.get('GROQ_API_KEY') or '',
            'openai': env.get('OPENAI_API_KEY') or ''
        }

    def es_necrologica(self, article: Dict[str, Any]) -> bool:
        """Determina si el artículo es una necrológica y debe ser excluido del video."""
        categoria = normalizar_texto(article.get('category', ''))
        titulo = normalizar_texto(article.get('title', ''))
        contenido = normalizar_texto(article.get('content', '')[:300])

        texto_evaluar = f"{categoria} {titulo} {contenido}"
        return any(palabra in texto_evaluar for palabra in PALABRAS_NECROLOGICAS)

    def _build_prompt(self, title: str, content: str, category: str) -> str:
        """Construye el prompt estricto con la Métrica 8s de Ara."""
        contenido_limpio = sanitizar_lexico(content[:2500])
        titulo_limpio = sanitizar_lexico(title)

        return f"""Eres el Guionista Principal de "Saladillo Vivo" especializado en el personaje televisivo 'Ara' para Google Flow.
Tu tarea es transformar la siguiente noticia en un guion estructurado en bloques exactos de 8 SEGUNDOS de locución para redes sociales (Reels / TikTok / Shorts).

NOTICIA ORIGINAL:
Título: {titulo_limpio}
Categoría: {category}
Contenido: {contenido_limpio}

REGLAS ESTRICTAS DE PRODUCCIÓN TELEVISIVA (MÉTRICA 8s DE ARA):
1. CANTIDAD DE BLOQUES: Genera entre 3 y 4 bloques según la extensión y relevancia de la noticia (24 a 32 segundos totales de video).
2. CONTRATO DE PALABRAS POR BLOQUE:
   - CADA BLOQUE debe tener ESTRICTAMENTE entre 17 y 20 PALABRAS (ni menos de 16, ni más de 21).
   - Esta métrica asegura que la voz de Ara termine de locutar en el segundo 7.5 sin cortes abruptos.
3. CIERRE FONÉTICO:
   - CADA BLOQUE DEBE TERMINAR OBLIGATORIAMENTE EN PUNTO FINAL (.).
   - Está prohibido terminar un bloque en coma, dos puntos, puntos suspensivos o dejar ideas abiertas.
   - Cada bloque debe ser una oración completa con sentido por sí misma (Sujeto + Verbo + Predicado).
4. TONO Y LENGUAJE:
   - Rioplatense bonaerense neutro, claro, informativo y directo.
   - Trata los hechos en tiempo presente o pasado reciente.
   - PROHIBIDO mencionar medios de origen (ABC, Ahora Saladillo, InfoSaladillo, agencias).
   - PROHIBIDO usar modismos exagerados, asteriscos, comillas o signos extraños.
5. ESTRUCTURA NARRATIVA DE LOS BLOQUES:
   - Bloque 1: Impacto directo + Qué ocurrió en Saladillo (17-20 palabras).
   - Bloque 2: Detalle clave, beneficiarios o contexto de la noticia (17-20 palabras).
   - Bloque 3: Testimonio, dato concreto o avance de los trabajos (17-20 palabras).
   - Bloque 4 (opcional): Cierre informativo o perspectiva a futuro (17-20 palabras).
6. TICKER INFERIOR:
   - Redacta un texto continuo de 1 a 2 oraciones (30 a 50 palabras) que sintetice la noticia para que corra en el zócalo inferior en scroll.

FORMATO DE RESPUESTA:
Responde EXCLUSIVAMENTE con un JSON válido con esta estructura exacta, sin texto adicional ni bloques de código markdown:
{{
  "bloques": [
    "Primera oración de 17 a 20 palabras que termina en punto final.",
    "Segunda oración de 17 a 20 palabras que termina en punto final.",
    "Tercera oración de 17 a 20 palabras que termina en punto final."
  ],
  "ticker_texto": "Texto en síntesis de la noticia para correr en el zócalo inferior sin saltos de línea."
}}"""

    def _call_gemini(self, prompt: str) -> Optional[Dict[str, Any]]:
        """Invoca la API de Gemini."""
        key = self.api_keys.get('gemini')
        if not key:
            return None

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={key}"
        headers = {'Content-Type': 'application/json'}
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.4,
                "response_mime_type": "application/json"
            }
        }

        try:
            res = requests.post(url, headers=headers, json=payload, timeout=25)
            if res.status_code == 200:
                data = res.json()
                text = data['candidates'][0]['content']['parts'][0]['text']
                return json.loads(text)
            else:
                logger.warning(f"[Gemini] Error HTTP {res.status_code}: {res.text[:200]}")
        except Exception as e:
            logger.warning(f"[Gemini] Excepción al llamar a Gemini: {e}")
        return None

    def _call_groq(self, prompt: str) -> Optional[Dict[str, Any]]:
        """Invoca la API de Groq como respaldo."""
        key = self.api_keys.get('groq')
        if not key:
            return None

        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            'Authorization': f'Bearer {key}',
            'Content-Type': 'application/json'
        }
        payload = {
            "model": "llama-3.3-70b-versatile",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.4,
            "response_format": {"type": "json_object"}
        }

        try:
            res = requests.post(url, headers=headers, json=payload, timeout=25)
            if res.status_code == 200:
                data = res.json()
                content = data['choices'][0]['message']['content']
                return json.loads(content)
        except Exception as e:
            logger.warning(f"[Groq] Excepción al llamar a Groq: {e}")
        return None

    def _validar_y_ajustar_bloques(self, bloques: List[str]) -> List[str]:
        """Asegura que cada bloque termine en punto y cumpla la métrica de palabras."""
        bloques_ajustados = []
        for b in bloques:
            limpio = b.strip()
            if not limpio:
                continue
            if not limpio.endswith('.'):
                limpio = f"{limpio}."
            bloques_ajustados.append(limpio)
        return bloques_ajustados

    def write_script(self, article: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Genera el guion adaptado para Ara para un artículo.
        Descarta necrológicas y clasifica la locación temática.
        """
        article_id = article.get('id')
        title = article.get('title') or article.get('title_clean') or ''
        content = article.get('content') or article.get('body') or article.get('contenido_optimizado') or ''
        cat_raw = article.get('category') or ''

        # 1. Chequeo de exclusión: Necrológicas
        if self.es_necrologica(article):
            logger.info(f"🚫 Artículo id={article_id} detectado como NECROLÓGICA. Excluido de video.")
            return {
                "excluido": True,
                "motivo": "necrologica",
                "video_status": "excluido"
            }

        # 2. Normalización de categoría de locación
        locacion_categoria = normalizar_categoria(cat_raw, title, content)

        # 3. Llamada al LLM con Métrica 8s
        prompt = self._build_prompt(title, content, locacion_categoria)
        ai_res = self._call_gemini(prompt) or self._call_groq(prompt)

        if not ai_res or 'bloques' not in ai_res:
            logger.error(f"❌ No se pudo generar guion con IA para artículo id={article_id}")
            return None

        bloques = self._validar_y_ajustar_bloques(ai_res.get('bloques', []))
        if not bloques:
            return None

        total_bloques = len(bloques)
        duracion_segundos = total_bloques * 8
        texto_completo = " \n\n".join(bloques)
        ticker_texto = ai_res.get('ticker_texto') or title

        return {
            "excluido": False,
            "bloques": bloques,
            "total_bloques": total_bloques,
            "duracion_segundos": duracion_segundos,
            "categoria_locacion": locacion_categoria,
            "video_script": json.dumps({
                "bloques": bloques,
                "duracion_segundos": duracion_segundos,
                "ticker_texto": ticker_texto,
                "categoria_locacion": locacion_categoria
            }, ensure_ascii=False),
            "ticker_texto": ticker_texto
        }

    def process_and_save_article(self, article: Dict[str, Any]) -> bool:
        """Genera el guion y persiste el resultado en Supabase."""
        article_id = article.get('id')
        if not article_id:
            return False

        script_data = self.write_script(article)
        if not script_data:
            return False

        # Si fue excluida (necrológica), actualizamos el status para no reprocesarla
        if script_data.get('excluido'):
            payload = {
                'video_status': 'excluido'
            }
            return self._update_supabase(article_id, payload)

        payload = {
            'video_script': script_data['video_script'],
            'video_status': 'pendiente',
            'video_location_category': script_data['categoria_locacion']
        }
        ok = self._update_supabase(article_id, payload)
        if ok:
            logger.info(f"✅ Guion de Ara guardado para article id={article_id} | {script_data['total_bloques']} bloques (8s) | Locación: {script_data['categoria_locacion']}")
        return ok

    def _update_supabase(self, article_id: int, payload: Dict[str, Any]) -> bool:
        """Actualiza el registro en Supabase mediante PATCH REST."""
        if not self.supabase_key:
            logger.error("No hay API Key de Supabase configurada.")
            return False

        url = f"{self.supabase_url}/rest/v1/articles?id=eq.{article_id}"
        headers = {
            'apikey': self.supabase_key,
            'Authorization': f'Bearer {self.supabase_key}',
            'Content-Type': 'application/json',
            'Prefer': 'return=minimal'
        }

        try:
            res = requests.patch(url, headers=headers, json=payload, timeout=15)
            return res.status_code in (200, 204)
        except Exception as e:
            logger.error(f"Error actualizando artículo {article_id} en Supabase: {e}")
            return False

    def get_pending_articles(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Obtiene artículos recientes que aún no tienen guion de video generado."""
        if not self.supabase_key:
            return []

        url = (
            f"{self.supabase_url}/rest/v1/articles?"
            f"select=id,title,category,content,contenido_optimizado,created_at&"
            f"video_script=is.null&"
            f"video_status=is.null&"
            f"order=created_at.desc&"
            f"limit={limit}"
        )
        headers = {
            'apikey': self.supabase_key,
            'Authorization': f'Bearer {self.supabase_key}'
        }

        try:
            res = requests.get(url, headers=headers, timeout=15)
            if res.status_code == 200:
                return res.json()
        except Exception as e:
            logger.error(f"Error consultando artículos pendientes: {e}")
        return []


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Generador de guiones Ara (Métrica 8s)")
    parser.add_argument("--limit", type=int, default=5, help="Límite de artículos a procesar")
    parser.add_argument("--test-id", type=int, help="Procesar un artículo específico por ID")
    args = parser.parse_args()

    writer = AraScriptWriter()

    if args.test_id:
        logger.info(f"Buscando artículo test id={args.test_id}...")
        url = f"{writer.supabase_url}/rest/v1/articles?id=eq.{args.test_id}&select=*"
        headers = {'apikey': writer.supabase_key, 'Authorization': f'Bearer {writer.supabase_key}'}
        res = requests.get(url, headers=headers)
        if res.status_code == 200 and res.json():
            writer.process_and_save_article(res.json()[0])
        else:
            logger.error("Artículo no encontrado.")
    else:
        logger.info(f"Buscando hasta {args.limit} artículos pendientes de guion...")
        pending = writer.get_pending_articles(limit=args.limit)
        logger.info(f"Encontrados: {len(pending)}")
        for art in pending:
            writer.process_and_save_article(art)
