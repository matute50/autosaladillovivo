# Saladillo Vivo Pro — Documentación de Arquitectura y Especificación Técnica del Sistema (`scraping.md`)

> **Propósito de este documento**: Proveer un compendio exhaustivo y de nivel técnico de toda la plataforma **Saladillo Vivo** (Next.js 15, React 19, Supabase, TailwindCSS, Zustand). Este archivo sirve como base de conocimiento, fuente de verdad y contexto maestro para que un agente de Inteligencia Artificial (o desarrollador) pueda redactar prompts precisos, planificar refactorizaciones o programar futuras ampliaciones sin degradar las características críticas de la plataforma (reproducción "TV-Grade", anti-branding de YouTube, estado desacoplado y optimizaciones de base de datos).

---

## 1. Visión General del Proyecto

**Saladillo Vivo** es una plataforma de streaming temático y portal hiperlocal de noticias, cultura y eventos del partido de Saladillo (Buenos Aires, Argentina). La aplicación fusiona la experiencia de un portal de noticias digital moderno con un canal de televisión continuo ("TV-Grade Live Streaming"), ofreciendo emisión ininterrumpida de video, clips a demanda, noticias interactivas con locución y diapositivas multimedia (.html), agenda de eventos, pronóstico del tiempo y automatizaciones de redes sociales.

### Principios Fundamentales de Diseño
1. **Continuidad Televisiva ("TV-Grade Broadcast")**: La reproducción nunca debe mostrar cortes abruptos ("Zero-Black"), demoras perceptibles ni pantallazos de carga.
2. **Anti-Branding Cinematográfico**: Toda fuente externa de streaming (principalmente YouTube) debe ser enmascarada para eliminar logotipos, títulos nativos, marcas de agua, barras de controles y sugerencias de videos externos.
3. **Multi-Dispositivo Reactivo**: Adaptación de interfaz según el dispositivo y entorno (Desktop, Smart TV con control remoto, dispositivos móviles y PWA instalable).
4. **Rendimiento y Eficiencia de Red**: Consumo selectivo de datos en Supabase a través de vistas y Funciones Almacenadas (RPC), reduciendo cargas masivas de datos a payloads mínimos (< 5% del volumen bruto).

---

## 2. Stack Tecnológico

| Capa | Tecnologías / Librerías | Versión / Detalle |
| :--- | :--- | :--- |
| **Framework Web** | Next.js (App Router, Server Components & Server Actions) | `^15.0.0` |
| **Librería UI** | React / React DOM | `^19.0.0` |
| **Lenguaje** | TypeScript | `^5.0.0` (Strict mode) |
| **Estilos y CSS** | TailwindCSS, `tailwindcss-animate`, `postcss`, `clsx`, `tailwind-merge` | `3.4.17` |
| **Base de Datos & Backend** | Supabase (PostgreSQL, Row Level Security, RPCs, Storage, Auth) | `@supabase/supabase-js ^2.58.0` |
| **Gestión de Estado Global** | Zustand con middleware de `devtools` | `^5.0.11` |
| **Animaciones y Transiciones** | Framer Motion & GSAP | `framer-motion ^12.23.24`, `gsap ^3.14.2` |
| **Componentes Accesibles** | Radix UI (`@radix-ui/react-dialog`, `slider`, `progress`, `toast`, `slot`) | Primitivos Headless |
| **Reproductores Multimedia** | React-Player, Plyr, Plyr-react, HTML5 Video & Audio APIs | `react-player ^2.16.1`, `plyr ^3.8.3` |
| **Carruseles y Sliders** | Swiper | `swiper ^12.0.2` |
| **Iconografía** | Lucide React | `lucide-react ^0.544.0` |
| **Generación de Medios / OG** | `@vercel/og`, Sharp | `@vercel/og ^0.8.5`, `sharp ^0.34.4` |
| **Feeds y Sindicalización** | RSS, XML manual | `rss ^1.2.2` |
| **PWA & Offline** | Workbox, Service Workers | Generación en build |
| **Herramientas de Audio CLI** | Node.js, `yt-dlp`, FFmpeg (loudnorm), Deno | Script `normalize-loudness.js` |

---

## 3. Arquitectura de Rutas y Middleware

La aplicación corre sobre el **Next.js App Router** dentro del directorio `src/app`.

