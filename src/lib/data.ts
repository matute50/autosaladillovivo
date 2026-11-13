import { supabase } from './supabaseClient';
import type { Article, Video, Interview, Banner, Ad, CalendarEvent, SupabaseArticle } from './types';

// Cached credentials to avoid repeated process.env reads
let _cachedCredentials: { supabaseUrl: string; supabaseAnonKey: string } | null = null;

// Helper to ensure Supabase credentials are set (cached)
function checkSupabaseCredentials() {
  if (_cachedCredentials) return _cachedCredentials;

  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || 'https://otwvfihzaznyjvjtkvvd.supabase.co';
  const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im90d3ZmaWh6YXpueWp2anRrdnZkIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDUxMDQ3OTAsImV4cCI6MjA2MDY4MDc5MH0.YbKdivZM6gJCdXAf51Xctn8IpKhQCrMch89NoHwP0Z4';

  if (!supabaseUrl || !supabaseAnonKey) {
    console.error('Supabase URL or Anon Key is not defined.');
    throw new Error('Supabase configuration is missing.');
  }
  _cachedCredentials = { supabaseUrl, supabaseAnonKey };
  return _cachedCredentials;
}

/**
 * Fetches articles from Supabase and categorizes them into featured and secondary.
 * - featuredNews: The most recent article with featureStatus = 'featured'.
 * - secondaryNews: All other articles, sorted by creation date.
 */
export async function getArticlesForHome(limitTotal: number = 25) {
  const { supabaseUrl, supabaseAnonKey } = checkSupabaseCredentials();
  const now = new Date();
  const fortyEightHoursAgo = new Date(now.getTime() - (48 * 60 * 60 * 1000)).toISOString();

  // Optimization: Fetch only necessary columns for the home rail. Exclude 'text' to save bandwidth.
  const apiUrl = `${supabaseUrl}/rest/v1/articles?select=id,title,image_url,featureStatus,updatedAt,created_at,slug,description,meta_title,meta_description,meta_keywords,published_at,audio_url,url_slide,animation_duration&or=(published_at.is.null,published_at.lte.${now.toISOString()})&created_at=gte.${fortyEightHoursAgo}&order=created_at.desc&limit=${limitTotal}`;

  try {
    const response = await fetch(apiUrl, {
      headers: {
        'apikey': supabaseAnonKey,
        'Authorization': `Bearer ${supabaseAnonKey}`,
      },
      next: { revalidate: 60 }
    });

    if (!response.ok) {
      console.error('Supabase fetch failed in getArticlesForHome. Status:', response.status, 'Text:', await response.text());
      return { featuredNews: null, secondaryNews: [], tertiaryNews: [], otherNews: [], allNews: [] };
    }
    const rawArticles = await response.json();
    if (!Array.isArray(rawArticles)) {
      console.error('Supabase response is not an array in getArticlesForHome:', rawArticles);
      return { featuredNews: null, secondaryNews: [], tertiaryNews: [], otherNews: [], allNews: [] };
    }
    const articles: SupabaseArticle[] = rawArticles as SupabaseArticle[];

    const processedNews = articles.map((item: SupabaseArticle): Article => ({
      id: item.id,
      titulo: item.title,
      slug: item.slug || item.id.toString(),
      description: item.description || 'Descripción no disponible.',
      resumen: item.description ? item.description.substring(0, 150) + (item.description.length > 150 ? '...' : '') : 'Resumen no disponible.',
      contenido: item.description || 'Contenido no disponible.',
      fecha: item.updatedAt ? new Date(item.updatedAt).toISOString() : (item.created_at ? new Date(item.created_at).toISOString() : new Date().toISOString()),
      created_at: item.created_at ? new Date(item.created_at).toISOString() : new Date().toISOString(),
      updatedAt: item.updatedAt ? new Date(item.updatedAt).toISOString() : (item.created_at ? new Date(item.created_at).toISOString() : new Date().toISOString()),
      autor: 'Equipo Editorial',
      categoria: item.featureStatus,
      imageUrl: item.image_url || 'https://saladillovivo.vercel.app/default-og-image.png',
      featureStatus: item.featureStatus,
      meta_title: item.meta_title,
      meta_description: item.meta_description,
      meta_keywords: item.meta_keywords,
      audio_url: item.audio_url,
      url_slide: item.url_slide,
      animation_duration: (item as any).animation_duration,
    }));

    // Clasificar noticias
    const featuredCandidates = processedNews.filter(news => news.featureStatus === 'featured');
    const secondaryNews = processedNews.filter(news => news.featureStatus === 'secondary');
    const tertiaryNews = processedNews.filter(news => news.featureStatus === 'tertiary');
    const otherNews = processedNews.filter(news => !news.featureStatus);

    let featuredNews: Article | null = null;

    // Asegurar que solo haya una noticia destacada
    if (featuredCandidates.length > 0) {
      // Ya vienen ordenadas por created_at.desc, así que la primera es la más nueva.
      featuredNews = featuredCandidates.shift()!;
      // Las demás 'featured' se convierten en 'secondary'
      secondaryNews.unshift(...featuredCandidates);
    } else if (processedNews.length > 0) {
      // Si no hay 'featured', la última generada (más reciente) es la destacada
      // processedNews ya viene ordenado por created_at DESC desde Supabase
      featuredNews = processedNews[0];
    }

    secondaryNews.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
    tertiaryNews.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());

    // Ordenar las "otras" noticias siguiendo la misma jerarquía (más nuevas primero)
    otherNews.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());

    // Filtrar la noticia destacada de las otras listas para evitar duplicados
    const allButFeatured = [...secondaryNews, ...tertiaryNews, ...otherNews].filter(n => n.id !== featuredNews?.id);


    return {
      featuredNews,
      secondaryNews: allButFeatured.filter(n => n.featureStatus === 'secondary' || featuredCandidates.some(fc => fc.id === n.id)),
      tertiaryNews: allButFeatured.filter(n => n.featureStatus === 'tertiary'),
      otherNews: allButFeatured.filter(n => !n.featureStatus),
      allNews: [featuredNews, ...allButFeatured].filter((n): n is Article => n !== null),
    };

  } catch (error) {
    console.error('Error in getArticlesForHome:', error);
    return { featuredNews: null, secondaryNews: [], tertiaryNews: [], otherNews: [], allNews: [] };
  }
}

