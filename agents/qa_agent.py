# -*- coding: utf-8 -*-
"""
agents/qa_agent.py — Agente de Auditoría QA
===========================================
Audita los resultados en cada paso crítico del pipeline para garantizar calidad.
Repara automáticamente problemas o marca alertas, devolviendo resultados
para que el OrchestratorAgent tome decisiones.
"""

import os
import sys
import json
import re
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

logger = logging.getLogger("SaladilloVivoQA")


# ── Expresiones regulares para filtrado de imágenes ─────────────────────
_THUMBNAIL_RE = re.compile(r'-\d{2,3}x\d{2,3}\.(?:webp|jpg|jpeg|png)$', re.I)
_LOGO_RE = re.compile(
    r'\b(?:logo|header|banner|favicon|badge|widget|watermark|icon)\.(?:png|jpg|jpeg|svg|gif)$',
    re.I
)
_GRAVATAR_RE = re.compile(r'gravatar\.com|avatar', re.I)


def _is_valid_image_url(url: str) -> bool:
    """Verifica que una URL de imagen sea razonable (no thumbnail, no logo, no placeholder)."""
    if not url or not isinstance(url, str):
        return False
    s = url.lower()
    if any(skip in s for skip in ['placeholder', 'noimage', 'default-', 'avatar', 'gravatar']):
        return False
    if _LOGO_RE.search(s):
        return False
    if _THUMBNAIL_RE.search(s):
        return False
    if '80x80' in s or '392x250' in s or '150x150' in s or '200x200' in s:
        return False
    # Conservar solo extensiones comunes de imagen
    if not re.search(r'\.(?:webp|jpg|jpeg|png|gif|avif)(?:\?|$)', s):
        return False
    return True


def _title_is_radial_friendly(title: str) -> Tuple[bool, str]:
    """Verifica si el título es apto para locución radial (longitud, formato). Retorna (válido, sugerencia)."""
    if not title:
        return False, "Título vacío"
    t = title.strip()
    words = t.split()
    if len(words) > 12:
        return False, f"Título demasiado largo ({len(words)} palabras), sugerido ≤12 palabras"
    if len(words) < 3:
        return False, f"Título muy corto ({len(words)} palabras)"
    if '...' in t or '…' in t:
        return False, "Título contiene puntos suspensos, no apto para locución"
    if re.search(r'[\[\]【】]', t):
        return False, "Título contiene corchetes"
    return True, "OK"


def _body_is_radioworthy(body: str) -> Tuple[bool, str]:
    """Verifica que el cuerpo del texto sea apto para locución (longitud, estilo). Retorna (válido, sugerencia)."""
    if not body:
        return False, "Cuerpo vacío"
    words = re.findall(r'[\u4e00-\u9fff]+|[a-zA-Z]+', body)
    wc = len(words)
    if wc < 60:
        return False, f"Cuerpo demasiado corto ({wc} palabras), sugerido ≥80 palabras"
    if wc > 150:
        return False, f"Cuerpo demasiado largo ({wc} palabras), sugerido ≤110 palabras"
    # Verificar presencia de números (no ideales para locución)
    digits = re.findall(r'\d+', body)
    if len(digits) > 3:
        return False, f"Cuerpo contiene demasiados números ({len(digits)})"
    return True, f"OK ({wc} palabras)"


