#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
publish_to_supabase.py — Sistema de Publicación y Persistencia Directo a Supabase
================================================================================
Desarrollado para: Saladillo Vivo (Next.js 15 + Supabase)
Objetivo: Gestionar el ciclo de persistencia de noticias en la tabla `articles`:
  - Fase 1 (Borrador): Ingesta inicial de noticias scrapeadas ('draft', is_published=False).
  - Fase 2 (Actualización IA): Actualización de títulos, textos, keywords y featureStatus.
  - Fase 3 (Publicación): Publicación definitiva ('published', is_published=True).

Cumple estrictamente con:
- Cero dependencias forzadas: `requests` + biblioteca estándar.
- Deduplicación algorítmica de slugs.
- Compatibilidad total con la tabla `articles` y la API REST de Supabase.
- NO modifica el reproductor de video, estética ni frontend.
"""

import os
import sys
import json
import time
import uuid
import unicodedata
import re
from datetime import datetime

# Asegurar encoding UTF-8 en Windows
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

try:
    import requests
except ImportError:
    print("[!] Error crítico: La biblioteca 'requests' es requerida para este módulo.")
    print("    Ejecute: pip install requests")
    sys.exit(1)

# Importar agentes modulares si están disponibles
try:
    from agents.storage_agent import StorageAgent, load_env_credentials
    from agents.publisher_agent import PublisherAgent
    USE_MODULAR_AGENTS = True
except ImportError:
    USE_MODULAR_AGENTS = False


# ==============================================================================
# CARGA DE CONFIGURACIÓN Y CREDENCIALES
# ==============================================================================
def get_credentials():
    """Lee variables desde el sistema y desde .env.local / .env."""
    env = {}
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
                            k, v = k.strip(), v.strip().strip("'\"")
                            if k not in env:
                                env[k] = v
            except Exception:
                pass

    for k, v in os.environ.items():
        env[k] = v

    supabase_url = env.get('NEXT_PUBLIC_SUPABASE_URL', 'https://otwvfihzaznyjvjtkvvd.supabase.co').rstrip('/')
    supabase_key = (
        env.get('SUPABASE_KEY') or
        env.get('SUPABASE_SERVICE_ROLE_KEY') or
        env.get('NEXT_PUBLIC_SUPABASE_ANON_KEY')
    )
    return supabase_url, supabase_key


SUPABASE_URL, SUPABASE_KEY = get_credentials()

SUPABASE_CONFIG = {
    'url': SUPABASE_URL,
    'key': SUPABASE_KEY,
    'table': 'articles'
}


# ==============================================================================
# CABECERAS HTTP Y AUTENTICACIÓN
# ==============================================================================
def get_supabase_headers(return_representation=True):
    """Genera cabeceras HTTP para autenticación con la API REST de Supabase."""
    headers = {
        'Authorization': f'Bearer {SUPABASE_CONFIG["key"]}',
        'Content-Type': 'application/json',
        'apikey': SUPABASE_CONFIG['key'],
    }
    if return_representation:
        headers['Prefer'] = 'return=representation'
    else:
        headers['Prefer'] = 'return=minimal'
    return headers


# ==============================================================================
# VERIFICACIÓN DE CONEXIÓN
# ==============================================================================
def verify_supabase_connection():
    """Verifica conectividad y credenciales con Supabase."""
    if not SUPABASE_CONFIG['key']:
        print("[!] Error: No se encontró SUPABASE_KEY ni NEXT_PUBLIC_SUPABASE_ANON_KEY.")
        return False

    try:
        url = f"{SUPABASE_CONFIG['url']}/rest/v1/{SUPABASE_CONFIG['table']}?select=id&limit=1"
        headers = get_supabase_headers(return_representation=False)
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            print(f"[OK] Conexión con Supabase verificada exitosamente ({SUPABASE_CONFIG['url']}).")
            return True
        else:
            print(f"[!] Error de conexión con Supabase: HTTP {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"[!] Excepción verificando conexión con Supabase: {e}")
        return False


# ==============================================================================
# DEDUPLICACIÓN DE SLUGS
# ==============================================================================
def slugify_title(text):
    """Convierte un título en slug limpio."""
    if not text:
        return f"noticia-{int(time.time())}"
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('utf-8')
    text = re.sub(r'[^\w\s-]', '', text).strip().lower()
    clean_slug = re.sub(r'[-\s]+', '-', text)
    return clean_slug[:90].rstrip('-')


def check_slug_exists(slug):
    """Verifica si el slug ya existe en la base de datos."""
    try:
        url = f"{SUPABASE_CONFIG['url']}/rest/v1/{SUPABASE_CONFIG['table']}"
        params = {'select': 'slug', 'slug': f'eq.{slug}', 'limit': 1}
        headers = get_supabase_headers(return_representation=False)
        response = requests.get(url, params=params, headers=headers, timeout=15)
        if response.status_code == 200:
            data = response.json()
            return len(data) > 0
        return False
    except Exception:
        return False


def generate_unique_slug(base_title):
    """Genera un slug único sin colisiones."""
    base_slug = slugify_title(base_title)
    if not check_slug_exists(base_slug):
        return base_slug

    counter = 1
    new_slug = f"{base_slug}-{counter}"
    while check_slug_exists(new_slug):
        counter += 1
        new_slug = f"{base_slug}-{counter}"
    return new_slug


# ==============================================================================
# PASO 2: GUARDAR EN BASE DE DATOS COMO BORRADOR
# ==============================================================================
def save_draft_to_supabase(article_data):
    """
    Inserta un artículo scrapeado como borrador inicial en Supabase.
    Retorna el ID asignado.
    """
    if USE_MODULAR_AGENTS:
        storage = StorageAgent(table=SUPABASE_CONFIG['table'])
        record = storage.save_draft(article_data)
        return record.get('id') if record else None

    title = article_data.get('original_title') or article_data.get('title') or 'Noticia sin título'
    text = article_data.get('original_text') or article_data.get('text') or ''
    desc = article_data.get('original_description') or article_data.get('description') or text[:200]
    img = article_data.get('image_url') or 'https://saladillovivo.vercel.app/default-og-image.png'
    slug = generate_unique_slug(title)
    now_iso = datetime.now().isoformat()

    payload = {
        'title': title,
        'text': text,
        'description': desc[:300],
        'slug': slug,
        'image_url': img,
        'thumbnail_url': img,
        'og_image_url': img,
        'featureStatus': 'secondary',
        'status': 'draft',
        'is_published': False,
        'created_at': article_data.get('created_at') or now_iso,
        'updatedAt': now_iso
    }

    url = f"{SUPABASE_CONFIG['url']}/rest/v1/{SUPABASE_CONFIG['table']}"
    headers = get_supabase_headers(return_representation=True)
    current_payload = dict(payload)

    for _ in range(5):
        resp = requests.post(url, headers=headers, json=current_payload, timeout=25)
        if resp.status_code in (200, 201):
            created = resp.json()[0]
            article_data['id'] = created['id']
            return created['id']
        elif resp.status_code == 400 and 'in the schema cache' in resp.text:
            m = re.search(r"'(\w+)' column", resp.text)
            if m and m.group(1) in current_payload:
                del current_payload[m.group(1)]
                continue
        break
    return None


# ==============================================================================
# PASO 4: OTRA VEZ GUARDAR EN BASE DE DATOS (ACTUALIZAR CON IA)
# ==============================================================================
def update_article_with_ai(article_id, ai_data):
    """
    Actualiza el registro existente en Supabase con los datos procesados por IA.
    """
    if USE_MODULAR_AGENTS:
        storage = StorageAgent(table=SUPABASE_CONFIG['table'])
        return storage.update_with_ai(article_id, ai_data)

    if not article_id:
        return None

    now_iso = datetime.now().isoformat()
    title = ai_data.get('titulo_ia') or ai_data.get('title')
    text = ai_data.get('contenido_ia') or ai_data.get('text')
    desc = ai_data.get('meta_description') or ai_data.get('description') or ''
    keywords = ai_data.get('meta_keywords') or ai_data.get('palabras_clave') or []
    kw_str = ', '.join(keywords) if isinstance(keywords, list) else str(keywords)

    payload = {
        'title': title,
        'text': text,
        'description': desc[:300],
        'meta_title': title,
        'meta_description': desc[:160],
        'meta_keywords': kw_str,
        'featureStatus': ai_data.get('featureStatus') or 'secondary',
        'status': 'ai_processed',
        'updatedAt': now_iso
    }

    url = f"{SUPABASE_CONFIG['url']}/rest/v1/{SUPABASE_CONFIG['table']}?id=eq.{article_id}"
    headers = get_supabase_headers(return_representation=True)
    current_payload = dict(payload)

    for _ in range(5):
        resp = requests.patch(url, headers=headers, json=current_payload, timeout=25)
        if resp.status_code in (200, 204):
            return resp.json() if resp.text else current_payload
        elif resp.status_code == 400 and 'in the schema cache' in resp.text:
            m = re.search(r"'(\w+)' column", resp.text)
            if m and m.group(1) in current_payload:
                del current_payload[m.group(1)]
                continue
        break
    return None


# ==============================================================================
# PASO 5: FINALMENTE PUBLICAR
# ==============================================================================
def publish_article_in_db(article_id, image_url=None, immediate=True):
    """
    Paso 5: Marca el artículo como publicado en Supabase.
    """
    if USE_MODULAR_AGENTS:
        pub = PublisherAgent()
        return pub.publish_article(article_id, image_url=image_url, immediate=immediate)

    if not article_id:
        return None

    now_iso = datetime.now().isoformat()
    img = image_url or 'https://saladillovivo.vercel.app/default-og-image.png'
    payload = {
        'is_published': True if immediate else False,
        'status': 'published',
        'published_at': now_iso,
        'publish_at': now_iso,
        'updatedAt': now_iso,
        'miniatura_url': img,
        'og_image_url': img
    }

    url = f"{SUPABASE_CONFIG['url']}/rest/v1/{SUPABASE_CONFIG['table']}?id=eq.{article_id}"
    headers = get_supabase_headers(return_representation=True)
    resp = requests.patch(url, headers=headers, json=payload, timeout=25)
    return resp.json() if (resp.status_code in (200, 204) and resp.text) else None


# ==============================================================================
# FUNCIÓN COMPLETA LEGACY (INSERTA Y PUBLICA DIRECTAMENTE)
# ==============================================================================
def publish_article(article_data, immediate=True):
    """Publica un artículo individual en Supabase."""
    title = article_data.get('titulo_ia') or article_data.get('title') or 'Noticia de Saladillo'
    text = article_data.get('contenido_ia') or article_data.get('text') or ''
    desc = article_data.get('meta_description') or article_data.get('description') or text[:160]
    img = article_data.get('image_url') or 'https://saladillovivo.vercel.app/default-og-image.png'

    slug = generate_unique_slug(title)
    now_iso = datetime.now().isoformat()
    raw_kw = article_data.get('meta_keywords') or []
    kw_str = ', '.join(raw_kw) if isinstance(raw_kw, list) else str(raw_kw)

    payload = {
        'title': title,
        'slug': slug,
        'description': desc[:300],
        'text': text,
        'image_url': img,
        'thumbnail_url': img,
        'og_image_url': img,
        'featureStatus': article_data.get('featureStatus') or 'secondary',
        'status': 'published',
        'is_published': immediate,
        'published_at': now_iso,
        'publish_at': now_iso,
        'created_at': article_data.get('created_at') or now_iso,
        'updatedAt': now_iso,
        'meta_title': title,
        'meta_description': desc[:160],
        'meta_keywords': kw_str
    }

    url = f"{SUPABASE_CONFIG['url']}/rest/v1/{SUPABASE_CONFIG['table']}"
    headers = get_supabase_headers(return_representation=True)
    current_payload = dict(payload)

    for _ in range(5):
        resp = requests.post(url, headers=headers, json=current_payload, timeout=25)
        if resp.status_code in (200, 201):
            created = resp.json()[0]
            print(f"  [OK] Publicado: \"{title[:50]}...\" (ID: {created.get('id')})")
            return created.get('id')
        elif resp.status_code == 400 and 'in the schema cache' in resp.text:
            m = re.search(r"'(\w+)' column", resp.text)
            if m and m.group(1) in current_payload:
                del current_payload[m.group(1)]
                continue
        print(f"  [!] Error publicando ({resp.status_code}): {resp.text}")
        break
    return None


def publish_to_supabase(input_file='data/modified_articles.json', report_file='data/publish_report.json', limit=None):
    """Carga artículos modificados y los publica en Supabase."""
    if not os.path.exists(input_file):
        print(f"[!] Archivo de entrada no encontrado: '{input_file}'")
        return None

    with open(input_file, 'r', encoding='utf-8') as f:
        articles = json.load(f)

    if limit:
        articles = articles[:limit]

    print(f"\n=================================================================")
    print(f" PUBLICANDO {len(articles)} ARTÍCULOS EN SUPABASE")
    print(f"=================================================================")

    published_count = 0
    failed_articles = []
    published_items = []

    for art in articles:
        art_id = publish_article(art, immediate=True)
        if art_id:
            published_count += 1
            published_items.append({'id': art_id, 'title': art.get('title')})
        else:
            failed_articles.append(art.get('title'))
        time.sleep(0.8)

    report = {
        'status': 'success' if published_count > 0 else 'failed',
        'published_count': published_count,
        'failed_count': len(failed_articles),
        'failed_articles': failed_articles,
        'published_items': published_items,
        'total_articles': len(articles),
        'timestamp': datetime.now().isoformat()
    }

    os.makedirs(os.path.dirname(os.path.abspath(report_file)), exist_ok=True)
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    return report


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Publicador y Gestor de Supabase para Saladillo Vivo")
    parser.add_argument('--input', type=str, default='data/modified_articles.json', help='Ruta del JSON')
    parser.add_argument('--report', type=str, default='data/publish_report.json', help='Ruta del reporte')
    parser.add_argument('--limit', type=int, default=None, help='Límite de artículos')
    parser.add_argument('--check-only', action='store_true', help='Verificar conexión y salir')
    parser.add_argument('--phase', type=str, default='all', choices=['all', 'draft', 'update-ai', 'publish'], help='Fase a ejecutar')

    args = parser.parse_args()

    if not verify_supabase_connection():
        sys.exit(1)

    if args.check_only:
        return

    report = publish_to_supabase(input_file=args.input, report_file=args.report, limit=args.limit)
    if not report or report['published_count'] == 0:
        sys.exit(1)


if __name__ == '__main__':
    main()
