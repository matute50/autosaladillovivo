#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para corregir títulos radiales de artículos ya publicados.
Clampea titulo_radial a 12 palabras y actualiza en Supabase.
"""

import os
import sys
import re
import requests
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.storage_agent import StorageAgent
from agents.ai_rewriter_agent import AiRewriterAgent

def clamp_title_to_max_words(title: str, max_words: int = 12) -> str:
    """Limita un título al número máximo de palabras permitidas."""
    words = title.strip().split()
    if len(words) <= max_words:
        return title.strip()
    return " ".join(words[:max_words]).rstrip(' ,.:;')

def main():
    sa = StorageAgent()
    url = sa.base_rest_url
    key = sa.key

    # Fetch all published articles
    resp = requests.get(
        url,
        params={
            'select': 'id,title,titulo_radial,titulo_gancho_imagen,status,is_published',
            'is_published': 'eq.true',
            'order': 'id.desc',
            'limit': 500
        },
        headers={'Authorization': f'Bearer {key}', 'apikey': key},
        timeout=15
    )

    if resp.status_code != 200:
        print(f"Error al obtener artículos: {resp.status_code} - {resp.text}")
        return

    articles = resp.json()
    print(f"Total artículos publicados: {len(articles)}")

    fixed = 0
    for art in articles:
        art_id = art['id']
        current_radial = art.get('titulo_radial') or art.get('title') or ''
        words = len(current_radial.split()) if current_radial else 0

        if words > 12:
            new_radial = clamp_title_to_max_words(current_radial, max_words=12)
            new_words = len(new_radial.split())
            print(f"  ID {art_id}: {words} → {new_words} palabras")
            print(f"    Antes: {current_radial[:100]}")
            print(f"    Ahora: {new_radial[:100]}")

            # Update in Supabase
            patch_resp = requests.patch(
                url,
                params={'id': f'eq.{art_id}'},
                headers={
                    'Authorization': f'Bearer {key}',
                    'apikey': key,
                    'Content-Type': 'application/json',
                    'Prefer': 'return=minimal'
                },
                json={
                    'titulo_radial': new_radial,
                    'title': new_radial,  # Also update the main title field
                    'updatedAt': datetime.now().isoformat()
                },
                timeout=25
            )

            if patch_resp.status_code in (200, 204):
                fixed += 1
                print(f"    ✅ Actualizado")
            else:
                print(f"    ❌ Error: {patch_resp.status_code} - {patch_resp.text}")

    print(f"\n✅ Artículos corregidos: {fixed}")

if __name__ == '__main__':
    main()