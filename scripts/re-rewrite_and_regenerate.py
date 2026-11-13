#!/usr/bin/env python3
"""
Regenera las últimas 3 noticias aplicando el AiRewriterAgent para obtener 
la nueva redacción mejorada (puntuación respiratoria, siglas desglosadas, etc.)
y luego regenera audio y slides.
"""
import os
import sys
import time
import logging
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
from agents.ai_rewriter_agent import AiRewriterAgent
from agents.audio_generator_agent import AudioGeneratorAgent
from agents.slide_generator_agent import SlideGeneratorAgent
from agents.storage_agent import StorageAgent

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

LIMIT = 3

def main():
    storage = StorageAgent()
    rewriter = AiRewriterAgent()
    audio = AudioGeneratorAgent()
    slide = SlideGeneratorAgent()

    # 1. Obtener las últimas 3 noticias publicadas
    print(f"🔍 Buscando las últimas {LIMIT} noticias...")
    resp = requests.get(
        storage.base_rest_url,
        params={
            "select": "id,title,text,meta_description,image_url,images_urls,created_at",
            "is_published": "eq.true",
            "order": "created_at.desc",
            "limit": LIMIT,
        },
        headers=storage.get_headers(False),
        timeout=25,
    )
    resp.raise_for_status()
    rows = resp.json() or []
    print(f"🔄 Artículos a re-procesar: {len(rows)}")

    for i, row in enumerate(rows, 1):
        art_id = row["id"]
        original_title = row.get("title") or ""
        original_text = row.get("text") or ""
        
        print(f"\n--- [{i}/{len(rows)}] id={art_id} ---")
        print(f"📝 Re-redactando: \"{original_title[:50]}...\"")
        
        # 2. Re-redactar con las nuevas reglas
        article_data = {
            'title': original_title,
            'text': original_text,
            'image_url': row.get('image_url')
        }
        
        # Llamamos directamente a rewrite_article que usa el prompt actualizado
        rewritten = rewriter.rewrite_article(article_data)
        
        if not rewritten or rewritten.get('rejected'):
            print(f"    ⚠️ Re-redacción rechazada o fallida para id={art_id}")
            continue

        new_title = rewritten.get('titulo_ia')
        new_text = rewritten.get('contenido_ia')
        
        print(f"    ✅ Nueva redacción obtenida ({len(new_text)} caracteres)")
        
        # 3. Generar Audio con el nuevo texto
        print(f"    🔊 Generando audio...")
        audio_url = audio.process_article_audio(
            article_id=art_id,
            title=new_title,
            text=new_text,
            description=rewritten.get('meta_description', '')
        )
        
        if not audio_url:
            print(f"    ❌ audio falló")
            continue

        dur = getattr(audio, "last_audio_duration", None)
        dur = round(dur, 1) if dur else None
        print(f"    ✅ Audio generado: {dur}s")

        # 4. Generar Slide
        print(f"    🖼️ Generando slide...")
        slide_url = None
        try:
            images_urls = list(row.get("images_urls") or [])
            if not images_urls and row.get("image_url"):
                images_urls = [row["image_url"]]
                
            slide_url = slide.process_article_slide(
                article_id=art_id,
                title=new_title,
                text=new_text,
                audio_url=audio_url,
                image_urls=images_urls,
                audio_duration=dur,
            )
        except Exception as e:
            print(f"    ⚠️ slide falló: {e}")

        # 5. Actualizar Base de Datos
        print(f"    💾 Actualizando DB...")
        patch = {
            "titulo_radial": new_title,
            "text": new_text,
            "audio_url": audio_url,
            "url_slide": slide_url,
            "meta_description": rewritten.get('meta_description'),
            "featureStatus": rewritten.get('featureStatus'),
            "updatedAt": datetime.now().isoformat()
        }
        if dur:
            patch["animation_duration"] = round(dur + 1, 1)
        if rewritten.get('titulo_gancho_imagen'):
            patch["titulo_gancho_imagen"] = rewritten['titulo_gancho_imagen']

        up = requests.patch(
            storage.base_rest_url,
            params={"id": f"eq.{art_id}"},
            json=patch,
            headers=storage.get_headers(False),
            timeout=25,
        )
        
        if up.status_code in (200, 204):
            print(f"    ✨ ID {art_id} ACTUALIZADO CON ÉXITO")
        else:
            print(f"    ❌ Error PATCH DB {up.status_code}: {up.text[:200]}")
            
        time.sleep(1.5)

    print(f"\n🏁 Proceso finalizado.")

if __name__ == "__main__":
    main()
