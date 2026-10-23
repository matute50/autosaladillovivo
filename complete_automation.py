#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
complete_automation.py — Orquestador Integral de Noticias de Saladillo Vivo
===========================================================================
Desarrollado para: Saladillo Vivo (Next.js 15 + Supabase)
Objetivo: Coordinar y automatizar el ciclo completo de noticias:
         1. Scraping Directo (simple_scraper.py)
         2. Enriquecimiento con IA Free-First (free_rewriter.py)
         3. Publicación en Supabase (publish_to_supabase.py)

Características:
- Cero dependencias forzadas: Implementado con bibliotecas estándar de Python
  (subprocess, threading, time, datetime, logging, json, os, sys, signal).
- Compatible con Windows, Linux y macOS usando `sys.executable`.
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
import subprocess
from datetime import datetime, timedelta

# Asegurar soporte de encoding en terminales Windows
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# ==============================================================================
# CONFIGURACIÓN DE DIRECTORIOS Y LOGGING
# ==============================================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
LOGS_DIR = os.path.join(BASE_DIR, 'logs')

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)

LOG_FILE = os.path.join(LOGS_DIR, 'automation.log')

# Configuración del Logger
logger = logging.getLogger("SaladilloVivoAutomation")
logger.setLevel(logging.INFO)

# Evitar duplicación de handlers si se recarga
if not logger.handlers:
    # Handler de archivo (con encoding UTF-8 explícito)
    file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8', mode='a')
    file_formatter = logging.Formatter('%(asctime)s - [%(levelname)s] - %(message)s')
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    # Handler de consola
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', datefmt='%H:%M:%S')
    stream_handler.setFormatter(stream_formatter)
    logger.addHandler(stream_handler)


