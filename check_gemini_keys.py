#!/usr/bin/env python3
"""
Verificador de keys Gemini TTS.
Comprueba cuántas keys están configuradas y si el rotador funciona.
"""
import os
import sys

ENV_PATH = "/home/matias/saladillo-vivo-pro/.env"
EXPECTED = 10


def check_keys():
    """Verifica cuántas keys Gemini hay en .env."""
    keys = []
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH) as f:
            for line in f:
                line = line.strip()
                if line.startswith("GEMINI_API_KEY_") and "=" in line and not line.startswith("#"):
                    var, _, val = line.partition("=")
                    val = val.strip().strip("'\"")
                    # Filtrar placeholders (no keys reales)
                    # Google usa formato AIza... (clásico) o AQ.Ab... (OAuth nuevo)
                    if val and "TU_KEY_GEMINI" not in val and "AQUI" not in val and (val.startswith("AIza") or val.startswith("AQ.Ab")):
                        keys.append(var)
    print(f"🔑 Keys Gemini configuradas (útiles): {len(keys)}/{EXPECTED}")
    for name in sorted(keys):
        print(f"   ✅ {name}")
    return len(keys)


def test_rotator():
    """Testea el rotador."""
    try:
        sys.path.insert(0, "/home/matias/saladillo-vivo-pro")
        from utils.gemini_tts_rotator import gemini_rotator
        if gemini_rotator.keys:
            print(f"\n✅ Rotador Gemini activo con {len(gemini_rotator.keys)} keys")
            status = gemini_rotator.get_status()
            print(f"   Día: {status['day']}")
            for k in status['keys']:
                print(f"   {k['key']}: {k['requests']}/{k['limit']} reqs ({k['pct']:.1f}%)")
        else:
            print("\n⚠️ Rotador inactivo (sin keys válidas)")
            print("   Agrega las keys a .env y reintenta.")
    except Exception as e:
        print(f"\n❌ Error testeando rotador: {e}")


if __name__ == "__main__":
    print("=" * 50)
    print(" VERIFICADOR GEMINI TTS - SALADILLO VIVO")
    print("=" * 50)
    n = check_keys()
    if n > 0:
        test_rotator()
    print("\n" + "=" * 50)
    print(" CÓMO OBTENER KEYS GEMINI (SIN TARJETA)")
    print("=" * 50)
    print("""
CÓMO OBTENER CADA KEY (2 min c/u):
------------------------------------
1. Ir a https://aistudio.google.com/apikey
2. Entrar con la cuenta Gmail
3. Click "Create API Key" → Google AI Studio
4. Copiar la key (empieza con AIza...)
5. Guardar en .env como GEMINI_API_KEY_XX

Formato en .env:
    GEMINI_API_KEY_01=AIza...
    GEMINI_API_KEY_02=AIza...
    ...
    GEMINI_API_KEY_10=AIza...

REPETIR PARA CADA UNA DE LAS 10 CUENTAS
""")