# -*- coding: utf-8 -*-
"""
agents/stream_monitor_agent.py — Agente de Monitoreo de Streaming en Vivo
========================================================================
Responsable de la supervisión continua de la transmisión en vivo (YouTube Live / HLS .m3u8),
validando el estado real de emisión mediante deep-check de YouTube ("isLive":true) o disponibilidad HLS,
detectando caídas de señal y notificando para el cambio automático a contingencia.
"""

import logging
import requests
from typing import Dict, Any, Optional

logger = logging.getLogger("StreamMonitorAgent")
logger.setLevel(logging.INFO)


class StreamMonitorAgent:
    """
    Agente centinela del estado de emisión en vivo de Saladillo Vivo.
    """
    def __init__(self, default_stream_url: Optional[str] = None):
        self.default_stream_url = default_stream_url or "https://www.youtube.com/watch?v=live_stream"
        self.last_status: Dict[str, Any] = {
            'is_live': False,
            'source_type': 'unknown',
            'checked_at': None,
            'details': {}
        }

    def check_stream(self, stream_url: Optional[str] = None) -> Dict[str, Any]:
        """
        Inspecciona una URL de stream y determina si está transmitiendo en vivo.
        Soporta YouTube y streams HLS directos (.m3u8).
        """
        url = stream_url or self.default_stream_url
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Cache-Control': 'no-cache'
        }

        try:
            resp = requests.get(url, headers=headers, timeout=12)
            if resp.status_code != 200:
                result = {
                    'is_live': False,
                    'status_code': resp.status_code,
                    'type': 'error',
                    'message': f"Servidor respondió con código {resp.status_code}"
                }
                self.last_status = result
                return result

            # 1. YouTube Deep Check
            if 'youtube.com' in url or 'youtu.be' in url:
                html = resp.text
                has_is_live_true = '"isLive":true' in html
                has_is_live_now = '"isLiveNow":true' in html
                has_live_badge = '"label":"LIVE"' in html or '"label":"EN VIVO"' in html
                is_live = has_is_live_true or has_is_live_now or (has_live_badge and '"isLive":false' not in html)

                result = {
                    'is_live': is_live,
                    'type': 'youtube',
                    'is_live_true': has_is_live_true,
                    'is_live_now': has_is_live_now,
                    'has_badge': has_live_badge,
                    'url': url
                }
                logger.info(f"StreamMonitorAgent YouTube Check: Live={is_live}")
                self.last_status = result
                return result

            # 2. HLS / m3u8 Check
            if '.m3u8' in url:
                text = resp.text
                is_valid_m3u8 = '#EXTM3U' in text
                result = {
                    'is_live': is_valid_m3u8,
                    'type': 'hls',
                    'has_m3u8_header': is_valid_m3u8,
                    'url': url
                }
                logger.info(f"StreamMonitorAgent HLS Check: Live={is_valid_m3u8}")
                self.last_status = result
                return result

            result = {'is_live': True, 'type': 'generic', 'url': url}
            self.last_status = result
            return result

        except Exception as e:
            logger.error(f"Error comprobando stream {url}: {e}")
            result = {'is_live': False, 'type': 'exception', 'error': str(e), 'url': url}
            self.last_status = result
            return result

    def get_last_status(self) -> Dict[str, Any]:
        """Retorna el último estado registrado de la transmisión."""
        return self.last_status
