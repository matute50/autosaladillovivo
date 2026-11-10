'use client';

import React from 'react';
import Image from 'next/image';
import { motion } from 'framer-motion';
import { Play } from 'lucide-react'; 
import { SlideMedia } from '@/lib/types';
import { format } from 'date-fns';
import { useNewsPlayerStore } from '@/store/useNewsPlayerStore';
import { cn, getHighResolutionImageUrl } from '@/lib/utils';
import { usePlayerStore } from '@/store/usePlayerStore';
import { useVolumeStore } from '@/store/useVolumeStore';

interface NewsCardProps {
  newsItem: any;
  index?: number;
  className?: string;
  isFeatured?: boolean;
}

const YOUTUBE_REGEX = new RegExp('(?:youtube\\.com\\/(?:[^/]+\\/.+\\/|(?:v|e(?:mbed)?)\\/|.*[?&]v=)|youtu\\.be\\/)([^"&?/\\s]{11})');

const NewsCard: React.FC<NewsCardProps> = ({ newsItem, index = 0, className = '', isFeatured = false }) => {
  const { playSlide } = useNewsPlayerStore();
  const { playTemporaryVideo } = usePlayerStore();
  const { setVolume } = useVolumeStore();

  if (!newsItem) return null;

  const rawTitle = newsItem.title || newsItem.titulo;
  // Limpieza común (pipes/barras/espacios dobles/comillas dobles y tipográficas) sin recorte de palabras
  const cleanFull = (t: string | null | undefined) =>
    (t || '').replace(/[\\|]/g, '').replace(/[¨"'“”‘’«»]/g, '').replace(/\s{2,}/g, ' ').trim().toUpperCase();

  const ganchoImagen = newsItem.titulo_gancho_imagen;
  // Tanto en noticia destacada como en tarjetas de la grilla se muestra el título COMPLETO.
  // El control visual seguro lo garantiza line-clamp-3 y la tipografía responsiva fluida (cqw).
  // Nunca recortar por conteo ciego de palabras, ya que amputa oraciones al medio.
  const title = cleanFull(rawTitle) || cleanFull(ganchoImagen);

  const finalImageUrl = getHighResolutionImageUrl(newsItem.image_url || newsItem.imageUrl);
  
  const createdAt = newsItem.created_at || newsItem.fecha;
  const audioUrl = newsItem.audio_url || newsItem.audioUrl;
  const urlSlide = newsItem.url_slide || newsItem.urlSlide;
  const duration = newsItem.animation_duration || 15;

  const hasSlide = !!urlSlide;
  const isHtmlSlide = hasSlide && (urlSlide.includes('.html') || urlSlide.includes('/slides/'));
  const hasAudioImage = !!finalImageUrl && !!audioUrl;
  const isPlayable = hasSlide || hasAudioImage;

  const scrollToPlayer = () => {
    if (typeof window !== 'undefined') {
      const playerEl = document.querySelector('.video-universe') || document.querySelector('[data-player-container]');
      if (playerEl) {
        playerEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
      } else {
        window.scrollTo({ top: 0, behavior: 'smooth' });
      }
    }
  };

  // Lógica para REPRODUCIR (Clic en toda la tarjeta con Presentación y Slide TV-Grade)
  const handlePlaySlide = (e: React.MouseEvent) => {
    e.preventDefault();
    
    // EXTRACCIÓN DE AUDIO
    const rawAudio = newsItem.audio_url || newsItem.audioUrl || newsItem.audioSourceUrl || newsItem.media_url || (newsItem.audio ? newsItem.audio.url : undefined);
    let finalAudioUrl: string | null = null;
    if (rawAudio) {
      const clean = rawAudio.trim();
      if (clean.startsWith('http')) {
        finalAudioUrl = clean;
      } else {
        const mediaUrl = process.env.NEXT_PUBLIC_MEDIA_URL || 'https://media.saladillovivo.com.ar';
        finalAudioUrl = `${mediaUrl}${clean.startsWith('/') ? '' : '/'}${clean}`;
      }
    }

    const slideDuration = Math.max(duration || 35, 35);

    // 1. Al dar play a una noticia, establecer el volumen al 70% (0.7) y desmutear
    setVolume(0.7);

    // 2. Si la noticia tiene slide interactivo HTML
    if (isHtmlSlide && urlSlide) {
      playSlide({
        url: urlSlide,
        type: 'html',
        duration: slideDuration,
        audioUrl: finalAudioUrl || audioUrl || null,
        title: title,
        embedsAudio: false
      });
      scrollToPlayer();
      return;
    }

    // 2. Si la noticia es imagen + audio o video
    let mediaData: SlideMedia = {
      id: newsItem.id.toString(),
      type: hasSlide ? 'video' : 'image',
      url: (hasSlide && !isHtmlSlide) ? urlSlide : "",
      imageSourceUrl: finalImageUrl,
      audioSourceUrl: finalAudioUrl || audioUrl,
      nombre: title,
      createdAt: createdAt,
      categoria: 'Noticias',
      imagen: finalImageUrl,
      novedad: true,
      duration: slideDuration
    };

    playTemporaryVideo(mediaData, 0.7, setVolume);
    scrollToPlayer();
  };

  const priority = index < 4;

  // Tipografía responsiva adaptativa según tipo de tarjeta y longitud del título para que aparezca completo sobre la imagen
  const getResponsiveTypography = (text: string, featured: boolean) => {
    const len = text.length;

    if (featured) {
      if (len > 100) {
        return {
          fontSize: 'clamp(0.85rem, 2.7cqw, 1.25rem)',
          lineHeight: '1.18',
          className: 'text-xs sm:text-sm md:text-base lg:text-lg',
        };
      } else if (len > 70) {
        return {
          fontSize: 'clamp(0.95rem, 3.3cqw, 1.5rem)',
          lineHeight: '1.2',
          className: 'text-sm sm:text-base md:text-lg lg:text-xl',
        };
      } else if (len > 40) {
        return {
          fontSize: 'clamp(1.1rem, 3.8cqw, 1.75rem)',
          lineHeight: '1.25',
          className: 'text-base sm:text-lg md:text-xl lg:text-2xl',
        };
      } else {
        return {
          fontSize: 'clamp(1.25rem, 4.5cqw, 2.25rem)',
          lineHeight: '1.25',
          className: 'text-lg sm:text-xl md:text-2xl lg:text-3xl',
        };
      }
    }

    // Tarjetas estándar (grid, carrusel, columnas)
    if (len > 100) {
      return {
        fontSize: 'clamp(0.68rem, 3.2cqw, 0.85rem)',
        lineHeight: '1.16',
        className: 'text-[10px] sm:text-[11px] md:text-xs',
      };
    } else if (len > 70) {
      return {
        fontSize: 'clamp(0.75rem, 3.6cqw, 0.95rem)',
        lineHeight: '1.18',
        className: 'text-[11px] sm:text-xs md:text-sm',
      };
    } else if (len > 40) {
      return {
        fontSize: 'clamp(0.82rem, 4.1cqw, 1.05rem)',
        lineHeight: '1.2',
        className: 'text-xs sm:text-sm md:text-base',
      };
    } else {
      return {
        fontSize: 'clamp(0.9rem, 4.6cqw, 1.15rem)',
        lineHeight: '1.25',
        className: 'text-sm sm:text-base md:text-lg',
      };
    }
  };

  const typography = getResponsiveTypography(title, isFeatured);

  return (
    <motion.article
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: index * 0.1 }}
      className={cn(
        "group relative flex flex-col rounded-xl overflow-hidden transition-all duration-300 h-full",
        "border-0 border-transparent shadow-none outline-none",
        "hover:scale-[1.02] hover:shadow-none",
        "cursor-pointer", 
        className
      )}
      onClick={handlePlaySlide} 
    >
      <div className="relative w-full h-full aspect-video overflow-hidden bg-black border-0 [container-type:inline-size]">
        <Image
          src={finalImageUrl}
          alt={title || 'Noticia'}
          fill
          className="object-cover transition-transform duration-700 group-hover:scale-110"
          priority={priority}
          unoptimized={true} 
          onError={(e) => { (e.target as HTMLImageElement).src = '/placeholder.jpg'; }}
        />
        {/* Viñeta Negra Intensificada sin blur sobre la imagen */}
        <div className="absolute inset-0 z-10 pointer-events-none bg-black/10 [mask-image:radial-gradient(circle,transparent_30%,black_100%)] shadow-[inset_0_0_100px_rgba(0,0,0,0.8)]" />
        <div className="absolute inset-x-0 top-0 h-[45%] bg-gradient-to-b from-black/95 via-black/50 to-transparent opacity-100 z-10 pointer-events-none" />
        <div className="absolute inset-0 bg-gradient-to-t from-black/95 via-black/60 to-transparent opacity-95 z-20 pointer-events-none" />

        {createdAt && (
          <div className="absolute top-3 left-3 z-30">
            <span className="bg-black/60 backdrop-blur-md text-white text-[9px] md:text-[11px] font-medium px-2 py-1 rounded shadow-sm">
                {format(new Date(createdAt), "dd/MM/yyyy")}
            </span>
          </div>
        )}

        {/* Contenedor de Botón Play y Título sobre la imagen */}
        <div className={cn(
          "absolute inset-x-0 bottom-0 z-30 flex flex-col items-center justify-end pointer-events-none",
          isFeatured ? "p-3 sm:p-4 md:p-5" : "p-2 sm:p-2.5 md:p-3"
        )}>
          {/* Botón Play: en noticia principal 25% más grande y 60px arriba del título */}
          <div className={cn(
            "flex items-center justify-center",
            isFeatured ? "mb-[60px]" : "mb-[20px]"
          )}>
            <div
              className={cn(
                "flex items-center justify-center rounded-full border border-white/80 shadow-2xl shadow-black/70 backdrop-blur-md bg-black/45 transition-all duration-300",
                "group-hover:bg-[#003399] group-hover:scale-110 group-hover:border-white",
                isFeatured
                  ? "w-[70px] h-[70px] sm:w-[80px] sm:h-[80px] group-hover:shadow-[0_0_40px_rgba(0,102,255,0.95),0_0_75px_rgba(0,153,255,0.65)]"
                  : "w-10 h-10 sm:w-11 sm:h-11 group-hover:shadow-[0_0_25px_rgba(0,102,255,0.75)]"
              )}
            >
              <Play
                size={isFeatured ? 35 : 20}
                fill="white"
                className="text-white drop-shadow-md translate-x-0.5"
                strokeWidth={1.5}
              />
            </div>
          </div>

          {/* Título: centrado, utilizando el ancho de la imagen, hasta 3 líneas */}
          <div className="w-full text-center">
            <h3
              style={{
                fontSize: typography.fontSize,
                lineHeight: typography.lineHeight
              }}
              className={cn(
                "font-bold text-white tracking-normal drop-shadow-[0_2px_3px_rgba(0,0,0,0.95)] group-hover:text-blue-200 transition-colors break-words text-center line-clamp-3",
                typography.className
              )}
            >
              {title}
            </h3>
          </div>
        </div>
      </div>
    </motion.article>
  );
};

export default NewsCard;