'use client';

import React from 'react';
import Image from 'next/image';
import { motion } from 'framer-motion';
import { Play } from 'lucide-react'; 
import { SlideMedia } from '@/lib/types';
import { format } from 'date-fns';
import { useNewsPlayerStore } from '@/store/useNewsPlayerStore';
import { cn } from '@/lib/utils';
import { usePlayerStore } from '@/store/usePlayerStore';
import { useVolumeStore } from '@/store/useVolumeStore';

// 1. CORRECCIÓN CLAVE: Aseguramos que la interfaz acepte 'onCardClick'
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
  const title = rawTitle ? rawTitle.replace(/\|/g, '').replace(/\s{2,}/g, ' ').trim().toUpperCase() : '';

  
  const getProcessedImageUrl = (inputUrl: string | undefined | null): string => {
      if (!inputUrl) return '/placeholder.png';
      
      const cleanUrl = inputUrl.trim();
      const ytMatch = cleanUrl.match(YOUTUBE_REGEX);
      
      if (ytMatch && ytMatch[1]) {
          return `https://img.youtube.com/vi/${ytMatch[1]}/hqdefault.jpg`;
      }
      if (cleanUrl.startsWith('http://') || cleanUrl.startsWith('https://')) {
          return cleanUrl;
      }
      const mediaUrlFallback = process.env.NEXT_PUBLIC_MEDIA_URL || 'https://media.saladillovivo.com.ar';
      return `${mediaUrlFallback}${cleanUrl.startsWith('/') ? cleanUrl : `/${cleanUrl}`}`;
  };

  const finalImageUrl = getProcessedImageUrl(newsItem.image_url || newsItem.imageUrl);
  
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

    // 1. Si la noticia tiene slide interactivo HTML
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

    playTemporaryVideo(mediaData, undefined, setVolume);
    scrollToPlayer();
  };

  const priority = index < 4;
  const titleSizeClass = isFeatured ? 'text-2xl md:text-3xl' : 'text-base md:text-lg';

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
      <div className="relative w-full h-full aspect-video overflow-hidden bg-black border-0">
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
        <div className="absolute inset-x-0 top-0 h-[50%] bg-gradient-to-b from-black/95 via-black/50 to-transparent opacity-100 z-10 pointer-events-none" />
        <div className="absolute inset-0 bg-gradient-to-t from-black/95 via-black/40 to-transparent opacity-90 z-20" />

        {createdAt && (
          <div className="absolute top-3 left-3 z-30">
            <span className="bg-black/60 backdrop-blur-md text-white text-[9px] md:text-[11px] font-medium px-2 py-1 rounded shadow-sm">
                {format(new Date(createdAt), "dd/MM/yyyy")}
            </span>
          </div>
        )}

        <div className="absolute bottom-0 left-0 w-full p-4 pr-12 z-30"> {/* pr-12 para dejar espacio al icono play */}
            <h3 className={`font-bold ${titleSizeClass} text-white leading-tight drop-shadow-[0_2px_2px_rgba(0,0,0,0.8)] group-hover:text-blue-200 transition-colors line-clamp-3`}>
              {title}
            </h3>
        </div>

        {/* Indicador de Play sutil en esquina inferior derecha */}
        {isPlayable && (
            <div className={cn(
                "absolute bottom-2 right-2 flex items-center justify-center rounded-full p-0.5 border border-white/70 shadow-lg shadow-black/50 backdrop-blur-md bg-black/40 group-hover:!bg-[#003399] group-hover:border-white group-hover:bg-opacity-100 z-30",
                isFeatured ? "w-11 h-11" : "w-8 h-8"
            )}>
                 <Play
                    size={isFeatured ? 25 : 18}
                    fill="white"
                    className="text-white drop-shadow-lg"
                    strokeWidth={1.35}
                 />
            </div>
        )}
      </div>

    </motion.article>
  );
};

export default NewsCard;
