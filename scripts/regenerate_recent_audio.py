#!/usr/bin/env python3
"""
Regenera audio + slide de las últimas noticias publicadas con todos los fixes.

Motivos:
  1. Los audios viejos se armaron con DOS sintesis (cuerpo por un motor, promo
     por otro) -> se escuchaba una voz distinta en la frase promocional.
  2. Esos registros no tienen animation_duration -> el reproductor cerraba el
     slide antes de terminar la locución.
  3. La galería completa (images_urls) no se propagaba al slide -> se perdían
     fotos y el Ken Burns quedaba sin material visual.

Con el código actual (síntesis continua + splice de 1 s exacto + duración real
+ galería completa + animation_duration = audio + 1s de cola) cada nota queda
con una sola voz de principio a fin, lee el texto COMPLETO (sin re-condensar),
muestra todas sus fotos y el slide dura exactamente lo que dura su audio + 1s.
"""
import os
import sys
import time
import logging
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
from agents.audio_generator_agent import AudioGeneratorAgent
from agents.slide_generator_agent import SlideGeneratorAgent
from agents.storage_agent import StorageAgent

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

DAYS = int(os.environ.get("REGEN_DAYS", "3"))
LIMIT = int(os.environ.get("REGEN_LIMIT", "30"))


def main():
    storage = StorageAgent()
    audio = AudioGeneratorAgent()
    slide = SlideGeneratorAgent()

    cutoff = (datetime.now() - timedelta(days=DAYS)).isoformat()
    resp = requests.get(
        storage.base_rest_url,
        params={
            "select": "id,title,text,meta_description,image_url,images_urls,audio_url,url_slide,created_at",
            "is_published": "eq.true",
            "created_at": f"gte.{cutoff}",
            "order": "created_at.desc",
            "limit": LIMIT,
        },
        headers=storage.get_headers(False),
        timeout=25,
    )
    resp.raise_for_status()
    rows = resp.json() or []
    print(f"🔄 Artículos a regenerar: {len(rows)} (últimos {DAYS} días)")

    ok = 0
    for i, row in enumerate(rows, 1):
        art_id = row["id"]
        title = row.get("title") or ""
        # Lectura COMPLETA: el texto en DB ya pasó por el rewriter; NO se re-condensa.
        text = row.get("text") or ""
        if not text:
            print(f"  [{i}/{len(rows)}] id={art_id} sin texto, omito")
            continue

        print(f"  [{i}/{len(rows)}] id={art_id} «{title[:48]}…»")
        audio_url = audio.process_article_audio(
            article_id=art_id,
            title=title,
            text=text,
            description=row.get("meta_description") or "",
        )
        if not audio_url:
            print(f"    ❌ audio falló, dejo el registro intacto")
            continue

        dur = getattr(audio, "last_audio_duration", None)
        dur = round(dur, 1) if dur else None

        slide_url = None
        try:
            # Galería COMPLETA si existe; fallback a la imagen principal.
            images_urls = list(row.get("images_urls") or [])
            if not images_urls and row.get("image_url"):
                images_urls = [row["image_url"]]
            slide_url = slide.process_article_slide(
                article_id=art_id,
                title=title,
                text=text,
                audio_url=audio_url,
                image_urls=images_urls,
                audio_duration=dur,
            )
        except Exception as e:
            print(f"    ⚠️ slide falló: {type(e).__name__}: {e}")

        patch = {"audio_url": audio_url}
        if dur:
            # El slide dura lo que dura el audio + 1s de cola para el fade.
            patch["animation_duration"] = round(dur + 1, 1)
        if slide_url:
            patch["url_slide"] = slide_url

        up = requests.patch(
            storage.base_rest_url,
            params={"id": f"eq.{art_id}"},
            json=patch,
            headers=storage.get_headers(False),
            timeout=25,
        )
        if up.status_code in (200, 204):
            ok += 1
            print(f"    ✅ audio {dur}s | slide {'ok' if slide_url else 'OMITIDO'}")
        else:
            print(f"    ❌ PATCH DB {up.status_code}: {up.text[:200]}")
        time.sleep(1.2)

    print(f"🏁 Regeneración completa: {ok}/{len(rows)} artículos actualizados.")


if __name__ == "__main__":
    main()
