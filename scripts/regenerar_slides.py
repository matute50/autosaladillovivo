#!/usr/bin/env python3
"""
regenerar_slides.py — Regenera slides de TODAS las noticias publicadas.

Comportamiento:
  - No toca audio ni texto (usa los valores existentes en DB).
  - Estima audio_duration desde el texto si falta en DB.
  - Pasa la galería COMPLETA (images_urls + image_url fallback) al slide.
  - La noticia más reciente siempre recibe featureStatus="featured".
  - Orden de publicación: de arriba hacia abajo en orden de aparición
    (chronological ASC: oldest first in the list, newest last/featured).
  - Usa rate limiting suave (2s entre artículos) para no saturar APIs.

Uso:
  python3 scripts/regenerar_slides.py [--limit N] [--dry-run]
"""
import os
import sys
import time
import logging
import argparse
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
from agents.slide_generator_agent import SlideGeneratorAgent
from agents.storage_agent import StorageAgent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)
log = logging.getLogger("regen_slides")


def get_headers(storage: StorageAgent, service_role: bool = False):
    return storage.get_headers(service_role)


def fetch_articles(storage: StorageAgent, limit: int) -> list:
    """Fetch published articles ordered by created_at DESC (newest first)."""
    r = requests.get(
        storage.base_rest_url,
        params={
            "select": "id,title,text,audio_url,images_urls,image_url,url_slide,"
                       "animation_duration,is_published,created_at,featureStatus",
            "is_published": "eq.true",
            "order": "created_at.desc",
            "limit": str(limit),
        },
        headers=storage.get_headers(False),
        timeout=30,
    )
    r.raise_for_status()
    rows = r.json() or []
    log.info(f"✅ {len(rows)} artículos publicados obtenidos")
    return rows


def build_image_list(row: dict) -> list:
    """Build complete image list from DB fields, avoiding duplicates."""
    seen = set()
    result = []

    # Primary image
    primary = row.get("image_url") or ""
    if primary and primary not in seen:
        seen.add(primary)
        result.append(primary)

    # Gallery
    raw_gallery = row.get("images_urls")
    if isinstance(raw_gallery, str):
        try:
            raw_gallery = __import__("json").loads(raw_gallery)
        except Exception:
            raw_gallery = []
    if isinstance(raw_gallery, list):
        for u in raw_gallery:
            if u and isinstance(u, str) and u not in seen:
                seen.add(u)
                result.append(u)

    return result


def estimate_duration(text: str, existing: float | None) -> float | None:
    """Return audio duration: prefer DB value, fall back to estimation."""
    if existing and existing > 0:
        return round(existing, 1)
    if not text:
        return None
    # Simple word-rate estimate (2.08 wps rioplatense TTS)
    words = len(text.split())
    est = max(4.0, words / 2.08 + 3.0)
    return round(est, 1)


def process_single(
    storage: StorageAgent,
    slide: SlideGeneratorAgent,
    row: dict,
    dry_run: bool,
) -> tuple[bool, str | None]:
    """Regenerate slide for one article. Returns (success, new_url)."""
    art_id = row["id"]
    title = row.get("title") or f"Noticia #{art_id}"
    text = row.get("text") or ""
    audio_url = row.get("audio_url") or ""
    imgs = build_image_list(row)
    dur = estimate_duration(text, row.get("animation_duration"))

    log.info(f"[{art_id}] Generando slide ({len(imgs)} imgs, audio={'✓' if audio_url else '✗'}, dur={dur}s)")

    if dry_run:
        log.info(f"[{art_id}] DRY-RUN: skip processing")
        return True, row.get("url_slide")

    try:
        new_url = slide.process_article_slide(
            article_id=art_id,
            title=title,
            text=text,
            audio_url=audio_url,
            image_urls=imgs,
            audio_duration=dur,
        )
        if new_url:
            log.info(f"[{art_id}] ✅ Slide regenerated: {new_url[:70]}...")
            return True, new_url
        else:
            log.error(f"[{art_id}] ❌ Slide generation returned None")
            return False, None
    except Exception as e:
        log.error(f"[{art_id}] ❌ Exception: {type(e).__name__}: {e}")
        return False, None


def patch_article(storage: StorageAgent, art_id: int, patch: dict) -> bool:
    """PATCH a single article in Supabase."""
    r = requests.patch(
        storage.base_rest_url,
        params={"id": f"eq.{art_id}"},
        json=patch,
        headers=storage.get_headers(False),
        timeout=25,
    )
    if r.status_code in (200, 204):
        return True
    log.warning(f"[{art_id}] PATCH failed: HTTP {r.status_code} → {r.text[:150]}")
    return False


def main():
    parser = argparse.ArgumentParser(description="Regenerar slides de noticias publicadas")
    parser.add_argument("--limit", type=int, default=50, help="Max artículos a procesar (default 50)")
    parser.add_argument("--dry-run", action="store_true", help="Simular sin generar ni parchear")
    args = parser.parse_args()

    storage = StorageAgent()
    slide = SlideGeneratorAgent()

    articles = fetch_articles(storage, args.limit)
    if not articles:
        log.warning("No hay artículos publicados. Nada que hacer.")
        return

    # Sort ASC (oldest first) for chronological publication order
    articles.sort(key=lambda a: a.get("created_at") or "")
    log.info(f"📋 {len(articles)} artículos ordenados cronológicamente (más antiguo → más nuevo)")

    # Track results
    updated = 0
    failed = 0
    skipped = 0

    for i, row in enumerate(articles, 1):
        art_id = row["id"]
        isNewest = (i == len(articles))  # last in ASC = most recent

        success, new_url = process_single(storage, slide, row, args.dry_run)

        if not success:
            failed += 1
            time.sleep(2)
            continue

        if not new_url:
            skipped += 1
            time.sleep(2)
            continue

        # Build patch payload
        patch: dict = {"url_slide": new_url, "updatedAt": datetime.now().isoformat()}
        if isNewest:
            patch["featureStatus"] = "featured"
            log.info(f"[{art_id}] ⭐ Marcado como DESTACADA (última adquirida)")

        if not args.dry_run:
            ok = patch_article(storage, art_id, patch)
            if ok:
                updated += 1
                log.info(f"[{art_id}] 💾 PATCH applied")
            else:
                failed += 1
        else:
            updated += 1
            log.info(f"[{art_id}] DRY-RUN PATCH (featureStatus={'featured' if isNewest else 'none'})")

        # Rate limit: 2s between articles to respect API quotas
        time.sleep(2)

    log.info("=" * 50)
    log.info(f"🏁 Regeneración completada:")
    log.info(f"   Actualizados: {updated}")
    log.info(f"   Fallidos:     {failed}")
    log.info(f"   Omitidos:     {skipped}")
    log.info(f"   Dry-run:      {args.dry_run}")
    if not args.dry_run:
        latest = articles[-1]
        log.info(f"   Destacada:    #{latest['id']} «{latest['title'][:50]}…»")
    log.info("=" * 50)


if __name__ == "__main__":
    main()
