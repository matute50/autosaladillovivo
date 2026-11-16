#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dry_run_v11_article900.py — Validación dry-run del pipeline v1.1 multi-clip.
REGLA DE SEGURIDAD: NO consume créditos (sin LLM), NO persiste en Supabase,
NO ejecuta Google Flow. Usa el generador determinista (fallback) y valida
la estructura ara_json v1.1 con bloques, generando prompts por clip.
"""
import json
import sys

sys.path.insert(0, '/home/matias/saladillo-vivo-pro')
sys.path.insert(0, '/home/matias/ara-video-factory/src')

from agents.ara_script_agent import AraScriptAgent
from prompt_assembler import (
    assemble_prompts_multi_clip,
    build_batch_json_for_multi_clip,
)

DRY_RUN = True  # Forzado: nunca persiste

# Datos del Artículo 900 (Feria de emprendedores en Saladillo)
ARTICLE_900 = {
    'id': 900,
    'titulo_radial': 'Feria de emprendedores en Saladillo',
    'title': 'Feria de emprendedores en Saladillo',
    'contenido_ia': (
        'Emprendedores locales mostraron productos regionales en la plaza '
        'principal de Saladillo este fin de semana. El evento reunió a decenas '
        'de stands con alimentos, artesanías y textiles producidos en la región. '
        'Los vecinos destacaron la calidad de la oferta y el ambiente familiar. '
        'La feria seguirá abierta el domingo de diez a diecinueve horas.'
    ),
    'text': (
        'Emprendedores locales mostraron productos regionales en la plaza '
        'principal de Saladillo este fin de semana. El evento reunió a decenas '
        'de stands con alimentos, artesanías y textiles producidos en la región.'
    ),
    'tono': 'ALEGRE',
}


def main():
    print("═" * 60)
    print("  VALIDACIÓN DRY-RUN v1.1 — Artículo 900")
    print("  Modo: determinista (fallback), sin LLM, sin persistencia")
    print("═" * 60)

    agent = AraScriptAgent()

    # 1) Generar ara_json v1.1 con bloques (determinista, sin créditos)
    print("\n[1/4] Generando ara_json v1.1 (fallback determinista)...")
    data = agent.apply_heuristic_fallback(
        ARTICLE_900['titulo_radial'],
        ARTICLE_900['contenido_ia'],
        ARTICLE_900['tono'],
    )

    # 2) Validar estructura v1.1
    print("[2/4] Validando estructura v1.1...")
    ok, errors = agent.validate_ara_json(data)
    version = data.get('version', '?')
    n_blocks = len(data.get('contenido', {}).get('bloques', []))
    print(f"      version={version} | bloques={n_blocks} | valid={ok}")

    bloques = data.get('contenido', {}).get('bloques', [])
    for b in bloques:
        wc = len(b['guion_ara'].split())
        marca = "OK" if 16 <= wc <= 22 else "FUERA DE RANGO"
        print(f"      Bloque {b['orden']}: {wc} palabras [{marca}]")
        print(f"        -> {b['guion_ara']}")

    if not ok:
        print(f"      ERRORES: {errors}")
        sys.exit(1)

    # 3) Generar prompts multi-clip desde bloques
    print("\n[3/4] Generando prompts multi-clip desde bloques...")
    prompts = assemble_prompts_multi_clip(data, n_clips=n_blocks)
    for p in prompts:
        wc = len(p['prompt_veo'].split())
        print(f"      Clip {p['clip_index']}: {wc} palabras | valid={p['valid']}")
        if p['errors']:
            print(f"        errors: {p['errors']}")
        if p['clip_index'] > 1:
            print(f"        (incluye directiva de continuidad visual v1.1)")

    # 4) Batch JSON encadenado
    print("\n[4/4] Batch JSON de flow (solo generado, NO ejecutado)...")
    batch = build_batch_json_for_multi_clip(
        data, n_clips=n_blocks, project_name=f"a{ARTICLE_900['id']}"
    )
    print(f"      project={batch['project']} | jobs={len(batch['jobs'])}")
    for j in batch['jobs']:
        start_note = f"start={j.get('start', 'ninguno')}"
        print(f"      - {j['name']}: {start_note}")

    # Resumen final
    continuidad = data.get('meta_ara', {}).get('continuidad_visual', '')
    ambiente = data.get('meta_ara', {}).get('ambiente_sonoro', '')
    print("\n═" * 60)
    print(f"  RESULTADO: VALIDADO | version={version} | {n_blocks} bloques | "
          f"prompts={'OK' if all(p['valid'] for p in prompts) else 'ERROR'}")
    print(f"  continuidad_visual: {continuidad[:70]}...")
    print(f"  ambiente_sonoro: {ambiente}")
    print("  Sin consumo de créditos. Sin persistencia. Sin Google Flow.")
    print("═" * 60)

    # Guardar resumen en scratch (sin tocar la BD)
    summary_path = '/home/matias/.hermes/cache/scratch/ara_v11_article900_dryrun.json'
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump({
            'article_id': 900,
            'version': version,
            'valid': ok,
            'n_blocks': n_blocks,
            'bloques': bloques,
            'prompts': prompts,
            'batch': batch,
            'dry_run': DRY_RUN,
        }, f, ensure_ascii=False, indent=2)
    print(f"\nResumen dry-run guardado en: {summary_path}")


if __name__ == '__main__':
    main()