/**
 * getVideosForHome — OPTIMIZADO v24.9
 * Usa la RPC `get_videos_prioritized` de Supabase para que el servidor aplique
 * toda la lógica de priorización (forzados → novedades → random).
 * Transfiere solo ~20 videos en lugar de 500, reduciendo el payload en ~96%.
 */
export async function getVideosForHome(limitRecent: number = 4) {
  try {
    const { data: videos, error } = await supabase
      .rpc('get_videos_prioritized', { p_limit: 20 });

    if (error || !videos) {
      console.error('Error en get_videos_prioritized RPC:', error);
      return { featuredVideo: null, recentVideos: [], allVideos: [], videoCategories: [] };
    }

    const allVideos: Video[] = (videos as any[]).map(v => ({
      ...v,
      id: String(v.id),
      createdAt: v.createdAt ? new Date(v.createdAt).toISOString() : new Date().toISOString(),
    }));

    const videoCategories = Array.from(new Set(allVideos
      .map(v => v.categoria)
      .filter((cat): cat is string => !!cat && cat !== 'NOVEDADES')))
      .sort();

    // featuredVideo: tier1 (forzado) > tier2 (novedad) > primero de la lista
    const featuredVideo = allVideos[0] || null;
    const recentVideos = allVideos.slice(1, 1 + limitRecent);

    return { featuredVideo, recentVideos, allVideos, videoCategories };

  } catch (error) {
    console.error('Error en getVideosForHome:', error);
    return { featuredVideo: null, recentVideos: [], allVideos: [], videoCategories: [] };
  }
}

