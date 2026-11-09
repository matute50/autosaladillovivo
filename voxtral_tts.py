# freeLLMAPI TTS Integration — Local Voxtral Small (Docker 127.0.0.1:3001)
# Verificado 2026-11-03: POST /v1/audio/speech a freeLLMAPI local
# Modelo: "auto" (router elige Voxtral Small) + voces estilo OpenAI: nova, shimmer, alloy
# La respuesta viene como AUDIO BINARIO DIRECTO (MP3), no JSON base64.
import requests
import os


def _load_env_value(var_name: str) -> str:
    """Lee una variable del entorno; si falta, la busca en .env / .env.local del proyecto."""
    value = os.getenv(var_name)
    if value:
        return value
    base_dir = os.path.dirname(os.path.abspath(__file__))
    for filename in ('.env.local', '.env'):
        filepath = os.path.join(base_dir, filename)
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith(f'{var_name}='):
                            return line.split('=', 1)[1].strip().strip('\'"')
            except Exception:
                pass
    return ''


# freeLLMAPI local (Docker)
FREELLMAPI_API_KEY = _load_env_value('HERMES_CUSTOM_127_0_0_1_3001_API_KEY') or _load_env_value('FREELLMAPI_API_KEY')
FREELLMAPI_BASE_URL = _load_env_value('FREELLMAPI_BASE_URL') or 'http://127.0.0.1:3001/v1'
# Voces estilo OpenAI que funcionan en freeLLMAPI Voxtral
FREELLMAPI_VOICE = _load_env_value('FREELLMAPI_VOICE') or 'nova'   # nova, shimmer, alloy


def generate_audio_voxtral(text: str, output_file: str) -> str:
    if not FREELLMAPI_API_KEY:
        raise RuntimeError('FREELLMAPI_API_KEY / HERMES_CUSTOM_127_0_0_1_3001_API_KEY no configurada')
    headers = {
        'Authorization': f'Bearer {FREELLMAPI_API_KEY}',
        'Content-Type': 'application/json'
    }
    data = {
        'model': 'auto',           # Router elige Voxtral Small
        'input': text,
        'voice': FREELLMAPI_VOICE, # nova, shimmer, alloy
    }
    response = requests.post(
        f'{FREELLMAPI_BASE_URL}/audio/speech',
        headers=headers,
        json=data,
        timeout=180
    )
    response.raise_for_status()

    # freeLLMAPI devuelve AUDIO BINARIO DIRECTO (MP3), no JSON
    audio_bytes = response.content
    if len(audio_bytes) < 1000:
        raise RuntimeError(f'Audio freeLLMAPI sospechosamente pequeño: {len(audio_bytes)} bytes')

    with open(output_file, 'wb') as f:
        f.write(audio_bytes)
    return output_file
