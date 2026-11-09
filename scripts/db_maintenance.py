#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/db_maintenance.py — Mantenimiento de base de datos Saladillo Vivo.

Elimina artículos con más de N días de antigüedad (created_at o updatedAt).
También limpia audios y slides asociados del storage de Supabase.

Uso:
    python3 scripts/db_maintenance.py --dry-run --days 3   # Simulación
    python3 scripts/db_maintenance.py --confirm --days 3   # Ejecutar borrado
    python3 scripts/db_maintenance.py --audit               # Solo reporte
"""

import os
import sys
import json
import re
import time
import argparse
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))
from agents.storage_agent import StorageAgent

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("DBMaintenance")

SUPABASE_URL = "https://otwvfihzaznyjvjtkvvd.supabase.co"
AUDIO_BUCKET = "audios"
SLIDE_BUCKET = "slides"


def get_headers(key: str):
    return {
        'Authorization': f'Bearer {key}',
        'apikey': key,
        'Content-Type': 'application/json',
    }


def get_article_age_days(created_at: str, updated_at: str, now: datetime) -> float:
    """Retorna los días de antigüedad del artículo (mínimo entre created_at y updatedAt)."""
    try:
        dt_created = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
        dt_updated = datetime.fromisoformat(updated_at.replace('Z', '+00:00')) if updated_at else dt_created
        age_created = (now - dt_created).total_seconds() / 86400
        age_updated = (now - dt_updated).total_seconds() / 86400
        return min(age_created, age_updated)
    except Exception:
        return 0.0


def fetch_old_articles(url: str, key: str, cutoff_iso: str) -> list:
    """Busca artículos con created_at < cutoff O updatedAt < cutoff."""
    # url ya es base_rest_url (incluye /rest/v1/articles)
    resp = requests.get(
        url,
        params={
            'select': 'id,title,created_at,updatedAt,audio_url,url_slide,image_url',
            'or': f'(created_at.lt.{cutoff_iso},updatedAt.lt.{cutoff_iso})',
            'order': 'created_at.asc',
            'limit': 1000
        },
        headers=get_headers(key),
        timeout=30,
    )
    if resp.status_code != 200:
        logger.error(f"Error al cargar artículos: HTTP {resp.status_code} - {resp.text[:200]}")
        return []
    return resp.json()


def delete_from_storage(url: str, key: str, bucket: str, path: str) -> bool:
    """Elimina un archivo del bucket de Supabase Storage."""
    if not path:
        return True
    # Extraer el nombre del archivo de la URL
    match = re.search(rf'/public/{bucket}/(.+)$', path)
    if not match:
        return True  # No es URL de nuestro storage, ignorar
    file_path = match.group(1)
    try:
        resp = requests.delete(
            f"{url}/storage/v1/object/{bucket}/{file_path}",
            headers=get_headers(key),
            timeout=15,
        )
        if resp.status_code in (200, 204, 404):
            return True
        logger.warning(f"Storage delete failed for {file_path}: HTTP {resp.status_code}")
        return False
    except Exception as e:
        logger.warning(f"Storage delete exception: {e}")
        return False


def audit_mode(url: str, key: str, days: int):
    """Modo auditoría: muestra estadísticas sin borrar nada."""
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)
    cutoff_iso = cutoff.isoformat()

    articles = fetch_old_articles(url, key, cutoff_iso)
    total = len(articles)

    by_date = {}
    with_audio = 0
    with_slide = 0
    with_image = 0

    for a in articles:
        d = a.get('created_at', '')[:10]
        by_date[d] = by_date.get(d, 0) + 1
        if a.get('audio_url'):
            with_audio += 1
        if a.get('url_slide'):
            with_slide += 1
        if a.get('image_url'):
            with_image += 1

    print(f"\n{'='*60}")
    print(f"  AUDITORÍA DB — Artículos con >{days} días")
    print(f"{'='*60}")
    print(f"  Total artículos antiguos: {total}")
    print(f"    Con audio:              {with_audio}")
    print(f"    Con slide:              {with_slide}")
    print(f"    Con imagen:             {with_image}")
    print(f"\n  Por fecha de creación:")
    for d in sorted(by_date.keys()):
        print(f"    {d}:  {by_date[d]}")
    print(f"{'='*60}\n")
    return total


def dry_run_mode(url: str, key: str, days: int):
    """Modo simulación: muestra qué se borraría sin ejecutar."""
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)
    cutoff_iso = cutoff.isoformat()

    articles = fetch_old_articles(url, key, cutoff_iso)
    total = len(articles)

    if total == 0:
        print("\n✅ No hay artículos antiguos para eliminar.\n")
        return 0

    print(f"\n{'='*60}")
    print(f"  DRY RUN — Se eliminarían {total} artículos (> {days} días)")
    print(f"{'='*60}")

    audio_urls = []
    slide_urls = []

    for a in articles:
        aid = a.get('id')
        title = a.get('title', '')[:50]
        created = a.get('created_at', '')[:10]
        updated = a.get('updatedAt', '')[:10]
        audio = a.get('audio_url') or ''
        slide = a.get('url_slide') or ''
        img = a.get('image_url') or ''

        print(f"\n  ID {aid} [{created} → {updated}]")
        print(f"    Título: {title}")
        if audio:
            print(f"    Audio:  {audio[:80]}")
            audio_urls.append(audio)
        if slide:
            print(f"    Slide:  {slide[:80]}")
            slide_urls.append(slide)
        if img:
            print(f"    Imagen: {img[:80]}")

    print(f"\n{'='*60}")
    print(f"  Resumen:")
    print(f"    Artículos a borrar:  {total}")
    print(f"    Audios a eliminar:   {len(audio_urls)}")
    print(f"    Slides a eliminar:   {len(slide_urls)}")
    print(f"{'='*60}\n")
    print("⚠️  Este es un DRY RUN. No se eliminó nada.")
    print("   Para ejecutar: python3 scripts/db_maintenance.py --confirm --days 3\n")
    return total


def confirm_mode(url: str, key: str, days: int, cleanup_storage: bool = False):
    """Modo confirmado: elimina artículos y opcionalmente recursos de storage."""
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)
    cutoff_iso = cutoff.isoformat()

    articles = fetch_old_articles(url, key, cutoff_iso)
    total = len(articles)

    if total == 0:
        print("\n✅ No hay artículos antiguos para eliminar.\n")
        return {'deleted': 0, 'errors': 0}

    stats = {'deleted': 0, 'errors': 0, 'audio_deleted': 0, 'slide_deleted': 0, 'articles': []}

    print(f"\n{'='*60}")
    print(f"  CONFIRMADO — Eliminando {total} artículos (> {days} días)")
    print(f"{'='*60}")

    for i, a in enumerate(articles):
        aid = a.get('id')
        title = a.get('title', '')[:50]
        created = a.get('created_at', '')[:10]
        audio_url = a.get('audio_url') or ''
        slide_url = a.get('url_slide') or ''

        print(f"\n[{i+1}/{total}] ID {aid} [{created}] | {title}")

        # Eliminar audio del storage
        if cleanup_storage and audio_url:
            if delete_from_storage(url, key, AUDIO_BUCKET, audio_url):
                stats['audio_deleted'] += 1
                print(f"  🗑️  Audio eliminado")

        # Eliminar slide del storage
        if cleanup_storage and slide_url:
            if delete_from_storage(url, key, SLIDE_BUCKET, slide_url):
                stats['slide_deleted'] += 1
                print(f"  🗑️  Slide eliminado")

        # Eliminar registro de Supabase
        try:
            resp = requests.delete(
                url,
                params={'id': f'eq.{aid}'},
                headers=get_headers(key),
                timeout=15,
            )
            if resp.status_code in (200, 204):
                stats['deleted'] += 1
                stats['articles'].append(aid)
                print(f"  ✅ Artículo eliminado")
            else:
                stats['errors'] += 1
                print(f"  ❌ Error al eliminar: HTTP {resp.status_code}")
        except Exception as e:
            stats['errors'] += 1
            print(f"  ❌ Excepción: {e}")

        time.sleep(0.3)  # Rate limiting suave

    print(f"\n{'='*60}")
    print(f"  RESUMEN FINAL")
    print(f"{'='*60}")
    print(f"  Artículos eliminados:    {stats['deleted']}/{total}")
    if cleanup_storage:
        print(f"  Audios eliminados:       {stats['audio_deleted']}")
        print(f"  Slides eliminados:       {stats['slide_deleted']}")
    print(f"  Errores:                 {stats['errors']}")
    print(f"{'='*60}\n")

    if stats['errors'] == 0:
        print("✅ Mantenimiento completado exitosamente.")
    else:
        print(f"⚠️  Completado con {stats['errors']} error(es). Revisar logs.")

    return stats


def main():
    parser = argparse.ArgumentParser(description='Mantenimiento de BD Saladillo Vivo')
    parser.add_argument('--dry-run', action='store_true', help='Simular borrado sin ejecutar')
    parser.add_argument('--confirm', action='store_true', help='Ejecutar borrado real')
    parser.add_argument('--audit', action='store_true', help='Solo reporte estadístico')
    parser.add_argument('--days', type=int, default=3, help='Días de antigüedad (default: 3)')
    parser.add_argument('--cleanup-storage', action='store_true', help='También eliminar audios/slides del storage')
    args = parser.parse_args()

    sa = StorageAgent()
    url = sa.base_rest_url
    key = sa.key

    if not key:
        print("❌ Error: No se encontraron credenciales de Supabase en .env")
        sys.exit(1)

    if args.dry_run:
        dry_run_mode(url, key, args.days)
    elif args.confirm:
        confirm_mode(url, key, args.days, args.cleanup_storage)
    elif args.audit:
        audit_mode(url, key, args.days)
    else:
        parser.print_help()
        print("\n⚠️  Debes especificar --dry-run, --confirm o --audit")
        sys.exit(1)


if __name__ == '__main__':
    main()