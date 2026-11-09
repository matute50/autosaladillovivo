"""
Rotador inteligente de 14 keys Gemini TTS (sin tarjeta, sin billing).
Round-robin con control de cuota diaria y fallback automático.

Keys: GEMINI_API_KEY_01.._14 en .env o .hermes/.env
Voz: gemini-2.5-flash-preview-tts con SOUL.md rioplatense.
"""
import os
import io
import time
import base64
import random
import logging
import wave
from typing import Optional, Tuple

logger = logging.getLogger("Gemini_TTS_Rotator")

# Voz Google para TTS rioplatense
GEMINI_VOICE = "Aoede"

# Cuota diaria por key (Gemini Free Tier ~15 RPM, generoso)
DAILY_LIMIT_REQUESTS = 1500


class GeminiTTSRotator:
    def __init__(self, env_keys=None):
        self.keys = []
        self.clients = {}
        self.current_index = 0
        self.usage = {}
        self._has_genai = True
        self._load_keys(env_keys)

    def _load_from_env(self):
        """Lee GEMINI_API_KEY_01.._14 desde entorno / .env / .hermes/.env.

        Prioridad por slot (gana la última fuente que tenga valor):
        variables de entorno < .hermes/.env < .env del proyecto.
        El .env del proyecto es la fuente de verdad: si existe, las
        variables de entorno se ignoran por completo (pueden contener
        keys viejas exportadas por una versión anterior de .hermes/.env,
        que llenarían slots que el usuario borró a propósito del .env).
        """
        project_env = "/home/matias/saladillo-vivo-pro/.env"
        env_keys = [""] * 14
        # 1) Menor prioridad: variables de entorno directas (solo si no hay .env de proyecto)
        if not os.path.exists(project_env):
            for i in range(1, 15):
                key = os.getenv(f"GEMINI_API_KEY_{i:02d}") or os.getenv(f"GEMINI_API_KEY_{i}")
                if key:
                    env_keys[i - 1] = key

        # 2) Overwrite con archivos: .hermes/.env primero, .env del proyecto al final (gana)
        for env_path in [
            "/home/matias/.hermes/.env",
            project_env,
        ]:
            if os.path.exists(env_path):
                with open(env_path) as f:
                    for line in f:
                        line = line.strip().strip("\r").strip()
                        if line.startswith("GEMINI_API_KEY_") and not line.startswith("#"):
                            var, _, val = line.partition("=")
                            idx_str = var.replace("GEMINI_API_KEY_", "").strip()
                            if idx_str.isdigit():
                                idx = int(idx_str)
                                if 1 <= idx <= 14:
                                    val = val.strip().strip("'\"")
                                    if val:
                                        env_keys[idx - 1] = val
        return env_keys

    def _load_keys(self, env_keys):
        """Carga las keys desde env: GEMINI_API_KEY_01.._14.

        Nota: se usa la API REST directamente (requests) en lugar del SDK
        google-genai, porque las claves nuevas formato AQ.Ab... no son
        soportadas por el SDK (lo trata como OAuth y devuelve 401
        ACCESS_TOKEN_TYPE_UNSUPPORTED). Via REST con ?key= funcionan.
        """
        try:
            import requests  # noqa: F401
            self._has_genai = True
        except ImportError:
            self._has_genai = False
            logger.warning("requests no instalado. Rotador inactivo.")
            return

        if env_keys is None:
            env_keys = self._load_from_env()

        for i, key in enumerate(env_keys):
            # Filtrar placeholders (no keys reales)
            # Google usa formato AIza... (clásico) o AQ.Ab... (OAuth nuevo)
            if not key or "AQUI" in key or "TU_KEY_GEMINI" in key:
                continue
            if not (key.startswith("AIza") or key.startswith("AQ.Ab")):
                logger.warning(f"Key {i+1} formato no reconocido: {key[:10]}...")
                continue
            self.clients[key] = True  # placeholder: sin clientes SDK
            self.keys.append(key)
            self.usage[key] = {"requests": 0, "day": ""}

        if self.keys:
            logger.info(f"✅ Rotador Gemini inicializado con {len(self.keys)} keys")
        else:
            logger.warning("⚠️ No hay keys Gemini válidas. Rotador inactivo.")

    def _reset_day_if_needed(self, key):
        """Resetea el contador diario si cambió el día."""
        today = time.strftime("%Y-%m-%d")
        if self.usage[key]["day"] != today:
            self.usage[key] = {"requests": 0, "day": today}

    def _get_next_available(self) -> Optional[Tuple[object, str]]:
        """Round-robin saltando keys sin cuota."""
        for _ in range(len(self.keys)):
            key = self.keys[self.current_index]
            self.current_index = (self.current_index + 1) % len(self.keys)

            self._reset_day_if_needed(key)
            if self.usage[key]["requests"] < DAILY_LIMIT_REQUESTS:
                return self.clients[key], key

        return None

    def synthesize(self, prompt: str) -> Optional[bytes]:
        """
        Sintetiza audio con Gemini TTS (API REST) usando rotación de keys.
        Recorre las keys round-robin: si una está desactivada (403/429) o
        falla, prueba con la siguiente antes de rendirse.
        Devuelve MP3 bytes o None.
        """
        if not self._has_genai or not self.keys:
            raise RuntimeError("Rotador Gemini no inicializado")

        for _ in range(len(self.keys)):
            result = self._get_next_available()
            if not result:
                break  # todas las keys sin cuota disponible
            _, key = result
            try:
                audio = self._synthesize_once(key, prompt)
            except Exception:
                audio = None
            if audio:
                return audio

        logger.warning("Gemini TTS: ninguna key disponible generó audio")
        return None

    def _synthesize_once(self, key: str, prompt: str) -> Optional[bytes]:
        """Un intento de síntesis con una key específica (REST)."""
        idx = self.keys.index(key) + 1

        try:
            import requests

            resp = requests.post(
                "https://generativelanguage.googleapis.com/v1beta/models/"
                f"gemini-2.5-flash-preview-tts:generateContent?key={key}",
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "responseModalities": ["AUDIO"],
                        "speechConfig": {
                            "voiceConfig": {
                                "prebuiltVoiceConfig": {"voiceName": GEMINI_VOICE}
                            }
                        },
                    },
                },
                timeout=90,
            )

            if resp.status_code == 429:
                # Cupo diario agotado: desactiva la key hasta mañana, prueba otra
                self.usage[key]["requests"] = DAILY_LIMIT_REQUESTS
                logger.warning(f"Gemini TTS key_{idx:02d}: cupo diario agotado (429)")
                return None
            if resp.status_code in (401, 402, 403):
                # Key inválida / sin free tier: desactivar por el resto del día
                self.usage[key]["requests"] = DAILY_LIMIT_REQUESTS
                logger.warning(
                    f"Gemini TTS key_{idx:02d}: desactivada (HTTP {resp.status_code})"
                )
                return None
            resp.raise_for_status()

            self.usage[key]["requests"] += 1

            data = resp.json()
            parts = data["candidates"][0]["content"]["parts"]
            for part in parts:
                inline = part.get("inlineData") or {}
                raw = inline.get("data")
                if raw:
                    pcm_bytes = self._extract_pcm(raw)
                    if pcm_bytes:
                        wav_bytes = self._pcm_to_wav(pcm_bytes, sample_rate=24000)
                        mp3_bytes = self._wav_to_mp3(wav_bytes)
                        logger.info(
                            f"🎙️ Gemini TTS key_{idx:02d}: {len(mp3_bytes)} bytes | "
                            f"reqs: {self.usage[key]['requests']}/{DAILY_LIMIT_REQUESTS}"
                        )
                        return mp3_bytes

            logger.error("Gemini TTS: no se recibió datos de audio")
            return None

        except Exception as e:
            logger.warning(f"Gemini TTS error en key_{idx:02d}: {e}")
            self.usage[key]["requests"] = DAILY_LIMIT_REQUESTS
            raise

    def _extract_pcm(self, raw) -> Optional[bytes]:
        """Convierte raw (str base64 o bytes) a PCM bytes."""
        if isinstance(raw, str):
            try:
                return base64.b64decode(raw)
            except Exception:
                return None
        elif isinstance(raw, bytes):
            try:
                return base64.b64decode(raw, validate=True)
            except Exception:
                return raw
        return None

    def _pcm_to_wav(self, pcm_bytes: bytes, sample_rate: int = 24000, channels: int = 1, sample_width: int = 2) -> bytes:
        """Envuelve PCM crudo en contenedor WAV."""
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, 'wb') as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(sample_width)
            wf.setframerate(sample_rate)
            wf.writeframes(pcm_bytes)
        wav_buffer.seek(0)
        return wav_buffer.read()

    def _wav_to_mp3(self, wav_bytes: bytes, bitrate: str = "128k") -> bytes:
        """Convierte WAV a MP3 usando ffmpeg."""
        try:
            import subprocess
            proc = subprocess.run(
                ['ffmpeg', '-y', '-i', 'pipe:0', '-c:a', 'libmp3lame', '-b:a', bitrate, '-f', 'mp3', 'pipe:1'],
                input=wav_bytes,
                capture_output=True,
                timeout=60
            )
            if proc.returncode == 0 and proc.stdout:
                return proc.stdout
            else:
                logger.warning(f"ffmpeg falló: {proc.stderr.decode()[:200]}")
                return wav_bytes
        except Exception as e:
            logger.warning(f"ffmpeg no disponible o error: {e}")
            return wav_bytes

    def get_status(self) -> dict:
        """Estado de uso de todas las keys."""
        today = time.strftime("%Y-%m-%d")
        keys_status = []
        for i, key in enumerate(self.keys):
            self._reset_day_if_needed(key)
            keys_status.append({
                "key": f"key_{i+1:02d}",
                "requests": self.usage[key]["requests"],
                "limit": DAILY_LIMIT_REQUESTS,
                "pct": (self.usage[key]["requests"] / DAILY_LIMIT_REQUESTS * 100)
            })
        return {"keys": keys_status, "day": today}


# Instancia global (inicialización perezosa: no falla sin keys)
tts_rotator = GeminiTTSRotator()
gemini_rotator = GeminiTTSRotator()