### 3.1. Enrutamiento y Middleware Dinámico (`middleware.ts`)
El middleware intercepta las peticiones evaluando el `User-Agent` del cliente y el subdominio objetivo:
- **Detección de Smart TV**: Agentes que contienen `TV|Large Screen|SmartTV|GoogleTV|AppleTV|HbbTV|CrKey|Tizen|WebOS`. Redirige a `https://tv.saladillovivo.com.ar`.
- **Detección Móvil**: Agentes `Android|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini` (excluyendo TV). Redirige a `https://m.saladillovivo.com.ar`.
- **Detección Desktop**: Dispositivos estándar de escritorio. Redirige a `https://www.saladillovivo.com.ar`.
- **Exclusiones del Matcher**: Archivos estáticos (`_next/static`, `_next/data`, `_next/image`, `favicon.ico`, imágenes, sitemaps y rutas `/api`).

### 3.2. Estructura de Páginas y Vistas
- **`/` (`src/app/page.tsx`)**:
  - Página de inicio (SSR con ISR `revalidate = 60`).
  - Obtiene en paralelo: noticias de portada (`getArticlesForHome`), videos priorizados (`getVideosForHome`), textos para el zócalo (`getTickerTexts`), entrevistas, anuncios publicitarios activos (`getActiveAds`), banners (`getActiveBanners`) y eventos del calendario (`getCalendarEvents`).
  - **Deep Linking**: Si la URL contiene `?v={id}` o `?url={videoUrl}`, busca dicho video y lo inyecta como elemento de máxima prioridad para su reproducción inmediata.
  - Entrega los datos al contenedor interactivo `ClientPageWrapper` / `ClientLayoutWrapper`.
- **`/noticia/[slug]` (`src/app/noticia/[slug]/page.tsx`)**:
  - Vista individual de noticia (`revalidate = 60`).
  - `generateMetadata`: Extrae título, descripción e imagen OpenGraph (`1200x628`) para previsualizaciones sociales dinámicas (Twitter/X, Facebook, WhatsApp).
  - Consulta a Supabase por `slug`. Si no existe, invoca `notFound()`.
  - Renderiza `NoticiaClient` con cuerpo de la nota, reproductor de audio adjunto (`audio_url`), imágenes y notas relacionadas.
- **`/categoria/[categoria]` (`src/app/categoria/[categoria]/page.tsx`)**:
  - Listado de noticias filtradas por estado o etiqueta temática.
  - Implementa `generateStaticParams` para pre-generar las categorías existentes.
  - Renderiza `CategoryPageClient`.
- **`/sitemap.xml`**: Mapa del sitio dinámico para motores de búsqueda.
- **`/rss.xml` (`src/app/rss.xml/route.ts`)**: Feed estándar RSS 2.0 de las últimas noticias para lectores de feeds.

### 3.3. Rutas de API y Endpoints de Automatización
- **`/api/check-stream` (`src/app/api/check-stream/route.ts`)**:
  - Verifica si una emisión en vivo está activa sin depender de la cuota de la YouTube Data API.
  - Para YouTube: Realiza un fetch con User-Agent emulado y escanea el contenido en busca de las señales `"isLive":true`, `"isLiveNow":true` o insignias de directo.
  - Para HLS (`.m3u8`): Comprueba que el archivo de lista de reproducción no contenga la etiqueta `#EXT-X-ENDLIST`.
  - Headers `Cache-Control: no-store` para garantizar estado en tiempo real.
- **`/api/revisar-noticias` (`src/app/api/revisar-noticias/route.ts`)**:
  - Tarea tipo Cron protegida por cabecera `Authorization: Bearer CRON_SECRET`.
  - Consulta en Supabase noticias listas para emitir (`is_published = false`, `publish_at <= now()`, con miniaturas generadas).
  - Despacha un payload Webhook a Make.com (para automatizar publicaciones en Instagram y Facebook con imágenes en proporciones 4:5 y 1.91:1).
  - Al recibir respuesta `200 OK`, actualiza la noticia a `is_published = true`.
- **`/feed/miniaturas` (`src/app/feed/miniaturas/route.ts`)**:
  - Feed Media RSS (`mrss`) generado bajo demanda (`dynamic = 'force-dynamic'`).
  - Formatea artículos programados con etiquetas `<media:content>` que incluyen dimensiones para Instagram (1080x1350) y Facebook (1200x628).
