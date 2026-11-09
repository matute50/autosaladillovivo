"""
Rotador inteligente de 10 cuentas Google Cloud TTS.
Round-robin con control de cuotas y fallback automático.
Inicialización perezosa: no falla si no hay credenciales.
"""
import os
import time
import random
import logging
from typing import Optional, Tuple

logger = logging.getLogger("GCP_TTS_Rotator")

GCP_PROJECTS = [
    {"id": "saladillo-tts-01", "creds": "gcp_01.json", "quota": 0, "limit": 4_000_000},
    {"id": "saladillo-tts-02", "creds": "gcp_02.json", "quota": 0, "limit": 4_000_000},
    {"id": "saladillo-tts-03", "creds": "gcp_03.json", "quota": 0, "limit": 4_000_000},
    {"id": "saladillo-tts-04", "creds": "gcp_04.json", "quota": 0, "limit": 4_000_000},
    {"id": "saladillo-tts-05", "creds": "gcp_05.json", "quota": 0, "limit": 4_000_000},
    {"id": "saladillo-tts-06", "creds": "gcp_06.json", "quota": 0, "limit": 4_000_000},
    {"id": "saladillo-tts-07", "creds": "gcp_07.json", "quota": 0, "limit": 4_000_000},
    {"id": "saladillo-tts-08", "creds": "gcp_08.json", "quota": 0, "limit": 4_000_000},
    {"id": "saladillo-tts-09", "creds": "gcp_09.json", "quota": 0, "limit": 4_000_000},
    {"id": "saladillo-tts-10", "creds": "gcp_10.json", "quota": 0, "limit": 4_000_000},
]

CREDS_DIR = "/home/matias/saladillo-vivo-pro/gcp_credentials"


class GCPTTSRotator:
    def __init__(self, creds_dir: str = CREDS_DIR):
        self.projects = []
        self.clients = {}
        self.current_index = 0
        self.creds_dir = creds_dir
        self.initialized = False
        self._init_clients()
    
    def _init_clients(self):
        """Inicializa clientes si hay credenciales. No falla si no hay."""
        try:
            from google.oauth2 import service_account
            from google.cloud import texttospeech
        except ImportError:
            logger.warning("google-cloud-texttospeech no instalado. Rotador inactivo.")
            return
        
        loaded = 0
        for p in GCP_PROJECTS:
            creds_path = os.path.join(self.creds_dir, p["creds"])
            if not os.path.exists(creds_path):
                continue
            
            creds = service_account.Credentials.from_service_account_file(creds_path)
            client = texttospeech.TextToSpeechClient(credentials=creds)
            self.clients[p["id"]] = client
            self.projects.append({**p, "client": client})
            loaded += 1
            logger.info(f"✅ Cliente inicializado: {p['id']}")
        
        if loaded > 0:
            self.initialized = True
            logger.info(f"🎯 Rotador inicializado con {loaded} proyectos")
        else:
            logger.warning("⚠️ No hay credenciales GCP. El rotador está inactivo.")
    
    def _get_next_available(self) -> Optional[Tuple[object, dict]]:
        if not self.initialized:
            return None
        for _ in range(len(self.projects)):
            p = self.projects[self.current_index]
            self.current_index = (self.current_index + 1) % len(self.projects)
            if p["quota"] < p["limit"]:
                return p["client"], p
        return None
    
    def synthesize_ssml(self, ssml: str, voice_name: str = "es-AR-Neural2-A",
                        speaking_rate: float = 0.85, pitch: float = -2.0) -> bytes:
        if not self.initialized:
            raise RuntimeError("Rotador GCP no inicializado: no hay credenciales")
        
        result = self._get_next_available()
        if not result:
            raise RuntimeError("Todas las cuotas de Google TTS agotadas")
        
        client, project = result
        
        try:
            from google.cloud import texttospeech
        except ImportError:
            raise RuntimeError("google-cloud-texttospeech no instalado")
        
        synthesis_input = texttospeech.SynthesisInput(ssml=ssml)
        voice = texttospeech.VoiceSelectionParams(
            language_code="es-AR",
            name=voice_name,
            ssml_gender=texttospeech.SsmlVoiceGender.FEMALE,
        )
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            speaking_rate=speaking_rate,
            pitch=pitch,
            volume_gain_db=0.0,
        )
        
        try:
            response = client.synthesize_speech(
                input=synthesis_input,
                voice=voice,
                audio_config=audio_config,
            )
        except Exception as e:
            logger.error(f"Error en {project['id']}: {e}")
            project["quota"] = project["limit"]
            raise
        
        chars = len(ssml)
        project["quota"] += chars
        
        pct = project["quota"] / project["limit"] * 100
        logger.info(f"🎙️ {project['id']}: {chars:,} chars | "
                    f"Total: {project['quota']:,}/{project['limit']:,} ({pct:.1f}%)")
        
        time.sleep(random.uniform(1.5, 3.0))
        
        return response.audio_content
    
    def get_quota_status(self) -> dict:
        total_used = sum(p["quota"] for p in self.projects)
        total_limit = sum(p["limit"] for p in self.projects)
        return {
            "total_used": total_used,
            "total_limit": total_limit,
            "percentage": (total_used / total_limit * 100) if total_limit else 0,
            "projects": [
                {"id": p["id"], "used": p["quota"], "limit": p["limit"],
                 "pct": (p["quota"] / p["limit"] * 100) if p["limit"] else 0}
                for p in self.projects
            ]
        }


# Instancia global (inicialización perezosa: no falla sin credenciales)
tts_rotator = GCPTTSRotator()
