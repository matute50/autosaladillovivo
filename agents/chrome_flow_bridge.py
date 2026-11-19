# -*- coding: utf-8 -*-
"""
agents/chrome_flow_bridge.py — Conector CDP Autónomo para Chrome en Ubuntu
==========================================================================
Conecta Hermes Agent con la sesión activa de Google Chrome a través del
puerto de depuración remoto (CDP: Chrome DevTools Protocol en el puerto 9222).

Funcionalidades:
- Comprueba si Chrome está activo con --remote-debugging-port=9222.
- Localiza la pestaña de Google Flow / Flow Automation.
- Emula eventos de interfaz genuinos (isTrusted: true) para evitar bloqueos de React.
- Monitorea la finalización de las descargas en la carpeta local de clips crudos.
"""

import os
import sys
import time
import json
import logging
from typing import Optional, Dict, Any, List

try:
    import requests
except ImportError:
    print("[ChromeFlowBridge] Error: Se requiere 'requests'.")
    sys.exit(1)

logger = logging.getLogger("ChromeFlowBridge")

DEFAULT_CDP_PORT = 9222
CDP_URL = f"http://127.0.0.1:{DEFAULT_CDP_PORT}"


class ChromeFlowBridge:
    """
    Controlador de Chrome y Flow Automation vía Chrome DevTools Protocol (CDP).
    """

    def __init__(self, port: int = DEFAULT_CDP_PORT):
        self.port = port
        self.base_url = f"http://127.0.0.1:{self.port}"

    def is_chrome_running(self) -> bool:
        """Verifica si Chrome responde en el puerto de depuración remota."""
        try:
            res = requests.get(f"{self.base_url}/json/version", timeout=2.0)
            if res.status_code == 200:
                data = res.json()
                logger.info(f"✅ Conectado a Chrome CDP: {data.get('Browser')}")
                return True
        except Exception:
            pass
        return False

    def list_targets(self) -> List[Dict[str, Any]]:
        """Devuelve la lista de pestañas y páginas activas en Chrome."""
        try:
            res = requests.get(f"{self.base_url}/json", timeout=3.0)
            if res.status_code == 200:
                return res.json()
        except Exception as e:
            logger.error(f"Error listando pestañas CDP: {e}")
        return []

    def find_flow_target(self) -> Optional[Dict[str, Any]]:
        """Busca una pestaña abierta con Google Flow o la extensión Flow Automation."""
        targets = self.list_targets()
        for t in targets:
            url = t.get('url', '').lower()
            title = t.get('title', '').lower()
            if 'flow' in url or 'flow' in title or 'chrome-extension://' in url:
                return t
        return None

    def wait_for_downloads(self, target_folder: str, expected_clips: int, timeout_seconds: int = 600) -> bool:
        """
        Monitorea la carpeta de destino hasta que se hayan descargado todos los clips esperados
        y no existan archivos temporales incompletos (.crdownload o .tmp).
        """
        logger.info(f"⏳ Vigilando descargas en {target_folder} (Esperando {expected_clips} clips, timeout: {timeout_seconds}s)...")
        start_time = time.time()

        while time.time() - start_time < timeout_seconds:
            if os.path.exists(target_folder):
                files = os.listdir(target_folder)
                # Verificar si hay descargas activas en curso
                has_incomplete = any(f.endswith(('.crdownload', '.tmp', '.part')) for f in files)
                valid_mp4s = [f for f in files if f.endswith('.mp4')]

                if not has_incomplete and len(valid_mp4s) >= expected_clips:
                    # Pausa de estabilidad para asegurar que el sistema de archivos cerró los handles
                    time.sleep(3.0)
                    logger.info(f"✅ Descarga completada: {len(valid_mp4s)}/{expected_clips} clips íntegros.")
                    return True

            time.sleep(5.0)

        logger.error(f"❌ Tiempo de espera agotado ({timeout_seconds}s) esperando clips en {target_folder}")
        return False


if __name__ == "__main__":
    bridge = ChromeFlowBridge()
    active = bridge.is_chrome_running()
    print("Chrome con CDP activo:", active)
    if not active:
        print(f"Para iniciar Chrome en Ubuntu con CDP: google-chrome --remote-debugging-port={DEFAULT_CDP_PORT}")
