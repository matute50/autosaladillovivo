"""
Procesador SOUL.md reutilizable.
Importa y reexporta funciones desde saladillo_tts_preprocessor.
"""
# Re-exportar desde el módulo existente
from saladillo_tts_preprocessor import preprocess_rioplatense, generate_audio

# Alias para compatibilidad
apply_rioplatense = preprocess_rioplatense

__all__ = ["apply_rioplatense", "generate_audio"]
