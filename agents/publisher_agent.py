# -*- coding: utf-8 -*-
"""
agents/publisher_agent.py — Agente de Publicación y Distribución
==============================================================
Paso 5 del ciclo: Publica oficialmente la noticia en Supabase ('articles').

Acciones:
- Establece `is_published: True` para visibilidad inmediata en el portal Next.js 15.
- Asigna `published_at` y `publish_at` con la fecha/hora actual (ISO-8601).
- Establece `status: 'published'`.
- Garantiza que `miniatura_url` y `og_image_url` estén configuradas para los feeds,
  OpenGraph, Twitter Cards y la integración con Make.com para Instagram/Facebook.
"""

import os
import sys
import json
import re
from datetime import datetime

try:
    import requests
except ImportError:
    print("[PublisherAgent] Error: Se requiere 'requests'. Ejecute: pip install requests")
    sys.exit(1)

from .storage_agent import StorageAgent


class PublisherAgent:
    """
    Agente de Publicación para Saladillo Vivo.
    """
    def __init__(self, storage_agent=None):
        self.storage = storage_agent or StorageAgent()

    def publish_article(self, article_id, image_url=None, immediate=True):
        """
        Paso 5: Marca un artículo como publicado oficialmente en Supabase.
        """
        if not article_id:
            print("  [PublisherAgent] Error: No se proporcionó article_id.")
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

        current_payload = dict(payload)
        headers = self.storage.get_headers(return_representation=True)

        for _ in range(5):
            resp = requests.patch(
                self.storage.base_rest_url,
                params={'id': f'eq.{article_id}'},
                headers=headers,
                json=current_payload,
                timeout=25
            )
            if resp.status_code in (200, 204):
                print(f"  [PublisherAgent] [Paso 5: Publicado Oficialmente] ID: {article_id} | is_published={immediate}")
                try:
                    res_json = resp.json()
                    return res_json[0] if (isinstance(res_json, list) and len(res_json) > 0) else current_payload
                except Exception:
                    return current_payload
            elif resp.status_code == 400 and 'in the schema cache' in resp.text:
                m = re.search(r"'(\w+)' column", resp.text)
                if m:
                    missing_col = m.group(1)
                    if missing_col in current_payload:
                        del current_payload[missing_col]
                        continue
            print(f"  [PublisherAgent] Error publicando artículo ({resp.status_code}): {resp.text}")
            break

        return None

    def publish_batch(self, articles_to_publish, immediate=True):
        """Publica un lote de artículos ya procesados en base de datos."""
        published_count = 0
        failed_count = 0

        for art in articles_to_publish:
            art_id = art.get('id')
            img = art.get('image_url')
            res = self.publish_article(art_id, image_url=img, immediate=immediate)
            if res:
                published_count += 1
            else:
                failed_count += 1

        return {
            'published_count': published_count,
            'failed_count': failed_count,
            'total': len(articles_to_publish)
        }