/**
 * getVideosByCategory — NUEVO v24.9
 * Fetch bajo demanda de videos de una categoría específica.
 * Usa la RPC `get_videos_by_category` en Supabase con ILIKE para coincidencias flexibles.
 * Solo se llama cuando el usuario navega a esa categoría en el carrusel.
 *
 * @param category - Término de categoría parcial (ej: 'cortos', 'clips', 'SEMBRANDO')
 * @param limit    - Máximo de videos a devolver (default: 20)
 */
export async function getVideosByCategory(category: string, limit: number = 20): Promise<Video[]> {
  try {
    const { data, error } = await supabase
      .rpc('get_videos_by_category', { p_category: category, p_limit: limit });

    if (error || !data) {
      console.error(`Error en get_videos_by_category (${category}):`, error);
      return [];
    }

    return (data as any[]).map(v => ({
      ...v,
      id: String(v.id),
      createdAt: v.createdAt ? new Date(v.createdAt).toISOString() : new Date().toISOString(),
    }));

  } catch (error) {
    console.error(`Error en getVideosByCategory (${category}):`, error);
    return [];
  }
}

export async function getRandomVideo(): Promise<Video | null> {
  const { supabaseUrl, supabaseAnonKey } = checkSupabaseCredentials();
  const apiUrl = `${supabaseUrl}/rest/v1/rpc/get_random_video_excluding_sv`;

  try {
    const response = await fetch(apiUrl, {
      method: 'POST',
      headers: {
        'apikey': supabaseAnonKey,
        'Authorization': `Bearer ${supabaseAnonKey}`,
        'Content-Type': 'application/json'
      },
      next: { revalidate: 30 }
    });

    if (response.ok) {
      const data = await response.json();
      return data && data.length > 0 ? data[0] : null;
    }
  } catch (error) {
    console.error('Error fetching random video:', error);
  }
  return null;
}

export async function getNewRandomVideo(currentId?: string, currentCategory?: string): Promise<Video | null> {
  try {
    // 1. Base Query: Excluir estrictamente HCD (v25.2)
    const query = supabase
      .from('videos')
      .select('id, nombre, url, createdAt, categoria, imagen, novedad, forzar_video, volumen_extra')
      .not('categoria', 'ilike', '%HCD%');

    // 2. Intentar buscar videos de OTRA categoría (v25.2)
    let candidatesQuery = query;
    if (currentId) {
      candidatesQuery = candidatesQuery.neq('id', currentId);
    }

    if (currentCategory) {
      const { data: switchCategoryData, error: switchError } = await candidatesQuery
        .neq('categoria', currentCategory)
        .limit(50); // Pool amplio para aleatoriedad

      if (!switchError && switchCategoryData && switchCategoryData.length > 0) {
        return switchCategoryData[Math.floor(Math.random() * switchCategoryData.length)];
      }
    }

    // 3. Fallback: Cualquier video (excepto actual e HCD) si no hay otras categorías disponibles
    const { data: fallbackData, error: fallbackError } = await query
      .limit(20);

    if (fallbackError || !fallbackData || fallbackData.length === 0) return null;

    let finalCandidates = fallbackData.filter(v => v.id !== currentId);
    if (finalCandidates.length === 0) finalCandidates = fallbackData;

    return finalCandidates[Math.floor(Math.random() * finalCandidates.length)];
  } catch (error) {
    console.error('Error in getNewRandomVideo:', error);
    return null;
  }
}

/**
 * Obtiene un video musical aleatorio de la categoría "clips" (Saladillo Vivo).
 * Se usa tras el intro post-news para reproducir contenido musical local.
 */
export async function getRandomMusicalVideo(excludeId?: string): Promise<Video | null> {
  try {
    let query = supabase
      .from('videos')
      .select('id, nombre, url, createdAt, categoria, imagen, novedad, forzar_video, volumen_extra')
      .eq('categoria', 'clips');

    if (excludeId) {
      query = query.neq('id', excludeId);
    }

    const { data, error } = await query.limit(50);
    if (error || !data || data.length === 0) return null;

    // Normalizar id a string para consistencia con el resto del sistema (los IDs numéricos de Supabase)
    const item = data[Math.floor(Math.random() * data.length)];
    return {
      ...item,
      id: String(item.id),
      createdAt: item.createdAt ? new Date(item.createdAt).toISOString() : new Date().toISOString(),
    };
  } catch (error) {
    console.error('Error in getRandomMusicalVideo:', error);
    return null;
  }
}

