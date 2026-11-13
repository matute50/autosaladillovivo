'use client';

import React, { useRef, useState, useEffect } from 'react';
import VideoPlayer from '@/components/VideoPlayer';
import { AnimatePresence, motion } from 'framer-motion';
import Image from 'next/image';
import { usePlayerStore } from '@/store/usePlayerStore';
import { useNewsPlayerStore } from '@/store/useNewsPlayerStore';
import { useVolumeStore } from '@/store/useVolumeStore';
import CustomControls from '@/components/CustomControls';
import VideoTitleBar from '@/components/VideoTitleBar';
import NewsTicker from '@/components/NewsTicker';
import WeatherOverlay from '@/components/tv/WeatherOverlay';
import { cn, cleanTitle } from '@/lib/utils';
import { Play } from 'lucide-react';
import AntiGravityLayer from './AntiGravityLayer';
import { NewsSlidePlayer } from '@/components/NewsSlidePlayer';

// Simplified VideoSection for Desktop Only

const VideoSection: React.FC = () => {
  const [isFullScreen, setIsFullScreen] = useState(false);
  const playerContainerRef = useRef<HTMLDivElement>(null);
  const [areCinematicBarsActive, setAreCinematicBarsActive] = useState(false);
  const isInitialLoadRef = useRef(true);

  const {
    currentVideo,
    nextVideo,
    isPlaying,
    handleOnEnded,
    saveCurrentProgress,
    setIsPlaying,
    isPreRollOverlayActive,
    overlayIntroVideo,
    viewMode,
    isContentPlaying,
    pauseForSlide,
    resumeAfterSlide,
    finishIntro,
    isPostNewsFadeIn,
    isPostNewsMusical,
  } = usePlayerStore();

  const { currentSlide, isPlaying: isSlidePlaying, stopSlide, isNewsIntroActive, setIsNewsIntroActive, isSlideOpen, closeSlide } = useNewsPlayerStore();
  const { volume, setVolume, isMuted, unmute } = useVolumeStore(); // Added unmute

  // Auto-Unmute for News or HTML Slides
  const isNewsSlide = !!(
    (isSlidePlaying && currentSlide && (
      Boolean((currentSlide as any)?.type === 'html' || (currentSlide as any)?.url?.includes('.html') || (currentSlide as any)?.url?.includes('/slides/'))
    )) ||
    (currentVideo?.type === 'html') ||
    Boolean(currentVideo?.url_slide && (currentVideo.url_slide.includes('.html') || currentVideo.url_slide.includes('/slides/')))
  );

  const isNewsImageAudio = !isNewsSlide && !!(
    currentVideo?.type === 'image' ||
    (!currentVideo?.url && !!(currentVideo?.audioSourceUrl || currentVideo?.imagen))
  );

  const isHtmlSlideActive = isNewsSlide;
  const isLocalIntro = currentVideo?.url && (
    currentVideo.url.startsWith('/') ||
    currentVideo.url.includes('videos_intro')
  ) || false;
  const isNewsContent = !!((currentVideo?.categoria === 'Noticias' || isNewsSlide || isNewsImageAudio) && !isLocalIntro);

  // P2-fix: el volumen y unmute se gestionan ahora directamente en el useEffect de activación del slide
  // para mayor precisión y cumplimiento de políticas de autoplay.

  // Limpiamos el flag de carga inicial solo después de que el primer video haya tenido tiempo de empezar
  // o cuando cambie el video por segunda vez.
  useEffect(() => {
    if (isInitialLoadRef.current && currentVideo) {
      const timer = setTimeout(() => {
        // isInitialLoadRef.current = false; // No lo limpiamos aquí aún, dejamos que handleOnEnded lo haga mejor
      }, 5000);
      return () => clearTimeout(timer);
    }
  }, [currentVideo]);

  const [showControls, setShowControls] = useState(false);
  const [thumbnailSrc, setThumbnailSrc] = useState<string>('data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=');
  const cinematicTimerRef = useRef<NodeJS.Timeout|null>(null);
  const lastProcessedVideoIdRef = useRef<string | null>(null);
  const [currentDuration, setCurrentDuration] = useState(0);
  const transitionSignaledRef = useRef(false);

  const audioRef = useRef<HTMLAudioElement>(null);
  const introVideoRef = useRef<HTMLVideoElement>(null);
  const [isIntroFadingOut, setIsIntroFadingOut] = useState(false);
  const [slideFadeOut, setSlideFadeOut] = useState(false);
  const [slideHtmlContent, setSlideHtmlContent] = useState<string | null>(null);



  // Carga asíncrona del HTML del slide para renderizar vía srcDoc (evita bloqueo CSP default-src: none de Supabase Storage)
  useEffect(() => {
    const rawUrl = typeof currentSlide === 'string' ? currentSlide : (currentSlide?.url || currentVideo?.url_slide);
    if (!rawUrl || !rawUrl.includes('.html')) {
      setSlideHtmlContent(null);
      return;
    }

    let isMounted = true;
    fetch(rawUrl)
      .then((res) => {
        if (!res.ok) throw new Error("HTTP " + res.status);
        return res.text();
      })
      .then((html) => {
        if (isMounted && html && html.includes('<!DOCTYPE html>')) {
          setSlideHtmlContent(html);
        }
      })
      .catch((err) => {
        console.warn("[VideoSection] Fetch slide HTML fallback:", err);
      });

    return () => {
      isMounted = false;
    };
  }, [currentSlide, currentVideo?.url_slide]);

  // --- SMART SLOT SYSTEM (v18.0) STATE ---
  const [activeSlot, setActiveSlot] = useState<'A' | 'B'>('A');
  const [slotAVideo, setSlotAVideo] = useState<typeof currentVideo>(currentVideo);
  const [slotBVideo, setSlotBVideo] = useState<typeof nextVideo>(nextVideo);

  // Sincronización continua de Slots A/B sin desmontar nodos en el DOM
  useEffect(() => {
    if (!currentVideo) return;

    console.log('[VideoSection] Slot effect triggered — activeSlot:', activeSlot, 'currentVideo:', currentVideo.id, 'slotA:', slotAVideo?.id, 'slotB:', slotBVideo?.id, 'nextVideo:', nextVideo?.id);

    if (activeSlot === 'A') {
      if (slotBVideo?.id === currentVideo.id) {
        // Swap A -> B sin corte
        setActiveSlot('B');
        if (nextVideo && nextVideo.id !== currentVideo.id) {
          setSlotAVideo(nextVideo);
        }
      } else if (slotAVideo?.id === currentVideo.id) {
        // Mismo slot A, asegurar que el inactivo B tenga nextVideo listo para precargar
        if (nextVideo && slotBVideo?.id !== nextVideo.id) {
          setSlotBVideo(nextVideo);
        }
      } else {
        // Asignación directa
        setSlotAVideo(currentVideo);
        if (nextVideo && nextVideo.id !== currentVideo.id) {
          setSlotBVideo(nextVideo);
        }
      }
    } else {
      // activeSlot === 'B'
      if (slotAVideo?.id === currentVideo.id) {
        // Swap B -> A sin corte
        setActiveSlot('A');
        if (nextVideo && nextVideo.id !== currentVideo.id) {
          setSlotBVideo(nextVideo);
        }
      } else if (slotBVideo?.id === currentVideo.id) {
        // Mismo slot B, asegurar que el inactivo A tenga nextVideo listo para precargar
        if (nextVideo && slotAVideo?.id !== nextVideo.id) {
          setSlotAVideo(nextVideo);
        }
      } else {
        // Asignación directa
        setSlotBVideo(currentVideo);
        if (nextVideo && nextVideo.id !== currentVideo.id) {
          setSlotAVideo(nextVideo);
        }
      }
    }
  }, [currentVideo, nextVideo, activeSlot, slotAVideo?.id, slotBVideo?.id]);

  // --- AUDIO LEVELLING (v23.1) ---
  useEffect(() => {
    if (audioRef.current) {
      if (isHtmlSlideActive) {
        audioRef.current.volume = 1;
        audioRef.current.muted = false;
      } else {
        const extra = (currentVideo as any)?.volumen_extra || 1;
        const targetVolume = Math.min(1, (volume || 1) * extra);
        audioRef.current.volume = isMuted ? 0 : targetVolume;
      }
    }
  }, [volume, isMuted, isHtmlSlideActive, currentVideo]);


  const [playBackgroundEarly, setPlayBackgroundEarly] = useState(false);
  const transitionTriggeredRef = useRef(false);
  const introWatchdogRef = useRef<NodeJS.Timeout | null>(null);
  const slideCloseTimerRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    setPlayBackgroundEarly(false);
    transitionSignaledRef.current = false;
    setCurrentDuration(0);
    setIsIntroFadingOut(false);
    setSlideFadeOut(false);
  }, [currentVideo?.id]);

  const hasStartedAudioRef = useRef(false);
  const [audioDurationSec, setAudioDurationSec] = useState<number | null>(null);

  // DIAGNÓSTICO DE SLIDES
  useEffect(() => {
    if (isSlidePlaying || currentSlide) {
      console.log("[AudioSlide-Status]", {
        isSlidePlaying,
        isHtmlSlideActive,
        type: currentSlide?.type,
        audioUrl: currentSlide?.audioUrl,
        embedsAudio: currentSlide?.embedsAudio,
        hasStartedAudio: hasStartedAudioRef.current
      });
    }
  }, [isSlidePlaying, isHtmlSlideActive, currentSlide]);

  // Audio Sync - Sincroniza el audio centralizado cuando termina la intro de noticias
  useEffect(() => {
    if (isNewsIntroActive || isPreRollOverlayActive) return;

    const audioUrl = isNewsSlide ? (currentSlide?.audioUrl || null) : (currentVideo?.audioSourceUrl || null);

    if (audioUrl && audioUrl !== 'NO_AUDIO_URL') {
      if (audioRef.current) {
        audioRef.current.muted = false;
        const extra = (currentVideo as any)?.volumen_extra || 1;
        const targetVolume = Math.min(1, (volume || 1) * extra);
        audioRef.current.volume = isMuted ? 0 : (isHtmlSlideActive ? 1 : targetVolume);
        // Solo reasignar src si es DIFERENTE al actual.
        // Re-asignar el mismo src resetea el elemento en algunos navegadores y dispara onEnded prematuro.
        if (audioRef.current.src !== audioUrl) {
          console.log('[AudioSync] Cambiando src a:', audioUrl.slice(-60));
          audioRef.current.src = audioUrl;
          hasStartedAudioRef.current = false; // Nuevo src = nuevo ciclo de reproducción
        }
        // Solo llamar play() si no estaba sonando ya este src
        if (!hasStartedAudioRef.current || audioRef.current.paused) {
          console.log('[AudioSync] Llamando play() — isNewsSlide:', isNewsSlide, 'hasStartedAudio:', hasStartedAudioRef.current, 'paused:', audioRef.current.paused);
          hasStartedAudioRef.current = true;
          audioRef.current.play().catch((err) => {
            console.warn("[VideoSection] Play audio noticia:", err);
          });
        } else {
          console.log('[AudioSync] Audio ya reproduciendo, no se llama play()');
        }
      }
    } else if (!isNewsSlide && !isNewsImageAudio) {
      if (audioRef.current && !audioRef.current.paused) {
        console.log('[AudioSync] Pausando audio (no es slide ni imagen):', audioRef.current.src.slice(-40));
        audioRef.current.pause();
        audioRef.current.src = "";
      }
    }
  }, [isNewsIntroActive, isPreRollOverlayActive, isNewsSlide, isNewsImageAudio, currentSlide?.audioUrl, currentVideo?.audioSourceUrl, isMuted, volume, currentVideo, isHtmlSlideActive]);

  // Reset del ref cuando el contenido específico cambia (ej: de un slide .html a otro)
  useEffect(() => {
    hasStartedAudioRef.current = false;
    setAudioDurationSec(null);
    if (slideCloseTimerRef.current) clearTimeout(slideCloseTimerRef.current);
  }, [currentSlide?.url]);



  // FIX AUTOPLAY: Si isPreRollOverlayActive está activo pero no hay video de intro asignado,
  // el reproductor quedaría bloqueado indefinidamente (isContentPlaying nunca se activaría).
  // En ese caso, saltamos la intro directamente.
  useEffect(() => {
    if (isPreRollOverlayActive && !overlayIntroVideo && currentVideo) {
      // Sin intro = sin overlay = activar contenido inmediatamente
      const timer = setTimeout(() => {
        finishIntro();
      }, 100); // 100ms de gracia para evitar estados intermedios del store
      return () => clearTimeout(timer);
    }
  }, [isPreRollOverlayActive, overlayIntroVideo, currentVideo, finishIntro]);

  // --- UNIVERSAL PAUSE-ZOOM STRATEGY (V23.2) ---
  // No specific "Return from News" detection needed.
  // The Pause state itself triggers the shield.

  useEffect(() => {
    let timer: NodeJS.Timeout;
    if (isNewsIntroActive) {
      // Watchdog de seguridad (7s) por si el video de intro no dispara onEnded o falla su carga.
      // El video /videos_intro/noticias.mp4 dura 4.64s y debe finalizar naturalmente via onEnded
      // antes de que comience la locución del cuerpo de la noticia.
      timer = setTimeout(() => {
        setIsNewsIntroActive(false);
      }, 7000);
    }
    return () => {
      if (timer) clearTimeout(timer);
    };
  }, [isNewsIntroActive, setIsNewsIntroActive]);


  useEffect(() => {
    const isNewVideo = !!(currentVideo && currentVideo.id !== lastProcessedVideoIdRef.current);

    // Clear any previous timer
    const clearTimer = () => {
      if (cinematicTimerRef.current) {
        clearTimeout(cinematicTimerRef.current);
        cinematicTimerRef.current = null;
      }
    };

    if (currentVideo?.id === 'live-stream') {
      setAreCinematicBarsActive(false);
      clearTimer();
      lastProcessedVideoIdRef.current = 'live-stream';
      return;
    }

    if (isPlaying) {
      if (isNewVideo && !isLocalIntro && !isPreRollOverlayActive) {
        // --- CASE: NEW VIDEO START (INTRO) ---
        lastProcessedVideoIdRef.current = currentVideo.id;
        setAreCinematicBarsActive(true);
        clearTimer();
        cinematicTimerRef.current = setTimeout(() => {
          setAreCinematicBarsActive(false);
        }, 5000); // 5s Anti-Branding Shield
      } else if (!isNewVideo) {
        // --- CASE: RESUME PLAY (Universal Anti-Branding V23.2) ---
        // Resume from Pause (or News) -> Hold Shield for 2s, then Zoom Out (1s)

        setAreCinematicBarsActive(true); // Ensure active
        clearTimer();
        cinematicTimerRef.current = setTimeout(() => {
          setAreCinematicBarsActive(false); // Triggers Zoom Out transition
        }, 5000); // 5s Hold (V23.3)
      } else if (isNewVideo) {
        // Backup: update ref even if we don't show bars
        lastProcessedVideoIdRef.current = currentVideo.id || null;
      }
    } else {
      // --- CASE: PAUSED (Manual or Auto) ---
      // Force Shield + Over-Scaling immediately
      if (!isLocalIntro && !isHtmlSlideActive && !isPreRollOverlayActive && currentVideo) {

        setAreCinematicBarsActive(true);
        clearTimer(); // Keep active indefinitely while paused
      } else {
        setAreCinematicBarsActive(false);
        clearTimer();
      }
    }

    return () => clearTimer();
  }, [isPlaying, currentVideo?.id, isLocalIntro, isHtmlSlideActive, isPreRollOverlayActive, currentVideo]);

  useEffect(() => {
    if (!currentVideo?.url || isLocalIntro) {
      setThumbnailSrc('data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=');
      return;
    }
    const cleanUrl = currentVideo.url.trim();
    const match = cleanUrl.match(/(?:youtu\.be\/|youtube\.com\/.*v=)([^&]+)/);
    if (match && match[1]) {
      setThumbnailSrc(`https://img.youtube.com/vi/${match[1]}/maxresdefault.jpg`);
    } else {
      setThumbnailSrc('data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=');
    }
  }, [currentVideo, isLocalIntro]);

  // Fullscreen con prefijos cross-browser (Safari / Chrome / Firefox)
  const toggleFullScreen = () => {
    if (!playerContainerRef.current) return;
    const el = document.documentElement as any;
    const doc = document as any;
    if (!doc.fullscreenElement && !el.webkitRequestFullscreen) {
      if (el.webkitRequestFullscreen) el.webkitRequestFullscreen();
      else if (el.mozRequestFullScreen) el.mozRequestFullScreen();
      else el.requestFullscreen?.();
    } else {
      if (doc.webkitIsFullScreen) doc.webkitCancelFullScreen?.();
      else if (doc.mozCancelFullScreen) doc.mozCancelFullScreen();
      else doc.exitFullscreen?.();
    }
  };

  useEffect(() => {
    const handleFs = () => {
      setIsFullScreen(!!document.fullscreenElement);
    };
    document.addEventListener('fullscreenchange', handleFs);
    return () => document.removeEventListener('fullscreenchange', handleFs);
  }, []);

  const handleProgress = (state: { playedSeconds: number, loadedSeconds: number }) => {
    const { playedSeconds } = state;

    if (!isLocalIntro && !isPreRollOverlayActive) {
      saveCurrentProgress(playedSeconds, volume);

      if (
        currentDuration > 0 &&
        currentDuration - playedSeconds <= 1 &&
        !transitionSignaledRef.current
      ) {

        transitionSignaledRef.current = true;
        handleOnEnded(setVolume, unmute);
      }

      // Capture volume 10s before end for persistence (v24.8)
      if (
        currentDuration > 0 &&
        currentDuration - playedSeconds <= 10 &&
        currentDuration - playedSeconds > 9.5
      ) {
        // captureVolumeForHistory(); // Function missing in context v24.8
      }
    }
  };


  const handleIntroTimeUpdate = (e: React.SyntheticEvent<HTMLVideoElement>) => {
    const video = e.currentTarget;
    if (!video.duration || !video.playbackRate) return;
    const timeLeft = (video.duration - video.currentTime) / video.playbackRate;
    if (timeLeft <= 1 && !video.muted) {
      const fadeProgress = Math.max(0, 1 - timeLeft);
      video.volume = Math.max(0, 1 - fadeProgress);
    }
    if (timeLeft <= 0.5 && !isIntroFadingOut) {
      setIsIntroFadingOut(true);
    }
    // Sincronización 2s: Iniciar contenido oculto detrás de la intro (v25.1)
    // IMPORTANTE: NO activar durante la fase post-noticia musical para evitar que
    // el video de YouTube antiguo quede expuesto y dispare onEnded → handleOnEnded
    // limpiando isPostNewsMusical antes de que finishIntro cargue el clip clips.
    if (timeLeft <= 2 && !isContentPlaying && isPreRollOverlayActive && !isPostNewsMusical) {
      usePlayerStore.setState({ isContentPlaying: true });
    }

    // Barras de Cine: 1s antes del fin de la intro (v25.1)
    // No activar si es un vivo
    if (timeLeft <= 1 && !areCinematicBarsActive && isPreRollOverlayActive && currentVideo?.id !== 'live-stream') {
      setAreCinematicBarsActive(true);
    }
  };

  const handleIntroMetadata = (e: React.SyntheticEvent<HTMLVideoElement>) => {
    const video = e.currentTarget;
    if (video.duration) {
      const rate = video.duration / 4.0;
      video.playbackRate = rate;
    }
  };


  const displayTitle = cleanTitle(currentVideo?.nombre || (typeof currentSlide === 'object' ? currentSlide?.title : undefined));
  const displaySubtitle = (currentVideo as any)?.resumen || (currentVideo as any)?.description || (typeof currentSlide === 'object' ? currentSlide?.subtitle : undefined);

  return (
    <div className="w-full overflow-visible">
      <div className="relative aspect-video w-full">
        <div
          ref={playerContainerRef}
          className={cn(
            "relative w-full h-full aspect-video bg-black overflow-hidden border-0 md:border md:rounded-xl card-blur-player shadow-lg",
          )}
          onMouseEnter={() => setShowControls(true)}
          onMouseLeave={() => setShowControls(false)}
        >
          {/* === VIDEO UNIVERSE (SCALABLE & IMMERSIVE) === */}
          <div
            className={cn(
              "video-universe absolute inset-0 w-full h-full transition-transform ease-in-out md:rounded-xl overflow-hidden"
            )}
            style={{
              transform: areCinematicBarsActive ? 'scale(1.20)' : 'scale(1)',
              transitionDuration: areCinematicBarsActive ? '75ms' : '2000ms',
              willChange: 'transform'
            }}
          >

            {/* 1. SLIDE INTERACTIVO HTML (TV-GRADE con srcDoc para evitar bloqueo CSP default-src none de Supabase Storage) */}
            {/* key={rawUrl} garantiza que React DESMONTE el iframe anterior al cambiar de noticia.
                Sin esto, el setInterval de rotación de fotos del slide viejo seguía corriendo
                y mezclaba imágenes entre diferentes noticias. */}
            {isNewsSlide && (slideHtmlContent || currentSlide?.url || currentVideo?.url_slide || (currentVideo?.url && currentVideo.url.includes('.html'))) && (() => {
              const rawUrl = typeof currentSlide === 'string' ? currentSlide : (currentSlide?.url || currentVideo?.url_slide || currentVideo?.url);
              return (
                <div key={rawUrl} className={`absolute inset-0 z-40 bg-black transition-opacity duration-500 ${slideFadeOut ? 'opacity-0' : 'opacity-100'}`}>
                  <iframe
                    srcDoc={slideHtmlContent || undefined}
                    src={slideHtmlContent ? undefined : rawUrl}
                    className="w-full h-full border-none pointer-events-auto"
                    title={typeof currentSlide === 'object' ? currentSlide?.title || currentVideo?.nombre || "Slide Noticia" : "Slide Noticia"}
                    sandbox="allow-same-origin allow-scripts allow-forms"
                    allow="autoplay; fullscreen"
                  />
                </div>
              );
            })()}

            {/* 2. NOTICIA CON FOTO Y AUDIO (CUANDO NO HAY SLIDE HTML PERO SÍ FOTO/AUDIO) */}
            {isNewsImageAudio && (
              <motion.div
                key={`news-image-${currentVideo?.id}`}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.75 }}
                className="absolute inset-0 z-30 bg-black flex items-center justify-center overflow-hidden"
              >
                {currentVideo?.imagen && (
                  <Image
                    src={currentVideo.imagen}
                    alt={currentVideo.nombre || "Noticia"}
                    fill
                    className="object-cover scale-105"
                    priority
                  />
                )}
                <div className="absolute inset-0 bg-gradient-to-t from-black/90 via-black/20 to-black/60 pointer-events-none" />
              </motion.div>
            )}

            {/* 3. REPRODUCTOR TRADICIONAL - SMART SLOT SYSTEM A/B (v18.0) */}
            <div className="absolute inset-0 bg-black overflow-hidden">
              {/* SLOT A */}
              <div
                className={cn(
                  "absolute inset-0 transition-opacity ease-in-out",
                  // When in post-news phase and the musical interlude is playing, animate fade-in of the active slot
                  isPostNewsFadeIn && isPostNewsMusical && activeSlot === 'A'
                    ? "opacity-0 animate-[fade-in-300s_0.3s_ease-in-out_forwards]"
                    : isPostNewsFadeIn
                      ? "duration-300 opacity-0"
                      : "duration-700 opacity-100",
                  activeSlot === 'A'
                    ? "z-10 pointer-events-auto"
                    : "z-0 pointer-events-none"
                )}
                data-slot="A"
              >
                {slotAVideo?.url && (
                  <VideoPlayer
                    id={slotAVideo.id}
                    videoUrl={slotAVideo.url}
                    autoplay={activeSlot === 'A' && isPlaying && (isContentPlaying || isInitialLoadRef.current) && !isNewsSlide && !isNewsImageAudio}
                    muted={activeSlot !== 'A' || !isPlaying || !isContentPlaying || isNewsSlide || isNewsImageAudio}
                    imageUrl={slotAVideo.imagen}
                    onClose={() => {
                      // No reanudar el video principal si hay un slide de noticias activo en curso;
                      // la prioridad absoluta es que la noticia termine de reproducirse completa.
                      if (activeSlot === 'A' && !transitionSignaledRef.current && slotAVideo?.id !== 'live-stream' && !isNewsSlide && !isNewsImageAudio) {
                        handleOnEnded(setVolume, unmute);
                      }
                    }}
                    onProgress={(state) => {
                      if (activeSlot === 'A') {
                        handleProgress(state);
                      }
                    }}
                    onDuration={(d) => {
                      if (activeSlot === 'A') {
                        setCurrentDuration(d);
                      }
                    }}
                    startAt={slotAVideo.id === lastProcessedVideoIdRef.current ? undefined : (slotAVideo.novedad ? 0 : undefined)}
                    volumen_extra={slotAVideo.volumen_extra}
                    audioUrl={slotAVideo.audioSourceUrl}
                    isFadeIn={isPostNewsFadeIn}
                  />
                )}
              </div>

              {/* SLOT B */}
              <div
                className={cn(
                  "absolute inset-0 transition-opacity ease-in-out",
                  isPostNewsFadeIn && isPostNewsMusical && activeSlot === 'B'
                    ? "opacity-0 animate-[fade-in-300s_0.3s_ease-in-out_forwards]"
                    : isPostNewsFadeIn
                      ? "duration-300 opacity-0"
                      : "duration-700 opacity-100",
                  activeSlot === 'B'
                    ? "z-10 pointer-events-auto"
                    : "z-0 pointer-events-none"
                )}
                data-slot="B"
              >
                {slotBVideo?.url && (
                  <VideoPlayer
                    id={slotBVideo.id}
                    videoUrl={slotBVideo.url}
                    autoplay={activeSlot === 'B' && isPlaying && (isContentPlaying || isInitialLoadRef.current) && !isNewsSlide && !isNewsImageAudio}
                    muted={activeSlot !== 'B' || !isPlaying || !isContentPlaying || isNewsSlide || isNewsImageAudio}
                    imageUrl={slotBVideo.imagen}
                    onClose={() => {
                      // No reanudar el video principal si hay un slide de noticias activo en curso;
                      // la prioridad absoluta es que la noticia termine de reproducirse completa.
                      if (activeSlot === 'B' && !transitionSignaledRef.current && slotBVideo?.id !== 'live-stream' && !isNewsSlide && !isNewsImageAudio) {
                        handleOnEnded(setVolume, unmute);
                      }
                    }}
                    onProgress={(state) => {
                      if (activeSlot === 'B') {
                        handleProgress(state);
                      }
                    }}
                    onDuration={(d) => {
                      if (activeSlot === 'B') {
                        setCurrentDuration(d);
                      }
                    }}
                    startAt={slotBVideo.id === lastProcessedVideoIdRef.current ? undefined : (slotBVideo.novedad ? 0 : undefined)}
                    volumen_extra={slotBVideo.volumen_extra}
                    audioUrl={slotBVideo.audioSourceUrl}
                    isFadeIn={isPostNewsFadeIn}
                  />
                )}
              </div>
            </div>

            {/* ELEMENTO AUDIO CENTRALIZADO TOP-LEVEL PARA NOTICIAS (GARANTIZA VOLUMEN AUDIBLE) */}
            <audio
              ref={audioRef}
              data-slide-audio="true"
              className="opacity-0 pointer-events-none absolute"
              preload="auto"
              crossOrigin="anonymous"
              playsInline
              onPlay={() => {
                try {
                  const iframe = document.querySelector('.video-universe iframe') as HTMLIFrameElement | null;
                  if (iframe && iframe.contentWindow) {
                    iframe.contentWindow.postMessage({ type: 'START_NEWS_PLAYBACK' }, '*');
                  }
                } catch (err) {}
              }}
              onLoadedMetadata={(e) => {
                const el = e.currentTarget;
                if (el.duration && isFinite(el.duration) && el.duration > 0) {
                  setAudioDurationSec(el.duration);
                  // Programa cierre del slide al terminar audio + 5s de cola.
                  // Margen aumentado para asegurar que la frase promocional final
                  // (últimos ~1-5s del audio) tenga tiempo suficiente para reproducirse completa.
                  // OnEnded es la vía primaria; este timeout es respaldo por si el
                  // evento no dispara (por ej. cortada de red, CORS parcial).
                  if (slideCloseTimerRef.current) clearTimeout(slideCloseTimerRef.current);
                  const pad = 5;
                  slideCloseTimerRef.current = setTimeout(() => {
                    // Guarda el estado actual para evaluar si realmente terminó
                    const audioEl = document.querySelector('audio[data-slide-audio="true"]') as HTMLAudioElement | null;
                    const dur = audioEl?.duration || el.duration || 0;
                    const ct = audioEl?.currentTime || 0;
                    console.log('[VideoSection] slideCloseTimer firing — audioDuration:', dur, 'currentTime:', ct.toFixed(2), 'diff:', (dur - ct).toFixed(2));
                    if (dur > 0 && (dur - ct) > 1) {
                      // Aún faltan >1s de audio; no cerrar, esperar al onEnded
                      console.log('[VideoSection] slideCloseTimer skipped — audio aún reproduce');
                      return;
                    }
                    stopSlide();
                    resumeAfterSlide();
                  }, (el.duration + pad) * 1000);
                  console.log('[VideoSection] slideCloseTimer scheduled at', el.duration, '+', pad, '=', (el.duration + pad), 's');
                  try {
                    const iframe = document.querySelector('.video-universe iframe') as HTMLIFrameElement | null;
                    if (iframe && iframe.contentWindow) {
                      iframe.contentWindow.postMessage({ type: 'SET_AUDIO_DURATION', duration: el.duration }, '*');
                    }
                  } catch (err) {}
                }
              }}
              onTimeUpdate={(e) => {
                const el = e.currentTarget;
                // Fade out del slide en los 0.5s finales del audio
                if ((el.duration - el.currentTime <= 0.5) && !slideFadeOut && el.duration > 0) {
                  setSlideFadeOut(true);
                }
                try {
                  const iframe = document.querySelector('.video-universe iframe') as HTMLIFrameElement | null;
                  if (iframe && iframe.contentWindow) {
                    iframe.contentWindow.postMessage({
                      type: 'AUDIO_TIME_UPDATE',
                      currentTime: el.currentTime,
                      duration: el.duration || 0
                    }, '*');
                  }
                } catch (err) {}
              }}
              onEnded={() => {
                console.log('[Audio-Ended] →', {
                  isHtmlSlideActive,
                  isNewsSlide,
                  isNewsImageAudio,
                  currentTime: audioRef.current?.currentTime,
                  duration: audioRef.current?.duration,
                  paused: audioRef.current?.paused,
                  networkState: audioRef.current?.networkState
                });
                if (isHtmlSlideActive || isNewsSlide || isNewsImageAudio) {
                  // Cancelar cualquier timer pendiente; onEnded es la fuente de verdad.
                  if (slideCloseTimerRef.current) clearTimeout(slideCloseTimerRef.current);
                  stopSlide();
                  resumeAfterSlide();
                } else {
                  console.log('[Audio-Ended] → SKIP (no es slide activo)');
                }
              }}
              onError={(e) => {
                const audioEl = audioRef.current;
                console.error("[VideoSection] Audio error — code:", (e.target as HTMLAudioElement).error?.code, "mediaError:", audioEl?.error, {
                  currentTime: audioEl?.currentTime,
                  duration: audioEl?.duration,
                  networkState: audioEl?.networkState
                });
                // Si hay error de carga (CORS, red, archivo truncado), cerramos el slide
                // para no dejarlo colgado indefinidamente sin audio.
                if (slideCloseTimerRef.current) clearTimeout(slideCloseTimerRef.current);
                stopSlide();
                resumeAfterSlide();
              }}
            />

            {/* === PERSISTENT INTRO OVERLAY === */}
            <div
              className={cn(
                "absolute inset-0 z-[999] bg-black transition-opacity duration-300",
                (isPreRollOverlayActive && overlayIntroVideo && !isIntroFadingOut)
                  ? "opacity-100"
                  : "opacity-0 invisible pointer-events-none"
              )}
            >
              {overlayIntroVideo?.url && (
                <video
                  ref={introVideoRef}
                  src={overlayIntroVideo.url}
                  autoPlay
                  playsInline
                  muted
                  className="w-full h-full object-cover"
                  onTimeUpdate={handleIntroTimeUpdate}
                  onLoadedData={() => {
                    // Watchdog: si la intro carga pero en 20s no termina, forzar finishIntro
                    if (introWatchdogRef.current) clearTimeout(introWatchdogRef.current);
                    introWatchdogRef.current = setTimeout(() => {
                      console.warn('[VideoSection] Intro watchdog: forzando finishIntro()');
                      finishIntro();
                    }, 20000);
                  }}
                  onEnded={() => {
                    if (isInitialLoadRef.current) {
                      isInitialLoadRef.current = false; // El primer video ya pasó su fase crítica de intro
                    }
                    if (introWatchdogRef.current) clearTimeout(introWatchdogRef.current);
                    finishIntro();
                  }}
                  onError={(e) => {
                    console.error("Intro Error:", e);
                    if (introWatchdogRef.current) clearTimeout(introWatchdogRef.current);
                    finishIntro();
                  }}
                />
              )}
            </div>

            {
              (!isPlaying) && !isLocalIntro && !playBackgroundEarly && !isHtmlSlideActive && (
                <Image
                  src={thumbnailSrc}
                  alt="Fondo"
                  fill
                  className="absolute inset-0 z-10 object-contain opacity-60"
                  priority
                  onError={() => setThumbnailSrc('data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=')}
                />
              )
            }

            <AnimatePresence>
              {isNewsIntroActive && (
                <motion.div
                  key="news-intro"
                  initial={{ opacity: 1 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.5 }}
                  className="absolute inset-0 z-[998] bg-black"
                >
                  <video
                    src="/videos_intro/noticias.mp4?v=20b"
                    autoPlay
                    playsInline
                    className="w-full h-full object-contain"
                    onEnded={() => {
                      setIsNewsIntroActive(false);
                      try {
                        const iframe = document.querySelector('.video-universe iframe') as HTMLIFrameElement | null;
                        if (iframe && iframe.contentWindow) {
                          iframe.contentWindow.postMessage({ type: 'START_NEWS_PLAYBACK' }, '*');
                        }
                      } catch (err) {}
                    }}
                    onError={() => {
                      setIsNewsIntroActive(false);
                      try {
                        const iframe = document.querySelector('.video-universe iframe') as HTMLIFrameElement | null;
                        if (iframe && iframe.contentWindow) {
                          iframe.contentWindow.postMessage({ type: 'START_NEWS_PLAYBACK' }, '*');
                        }
                      } catch (err) {}
                    }}
                  />
                </motion.div>
              )}

              {areCinematicBarsActive && !isNewsContent && (
                <motion.div
                  key="cinematic-bar-top-solid"
                  className="absolute top-0 left-0 right-0 h-[14%] bg-black z-[45] pointer-events-auto"
                  initial={{ y: 0 }}
                  animate={{ y: 0 }}
                  exit={{ y: "-100%" }}
                  transition={{ duration: 1.2, ease: "easeInOut" }}
                />
              )}
              {areCinematicBarsActive && !isNewsContent && (
                <motion.div
                  key="cinematic-bar-top-gradient"
                  className="absolute top-0 left-0 right-0 h-[35%] bg-gradient-to-b from-black via-black/90 to-transparent z-[45] pointer-events-auto"
                  initial={{ opacity: 1 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 2.0, ease: "easeOut" }}
                />
              )}
              {areCinematicBarsActive && !isNewsContent && (
                <motion.div
                  key="cinematic-bar-bottom-solid"
                  className="absolute bottom-0 left-0 right-0 h-[14%] bg-black z-[45] pointer-events-auto"
                  initial={{ y: 0 }}
                  animate={{ y: 0 }}
                  exit={{ y: "100%" }}
                  transition={{ duration: 1.2, ease: "easeInOut" }}
                />
              )}
              {areCinematicBarsActive && !isNewsContent && (
                <motion.div
                  key="cinematic-bar-bottom-gradient"
                  className="absolute bottom-0 left-0 right-0 h-[35%] bg-gradient-to-t from-black via-black/90 to-transparent z-[45] pointer-events-auto"
                  initial={{ opacity: 1 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 2.0, ease: "easeOut" }}
                />
              )}
            </AnimatePresence>
          </div>

          {/* === ANTI-GRAVITY UI LAYER (STATIC & PRESERVED) === */}
          <AntiGravityLayer areCinematicBarsActive={areCinematicBarsActive}>

            {isNewsContent && !isNewsSlide && !isHtmlSlideActive && (
              <>
                <div className="absolute inset-x-0 top-0 top-safe-area z-[50] p-4 bg-gradient-to-b from-black/80 to-transparent pointer-events-none">
                  <div className="bg-black/60 backdrop-blur-md px-3 py-1.5 rounded-lg border border-white/10 inline-block max-w-[90%] md:max-w-[70%] shadow-2xl">
                    <h2 className="text-white text-base md:text-xl font-bold leading-tight drop-shadow-lg break-words">
                      {displayTitle}
                    </h2>
                  </div>
                </div>

                <div className="absolute inset-x-0 bottom-0 z-[50] pointer-events-auto h-8 bg-black/80 backdrop-blur-md border-t border-white/10 flex items-center">
                  <NewsTicker tickerTexts={[displaySubtitle || '']} />
                </div>
              </>
            )}

            {!isNewsSlide && !isHtmlSlideActive && <WeatherOverlay />}

            <AnimatePresence>
              {showControls && !isHtmlSlideActive && !isLocalIntro && !isPreRollOverlayActive && (
                <motion.div key="controls" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="absolute bottom-0 left-0 right-0 w-full z-[51] pointer-events-auto">
                  <CustomControls onToggleFullScreen={toggleFullScreen} isFullScreen={isFullScreen} />
                </motion.div>
              )}

              {!isPlaying && !isHtmlSlideActive && !isLocalIntro && !playBackgroundEarly && currentVideo && (
                <motion.div
                  key="play"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="absolute inset-0 flex items-center justify-center z-50 cursor-pointer pointer-events-auto"
                  onClick={() => setIsPlaying(true)}
                >
                  <div className="p-4 bg-black/40 rounded-full border border-white backdrop-blur-sm"><Play size={38} className="text-white/80" fill="white" strokeWidth={1.35} /></div>
                </motion.div>
              )}
            </AnimatePresence>

          </AntiGravityLayer>
        </div>
      </div >
      {viewMode === 'diario' && <VideoTitleBar className="mt-0 rounded-t-none border-t-0" />}

      {/* Modal de Slide Interactivo con Voz Rioplatense */}
      {isSlideOpen && currentSlide?.url && (
        <NewsSlidePlayer 
          slideUrl={currentSlide.url} 
          onClose={closeSlide} 
        />
      )}
    </div >
  );

};

export default VideoSection;