import re
try:
    from utils.glossary_manager import apply_audio_glossary
except ImportError:
    apply_audio_glossary = lambda t: t

def preprocess_rioplatense(text: str) -> str:
    if not text:
        return ""

    # Aplicar glosario fonético antes de las transformaciones fonéticas
    processed = apply_audio_glossary(text)

    # Yeísmo / Sheísmo (ll → sh, y → sh), cubriendo mayúsculas iniciales
    # ("Llegó" → "Shegó", "Yuyo" → "Shuyo")
    processed = processed.replace('ll', 'sh').replace('Ll', 'Sh').replace('LL', 'SH')
    processed = re.sub(r'(?<![a-záéíóúüñ])y(?=[aeiou])', 'sh', processed)
    processed = re.sub(r'(?<![A-ZÁÉÍÓÚÜÑ])Y(?=[aeiouáéíóú])', 'Sh', processed)
    processed = re.sub(r'(?<![A-ZÁÉÍÓÚÜÑ])Y(?=[AEIOUÁÉÍÓÚ])', 'Sh', processed)

    # Aspiración suave de S en coda — con (?!h) para NO tocar el dígrafo 'sh' recién creado
    # Usamos 'hs' en vez de 'h' puro: preserva la fricción sibilante con aire,
    # evitando que la S suene completamente ausente o como una J gutural.
    # ("bosque" → "boshke", NUNCA "bohke")
    processed = re.sub(r's(?!h)(?=[bcdfghjklmnpqrstvwxyz])', 'hs', processed)
    processed = re.sub(r's(?=\s|$|[.,;:!?])', 'hs', processed)

    # Tag tonal obligatorio: se antepone AL FINAL, intacto (nunca se reescribe fonéticamente)
    processed = f"[relaxed, colloquial tone, argentinian rioplatense accent, mild s-aspiration] {processed}"
    return processed

from voxtral_tts import generate_audio_voxtral

def generate_audio(text: str, output_file: str) -> str:
    processed_text = preprocess_rioplatense(text)
    return generate_audio_voxtral(processed_text, output_file)