export async function getTickerTexts(): Promise<string[]> {
  const { supabaseUrl, supabaseAnonKey } = checkSupabaseCredentials();
  const apiUrl = `${supabaseUrl}/rest/v1/textos_ticker?select=text,isActive&isActive=eq.true&order=createdAt.asc`;

  try {
    const response = await fetch(apiUrl, {
      headers: {
        'apikey': supabaseAnonKey,
        'Authorization': `Bearer ${supabaseAnonKey}`,
      },
      next: { revalidate: 60 }
    });

    if (response.ok) {
      const data = await response.json();
      if (data && data.length > 0) {
        return data.map((t: any) => t.text).filter(Boolean);
      }
    }
  } catch (error) {
    console.warn('Error fetching ticker texts:', error);
  }
  return ["Bienvenido a Saladillo Vivo - Manténgase informado."];
}

export async function getInterviews(): Promise<Interview[]> {
  const { supabaseUrl, supabaseAnonKey } = checkSupabaseCredentials();
  const apiUrl = `${supabaseUrl}/rest/v1/entrevistas?select=id,nombre,url,created_at,updated_at,categoria,imagen&order=created_at.desc`;

  try {
    const response = await fetch(apiUrl, {
      headers: {
        'apikey': supabaseAnonKey,
        'Authorization': `Bearer ${supabaseAnonKey}`,
      },
      next: { revalidate: 60 }
    });

    if (response.ok) {
      const data = await response.json();
      return (data || []).map((item: any): Interview => ({
        id: item.id,
        nombre: item.nombre,
        url: item.url,
        createdAt: item.created_at ? new Date(item.created_at).toISOString() : new Date().toISOString(),
        updatedAt: item.updated_at ? new Date(item.updated_at).toISOString() : (item.created_at ? new Date(item.created_at).toISOString() : new Date().toISOString()),
        categoria: item.categoria,
        imagen: item.imagen,
      }));
    }
  } catch (error) {
    console.error('Error fetching interviews:', error);
  }
  return [];
}

export async function getActiveBanners(): Promise<Banner[]> {
  const { supabaseUrl, supabaseAnonKey } = checkSupabaseCredentials();
  const apiUrl = `${supabaseUrl}/rest/v1/banner?select=id,imageUrl,nombre,isActive&isActive=eq.true&order=createdAt.desc`;

  try {
    const response = await fetch(apiUrl, {
      headers: {
        'apikey': supabaseAnonKey,
        'Authorization': `Bearer ${supabaseAnonKey}`,
      },
      next: { revalidate: 300 }
    });

    if (response.ok) {
      return await response.json();
    }
  } catch (error) {
    console.error('Error fetching banners:', error);
  }
  return [];
}

export async function getActiveAds(): Promise<Ad[]> {
  const { supabaseUrl, supabaseAnonKey } = checkSupabaseCredentials();
  const apiUrl = `${supabaseUrl}/rest/v1/anuncios?select=id,image_url,title,is_active,link_url&is_active=eq.true&order=created_at.desc`;

  try {
    const response = await fetch(apiUrl, {
      headers: {
        'apikey': supabaseAnonKey,
        'Authorization': `Bearer ${supabaseAnonKey}`,
      },
      next: { revalidate: 300 }
    });

    if (response.ok) {
      const dbAds = await response.json();
      return dbAds.map((ad: any) => ({
        id: ad.id,
        imageUrl: ad.image_url,
        name: ad.title,
        linkUrl: ad.link_url,
        isActive: ad.is_active,
      }));
    }
    return [];
  } catch (error) {
    console.error('Error fetching ads:', error);
    return [];
  }
}

