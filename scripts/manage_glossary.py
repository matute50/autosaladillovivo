#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/manage_glossary.py — Gestor CLI de Glosario de Texto y Audio para Saladillo Vivo
======================================================================================
Permite consultar, agregar, eliminar y probar términos en el glosario de redacción y audio.

Uso:
  # Listar todos los términos:
  python scripts/manage_glossary.py list

  # Agregar término de audio (fonética TTS):
  python scripts/manage_glossary.py add "CES" "C-E-S" --target audio

  # Agregar término de redacción (texto visible):
  python scripts/manage_glossary.py add "Salomon" "Salomón" --target redaccion

  # Agregar término global (aplica a redacción y audio):
  python scripts/manage_glossary.py add "saladillo vivo" "Saladillo Vivo" --target ambos

  # Eliminar un término:
  python scripts/manage_glossary.py remove "CES" --target audio

  # Probar cómo se transformaría un texto:
  python scripts/manage_glossary.py test "El intendente Salomon visito la CES y el HCD"
"""

import sys
import argparse
from pathlib import Path

# Agregar directorio raíz al PATH
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from utils.glossary_manager import GlossaryManager, apply_text_glossary, apply_audio_glossary


def cmd_list(args):
    mgr = GlossaryManager.get_instance()
    terms = mgr.list_terms(args.target)
    print("\n=======================================================")
    print(" GLOSARIO DE SALADILLO VIVO (REDACCIÓN Y AUDIO)")
    print("=======================================================")
    for category, mapping in terms.items():
        print(f"\n📂 Categoría: [{category.upper()}] ({len(mapping)} términos)")
        print("-" * 55)
        if not mapping:
            print("  (Sin términos registrados)")
        for term, repl in sorted(mapping.items()):
            print(f"  • \"{term}\"  ➜  \"{repl}\"")
    print("\n=======================================================\n")


def cmd_add(args):
    mgr = GlossaryManager.get_instance()
    ok = mgr.add_term(args.term, args.replacement, target=args.target)
    if ok:
        print(f"✅ Término agregado con éxito a [{args.target.upper()}]: \"{args.term}\" ➜ \"{args.replacement}\"")
    else:
        print(f"❌ Error al guardar el término en el glosario.")
        sys.exit(1)


def cmd_remove(args):
    mgr = GlossaryManager.get_instance()
    ok = mgr.remove_term(args.term, target=args.target)
    if ok:
        print(f"🗑️ Término \"{args.term}\" eliminado de [{args.target or 'todas las categorías'}].")
    else:
        print(f"⚠️ No se encontró el término \"{args.term}\" para eliminar.")


def cmd_test(args):
    text = args.text
    print("\n=======================================================")
    print(" PRUEBA DE TRANSFORMACIÓN DE GLOSARIO")
    print("=======================================================")
    print(f"\n📝 Texto Original:\n  \"{text}\"")
    print(f"\n📄 Salida Redacción (Texto Web y Slides):\n  \"{apply_text_glossary(text)}\"")
    print(f"\n🎙️ Salida Audio (Locución Fonética TTS):\n  \"{apply_audio_glossary(text)}\"")
    print("\n=======================================================\n")


def main():
    parser = argparse.ArgumentParser(description="Gestor de Glosario para Redacción y Audio de Saladillo Vivo")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # list
    p_list = subparsers.add_parser("list", help="Listar términos cargados en el glosario")
    p_list.add_argument("--target", choices=["redaccion", "audio", "ambos"], default=None, help="Filtrar por categoría")
    p_list.set_defaults(func=cmd_list)

    # add
    p_add = subparsers.add_parser("add", help="Agregar o actualizar un término")
    p_add.add_argument("term", help="Palabra o término a buscar")
    p_add.add_argument("replacement", help="Palabra o pronunciación corregida")
    p_add.add_argument("--target", choices=["redaccion", "audio", "ambos"], default="audio", help="Destino de la regla (default: audio)")
    p_add.set_defaults(func=cmd_add)

    # remove
    p_rem = subparsers.add_parser("remove", help="Eliminar un término")
    p_rem.add_argument("term", help="Término a eliminar")
    p_rem.add_argument("--target", choices=["redaccion", "audio", "ambos"], default=None, help="Categoría de la cual eliminar (default: todas)")
    p_rem.set_defaults(func=cmd_remove)

    # test
    p_test = subparsers.add_parser("test", help="Probar cómo el glosario transforma un texto de ejemplo")
    p_test.add_argument("text", help="Texto de prueba a transformar")
    p_test.set_defaults(func=cmd_test)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
