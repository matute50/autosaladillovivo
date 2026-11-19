# -*- coding: utf-8 -*-
"""
agents/video_consolidator.py — Consolidación Multimedia con FFmpeg (TV-Grade 9:16)
================================================================================
Concatena los clips de 8 segundos generados por Google Flow y aplica el diseño
televisivo con Safe Zone para redes sociales (Reels / TikTok / Shorts):

Especificaciones:
- Resolución: 720x1280 (Vertical 9:16).
- Audio: Pista vocal limpia de Ara.
- Zócalo inferior: Franja color negro elevada 140px sobre el borde inferior.
- Logo Saladillo Vivo: Mosca fija a la izquierda del zócalo (public/favicon.ico.png).
- Ticker: Texto continuo de la noticia corriendo de derecha a izquierda en Arial blanca,
  desvaneciéndose/ocultándose por debajo del logo izquierdo.
- Nomenclatura: video_<id>_<slug>.mp4.
- Limpieza automática de clips temporales tras validar el render final.
"""

import os
import sys
import subprocess
import glob
import re
import unicodedata
import json
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any

from .storage_agent import StorageAgent, load_env_credentials

logger = logging.getLogger("VideoConsolidator")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGO_PATH = os.path.join(BASE_DIR, 'public', 'favicon.ico.png')
VIDEOS_DIR = os.path.join(BASE_DIR, 'output', 'videos_finales')
RAW_DIR = os.path.join(BASE_DIR, 'output', 'raw_clips')

os.makedirs(VIDEOS_DIR, exist_ok=True)
os.makedirs(RAW_DIR, exist_ok=True)


def slugify(texto: str) -> str:
    """Convierte un texto en un slug amigable para nombres de archivo."""
    if not texto:
        return "noticia"
    texto_norm = unicodedata.normalize('NFKD', texto).encode('ascii', 'ignore').decode('utf-8')
    texto_limpio = re.sub(r'[^\w\s-]', '', texto_norm).strip().lower()
    return re.sub(r'[-\s]+', '_', texto_limpio)[:45]


