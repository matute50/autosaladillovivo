'use client';

import { motion } from "framer-motion";


import React, { useState, useCallback, useEffect, useMemo } from 'react';
import { useNewsStore } from '@/store/useNewsStore';
import { usePlayerStore } from '@/store/usePlayerStore';
import { useNewsPlayerStore } from '@/store/useNewsPlayerStore';
import { useVolumeStore } from '@/store/useVolumeStore';
import CategoryCycler from '@/components/layout/CategoryCycler';
import { Video, Article } from '@/lib/types';
import { categoryMappings, type CategoryMapping } from '@/lib/categoryMappings';
import { cleanTitle, shuffleArray } from '@/lib/utils';

const TRANSPARENT_PNG_DATA_URI = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=';

interface TvContentRailProps {
  searchResults: Video[];
  isSearching: boolean;
  searchLoading: boolean;
  initialCategory?: CategoryMapping; // Nuevo prop para la categoría inicial
  isVisible?: boolean; // Nuevo prop para controlar la visibilidad
  onVideoSelect?: () => void; // Callback cuando se elige un video
}

const TvContentRail: React.FC<TvContentRailProps> = ({ searchResults, isSearching, searchLoading, initialCategory, isVisible = true, onVideoSelect }) => {
  const { galleryVideos, allNews, isLoading: isLoadingNews } = useNewsStore();
  const { playSpecificVideo, playTemporaryVideo } = usePlayerStore();
  const { playSlide } = useNewsPlayerStore();
  const { volume, setVolume } = useVolumeStore();

  const [categoryIndex, setCategoryIndex] = useState(0);
  const [shuffleNonce, setShuffleNonce] = useState(0); // v26.1: Forzar reshuffle en cada elección

  const availableCategoryMappings = useMemo(() => {
    if (isLoadingNews) return [];

    return categoryMappings.filter(category => {
      // Excluir explícitamente "Noticias (Slides)" y "Novedades" (Request v26)
      if (category.display === 'Noticias (Slides)') return false;
      if (category.dbCategory === '__NOVEDADES__') return false;

      const targetCategories = Array.isArray(category.dbCategory)
        ? category.dbCategory.map(c => c.trim().toLowerCase())
        : [category.dbCategory.trim().toLowerCase()];

      return galleryVideos.some(video => {
        const videoCat = (video.categoria || '').trim().toLowerCase();
        return targetCategories.includes(videoCat);
      });
    });
  }, [galleryVideos, allNews, isLoadingNews]);

  useEffect(() => {
    if (availableCategoryMappings.length > 0) {
      if (initialCategory) {
        const initialIndex = availableCategoryMappings.findIndex(
          (cat) =>
            cat.display === initialCategory.display &&
            JSON.stringify(cat.dbCategory) === JSON.stringify(initialCategory.dbCategory)
        );
        if (initialIndex !== -1) {
          setCategoryIndex(initialIndex);
        } else {
          // Fallback if initialCategory is not found in available mappings
          const newsIndex = availableCategoryMappings.findIndex(c => c.dbCategory === '__NOTICIAS__');
          setCategoryIndex(newsIndex !== -1 ? newsIndex : 0);
        }
      } else {
        // En cada inicio de la aplicación elegir al azar la categoría a mostrar (Request v26)
        const randomIndex = Math.floor(Math.random() * availableCategoryMappings.length);
        setCategoryIndex(randomIndex);
      }
    }
  }, [availableCategoryMappings, initialCategory]); // Add initialCategory to dependencies

  const handleNextCategory = useCallback(() => {
    setCategoryIndex(prev => (prev + 1) % availableCategoryMappings.length);
    setShuffleNonce(n => n + 1); // Forzar nuevo orden en cada elección (v26.1)
  }, [availableCategoryMappings.length]);

  const handlePrevCategory = useCallback(() => {
    setCategoryIndex(prev => (prev - 1 + availableCategoryMappings.length) % availableCategoryMappings.length);
    setShuffleNonce(n => n + 1); // Forzar nuevo orden en cada elección (v26.1)
  }, [availableCategoryMappings.length]);

  // Manejo de Clics
  const handleCardClick = useCallback((item: Video | Article) => {
    const isArticle = 'slug' in item || 'titulo' in item || 'url_slide' in item;

    const getProcessedAudioUrl = (inputUrl: string | undefined | null): string | null => {
      if (!inputUrl) return null;
      const cleanUrl = inputUrl.trim();
      if (cleanUrl.startsWith('http://') || cleanUrl.startsWith('https://')) {
        return cleanUrl;
      }
      const mediaUrl = process.env.NEXT_PUBLIC_MEDIA_URL || 'https://media.saladillovivo.com.ar';
      return `${mediaUrl}${cleanUrl.startsWith('/') ? cleanUrl : `/${cleanUrl}`}`;
    };

    if (isArticle) {
      const newsItem = item as any;
      const title = cleanTitle(newsItem.title || newsItem.titulo);
      const imageUrl = newsItem.imageUrl || newsItem.image_url || newsItem.imagen || 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=';
      const rawAudio = newsItem.audio_url || newsItem.audioUrl || newsItem.audioSourceUrl || newsItem.media_url || (newsItem.audio ? newsItem.audio.url : undefined);
      const audioUrl = getProcessedAudioUrl(rawAudio);
      const urlSlide = newsItem.url_slide || newsItem.urlSlide;
      // Duración = la real del audio (animation_duration en DB, = locución + 1s de cola).
      // Si viene vacía (artículos viejos), 0: el reproductor espera el fin del audio.
      const duration = newsItem.animation_duration || newsItem.duration || 0;
      const isHtmlSlide = urlSlide && urlSlide.endsWith('.html');

      console.group(`[TvRail-Click] ${title}`);
      console.log('Item Original:', { 
        audio_url: newsItem.audio_url, 
        audioUrl: newsItem.audioUrl, 
        audioSourceUrl: newsItem.audioSourceUrl 
      });
      console.log('Dato Crudo seleccionado:', rawAudio);
      console.log('URL Procesada:', audioUrl);
      console.groupEnd();

      if (isHtmlSlide) {
        // pauseForSlide() en VideoSection.tsx gestiona la pausa automáticamente (P4-fix)
        const slideToPlay = {
          url: urlSlide,
          type: 'html' as const,
          duration,
          audioUrl: audioUrl || null,
          title,
          embedsAudio: false  // El audio es centralizado por VideoSection; el iframe NO maneja <audio>
        };
        console.log('[TvRail-Click] Ejecutando playSlide con:', slideToPlay);
        playSlide(slideToPlay);
      } else if (urlSlide) {
        // Video temporal
        playTemporaryVideo({
          id: (newsItem.id || Date.now()).toString(),
          type: 'video',
          url: urlSlide,
          nombre: title,
          categoria: 'Noticias',
          imagen: imageUrl,
          duration: duration,
          createdAt: new Date().toISOString(),
          novedad: false // Added to satisfy SlideMedia interface
        }, volume, setVolume);
      }
    } else {
      playSpecificVideo(item as Video, volume, setVolume);
    }

    // Llamar callback para ocultar overlays
    onVideoSelect?.();
  }, [playSpecificVideo, playTemporaryVideo, playSlide, volume, setVolume, onVideoSelect]);

  const processThumbnails = useCallback((items: any[]) => {
    return items.map(item => {
      let thumb = item.imageUrl || item.image_url || item.imagen;
      // Only use url_slide if it's not an HTML file (prevent broken images)
      if (!thumb && item.url_slide && !item.url_slide.endsWith('.html')) {
        thumb = item.url_slide;
      }
      thumb = thumb || TRANSPARENT_PNG_DATA_URI;
      if ((thumb === TRANSPARENT_PNG_DATA_URI || !thumb) && item.url) {
        const match = item.url.match(/(?:youtu\.be\/|youtube\.com\/.*v=)([^&]+)/);
        if (match && match[1]) thumb = `https://img.youtube.com/vi/${match[1]}/hqdefault.jpg`;
      }

      // Map title/titulo to nombre for ExclusiveVideoCarousel
      const nombre = cleanTitle(item.nombre || item.title || item.titulo || '');

      return { ...item, imageUrl: thumb, imagen: thumb, nombre };
    });
  }, []); // galleryVideos removed from dependencies as it's not directly used inside

  const processedAllNews = useMemo(() => {
    const processed = processThumbnails(allNews);
    return shuffleArray(processed);
  }, [allNews, processThumbnails]);

  // Determine activeCategory and rawItems only if availableCategoryMappings is not empty
  const activeCategory = availableCategoryMappings.length > 0 ? availableCategoryMappings[categoryIndex] : undefined;

  const rawItems = useMemo(() => {
    return activeCategory ? (activeCategory.dbCategory === '__NOTICIAS__' ? allNews : galleryVideos) : [];
  }, [activeCategory, allNews, galleryVideos]);

  const processedItems = useMemo(() => {
    const processed = processThumbnails(rawItems);
    return shuffleArray(processed);
  }, [rawItems, processThumbnails, shuffleNonce]); // v26.1: Dependencia de shuffleNonce

  if (isLoadingNews || availableCategoryMappings.length === 0) {
    return <div className="text-white p-4 bg-white/10 rounded-lg flex justify-center items-center h-[126px]">Cargando...</div>;
  }

  // --- RENDERIZADO ---
  if (isSearching) {
    if (searchLoading) return <div className="text-white p-4">Buscando...</div>;
    const processed = processThumbnails(searchResults);
    return (
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: isVisible ? 1 : 0, y: isVisible ? 0 : 20 }}
        transition={{ duration: 0.5 }}
        style={{ pointerEvents: isVisible ? 'auto' : 'none' }}
        className="w-full max-w-screen-xl mx-auto px-4"
      >
        <CategoryCycler
          allVideos={processed}
          activeCategory={{ display: 'Tu Búsqueda', dbCategory: 'search_results' }}
          onNext={() => { }}
          onPrev={() => { }}
          onCardClick={handleCardClick}
          isSearchResult={true}
          instanceId="search-carousel"
        />      </motion.div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: isVisible ? 1 : 0, y: isVisible ? 0 : 20 }}
      transition={{ duration: 0.5 }}
      style={{ pointerEvents: isVisible ? 'auto' : 'none' }}
      className="w-full max-w-screen-xl mx-auto px-4"
    >
      <div className="-mt-[5px] w-full relative z-0 flex flex-col gap-6">
        {/* Static Latest News Carousel */}
        <CategoryCycler
          allVideos={processedAllNews}
          activeCategory={{ display: 'ÚLTIMAS NOTICIAS', dbCategory: '__NOTICIAS__' }}
          // Hide navigation arrows for this static row if preferred, or keep them empty/managed internally if needed.
          // Since CategoryCycler handles its own internal filtering/display, passing 'allNews' is correct.
          // However, CategoryCycler usually expects onNext/onPrev for the *category* switching.
          // If we just want a carousel of items without category switching, we can pass dummy/empty functions or modify CategoryCycler.
          // Based on current CategoryCycler, it renders navigation buttons for the CATEGORY.
          // For this specific 'Latest News' row, we likely DON'T want category switching arrows.
          onNext={undefined}
          onPrev={undefined}
          onCardClick={handleCardClick}
          instanceId="tv-latest-news"
          loop={true}
        />

        {/* Dynamic Category Cycler */}
        {activeCategory && (
          <CategoryCycler
            allVideos={processedItems}
            activeCategory={activeCategory}
            onNext={handleNextCategory}
            onPrev={handlePrevCategory}
            onCardClick={handleCardClick}
            instanceId="tv-carousel"
            loop={true}
          />
        )}
      </div>
    </motion.div>
  );
};

export default TvContentRail;