class QAConfig:
    """Configuración de la auditoría QA"""
    def __init__(self, supabase_url: str, supabase_key: str):
        self.supabase_url = supabase_url.rstrip('/')
        self.supabase_key = supabase_key

    @classmethod
    def from_env(cls):
        env_path = os.path.join(os.path.expanduser('~'), 'saladillo-vivo-pro', '.env')
        url = "https://otwvfihzaznyjvjtkvvd.supabase.co"
        key = ""
        if os.path.exists(env_path):
            with open(env_path, encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('#') or '=' not in line:
                        continue
                    k, v = line.split('=', 1)
                    k, v = k.strip(), v.strip().strip("'\"")
                    if 'SUPABASE_URL' in k or 'NEXT_PUBLIC_SUPABASE_URL' in k:
                        url = v
                    if k in ('SUPABASE_KEY', 'SUPABASE_SERVICE_ROLE_KEY'):
                        key = v
        return cls(url, key)


class QAResult:
    """Resultado de QA para un solo artículo"""
    def __init__(self, article_id=None, title='', image_url=''):
        self.article_id = article_id
        self.title = title
        self.image_url = image_url
        self.issues: List[Dict[str, str]] = []
        self.severity: str = 'ok'  # ok | warning | error

    def add_issue(self, field: str, severity: str, message: str):
        self.issues.append({'field': field, 'severity': severity, 'message': message})
        if severity == 'error':
            self.severity = 'error'
        elif severity == 'warning' and self.severity != 'error':
            self.severity = 'warning'

    def is_ok(self) -> bool:
        return self.severity == 'ok'

    def is_fixable(self) -> bool:
        return self.severity == 'warning'

    def to_dict(self):
        return {
            'article_id': self.article_id,
            'title': self.title,
            'image_url': self.image_url,
            'severity': self.severity,
            'issues': self.issues,
        }


class QAAuditor:
    """
    Agente de Auditoría QA: audita cada artículo en contenido, imágenes y formato.
    Soporta: scrape → rewrite → audio → publish.
    """

    def __init__(self, config: QAConfig):
        self.cfg = config
        self._recent_images: Dict[str, List[str]] = {}  # slug_prefix -> [image_urls]
        self._all_known_images: Dict[str, List[int]] = {}  # image_url -> [article_ids] (global cache)
        self._load_recent_articles(limit=200)

    @staticmethod
    def is_valid_image_url(url: str) -> bool:
        """Método estático: verifica si una URL de imagen es válida (usado por Orchestrator)."""
        return _is_valid_image_url(url)

    def _load_recent_articles(self, limit: int = 200):
        """Carga artículos recientes para comparar duplicados (global y por prefijo)."""
        if not HAS_REQUESTS:
            return
        try:
            r = requests.get(
                f"{self.cfg.supabase_url}/rest/v1/articles"
                f"?select=id,title,image_url,slug"
                f"&order=id.desc&limit={limit}",
                headers={
                    'apikey': self.cfg.supabase_key,
                    'Authorization': f'Bearer {self.cfg.supabase_key}',
                },
                timeout=15,
            )
            if r.status_code == 200:
                for art in r.json():
                    aid = art.get('id')
                    slug = art.get('slug', '') or ''
                    img = art.get('image_url') or ''
                    if img and _is_valid_image_url(img):
                        # Index by slug prefix (legacy)
                        if slug:
                            prefix = slug[:6]
                            self._recent_images.setdefault(prefix, []).append(img)
                        # Index globally by image URL
                        self._all_known_images.setdefault(img, []).append(aid)
        except Exception as e:
            logger.warning(f"[QA] Error al cargar artículos recientes: {e}")

    def audit_scraped_article(self, article: Dict) -> QAResult:
        """Audita el artículo original obtenido del scraper."""
        res = QAResult(
            article_id=article.get('id'),
            title=article.get('title', ''),
            image_url=article.get('image_url', ''),
        )
        # 1. Título
        title = article.get('title', '').strip()
        if not title:
            res.add_issue('title', 'error', 'Título vacío')
        elif len(title.split()) > 12:
            res.add_issue('title', 'warning', f'Título demasiado largo ({len(title.split())} palabras), sugerido ≤12 palabras')

        # 2. Cuerpo
        text = article.get('text', article.get('content', ''))
        if not text or len(text.strip()) < 50:
            res.add_issue('text', 'warning', 'Cuerpo demasiado corto o vacío')

        # NUEVO: Validar tiempo de lectura (máximo 45 segundos)
        if text:
            wc = len(re.findall(r'[\u4e00-\u9fff]+|[a-zA-Z]+', text))
            seconds = (wc / 140) * 60
            if seconds > 45:
                res.add_issue('reading_time', 'warning',
                    f'Tiempo de lectura estimado: {seconds:.1f}s (máximo 45s sugerido), '
                    f'cuerpo tiene {wc} palabras')
            else:
                res.add_issue('reading_time', 'ok',
                    f'Tiempo de lectura estimado: {seconds:.1f}s (dentro del límite de 45s)')

        # 3. Imagen (lo más crítico)
        img = article.get('image_url', '')
        if not img:
            res.add_issue('image_url', 'error', 'Falta URL de imagen')
        elif not _is_valid_image_url(img):
            res.add_issue('image_url', 'error',
                f'Imagen parece thumbnail o logo, URL: {img[:80]}')
        else:
            # Verificar duplicados: global (últimos 200) Y por prefijo de slug
            # Check global cache
            dup_in_global = False
            if img in self._all_known_images:
                existing_ids = self._all_known_images[img]
                current_id = article.get('id')
                if any(eid != current_id for eid in existing_ids):
                    dup_in_global = True
                    res.add_issue('image_url', 'warning',
                        f'Imagen duplicada: usada en {len(existing_ids)} artículos recientes')

            # Check slug-prefix cache (legacy)
            slug = article.get('slug', '')
            if slug and not dup_in_global:
                prefix = slug[:6]
                for prev_imgs in self._recent_images.get(prefix, []):
                    if prev_imgs == img:
                        res.add_issue('image_url', 'warning',
                            f'Esta imagen ya fue usada en un artículo reciente (slug={prefix}...)')
                        break

            # Actualizar caches
            if img not in self._all_known_images:
                self._all_known_images[img] = []
            self._all_known_images[img].append(article.get('id'))
            if slug:
                prefix = slug[:6]
                self._recent_images.setdefault(prefix, []).append(img)

        return res

    def audit_rewritten_article(self, article: Dict) -> QAResult:
        """Audita el artículo tras la reescritura con IA."""
        res = QAResult(
            article_id=article.get('id'),
            title=article.get('titulo_ia') or article.get('title', ''),
            image_url=article.get('image_url', ''),
        )

        # 1. Local/regional filter
        is_local = article.get('es_local_regional', True)
        if is_local is False or article.get('rejected'):
            res.add_issue('filter', 'error', 'Artículo clasificado como noticia no local/internacional, no debería publicarse')
            return res

        # 2. Calidad del título
        title = article.get('titulo_ia') or article.get('title', '')
        ok, tip = _title_is_radial_friendly(title)
        if not ok:
            res.add_issue('titulo_ia', 'warning', tip)

        # 3. Calidad del cuerpo
        body = article.get('contenido_ia') or article.get('text', '')
        ok, tip = _body_is_radioworthy(body)
        if not ok:
            res.add_issue('contenido_ia', 'warning', tip)

        # 4. Imagen (verificación nuevamente)
        img = article.get('image_url', '')
        if img and not _is_valid_image_url(img):
            res.add_issue('image_url', 'error', f'URL de imagen inválida: {img[:80]}')

        # 5. Meta descripción
        meta = article.get('meta_description', '')
        if meta and len(meta) > 155:
            res.add_issue('meta_description', 'warning',
                f'meta_description supera 155 caracteres ({len(meta)}), será recortada')
        elif not meta:
            res.add_issue('meta_description', 'warning', 'Falta meta_description')

        return res

    def audit_published_article(self, article: Dict) -> QAResult:
        """Audita artículos ya publicados (leídos desde la base de datos)."""
        # DB campos mapeados (clave interna → columna en la base)
        db_title = article.get('title') or article.get('titulo_ia', '')
        db_text = article.get('text') or article.get('contenido_ia', '')
        db_img = article.get('image_url') or article.get('og_image_url') or ''
        db_audio = article.get('audio_url') or ''
        db_slide = article.get('url_slide') or ''

        res = QAResult(
            article_id=article.get('id'),
            title=db_title,
            image_url=db_img,
        )

        required = {
            'title': ('title', 'Título'),
            'text': ('text', 'Cuerpo'),
            'audio_url': ('audio_url', 'Audio'),
            'url_slide': ('url_slide', 'Diapositiva'),
            'image_url': ('image_url', 'Imagen'),
        }
        for db_field, (internal_key, label) in required.items():
            val = article.get(db_field) or article.get(internal_key) or ''
            if not val or (isinstance(val, str) and not val.strip()):
                res.add_issue(db_field, 'error', f'{label} vacío')

        # Validez de la imagen
        img = article.get('image_url') or article.get('og_image_url') or ''
        if img and not _is_valid_image_url(img):
            res.add_issue('image_url', 'error', f'URL de imagen inválida: {img[:100]}')
        elif not img:
            res.add_issue('image_url', 'error', 'Falta URL de imagen')

        # Verificación de longitud del título
        if db_title and len(db_title.strip().split()) > 12:
            res.add_issue('title', 'warning', f'Título demasiado largo ({len(db_title.strip().split())} palabras), sugerido ≤12 palabras')

        # Verificación de longitud del cuerpo
        if db_text:
            words = re.findall(r'[\u4e00-\u9fff]+|[a-zA-Z]+', db_text)
            wc = len(words)
            if wc < 60:
                res.add_issue('text', 'warning', f'Cuerpo demasiado corto ({wc} palabras)')
            elif wc > 150:
                res.add_issue('text', 'warning', f'Cuerpo demasiado largo ({wc} palabras)')

        return res

    def batch_audit_published(self, articles: List[Dict]) -> List[QAResult]:
        """Audita artículos publicados en lote, retorna lista de resultados."""
        results = []
        for art in articles:
            res = self.audit_published_article(art)
            results.append(res)
            # Actualizar caché de imágenes recientes
            slug = art.get('slug', '')
            img = art.get('image_url', '')
            if slug and img and _is_valid_image_url(img):
                self._recent_images.setdefault(slug[:6], []).append(img)
        return results

    def generate_report(self, results: List[QAResult]) -> Dict:
        """Genera un reporte de auditoría resumido."""
        total = len(results)
        errors = sum(1 for r in results if r.severity == 'error')
        warnings = sum(1 for r in results if r.severity == 'warning')
        oks = sum(1 for r in results if r.is_ok())

        error_details = [
            r.to_dict() for r in results if r.severity == 'error'
        ]

        return {
            'total': total,
            'ok': oks,
            'warnings': warnings,
            'errors': errors,
            'error_rate_pct': round(errors / total * 100, 1) if total else 0,
            'error_articles': error_details,
            'timestamp': datetime.now().isoformat(),
            'status': 'passed' if errors == 0 else 'failed',
        }

    def auto_fix_image(self, article_id: int, suggested_url: str) -> bool:
        """Intenta reparar automáticamente la URL de imagen (directamente en Supabase)."""
        if not HAS_REQUESTS or not suggested_url or not _is_valid_image_url(suggested_url):
            return False
        try:
            r = requests.patch(
                f"{self.cfg.supabase_url}/rest/v1/articles?id=eq.{article_id}",
                json={'image_url': suggested_url, 'thumbnail_url': suggested_url,
                      'og_image_url': suggested_url},
                headers={
                    'apikey': self.cfg.supabase_key,
                    'Authorization': f'Bearer {self.cfg.supabase_key}',
                    'Prefer': 'return=representation',
                },
                timeout=15,
            )
            if r.status_code == 200:
                logger.info(f"[QA] Reparada automáticamente la imagen del artículo {article_id} con: {suggested_url[:60]}")
                return True
            logger.warning(f"[QA] Falló la reparación automática article={article_id} status={r.status_code}")
        except Exception as e:
            logger.error(f"[QA] Excepción en reparación automática: {e}")
        return False

    def auto_fix_published_article(self, article: Dict) -> bool:
        """Realiza reparaciones automáticas en artículos ya publicados (imagen y otros problemas corregibles). Retorna si se reparó con éxito."""
        res = self.audit_published_article(article)
        if res.severity == 'ok':
            return True  # No requiere reparación
        fixed = False
        for issue in res.issues:
            if issue['field'] == 'image_url' and issue['severity'] == 'error':
                # Intentar encontrar una mejor imagen desde campos relacionados
                for key in ('og_image_url', 'thumbnail_url', 'image_url'):
                    cand = article.get(key, '')
                    if cand and _is_valid_image_url(cand) and cand != article.get('image_url', ''):
                        if self.auto_fix_image(article['id'], cand):
                            fixed = True
                            break
        return fixed

    # ── Detección y reparación de imágenes duplicadas ─────────────────────
    def detect_and_fix_duplicate_images(self) -> Dict:
        """
        Escanea TODOS los artículos publicados, detecta imágenes repetidas
        y las repara automáticamente eligiendo alternativas cuando es posible.
        Retorna un reporte con: total_articulos, imagenes_unicas, duplicados, fijados, no_fijados.
        """
        if not HAS_REQUESTS or not self.cfg.supabase_key:
            return {'status': 'skipped', 'reason': 'Sin credenciales'}

        try:
            # Cargar TODOS los artículos publicados
            resp = requests.get(
                f"{self.cfg.supabase_url}/rest/v1/articles",
                params={
                    'select': 'id,title,image_url,og_image_url,thumbnail_url,images_urls,is_published',
                    'is_published': 'eq.true',
                    'order': 'id.desc',
                    'limit': 1000
                },
                headers={
                    'apikey': self.cfg.supabase_key,
                    'Authorization': f'Bearer {self.cfg.supabase_key}',
                },
                timeout=30,
            )
            if resp.status_code != 200:
                logger.warning(f"[QA] Error al cargar artículos para detectar duplicados: HTTP {resp.status_code}")
                return {'status': 'error', 'http': resp.status_code}

            articles = resp.json()
            logger.info(f"[QA-DupImg] Escaneando {len(articles)} artículos publicados...")

            # Construir mapa: imagen_url -> lista de artículos
            from collections import defaultdict
            img_to_articles = defaultdict(list)
            for art in articles:
                img = art.get('image_url', '').strip()
                if img and _is_valid_image_url(img):
                    img_to_articles[img].append(art)

            # Identificar duplicados (misma imagen en 2+ artículos)
            duplicates = {img: arts for img, arts in img_to_articles.items() if len(arts) > 1}
            total_dups = sum(len(arts) for arts in duplicates.values())
            logger.info(f"[QA-DupImg] Encontrados {len(duplicates)} grupos con imágenes duplicadas ({total_dups} artículos afectados)")

            fijados = 0
            no_fijados = []

            for dup_img, dup_articles in duplicates.items():
                # Para cada grupo de duplicados, mantener la imagen en el artículo más reciente
                # y buscar alternativa para los demás
                sorted_by_id = sorted(dup_articles, key=lambda a: a.get('id', 0), reverse=True)
                keeper = sorted_by_id[0]  # El más reciente mantiene la imagen original

                for art in sorted_by_id[1:]:
                    art_id = art.get('id')
                    # Buscar alternativa: og_image_url, thumbnail_url o images_urls diferente
                    alt_img = None
                    for alt_key in ('og_image_url', 'thumbnail_url'):
                        cand = art.get(alt_key, '').strip()
                        if cand and cand != dup_img and _is_valid_image_url(cand):
                            alt_img = cand
                            break

                    # También revisar images_urls si está presente
                    if not alt_img and art.get('images_urls'):
                        # Puede ser un array o string
                        images = art.get('images_urls')
                        if isinstance(images, str):
                            # Parse JSON string
                            import json
                            try:
                                images = json.loads(images)
                            except:
                                images = []
                        elif not isinstance(images, list):
                            images = []

                        for cand in images:
                            if cand != dup_img and _is_valid_image_url(cand):
                                alt_img = cand
                                break

                    if alt_img:
                        # Actualizar la imagen del artículo
                        patch_resp = requests.patch(
                            f"{self.cfg.supabase_url}/rest/v1/articles?id=eq.{art_id}",
                            json={
                                'image_url': alt_img,
                                'updatedAt': datetime.now().isoformat(),
                            },
                            headers={
                                'apikey': self.cfg.supabase_key,
                                'Authorization': f'Bearer {self.cfg.supabase_key}',
                                'Content-Type': 'application/json',
                                'Prefer': 'return=minimal',
                            },
                            timeout=20,
                        )
                        if patch_resp.status_code in (200, 204):
                            fijados += 1
                            logger.info(f"  [QA-DupImg] ID {art_id}: '{art.get('title','?')[:40]}...' → nueva imagen")
                        else:
                            no_fijados.append({
                                'id': art_id,
                                'title': art.get('title', ''),
                                'current_image': dup_img[:80],
                                'error': f"HTTP {patch_resp.status_code}"
                            })
                    else:
                        no_fijados.append({
                            'id': art_id,
                            'title': art.get('title', ''),
                            'current_image': dup_img[:80],
                            'error': 'Sin imagen alternativa disponible'
                        })
                        logger.warning(f"  [QA-DupImg] ID {art_id}: sin alternativa para '{dup_img[:60]}...'")

            report = {
                'total_articulos': len(articles),
                'imagenes_unicas': len(img_to_articles),
                'grupos_duplicados': len(duplicates),
                'articulos_afectados': total_dups,
                'fijados': fijados,
                'no_fijados': len(no_fijados),
                'no_fijados_detalle': no_fijados[:10],  # Primeros 10 para logging
                'timestamp': datetime.now().isoformat(),
            }
            logger.info(f"[QA-DupImg] Reporte: fijados={fijados}, no_fijados={len(no_fijados)}")
            return report

        except Exception as e:
            logger.error(f"[QA-DupImg] Excepción: {e}")
            return {'status': 'error', 'exception': str(e)}

    # ── Verificación de cron jobs ────────────────────────────────────────────
    def check_cron_health(self) -> Dict:
        """
        Verifica que el pipeline de Saladillo Vivo esté corriendo en los momentos indicados.
        Comprueba:
        1. Que el job 'saladillo-news-pipeline' existe y está activo
        2. Que la última ejecución fue exitosa (o se recuperó)
        3. Que no hay failures recientes sin recuperación
        4. Próximo horario de ejecución esperado

        Retorna un reporte con estado del cron.
        """
        import subprocess

        result = {
            'status': 'unknown',
            'job_found': False,
            'job_active': False,
            'last_run': None,
            'last_status': None,
            'last_failure': None,
            'next_run': None,
            'schedule': None,
            'issues': []
        }

        try:
            # Ejecutar hermes cron list y capturar salida
            proc = subprocess.run(
                ['hermes', 'cron', 'list'],
                capture_output=True,
                text=True,
                timeout=30
            )

            if proc.returncode != 0:
                result['status'] = 'error'
                result['issues'].append(f'Error ejecutando hermes cron list: {proc.stderr[:200]}')
                return result

            output = proc.stdout

            # Parsear la salida para encontrar el job del pipeline
            in_pipeline_section = False
            lines = output.split('\n')

            for i, line in enumerate(lines):
                if 'saladillo-news-pipeline' in line.lower():
                    in_pipeline_section = True
                    result['job_found'] = True
                    continue

                if in_pipeline_section:
                    # Extraer información clave
                    if 'Schedule:' in line:
                        schedule = line.split('Schedule:')[1].strip()
                        result['schedule'] = schedule
                    elif 'Next run:' in line:
                        next_run = line.split('Next run:')[1].strip()
                        result['next_run'] = next_run
                    elif 'Last run:' in line:
                        last_run_info = line.split('Last run:')[1].strip()
                        # Separar timestamp y status
                        parts = last_run_info.split()
                        if parts:
                            result['last_run'] = parts[0]
                        if 'ok' in last_run_info.lower():
                            result['last_status'] = 'ok'
                            result['job_active'] = True
                        elif 'error' in last_run_info.lower() or 'failed' in last_run_info.lower():
                            result['last_status'] = 'error'
                    elif 'Last failure' in line:
                        failure_info = line.split('Last failure')[1].strip()
                        result['last_failure'] = failure_info
                        if 'recovered' not in failure_info.lower():
                            result['issues'].append(f'Failure sin recuperar: {failure_info[:100]}')
                    elif line.strip().startswith('Name:') and 'saladillo' not in line.lower():
                        # Salimos de la sección del job
                        break

            # Verificar estado general
            if not result['job_found']:
                result['status'] = 'missing'
                result['issues'].append('Job saladillo-news-pipeline NO encontrado en cron')
            elif not result['job_active']:
                result['status'] = 'warning'
                result['issues'].append('Job existe pero última ejecución fue error')
            else:
                result['status'] = 'ok'

            # Verificar si hay jobs fallidos Otros
            if 'freellmapi-autoupdate' in output or 'cron-health-daily' in output:
                # Buscar estos jobs también para reportar
                for job_name in ['freellmapi-autoupdate', 'cron-health-daily']:
                    if job_name in output:
                        # Extraer estado del job
                        job_section = []
                        in_job = False
                        for line in lines:
                            if job_name in line.lower():
                                in_job = True
                            if in_job:
                                job_section.append(line)
                                if line.strip().startswith('Name:') and job_name not in line:
                                    break

                        section_text = '\n'.join(job_section)
                        if 'error' in section_text.lower() and 'recovered' not in section_text.lower():
                            result['issues'].append(f'Job {job_name} tiene error sin recuperar')

        except subprocess.TimeoutExpired:
            result['status'] = 'error'
            result['issues'].append('Timeout ejecutando hermes cron list')
        except Exception as e:
            result['status'] = 'error'
            result['issues'].append(f'Excepción: {str(e)[:200]}')

        result['timestamp'] = datetime.now().isoformat()
        return result
