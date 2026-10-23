# -*- coding: utf-8 -*-
"""
agents/scraper_agent.py — Agente de Scraping de Noticias Locales
==============================================================
Extrae noticias hiperlocales de Saladillo desde:
- ABC Saladillo (https://www.abcsaladillo.com.ar)
- Ahora Saladillo (https://ahorasaladillo-diariodigital.com.ar)
- InfoSaladillo (https://infosaladillo.com.ar)

Cumple con:
- Uso de bibliotecas estándar y requests.
- Headers rotativos y delays de cortesía para evitar rate limiting o bloqueos.
- Extracción limpia de título, texto, copete, imagen destacada, fecha y URL de origen.
"""

import os
import sys
import re
import json
import time
import random
import hashlib
import unicodedata
from datetime import datetime
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    import urllib.request
    import urllib.error

# Fuentes hiperlocales oficiales de Saladillo
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

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
]


class LinkExtractor(HTMLParser):
    """Extrae enlaces válidos de artículos desde el HTML de la portada."""
    def __init__(self, base_url, domain, exclude_paths, min_url_length):
        super().__init__()
        self.base_url = base_url
        self.domain = domain
        self.exclude_paths = exclude_paths
        self.min_url_length = min_url_length
        self.links = []
        self._seen = set()

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            for name, value in attrs:
                if name == 'href' and value:
                    full_url = urljoin(self.base_url, value.strip())
                    parsed = urlparse(full_url)
                    if self.domain in parsed.netloc:
                        if len(full_url) >= self.min_url_length:
                            if not any(ex in full_url.lower() for ex in self.exclude_paths):
                                if full_url not in self._seen:
                                    self._seen.add(full_url)
                                    self.links.append(full_url)


class ArticleContentExtractor(HTMLParser):
    """Extrae título, texto de párrafos e imagen destacada del artículo."""
    def __init__(self, base_url):
        super().__init__()
        self.base_url = base_url
        self.in_title = False
        self.in_h1 = False
        self.in_paragraph = False
        self.in_ignored_tag = False
        self.ignored_tags = {'script', 'style', 'nav', 'header', 'footer', 'aside', 'form', 'noscript'}
        
        self.title_candidates = []
        self.paragraphs = []
        self.current_paragraph = []
        self.images = []
        self.meta_og_image = None
        self.meta_description = None

    def handle_starttag(self, tag, attrs):
        attr_dict = dict(attrs)
        tag_lower = tag.lower()

        if tag_lower in self.ignored_tags:
            self.in_ignored_tag = True
            return

        if tag_lower == 'meta':
            prop = attr_dict.get('property', '').lower()
            name = attr_dict.get('name', '').lower()
            content = attr_dict.get('content', '')
            if prop == 'og:image' and content:
                self.meta_og_image = urljoin(self.base_url, content)
            elif name == 'description' or prop == 'og:description':
                if content and not self.meta_description:
                    self.meta_description = content.strip()

        elif tag_lower == 'title':
            self.in_title = True
        elif tag_lower == 'h1':
            self.in_h1 = True
        elif tag_lower == 'p':
            self.in_paragraph = True
            self.current_paragraph = []
        elif tag_lower == 'img':
            src = attr_dict.get('src') or attr_dict.get('data-src') or attr_dict.get('data-lazy-src')
            if src:
                src_full = urljoin(self.base_url, src)
                if not any(x in src_full.lower() for x in ['logo', 'icon', 'banner', 'pixel', 'advert', 'publicidad']):
                    self.images.append(src_full)

    def handle_endtag(self, tag):
        tag_lower = tag.lower()
        if tag_lower in self.ignored_tags:
            self.in_ignored_tag = False
        elif tag_lower == 'title':
            self.in_title = False
        elif tag_lower == 'h1':
            self.in_h1 = False
        elif tag_lower == 'p':
            self.in_paragraph = False
            text = ' '.join(self.current_paragraph).strip()
            if len(text) > 25:
                self.paragraphs.append(text)
            self.current_paragraph = []

    def handle_data(self, data):
        if self.in_ignored_tag:
            return
        cleaned = re.sub(r'\s+', ' ', data)
        if not cleaned.strip():
            return

        if self.in_h1 or self.in_title:
            self.title_candidates.append(cleaned.strip())
        elif self.in_paragraph:
            self.current_paragraph.append(cleaned.strip())


