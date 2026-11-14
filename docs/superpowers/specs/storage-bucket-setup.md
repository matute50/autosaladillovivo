# Bucket de Storage: `video-factory-assets`

## Creación del Bucket

Ir a **Supabase Dashboard → Storage → New Bucket** con la configuración:

| Campo | Valor |
|-------|-------|
| Name | `video-factory-assets` |
| Public bucket | ✅ Sí (las ubicaciones y videos finales deben ser accesibles públicamente) |
| File size limit | 500 MB |
| Allowed MIME types | `image/*`, `video/mp4`, `video/webm` |

## Estructura de Carpetas

El bucket usa las siguientes carpetas (los paths se definen en el código como constantes):

```
video-factory-assets/
├── locations/          # Fotos y videos de fondo (por presenter_id opcional)
│   └── {id}/           # Subcarpeta por locación (opcional, para organización)
├── master-images/      # Imágenes maestras generadas por Flow/Veo
│   └── {job_id}.png    # Por job de video
└── final-videos/       # Videos finales renderizados
    └── {job_id}_final.mp4
```

## Reglas de Nombrado

- Las ubicaciones se suben con UUID como key: `locations/{uuid}.jpg` o `locations/{uuid}.mp4`
- Las imágenes maestras: `master-images/{ara_video_jobs_id}.png`
- Los videos finales: `final-videos/{ara_video_jobs_id}_final.mp4`

## Políticas de Acceso

Como es un bucket público:
- Lectura pública: cualquier URL directa es accesible
- Escritura: requiere autenticación via Supabase Edge Functions o server-side con service role key

## Uso desde el Frontend

Las URLs públicas se construyen así:
```
https://otwvfihzaznyjvjtkvvd.supabase.co/storage/v1/object/public/video-factory-assets/{path}
```

Ejemplo:
```
https://otwvfihzaznyjvjtkvvd.supabase.co/storage/v1/object/public/video-factory-assets/locations/e4a3b2c1-d8f7-4e6a-9b1c-2d3e4f5a6b7c.jpg
```