export async function getCalendarEvents(): Promise<CalendarEvent[]> {
  const { supabaseUrl, supabaseAnonKey } = checkSupabaseCredentials();
  const apiUrl = `${supabaseUrl}/rest/v1/eventos?select=nombre,fecha,hora&order=fecha.asc,hora.asc`;

  try {
    const response = await fetch(apiUrl, {
      headers: {
        'apikey': supabaseAnonKey,
        'Authorization': `Bearer ${supabaseAnonKey}`,
      },
      next: { revalidate: 60 }
    });

    if (response.ok) {
      return await response.json();
    }
  } catch (error) {
    console.warn('Error fetching calendar events:', error);
  }
  return [];
}

export async function getArticles() {
  const { allNews } = await getArticlesForHome(100);

  const destacada = allNews.find(a => a.featureStatus === 'featured') || null;
  const noticias2 = allNews.filter(a => a.featureStatus === 'secondary');
  const noticias3 = allNews.filter(a => a.featureStatus === 'tertiary');
  const otrasNoticias = allNews.filter(a => !a.featureStatus);

  return {
    destacada,
    noticias2,
    noticias3,
    otrasNoticias,
    allNews,
  };
}

export async function getArticlesForRss(limit: number = 50): Promise<Article[]> {
  const { supabaseUrl, supabaseAnonKey } = checkSupabaseCredentials();
  const now = new Date();
  const fortyEightHoursAgo = new Date(now.getTime() - (48 * 60 * 60 * 1000)).toISOString();

  // CORRECCIÓN: Agregado 'animation_duration' también aquí por consistencia
  const apiUrl = `${supabaseUrl}/rest/v1/articles?select=id,title,text,image_url,featureStatus,updatedAt,created_at,slug,description,meta_title,meta_description,meta_keywords,published_at,audio_url,url_slide,animation_duration&or=(published_at.is.null,published_at.lte.${now.toISOString()})&created_at=gte.${fortyEightHoursAgo}&order=created_at.desc&limit=${limit}`;

  try {
    const response = await fetch(apiUrl, {
      headers: {
        'apikey': supabaseAnonKey,
        'Authorization': `Bearer ${supabaseAnonKey}`
      },
      next: { revalidate: 60 }
    });

    if (!response.ok) {
      console.error('Supabase fetch failed for RSS articles. Status:', response.status, 'Text:', await response.text());
      throw new Error(`Supabase fetch failed: ${response.statusText}`);
    }

    const articles: SupabaseArticle[] = await response.json();

    return articles.map((item: SupabaseArticle): Article => ({
      id: item.id,
      titulo: item.title,
      slug: item.slug || item.id.toString(),
      description: item.description || (item.text ? item.text.substring(0, 160) : 'Descripción no disponible.'),
      resumen: item.text ? item.text.substring(0, 150) + (item.text.length > 150 ? '...' : '') : 'Resumen no disponible.',
      contenido: item.text || 'Contenido no disponible.',
      fecha: item.updatedAt ? new Date(item.updatedAt).toISOString() : (item.created_at ? new Date(item.created_at).toISOString() : new Date().toISOString()),
      created_at: item.created_at ? new Date(item.created_at).toISOString() : new Date().toISOString(),
      updatedAt: item.updatedAt ? new Date(item.updatedAt).toISOString() : (item.created_at ? new Date(item.created_at).toISOString() : new Date().toISOString()),
      autor: 'Equipo Editorial',
      categoria: item.featureStatus,
      imageUrl: item.image_url || 'https://saladillovivo.vercel.app/default-og-image.png',
      featureStatus: item.featureStatus,
      meta_title: item.meta_title,
      meta_description: item.meta_description,
      meta_keywords: item.meta_keywords,
      audio_url: item.audio_url,
      url_slide: item.url_slide,
      animation_duration: (item as any).animation_duration,
    }));

  } catch (error) {
    console.error('Error in getArticlesForRss:', error);
    return [];
  }
}

