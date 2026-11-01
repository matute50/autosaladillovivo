# -*- coding: utf-8 -*-
"""
agents/scraper_agent.py — Agente de Scraping de Noticias Locales y Regionales
============================================================================
Extrae noticias hiperlocales y regionales exclusivamente desde:
- ABC Saladillo (https://www.abcsaladillo.com.ar)
- Ahora Saladillo (https://ahorasaladillo-diariodigital.com.ar)
- InfoSaladillo (https://infosaladillo.com.ar)

Reglas editoriales estrictas:
1. Omitir noticias de orden nacional e internacional (Saladillo Vivo muestra únicamente noticias locales y regionales).
2. Omitir estrictamente la columna "Reflexiones" de InfoSaladillo.
3. Analizar y eliminar posibles noticias repetidas entre los tres medios (deduplicación multi-fuente).
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
from difflib import SequenceMatcher
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    import urllib.request
    import urllib.error

# Rutas comunes a excluir en todas las fuentes (secciones institucionales, tags, categorías genéricas o nacionales)
COMMON_EXCLUDE_PATHS = [
    '/seccion/', '/tag/', '/category/', '/author/', '/page/',
    '/feed/', '/contacto', '/quienes-somos', '/staff', '/politica-de-privacidad',
    '/farmacias-de-turno', '/cdn-cgi/', '#', 'facebook.com', 'instagram.com',
    'twitter.com', 'youtube.com', 'whatsapp.com', '/wp-content/',
    # Categorías nacionales e internacionales que deben omitirse
    '/nacionales/', '/internacionales/', '/el-pais/', '/el-mundo/', '/mundo/',
    '/pais/', '/argentina/', '/espectaculos/', '/farandula/', '/autos/', '/motores/',
    '/deportes-nacionales/'
]

# Fuentes hiperlocales oficiales de Saladillo
SOURCES = {
    'abcsaladillo': {
        'name': 'ABC Saladillo',
        'url': 'https://www.abcsaladillo.com.ar',
        'base_url': 'https://www.abcsaladillo.com.ar',
        'domain': 'abcsaladillo.com.ar',
        'category': 'Local',
        'exclude_paths': COMMON_EXCLUDE_PATHS,
        'min_url_length': 35
    },
    'ahorasaladillo': {
        'name': 'Ahora Saladillo',
        'url': 'https://ahorasaladillo-diariodigital.com.ar',
        'base_url': 'https://ahorasaladillo-diariodigital.com.ar',
        'domain': 'ahorasaladillo-diariodigital.com.ar',
        'category': 'Local',
        'exclude_paths': COMMON_EXCLUDE_PATHS,
        'min_url_length': 35
    },
    'infosaladillo': {
        'name': 'InfoSaladillo',
        'url': 'https://infosaladillo.com.ar',
        'base_url': 'https://infosaladillo.com.ar',
        'domain': 'infosaladillo.com.ar',
        'category': 'Local',
        # Excluir explícitamente la columna y categoría "Reflexiones"
        'exclude_paths': COMMON_EXCLUDE_PATHS + [
            '/seccion/reflexiones/', '/reflexiones/', '/reflexion/'
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

SPANISH_STOPWORDS = {
    'el', 'la', 'los', 'las', 'un', 'una', 'unos', 'unas', 'de', 'del', 'a', 'al', 'en', 'con',
    'por', 'para', 'y', 'o', 'u', 'que', 'se', 'su', 'sus', 'es', 'son', 'fue', 'fueron', 'era',
    'este', 'esta', 'estos', 'estas', 'lo', 'como', 'mas', 'pero', 'sin', 'sobre', 'tras', 'durante',
    'hacia', 'hasta', 'desde', 'entre', 'ante', 'bajo', 'segun', 'muy', 'ya', 'no', 'si'
}

# Palabras genéricas compartidas por toda noticia local que no deben usarse solas para detectar duplicados
GENERIC_NEWS_WORDS = {
    'saladillo', 'saladillense', 'local', 'ciudad', 'partido', 'provincia', 'buenos', 'aires',
    'argentina', 'diario', 'digital', 'noticias', 'info', 'com', 'portal', 'hoy', 'ayer', 'ahora',
    'dia', 'ano', 'mes', 'general'
}

# Términos que validan origen local o regional
LOCAL_REGIONAL_TERMS = {
    # Saladillo y parajes / localidades del partido:
    'saladillo', 'del carril', 'cazon', 'cazón', 'polvaredas', 'toledo', 'alvarez de toledo', 'álvarez de toledo',
    'saladillo norte', 'blaquier', 'barrancosa', 'la barrancosa',
    # Ciudades y partidos de la región (Séptima Sección e interior bonaerense circundante):
    'roque perez', 'roque pérez', '25 de mayo', 'veinticinco de mayo', 'general alvear', 'alvear',
    'las flores', 'lobos', 'tapalque', 'tapalqué', 'bolivar', 'bolívar', 'azul', 'olavarria', 'olavarría',
    'navarro', 'mercedes', 'monte', 'san miguel del monte', 'canuelas', 'cañuelas', 'chivilcoy', 'bragado',
    'alberti', 'suipacha', 'riestra', 'norberto de la riestra', 'pedernales', 'ernestina', 'beguerie',
    # Instituciones y referencias hiperlocales:
    'salomon', 'salomón', 'jose luis salomon', 'josé luis salomón', 'intendente', 'municipalidad', 'comuna',
    'ces', 'cooperativa electrica', 'cooperativa eléctrica', 'hospital posadas', 'curs',
    'concejo deliberante', 'hcd', 'sociedad rural', 'defensa civil', 'bomberos voluntarios', 'comisaria', 'comisaría',
    'cpr', 'patrulla rural', 'policia comunal', 'policía comunal', 'aeroclub',
    'ruta 205', 'ruta 51', 'ruta 41', 'ruta 3', 'cuenca del salado', 'rio salado', 'río salado',
    'huracan de saladillo', 'huracán de saladillo', 'la lola', 'jacobo urso', 'union apeadero', 'unión apeadero',
    'deportivo cazon', 'deportivo cazón', 'defensores de del carril', 'comercio'
}

# Descalificadores directos de orden nacional e internacional
NON_LOCAL_DISQUALIFIERS = [
    # Países y líderes internacionales:
    'bolsonaro', 'lula', 'brasil', 'trump', 'biden', 'kamala', 'ee.uu', 'ee uu', 'estados unidos',
    'putin', 'rusia', 'ucrania', 'zelenski', 'kiev', 'moscu', 'moscú',
    'netanyahu', 'israel', 'gaza', 'hamas', 'hamás', 'hezbollah', 'iran', 'irán', 'libano', 'líbano',
    'maduro', 'venezuela', 'caracas', 'china', 'xi jinping', 'taiwan', 'taiwán',
    'espana', 'españa', 'madrid', 'francia', 'macron', 'paris', 'parís', 'alemania', 'reino unido', 'londres',
    'union europea', 'unión europea', 'otan', 'onu', 'fmi',
    # Fútbol de primera división / nacional sin conexión local:
    'river plate', 'river define', 'boca juniors', 'superclasico', 'superclásico', 'demichelis', 'gallardo',
    'scaloni', 'seleccion argentina', 'selección argentina', 'champions league', 'copa libertadores',
    # Farándula nacional:
    'gran hermano', 'wanda nara', 'l-gante', 'marcelo tinelli', 'susana gimenez', 'susana giménez',
    # Reseñas comerciales automotrices / reviews de mercado nacional:
    'jeep avenger', 'suv mas accesible', 'suv más accesible', 'test drive'
]


def normalize_text_for_comparison(text):
    """Normaliza texto para comparación eliminando acentos, puntuación y mayúsculas."""
    if not text:
        return ""
    text = text.lower()
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('utf-8')
    text = re.sub(r'[^\w\s]', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()


def extract_distinctive_keywords(text):
    """Extrae palabras clave sustantivas del hecho eliminando stopwords y vocabulario genérico de noticias."""
    norm = normalize_text_for_comparison(text)
    words = [w for w in norm.split() if len(w) > 2 and w not in SPANISH_STOPWORDS and w not in GENERIC_NEWS_WORDS]
    return set(words)


def is_local_or_regional(title, text="", url="", section=None):
    """
    Determina si una noticia es local o regional de Saladillo y su zona de influencia.
    Omite cualquier noticia de orden nacional o internacional.
    """
    if section:
        s_norm = normalize_text_for_comparison(section)
        if any(bad in s_norm for bad in ['nacional', 'internacional', 'mundo', 'pais', 'espectaculo', 'farandula', 'auto']):
            return False, f"Sección nacional/internacional: {section}"

    combined = f"{title} {text[:400]} {url}".lower()
    combined_norm = normalize_text_for_comparison(combined)

    has_local = any(loc in combined_norm for loc in LOCAL_REGIONAL_TERMS)

    for disq in NON_LOCAL_DISQUALIFIERS:
        if disq in combined_norm:
            if not has_local:
                return False, f"Descalificado por contenido nacional/internacional ({disq})"

    title_norm = normalize_text_for_comparison(title)
    national_macro = ['inflacion', 'indec', 'dolar blue', 'gobierno nacional', 'casa rosada', 'senado de la nacion', 'congreso nacional']
    for nm in national_macro:
        if nm in title_norm and not has_local:
            return False, f"Descalificado por temática macroeconómica/nacional ({nm})"

    return True, "Local/Regional verificado"


def are_articles_duplicate(art1, art2):
    """
    Analiza si dos artículos de noticias tratan sobre el mismo hecho.
    Compara títulos con SequenceMatcher, Jaccard de términos distintivos y cuerpo de texto.
    """
    t1 = art1.get('title') or art1.get('original_title') or ''
    t2 = art2.get('title') or art2.get('original_title') or ''

    norm1 = normalize_text_for_comparison(t1)
    norm2 = normalize_text_for_comparison(t2)
    seq = SequenceMatcher(None, norm1, norm2).ratio()

    # Si los títulos son idénticos o 65%+ similares en cadena
    if seq >= 0.65:
        return True

    kw1 = extract_distinctive_keywords(t1)
    kw2 = extract_distinctive_keywords(t2)
    if not kw1 or not kw2:
        return False

    inter = kw1.intersection(kw2)
    union = kw1.union(kw2)
    jaccard = len(inter) / len(union) if union else 0.0

    # Si comparten al menos 3 palabras distintivas del hecho Y jaccard >= 0.35
    if len(inter) >= 3 and jaccard >= 0.35:
        return True

    # Si comparten al menos 4 palabras distintivas del hecho
    if len(inter) >= 4:
        return True

    # Gacetillas de prensa compartidas (primer párrafo)
    txt1 = art1.get('text') or art1.get('original_text') or ''
    txt2 = art2.get('text') or art2.get('original_text') or ''
    b1 = extract_distinctive_keywords(txt1[:400])
    b2 = extract_distinctive_keywords(txt2[:400])
    b_inter = b1.intersection(b2)
    b_union = b1.union(b2)
    b_j = len(b_inter) / len(b_union) if b_union else 0.0

    if len(inter) >= 2 and b_j >= 0.40:
        return True

    return False


def deduplicate_batch(articles):
    """
    Analiza y elimina noticias repetidas entre los tres medios.
    Conserva únicamente una noticia por cada hecho (la de texto más completo).
    """
    unique_articles = []
    discarded_count = 0

    for cand in articles:
        is_dup = False
        cand_title = cand.get('title', '')
        cand_source = cand.get('source_name', '')

        for kept in unique_articles:
            if are_articles_duplicate(cand, kept):
                is_dup = True
                discarded_count += 1
                kept_title = kept.get('title', '')
                kept_source = kept.get('source_name', '')
                print(f"  [Deduplicación] Noticia repetida detectada: '{cand_title[:55]}...' ({cand_source}) coincide con '{kept_title[:55]}...' ({kept_source}). Se descarta repetición.")

                # Si el nuevo candidato tiene más texto y mejor imagen, enriquecer el elemento conservado
                if len(cand.get('text', '')) > len(kept.get('text', '')) + 200:
                    kept['text'] = cand['text']
                    kept['original_text'] = cand['text']
                if 'default-og-image' in kept.get('image_url', '') and 'default-og-image' not in cand.get('image_url', ''):
                    kept['image_url'] = cand['image_url']
                break

        if not is_dup:
            unique_articles.append(cand)

    if discarded_count > 0:
        print(f"  [Deduplicación] {discarded_count} noticias duplicadas eliminadas entre medios.")
    return unique_articles


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
                            url_lower = full_url.lower()
                            # Omitir estrictamente Reflexiones
                            if 'reflexion' in url_lower:
                                continue
                            if not any(ex in url_lower for ex in self.exclude_paths):
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
        self.meta_section = None
        self.is_reflexiones = False

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
            elif prop in ('article:section', 'section') or name in ('article:section', 'section'):
                self.meta_section = content.strip()
                if 'reflexion' in content.lower():
                    self.is_reflexiones = True

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
    Aplica filtros de localidad/regionalidad, omisión de Reflexiones y deduplicación.
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
        """Extrae el contenido completo y metadatos de un artículo con validación editorial."""
        # 1. Filtro estricto: Omitir la columna "Reflexiones" de InfoSaladillo
        if 'reflexion' in url.lower():
            print(f"  [ScraperAgent] Omitiendo columna 'Reflexiones': {url}")
            return None

        html = self.fetch_url(url)
        if not html:
            return None

        # Detección exacta de sección Reflexiones en InfoSaladillo (meta tag o JSON-LD)
        if 'infosaladillo.com.ar' in url:
            is_refl_meta = bool(re.search(r'<meta property=["\']article:section["\'] content=["\']Reflexiones["\']', html, re.I))
            is_refl_jsonld = bool(re.search(r'["\']articleSection["\']\s*:\s*["\']Reflexiones["\']', html, re.I))
            if is_refl_meta or is_refl_jsonld:
                print(f"  [ScraperAgent] Omitiendo post de sección Reflexiones en InfoSaladillo: {url}")
                return None

        parser = ArticleContentExtractor(url)
        try:
            parser.feed(html)
        except Exception:
            pass

        if parser.is_reflexiones:
            print(f"  [ScraperAgent] Omitiendo artículo marcado como Reflexiones: {url}")
            return None

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

        # 2. Filtro estricto: Omitir noticias nacionales o internacionales (solo locales y regionales)
        is_loc, reason = is_local_or_regional(title, body_text, url, parser.meta_section)
        if not is_loc:
            print(f"  [ScraperAgent] Omitiendo noticia no local ({reason}): \"{title[:60]}...\"")
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
        Deduplica contra hashes previos y analiza repeticiones entre los 3 medios.
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
                    time.sleep(random.uniform(0.8, 1.5))

            print(f"  [ScraperAgent] {config['name']}: {count} artículos nuevos extraídos.")

        print(f"[ScraperAgent] Artículos pre-filtrados: {len(scraped_articles)}. Analizando noticias repetidas entre medios...")

        # 3. Analizar y eliminar noticias repetidas entre los tres medios
        final_articles = deduplicate_batch(scraped_articles)

        print(f"[ScraperAgent] Finalizado: {len(final_articles)} artículos únicos locales y regionales listos para publicar.")
        return final_articles
