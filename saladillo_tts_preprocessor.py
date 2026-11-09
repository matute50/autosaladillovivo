import re

def preprocess_rioplatense(text: str) -> str:
    if not text:
        return ""

    processed = text

    # Yeísmo / Sheísmo (ll → sh, y → sh), cubriendo mayúsculas iniciales
    # ("Llegó" → "Shegó", "Yuyo" → "Shuyo")
    processed = processed.replace('ll', 'sh').replace('Ll', 'Sh').replace('LL', 'SH')
    processed = re.sub(r'(?<![a-záéíóúüñ])y(?=[aeiou])', 'sh', processed)
    processed = re.sub(r'(?<![A-ZÁÉÍÓÚÜÑ])Y(?=[aeiouáéíóú])', 'Sh', processed)
    processed = re.sub(r'(?<![A-ZÁÉÍÓÚÜÑ])Y(?=[AEIOUÁÉÍÓÚ])', 'Sh', processed)

    # Aspiración de S en coda — con (?!h) para NO tocar el dígrafo 'sh' recién creado
    # ("saladillo" → "saladisho", NUNCA "saladihho")
    processed = re.sub(r's(?!h)(?=[bcdfghjklmnpqrstvwxyz])', 'h', processed)
    processed = re.sub(r's(?=\s|$|[.,;:!?])', 'h', processed)

    # Tag tonal obligatorio: se antepone AL FINAL, intacto (nunca se reescribe fonéticamente)
    processed = f"[relaxed, colloquial tone, argentinian rioplatense accent, mild s-aspiration] {processed}"
    return processed

from voxtral_tts import generate_audio_voxtral

def generate_audio(text: str, output_file: str) -> str:
    processed_text = preprocess_rioplatense(text)
    return generate_audio_voxtral(processed_text, output_file)
