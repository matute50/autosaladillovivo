# -*- coding: utf-8 -*-
"""
agents/orchestrator_agent.py — Agente Maestro de Orquestación Periodística
========================================================================
Coordina de forma autónoma el ciclo de 5 pasos requerido para Saladillo Vivo:
  1. Scraping de noticias locales (ScraperAgent)
  2. Guardado en base de datos como borrador/raw (StorageAgent)
  3. Modificación de título y texto con IA (AiRewriterAgent)
  4. Otra vez guardado en base de datos con los datos de IA (StorageAgent)
  5. Publicación oficial final (PublisherAgent)

Características:
- Programación dinámica por franjas horarias (30 min / 1 hora / 3 horas).
- Modo de ejecución inmediata única (--once) y modo continuo (daemon).
- Logging estructurado dual (consola + logs/automation.log).
- Informes de ejecución en data/cycle_summary.json.
"""

import os
import sys
import json
import time
import logging
import threading
from datetime import datetime, timedelta

from .scraper_agent import ScraperAgent
from .storage_agent import StorageAgent
from .ai_rewriter_agent import AiRewriterAgent
from .publisher_agent import PublisherAgent

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')
LOGS_DIR = os.path.join(BASE_DIR, 'logs')

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)

logger = logging.getLogger("SaladilloVivoMultiAgent")
logger.setLevel(logging.INFO)

if not logger.handlers:
    fh = logging.FileHandler(os.path.join(LOGS_DIR, 'automation.log'), encoding='utf-8', mode='a')
    fh.setFormatter(logging.Formatter('%(asctime)s - [%(levelname)s] - %(message)s'))
    logger.addHandler(fh)

    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', datefmt='%H:%M:%S'))
    logger.addHandler(sh)