- **`/api/og` (`src/app/api/og/route.tsx`)**:
  - Generador dinámico de banners OpenGraph mediante la biblioteca `@vercel/og` y JSX sobre el Edge Runtime.
- **`/api/generate-image` (`src/app/api/generate-image/route.ts`)**:
  - Endpoint de procesamiento gráfico auxiliar para generación de artes y miniaturas.

---

## 4. Estructura de la Base de Datos (Supabase / PostgreSQL)

El proyecto almacena y consulta sus datos en Supabase con los siguientes esquemas de tablas y procedimientos almacenados (RPC).

### 4.1. Tablas del Sistema

#### 1. `articles` (Noticias y Contenido Editorial)
Representa las noticias periodísticas publicadas en la portada y en redes.
- `id` (`text` o `uuid`, Primary Key): Identificador único.
- `title` / `titulo` (`text`): Título periodístico de la nota.
- `slug` (`text`, Unique): Identificador amigable para URL (ej: `inauguracion-hospital-saladillovivo`).
- `description` (`text`): Bajada o copete de la noticia.
- `text` / `contenido` (`text`): Contenido completo de la noticia (puede incluir marcado HTML o texto plano).
- `image_url` / `imageUrl` (`text`): URL de la imagen principal de la nota.
- `featureStatus` (`text`, Nullable): Jerarquía editorial en la portada (`featured` = destacada principal, `secondary` = secundaria, `tertiary` = terciaria, o `null` = noticia estándar).
- `created_at` (`timestamp with time zone`): Fecha de creación del registro.
- `updatedAt` / `updated_at` (`timestamp with time zone`): Fecha de última modificación.
- `published_at` / `publish_at` (`timestamp with time zone`, Nullable): Fecha y hora programada de publicación.
- `is_published` (`boolean`, Default `false`): Bandera para indicar si ya fue difundida en redes sociales.
- `miniatura_url` (`text`, Nullable): Imagen en formato vertical 4:5 (1080x1350 px) optimizada para feed de Instagram.
- `og_image_url` (`text`, Nullable): Imagen en formato horizontal 1.91:1 (1200x628 px) para OpenGraph / Facebook.
- `audio_url` (`text`, Nullable): URL del archivo de audio con la locución o crónica radial de la noticia.
- `url_slide` (`text`, Nullable): URL a un archivo `.html` con diapositiva interactiva para ser reproducida en el reproductor de video.
- `animation_duration` (`numeric`, Nullable): Duración en segundos de la animación del slide interactivo.
- `meta_title`, `meta_description`, `meta_keywords` (`text`, Nullable): Campos para optimización en motores de búsqueda (SEO).
- `autor` (`text`, Default `'Equipo Editorial'`): Firma del periodista o redacción.
- `categoria` (`text`, Nullable): Rubro de la noticia (Sociedad, Política, Policiales, Cultura, Deportes, etc.).

#### 2. `videos` (Repositorio Audiovisual)
Almacena el catálogo de videos que alimentan la emisión continua y los carruseles temáticos.
- `id` (`bigint` o `text`, Primary Key): Identificador del video.
- `nombre` / `title` (`text`): Título descriptivo del video.
- `url` (`text`): URL del video (enlaces de YouTube, archivos MP4, HLS).
- `createdAt` (`timestamp with time zone`): Fecha de alta del video.
- `categoria` (`text`): Categoría asignada (ej: `SEMBRANDO FUTURO`, `FIERROS`, `HCD DE SALADILLO - Período 2025`, `clips`, `cortos`, `export`, etc.).
- `imagen` (`text`): URL de la miniatura o poster del video.
- `novedad` (`boolean`, Default `false`): Marca el video como contenido reciente (Tier 2).
- `forzar_video` (`boolean`, Default `false`): Fuerza que el video sea seleccionado obligatoriamente en la emisión inicial (Tier 1).
- `volumen_extra` (`numeric`, Default `1.0`): Multiplicador de audio normalizado (calculado vía LUFS con `normalize-loudness.js`) para equilibrar el volumen relativo de videos con audio bajo.
- `duration` (`numeric`, Nullable): Duración en segundos.

