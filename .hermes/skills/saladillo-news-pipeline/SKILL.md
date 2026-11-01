---
name: saladillo-news-pipeline
description: Pipeline automatizado de noticias locales para Saladillo Vivo Pro (Next.js 15 + Supabase). Extrae noticias de portales de Saladillo, las reescribe con modelos FREE con fallback, genera locución rioplatense (es-AR), slides cinemáticos con zoom suave y publica oficialmente en Supabase.
---

# Skill: Saladillo News Pipeline

## Contexto del Proyecto
- **Directorio Raíz**: `D:\GEMINI-CLI\SALADILLOVIVO_NEXT\saladillo-vivo-pro`
- **Plataforma**: Portal hiperlocal y canal de streaming de Saladillo (Buenos Aires, Argentina).
- **Backend**: Supabase (`articles`, buckets `audios` y `slides`).

## Directivas Editoriales y de Redacción
1. Fidelidad estricta a hechos, fechas, nombres propios y citas locales.
2. Título periodístico atractivo para lectores locales digitales.
3. Primer párrafo (lead) con los datos esenciales (qué, quién, cuándo, dónde).
4. Meta descripción SEO concisa (máximo 155 caracteres) y palabras clave con términos de Saladillo.

## Instrucciones de Ejecución

### 1. Ejecución de un Ciclo Completo (Scraping -> Redacción -> Audio -> Slide -> Publicación)
Ejecuta el siguiente comando en la terminal para procesar y publicar noticias:
```powershell
python D:\GEMINI-CLI\SALADILLOVIVO_NEXT\saladillo-vivo-pro\complete_automation.py --once --json-output
```

### 2. Parámetros Disponibles
- `--once` o `--single-run`: Corre una pasada completa y finaliza.
- `--limit N`: Límite máximo de artículos a extraer por cada portal de noticias (por defecto: 10).
- `--json-output`: Emite un objeto JSON en la última línea con el estado y resumen del ciclo.
- `--no-audio`: Desactiva la síntesis de locución.
- `--no-slides`: Desactiva la generación de diapositivas interactivas.

### 3. Auditoría y Logs
- Log general del pipeline: `D:\GEMINI-CLI\SALADILLOVIVO_NEXT\saladillo-vivo-pro\logs\automation.log`
- Resumen del último ciclo: `D:\GEMINI-CLI\SALADILLOVIVO_NEXT\saladillo-vivo-pro\data\cycle_summary.json`
