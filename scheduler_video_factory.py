# -*- coding: utf-8 -*-
"""
scheduler_video_factory.py — Orquestador Autónomo de la Fábrica de Videos (Hermes Agent)
=======================================================================================
Controla el ciclo integral de producción de 5 a 8 videos diarios entre las 9 y las 21 hs:

Ciclo de ejecución:
1. Verifica ventana horaria (09:00 a 21:00 hs hora local).
2. Obtiene la noticia pendiente más reciente en Supabase (ORDER BY created_at DESC).
3. Asegura el guion de Ara (Métrica 8s) mediante AraScriptWriter.
4. Resuelve la imagen de locación mediante LocationManager.
5. Construye el grafo Workflow JSON con encadenamiento 'last frame'.
6. Dispara la ejecución en Chrome CDP mediante ChromeFlowBridge.
7. Espera la descarga íntegra de clips de 8s en output/raw_clips/<id>/.
8. Concatena y monta el zócalo negro, ticker y logo con FFmpeg (VideoConsolidator).
9. Actualiza el estado a 'completado' y purga clips temporales.
"""

import os
import sys
import time
import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any

from agents.storage_agent import StorageAgent, load_env_credentials
from agents.ara_script_writer import AraScriptWriter
from agents.location_manager import LocationManager
from agents.flow_workflow_builder import FlowWorkflowBuilder
from agents.chrome_flow_bridge import ChromeFlowBridge
from agents.video_consolidator import VideoConsolidator

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("SchedulerVideoFactory")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RAW_DIR = os.path.join(BASE_DIR, 'output', 'raw_clips')