# ==============================================================================
# CLASE PRINCIPAL: SISTEMA DE ORQUESTACIÓN
# ==============================================================================
class NewsAutomationSystem:
    """
    Controlador maestro del pipeline de noticias para Saladillo Vivo.
    """
    def __init__(self, limit_per_source=15, run_immediately=True):
        self.limit_per_source = limit_per_source
        self.run_immediately = run_immediately
        self.running = False
        self.thread = None
        self.last_execution = None
        self.execution_count = 0
        self._stop_event = threading.Event()

    def get_next_execution_time(self, current_dt=None):
        """
        Calcula la próxima ejecución de acuerdo con la hora local:
        - 07:00 - 12:00: cada 30 minutos
        - 12:00 - 22:00: cada 1 hora
        - 22:00 - 07:00: cada 3 horas
        """
        now = current_dt or datetime.now()
        hour = now.hour

        if 7 <= hour < 12:
            target_min = 30 if now.minute < 30 else 0
            if target_min == 0:
                next_time = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
            else:
                next_time = now.replace(minute=30, second=0, microsecond=0)
            desc = "30 minutos (07:00 - 12:00)"

        elif 12 <= hour < 22:
            next_time = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
            desc = "1 hora (12:00 - 22:00)"

        else:
            next_time = (now + timedelta(hours=3)).replace(minute=0, second=0, microsecond=0)
            desc = "3 horas (22:00 - 07:00)"

        return next_time, desc

    # --------------------------------------------------------------------------
    # SUBPROCESO 1: SCRAPING DE NOTICIAS
    # --------------------------------------------------------------------------
    def execute_scraping(self):
        """Ejecuta simple_scraper.py mediante subproceso seguro."""
        logger.info("[Paso 1/3] Iniciando scraping de noticias locales...")
        script_path = os.path.join(BASE_DIR, 'simple_scraper.py')

        cmd = [
            sys.executable,
            script_path,
            '--limit', str(self.limit_per_source)
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=360,  # 6 minutos máximo
                cwd=BASE_DIR
            )

            if result.returncode == 0:
                scraped_file = os.path.join(DATA_DIR, 'scraped_articles.json')
                if os.path.exists(scraped_file):
                    with open(scraped_file, 'r', encoding='utf-8') as f:
                        articles = json.load(f)
                    logger.info(f"[Paso 1/3 OK] Scraping finalizado: {len(articles)} artículos en base local.")
                    return articles
                logger.warning("[Paso 1/3] Script finalizó pero no generó scraped_articles.json.")
                return []
            else:
                logger.error(f"[Paso 1/3 ERROR] Scraping falló (código {result.returncode}):\n{result.stderr[-400:]}")
                return None

        except subprocess.TimeoutExpired:
            logger.error("[Paso 1/3 ERROR] Timeout excedido en el script de scraping.")
            return None
        except Exception as e:
            logger.error(f"[Paso 1/3 ERROR] Excepción ejecutando scraping: {e}")
            return None

    # --------------------------------------------------------------------------
    # SUBPROCESO 2: MODIFICACIÓN CON IA (FREE-FIRST)
    # --------------------------------------------------------------------------
    def execute_ia_modification(self, articles):
        """Ejecuta free_rewriter.py sobre los artículos recopilados."""
        logger.info(f"[Paso 2/3] Iniciando reescritura con IA para {len(articles)} artículos...")
        script_path = os.path.join(BASE_DIR, 'free_rewriter.py')

        cmd = [
            sys.executable,
            script_path,
            '--input', os.path.join(DATA_DIR, 'scraped_articles.json'),
            '--output', os.path.join(DATA_DIR, 'modified_articles.json')
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=600,  # 10 minutos máximo
                cwd=BASE_DIR
            )

            if result.returncode == 0:
                modified_file = os.path.join(DATA_DIR, 'modified_articles.json')
                if os.path.exists(modified_file):
                    with open(modified_file, 'r', encoding='utf-8') as f:
                        modified_data = json.load(f)
                    logger.info(f"[Paso 2/3 OK] Modificación con IA completada: {len(modified_data)} artículos listos.")
                    return modified_data
                logger.warning("[Paso 2/3] Script finalizó pero no generó modified_articles.json.")
                return []
            else:
                logger.error(f"[Paso 2/3 ERROR] IA falló (código {result.returncode}):\n{result.stderr[-400:]}")
                return None

        except subprocess.TimeoutExpired:
            logger.error("[Paso 2/3 ERROR] Timeout excedido en reescritura de IA.")
            return None
        except Exception as e:
            logger.error(f"[Paso 2/3 ERROR] Excepción en reescritura con IA: {e}")
            return None

    # --------------------------------------------------------------------------
    # SUBPROCESO 3: PUBLICACIÓN EN SUPABASE
    # --------------------------------------------------------------------------
    def execute_publishing(self, articles):
        """Ejecuta publish_to_supabase.py para insertar los artículos en la base."""
        logger.info(f"[Paso 3/3] Publicando {len(articles)} artículos en Supabase...")
        script_path = os.path.join(BASE_DIR, 'publish_to_supabase.py')

        cmd = [
            sys.executable,
            script_path,
            '--input', os.path.join(DATA_DIR, 'modified_articles.json'),
            '--report', os.path.join(DATA_DIR, 'publish_report.json')
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=900,  # 15 minutos máximo
                cwd=BASE_DIR
            )

            report_file = os.path.join(DATA_DIR, 'publish_report.json')
            if os.path.exists(report_file):
                with open(report_file, 'r', encoding='utf-8') as f:
                    report = json.load(f)
                logger.info(f"[Paso 3/3 OK] Publicación: {report.get('published_count', 0)} insertados / {report.get('failed_count', 0)} fallidos.")
                return report
            else:
                logger.error(f"[Paso 3/3 ERROR] No se generó reporte de publicación. Salida:\n{result.stderr[-400:]}")
                return None

        except subprocess.TimeoutExpired:
            logger.error("[Paso 3/3 ERROR] Timeout excedido publicando en Supabase.")
            return None
        except Exception as e:
            logger.error(f"[Paso 3/3 ERROR] Excepción publicando en Supabase: {e}")
            return None

    # --------------------------------------------------------------------------
    # GENERADOR DE REPORTES DE CICLO
    # --------------------------------------------------------------------------
    def generate_execution_report(self, start_time, scraping_result, ia_result, publish_result):
        """Genera un archivo resumen consolidado en data/cycle_summary.json."""
        end_time = datetime.now()
        duration_sec = (end_time - start_time).total_seconds()

        total = publish_result.get('total_articles', len(ia_result) if ia_result else 0)
        published = publish_result.get('published_count', 0)
        failed = publish_result.get('failed_count', 0)
        success_rate = (published / total * 100) if total > 0 else 0.0

        summary = {
            'execution_id': self.execution_count + 1,
            'status': 'completed' if published > 0 or total == 0 else 'failed',
            'start_time': start_time.isoformat(),
            'end_time': end_time.isoformat(),
            'duration_seconds': round(duration_sec, 2),
            'scraping_count': len(scraping_result) if scraping_result else 0,
            'ia_modified_count': len(ia_result) if ia_result else 0,
            'published_count': published,
            'failed_count': failed,
            'success_rate_percent': round(success_rate, 2),
            'timestamp': datetime.now().isoformat()
        }

        summary_file = os.path.join(DATA_DIR, 'cycle_summary.json')
        try:
            with open(summary_file, 'w', encoding='utf-8') as f:
                json.dump(summary, f, ensure_ascii=False, indent=2)
            logger.info(f"[Reporte] Resumen de ciclo guardado en '{summary_file}' ({success_rate:.1f}% éxito).")
        except Exception as e:
            logger.error(f"[Reporte ERROR] No se pudo guardar cycle_summary.json: {e}")

        return summary

    # --------------------------------------------------------------------------
    # EJECUCIÓN DEL PIPELINE COMPLETO
    # --------------------------------------------------------------------------
    def execute_full_pipeline(self):
        """
        Orquesta el flujo secuencial completo: Scraping -> IA -> Publicación.
        """
        start_time = datetime.now()
        logger.info("================================================================")
        logger.info(f"🚀 INICIANDO CICLO #{self.execution_count + 1} DE AUTOMATIZACIÓN COMPLETA")
        logger.info("================================================================")

        try:
            # 1. Scraping
            scraping_result = self.execute_scraping()
            if scraping_result is None or len(scraping_result) == 0:
                logger.warning("[!] Scraping no devolvió artículos nuevos. Concluyendo ciclo sin cambios.")
                return False

            # 2. Reescritura IA
            ia_result = self.execute_ia_modification(scraping_result)
            if ia_result is None or len(ia_result) == 0:
                logger.error("[!] Falló la etapa de IA. Abortando publicación para proteger calidad.")
                return False

            # 3. Publicación
            publish_result = self.execute_publishing(ia_result)
            if publish_result is None:
                logger.error("[!] Falló la etapa de publicación en Supabase.")
                return False

            # 4. Reporte consolidado
            self.generate_execution_report(start_time, scraping_result, ia_result, publish_result)

            self.execution_count += 1
            self.last_execution = datetime.now()
            logger.info(f"🎉 Ciclo #{self.execution_count} completado exitosamente en {(datetime.now() - start_time).total_seconds():.1f}s.")
            return True

        except Exception as e:
            logger.error(f"[!] Error crítico no controlado en pipeline: {e}", exc_info=True)
            return False

    # --------------------------------------------------------------------------
    # BUCLE DEL PLANIFICADOR
    # --------------------------------------------------------------------------
    def _run_loop(self):
        """Bucle permanente de automatización periódica."""
        logger.info("⚡ Planificador de automatización en ejecución activa.")

        if self.run_immediately:
            logger.info("▶ Ejecución inicial inmediata activada.")
            self.execute_full_pipeline()

        while self.running and not self._stop_event.is_set():
            next_time, interval_desc = self.get_next_execution_time()
            now = datetime.now()
            wait_seconds = max(5.0, (next_time - now).total_seconds())

            next_str = next_time.strftime("%H:%M:%S (%d/%m/%Y)")
            logger.info(f"⏰ Próximo ciclo programado: {next_str} | Intervalo: {interval_desc}")
            logger.info(f"💤 Esperando {int(wait_seconds)} segundos ({wait_seconds/60:.1f} minutos)...")

            # Espera reactiva con stop_event para responder inmediatamente a Ctrl+C
            if self._stop_event.wait(timeout=wait_seconds):
                break

            if self.running and not self._stop_event.is_set():
                self.execute_full_pipeline()

        logger.info("⏹ Bucle de automatización detenido.")

    def start_automation(self, in_background=True):
        """Inicia el sistema de automatización."""
        self.running = True
        self._stop_event.clear()

        if in_background:
            self.thread = threading.Thread(target=self._run_loop, daemon=True, name="NewsAutomationThread")
            self.thread.start()
            logger.info("🚀 Hilo en segundo plano de automatización iniciado.")
        else:
            self._run_loop()

    def stop_automation(self):
        """Detiene de forma limpia el sistema de automatización."""
        logger.info("Deteniendo sistema de automatización...")
        self.running = False
        self._stop_event.set()
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=8)
        logger.info("✅ Sistema de automatización detenido.")

    def get_status(self):
        """Devuelve un diccionario con el estado actual del sistema."""
        next_time, _ = self.get_next_execution_time()
        return {
            'running': self.running,
            'execution_count': self.execution_count,
            'last_execution': self.last_execution.isoformat() if self.last_execution else None,
            'next_execution': next_time.isoformat()
        }