#### 3. `entrevistas` (Contenido de Mano a Mano y Testimonios)
- `id` (`text` / `uuid`, Primary Key).
- `nombre` (`text`): Título de la entrevista o entrevistado.
- `url` (`text`): Enlace al video de la entrevista.
- `imagen` (`text`): Miniatura de la entrevista.
- `categoria` (`text`): Rubro temático.
- `created_at`, `updated_at` (`timestamp with time zone`).

#### 4. `banner` & `anuncios` (Sistema Publicitario y Auspiciantes)
- **`banner`**:
  - `id` (`text` / `uuid`, Primary Key).
  - `imageUrl` (`text`): Gráfica del banner.
  - `nombre` (`text`): Nombre del auspiciante.
  - `isActive` (`boolean`): Estado de activación.
  - `createdAt` (`timestamp with time zone`).
- **`anuncios`**:
  - `id` (`text` / `uuid`, Primary Key).
  - `image_url` (`text`): Imagen del anuncio.
  - `title` (`text`): Título de la campaña.
  - `link_url` (`text`, Nullable): Destino del hipervínculo en caso de clic.
  - `is_active` (`boolean`): Interruptor de visibilidad comercial.
  - `created_at` (`timestamp with time zone`).

#### 5. `textos_ticker` (Zócalo de Noticias y Avisos en Pantalla)
- `id` (`text` / `uuid`, Primary Key).
- `text` (`text`): Texto del mensaje a desplegar en el cintillo inferior.
- `isActive` (`boolean`, Default `true`): Visibilidad del texto en rotación.
- `createdAt` (`timestamp with time zone`).

#### 6. `eventos` (Agenda Cultural y Comunitaria)
- `id` (`text` / `uuid`, Primary Key).
- `nombre` (`text`): Denominación del evento o festividad.
- `fecha` (`date` o `text`): Fecha del evento.
- `hora` (`text`): Horario de inicio.

---

### 4.2. Procedimientos Almacenados en PostgreSQL (RPCs)

Para optimizar al máximo la transferencia de datos y evitar que el cliente descargue cientos de registros por cada usuario, se implementaron funciones PostgreSQL en Supabase:

1. **`get_videos_prioritized(p_limit int)`**:
   - Devuelve los videos ordenados por capas jerárquicas:
     - **Tier 1**: Videos con `forzar_video = true`.
     - **Tier 2**: Videos marcados con `novedad = true`.
     - **Tier 3**: Videos aleatorios (`ORDER BY RANDOM()`).
   - Excluye categorías institucionales que no deben sonar en rotación común (como sesiones completas del `HCD de Saladillo`).
2. **`get_videos_by_category(p_category text, p_limit int)`**:
   - Permite cargar bajo demanda los videos de una categoría específica utilizando operadores `ILIKE` para emparejar etiquetas y variaciones de texto.
3. **`get_random_video_excluding_sv()`**:
   - Retorna un video al azar para alimentar la cola de reproducción automática cuando el video actual finaliza, garantizando variedad musical y cultural.

---

## 5. Arquitectura de Reproducción "TV-Grade" y Anti-Branding

La seña de identidad de Saladillo Vivo es su motor de reproducción multimedia con estándares de transmisión televisiva.

### 5.1. Sistema de Capas "Cinematic Shield" y Z-Index
YouTube impone elementos de interfaz no deseados (título, avatar de canal, botones de compartir, sugerencias al pausar). Para garantizar una experiencia de canal de televisión, se aplica la estrategia **Cinematic Shield**:
1. **Z-0 (`ReactPlayer` / YouTube iFrame)**: Escalado con sobremedida y contenedor sin eventos directos de cursor (`pointer-events-none`).
2. **Z-10 (`Cinematic Bars`)**: Franjas negras letterbox superiores e inferiores que tapan barras de progreso o textos nativos del player.
3. **Z-20 (`VideoTitleBar` / `CustomControls`)**: Controles propios desarrollados con Radix y Lucide React, desplegando tipografía institucional y metadata propia.
4. **Z-30 (`Intro Overlay / Pre-Roll Layer`)**: Videos breves institucionales (`/videos_intro/intro1.mp4` a `intro5.mp4` o placas de "Espacio Publicitario") que se colocan encima de la reproducción durante 3 segundos ("Safety Delay"). Mientras la intro se reproduce sobre el usuario, el iframe de YouTube de fondo inicia el buffering y los controles nativos desaparecen antes de que la intro se retire con un fade.

