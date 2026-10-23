#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
free_rewriter.py — Sistema de Modificación de Noticias con IA (Free-First)
========================================================================
Desarrollado para: Saladillo Vivo (Next.js 15 + Supabase)
Objetivo: Reestructurar y enriquecer noticias locales con IA profesional sin alterar
los hechos, optimizando títulos, redacción, copetes, metadatos SEO y prioridades editoriales.

Estrategia Free-First:
1. GLM (Zhipu AI / Z.AI - glm-4 / glm-4-flash): Primario, alta cuota gratuita y permanente.
2. Gemini (Google AI Studio - gemini-1.5-flash / gemini-pro): Secundario, rápido y gratuito.
3. OpenAI (GPT-4o-mini / GPT-3.5-turbo): Terciario, comercial como fallback final.
4. Fallback Heurístico Local: Garantiza continuidad operativa si no hay API keys configuradas.

Cumple estrictamente:
- NO modifica reproductores de video ni lógica visual del frontend.
- Cero dependencias forzadas: Implementado con la biblioteca estándar y requests.
"""

import os
import sys
import json
import re
import time
from datetime import datetime
from urllib.parse import urljoin

# Asegurar soporte de encoding en terminales Windows
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# Intento de importar requests, con fallback transparente a urllib
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    import urllib.request
    import urllib.error

# ==============================================================================
# CARGA DE VARIABLES DE ENTORNO
# ==============================================================================
def load_env_variables():
    """Carga variables desde el entorno y desde .env.local / .env si existen."""
    env_vars = {}
    base_dir = os.path.dirname(os.path.abspath(__file__))

    for filename in ['.env.local', '.env']:
        filepath = os.path.join(base_dir, filename)
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            k, v = line.split('=', 1)
                            k = k.strip()
                            v = v.strip().strip("'\"")
                            if k not in env_vars:
                                env_vars[k] = v
            except Exception:
                pass

    # El entorno del sistema tiene prioridad
    for k, v in os.environ.items():
        env_vars[k] = v

    return env_vars

ENV = load_env_variables()

# ==============================================================================
# CONFIGURACIÓN DE PROVIDERS IA (FREE-FIRST APPROACH)
# ==============================================================================
API_CONFIG = {
    'glm': {
        'name': 'GLM (Zhipu AI)',
        'url': 'https://open.bigmodel.cn/api/paas/v4/chat/completions',
        'key': ENV.get('GLM_API_KEY') or ENV.get('ZHIPU_API_KEY'),
        'model': ENV.get('GLM_MODEL', 'glm-4-flash'),
        'priority': 1
    },
    'gemini': {
        'name': 'Google Gemini',
        'url': 'https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent',
        'fallback_url': 'https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent',
        'key': ENV.get('GEMINI_API_KEY') or ENV.get('GOOGLE_API_KEY') or ENV.get('NEXT_PUBLIC_GEMINI_API_KEY'),
        'priority': 2
    },
    'openai': {
        'name': 'OpenAI',
        'url': 'https://api.openai.com/v1/chat/completions',
        'key': ENV.get('OPENAI_API_KEY'),
        'model': ENV.get('OPENAI_MODEL', 'gpt-4o-mini'),
        'priority': 3
    }
}

# ==============================================================================
# PROMPT PERIODÍSTICO HIPERLOCAL PARA SALADILLO VIVO
# ==============================================================================
def create_ai_prompt(article_data):
    """
    Genera un prompt especializado para reestructurar noticias locales
    con enfoque editorial y optimización SEO.
    """
    title = article_data.get('title') or article_data.get('titulo') or ''
    content = article_data.get('text') or article_data.get('contenido') or article_data.get('content') or ''
    author = article_data.get('autor') or 'Fuente Local'

    return f"""Eres un periodista profesional y editor general de "Saladillo Vivo", el portal temático de noticias y canal en vivo de Saladillo, Provincia de Buenos Aires.

Tu labor es reestructurar profesionalmente el siguiente despacho periodístico de forma completa (redacción fresca, atractiva, sin alterar datos ni citas reales).

FUENTE ORIGINAL: {author}
TÍTULO ORIGINAL: {title}
CONTENIDO ORIGINAL:
{content[:4000]}

