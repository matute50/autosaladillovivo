#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
publish_to_supabase.py — Sistema de Publicación Directo a Supabase
===================================================================
Desarrollado para: Saladillo Vivo (Next.js 15 + Supabase)
Objetivo: Publicar noticias procesadas en la tabla `articles` de Supabase respetando
los esquemas de metadatos, control de duplicados por slug, y preparación para la
automatización de redes sociales (Instagram, Facebook y Make.com).

Características:
- Cero dependencias forzadas: Implementado con `requests` y la biblioteca estándar.
- Deduplicación algorítmica de slugs (consulta en tiempo real a Supabase).
- Verificación previa del estado de la conexión con la base de datos.
- Sincronización con el flujo de automatización de redes:
  `is_published: false`, `miniatura_url`, `og_image_url`, `publish_at`.
- Manejo inteligente de tipos de Primary Key (soporta IDs de texto, UUIDs y autoincrementales).
- Generación de informe de auditoría detallado en `data/publish_report.json`.
- Política de oro: NO modifica reproductor de video, estética ni lógica del frontend.
"""

import os
import sys
import json
import time
import uuid
import unicodedata
import re
from datetime import datetime

# Asegurar soporte de encoding en terminales Windows
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

# ==============================================================================
# CARGA DE CONFIGURACIÓN Y CREDENCIALES
# ==============================================================================
def load_env_credentials():
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

SUPABASE_URL, SUPABASE_KEY = load_env_credentials()

SUPABASE_CONFIG = {
    'url': SUPABASE_URL,
    'key': SUPABASE_KEY,
    'table': 'articles'
}

# ==============================================================================
# CABECERAS HTTP Y AUTENTICACIÓN
# ==============================================================================
def get_supabase_headers(return_representation=True):
    """
    Genera cabeceras HTTP para autenticación con la API REST de Supabase.
    'Prefer: return=representation' permite que PostgREST devuelva el objeto insertado con su ID.
    """
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
    """
    Verifica que las credenciales y la conectividad con Supabase sean válidas.
    """
    if not SUPABASE_CONFIG['key']:
        print("[!] Error: No se encontró SUPABASE_KEY ni NEXT_PUBLIC_SUPABASE_ANON_KEY.")
        print("    Configure la variable en su entorno o en el archivo .env.local.")
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
# SISTEMA DE DEDUPLICACIÓN DE SLUGS
# ==============================================================================
def slugify_title(text):
    """Convierte un título en una cadena alfanumérica en minúsculas y sin acentos."""
    if not text:
        return f"noticia-{int(time.time())}"
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('utf-8')
    text = re.sub(r'[^\w\s-]', '', text).strip().lower()
    clean_slug = re.sub(r'[-\s]+', '-', text)
    return clean_slug[:90].rstrip('-')

def check_slug_exists(slug):
    """
    Verifica mediante la API REST de Supabase si el slug ya existe en la base de datos.
    """
    try:
        url = f"{SUPABASE_CONFIG['url']}/rest/v1/{SUPABASE_CONFIG['table']}"
        params = {
            'select': 'slug',
            'slug': f'eq.{slug}',
            'limit': 1
        }
        headers = get_supabase_headers(return_representation=False)
        response = requests.get(url, params=params, headers=headers, timeout=15)

        if response.status_code == 200:
            data = response.json()
            return len(data) > 0

        return False
    except Exception as e:
        print(f"  [!] Advertencia al verificar slug '{slug}': {e}")
        return False

def generate_unique_slug(base_title):
    """
    Genera un slug único asegurando que no colisione con artículos existentes.
    Si colisiona, anexa un sufijo secuencial (-1, -2, etc.).
    """
    base_slug = slugify_title(base_title)
    if not base_slug:
        base_slug = f"noticia-{int(time.time())}"

    if not check_slug_exists(base_slug):
        return base_slug

    counter = 1
    new_slug = f"{base_slug}-{counter}"
    while check_slug_exists(new_slug):
        counter += 1
        new_slug = f"{base_slug}-{counter}"

    return new_slug

# ==============================================================================
# PUBLICACIÓN DE ARTÍCULO INDIVIDUAL
# ==============================================================================
def publish_article(article_data):
    """
    Mapea y publica un artículo individual en la tabla 'articles' existente.
    """
    title_to_use = (
        article_data.get('titulo_ia') or
        article_data.get('title') or
        article_data.get('titulo') or
        'Noticia de Saladillo Vivo'
    )

    content_to_use = (
        article_data.get('contenido_ia') or
        article_data.get('text') or
        article_data.get('contenido') or
        article_data.get('content') or
        ''
    )

    desc_to_use = (
        article_data.get('meta_description') or
        article_data.get('description') or
        article_data.get('resumen') or
        (content_to_use[:160] if content_to_use else '')
    )

    image_to_use = (
        article_data.get('image_url') or
        article_data.get('imageUrl') or
        'https://saladillovivo.vercel.app/default-og-image.png'
    )

    # Slug único garantizado
    unique_slug = generate_unique_slug(title_to_use)

    # Keywords en formato string o array compatible
    raw_keywords = article_data.get('meta_keywords') or article_data.get('palabras_clave') or []
    if isinstance(raw_keywords, list):
        keywords_str = ', '.join(raw_keywords)
    else:
        keywords_str = str(raw_keywords)

    now_iso = datetime.now().isoformat()
    created_at = article_data.get('created_at') or article_data.get('scraped_at') or now_iso
    publish_at = article_data.get('published_at') or article_data.get('publish_at') or now_iso

    # Mapeo idéntico al esquema de Supabase documentado y verificado en la base de datos
    mapped_article = {
        'title': title_to_use,
        'slug': unique_slug,
        'description': desc_to_use,
        'text': content_to_use,
        'image_url': image_to_use,
        'featureStatus': article_data.get('featureStatus') or 'secondary',
        'created_at': created_at,
        'updatedAt': now_iso,
        'published_at': publish_at,
        'publish_at': publish_at,
        'is_published': False,  # False para que el cron de redes sociales (Make.com / Vercel) lo tome y publique
        'og_image_url': image_to_use,   # Proporción 1.91:1 para Facebook / OpenGraph
        'meta_title': title_to_use,
        'meta_description': desc_to_use[:160],
        'meta_keywords': keywords_str
    }

    url = f"{SUPABASE_CONFIG['url']}/rest/v1/{SUPABASE_CONFIG['table']}"
    headers = get_supabase_headers(return_representation=True)

    try:
        # Mecanismo auto-adaptativo con reintentos si alguna columna no está en el schema cache
        current_payload = dict(mapped_article)
        response = None

        for _ in range(5):
            response = requests.post(url, headers=headers, json=current_payload, timeout=25)

            if response.status_code in (200, 201):
                break

            # Si alguna columna no existe en el esquema de Supabase, la eliminamos y reintentamos
            if response.status_code == 400 and 'in the schema cache' in response.text:
                m = re.search(r"'(\w+)' column", response.text)
                if m:
                    missing_col = m.group(1)
                    if missing_col in current_payload:
                        del current_payload[missing_col]
                        continue
            break

        if response and response.status_code in (200, 201):
            try:
                res_data = response.json()
                article_id = res_data[0].get('id', unique_slug) if isinstance(res_data, list) and res_data else unique_slug
            except Exception:
                article_id = unique_slug

            print(f"  [OK] Publicado exitosamente: \"{title_to_use[:55]}...\" (ID: {article_id} | Slug: {unique_slug})")
            return article_id
        else:
            err_msg = response.text if response else "Sin respuesta"
            print(f"  [!] Fallo publicando ({response.status_code if response else 'ERR'}): {err_msg}")
            return None

    except Exception as e:
        print(f"  [!] Excepción publicando \"{title_to_use[:50]}\": {e}")
        return None

# ==============================================================================
# PUBLICACIÓN MASIVA Y GENERACIÓN DE REPORTE
# ==============================================================================
def publish_to_supabase(input_file='data/modified_articles.json',
                        report_file='data/publish_report.json',
                        limit=None):
    """
    Lee artículos procesados y los publica en Supabase, generando un reporte final.
    """
    if not os.path.exists(input_file):
        # Fallback a artículos scrapeados originales si modified_articles.json aún no existe
        alt_input = 'data/scraped_articles.json'
        if os.path.exists(alt_input):
            print(f"[i] No se encontró '{input_file}', usando '{alt_input}'.")
            input_file = alt_input
        else:
            print(f"[!] No se encontró '{input_file}' ni '{alt_input}'.")
            print("    Ejecute primero 'python simple_scraper.py' o 'python free_rewriter.py'.")
            return None

    with open(input_file, 'r', encoding='utf-8') as f:
        articles = json.load(f)

    if not articles:
        print("[i] El archivo de entrada no contiene artículos.")
        return None

    if limit:
        articles_to_publish = articles[:limit]
    else:
        articles_to_publish = articles

    print("=================================================================")
    print(" SALADILLO VIVO — PUBLICACIÓN DIRECTA A SUPABASE")
    print(f" Inicio: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f" Origen de datos: '{input_file}'")
    print(f" Total a procesar: {len(articles_to_publish)} de {len(articles)}")
    print("=================================================================")

    published_count = 0
    failed_articles = []
    published_items = []

    for idx, article in enumerate(articles_to_publish, 1):
        title = article.get('titulo_ia') or article.get('title') or 'Sin título'
        print(f"\n[{idx}/{len(articles_to_publish)}] Procesando publicación...")

        article_id = publish_article(article)

        if article_id:
            published_count += 1
            published_items.append({
                'id': article_id,
                'title': title,
                'slug': article.get('slug'),
                'timestamp': datetime.now().isoformat()
            })
        else:
            failed_articles.append({
                'title': title,
                'timestamp': datetime.now().isoformat()
            })

        # Pausa de 0.8s para cortesía y control de rate limiting de Supabase
        time.sleep(0.8)

    # Generar informe de auditoría
    report = {
        'status': 'success' if published_count > 0 else 'failed',
        'published_count': published_count,
        'failed_count': len(failed_articles),
        'failed_articles': failed_articles,
        'published_items': published_items,
        'timestamp': datetime.now().isoformat(),
        'total_articles': len(articles_to_publish),
        'source_file': input_file
    }

    os.makedirs(os.path.dirname(os.path.abspath(report_file)), exist_ok=True)
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n=================================================================")
    print(f"[OK] Proceso de publicación concluido.")
    print(f"     Artículos publicados: {published_count}/{len(articles_to_publish)}")
    print(f"     Artículos fallidos:   {len(failed_articles)}")
    print(f"     Reporte guardado en:  '{report_file}'")
    print("=================================================================")

    return report

def main():
    """Punto de entrada de línea de comandos."""
    import argparse
    parser = argparse.ArgumentParser(description="Publicador Directo de Noticias en Supabase para Saladillo Vivo")
    parser.add_argument('--input', type=str, default='data/modified_articles.json', help='Ruta del archivo JSON de noticias')
    parser.add_argument('--report', type=str, default='data/publish_report.json', help='Ruta de salida del reporte JSON')
    parser.add_argument('--limit', type=int, default=None, help='Límite de artículos a publicar')
    parser.add_argument('--check-only', action='store_true', help='Verificar únicamente la conexión y salir')

    args = parser.parse_args()

    print("[*] Verificando conexión con Supabase...")
    if not verify_supabase_connection():
        print("[!] Conexión fallida. Abortando publicación.")
        sys.exit(1)

    if args.check_only:
        print("[OK] Verificación completada con éxito. No se realizaron inserciones.")
        return

    report = publish_to_supabase(
        input_file=args.input,
        report_file=args.report,
        limit=args.limit
    )

    if not report or report['published_count'] == 0 and report['total_articles'] > 0:
        sys.exit(1)

if __name__ == '__main__':
    main()
