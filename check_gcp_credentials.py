#!/usr/bin/env python3
"""
Verificador de credenciales Google Cloud TTS.
Comprueba cuántas cuentas están configuradas y si el rotador funciona.
"""
import os
import sys
import glob

CREDS_DIR = "/home/matias/saladillo-vivo-pro/gcp_credentials"
EXPECTED = 10

def check_credentials():
    """Verifica cuántos JSON de credenciales hay."""
    if not os.path.exists(CREDS_DIR):
        print(f"❌ Directorio no existe: {CREDS_DIR}")
        print("   Crear con: mkdir -p " + CREDS_DIR)
        return 0
    
    creds = glob.glob(os.path.join(CREDS_DIR, "gcp_*.json"))
    print(f"📁 Credenciales encontradas: {len(creds)}/{EXPECTED}")
    
    if len(creds) == EXPECTED:
        print("✅ Todas las cuentas configuradas")
        return len(creds)
    
    missing = EXPECTED - len(creds)
    print(f"⚠️ Faltan {missing} credenciales")
    
    # Mostrar cuáles faltan
    present = {os.path.basename(f) for f in creds}
    for i in range(1, EXPECTED + 1):
        name = f"gcp_{i:02d}.json"
        status = "✅" if name in present else "⬜"
        print(f"   {status} {name}")
    
    return len(creds)


def test_rotator():
    """Testea el rotador."""
    try:
        sys.path.insert(0, "/home/matias/saladillo-vivo-pro")
        from utils.gcp_tts_rotator import tts_rotator
        if tts_rotator.initialized:
            print("\n✅ Rotador inicializado")
            status = tts_rotator.get_quota_status()
            print(f"   Proyectos activos: {len([p for p in status['projects'] if p['used'] < p['limit']])}")
            print(f"   Cuota total: {status['total_used']:,}/{status['total_limit']:,}")
        else:
            print("\n⚠️ Rotador no inicializado (sin credenciales)")
            print("   Configura las credenciales GCP y reintenta.")
    except Exception as e:
        print(f"\n❌ Error testeando rotador: {e}")


if __name__ == "__main__":
    print("=" * 50)
    print(" VERIFICADOR GOOGLE CLOUD TTS - SALADILLO VIVO")
    print("=" * 50)
    n = check_credentials()
    if n > 0:
        test_rotator()
    print("\n" + "=" * 50)
    print(" PRÓXIMO PASO: Configurar las cuentas GCP")
    print("=" * 50)
    print("""
CÓMO CONFIGURAR CADA CUENTA (5 min c/u):
------------------------------------------
1. Ir a https://console.cloud.google.com y entrar con la cuenta Gmail
2. Crear proyecto: "saladillo-tts-XX" (XX = 01 al 10)
3. Habilitar API: Cloud Text-to-Speech API
4. IAM > Cuentas de servicio > Crear:
   - Nombre: saladillo-tts-XX-tts
   - Rol: Cloud Text-to-Speech User
   - Clave JSON: Descargar
5. Renombrar a gcp_XX.json y mover a gcp_credentials/

REPETIR PARA CADA UNA DE LAS 10 CUENTAS
""")