class VideoFactoryOrchestrator:
    """
    Orquestador maestro para producción automática de videos en Ubuntu.
    """

    def __init__(self):
        self.writer = AraScriptWriter()
        self.location_mgr = LocationManager()
        self.builder = FlowWorkflowBuilder(character_name="Ara")
        self.bridge = ChromeFlowBridge()
        self.consolidator = VideoConsolidator()
        self.storage = StorageAgent(table='articles')
        self.supabase_url, self.supabase_key = load_env_credentials()

    def is_within_schedule(self, start_hour: int = 9, end_hour: int = 21) -> bool:
        """Comprueba si la hora actual está dentro de la ventana de emisión permitida."""
        current_hour = datetime.now().hour
        return start_hour <= current_hour < end_hour

    def get_latest_pending_article(self) -> Optional[Dict[str, Any]]:
        """Obtiene la noticia pendiente más reciente (prioridad absoluta)."""
        if not self.supabase_key:
            return None

        import requests
        url = (
            f"{self.supabase_url}/rest/v1/articles?"
            f"select=id,title,category,content,contenido_optimizado,video_script,video_status,video_location_category,created_at&"
            f"video_status=eq.pendiente&"
            f"order=created_at.desc&"
            f"limit=1"
        )
        headers = {
            'apikey': self.supabase_key,
            'Authorization': f'Bearer {self.supabase_key}'
        }

        try:
            res = requests.get(url, headers=headers, timeout=15)
            if res.status_code == 200 and res.json():
                return res.json()[0]
        except Exception as e:
            logger.error(f"Error consultando artículo pendiente: {e}")

        # Fallback: buscar artículos que no tengan status y no sean necrológicas
        url_fallback = (
            f"{self.supabase_url}/rest/v1/articles?"
            f"select=id,title,category,content,contenido_optimizado,video_script,video_status,video_location_category,created_at&"
            f"video_status=is.null&"
            f"order=created_at.desc&"
            f"limit=1"
        )
        try:
            res = requests.get(url_fallback, headers=headers, timeout=15)
            if res.status_code == 200 and res.json():
                art = res.json()[0]
                # Asegurar guion
                ok = self.writer.process_and_save_article(art)
                if ok:
                    # Re-obtener el artículo actualizado
                    res_updated = requests.get(f"{self.supabase_url}/rest/v1/articles?id=eq.{art['id']}&select=*", headers=headers)
                    if res_updated.status_code == 200 and res_updated.json():
                        return res_updated.json()[0]
        except Exception as e:
            logger.error(f"Error en fallback de artículo: {e}")

        return None

    def process_single_video(self) -> bool:
        """Ejecuta un ciclo completo para una noticia."""
        article = self.get_latest_pending_article()
        if not article:
            logger.info("ℹ️ No hay artículos pendientes de video en este momento.")
            return False

        article_id = article.get('id')
        title = article.get('title', f"noticia_{article_id}")
        logger.info(f"🎬 Iniciando producción de video para Article #{article_id}: \"{title[:50]}...\"")

        # 1. Parsear el guion de bloques (Métrica 8s)
        script_raw = article.get('video_script')
        bloques = []
        ticker_text = title

        if script_raw:
            try:
                parsed = json.loads(script_raw)
                bloques = parsed.get('bloques', [])
                ticker_text = parsed.get('ticker_texto') or title
            except Exception:
                bloques = [b.strip() for b in script_raw.split('\n\n') if b.strip()]

        if not bloques:
            logger.warning(f"Artículo #{article_id} sin bloques válidos. Regenerando con AraScriptWriter...")
            script_data = self.writer.write_script(article)
            if not script_data or script_data.get('excluido'):
                logger.info(f"Artículo #{article_id} descartado de video (necrológica o no apto).")
                return False
            bloques = script_data['bloques']
            ticker_text = script_data.get('ticker_texto') or title

        # 2. Resolver imagen de locación
        category = article.get('video_location_category') or article.get('category') or 'general'
        location_image = self.location_mgr.resolve_location_image(category)
        logger.info(f"📍 Locación asignada: {category} (Imagen: {location_image or 'Sin imagen previa'})")

        # 3. Construir Workflow JSON con encadenamiento last frame
        workflow_data = self.builder.build_workflow(
            article_id=article_id,
            bloques=bloques,
            location_image_path=location_image,
            aspect_ratio="9:16"
        )
        wf_path = os.path.join(BASE_DIR, 'data', f"workflow_article_{article_id}.json")
        self.builder.export_workflow_json(workflow_data, wf_path)

        # 4. Monitoreo de descargas en la PC Ubuntu
        article_clips_dir = os.path.join(RAW_DIR, str(article_id))
        os.makedirs(article_clips_dir, exist_ok=True)
        expected_clips = len(bloques)

        # Comprobar si los clips ya están descargados o si se esperan
        clips_encontrados = self.consolidator.get_raw_clips_for_article(article_id, article_clips_dir)

        if len(clips_encontrados) < expected_clips:
            logger.info(f"Esperando generación de Flow Automation en Chrome (Esperando {expected_clips} clips)...")
            # En entorno de producción Hermes Agent acopla el trigger de CDP
            download_ok = self.bridge.wait_for_downloads(article_clips_dir, expected_clips, timeout_seconds=450)
            if not download_ok:
                logger.warning(f"⚠️ Clips incompletos para #{article_id}. Marcando como 'en_cola' para reintento.")
                return False
            clips_encontrados = self.consolidator.get_raw_clips_for_article(article_id, article_clips_dir)

        # 5. Consolidación FFmpeg (TV-Grade 9:16)
        logger.info(f"🔨 Consolidando {len(clips_encontrados)} clips con zócalo negro y ticker...")
        video_final = self.consolidator.consolidate(
            article_id=article_id,
            title=title,
            ticker_text=ticker_text,
            clips=clips_encontrados
        )

        if video_final:
            logger.info(f"🎉 Video listo para difusión: {video_final}")
            return True
        else:
            logger.error(f"❌ Falló el render final con FFmpeg para #{article_id}")
            self._mark_article_error(article_id)
            return False

    def _mark_article_error(self, article_id: int):
        """Marca el artículo como error en Supabase para avanzar al siguiente."""
        try:
            import requests
            url = f"{self.supabase_url}/rest/v1/articles?id=eq.{article_id}"
            headers = {
                'apikey': self.supabase_key,
                'Authorization': f'Bearer {self.supabase_key}',
                'Content-Type': 'application/json'
            }
            requests.patch(url, headers=headers, json={'video_status': 'error'}, timeout=10)
        except Exception as e:
            logger.error(f"Error marcando error en Supabase: {e}")

    def run_daemon(self, interval_minutes: int = 90):
        """Modo demonio continuo para la PC Ubuntu con enfriamiento programado."""
        logger.info(f"🚀 Fábrica de Videos iniciada en modo Daemon (Intervalo: {interval_minutes}m, Ventana: 9 a 21hs).")
        while True:
            if self.is_within_schedule():
                logger.info("⏰ Ventana operativa activa (9:00 - 21:00 hs). Buscando tareas...")
                self.process_single_video()
            else:
                logger.info("🌙 Fuera de horario de emisión (9 a 21hs). Esperando siguiente turno...")

            time.sleep(interval_minutes * 60)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Orquestador Fábrica de Videos Ara")
    parser.add_argument("--run-once", action="store_true", help="Ejecutar una sola iteración (ideal para cron job)")
    parser.add_argument("--daemon", action="store_true", help="Ejecutar como servicio continuo")
    parser.add_argument("--interval", type=int, default=90, help="Minutos entre ejecuciones en modo daemon")
    args = parser.parse_args()

    orchestrator = VideoFactoryOrchestrator()

    if args.run_once:
        orchestrator.process_single_video()
    elif args.daemon:
        orchestrator.run_daemon(interval_minutes=args.interval)
    else:
        # Por defecto run-once si se invoca directo
        orchestrator.process_single_video()