# ==============================================================================
# ENTRADA PRINCIPAL Y CONFIGURACIÓN CLI
# ==============================================================================
def main():
    import argparse
    parser = argparse.ArgumentParser(description="Orquestador Completo de Noticias para Saladillo Vivo")
    parser.add_argument('--run-now', action='store_true', help='Ejecutar un ciclo inmediatamente al iniciar')
    parser.add_argument('--single-run', action='store_true', help='Ejecutar un solo ciclo completo y salir')
    parser.add_argument('--limit', type=int, default=15, help='Límite de artículos por portal (default: 15)')
    parser.add_argument('--no-initial-run', action='store_true', help='Esperar al próximo horario programado sin ejecutar al inicio')

    args = parser.parse_args()

    print("=================================================================")
    print(" SALADILLO VIVO — ORQUESTADOR DE AUTOMATIZACIÓN COMPLETA")
    print(f" Inicio: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f" Modo: {'Ejecución Única (--single-run)' if args.single_run else 'Servicio Continuo'}")
    print(f" Archivo de Log: {LOG_FILE}")
    print("=================================================================")

    run_immediately = args.run_now or not args.no_initial_run

    automation = NewsAutomationSystem(
        limit_per_source=args.limit,
        run_immediately=run_immediately
    )

    if args.single_run:
        success = automation.execute_full_pipeline()
        sys.exit(0 if success else 1)

    # Captura de señales para detención limpia (Ctrl + C)
    def handle_signal(sig, frame):
        automation.stop_automation()
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    try:
        automation.start_automation(in_background=False)
    except KeyboardInterrupt:
        automation.stop_automation()


if __name__ == '__main__':
    main()
