"""
Constructor de SSML semántico con reglas SOUL.md integradas.
Convierte texto plano → SSML optimizado para Google TTS Neural2.
"""
import re
import random
from typing import List

from constants.tts_tags import RIOP_LATENT_TAG

INSTITUTIONAL_CLOSINGS = [
    "En Saladillo Vivo. Dale play a la noticia.",
    "No lo leas, escuchálo, en Saladillo Vivo.",
    "Saladillo Vivo le pone voz a las noticias.",
    "Escuchá más, en Saladillo Vivo.",
    "Seguí escuchando, en Saladillo Vivo.",
    "La ciudad se escucha, en Saladillo Vivo.",
    "Enteráte escuchando, en Saladillo Vivo.",
    "Más info, en voz alta, en Saladillo Vivo.",
    "Saladillo Vivo. Menos textos, más audios.",
    "Cerrá los ojos, y escuchá Saladillo Vivo.",
]

# Alias por compatibilidad con código existente que referencie STYLE_TAG
STYLE_TAG = RIOP_LATENT_TAG


def apply_rioplatense_phonetics(text: str) -> str:
    """Aplica reglas fonéticas SOUL.md."""
    if not text:
        return ""
    
    text = re.sub(
        r'([aeiouáéíóúAEIOUÁÉÍÓÚ])s([aeiouáéíóúAEIOUÁÉÍÓÚ])',
        r'\1§S_INTERVOCALICA§\2',
        text,
        flags=re.IGNORECASE
    )
    
    text = re.sub(
        r's(?=[bcdfghjklmnñpqrstvwxyzBCDFGHJKLMNÑPQRSTVWXYZ])',
        'hs',
        text
    )

    text = re.sub(r's\b', 'hs', text)
    text = text.replace('§S_INTERVOCALICA§', 's')
    
    text = re.sub(r'\by\b', 'i', text, flags=re.IGNORECASE)
    text = re.sub(r'\by(?=[aeiouáéíóúAEIOUÁÉÍÓÚ])', 'sh', text, flags=re.IGNORECASE)
    text = re.sub(r'll', 'sh', text, flags=re.IGNORECASE)
    
    return text


def split_sentences(text: str) -> List[str]:
    """Divide texto en oraciones preservando puntuación."""
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    return [s for s in sentences if s]


def build_speech_text(article: dict) -> str:
    parts = []
    
    title = article.get("titulo_ia") or article.get("title") or ""
    if title:
        parts.append(title.strip())
    
    content = article.get("contenido_ia") or article.get("text") or ""
    if content:
        content = re.sub(r'<[^>]+>', ' ', content)
        content = re.sub(r'http\S+', '', content)
        content = re.sub(r'\s+', ' ', content).strip()
        if content:
            parts.append(content)
    
    closing = random.choice(INSTITUTIONAL_CLOSINGS)
    parts.append(closing)
    
    return ". ".join(parts)


def build_ssml(text: str, voice: str = "es-AR-Neural2-A") -> str:
    """Convierte texto procesado → SSML semántico para Google TTS Neural2."""
    processed = apply_rioplatense_phonetics(text)
    sentences = split_sentences(processed)
    
    ssml = f'<speak><voice name="{voice}">'
    ssml += '<prosody rate="0.85" pitch="-2st" volume="medium">'
    ssml += f'<emphasis level="none">{STYLE_TAG}</emphasis>'
    ssml += '<break time="200ms"/>'
    
    for i, sentence in enumerate(sentences):
        words = sentence.split()
        
        if len(words) > 5:
            base = ' '.join(words[:-3])
            emphasis = ' '.join(words[-3:])
            ssml += base + ' '
            ssml += f'<emphasis level="moderate">{emphasis}</emphasis>'
        else:
            ssml += sentence
        
        if i < len(sentences) - 1:
            if sentence.rstrip().endswith('.'):
                ssml += '<break time="500ms"/>'
            else:
                ssml += '<break time="300ms"/>'
    
    ssml += '</prosody></voice></speak>'
    return ssml
