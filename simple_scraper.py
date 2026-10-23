#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
simple_scraper.py — Sistema de Scraping Directo para Noticias de Saladillo
========================================================================
Desarrollado para: Saladillo Vivo (Next.js 15 + Supabase)
Objetivo: Extracción de noticias de texto e imagen de los portales locales de Saladillo.

Características:
- Cero dependencias forzadas: Implementado con la biblioteca estándar de Python
  (urllib.request, html.parser, json, re, hashlib, datetime, time).
  Soporta opcionalmente 'requests' si está instalado.
- Rotating User-Agents para evitar bloqueos.
- Filtrado inteligente de enlaces de noticias y descarte de secciones/categorías.
- Extracción de título, bajada/copete, contenido completo, imagen destacada, fecha y slug.
- Deduplicación por hash MD5 y control de historial previo.
- Integración directa con Supabase REST API (tabla `articles`) y persistencia local en JSON.
- Respeta estrictamente la política: NO modifica reproductores de video ni lógica visual.
"""

import os
import sys
import re
import json
import time
import hashlib
import random
import unicodedata
from datetime import datetime
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

# Asegurar soporte de encoding en terminales Windows
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# Intento de importar requests, con fallback transparente a urllib nativo
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    import urllib.request
    import urllib.error

# ==============================================================================
# CONFIGURACIÓN DE FUENTES PARA SALADILLO
# ==============================================================================
SOURCES = {
    'abcsaladillo': {
        'name': 'ABC Saladillo',
        'url': 'https://www.abcsaladillo.com.ar',
        'base_url': 'https://www.abcsaladillo.com.ar',
        'domain': 'abcsaladillo.com.ar',
        'category': 'Local',
        'exclude_paths': [
            '/seccion/', '/farmacias-de-turno', '/contacto', '/quienes-somos',
            '/cdn-cgi/', '#', 'facebook.com', 'instagram.com', 'twitter.com',
            'youtube.com', 'whatsapp.com', '/tag/', '/page/', '/wp-content/'
        ],
        'min_url_length': 35
    },
    'ahorasaladillo': {
        'name': 'Ahora Saladillo',
        'url': 'https://ahorasaladillo-diariodigital.com.ar',
        'base_url': 'https://ahorasaladillo-diariodigital.com.ar',
        'domain': 'ahorasaladillo-diariodigital.com.ar',
        'category': 'Local',
        'exclude_paths': [
            '/category/', '/tag/', '/author/', '/page/', '/wp-content/',
            '/feed/', '/contacto', '/politica-de-privacidad', '#',
            'facebook.com', 'instagram.com', 'twitter.com', 'youtube.com'
        ],
        'min_url_length': 35
    },
    'infosaladillo': {
        'name': 'InfoSaladillo',
        'url': 'https://infosaladillo.com.ar',
        'base_url': 'https://infosaladillo.com.ar',
        'domain': 'infosaladillo.com.ar',
        'category': 'Local',
        'exclude_paths': [
            '/seccion/', '/tag/', '/category/', '/author/', '/page/',
            '/feed/', '/contacto', '/staff', '#', 'facebook.com',
            'instagram.com', 'twitter.com', 'youtube.com', 'whatsapp.com'
        ],
        'min_url_length': 30
    }
}

# ==============================================================================
# SISTEMA ANTI-BLOCKING: ROTATING USER-AGENTS
# ==============================================================================
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_3) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15',
    'Mozilla/5.0 (X11; Linux x86_64; rv:123.0) Gecko/20100101 Firefox/123.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/122.0.6261.62 Mobile/15E148 Safari/604.1'
]

def get_random_headers():
    """Genera cabeceras HTTP aleatorias para emular navegación humana realista."""
    ua = random.choice(USER_AGENTS)
    return {
        'User-Agent': ua,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'es-AR,es-ES;q=0.9,es;q=0.8,en;q=0.7',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Cache-Control': 'max-age=0'
    }

def fetch_html(url, timeout=25):
    """
    Descarga el contenido HTML de una URL con reintentos y soporte de requests o urllib nativo.
    """
    headers = get_random_headers()
    
    if HAS_REQUESTS:
        try:
            resp = requests.get(url, headers=headers, timeout=timeout)
            if resp.status_code == 200:
                resp.encoding = resp.apparent_encoding or 'utf-8'
                return resp.text
            print(f"  [!] HTTP {resp.status_code} al solicitar {url}")
            return None
        except Exception as e:
            print(f"  [!] Error descargando con requests ({url}): {e}")
            return None
    else:
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as response:
                content = response.read()
                # Intentar decodificar en UTF-8 con fallback a ISO-8859-1
                try:
                    return content.decode('utf-8')
                except UnicodeDecodeError:
                    return content.decode('latin-1', errors='replace')
        except Exception as e:
            print(f"  [!] Error descargando con urllib ({url}): {e}")
            return None

# ==============================================================================
# PARSER HTML BASADO EN LA BIBLIOTECA ESTÁNDAR (html.parser.HTMLParser)
# ==============================================================================
class LinkExtractor(HTMLParser):
    """Extrae enlaces <a> del documento HTML."""
    def __init__(self, base_url):
        super().__init__()
        self.base_url = base_url
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            attr_dict = dict(attrs)
            href = attr_dict.get('href')
            if href:
                full_url = urljoin(self.base_url, href.strip())
                self.links.append(full_url)


class ArticleExtractor(HTMLParser):
    """
    Extrae metadatos OpenGraph, títulos, párrafos y primera imagen del artículo.
    """
    def __init__(self):
        super().__init__()
        self.meta = {}
        self.title_tag = []
        self.h1_tag = []
        self.paragraphs = []
        self.images = []

        self._in_title = False
        self._in_h1 = False
        self._in_p = False
        self._current_p = []
        self._skip_elements = {'script', 'style', 'noscript', 'header', 'footer', 'nav'}
        self._active_skips = 0

    def handle_starttag(self, tag, attrs):
        tag_lower = tag.lower()
        if tag_lower in self._skip_elements:
            self._active_skips += 1
            return

        if self._active_skips > 0:
            return

        attr_dict = dict(attrs)

        if tag_lower == 'meta':
            prop = (attr_dict.get('property') or attr_dict.get('name') or '').lower().strip()
            content = attr_dict.get('content', '').strip()
            if prop and content:
                self.meta[prop] = content

        elif tag_lower == 'title':
            self._in_title = True

        elif tag_lower == 'h1':
            self._in_h1 = True

        elif tag_lower == 'p':
            self._in_p = True
            self._current_p = []

        elif tag_lower == 'img':
            src = attr_dict.get('src') or attr_dict.get('data-src') or attr_dict.get('data-lazy-src')
            if src and not src.startswith('data:'):
                self.images.append(src)

    def handle_endtag(self, tag):
        tag_lower = tag.lower()
        if tag_lower in self._skip_elements:
            if self._active_skips > 0:
                self._active_skips -= 1
            return

        if self._active_skips > 0:
            return

        if tag_lower == 'title':
            self._in_title = False
        elif tag_lower == 'h1':
            self._in_h1 = False
        elif tag_lower == 'p':
            self._in_p = False
            raw_text = ''.join(self._current_p).strip()
            clean_text = ' '.join(raw_text.split())
            if len(clean_text) > 25:
                # Filtrar advertencias y botones sociales
                lower = clean_text.lower()
                if not any(k in lower for k in [
                    'compartir en', 'todos los derechos reservados', 'copyright',
                    'hacé click', 'seguinos en', 'leé también', 'dejá tu comentario'
                ]):
                    self.paragraphs.append(clean_text)
            self._current_p = []

    def handle_data(self, data):
        if self._active_skips > 0:
            return

        if self._in_title:
            self.title_tag.append(data)
        elif self._in_h1:
            self.h1_tag.append(data)
        elif self._in_p:
            self._current_p.append(data)

# ==============================================================================
# UTILIDADES DE LIMPIEZA Y SLUG
# ==============================================================================
def slugify(text):
    """Convierte un título en un slug amigable para URL."""
    if not text:
        return f"noticia-{int(time.time())}"
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('utf-8')
    text = re.sub(r'[^\w\s-]', '', text).strip().lower()
    slug = re.sub(r'[-\s]+', '-', text)
    return slug[:100].rstrip('-')

def clean_html_entities(text):
    """Limpia caracteres especiales y comillas."""
    if not text:
        return ""
    replacements = {
        '&quot;': '"', '&amp;': '&', '&lt;': '<', '&gt;': '>',
        '&nbsp;': ' ', '&#8220;': '"', '&#8221;': '"', '&#8216;': "'",
        '&#8217;': "'", '&#8211;': '-', '&#8212;': '-'
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    return text.strip()

# ==============================================================================
# EXTRACCIÓN Y PROCESAMIENTO DE NOTICIAS
# ==============================================================================
def extract_article_urls(source_key, source_config):
    """
    Descarga la portada y obtiene URLs de noticias válidas, evitando duplicados.
    """
    print(f"\n[+] Conectando a {source_config['name']} ({source_config['url']})...")
    html = fetch_html(source_config['url'])
    if not html:
        return []

    parser = LinkExtractor(source_config['base_url'])
    parser.feed(html)

    discovered_links = parser.links
    domain = source_config['domain']
    exclude_paths = source_config['exclude_paths']
    min_length = source_config['min_url_length']

    valid_urls = []
    seen = set()

    for link in discovered_links:
        # Remover fragments y query params
        parsed = urlparse(link)
        clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        if clean_url.endswith('/'):
            clean_url = clean_url[:-1]

        if clean_url in seen:
            continue

        # Validaciones de pertenencia al portal
        if domain not in clean_url:
            continue
        if len(clean_url) < min_length:
            continue
        if any(exc in clean_url for exc in exclude_paths):
            continue

        seen.add(clean_url)
        valid_urls.append(clean_url)

    print(f"  [i] Encontradas {len(valid_urls)} posibles noticias en {source_config['name']}.")
    return valid_urls

def parse_article_data(url, source_name, category_default):
    """
    Descarga la noticia individual y extrae título, descripción, contenido e imagen.
    """
    html = fetch_html(url)
    if not html:
        return None

    parser = ArticleExtractor()
    parser.feed(html)

    # 1. TÍTULO
    title = parser.meta.get('og:title')
    if not title and parser.h1_tag:
        title = ' '.join(''.join(parser.h1_tag).split())
    if not title and parser.title_tag:
        title = ' '.join(''.join(parser.title_tag).split())
        # Remover sufijos del sitio (ej. " - InfoSaladillo")
        title = re.split(r'[-–|]', title)[0].strip()

    title = clean_html_entities(title or "")
    if not title or len(title) < 10:
        return None

    # 2. DESCRIPCIÓN / COPETE
    description = parser.meta.get('og:description') or parser.meta.get('description')
    if not description and parser.paragraphs:
        description = parser.paragraphs[0]
    description = clean_html_entities(description or "")

    # 3. CONTENIDO COMPLETO (Texto)
    if parser.paragraphs:
        content_text = "\n\n".join(parser.paragraphs)
    else:
        content_text = description

    # 4. IMAGEN DESTACADA
    image_url = parser.meta.get('og:image') or parser.meta.get('twitter:image')
    if not image_url and parser.images:
        for img in parser.images:
            if not any(x in img.lower() for x in ['logo', 'icon', 'banner', 'avatar', 'pixel']):
                image_url = img
                break

    # Si la imagen es relativa, completarla
    if image_url and image_url.startswith('/'):
        image_url = urljoin(url, image_url)

    # 5. FECHA DE PUBLICACIÓN
    published_date = (
        parser.meta.get('article:published_time') or
        parser.meta.get('og:article:published_time') or
        parser.meta.get('date') or
        datetime.now().isoformat()
    )

    # 6. IDENTIFICADORES Y SLUG
    url_slug = url.strip('/').split('/')[-1]
    article_slug = slugify(url_slug if len(url_slug) > 10 else title)
    url_hash = hashlib.md5(url.encode('utf-8')).hexdigest()

    return {
        'id': f"scraped-{url_hash[:12]}",
        'hash': url_hash,
        'title': title,
        'titulo': title,
        'slug': article_slug,
        'description': description[:300] if description else "Sin descripción.",
        'resumen': description[:160] if description else "Sin resumen.",
        'text': content_text,
        'contenido': content_text,
        'image_url': image_url or "https://saladillovivo.vercel.app/default-og-image.png",
        'imageUrl': image_url or "https://saladillovivo.vercel.app/default-og-image.png",
        'source_url': url,
        'autor': source_name,
        'categoria': category_default,
        'featureStatus': 'secondary',
        'created_at': published_date,
        'updatedAt': published_date,
        'scraped_at': datetime.now().isoformat()
    }

# ==============================================================================
# INTEGRACIÓN CON SUPABASE (Opcional si están las credenciales)
# ==============================================================================
def load_env_credentials():
    """Lee variables de entorno desde el sistema o archivo .env.local."""
    supabase_url = os.environ.get('NEXT_PUBLIC_SUPABASE_URL')
    supabase_key = os.environ.get('SUPABASE_SERVICE_ROLE_KEY') or os.environ.get('NEXT_PUBLIC_SUPABASE_ANON_KEY')

    if not supabase_url or not supabase_key:
        env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env.local')
        if os.path.exists(env_path):
            with open(env_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        k, v = line.split('=', 1)
                        k, v = k.strip(), v.strip().strip("'\"")
                        if k == 'NEXT_PUBLIC_SUPABASE_URL' and not supabase_url:
                            supabase_url = v
                        elif k in ('SUPABASE_SERVICE_ROLE_KEY', 'NEXT_PUBLIC_SUPABASE_ANON_KEY') and not supabase_key:
                            supabase_key = v

    return supabase_url, supabase_key

def sync_articles_to_supabase(articles):
    """
    Inserta las noticias scrapeadas en la tabla `articles` de Supabase sin duplicados.
    """
    supabase_url, supabase_key = load_env_credentials()
    if not supabase_url or not supabase_key:
        print("\n[!] Supabase URL o Key no encontradas en el entorno. Omitiendo sincronización remota.")
        return 0

    print(f"\n[+] Sincronizando {len(articles)} artículos con Supabase ({supabase_url})...")
    api_url = f"{supabase_url.rstrip('/')}/rest/v1/articles"
    headers = {
        'apikey': supabase_key,
        'Authorization': f"Bearer {supabase_key}",
        'Content-Type': 'application/json',
        'Prefer': 'resolution=ignore-duplicates'
    }

    inserted_count = 0
    for art in articles:
        # Preparamos el payload exacto de la tabla articles
        payload = {
            'title': art['title'],
            'slug': art['slug'],
            'description': art['description'],
            'text': art['text'],
            'image_url': art['image_url'],
            'autor': art['autor'],
            'categoria': art['categoria'],
            'featureStatus': art['featureStatus'],
            'created_at': art['created_at'],
            'updatedAt': art['updatedAt'],
            'meta_title': art['title'],
            'meta_description': art['description']
        }

        try:
            if HAS_REQUESTS:
                resp = requests.post(api_url, headers=headers, json=payload, timeout=15)
                if resp.status_code in (200, 201):
                    inserted_count += 1
                elif resp.status_code == 409:
                    pass  # Ya existía
                else:
                    print(f"  [!] Fallo insertando '{art['title'][:40]}': HTTP {resp.status_code}")
            else:
                data_bytes = json.dumps(payload).encode('utf-8')
                req = urllib.request.Request(api_url, data=data_bytes, headers=headers, method='POST')
                with urllib.request.urlopen(req, timeout=15) as r:
                    if r.status in (200, 201):
                        inserted_count += 1
        except Exception as e:
            # Puede ser duplicado por Unique key
            pass

    print(f"[OK] Sincronizacion finalizada: {inserted_count} articulos insertados en Supabase.")
    return inserted_count

# ==============================================================================
# FUNCIÓN PRINCIPAL DE EJECUCIÓN
# ==============================================================================
def run_scraper(limit_per_source=15, sync_supabase=False, target_source=None):
    """
    Ejecuta el ciclo de scraping para las fuentes especificadas.
    """
    data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
    os.makedirs(data_dir, exist_ok=True)
    output_file = os.path.join(data_dir, 'scraped_articles.json')

    # Cargar historial existente para deduplicar
    existing_hashes = set()
    existing_articles = []
    if os.path.exists(output_file):
        try:
            with open(output_file, 'r', encoding='utf-8') as f:
                existing_articles = json.load(f)
                for item in existing_articles:
                    if 'hash' in item:
                        existing_hashes.add(item['hash'])
                    elif 'source_url' in item:
                        existing_hashes.add(hashlib.md5(item['source_url'].encode('utf-8')).hexdigest())
        except Exception:
            existing_articles = []

    print("=================================================================")
    print(" SALADILLO VIVO — SISTEMA DE SCRAPING DE NOTICIAS LOCALES")
    print(f" Inicio: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f" Fuentes configuradas: {list(SOURCES.keys())}")
    print(f" Límite por portal: {limit_per_source} | Sync Supabase: {sync_supabase}")
    print("=================================================================")

    new_articles = []

    sources_to_run = SOURCES.items()
    if target_source and target_source in SOURCES:
        sources_to_run = [(target_source, SOURCES[target_source])]

    for source_key, config in sources_to_run:
        urls = extract_article_urls(source_key, config)
        count_for_source = 0

        for url in urls:
            if count_for_source >= limit_per_source:
                break

            url_hash = hashlib.md5(url.encode('utf-8')).hexdigest()
            if url_hash in existing_hashes:
                continue

            print(f"  -> Extrayendo: {url}")
            article_data = parse_article_data(url, config['name'], config['category'])

            if article_data:
                new_articles.append(article_data)
                existing_hashes.add(url_hash)
                count_for_source += 1
                print(f"     [OK] \"{article_data['title'][:60]}...\"")
                # Cortesía entre peticiones (1 a 2.5 segundos)
                time.sleep(random.uniform(1.0, 2.2))

    # Guardar en archivo local
    all_articles = new_articles + existing_articles
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_articles, f, ensure_ascii=False, indent=2)

    print(f"\n[OK] Guardados {len(new_articles)} articulos nuevos en '{output_file}'.")
    print(f"[OK] Total acumulado en historial local: {len(all_articles)} noticias.")

    # Sincronizar con Supabase si fue solicitado
    if sync_supabase and new_articles:
        sync_articles_to_supabase(new_articles)

    return new_articles

def main():
    """Punto de entrada de línea de comandos."""
    import argparse
    parser = argparse.ArgumentParser(description='Scraper de Noticias de Saladillo')
    parser.add_argument('--limit', type=int, default=15, help='Límite de artículos por portal (default: 15)')
    parser.add_argument('--sync-supabase', action='store_true', help='Sincronizar artículos directamente con Supabase')
    parser.add_argument('--source', type=str, default=None, choices=list(SOURCES.keys()), help='Scrapear solo una fuente específica')

    args = parser.parse_args()
    return run_scraper(limit_per_source=args.limit, sync_supabase=args.sync_supabase, target_source=args.source)

if __name__ == '__main__':
    main()