export async function getVideos(): Promise<Video[]> {
  const { supabaseUrl, supabaseAnonKey } = checkSupabaseCredentials();
  const apiUrl = `${supabaseUrl}/rest/v1/videos?select=id,nombre,url,createdAt,categoria,imagen,novedad&order=createdAt.desc`;

  try {
    const response = await fetch(apiUrl, {
      headers: {
        'apikey': supabaseAnonKey,
        'Authorization': `Bearer ${supabaseAnonKey}`,
      },
      next: { revalidate: 60 }
    });

    if (response.ok) {
      const data = await response.json();
      return (data || []).map((item: any) => ({
        ...item,
        createdAt: item.createdAt ? new Date(item.createdAt).toISOString() : new Date().toISOString(),
      }));
    }
  } catch (error) {
    console.error('Error fetching videos:', error);
  }
  return [];
}

function filterSearchTerms(query: string): string {
  const stopWords = new Set([
    'el', 'la', 'los', 'las', 'un', 'una', 'y', 'o', 'pero', 'a', 'en', 'de', 'del', 'al',
    'por', 'para', 'con', 'buscar', 'encontrar', 'explorar', 'ver', 'video', 'videos'
  ]);

  const cleanedQuery = query
    .toLowerCase()
    .split(/\s+/)
    .filter(word => word.length > 1 && !stopWords.has(word))
    .join(' & ');

  return cleanedQuery;
}


export async function fetchVideosBySearch(searchTerm: string): Promise<Video[]> {
  const processedTerm = filterSearchTerms(searchTerm);

  if (!processedTerm) {
    return [];
  }

  const { supabaseUrl, supabaseAnonKey } = checkSupabaseCredentials();
  const apiUrl = `${supabaseUrl}/rest/v1/videos?select=id,nombre,url,createdAt,categoria,imagen,novedad&nombre=ilike.*${encodeURIComponent(searchTerm)}*`;

  try {
    const response = await fetch(apiUrl, {
      headers: {
        'apikey': supabaseAnonKey,
        'Authorization': `Bearer ${supabaseAnonKey}`,
      },
      next: { revalidate: 60 }
    });

    if (response.ok) {
      return await response.json();
    }
  } catch (error) {
    console.error('Error searching videos:', error);
  }

  return [];
}

export async function getVideoByUrl(url: string): Promise<Video | null> {
  const { data, error } = await supabase
    .from('videos')
    .select('id, nombre, url, createdAt, categoria, imagen, novedad, volumen_extra')
    .eq('url', url)
    .maybeSingle();

  if (error) {
    console.error('Error fetching video by URL:', error);
    return null;
  }
  return data;
}

export async function getVideoById(id: string): Promise<Video | null> {
  const { data, error } = await supabase
    .from('videos')
    .select('id, nombre, url, createdAt, categoria, imagen, novedad, volumen_extra')
    .eq('id', id)
    .maybeSingle();

  if (error) {
    console.error('Error fetching video by ID:', error);
    return null;
  }
  return data;
}

export async function getArticleById(id: string): Promise<Article | null> {
  const { data, error } = await supabase
    .from('articles')
    .select('id, title, image_url, featureStatus, updatedAt, created_at, slug, description, audio_url, url_slide, animation_duration')
    .eq('id', id)
    .maybeSingle();

  if (error) {
    console.error('Error fetching article by ID:', error);
    return null;
  }
  if (!data) return null;
  const item = data as any;
  return {
    id: item.id,
    titulo: item.title,
    slug: item.slug || item.id.toString(),
    description: item.description || '',
    resumen: item.description ? item.description.substring(0, 150) : '',
    contenido: item.description || '',
    fecha: item.updatedAt ? new Date(item.updatedAt).toISOString() : new Date().toISOString(),
    created_at: item.created_at ? new Date(item.created_at).toISOString() : new Date().toISOString(),
    updatedAt: item.updatedAt ? new Date(item.updatedAt).toISOString() : new Date().toISOString(),
    autor: 'Equipo Editorial',
    categoria: item.featureStatus,
    imageUrl: item.image_url || '',
    featureStatus: item.featureStatus,
    audio_url: item.audio_url,
    url_slide: item.url_slide,
    animation_duration: item.animation_duration,
  } as Article;
}