class ScraperAgent:
    """
    Agente 1: Responsable exclusivo de extraer noticias frescas desde la web local.
    """
    def __init__(self, sources=None):
        self.sources = sources or SOURCES

    def _get_headers(self):
        return {
            'User-Agent': random.choice(USER_AGENTS),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'es-AR,es;q=0.9,es-ES;q=0.8,en;q=0.7',
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive'
        }

    def fetch_url(self, url, timeout=25):
        """Descarga HTML de una URL con manejo de reintentos."""
        headers = self._get_headers()
        if HAS_REQUESTS:
            try:
                resp = requests.get(url, headers=headers, timeout=timeout)
                if resp.status_code == 200:
                    resp.encoding = resp.apparent_encoding or 'utf-8'
                    return resp.text
            except Exception as e:
                print(f"  [ScraperAgent] Error descargando con requests ({url}): {e}")
        else:
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=timeout) as response:
                    charset = response.headers.get_content_charset() or 'utf-8'
                    return response.read().decode(charset, errors='replace')
            except Exception as e:
                print(f"  [ScraperAgent] Error descargando con urllib ({url}): {e}")
        return None

    def extract_links(self, source_key, config):
        """Descarga la portada y extrae URLs candidatas de artículos."""
        html = self.fetch_url(config['url'])
        if not html:
            return []
        parser = LinkExtractor(config['base_url'], config['domain'], config['exclude_paths'], config['min_url_length'])
        try:
            parser.feed(html)
        except Exception:
            pass
        return parser.links

    def parse_article(self, url, source_name, category='Local'):
        """Extrae el contenido completo y metadatos de un artículo."""
        html = self.fetch_url(url)
        if not html:
            return None

        parser = ArticleContentExtractor(url)
        try:
            parser.feed(html)
        except Exception:
            pass

        # Seleccionar título más representativo
        title = ""
        for cand in parser.title_candidates:
            if len(cand) > len(title) and not any(cand.endswith(x) for x in ['- ABC Saladillo', '| InfoSaladillo']):
                title = cand
        if not title and parser.title_candidates:
            title = parser.title_candidates[0]

        # Limpiar sufijos típicos de medios
        title = re.sub(r'\s*[-|]\s*(ABC Saladillo|Ahora Saladillo|InfoSaladillo|Diario Digital).*$', '', title, flags=re.I).strip()

        if not title or len(title) < 10:
            return None

        body_text = "\n\n".join(parser.paragraphs)
        if len(body_text) < 120:
            return None

        description = parser.meta_description or (parser.paragraphs[0] if parser.paragraphs else title)
        image_url = parser.meta_og_image or (parser.images[0] if parser.images else 'https://saladillovivo.vercel.app/default-og-image.png')

        url_hash = hashlib.md5(url.encode('utf-8')).hexdigest()

        return {
            'title': title,
            'original_title': title,
            'text': body_text,
            'original_text': body_text,
            'description': description[:300],
            'original_description': description[:300],
            'image_url': image_url,
            'source_url': url,
            'source_name': source_name,
            'categoria': category,
            'hash': url_hash,
            'scraped_at': datetime.now().isoformat(),
            'created_at': datetime.now().isoformat()
        }

    def scrape_all(self, limit_per_source=10, existing_hashes=None):
        """
        Ejecuta el ciclo de scraping sobre todas las fuentes configuradas.
        Deduplica contra un conjunto de hashes previamente conocidos.
        """
        existing = existing_hashes or set()
        scraped_articles = []

        print(f"[ScraperAgent] Iniciando extracción en {len(self.sources)} fuentes locales...")

        for source_key, config in self.sources.items():
            print(f"  -> Explorando portal: {config['name']} ({config['url']})")
            candidate_urls = self.extract_links(source_key, config)
            count = 0

            for url in candidate_urls:
                if count >= limit_per_source:
                    break

                url_hash = hashlib.md5(url.encode('utf-8')).hexdigest()
                if url_hash in existing:
                    continue

                article = self.parse_article(url, config['name'], config['category'])
                if article:
                    scraped_articles.append(article)
                    existing.add(url_hash)
                    count += 1
                    print(f"     [Extraído] \"{article['title'][:65]}...\"")
                    time.sleep(random.uniform(1.0, 2.0))

            print(f"  [ScraperAgent] {config['name']}: {count} artículos nuevos extraídos.")

        print(f"[ScraperAgent] Finalizado: {len(scraped_articles)} artículos totales en esta pasada.")
        return scraped_articles