DIRECTIVAS EDITORIALES OBLIGATORIAS:
1. Reestructura el contenido desde cero con prosa periodística ágil, clara y atractiva.
2. Adopta un tono informativo local riguroso, cercano a la comunidad de Saladillo.
3. Organiza en párrafos bien estructurados (apertura con el qué/quién/cuándo/dónde, desarrollo y cierre).
4. Genera una meta descripción óptima (130-160 caracteres) para Google y redes sociales.
5. Extrae entre 4 y 7 palabras clave (keywords) relevantes (ej: ["Saladillo", "Saladillo Vivo", ...]).
6. Longitud recomendada del contenido optimizado: entre 400 y 1600 caracteres.
7. RESPONDER EXCLUSIVAMENTE UN OBJETO JSON VÁLIDO. No agregues saludos, explicaciones ni texto fuera del JSON.

FORMATO JSON OBLIGATORIO:
{{
    "titulo_optimizado": "Titular periodístico claro y atrapante",
    "contenido_optimizado": "Texto completo reestructurado en párrafos con saltos de línea \\n\\n...",
    "meta_description": "Resumen directo para motores de búsqueda de 130 a 160 caracteres.",
    "palabras_clave": ["Saladillo", "Sociedad", "Comunidad"]
}}"""

# ==============================================================================
# EXTRACCIÓN Y LIMPIEZA DE JSON DE RESPUESTAS LLM
# ==============================================================================
def clean_and_parse_json(raw_text):
    """
    Extrae y parsea un bloque JSON de la respuesta del modelo, tolerando
    bloques markdown ```json ... ``` y texto circundante.
    """
    if not raw_text:
        return None

    cleaned = raw_text.strip()

    # Si viene envuelto en markdown code blocks
    match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', cleaned, re.IGNORECASE)
    if match:
        cleaned = match.group(1).strip()

    # Buscar primera llave { y última }
    start = cleaned.find('{')
    end = cleaned.rfind('}')
    if start != -1 and end != -1 and end > start:
        cleaned = cleaned[start:end+1]

    try:
        data = json.loads(cleaned)
        # Validar campos esenciales
        if 'titulo_optimizado' in data and 'contenido_optimizado' in data:
            return data
    except Exception:
        pass

    return None

# ==============================================================================
# IMPLEMENTACIÓN DE LLAMADAS A PROVIDERS (FREE-FIRST)
# ==============================================================================
def modify_with_glm(prompt, provider):
    """Provider 1: GLM (Zhipu AI) - Primario / Free"""
    headers = {
        'Authorization': f'Bearer {provider["key"]}',
        'Content-Type': 'application/json'
    }
    payload = {
        'model': provider['model'],
        'messages': [
            {'role': 'system', 'content': 'Eres un redactor y editor periodístico profesional que responde únicamente en formato JSON válido.'},
            {'role': 'user', 'content': prompt}
        ],
        'temperature': 0.6,
        'max_tokens': 1600
    }

    if HAS_REQUESTS:
        resp = requests.post(provider['url'], headers=headers, json=payload, timeout=35)
        resp.raise_for_status()
        res_json = resp.json()
    else:
        req = urllib.request.Request(
            provider['url'],
            data=json.dumps(payload).encode('utf-8'),
            headers=headers,
            method='POST'
        )
        with urllib.request.urlopen(req, timeout=35) as r:
            res_json = json.loads(r.read().decode('utf-8'))

    content = res_json['choices'][0]['message']['content']
    return clean_and_parse_json(content)

def modify_with_gemini(prompt, provider):
    """Provider 2: Google Gemini (gemini-1.5-flash / gemini-pro) - Secundario / Free"""
    url = f"{provider['url']}?key={provider['key']}"
    headers = {'Content-Type': 'application/json'}
    payload = {
        'contents': [
            {'parts': [{'text': prompt}]}
        ],
        'generationConfig': {
            'temperature': 0.6,
            'topK': 20,
            'topP': 0.9,
            'maxOutputTokens': 1600,
            'responseMimeType': 'application/json'
        }
    }

    raw_text = None
    try:
        if HAS_REQUESTS:
            resp = requests.post(url, headers=headers, json=payload, timeout=35)
            if resp.status_code != 200 and 'fallback_url' in provider:
                # Reintento con fallback URL
                url_fb = f"{provider['fallback_url']}?key={provider['key']}"
                resp = requests.post(url_fb, headers=headers, json=payload, timeout=35)
            resp.raise_for_status()
            res_json = resp.json()
        else:
            req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers, method='POST')
            with urllib.request.urlopen(req, timeout=35) as r:
                res_json = json.loads(r.read().decode('utf-8'))

        candidates = res_json.get('candidates', [])
        if candidates and 'content' in candidates[0]:
            parts = candidates[0]['content'].get('parts', [])
            if parts and 'text' in parts[0]:
                raw_text = parts[0]['text']
    except Exception as e:
        raise RuntimeError(f"Fallo en Gemini API: {e}")

    return clean_and_parse_json(raw_text)

def modify_with_openai(prompt, provider):
    """Provider 3: OpenAI (GPT-4o-mini / GPT-3.5-turbo) - Terciario / Fallback"""
    headers = {
        'Authorization': f'Bearer {provider["key"]}',
        'Content-Type': 'application/json'
    }
    payload = {
        'model': provider['model'],
        'messages': [
            {'role': 'system', 'content': 'Eres un redactor y editor periodístico profesional que responde únicamente en formato JSON válido.'},
            {'role': 'user', 'content': prompt}
        ],
        'temperature': 0.6,
        'max_tokens': 1600,
        'response_format': {'type': 'json_object'}
    }

    if HAS_REQUESTS:
        resp = requests.post(provider['url'], headers=headers, json=payload, timeout=35)
        resp.raise_for_status()
        res_json = resp.json()
    else:
        req = urllib.request.Request(
            provider['url'],
            data=json.dumps(payload).encode('utf-8'),
            headers=headers,
            method='POST'
        )
        with urllib.request.urlopen(req, timeout=35) as r:
            res_json = json.loads(r.read().decode('utf-8'))

    content = res_json['choices'][0]['message']['content']
    return clean_and_parse_json(content)

# ==============================================================================
# FALLBACK HEURÍSTICO LOCAL (Si ninguna API externa está disponible)
# ==============================================================================
def fallback_heuristic_rewriter(article_data):
    """
    Reestructura periodísticamente la nota utilizando reglas heurísticas locales
    en caso de no contar con conexión o saldo en proveedores de IA externos.
    """
    title = (article_data.get('title') or article_data.get('titulo') or '').strip()
    raw_content = (article_data.get('text') or article_data.get('contenido') or article_data.get('description') or '').strip()

    # Limpiar y normalizar párrafos
    paragraphs = [p.strip() for p in raw_content.split('\n') if len(p.strip()) > 30]
    if not paragraphs:
        paragraphs = [raw_content] if raw_content else ["Información en desarrollo."]

    # Generar titular pulido
    title_clean = re.sub(r'\s+', ' ', title)
    title_clean = title_clean.rstrip('. ')

    # Meta descripción optimizada (140-155 caracteres)
    lead_paragraph = paragraphs[0] if paragraphs else title_clean
    meta_desc = lead_paragraph[:150].strip()
    if len(lead_paragraph) > 150:
        meta_desc = meta_desc.rsplit(' ', 1)[0] + '...'

    # Keywords automáticas
    keywords = ["Saladillo", "Saladillo Vivo", "Noticias Locales", "Actualidad"]
    lower_content = (title + " " + raw_content).lower()
    for kw, label in [
        ('cooperativa', 'CES Saladillo'), ('municipal', 'Municipio de Saladillo'),
        ('salud', 'Salud'), ('obras', 'Obras Públicas'), ('cultura', 'Cultura'),
        ('deportes', 'Deportes'), ('policial', 'Seguridad'), ('educación', 'Educación')
    ]:
        if kw in lower_content and label not in keywords:
            keywords.append(label)

    return {
        "titulo_optimizado": title_clean,
        "contenido_optimizado": "\n\n".join(paragraphs),
        "meta_description": meta_desc,
        "palabras_clave": keywords[:6],
        "_is_heuristic": True
    }

# ==============================================================================
# COORDINADOR DE MODIFICACIÓN CON IA (FREE-FIRST)
# ==============================================================================
def modify_content_with_ai(article_data, force_provider=None):
    """
    Modifica el contenido de una noticia recorriendo los proveedores según
    prioridad: GLM (1) -> Gemini (2) -> OpenAI (3) -> Fallback Heurístico.
    """
    prompt = create_ai_prompt(article_data)

    provider_order = ['glm', 'gemini', 'openai']
    if force_provider and force_provider in API_CONFIG:
        provider_order = [force_provider]

    for provider_key in provider_order:
        provider = API_CONFIG[provider_key]

        if not provider.get('key'):
            continue

        try:
            print(f"  [>] Consultando {provider['name']}...")
            if provider_key == 'glm':
                result = modify_with_glm(prompt, provider)
            elif provider_key == 'gemini':
                result = modify_with_gemini(prompt, provider)
            elif provider_key == 'openai':
                result = modify_with_openai(prompt, provider)
            else:
                result = None

            if result and result.get('titulo_optimizado') and result.get('contenido_optimizado'):
                print(f"  [OK] Procesado con éxito por {provider['name']}.")
                result['_provider'] = provider_key
                return result

        except Exception as e:
            print(f"  [!] Advertencia con {provider['name']}: {e}")
            continue

    # Fallback si ningún proveedor respondió
    print("  [i] Usando fallback heurístico local (sin consumo de API).")
    fallback = fallback_heuristic_rewriter(article_data)
    fallback['_provider'] = 'heuristic_fallback'
    return fallback

# ==============================================================================
# SISTEMA DE PRIORIZACIÓN EDITORIAL AUTOMÁTICA
# ==============================================================================
def calculate_priority_score(article_data):
    """
    Calcula una puntuación de prioridad editorial de 0 a 100 puntos:
    - Relevancia local (40%): Menciona explícitamente Saladillo.
    - Impacto / Noticia de última hora (30%): Urgente, importante, alerta, etc.
    - Contenido multimedia (20%): Posee imagen de alta resolución.
    - Longitud y completitud del cuerpo (10%): Extensión entre 300 y 3000 caracteres.
    """
    score = 0
    title_lower = (article_data.get('title') or article_data.get('titulo') or '').lower()
    content_lower = (article_data.get('text') or article_data.get('contenido') or '').lower()

    # 1. Relevancia local (40 pts)
    if 'saladillo' in title_lower or 'saladillo' in content_lower:
        score += 40

    # 2. Términos de impacto o interés general (30 pts)
    impact_keywords = [
        'urgente', 'importante', 'destacado', 'crítico', 'alerta',
        'atención', 'comunicado', 'inauguración', 'oficial', 'último momento',
        'aniversario', 'conferencia', 'sesión', 'hcd'
    ]
    if any(k in title_lower for k in impact_keywords):
        score += 30
    elif any(k in content_lower[:400] for k in impact_keywords):
        score += 15

    # 3. Contenido multimedia (20 pts)
    img = article_data.get('image_url') or article_data.get('imageUrl')
    if img and 'default-og-image' not in img:
        score += 20

    # 4. Longitud y completitud (10 pts)
    text_len = len(content_lower)
    if 300 <= text_len <= 3500:
        score += 10

    return score

def determine_priority(article_data):
    """
    Determina la jerarquía editorial en la portada de Saladillo Vivo:
    - >= 70 pts: 'featured'  (Noticia destacada principal)
    - >= 40 pts: 'secondary' (Parrilla secundaria de noticias)
    - >= 20 pts: 'tertiary'  (Noticias complementarias)
    - < 20 pts:  None        (Archivo estándar / otras noticias)
    """
    score = calculate_priority_score(article_data)

    if score >= 70:
        return 'featured'
    elif score >= 40:
        return 'secondary'
    elif score >= 20:
        return 'tertiary'
    else:
        return None

# ==============================================================================
# SINCRONIZACIÓN OPCIONAL CON SUPABASE (Next.js 15 Backend)
# ==============================================================================
def sync_modified_to_supabase(articles):
    """Actualiza o inserta las noticias mejoradas con IA en Supabase."""
    supabase_url = ENV.get('NEXT_PUBLIC_SUPABASE_URL')
    supabase_key = ENV.get('SUPABASE_SERVICE_ROLE_KEY') or ENV.get('NEXT_PUBLIC_SUPABASE_ANON_KEY')

    if not supabase_url or not supabase_key:
        print("[!] Variables de Supabase no disponibles. Omitiendo sincronización remota.")
        return 0

    print(f"\n[+] Sincronizando noticias procesadas con Supabase...")
    api_url = f"{supabase_url.rstrip('/')}/rest/v1/articles"
    headers = {
        'apikey': supabase_key,
        'Authorization': f"Bearer {supabase_key}",
        'Content-Type': 'application/json',
        'Prefer': 'resolution=merge-duplicates'
    }

    synced = 0
    for art in articles:
        payload = {
            'title': art.get('titulo_ia') or art.get('title'),
            'slug': art.get('slug'),
            'description': art.get('meta_description') or art.get('description'),
            'text': art.get('contenido_ia') or art.get('text'),
            'image_url': art.get('image_url') or art.get('imageUrl'),
            'autor': art.get('autor') or 'Equipo Editorial',
            'categoria': art.get('categoria') or 'Local',
            'featureStatus': art.get('featureStatus'),
            'meta_title': art.get('titulo_ia') or art.get('title'),
            'meta_description': art.get('meta_description') or art.get('description'),
            'meta_keywords': ', '.join(art.get('meta_keywords', [])) if isinstance(art.get('meta_keywords'), list) else art.get('meta_keywords'),
            'updatedAt': datetime.now().isoformat()
        }

        try:
            if HAS_REQUESTS:
                resp = requests.post(api_url, headers=headers, json=payload, timeout=15)
                if resp.status_code in (200, 201, 204):
                    synced += 1
            else:
                req = urllib.request.Request(api_url, data=json.dumps(payload).encode('utf-8'), headers=headers, method='POST')
                with urllib.request.urlopen(req, timeout=15) as r:
                    if r.status in (200, 201, 204):
                        synced += 1
        except Exception:
            pass

    print(f"[OK] Sincronizados {synced} artículos con Supabase.")
    return synced

# ==============================================================================
# FUNCIÓN PRINCIPAL DE EJECUCIÓN
# ==============================================================================
def process_articles_with_ai(input_path='data/scraped_articles.json',
                             output_path='data/modified_articles.json',
                             limit=None,
                             sync_supabase=False,
                             force_provider=None):
    """
    Carga artículos scrapeados, los optimiza con IA mediante la estrategia
    free-first, asigna prioridades editoriales y persiste los resultados.
    """
    if not os.path.exists(input_path):
        print(f"[!] Archivo de entrada no encontrado: '{input_path}'")
        print("[i] Ejecute primero 'python simple_scraper.py' para recopilar noticias.")
        return []

    with open(input_path, 'r', encoding='utf-8') as f:
        articles = json.load(f)

    if not articles:
        print("[i] No hay artículos para procesar en el archivo de entrada.")
        return []

    if limit:
        articles_to_process = articles[:limit]
    else:
        articles_to_process = articles

    print("=================================================================")
    print(" SALADILLO VIVO — REESCRITURA PERIODÍSTICA CON IA (FREE-FIRST)")
    print(f" Inicio: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f" Artículos a procesar: {len(articles_to_process)} de {len(articles)}")
    print(f" Prioridad de proveedores: GLM -> Gemini -> OpenAI -> Fallback Heurístico")
    print(f" Proveedor forzado: {force_provider or 'Automático'}")
    print("=================================================================")

    modified_list = []
    featured_assigned = False

    for idx, article in enumerate(articles_to_process, 1):
        title = article.get('title') or article.get('titulo') or 'Sin título'
        print(f"\n[{idx}/{len(articles_to_process)}] Procesando: \"{title[:65]}...\"")

        # Modificación con IA
        ai_result = modify_content_with_ai(article, force_provider=force_provider)

        # Cálculo de prioridad editorial
        priority = determine_priority(article)

        # Garantizar que sólo una noticia sea 'featured' por lote para respetar la portada
        if priority == 'featured':
            if featured_assigned:
                priority = 'secondary'
            else:
                featured_assigned = True

        # Enriquecer el objeto de la noticia
        enhanced_article = dict(article)
        enhanced_article.update({
            'titulo_ia': ai_result.get('titulo_optimizado') or title,
            'contenido_ia': ai_result.get('contenido_optimizado') or article.get('text', ''),
            'meta_description': ai_result.get('meta_description') or article.get('description', ''),
            'meta_keywords': ai_result.get('palabras_clave', ["Saladillo", "Saladillo Vivo"]),
            'featureStatus': priority,
            'ia_provider_used': ai_result.get('_provider', 'unknown'),
            'priority_score': calculate_priority_score(article),
            'modified_at': datetime.now().isoformat()
        })

        modified_list.append(enhanced_article)
        time.sleep(1.0)  # Pausa de cortesía entre llamadas

    # Guardar en archivo de salida
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(modified_list, f, ensure_ascii=False, indent=2)

    print(f"\n[OK] Guardados {len(modified_list)} artículos modificados en '{output_path}'.")

    # Sincronizar con Supabase si fue requerido
    if sync_supabase:
        sync_modified_to_supabase(modified_list)

    return modified_list

def main():
    """CLI para ejecución directa."""
    import argparse
    parser = argparse.ArgumentParser(description="Sistema de Modificación de Noticias con IA para Saladillo Vivo")
    parser.add_argument('--input', type=str, default='data/scraped_articles.json', help='Ruta del archivo de entrada JSON')
    parser.add_argument('--output', type=str, default='data/modified_articles.json', help='Ruta del archivo de salida JSON')
    parser.add_argument('--limit', type=int, default=None, help='Límite de artículos a procesar (default: todos)')
    parser.add_argument('--sync-supabase', action='store_true', help='Sincronizar directamente con Supabase')
    parser.add_argument('--provider', type=str, choices=['glm', 'gemini', 'openai'], default=None, help='Forzar un proveedor específico')

    args = parser.parse_args()

    process_articles_with_ai(
        input_path=args.input,
        output_path=args.output,
        limit=args.limit,
        sync_supabase=args.sync_supabase,
        force_provider=args.provider
    )

if __name__ == '__main__':
    main()