### 5.2. Transiciones Zero-Black ("Cover First, Swap Later")
- **Problema habitual**: Desmontar el player anterior causa un pantallazo negro visible de 1 a 2 segundos mientras el nuevo recurso se conecta.
- **Solución implementada**:
  - Al solicitar un cambio de video, la capa de transición (Intro o Slide) se despliega al 100% de opacidad sobre el video en curso.
  - El video saliente sigue reproduciéndose por debajo durante ~800 ms (**Safety Delay**).
  - Recién cuando la capa superior es totalmente opaca y sólida, se conmuta el contenido del reproductor subyacente.
  - Al concluir la transición, la capa superior realiza un Fade-Out de 0.75s revelando el nuevo contenido ya iniciado y fluido.

### 5.3. Noticias Interactivas (.html Slides) y Locución
Las noticias pueden ser emitidas como piezas televisivas animadas:
1. Si un artículo cuenta con `url_slide` (archivo que finaliza en `.html`), el `useNewsPlayerStore` dispara el slide.
2. El video de fondo se pausa automáticamente guardando su posición en segundos (`pauseForSlide`).
3. El slide se despliega en pantalla completa o sobre el contenedor de video.
4. Si la noticia posee `audio_url`, se reproduce en paralelo con un elemento `<audio>` sincronizado.
5. Al completarse la duración del slide o terminar el audio, el reproductor de video de fondo se reactiva de forma transparente (`resumeAfterSlide`).

### 5.4. Normalización de Volumen (LUFS & `volumen_extra`)
Debido a que los videos de YouTube poseen niveles dispares de sonoridad, el sistema cuenta con el campo `volumen_extra`:
- `1.0`: Ganancia nativa estándar.
- `> 1.0` (ej: `1.8`): Impulso para videos con mezcla de sonido baja.
- El script de mantenimiento `scripts/normalize-loudness.js` toma una categoría de referencia (`SEMBRANDO FUTURO`), extrae el audio con `yt-dlp` + Deno y mide el volumen integrado en LUFS mediante el filtro `loudnorm` de FFmpeg, persistiendo el multiplicador resultante en Supabase.
- En el cliente, `useVolumeStore` y `VideoPlayer.tsx` computan el volumen objetivo:  
  `TargetVolume = Math.min(1.0, GlobalVolume * (volumen_extra || 1.0))`.

---

## 6. Módulos y Secciones de la Plataforma

### 6.1. Cabecera y Navegación (`Header.tsx`)
- Logo de Saladillo Vivo y estado en tiempo real.
- Barra de búsqueda interactiva conectada a `useNewsStore`.
- Selector de modo: Modo Diario (Portal web tradicional) vs. Modo TV (pantalla limpia para smart TVs o proyectores).
- Control global de volumen y silenciado rápido (Mute/Unmute).

### 6.2. Sección Central de Video (`VideoSection.tsx`)
- Contenedor principal del reproductor de video con relación de aspecto cinematográfica.
- Integra las barras cinemáticas, el zócalo de noticias (`NewsTicker`), el widget meteorológico superpuesto (`WeatherOverlay`), y la capa `AntiGravityLayer`.
- Manejo de pantalla completa con la API estándar de Fullscreen del navegador.

### 6.3. Carrusel Dinámico y Categorías de Video (`CategoryCycler.tsx` / `ExclusiveVideoCarousel.tsx`)
Muestra el catálogo segmentado por programas y secciones temáticas:
- **`Sembrando Futuro`**: Producción agropecuaria, emprendimientos y desarrollo local.
- **`Gente de Acá`**: Historias de vida de habitantes y personajes destacados de Saladillo.
- **`Fierros de Saladillo`**: Automovilismo, talleres, karting y mecánica tradicional.
- **`ITEC "Augusto Cicaré"`**: Educación técnica e innovaciones del Instituto Tecnológico Cicaré.
- **`Saladillo Canta`**: Festivales musicales, recitales y folklore.
- **`Hacelo Corto`**: Cortometrajes y piezas audiovisuales breves.
- **`De Otros Tiempos`**: Archivo histórico y memorias de la ciudad.
- **`HCD de Saladillo`**: Sesiones del Honorable Concejo Deliberante (disponible en selección a demanda, excluida de la rotación aleatoria).
- **Mecanismo de Aleatoriedad Extrema (Fisher-Yates Shuffle)**: Al alternar entre categorías con las flechas o iniciar la app, se genera un nuevo `shuffleNonce` para que el orden de videos sea siempre impredecible y fresco.