class VideoConsolidator:
    """
    Motor de consolidación de video y post-producción gráfica con FFmpeg.
    """

    def __init__(self, logo_path: str = LOGO_PATH, output_dir: str = VIDEOS_DIR):
        self.logo_path = logo_path
        self.output_dir = output_dir
        self.storage = StorageAgent(table='articles')
        self.supabase_url, self.supabase_key = load_env_credentials()

    def get_raw_clips_for_article(self, article_id: int, clips_folder: Optional[str] = None) -> List[str]:
        """Obtiene y ordena numéricamente los clips de 8s del artículo."""
        folder = clips_folder or os.path.join(RAW_DIR, str(article_id))
        if not os.path.exists(folder):
            return []

        clips = glob.glob(os.path.join(folder, "*.mp4"))
        return sorted(clips)

    def consolidate(
        self,
        article_id: int,
        title: str,
        ticker_text: str,
        clips: List[str]
    ) -> Optional[str]:
        """
        Concatena clips y renderiza zócalo negro, ticker y logo con FFmpeg.
        """
        if not clips:
            logger.error(f"[Consolidator] No se proporcionaron clips para article_id={article_id}")
            return None

        slug_title = slugify(title)
        output_filename = f"video_{article_id}_{slug_title}.mp4"
        output_path = os.path.join(self.output_dir, output_filename)

        # 1. Crear lista de concatenación para ffmpeg concat demuxer
        concat_list_path = os.path.join(os.path.dirname(clips[0]), f"concat_{article_id}.txt")
        try:
            with open(concat_list_path, 'w', encoding='utf-8') as f:
                for c in clips:
                    # ffmpeg concat requiere paths escapados
                    abs_path = os.path.abspath(c).replace('\\', '/')
                    f.write(f"file '{abs_path}'\n")
        except Exception as e:
            logger.error(f"Error escribiendo lista concat: {e}")
            return None

        # 2. Parámetros de geometría y Safe Zone (720x1280)
        # Zócalo negro: Y de 1040 a 1130 (altura 90px, a 150px del borde inferior)
        zocalo_y = 1045
        zocalo_h = 85
        logo_w = 65
        logo_h = 65
        logo_x = 25
        logo_y = zocalo_y + (zocalo_h - logo_h) // 2

        # Sanitizar texto de ticker para drawtext de ffmpeg
        ticker_clean = ticker_text.replace("'", "").replace(":", " ").replace("%", " por ciento ")
        ticker_clean = re.sub(r'[\r\n]+', ' ', ticker_clean).strip()

        # Filtro de FFmpeg:
        # [0:v] -> drawbox (zócalo negro completo)
        #       -> drawtext (texto en scroll de derecha a izquierda)
        # [1:v] -> logo escalado a 65x65
        # [base_con_texto][logo_con_bloque] -> overlay del logo sobre la izquierda para tapar el texto saliente
        filter_complex = (
            f"[0:v]scale=720:1280:force_original_aspect_ratio=decrease,pad=720:1280:(ow-iw)/2:(oh-ih)/2,setsar=1,"
            f"drawbox=y={zocalo_y}:color=black@1.0:width=iw:height={zocalo_h}:t=fill,"
            f"drawtext=text='{ticker_clean}':font='Arial':fontsize=26:fontcolor=white:"
            f"y={zocalo_y + 28}:x=w-mod(t*140\\,w+text_w+100)[text_layer];"
            f"[1:v]scale={logo_w}:{logo_h}[logo_scaled];"
            f"[text_layer]drawbox=x=0:y={zocalo_y}:color=black@1.0:width={logo_x + logo_w + 15}:height={zocalo_h}:t=fill[masked_base];"
            f"[masked_base][logo_scaled]overlay=x={logo_x}:y={logo_y}[v_out]"
        )

        has_logo = os.path.exists(self.logo_path)
        input_args = ["-f", "concat", "-safe", "0", "-i", concat_list_path]

        if has_logo:
            input_args.extend(["-i", os.path.abspath(self.logo_path)])
            maps = ["-map", "[v_out]", "-map", "0:a?"]
            vf_arg = ["-filter_complex", filter_complex]
        else:
            # Fallback sin logo: solo zócalo y texto
            simple_vf = (
                f"scale=720:1280:force_original_aspect_ratio=decrease,pad=720:1280:(ow-iw)/2:(oh-ih)/2,setsar=1,"
                f"drawbox=y={zocalo_y}:color=black@1.0:width=iw:height={zocalo_h}:t=fill,"
                f"drawtext=text='{ticker_clean}':font='Arial':fontsize=26:fontcolor=white:y={zocalo_y + 28}:x=w-mod(t*140\\,w+text_w+100)"
            )
            maps = ["-map", "0:v", "-map", "0:a?"]
            vf_arg = ["-vf", simple_vf]

        cmd = [
            "ffmpeg", "-y",
            *input_args,
            *vf_arg,
            *maps,
            "-c:v", "libx264", "-preset", "fast", "-crf", "22",
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
            output_path
        ]

        logger.info(f"[FFmpeg] Iniciando render de {output_filename}...")
        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180)
            if res.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 10000:
                logger.info(f"✅ Video consolidado con éxito: {output_path} ({os.path.getsize(output_path) / 1024:.1f} KB)")
                # Limpieza de lista concat
                if os.path.exists(concat_list_path):
                    os.remove(concat_list_path)
                # Limpieza automática de clips temporales
                self._purge_raw_clips(clips)
                # Actualizar Supabase
                self._update_supabase_status(article_id, output_path)
                return output_path
            else:
                logger.error(f"❌ Error en FFmpeg (code {res.returncode}): {res.stderr.decode('utf-8', errors='ignore')[-300:]}")
                return None
        except Exception as e:
            logger.error(f"❌ Excepción ejecutando FFmpeg: {e}")
            return None

    def _purge_raw_clips(self, clips: List[str]):
        """Elimina los clips crudos temporales tras la consolidación exitosa."""
        for c in clips:
            try:
                if os.path.exists(c):
                    os.remove(c)
            except Exception as e:
                logger.warning(f"No se pudo eliminar clip temporal {c}: {e}")
        logger.info(f"🧹 Purgados {len(clips)} clips temporales.")

    def _update_supabase_status(self, article_id: int, video_path: str):
        """Actualiza en Supabase el estado a 'completado' y la ruta local."""
        now_iso = datetime.now().isoformat()
        payload = {
            'video_status': 'completado',
            'video_path': video_path,
            'video_generated_at': now_iso
        }
        try:
            import requests
            url = f"{self.supabase_url}/rest/v1/articles?id=eq.{article_id}"
            headers = {
                'apikey': self.supabase_key,
                'Authorization': f'Bearer {self.supabase_key}',
                'Content-Type': 'application/json',
                'Prefer': 'return=minimal'
            }
            requests.patch(url, headers=headers, json=payload, timeout=15)
            logger.info(f"✅ Supabase actualizado para article_id={article_id} (video_status='completado').")
        except Exception as e:
            logger.error(f"Error actualizando status en Supabase: {e}")


if __name__ == "__main__":
    consolidator = VideoConsolidator()
    print("VideoConsolidator inicializado. Logo detectado:", os.path.exists(LOGO_PATH))
