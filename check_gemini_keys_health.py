#!/usr/bin/env python3
"""
Chequeo de salud de las keys Gemini usadas por el rotador TTS.

Fuente de verdad: /home/matias/saladillo-vivo-pro/.env (igual que
utils/gemini_tts_rotator.py). Opcionalmente, con --all compara también
contra las variables de entorno (útil para detectar exports stale).

Uso:
    python3 check_gemini_keys_health.py           # solo .env
    python3 check_gemini_keys_health.py --all     # .env + entorno
    python3 check_gemini_keys_health.py --json    # salida machine-readable
"""
import argparse
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request

DOTENV = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
MAX_SLOT = 14
TIMEOUT = 15


def load_dotenv():
    keys, order = {}, []
    with open(DOTENV, encoding="utf-8") as fh:
        for line in fh:
            m = re.match(r"^(GEMINI_API_KEY_\d{1,2})=(\S+)", line.strip())
            if m:
                name, val = m.group(1), m.group(2)
                keys.setdefault(name, val)
                if name not in order:
                    order.append(name)
    return keys, order


def sig(key):
    return f"{key[:4]}…len{len(key)}/sha{hashlib.sha256(key.encode()).hexdigest()[:6]}"


def api_status(key):
    """(http_code, modelos_tts_visibles). Nunca imprime la key."""
    url = "https://generativelanguage.googleapis.com/v1beta/models?pageSize=1000&key=" + key
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT) as r:
            body = json.load(r)
    except urllib.error.HTTPError as e:
        return e.code, 0
    except Exception as e:  # noqa: BLE001
        return f"ERR:{type(e).__name__}", 0
    tts = [m["name"] for m in body.get("models", []) if "tts" in m.get("name", "")]
    return 200, len(tts)


def check(name, key):
    code, tts = api_status(key)
    if code == 200:
        salud = "VIVA"
    elif code == 429:
        salud = "CUOTA"  # viva, pero sin turnos hoy: no es una key muerta
    else:
        salud = "MUERTA"
    return {
        "name": name, "firma": sig(key), "http": code,
        "tts_models": tts, "salud": salud,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="incluir variables de entorno (detección de exports stale)")
    ap.add_argument("--json", action="store_true", help="salida JSON")
    args = ap.parse_args()

    if not os.path.exists(DOTENV):
        print(f"ERROR: no existe {DOTENV}", file=sys.stderr)
        return 2

    dotenv, _ = load_dotenv()
    results = [check(n, k) for n, k in sorted(dotenv.items())]

    env_results = []
    if args.all:
        for i in range(1, MAX_SLOT + 1):
            name = f"GEMINI_API_KEY_{i:02d}"
            val = os.environ.get(name)
            if not val:
                continue
            if val in dotenv.values():
                continue  # ya chequeada desde .env
            env_results.append(check(f"{name} (env)", val))

    if args.json:
        print(json.dumps({"dotenv": results, "entorno_stale": env_results}, indent=2))
    else:
        print(f"🩺 Salud de keys Gemini — fuente de verdad: {DOTENV}\n")
        for r in results:
            icon = {"VIVA": "🟢", "CUOTA": "🟡"}.get(r["salud"], "🔴")
            tts = f", {r['tts_models']} modelos TTS" if r["salud"] == "VIVA" else ""
            print(f"  {icon} {r['name']:<20} {r['salud']:<7} HTTP {r['http']} ({r['firma']}{tts})")
        vivas = sum(1 for r in results if r["salud"] == "VIVA")
        print(f"\n  Resumen: {vivas}/{len(results)} vivas en .env")
        if env_results:
            print("\n  ⚠️  Keys en variables de entorno que NO están en .env (posibles stale/huérfanas):")
            for r in env_results:
                icon = "🟢" if r["salud"] == "VIVA" else "🔴"
                warn = " ← ¡válida sin uso, revocarla en AI Studio!" if r["salud"] == "VIVA" else ""
                print(f"    {icon} {r['name']:<24} HTTP {r['http']} ({r['firma']}){warn}")
        elif args.all:
            print("\n  ✅ Sin keys huérfanas en el entorno.")

    return 0 if all(r["salud"] == "VIVA" for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