### 6.4. Parrilla de Noticias (`NewsAndMostWatched.tsx`, `NewsColumn.tsx`, `MoreNewsGrid.tsx`)
- **Noticia Destacada (`featured`)**: Tarjeta principal con titular de alto impacto, bajada e imagen.
- **Noticias Secundarias y Terciarias**: Diseño en cuadrícula modular con tarjetas `NewsCard`.
- **Reproductor de Noticia en Video**: Botón "Play" directo sobre las tarjetas que transmuta el slide de la noticia al reproductor de video principal.
- **Modal de Detalle (`NewsDetailModal.tsx`)**: Lectura rápida en ventana modal sin abandonar la página de inicio.

### 6.5. Modo TV Dedicado (`TvModeLayout.tsx` & componentes `src/components/tv/`)
- Interfaz adaptada para pantallas grandes y Smart TVs (1080p / 4K).
- Desaparición de controles por inactividad: Si no se detecta movimiento de mouse o pulsaciones de teclado durante 1 segundo, la interfaz se oculta por completo, dejando únicamente el streaming.
- **Riel de Contenido TV (`TvContentRail.tsx`)**: Carrusel inferior semi-transparente optimizado para navegación con control remoto.
- **Widget del Clima en Pantalla (`WeatherOverlay.tsx`)**: Indicador de temperatura, humedad, viento y estado meteorológico de Saladillo provisto por el hook `useWeather`.

### 6.6. Banners Comerciales y Eventos (`AdsSection.tsx`, `BannerCarousel.tsx`)
- Rotación automática de banners institucionales y comerciales con enlaces directos a anunciantes.
- Agenda de eventos comunitarios, culturales y deportivos sincronizados con la tabla `eventos`.

---

## 7. Estado Global de la Aplicación (Zustand Stores)

Toda la reactividad del sistema está organizada en almacenes especializados en `src/store/`:

1. **`usePlayerStore`** (`src/store/usePlayerStore.ts`):
   - Controla el video en reproducción (`currentVideo`), video precargado (`nextVideo`), estado de reproducción (`isPlaying`), modo de vista (`diario` | `tv`).
   - Gestiona la superposición de intros (`isPreRollOverlayActive`, `overlayIntroVideo`).
   - Mantiene los estados de mutex (`activeContentId`) para prevenir que múltiples instancias de video reproduzcan simultáneamente.
   - Maneja la cola de reproducción aleatoria (`handleOnEnded`, `playNextVideoInQueue`, `playSpecificVideo`).
   - Pausa y reanudación por slides interactivos (`pauseForSlide`, `resumeAfterSlide`).
2. **`useNewsPlayerStore`** (`src/store/useNewsPlayerStore.ts`):
   - Controla las diapositivas interactivas (`currentSlide`: html, imagen o video).
   - Flag `isNewsIntroActive` para animar la transición visual de entrada y salida del slide de noticias.
   - Emite el audio locutado de la noticia.
3. **`useVolumeStore`** (`src/store/useVolumeStore.ts`):
   - Almacena el nivel global de volumen (`volume`: float entre 0 y 1).
   - Estado de silencio (`isMuted`).
   - Métodos `setVolume(v)`, `toggleMute()`, `unmute()`.
4. **`useNewsStore`** (`src/store/useNewsStore.ts`):
   - Maneja la barra de búsqueda general de noticias y videos.
   - Término de búsqueda, resultados filtrados, estado de carga (`searchLoading`) y apertura del buscador.
5. **`useWeatherUIStore`** (`src/store/useWeatherUIStore.ts`):
   - Estado de visualización y capas del módulo del clima.
6. **`useShieldModeStore`** (`src/store/useShieldModeStore.ts`):
   - Controla el modo blindado anti-branding y la visibilidad de barras negras cinemáticas.

---

## 8. Mapeo de Categorías de Video (`src/lib/categoryMappings.ts`)

Para mapear los nombres de la base de datos con los nombres visibles al público se utiliza la siguiente tabla de traducción:

