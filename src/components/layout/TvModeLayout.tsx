'use client';

import React, { useState, useEffect, useCallback } from 'react';
import VideoSection from './VideoSection';
import VideoControls from '../VideoControls';
import TvContentRail from '../tv/TvContentRail';
import { useNewsStore } from '@/store/useNewsStore';
import Image from 'next/image';
import { motion, AnimatePresence } from 'framer-motion';
import { usePlayerStore } from '@/store/usePlayerStore';
import { useNewsPlayerStore } from '@/store/useNewsPlayerStore';
import { CategoryMapping } from '@/lib/categoryMappings';

// Definir las categorías elegibles para el inicio aleatorio
const INITIAL_TV_CATEGORIES: CategoryMapping[] = [
  { display: 'Saladillo Canta', dbCategory: 'clips' },
  { display: 'Gente de Acá', dbCategory: 'export' },
  { display: 'Sembrando Futuro', dbCategory: 'SEMBRANDO FUTURO' },
];

const TvModeLayout = () => {
  const { handleSearch, searchResults, isSearching, searchLoading } = useNewsStore();
  const { isPlaying, setViewMode, loadInitialPlaylist } = usePlayerStore();
  const { isPlaying: isNewsPlaying } = useNewsPlayerStore();
  const [initialTvCategory, setInitialTvCategory] = useState<CategoryMapping | undefined>(undefined);

  useEffect(() => {
    const randomIndex = Math.floor(Math.random() * INITIAL_TV_CATEGORIES.length);
    setInitialTvCategory(INITIAL_TV_CATEGORIES[randomIndex]);
    loadInitialPlaylist(null);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const onSearchSubmit = useCallback((term: string) => {
    handleSearch(term);
  }, [handleSearch]);

  const [isOverlayVisible, setIsOverlayVisible] = useState(true);
  const [isCarouselVisible, setIsCarouselVisible] = useState(true);

  const toggleOverlays = useCallback(() => {
    setIsOverlayVisible(prev => !prev);
    setIsCarouselVisible(prev => !prev);
  }, []);

  const hideOverlays = useCallback(() => {
    setIsOverlayVisible(false);
    setIsCarouselVisible(false);
  }, []);

  // Gestión de inactividad: Ocultar controles tras 1 segundo (v28.0)
  useEffect(() => {
    let timeoutId: NodeJS.Timeout;

    const resetInactivityTimer = () => {
      setIsOverlayVisible(true);
      setIsCarouselVisible(true);
      
      if (timeoutId) clearTimeout(timeoutId);
      timeoutId = setTimeout(() => {
        setIsOverlayVisible(false);
        setIsCarouselVisible(false);
      }, 1000); // 1 segundo de gracia
    };

    // Eventos que "despiertan" la UI
    window.addEventListener('mousemove', resetInactivityTimer);
    window.addEventListener('keydown', resetInactivityTimer);
    window.addEventListener('mousedown', resetInactivityTimer);
    window.addEventListener('touchstart', resetInactivityTimer);

    // Arrancar el timer al inicio
    resetInactivityTimer();

    return () => {
      window.removeEventListener('mousemove', resetInactivityTimer);
      window.removeEventListener('keydown', resetInactivityTimer);
      window.removeEventListener('mousedown', resetInactivityTimer);
      window.removeEventListener('touchstart', resetInactivityTimer);
      if (timeoutId) clearTimeout(timeoutId);
    };
  }, []);


  // Volver a modo diario al salir de pantalla completa (ESC o manual) (v28.2)
  useEffect(() => {
    const handleFSChange = () => {
      const isCurrentlyFS = !!document.fullscreenElement;
      setIsFullScreen(isCurrentlyFS);
      
      if (!isCurrentlyFS) {
        setViewMode('diario');
      }
    };

    document.addEventListener('fullscreenchange', handleFSChange);
    return () => document.removeEventListener('fullscreenchange', handleFSChange);
  }, [setViewMode]);

  const [isFullScreen, setIsFullScreen] = useState(false);

  const toggleFullScreen = useCallback(() => {
    if (!document.fullscreenElement) {
      const el = document.documentElement as any;
      (el.webkitRequestFullscreen || el.mozRequestFullScreen || el.requestFullscreen)?.call(el)
        .catch((e: any) => console.error("Fullscreen requiere interacción:", e));
    } else {
      document.exitFullscreen?.().catch(() => {});
    }
  }, []);

  const handleSwitchToDailyMode = useCallback(() => {
    setViewMode('diario');
    if (document.fullscreenElement) {
      document.exitFullscreen().catch(() => {});
    }
  }, [setViewMode]);

  return (

    <div
      className="relative h-screen w-screen overflow-hidden bg-black"
    >
      <div className="absolute inset-0 z-0">
        <VideoSection />
        {/* Capa transparente para capturar clicks y mostrar/ocultar overlays */}
        <div className="absolute inset-0 z-10" onClick={toggleOverlays} />
      </div>
      <AnimatePresence>
        {!isPlaying && !isNewsPlaying && isOverlayVisible && (
          <motion.div
            initial={{ opacity: 1 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 2.0, ease: "easeOut" }}
            className="absolute inset-0 z-20 pointer-events-none"
          >
            <div className="absolute top-0 left-0 w-full bg-black h-[15%] pointer-events-auto" />
            <div className="absolute bottom-0 left-0 w-full bg-black h-[15%] pointer-events-auto" />
          </motion.div>
        )}
      </AnimatePresence>
      {/* 3. UI Overlay - IMPORTANTE: pointer-events-none para no bloquear el fondo */}
      <div
        className={`absolute inset-0 z-30 flex flex-col justify-between h-full transition-opacity duration-500 ease-in-out pointer-events-none will-change-[opacity] ${isOverlayVisible ? 'opacity-100' : 'opacity-0'}`}

      >
        <div
          className={`bg-gradient-to-b from-black/80 to-transparent p-8 ${isOverlayVisible ? 'pointer-events-auto' : 'pointer-events-none'}`}

        >
          <div className="bg-black/10 backdrop-blur-lg shadow-lg shadow-black/50 rounded-md p-4 inline-block">
            <Image
              src="/FONDO_OSCURO.png"
              alt="Saladillo Vivo Logo"
              width={288}
              height={72}
              className="h-auto w-72 object-contain"
              priority
            />
          </div>
        </div>

        <div
          className={`bg-gradient-to-t from-black/80 to-transparent p-8 ${isOverlayVisible ? 'pointer-events-auto' : 'pointer-events-none'}`}

        >
          <div className="flex justify-between items-end">
            <div
              className={isOverlayVisible ? 'pointer-events-auto' : 'pointer-events-none'} // Permitir eventos de mouse solo si es visible

            >
              <TvContentRail
                searchResults={searchResults}
                isSearching={isSearching}
                searchLoading={searchLoading}
                initialCategory={initialTvCategory} // Pasa la categoría inicial aleatoria
                isVisible={isCarouselVisible} // Pasa la visibilidad al carrusel
                onVideoSelect={hideOverlays} // Ocultar overlays al elegir video
              />
            </div>
          </div>
        </div>

        <div
          className={`absolute top-4 right-4 z-[60] flex items-center gap-2 ${isOverlayVisible ? 'pointer-events-auto' : 'pointer-events-none'}`}

        >
          <div className="rounded-md p-2 bg-black/10 backdrop-blur-lg shadow-lg shadow-black/50">
            <VideoControls
              showControls={isOverlayVisible}
              onToggleFullScreen={toggleFullScreen}
              isFullScreen={isFullScreen}
              onSwitchToDailyMode={handleSwitchToDailyMode}
              onSearchSubmit={onSearchSubmit}
            />
          </div>
        </div>
      </div>
    </div>
  );

};

export default TvModeLayout;