class OrchestratorAgent:
    """
    Orquestador multi-agente del ciclo de noticias.
    """
    def __init__(self, limit_per_source=10, immediate_publish=True):
        self.limit_per_source = limit_per_source
        self.immediate_publish = immediate_publish
        self.running = False
        self.thread = None
        self.last_execution = None
        self.execution_count = 0
        self._stop_event = threading.Event()

        # Instanciar agentes
        self.scraper_agent = ScraperAgent()
        self.storage_agent = StorageAgent()
        self.rewriter_agent = AiRewriterAgent()
        self.publisher_agent = PublisherAgent(self.storage_agent)

    def get_next_execution_time(self, current_dt=None):
        """
        Calcula la próxima ejecución según la franja horaria:
        - 07:00 a 12:00: cada 30 minutos
        - 12:00 a 22:00: cada 1 hora
        - 22:00 a 07:00: cada 3 horas
        """
        now = current_dt or datetime.now()
        hour = now.hour

        if 7 <= hour < 12:
            target_min = 30 if now.minute < 30 else 0
            if target_min == 0:
                next_time = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
            else:
                next_time = now.replace(minute=30, second=0, microsecond=0)
            freq_desc = "30 minutos (07:00 a 12:00)"
        elif 12 <= hour < 22:
            next_time = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
            freq_desc = "1 hora (12:00 a 22:00)"
        else:
            next_time = (now + timedelta(hours=3)).replace(minute=0, second=0, microsecond=0)
            freq_desc = "3 horas (22:00 a 07:00)"

        return next_time, freq_desc

    def run_full_pipeline(self):
        """
        Ejecuta el ciclo de 5 pasos:
        1. Scraping
        2. Guardar en Base de Datos (Borrador)
        3. Modificar Título y Texto con IA
        4. Guardar en Base de Datos (Actualización IA)
        5. Publicar en Base de Datos
        """
        start_time = datetime.now()
        logger.info("=================================================================")
        logger.info("🚀 INICIANDO CICLO MULTI-AGENTE DE NOTICIAS — SALADILLO VIVO")
        logger.info(f"   Hora de inicio: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=================================================================")

        # Verificar conectividad con Supabase
        if not self.storage_agent.verify_connection():
            logger.error("❌ Falló la verificación de conexión con Supabase. Abortando ciclo.")
            return False

        # Cargar historial local para no re-scrapear
        history_path = os.path.join(DATA_DIR, 'scraped_articles.json')
        existing_hashes = set()
        if os.path.exists(history_path):
            try:
                with open(history_path, 'r', encoding='utf-8') as f:
                    history = json.load(f)
                    for item in history:
                        if 'hash' in item:
                            existing_hashes.add(item['hash'])
            except Exception:
                pass

        # ----------------------------------------------------------------------
        # PASO 1: SCRAPING
        # ----------------------------------------------------------------------
        logger.info("📰 [PASO 1/5] ScraperAgent: Extrayendo noticias locales...")
        scraped_articles = self.scraper_agent.scrape_all(
            limit_per_source=self.limit_per_source,
            existing_hashes=existing_hashes
        )

        if not scraped_articles:
            logger.info("ℹ️ No se detectaron noticias nuevas en esta iteración.")
            # Verificar si hay borradores previos pendientes de procesar
            pending_db = self.storage_agent.find_pending_ai_articles(limit=5)
            if not pending_db:
                logger.info("✅ No hay tareas pendientes en la base de datos.")
                return True
            logger.info(f"🔁 Se encontraron {len(pending_db)} artículos en borrador para continuar el flujo.")
            articles_to_process = pending_db
        else:
            logger.info(f"✅ [PASO 1/5] Scraping finalizado: {len(scraped_articles)} artículos nuevos extraídos.")
            # Guardar backup local
            all_scraped = scraped_articles
            if os.path.exists(history_path):
                try:
                    with open(history_path, 'r', encoding='utf-8') as f:
                        all_scraped = scraped_articles + json.load(f)
                except Exception:
                    pass
            with open(history_path, 'w', encoding='utf-8') as f:
                json.dump(all_scraped, f, ensure_ascii=False, indent=2)

            # ------------------------------------------------------------------
            # PASO 2: GUARDAR EN BASE DE DATOS (BORRADOR)
            # ------------------------------------------------------------------
            logger.info("💾 [PASO 2/5] StorageAgent: Guardando en Supabase como borrador preliminar...")
            articles_to_process = []
            for art in scraped_articles:
                draft_record = self.storage_agent.save_draft(art)
                if draft_record and draft_record.get('id'):
                    art['id'] = draft_record['id']
                    articles_to_process.append(art)
                time.sleep(0.5)

            logger.info(f"✅ [PASO 2/5] Guardados en Supabase: {len(articles_to_process)} borradores con ID asignado.")

        if not articles_to_process:
            logger.warning("⚠️ No se pudieron registrar artículos en la base de datos.")
            return False

        # ----------------------------------------------------------------------
        # PASO 3: MODIFICAR TÍTULO Y TEXTO CON IA
        # ----------------------------------------------------------------------
        logger.info("🤖 [PASO 3/5] AiRewriterAgent: Reestructurando con IA Free-First (GLM/Gemini/OpenAI/Fallback)...")
        modified_list = []
        for art in articles_to_process:
            ai_data = self.rewriter_agent.rewrite_article(art)
            art.update(ai_data)
            modified_list.append(art)
            time.sleep(1.0)

        # Guardar en JSON local de respaldo
        with open(os.path.join(DATA_DIR, 'modified_articles.json'), 'w', encoding='utf-8') as f:
            json.dump(modified_list, f, ensure_ascii=False, indent=2)

        logger.info(f"✅ [PASO 3/5] Modificación con IA completada: {len(modified_list)} artículos listos.")

        # ----------------------------------------------------------------------
        # PASO 4: OTRA VEZ GUARDAR EN BASE DE DATOS (ACTUALIZAR CON IA)
        # ----------------------------------------------------------------------
        logger.info("🔄 [PASO 4/5] StorageAgent: Actualizando registros en Supabase con contenido de IA...")
        updated_count = 0
        for art in modified_list:
            art_id = art.get('id')
            upd = self.storage_agent.update_with_ai(art_id, art)
            if upd:
                updated_count += 1
            time.sleep(0.5)

        logger.info(f"✅ [PASO 4/5] Base de datos actualizada: {updated_count}/{len(modified_list)} artículos con datos de IA.")

        # ----------------------------------------------------------------------
        # PASO 5: FINALMENTE PUBLICAR
        # ----------------------------------------------------------------------
        logger.info("📢 [PASO 5/5] PublisherAgent: Publicando oficialmente...")
        published_count = 0
        for art in modified_list:
            art_id = art.get('id')
            img = art.get('image_url')
            pub = self.publisher_agent.publish_article(art_id, image_url=img, immediate=self.immediate_publish)
            if pub:
                published_count += 1
            time.sleep(0.5)

        logger.info(f"✅ [PASO 5/5] Publicación completada: {published_count}/{len(modified_list)} noticias en vivo.")

        # Generar reporte de ciclo
        duration = datetime.now() - start_time
        cycle_report = {
            'execution_id': self.execution_count + 1,
            'start_time': start_time.isoformat(),
            'end_time': datetime.now().isoformat(),
            'duration_seconds': duration.total_seconds(),
            'scraped_count': len(scraped_articles),
            'drafts_saved_to_db': len(articles_to_process),
            'ai_modified_count': len(modified_list),
            'db_updated_with_ai': updated_count,
            'published_count': published_count,
            'success_rate': (published_count / len(modified_list) * 100) if modified_list else 100.0,
            'timestamp': datetime.now().isoformat()
        }

        with open(os.path.join(DATA_DIR, 'cycle_summary.json'), 'w', encoding='utf-8') as f:
            json.dump(cycle_report, f, ensure_ascii=False, indent=2)

        self.execution_count += 1
        self.last_execution = datetime.now()

        logger.info(f"🎉 Ciclo completado con éxito en {duration.total_seconds():.1f} segundos.")
        return True

    def start_scheduler(self):
        """Inicia el ciclo automático en un hilo en segundo plano."""
        self.running = True

        def loop():
            while self.running and not self._stop_event.is_set():
                self.run_full_pipeline()
                next_time, desc = self.get_next_execution_time()
                wait_sec = max(10, (next_time - datetime.now()).total_seconds())
                logger.info(f"⏰ Próximo ciclo en {wait_sec/60:.1f} minutos ({next_time.strftime('%H:%M:%S')}) — Franja: {desc}")
                self._stop_event.wait(timeout=wait_sec)

        self.thread = threading.Thread(target=loop, daemon=True)
        self.thread.start()
        logger.info("🟢 Agente Orquestador iniciado en modo continuo.")

    def stop_scheduler(self):
        """Detiene el orquestador de manera limpia."""
        self.running = False
        self._stop_event.set()
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("🔴 Agente Orquestador detenido.")
