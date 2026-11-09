import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export const slugify = (text: string | undefined | null, id: number | string): string => {
  if (!text) {
    text = ''; // Default to empty string if text is undefined or null
  }
  const a = 'àáâäæãåāăąçćčđďèéêëēėęěğǵḧîïíīįìłḿñńǹňôöòóœøōõőṕŕřßśšşșťțûüùúūǘůűųẃẍÿýžźż·/_,:;'
  const b = 'aaaaaaaaaacccddeeeeeeeegghiiiiiilmnnnnoooooooooprrssssssttuuuuuuuuuwxyyzzz------'
  const p = new RegExp(a.split('').join('|'), 'g')

  return text.toString().toLowerCase()
    .replace(/\s+/g, '-') // Replace spaces with -
    .replace(p, c => b.charAt(a.indexOf(c))) // Replace special characters
    .replace(/&/g, '-and-') // Replace & with 'and'

    // --- ARREGLO 1: Quitado el '\' de [^\w-]+ ---
    .replace(/[^\w-]+/g, '') // Remove all non-word chars

    // --- ARREGLO 2: Quitado el '\' de /--+/g ---
    .replace(/--+/g, '-') // Replace multiple - with single -

    .replace(/^-+/, '') // Trim - from start of text
    .replace(/-+$/, '') + '-' + id // Trim - from end of text and append id
}

export const formatDate = (dateString: string, format: 'short' | 'numeric' = 'numeric'): string => {
  if (!dateString) return 'Fecha no disponible';

  const options: Intl.DateTimeFormatOptions = {
    day: 'numeric',
    month: format === 'short' ? 'short' : 'numeric',
    year: format === 'short' ? 'numeric' : '2-digit',
  };

  try {
    return new Date(dateString).toLocaleDateString('es-ES', options);
  } catch (error) {
    console.error("Error al formatear fecha:", dateString, error);
    return 'Fecha inválida';
  }
};

export function isValidSlideUrl(url: string | null | undefined): url is string {

  if (!url) {

    return false;
  }
  const startsWithCorrectPrefix = url.startsWith('https://media.saladillovivo.com.ar/slides/');

  const includesWebm = url.includes('.webm');

  return startsWithCorrectPrefix && includesWebm;
}

export const isYouTubeVideo = (url: string) => {
  return url.includes('youtu.be/') || url.includes('youtube.com/');
};

export function shuffleArray<T>(array: T[]): T[] {
  const newArray = [...array];
  for (let i = newArray.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [newArray[i], newArray[j]] = [newArray[j], newArray[i]];
  }
  return newArray;
}

export const cleanTitle = (title: string | undefined | null): string => {
  if (!title) return '';
  // Elimina comillas de todo tipo y el carácter ¨ solicitado, además de pipes
  return title
    .replace(/[¨"'“”‘’«»|]/g, '')
    .trim()
    .split(' ')
    .slice(0, 8)
    .join(' ')
    .toUpperCase();
};

export const normalizeYoutubeUrl = (url: string | null | undefined): string => {
  if (!url) return '';
  
  // Clean potential corruption (v25.5 Guard)
  // If the url contains the prefix twice or starts with the corruption pattern
  if (url.includes('https://www.yhttps://www.youtube.com')) {
    url = url.replace('https://www.yhttps://www.youtube.com', 'https://www.youtube.com');
  }

  // Extraer ID de YouTube (soporta /watch?v=, /live/, youtu.be/)
  let videoId = '';
  
  try {
    const watchMatch = url.match(/[?&]v=([^&/?]+)/);
    if (watchMatch) videoId = watchMatch[1];
    
    if (!videoId) {
      const liveMatch = url.match(/\/live\/([^/?]+)/);
      if (liveMatch) videoId = liveMatch[1];
    }
    
    if (!videoId) {
      const shortMatch = url.match(/youtu\.be\/([^/?]+)/);
      if (shortMatch) videoId = shortMatch[1];
    }
    
    if (!videoId) {
      const embedMatch = url.match(/\/embed\/([^/?]+)/);
      if (embedMatch) videoId = embedMatch[1];
    }

    // Si encontramos un ID, reconstruimos la URL oficial de visualización
    if (videoId) {
      return `https://www.youtube.com/watch?v=${videoId}`;
    }
  } catch (e) {
    console.error("Error normalizing YouTube URL:", url, e);
  }

  return url; // Fallback al original si no se reconoce o hay error
};


export const getHighResolutionImageUrl = (inputUrl: string | undefined | null): string => {
  if (!inputUrl) return '/placeholder.png';
  let cleanUrl = inputUrl.trim();
  if (!cleanUrl) return '/placeholder.png';

  // Si es un enlace de YouTube, extraer miniatura en HQ
  const ytMatch = cleanUrl.match(/(?:youtube\.com\/(?:[^/]+\/.+\/|(?:v|e(?:mbed)?)\/|.*[?&]v=)|youtu\.be\/)([^"&?/\s]{11})/);
  if (ytMatch && ytMatch[1]) {
    return `https://img.youtube.com/vi/${ytMatch[1]}/hqdefault.jpg`;
  }

  // Eliminar sufijos de recorte automático de WordPress (-80x80, -150x150, -300x200, -768x..., etc.)
  cleanUrl = cleanUrl.replace(/-\d+x\d+(\.(?:webp|jpg|jpeg|png))(?:\?.*)?$/i, '$1');

  // Limpiar parámetros restrictivos de resize/fit de Jetpack/Photon (i0.wp.com, etc.)
  if (cleanUrl.includes('?') && (cleanUrl.includes('resize=') || cleanUrl.includes('fit='))) {
    const [basePart, queryPart] = cleanUrl.split('?');
    const keptParams = queryPart
      .split('&')
      .filter(p => !p.toLowerCase().startsWith('resize=') && !p.toLowerCase().startsWith('fit=') && !p.toLowerCase().startsWith('w=') && !p.toLowerCase().startsWith('h='));
    cleanUrl = keptParams.length > 0 ? `${basePart}?${keptParams.join('&')}` : basePart;
  }

  if (cleanUrl.startsWith('http://') || cleanUrl.startsWith('https://')) {
    return cleanUrl;
  }

  const mediaUrlFallback = process.env.NEXT_PUBLIC_MEDIA_URL || 'https://media.saladillovivo.com.ar';
  return `${mediaUrlFallback}${cleanUrl.startsWith('/') ? cleanUrl : `/${cleanUrl}`}`;
};