| Etiqueta Visible (`display`) | Valor en Base de Datos (`dbCategory`) | Notas |
| :--- | :--- | :--- |
| **Novedades** | `__NOVEDADES__` | Filtrada y excluida de la navegación circular común |
| **HCD de Saladillo** | `'HCD DE SALADILLO - Período 2025'` | Oculta de rotación aleatoria por ser sesiones formales |
| **ITEC ¨Augusto Cicaré¨** | `['ITEC ¨AUGUSTO CICARE¨ SALADILLO', 'iteccicare', 'itec']` | Agrupa todas las variantes del instituto tecnológico |
| **Fierros de Saladillo** | `'FIERROS'` | Deporte motor y automovilismo |
| **Gente de Acá** | `'export'` | Entrevistas y perfiles biográficos |
| **Sembrando Futuro** | `'SEMBRANDO FUTURO'` | Agro, industria y economía rural |
| **De Otros Tiempos** | `['ARCHIVO SALADILLO VIVO', 'historia']` | Videos y fotos históricas digitalizadas |
| **Saladillo Canta** | `'clips'` | Música local y actuaciones en vivo |
| **Hacelo Corto** | `['cortos', 'Hacelo Corto']` | Producciones audiovisuales cortas |

---

## 9. Guía para Futuras Ampliaciones y Reglas para Prompts de IA

Cuando se redacten prompts para otra IA o se desarrollen nuevos módulos en este proyecto, se **deben** acatar las siguientes directivas técnicas:

### ⚠️ Reglas Inviolables ("Reglas de Oro")
1. **Nunca exponer los controles o marcas de YouTube**: Todo reproductor embebido de YouTube debe conservar las banderas `modestbranding=1`, `controls=0`, `rel=0` y mantenerse detrás de las capas de protección visual (`Cinematic Bars` y `AntiGravityLayer`).
2. **Respetar la Persistencia de Nodos (Node Persistence)**: No colocar atributos `key={video.id}` sobre los contenedores principales de video que obliguen a React a destruir y recrear el elemento `<video>` o iframe del DOM. Los cambios de video deben ocurrir reutilizando el nodo montado.
3. **No realizar consultas abiertas `SELECT *` sobre tablas de video o artículos**:
   - En la home, utilizar siempre la RPC `get_videos_prioritized` o consultas acotadas con `limit(20)`.
   - Excluir el campo de texto pesado `text` en listas y carruseles (descargar solo `id, title, slug, image_url, description`).
4. **Respetar el Mutex de Audio**:
   - Cuando entra un slide interactivo o una noticia con audio (`useNewsPlayerStore`), el reproductor de video de fondo debe ser pausado (`pauseForSlide`) o silenciado de forma estricta.
   - Al terminar el slide, restaurar la reproducción desde el segundo guardado (`savedProgress`) mediante `resumeAfterSlide`.
5. **No eliminar la exclusión de HCD en queries aleatorias**: La categoría `HCD de Saladillo` sólo debe ser accesible por click explícito del usuario en su carrusel, jamás debe insertarse automáticamente en la reproducción de entretenimiento general.
6. **Manejo de Hidratación en Next.js**: Componentes que lean variables de ventana (`window`, `localStorage`, `document.fullscreenElement`) deben implementar banderas de montaje (`isMounted`) o ser cargados dinámicamente con `dynamic(() => import(...), { ssr: false })` para evitar errores de hidratación entre servidor y cliente.

### 💡 Casos Típicos de Futuras Ampliaciones
- **Transmisiones en Vivo Planificadas**: Integración de un contador regresivo que consulte `/api/check-stream` y tome automáticamente el control del reproductor principal cuando comience una transmisión oficial en vivo.
- **Panel de Administración (Backoffice)**: Interfaz protegida para subir noticias, asignar tags de `featureStatus`, programar horarios de publicación (`publish_at`) y gestionar el zócalo de noticias sin necesidad de acceder a la consola de Supabase.
- **Módulo de Notificaciones Web Push**: Utilizar la infraestructura de Service Worker (`sw.js`) para alertar sobre noticias de última hora o eventos en vivo.
- **Mejoras del Widget de Clima**: Ampliación con alertas meteorológicas tempranas del SMN (Servicio Meteorológico Nacional).
