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
    'union europea', 'unión europea', 'otan', 'onu', 'fmi', 'mexico', 'méxico', 'colombia', 'chile',
    'peru', 'perú', 'uruguay', 'paraguay', 'bolivia', 'cuba', 'iran', 'japon', 'japón', 'corea',
    # Deportes internacionales:
    'balon de oro', 'balón de oro', 'harry kane', 'messi', 'cristiano ronaldo', 'champions league',
    'premier league', 'f1', 'formula 1', 'kimi antonelli', 'nba', 'serie a',
    # Fútbol de primera división / nacional sin conexión local:
    'river plate', 'river define', 'boca juniors', 'superclasico', 'superclásico', 'demichelis', 'gallardo',
    'scaloni', 'seleccion argentina', 'selección argentina', 'copa libertadores', 'primera division',
    'primera división', 'liga profesional', 'afa',
    # Farándula nacional:
    'gran hermano', 'wanda nara', 'l-gante', 'marcelo tinelli', 'susana gimenez', 'susana giménez',
    'lali esposito', 'lali espósito', 'pedro rosemblat', 'casamiento', 'famoso', 'famosos', 'premios',
    'martin fierro', 'marti nfierro', 'farandula', 'farándula',
    # Reseñas comerciales automotrices / reviews de mercado nacional:
    'jeep avenger', 'suv mas accesible', 'suv más accesible', 'test drive', 'lanzamiento comercial',
    # Whatsapp y aplicaciones tecnológicas nacionales:
    'whatsapp', 'instagram', 'facebook', 'tiktok', 'aplicacion', 'aplicación',
    # Temas nacionales macroeconómicos:
    'inflacion', 'inflación', 'indec', 'dolar', 'dólar', 'gobierno nacional', 'casa rosada',
    'senado de la nacion', 'congreso nacional', 'deuda externa', 'presupuesto nacional',
    'reforma jubilatoria', 'reforma laboral', 'reforma fiscal'
]


