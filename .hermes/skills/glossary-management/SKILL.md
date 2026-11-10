---
name: glossary-management
description: Gestión dinámica del glosario de términos locales de Saladillo para corrección ortotipográfica en redacción periodística y adaptación fonética para el motor TTS de audio.
---

# Skill: Gestión del Glosario Local (Redacción y Audio)

## Contexto y Propósito
El glosario se almacena de forma persistente en `data/glossary.json` y es administrado por `utils/glossary_manager.py`.
Permite resolver dos necesidades críticas del ciclo de Saladillo Vivo:
1. **Redacción (`redaccion`)**: Corrección ortotipográfica de nombres propios, topónimos, instituciones locales y errores recurrentes de OCR/portales para que en la web y los slides se lean con la ortografía correcta (ej. `"Salomon"` ➜ `"Salomón"`, `"hcd"` ➜ `"HCD"`).
2. **Audio / Fonética (`audio`)**: Adaptación del guion antes de enviarlo a locución TTS (Voxtral / Elena) para que siglas, extranjerismos o términos locales suenen con pronunciación argentina natural y sin trabas mecánicas (ej. `"CES"` ➜ `"C-E-S"`, `"HCD"` ➜ `"Ache-Ce-De"`, `"Cicaré"` ➜ `"Sicaré"`).
3. **Global (`ambos`)**: Aplica tanto al texto visible como a la locución de audio.

---

## Protocolo de Interacción en el Chat con el Usuario

Cuando el usuario escriba en el chat una instrucción como:
> *"agregar palabra al glosario el nombre del club es APEADERO o UNION APEADERO"*
> *"agregar término al glosario..."*
> *"corregir en el glosario la pronunciación de..."*

Debes ejecutar los siguientes pasos:

### Paso 1: Análisis Semántico y Fonético
1. **Identificar la Entidad / Concepto**:
   - Comprender qué representa el término en el contexto hiperlocal de Saladillo (ej. club barrial o deportivo, funcionario público, paraje rural, cooperativa, empresa local).
2. **Determinar la Forma Canónica Escrita (`redaccion`)**:
   - Determinar la ortografía correcta y profesional (mayúsculas, tildes, puntuación). Ej: `"Unión Apeadero"`, `"Club Unión Apeadero"`, `"Apeadero"`.
   - Identificar posibles variantes erróneas o tipográficas comunes de los portales (ej: `"UNION APEADERRO"`, `"apeadero"`) y mapearlas a la forma correcta.
3. **Determinar la Transcripción Fonética (`audio`)**:
   - Analizar cómo el motor TTS lee la palabra y cómo debe transcribirse para que suene impecable en acento rioplatense (evitar que lea siglas como palabras continuas, colocar guiones en siglas si es necesario, o tildes fonéticas si el TTS acentúa mal).
   - Ejemplo: Para siglas como `"UDC"`, registrar `"U-De-Ce"`. Para un club o nombre compuesto claro como `"Unión Apeadero"`, verificar si el motor lo lee de forma fluida.

### Paso 2: Ejecución del Registro
Utiliza el script gestor por terminal:
```bash
python scripts/manage_glossary.py add "<termino_a_buscar>" "<reemplazo>" --target <redaccion|audio|ambos>
```
O edita directamente `data/glossary.json`.

Ejemplo para el Club Apeadero:
```bash
python scripts/manage_glossary.py add "UNION APEADERRO" "Unión Apeadero" --target redaccion
python scripts/manage_glossary.py add "apeadero" "Apeadero" --target redaccion
python scripts/manage_glossary.py add "Apeadero" "Apeadero" --target ambos
```

### Paso 3: Confirmación al Usuario
Responde explicando con claridad:
- Qué entidad o concepto registraste y qué significa.
- Cómo quedó registrado para la **redacción de textos** (artículo, título, slides).
- Cómo quedó registrado para la **locución de audio TTS** (para que suene correcto).

---

## Consulta Obligatoria en el Pipeline
Antes de procesar o publicar noticias:
- `AiRewriterAgent` aplica automáticamente `apply_text_glossary()` sobre títulos y contenido.
- `AudioGeneratorAgent` y `saladillo_tts_preprocessor` aplican automáticamente `apply_audio_glossary()` sobre el guion locutado.
- El archivo `data/glossary.json` se recarga en caliente ante cualquier modificación.
