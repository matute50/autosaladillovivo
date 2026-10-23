#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
complete_automation.py — Orquestador Multi-Agente Integral para Saladillo Vivo
=============================================================================
Desarrollado para: Saladillo Vivo (Next.js 15 + Supabase)
Objetivo: Coordinar y automatizar el ciclo completo de 5 pasos:
          1. Scraping Directo (ScraperAgent)
          2. Guardado en Base de Datos como Borrador (StorageAgent)
          3. Modificación de Título y Texto con IA (AiRewriterAgent)
          4. Otra vez Guardado en Base de Datos con Datos de IA (StorageAgent)
          5. Publicación Oficial en Base de Datos (PublisherAgent)

Características:
- Cero dependencias forzadas: Biblioteca estándar de Python y `requests`.
- Frecuencia horaria dinámica:
  * 07:00 a 12:00: cada 30 minutos (horas pico matutinas)
  * 12:00 a 22:00: cada 1 hora (tarde y noche)
  * 22:00 a 07:00: cada 3 horas (guardia nocturna pasiva)
- Logging dual estructurado: Consola y archivo rotativo `logs/automation.log` con UTF-8.
- Manejo robusto de timeouts, excepciones y recuperación ante fallos.
- Generación automática del informe de ciclo en `data/cycle_summary.json`.
- Política de oro: NO altera reproductores de video, estética ni frontend.
"""

import os
import sys
import json
import time
import signal
import logging
import threading
from datetime import datetime, timedelta

# Asegurar soporte de encoding en terminales Windows
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# Importar arquitectura multi-agente
from agents.orchestrator_agent import OrchestratorAgent
from agents.scraper_agent import ScraperAgent
from agents.storage_agent import StorageAgent
from agents.ai_rewriter_agent import AiRewriterAgent
from agents.publisher_agent import PublisherAgent

# Directorios de trabajo
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
LOGS_DIR = os.path.join(BASE_DIR, 'logs')

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)

LOG_FILE = os.path.join(LOGS_DIR, 'automation.log')

# Logger
logger = logging.getLogger("SaladilloVivoAutomation")
logger.setLevel(logging.INFO)

if not logger.handlers:
    file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8', mode='a')
    file_formatter = logging.Formatter('%(asctime)s - [%(levelname)s] - %(message)s')
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', datefmt='%H:%M:%S')
    stream_handler.setFormatter(stream_formatter)
    logger.addHandler(stream_handler)


class NewsAutomationSystem:
    """
    Controlador maestro del pipeline de 5 pasos para Saladillo Vivo.
    """
    def __init__(self, limit_per_source=10, run_immediately=True, immediate_publish=True):
        self.limit_per_source = limit_per_source
        self.run_immediately = run_immediately
        self.immediate_publish = immediate_publish
        self.orchestrator = OrchestratorAgent(
            limit_per_source=limit_per_source,
            immediate_publish=immediate_publish
        )
        self.running = False
        self.thread = None
        self._stop_event = threading.Event()

    def get_next_execution_time(self):
        """Calcula próxima ejecución según ventana horaria."""
        return self.orchestrator.get_next_execution_time()

    def execute_full_pipeline(self):
        """Ejecuta el pipeline completo de los 5 pasos coordinados."""
        return self.orchestrator.run_full_pipeline()

    def start_automation(self, in_background=True):
        """Inicia el sistema de automatización."""
        self.running = True
        logger.info("🚀 Sistema de automatización multi-agente iniciado.")

        def run_loop():
            if self.run_immediately:
                logger.info("⚡ Ejecución inmediata inicial activada.")
                self.execute_full_pipeline()

            while self.running and not self._stop_event.is_set():
                next_time, desc = self.get_next_execution_time()
                wait_seconds = max(10, (next_time - datetime.now()).total_seconds())

                logger.info(f"⏰ Próxima ejecución programada en {wait_seconds/60:.1f} minutos ({next_time.strftime('%H:%M:%S')}) — Franja: {desc}")
                self._stop_event.wait(timeout=wait_seconds)

                if self.running and not self._stop_event.is_set():
                    self.execute_full_pipeline()

        if in_background:
            self.thread = threading.Thread(target=run_loop, daemon=True)
            self.thread.start()
        else:
            run_loop()

    def stop_automation(self):
        """Detiene el sistema de automatización de forma controlada."""
        self.running = False
        self._stop_event.set()
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("⏹️ Sistema de automatización detenido.")

    def get_status(self):
        """Obtiene el estado actual del sistema."""
        next_time, _ = self.get_next_execution_time()
        return {
            'running': self.running,
            'execution_count': self.orchestrator.execution_count,
            'last_execution': self.orchestrator.last_execution.isoformat() if self.orchestrator.last_execution else None,
            'next_execution': next_time.isoformat()
        }


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Sistema de Automatización Completo de Noticias para Saladillo Vivo")
    parser.add_argument('--single-run', '--once', action='store_true', dest='single_run', help='Ejecutar un solo ciclo completo de 5 pasos y salir')
    parser.add_argument('--limit', type=int, default=10, help='Límite de artículos por portal (default: 10)')
    parser.add_argument('--no-immediate', action='store_true', help='Publicar en estado no inmediato (para delegar al cron de Make.com)')

    args = parser.parse_args()

    print("=================================================================")
    print(" SALADILLO VIVO — SISTEMA MULTI-AGENTE DE NOTICIAS LOCALES")
    print(f" Inicio: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f" Modo: {'Ejecución Única (--once)' if args.single_run else 'Servicio Continuo Automático'}")
    print(f" Archivo de Log: {LOG_FILE}")
    print("=================================================================")

    automation = NewsAutomationSystem(
        limit_per_source=args.limit,
        run_immediately=True,
        immediate_publish=not args.no_immediate
    )

    if args.single_run:
        success = automation.execute_full_pipeline()
        sys.exit(0 if success else 1)

    def handle_signal(sig, frame):
        automation.stop_automation()
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    try:
        automation.start_automation(in_background=False)
    except KeyboardInterrupt:
        automation.stop_automation()


if __name__ == "__main__":
    main()