def normalize_text_for_comparison(text):
    """Normaliza texto para comparación eliminando acentos, puntuación y mayúsculas."""
    if not text:
        return ""
    text = text.lower()
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('utf-8')
    text = re.sub(r'[^\w\s]', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()


# Medios de origen: sus menciones NUNCA deben propagarse al pipeline
# (skill saladillo-news-editorial-filter, sección 7.3)
_MEDIA_MENTION_RE = re.compile(
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
# "Ahora Saladillo" con A mayúscula es el medio; "ahora Saladillo" en una frase
# ("...y ahora Saladillo suma obras") es referencia temporal y NO se toca.
_MEDIA_MENTION_BARE_RE = re.compile(r'\s*[-–—|:–]*\s*Ahora Saladillo(?!\s+Diario)')


def strip_media_mentions(text):
    """Elimina menciones a los medios de origen de títulos y cuerpos de noticia."""
    if not text:
        return ""
    clean = _MEDIA_MENTION_RE.sub(' ', str(text))
    clean = _MEDIA_MENTION_BARE_RE.sub(' ', clean)
    clean = re.sub(r'\(\s*\)', ' ', clean)
    clean = re.sub(r'\[\s*\]', ' ', clean)
    clean = re.sub(r'\s{2,}', ' ', clean)
    clean = re.sub(r'[\s]*[-–—|:]+(?=[\.\,\!\?])', ' ', clean)
    clean = re.sub(r'\s*\.{2,}\s*$', '', clean)
    clean = re.sub(r'\s+([,.;:!?])', r'\1', clean)
    return clean.strip(' -–—|:.').strip()


def extract_distinctive_keywords(text):
    """Extrae palabras clave sustantivas del hecho eliminando stopwords y vocabulario genérico de noticias."""
    norm = normalize_text_for_comparison(text)
    words = [w for w in norm.split() if len(w) > 2 and w not in SPANISH_STOPWORDS and w not in GENERIC_NEWS_WORDS]
    return set(words)


def score_image_quality(image_url: str) -> int:
    """
    Calcula un puntaje de calidad para una URL de imagen (0-100).
    Mayor puntaje = mejor calidad esperada.

    Criterios:
    - Thumbnails/logos pequeños: penalización fuerte
    - URLs con parámetros de tamaño (w=, h=, wXXxYY): deduce resolución
    - Dominios de medios grandes: ligera bonificación
    - Extensiones y paths que indican original vs thumbnail
    """
    if not image_url:
        return 0

    url_lower = image_url.lower()
    score = 50  # Puntaje base

    # Penalizaciones por thumbnails y logos
    thumb_indicators = [
        '-80x80', '-150x150', '-300x250', '-392x250', '-200x200',
        'thumbnail', 'thumb', 'small', 'mini', 'sml', 'tiny',
        'logo', 'favicon', 'badge', 'icon', 'avatar',
        'placeholder', 'noimage', 'default-'
    ]
    for indicator in thumb_indicators:
        if indicator in url_lower:
            score -= 30
            break

    # Penalización por dimensiones en URL (suele ser imagen pequeña/redimensionada)
    dim_match = re.search(r'(?:w|width)?(\d{2,3})x(\d{2,3})', url_lower)
    if dim_match:
        w, h = int(dim_match.group(1)), int(dim_match.group(2))
        if w < 400 or h < 300:
            score -= 25
        elif w < 800 or h < 600:
            score -= 10

    # Resoluciones en nombre de archivo (ej: image-1920x1080.jpg)
    resolution_match = re.search(r'(\d{3,4})x(\d{3,4})', url_lower)
    if resolution_match:
        w, h = int(resolution_match.group(1)), int(resolution_match.group(2))
        if w >= 1920 and h >= 1080:
            score += 25
        elif w >= 1280 and h >= 720:
            score += 15
        elif w >= 800 and h >= 600:
            score += 10

    # Bonificación por extensiones de alta calidad
    high_quality_exts = ['.webp', '.png', '.jpg', '.jpeg']
    if any(url_lower.endswith(ext) for ext in high_quality_exts):
        score += 5

    # Bonificación por dominios de medios locales establecidos
    local_domains = ['abcsaladillo.com.ar', 'ahorasaladillo-diariodigital.com.ar', 'infosaladillo.com.ar']
    if any(domain in url_lower for domain in local_domains):
        score += 5

    # Penalización por shortcodes/CDN que suelen ser versiones comprimidas
    if any(cdns in url_lower for cdns in ['i0.wp.com', 'i1.wp.com', 'i2.wp.com', 'i3.wp.com']):
        score -= 10

    # Penalización por parámetros de compresión en URL
    compress_params = ['?resize=', '?fit=', '?crop=', '&quality=', 'quality=']
    for param in compress_params:
        if param in url_lower:
            score -= 5
            break

    return max(0, min(100, score))


def get_article_image_score(article: dict) -> int:
    """Calcula el score de imagen para un artículo scrapeado."""
    img_url = article.get('image_url', '') or article.get('og_image_url', '')
    return score_image_quality(img_url)


def is_local_or_regional(title, text="", url="", section=None):
    """
    Determina si una noticia es local o regional de Saladillo y su zona de influencia.
    Omite cualquier noticia de orden nacional o internacional.
    Regla estricta: Si el TÍTULO contiene términos nacionales/internacionales → descartar siempre,
    incluso si hay menciones locales. Solo se acepta si el hecho principal es claramente local.
    """
    if section:
        s_norm = normalize_text_for_comparison(section)
        if any(bad in s_norm for bad in ['nacional', 'internacional', 'mundo', 'pais', 'espectaculo', 'farandula', 'auto']):
            return False, f"Sección nacional/internacional: {section}"

    combined = f"{title} {text[:600]} {url}".lower()
    combined_norm = normalize_text_for_comparison(combined)

    title_norm = normalize_text_for_comparison(title)

    # PASO 1: Verificar descalificadores en el TÍTULO → descartar SIEMPRE
    # (el título es el indicador más fuerte del tema principal de la noticia)
    title_disqs = [disq for disq in NON_LOCAL_DISQUALIFIERS if disq in title_norm]
    if title_disqs:
        return False, f"Título con contenido nacional/internacional ({title_disqs[0]})"

    # PASO 2: Verificar macros nacionales en el título
    national_macro = ['inflacion', 'indec', 'dolar blue', 'gobierno nacional', 'casa rosada',
                      'senado de la nacion', 'congreso nacional', 'balon de oro', 'primera division',
                      'superclasico', 'seleccion argentina', 'premios', 'famoso', 'famosos']
    for nm in national_macro:
        if nm in title_norm:
            return False, f"Descalificado por temática macroeconómica/nacional en título ({nm})"

    # PASO 3: Verificar si hay anclaje local en cualquier parte
    has_local = any(loc in combined_norm for loc in LOCAL_REGIONAL_TERMS)
    if not has_local:
        return False, "Sin anclaje local/regional"

    # PASO 4: Si hay descalificadores en el CUERPO (pero no en el título),
    # verificar que la noticia trata predominantemente del hecho local
    body_disqs = [disq for disq in NON_LOCAL_DISQUALIFIERS if disq in combined_norm]
    if body_disqs:
        # Contar menciones locales vs. descalificadores en todo el texto
        local_count = sum(1 for loc in LOCAL_REGIONAL_TERMS if loc in combined_norm)
        disq_count = len(body_disqs)
        # Si hay más menciones de términos nacionales que locales → descartar
        if disq_count >= local_count:
            return False, f"Dominan términos nacionales/internacionales en cuerpo ({body_disqs[0]})"
        # Si hay términos locales dominantes, aceptar (el hecho principal es local)

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
    Conserva únicamente una noticia por cada hecho, priorizando:
    1. Texto más completo (>200 palabras más)
    2. Mejor calidad de imagen (score_image_quality)
    3. NUEVA REGLA: Si una noticia no tiene imagen, buscarla en otros medios.
       - Si se encuentra con imagen, preferirla.
       - Si solo se encuentra sin imagen, descartar la noticia.
    """
    from collections import defaultdict

    # Primer paso: agrupar artículos por título normalizado para encontrar duplicados
    normalized_to_articles = defaultdict(list)
    for art in articles:
        title_norm = normalize_text_for_comparison(art.get('title', ''))
        normalized_to_articles[title_norm].append(art)

    unique_articles = []
    discarded_count = 0

    for title_norm, group in normalized_to_articles.items():
        if len(group) == 1:
            # Único artículo con este título, conservarlo tal como está
            unique_articles.append(group[0])
            continue

        # Hay múltiples artículos con títulos similares - aplicar lógica de selección
        # Separar aquellos con imagen y sin imagen
        with_img = []
        without_img = []

        for art in group:
            img_score = get_article_image_score(art)
            if img_score > 0:
                with_img.append(art)
            else:
                without_img.append(art)

        # Aplicar prioridades:
        # 1. Si hay al menos un artículo con imagen, elegir el de mejor calidad de imagen
        if with_img:
            # Ordenar por score de imagen (mayor es mejor)
            with_img.sort(key=lambda a: get_article_image_score(a), reverse=True)
            chosen = with_img[0]
            discarded_in_group = len(with_img) - 1 + len(without_img)
            discarded_count += discarded_in_group

            # Enriquecer el elegido con mejor texto si hay otro con mejor texto pero sin imagen
            for art in with_img[1:] + without_img:
                cand_text_len = len(art.get('text', ''))
                chosen_text_len = len(chosen.get('text', ''))
                if cand_text_len > chosen_text_len + 200:
                    chosen['text'] = art['text']
                    chosen['original_text'] = art['text']
                # Enriquecer también imagen lógica y galería (merge con remoto)
                if 'default-og-image' in chosen.get('image_url', '') and 'default-og-image' not in art.get('image_url', ''):
                    chosen['image_url'] = art['image_url']
                if len(art.get('images_urls', [])) > len(chosen.get('images_urls', [])):
                    chosen['images_urls'] = art['images_urls']
            unique_articles.append(chosen)
            print(f"  [Deduplicación] Título duplicado: conservado artículo CON imagen ({chosen['source_name']}) y descartados {discarded_in_group} sin imagen")

        # 2. Si todos los artículos sobre este tema NO tienen imagen, descartar todos
        else:
            # Todos los artículos sobre este tema no tienen imagen
            # Descartarlos todos, pero enricher el último con mejor texto antes de tirar
            if without_img:
                # Ordenar por longitud de texto (el más completo)
                without_img.sort(key=lambda a: len(a.get('text', '')), reverse=True)
                # Aun así, descartarlos todos, pero imprimir mensaje
                discarded_count += len(without_img)
                print(f"  [Deduplicación] Título duplicado SIN imagen en ningún medio: descartados todos ({len(without_img)} artículos) - título: '{without_img[0]['title'][:50]}...'")
            # No agregar nada a unique_articles

    if discarded_count > 0:
        print(f"  [Deduplicación] {discarded_count} noticias eliminadas por falta de imagen o duplicados.")

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
                s = src_full.lower()
                # skip logos, icons, sidebars/widgets, thumbnails, gravatars, etc.
                if any(x in s for x in ['logo', 'icon', 'banner', 'pixel', 'advert', 'publicidad', 'gravatar', 'avatar']):
                    pass
                elif __import__('re').search(r'-\d{2,3}x\d{2,3}\.(?:webp|jpg|jpeg|png)$', s):
                    pass
                elif __import__('re').search(r'\b(logo|header|banner|favicon|badge|widget|avatar)\.(?:png|jpg|jpeg|svg)$', s):
                    pass
                elif __import__('re').search(r'ahorasaladillo\.png$', s):
                    pass
                else:
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


def normalize_image_url(raw_url, base_url=""):
    """
    Normaliza una URL de imagen a su máxima resolución original:
    - Resuelve URLs relativas con base_url.
    - Elimina sufijos de recorte automáticos de WordPress (ej: -80x80, -300x200, -768x... -> versión original).
    - Remueve parámetros restrictivos de resize/fit de Jetpack/Photon.
    """
    if not raw_url or not isinstance(raw_url, str):
        return None
    clean = raw_url.replace('&#038;', '&').replace('&amp;', '&').strip()
    if clean.startswith(('data:', 'blob:')):
        return None
    if base_url:
        clean = urljoin(base_url, clean)

    # 1. Quitar sufijo de dimensiones de WordPress: imagen-80x80.webp -> imagen.webp
    clean = re.sub(r'-\d+x\d+(\.(?:webp|jpg|jpeg|png))(?:\?.*)?$', r'\1', clean, flags=re.I)

    # 2. Limpiar query params de resize/fit forzados en Jetpack/Photon
    if '?' in clean:
        base_part, query_part = clean.split('?', 1)
        params = [p for p in query_part.split('&') if not p.lower().startswith(('resize=', 'fit=', 'w=', 'h=', 'strip='))]
        clean = base_part + ('?' + '&'.join(params) if params else '')

    return clean


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

    def extract_gallery_images(self, html, base_url, og_image=None):
        """
        Extrae todas las imágenes de la noticia garantizando MÁXIMA RESOLUCIÓN ORIGINAL:
        - Aísla estrictamente el cuerpo del artículo descartando sidemenus, breaking news, widgets y banners.
        - Prioriza la imagen destacada principal de WordPress (wp-post-image, fetchpriority).
        - Desescala y normaliza URLs de WordPress eliminando sufijos de recorte automáticos (-80x80, -300x200, etc.).
        - Deduplica conservando siempre la versión Full HD.
        """
        if not html:
            norm_og = normalize_image_url(og_image, base_url) if og_image else None
            return [norm_og] if norm_og else []

        images = []
        seen_keys = set()

        def add_candidate(img_candidate):
            norm_url = normalize_image_url(img_candidate, base_url)
            if not norm_url or not isinstance(norm_url, str):
                return
            lower = norm_url.lower()

            # Descartar logos, iconos, avatares, banners, pixels, widgets sociales y publicidad
            if any(k in lower for k in [
                'logo', 'icon', 'avatar', 'gravatar', 'banner', 'pixel', 'advert',
                'publicidad', 'sponsor', 'theme', 'emoji', 'button', 'mobile.png',
                'empty.png', 'transparente', '.svg', 'facebook', 'twitter', 'instagram',
                'whatsapp', 'share', 'jeg-empty', 'pinterest', 'linkedin'
            ]):
                return

            # Descartar miniaturas explícitas que no se hayan podido desescalar
            if re.search(r'-(?:80x80|100x100|150x150)\.(?:webp|jpg|jpeg|png)', lower):
                return

            # Validar que la ruta del recurso termine en formato de imagen admitido
            parsed_path = urlparse(norm_url).path.lower()
            if not any(parsed_path.endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.webp']):
                return

            # Clave de deduplicación basada en la URL base sin query
            clean_key = lower.split('?')[0]
            if clean_key not in seen_keys:
                seen_keys.add(clean_key)
                images.append(norm_url)

        # 1. Limpieza inicial: remover bloques ruidosos globales (header, footer, nav, aside, sidemenu)
        cleaned_html = re.sub(r'<(?:header|footer|aside|nav)[^>]*>.*?</(?:header|footer|aside|nav)>', '', html, flags=re.DOTALL | re.I)
        cleaned_html = re.sub(r'<div[^>]*class=[\x22\x27][^\x22\x27]*(?:sidemenu|recent-post|related-post|widget_shopping|td-related-row|jnews_related_post|related-posts|comments|post-comments)[^\x22\x27]*[\x22\x27].*?</div>', '', cleaned_html, flags=re.DOTALL | re.I)

        # 2. Aislar el contenedor del artículo buscando article o contenedores WordPress típicos
        scoped_html = None
        art_match = re.search(r'<article[^>]*>(.*?)</article>', cleaned_html, re.DOTALL | re.I)
        if art_match:
            scoped_html = art_match.group(1)
        else:
            container_match = re.search(r'(<div[^>]*class=[\x22\x27][^\x22\x27]*(?:blog-single|single-post|post-\d+|blog-content|entry-content|td-post-content|post-content)[^\x22\x27]*[\x22\x27].*?)(?:<footer|<div[^>]*class=[\x22\x27][^\x22\x27]*(?:related-post|recent-post|comments)|$)', cleaned_html, re.DOTALL | re.I)
            if container_match:
                scoped_html = container_match.group(1)
            else:
                scoped_html = cleaned_html

        # 3. Prioridad 1: Buscar la imagen destacada principal de WordPress (wp-post-image o fetchpriority)
        featured_image = None
        for img_tag in re.findall(r'<img\s+[^>]+>', scoped_html, re.I):
            attrs_lower = img_tag.lower()
            if any(k in attrs_lower for k in ['gravatar', 'avatar', '80x80', '150x150', 'logo', 'icon', 'advert']):
                continue
            if any(k in attrs_lower for k in ['wp-post-image', 'fetchpriority', 'attachment-post-thumbnail', 'attachment-large', 'attachment-full']):
                src_m = re.search(r'(?:data-large-file|data-orig-file|data-full-url|data-img-url|data-src|src)=[\x22\x27]([^\x22\x27]+)[\x22\x27]', img_tag, re.I)
                if src_m:
                    norm = normalize_image_url(src_m.group(1), base_url)
                    if norm:
                        featured_image = norm
                        break

        if featured_image:
            add_candidate(featured_image)
        elif og_image:
            add_candidate(normalize_image_url(og_image, base_url))

        # 4. Extraer enlaces directos a imágenes (típicos de galerías lightbox)
        for a_match in re.finditer(r'<a\s+[^>]*href=[\x22\x27](https?://[^\x22\x27]+\.(?:jpg|jpeg|png|webp)(?:\?[^\x22\x27]*)?)[\x22\x27]', scoped_html, re.I):
            add_candidate(a_match.group(1))

        # 5. Extraer imágenes dentro de etiquetas <img> del cuerpo
        for img_match in re.finditer(r'<img\s+([^>]+)>', scoped_html, re.I):
            attrs = img_match.group(1)

            # Descartar miniaturas explícitas
            if any(k in attrs.lower() for k in ['80x80', '150x150', 'avatar', 'gravatar', 'tnews_80x80']):
                continue

            # Si posee srcset, extraer la de mayor ancho (w)
            srcset_match = re.search(r'srcset=[\x22\x27]([^\x22\x27]+)[\x22\x27]', attrs, re.I)
            if srcset_match:
                parts = [p.strip().split() for p in srcset_match.group(1).split(',') if p.strip()]
                candidates = []
                for p in parts:
                    if len(p) >= 2 and p[1].endswith('w'):
                        try:
                            candidates.append((int(p[1][:-1]), p[0]))
                        except ValueError:
                            pass
                    elif len(p) >= 1:
                        candidates.append((0, p[0]))
                if candidates:
                    candidates.sort(reverse=True, key=lambda x: x[0])
                    add_candidate(candidates[0][1])
                    continue

            # Atributos de alta resolución y lazy loading
            for attr in ['data-orig-file', 'data-large-file', 'data-full-url', 'data-img-url', 'data-src', 'data-lazy-src', 'src']:
                attr_match = re.search(rf'{attr}=[\x22\x27]([^\x22\x27]+)[\x22\x27]', attrs, re.I)
                if attr_match and not attr_match.group(1).startswith('data:'):
                    add_candidate(attr_match.group(1))
                    break

        return images

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

        # Limpiar sufijos típicos de medios + cualquier otra mención al medio de origen
        title = re.sub(r'\s*[-|]\s*(ABC Saladillo|Ahora Saladillo|InfoSaladillo|Diario Digital).*$', '', title, flags=re.I).strip()
        title = strip_media_mentions(title)

        if not title or len(title) < 10:
            return None

        # El cuerpo tampoco debe propagar menciones a los medios de origen
        body_text = strip_media_mentions("\n\n".join(parser.paragraphs))
        if len(body_text) < 120:
            return None

        # 2. Filtro estricto: Omitir noticias nacionales o internacionales (solo locales y regionales)
        is_loc, reason = is_local_or_regional(title, body_text, url, parser.meta_section)
        if not is_loc:
            print(f"  [ScraperAgent] Omitiendo noticia no local ({reason}): \"{title[:60]}...\"")
            return None

        description = parser.meta_description or (parser.paragraphs[0] if parser.paragraphs else title)

        # Extracción completa de fotos de la noticia y galerías garantizando Full HD
        gallery_images = self.extract_gallery_images(html, url, parser.meta_og_image)
        raw_img = gallery_images[0] if gallery_images else (parser.meta_og_image or 'https://saladillovivo.vercel.app/default-og-image.png')
        image_url = normalize_image_url(raw_img, url) or 'https://saladillovivo.vercel.app/default-og-image.png'

        url_hash = hashlib.md5(url.encode('utf-8')).hexdigest()

        return {
            'title': title,
            'original_title': title,
            'text': body_text,
            'original_text': body_text,
            'description': description[:300],
            'original_description': description[:300],
            'image_url': image_url,
            'images_urls': gallery_images,
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
