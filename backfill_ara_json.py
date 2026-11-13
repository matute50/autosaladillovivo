#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
backfill_ara_json.py — Poblador retroactivo de ara_json para artículos publicados existentes.
Uso: cd /home/matias/saladillo-vivo-pro && python backfill_ara_json.py [--limit N]
"""
import os
import sys
import json
import time
import argparse
import logging
import requests
from dotenv import load_dotenv

load_dotenv('/home/matias/saladillo-vivo-pro/.env')

sys.path.insert(0, '/home/matias/saladillo-vivo-pro')

from agents.ara_script_agent import AraScriptAgent
from agents.storage_agent import StorageAgent, load_env_credentials

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
logger = logging.getLogger('BackfillAraJson')


def fetch_pending_articles(storage, limit: int):
    """Fetch published articles without ara_json, newest first, using PostgREST."""
    headers = storage.get_headers(False)
    # Only use columns that actually exist in the table
    params = {
        'select': 'id,title,titulo_radial,text,status',
        'status': 'eq.published',
        'ara_json': 'is.null',
        'order': 'id.desc',
        'limit': str(limit),
    }
    resp = requests.get(storage.base_rest_url, headers=headers, params=params, timeout=25)
    if resp.status_code != 200:
        logger.error("HTTP %s al consultar pendientes: %s", resp.status_code, resp.text[:300])
        return []
    return resp.json()


def main(limit: int):
    logger.info("══════════════════════════════════════════════════════")
    logger.info("  BACKFILL ARA_JSON — Artículos publicados sin ara_json")
    logger.info("══════════════════════════════════════════════════════")

    agent = AraScriptAgent()
    storage = StorageAgent()

    pending = fetch_pending_articles(storage, limit)
    logger.info("Encontrados %d artículos sin ara_json (most recent first)", len(pending))

    if not pending:
        logger.info("Nada que procesar.")
        return

    processed = []
    errors = []

    for art in pending:
        art_id = art['id']
        title = art.get('title', '')[:70]
        radial = art.get('titulo_radial', '') or ''
        text = art.get('text', '') or ''

        # Derive tono from content (simple heuristic)
        tone_hint = (radial + ' ' + text).lower()
        if any(w in tone_hint for w in ['falleció', 'muerte', 'accidente', 'trágico', 'luto', 'fallecimiento', 'choque', 'incendio', 'asesinato', 'homicidio']):
            tono = 'SOLEMNE'
        elif any(w in tone_hint for w in ['campeón', 'ganó', 'victoria', 'triunfo', 'festejo', 'fiesta', 'cultural', 'espectáculo', 'concierto', 'arte', 'deporte']):
            tono = 'ALEGRE'
        else:
            tono = 'NEUTRAL'

        logger.info("⏳ ID=%s | tono=%s | '%s'", art_id, tono, title)

        # Build the article_data dict expected by generate_ara_json
        article_data = {
            'id': art_id,
            'titulo_radial': radial or title,
            'contenido_ia': text,
            'text': text,
            'tono': tono,
        }

        try:
            result = agent.generate_ara_json(article_data)
            if result is None:
                errors.append((art_id, 'generate_ara_json returned None'))
                continue

            # Save via storage agent
            ok = storage.update_ara_json(art_id, result)
            if ok is None:
                errors.append((art_id, 'update_ara_json returned None'))
                continue

            tenor = result.get('meta_ara', {}).get('tenor', '?')
            words = len(result.get('contenido', {}).get('guion_ara', '').split())
            provider = result.get('provider_used', '?')
            logger.info("✅ ID=%s | tenor=%s | guion=%d palabras | prov=%s | %s",
                        art_id, tenor, words, provider, title)
            processed.append({
                'id': art_id,
                'title': title,
                'tenor': tenor,
                'word_count': words,
                'provider': provider,
                'json': result,
            })

        except Exception as exc:
            logger.error("❌ ID=%s | ERROR: %s | %s", art_id, exc, title)
            errors.append((art_id, str(exc)))

        time.sleep(1.0)  # Rate limit between requests

    logger.info("")
    logger.info("══════════════════════════════════════════════════════")
    logger.info("RESUMEN BACKFILL:")
    logger.info("  Procesados: %d", len(processed))
    logger.info("  Errores:    %d", len(errors))
    logger.info("══════════════════════════════════════════════════════")
    for e in errors:
        logger.error("  ❌ ID=%s | %s", e[0], e[1])

    # Save summary to scratch
    summary_path = '/home/matias/.hermes/cache/scratch/backfill_summary.json'
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump({
            'processed': processed,
            'errors': [{'id': eid, 'err': err} for eid, err in errors],
        }, f, ensure_ascii=False, indent=2)
    logger.info("Resumen guardado en: %s", summary_path)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Backfill ara_json for published articles.')
    parser.add_argument('--limit', type=int, default=5, help='Max articles to process (default: 5)')
    args = parser.parse_args()
    main(args.limit)