# -*- coding: utf-8 -*-
"""
agents/feed_seo_agent.py — Agente de Distribución Multicanal, RSS y SEO
======================================================================
Controla la visibilidad externa, posicionamiento y sindicación de contenidos de Saladillo Vivo:
- Verificación y consistencia del feed RSS 2.0 (/rss.xml).
- Auditoría de URLs de sitemap (/sitemap.xml).
- Monitoreo de metatags OpenGraph para Facebook, X y WhatsApp (/api/og).
- Verificación del feed de miniaturas rápidas (/feed/miniaturas).
"""

import logging
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Dict, Any, Optional

try:
    import requests
except ImportError:
    requests = None

from .storage_agent import load_env_credentials

logger = logging.getLogger("FeedSeoAgent")
logger.setLevel(logging.INFO)


class FeedSeoAgent:
    """
    Agente de SEO, sindicación RSS y distribución de Saladillo Vivo.
    """
    def __init__(self, base_site_url: str = "https://www.saladillovivo.com.ar"):
        self.base_site_url = base_site_url.rstrip('/')
        self.supabase_url, self.supabase_key = load_env_credentials()

    def audit_rss_feed(self) -> Dict[str, Any]:
        """Audita el feed RSS oficial de la plataforma."""
        rss_url = f"{self.base_site_url}/rss.xml"
        if not requests:
            return {"status": "error", "message": "requests no disponible"}

        try:
            resp = requests.get(rss_url, timeout=12)
            if resp.status_code == 200:
                root = ET.fromstring(resp.content)
                items = root.findall('.//item')
                return {
                    "status": "ok",
                    "rss_url": rss_url,
                    "status_code": resp.status_code,
                    "items_count": len(items),
                    "channel_title": root.findtext('.//channel/title', default=""),
                    "checked_at": datetime.now().isoformat()
                }
            else:
                return {
                    "status": "warning",
                    "rss_url": rss_url,
                    "status_code": resp.status_code,
                    "message": f"RSS respondió con HTTP {resp.status_code}"
                }
        except Exception as e:
            logger.warning(f"Error auditando RSS en {rss_url}: {e}")
            return {"status": "error", "rss_url": rss_url, "error": str(e)}

    def check_sitemap_health(self) -> Dict[str, Any]:
        """Verifica la respuesta del sitemap dinámico."""
        sitemap_url = f"{self.base_site_url}/sitemap.xml"
        if not requests:
            return {"status": "error", "message": "requests no disponible"}

        try:
            resp = requests.get(sitemap_url, timeout=12)
            return {
                "status": "ok" if resp.status_code == 200 else "warning",
                "sitemap_url": sitemap_url,
                "status_code": resp.status_code,
                "is_xml": "xml" in resp.headers.get("content-type", "").lower()
            }
        except Exception as e:
            return {"status": "error", "sitemap_url": sitemap_url, "error": str(e)}

    def test_opengraph_generator(self, test_title: str = "Noticia Saladillo Vivo") -> Dict[str, Any]:
        """Valida que la ruta de generación de imágenes OpenGraph esté activa."""
        og_url = f"{self.base_site_url}/api/og?title={requests.utils.quote(test_title)}" if requests else ""
        try:
            resp = requests.get(og_url, timeout=15)
            return {
                "status": "ok" if resp.status_code == 200 else "warning",
                "status_code": resp.status_code,
                "content_type": resp.headers.get("content-type"),
                "og_url": og_url
            }
        except Exception as e:
            return {"status": "error", "og_url": og_url, "error": str(e)}
