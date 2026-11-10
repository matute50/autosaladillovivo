'use client';

import React, { useRef, useState } from 'react';
import Image from 'next/image';
import { motion } from 'framer-motion';
import { Swiper, SwiperSlide } from 'swiper/react';
import { Navigation } from 'swiper/modules';
import { ChevronLeft, ChevronRight } from 'lucide-react';

import { usePlayerStore } from '@/store/usePlayerStore';
import { useVolumeStore } from '@/store/useVolumeStore';
import { useThemeButtonColors } from '@/hooks/useThemeButtonColors';
import { useToast } from '@/components/ui/use-toast';
import { cn } from '@/lib/utils';
import { Video, ExclusiveVideoCarouselProps } from '@/lib/types';

const ExclusiveVideoCarousel: React.FC<ExclusiveVideoCarouselProps> = ({ videos, isLoading, carouselId, isLive = false, onVideoClick }) => {
  const { playSpecificVideo, playLiveStream, streamStatus } = usePlayerStore();
  const { setVolume } = useVolumeStore();
  const { toast } = useToast();
  const swiperRef = useRef(null);
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);
  const { buttonColor, buttonBorderColor } = useThemeButtonColors();


  const getYoutubeThumbnail = (video: Video): string => {
    if (!video) return 'https://via.placeholder.com/320x180.png?text=No+disponible';

    const youTubeRegex = /(?:https?:\/\/)?(?:www\.)?(?:youtube\.com\/(?:watch\?v=|embed\/|v\/|live\/)|youtu\.be\/)([a-zA-Z0-9_-]{11})/;

    // Prioridad: Extraer del video.url si es link de YouTube
    if (video.url) {
      const videoIdMatch = video.url.match(youTubeRegex);
      if (videoIdMatch) {
        return `https://img.youtube.com/vi/${videoIdMatch[1]}/hqdefault.jpg`;
      }
    }

    // Procesar video.imagen
    const cleanImageUrl = (video.imagen || '').trim();

    if (!cleanImageUrl) {
      return 'https://via.placeholder.com/320x180.png?text=Miniatura';
    }

    // Si video.imagen es URL de YouTube, extraer miniatura
    if (cleanImageUrl.includes('youtube.com') || cleanImageUrl.includes('youtu.be')) {
      const videoIdMatch = cleanImageUrl.match(youTubeRegex);
      if (videoIdMatch) {
        return `https://img.youtube.com/vi/${videoIdMatch[1]}/mqdefault.jpg`;
      }
    }

    // Si es absoluta, usarla tal cual
    if (cleanImageUrl.match(/^(http|https):\/\//)) {
      return cleanImageUrl;
    }

    // CORRECCIÓN DE BUG: 'cleanUrl' no existía, debía ser 'cleanImageUrl'
    const mediaUrl = process.env.NEXT_PUBLIC_MEDIA_URL || 'https://media.saladillovivo.com.ar';
    return `${mediaUrl}${cleanImageUrl.startsWith('/') ? '' : '/'}${cleanImageUrl}`;
  };

  const handleVideoClick = (video: Video) => {
    if (onVideoClick) {
      onVideoClick(video);
      return;
    }

    if (isLive || video.isLiveThumbnail) {
      if (streamStatus) {
        playLiveStream(streamStatus);
      }
    } else if (video.isEvent) {
      toast({
        title: "Próximo Evento",
        description: "Este es un evento futuro. ¡Vuelve pronto para verlo en vivo!",
      });
    } else {
      playSpecificVideo(video as any, undefined, setVolume);
    }
  };

  if (isLoading) {
    return <div className="relative w-full flex items-center justify-center min-h-[126px] bg-muted/50 animate-pulse rounded-lg"></div>;
  }

  if (!videos || videos.length === 0) {
    return <div className="relative w-full flex items-center justify-center min-h-[126px] text-muted-foreground rounded-lg bg-muted/20">No hay contenido disponible.</div>;
  }



  return (
    <div className="relative w-full flex items-center justify-center rounded-xl p-4">
      <Swiper
        ref={swiperRef}
        slidesPerView={'auto'}
        centeredSlides={true}
        initialSlide={videos.length > 1 ? 1 : 0}
        spaceBetween={10}
        loop={videos.length > 5}
        navigation={{
          prevEl: `#prev-${carouselId}`,
          nextEl: `#next-${carouselId}`,
        }}
        modules={[Navigation]}
      >
        {videos.map((video, index) => {
          const isLiveOrEvent = isLive || video.isLiveThumbnail || video.isEvent;

          const slideClasses = "transition-all duration-300 ease-in-out opacity-100 blur-none";
          const titleOverlayClasses = "absolute inset-0 p-2 bg-gradient-to-t from-black/80 to-transparent flex justify-center items-end text-center opacity-100 z-30 transition-opacity duration-300 ease-in-out";

          // La lógica de clase para slideClasses y titleOverlayClasses se ha simplificado
          // para que siempre estén visibles y sin blur/opacidad dinámica para el fondo y título.
          // El z-index ya se gestiona en titleOverlayClasses.
          if (videos.length === 2) {
            const isActiveByHover = (hoveredIndex === null && index === 0) || hoveredIndex === index;
            if (isActiveByHover) {
              // No es necesario añadir z-20 aquí si ya está en titleOverlayClasses
            } else {
              // No es necesario opacity-0 aquí
            }
          } else {
            // No es necesario opacity-0 o z-20 aquí
          }

          const thumbUrl = getYoutubeThumbnail(video);
          // DETECCIÓN DE YOUTUBE PARA EVITAR ERROR 402
          const isYouTube = thumbUrl.includes('youtube.com') || thumbUrl.includes('ytimg.com');

          return (
            <SwiperSlide
              key={video.id || video.url}
              style={{ width: 'auto' }}
              className={slideClasses}
              onMouseEnter={() => videos.length === 2 && setHoveredIndex(index)}
              onMouseLeave={() => videos.length === 2 && setHoveredIndex(null)}
            >
              <div
                onClick={() => handleVideoClick(video)}
                className="relative cursor-pointer group rounded-xl overflow-hidden shadow-lg dark:shadow-none hover:shadow-2xl transition-all duration-300 ease-in-out"
              >
                <div className="relative w-56 aspect-video flex items-center justify-center bg-black">
                  <Image
                    src={thumbUrl}
                    alt={video.nombre || "Miniatura de video"}
                    fill
                    sizes="(max-width: 768px) 100vw, (max-width: 1200px) 50vw, 33vw"
                    priority={index === 0}
                    className={`${isLiveOrEvent ? 'object-contain' : 'object-cover'} transition-transform duration-300 group-hover:scale-110`}
                    // LA SOLUCIÓN MÁGICA:
                    unoptimized={isYouTube}
                    onError={(e) => { (e.target as HTMLImageElement).src = '/placeholder.jpg'; }}
                  />
                </div>
                <div className="absolute inset-x-0 bottom-0 h-1/2 z-[15] pointer-events-none" 
                  style={{ 
                    maskImage: 'linear-gradient(to top, black 20%, transparent 100%)',
                    WebkitMaskImage: 'linear-gradient(to top, black 20%, transparent 100%)'
                  }} 
                />
                <div className={titleOverlayClasses}>
                  <p className={cn(
                    "text-white font-thin uppercase leading-tight break-words line-clamp-2 text-center",
                    (video.nombre || '').length > 70 ? "text-[10px]" : ((video.nombre || '').length > 40 ? "text-[11px]" : "text-xs")
                  )}>{video.nombre}</p>
                </div>
              </div>
            </SwiperSlide>
          );
        })}
      </Swiper>
      <>
        <motion.button
          id={`prev-${carouselId}`}
          className="carousel-nav-button absolute top-1/2 -translate-y-1/2 left-0 z-20 rounded-md p-1 cursor-pointer border shadow-lg shadow-black/50 backdrop-blur-md"
          animate={{ color: buttonColor, borderColor: buttonBorderColor, backgroundColor: 'rgba(0, 0, 0, 0.4)' }}
          whileHover={{ backgroundColor: '#012078' }}
          transition={{ duration: 0.3, ease: 'easeInOut' }}
        >
          <ChevronLeft size={30} />
        </motion.button>
        <motion.button
          id={`next-${carouselId}`}
          className="carousel-nav-button absolute top-1/2 -translate-y-1/2 right-0 z-20 rounded-md p-1 cursor-pointer border shadow-lg shadow-black/50 backdrop-blur-md"
          animate={{ color: buttonColor, borderColor: buttonColor, backgroundColor: 'rgba(0, 0, 0, 0.4)' }}
          whileHover={{ backgroundColor: '#012078' }}
          transition={{ duration: 0.3, ease: 'easeInOut' }}
        >
          <ChevronRight size={30} />
        </motion.button>
      </>
    </div>
  );
};

export default ExclusiveVideoCarousel;
