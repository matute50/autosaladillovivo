'use client';

import { useRef, useState, useEffect, useCallback } from 'react';
import ReactPlayer from 'react-player';
import { useIsPresent } from 'framer-motion';
import { usePlayerStore } from '@/store/usePlayerStore';
import { useVolumeStore } from '@/store/useVolumeStore';
import { isYouTubeVideo } from '@/lib/utils';

interface VideoPlayerProps {
  videoUrl: string;
  autoplay?: boolean;
  onClose?: () => void;
  onProgress?: (state: { playedSeconds: number, loadedSeconds: number }) => void;
  onDuration?: (duration: number) => void;
  startAt?: number;
  imageUrl?: string;
  audioUrl?: string | null;
  id?: string; // Mutex ID (v23.5)
  playerVolume?: number;
  volumen_extra?: number;
  muted?: boolean; // New prop to force mute locally
}

export default function VideoPlayer({
  videoUrl,
  autoplay = true,
  onClose,
  onProgress,
  onDuration,
  startAt,
  playerVolume,
  volumen_extra = 1,
  audioUrl,
  muted: forceMuted, // Alias to avoid conflict with global isMuted
  id
}: VideoPlayerProps) {
  const { activeContentId } = usePlayerStore();
  const [isMounted, setIsMounted] = useState(false);
  const playerRef = useRef<ReactPlayer>(null);
  const hasSeeked = useRef(false);
  const [localVolume, setLocalVolume] = useState(0);
  const isFadingIn = useRef(false);
  const [isPlayingInternal, setIsPlayingInternal] = useState(false);
  const [isFadingOut, setIsFadingOut] = useState(false);
  const durationRef = useRef(0);
  const playStartTimeRef = useRef<number | null>(null);
  const [shouldPlay, setShouldPlay] = useState(autoplay);
  const [internalMuted, setInternalMuted] = useState(true);
  const [hasStartedPlaying, setHasStartedPlaying] = useState(false);
  const sessionStartPlayedSecondsRef = useRef<number | null>(null);
  const audioRef = useRef<HTMLAudioElement>(null);

  // Consumimos el estado global del volumen
  const { volume, isMuted } = useVolumeStore();

  const fadeIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const fadeOutIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const kickIntervalRef = useRef<NodeJS.Timeout | null>(null);

  const isPresent = useIsPresent();
  const isPresentRef = useRef(true);

  useEffect(() => {
    setIsMounted(true);
  }, []);

  // ATOMIC MUTEX: Only play if this is the active content ID (if ID provided)
  const isMutexActive = !id || !activeContentId || id === activeContentId;
  const finalPlaying = shouldPlay && isMutexActive;
  // finalMuted force rules:
  // 1. Must be muted if the store says so
  // 2. Must be muted if forced by parent (intro phase)
  // 3. Must be muted if not the active player in mutex
  // 4. MUST be muted if it hasn't successfully started playing yet (Golden Rule for Autoplay)
  const finalMuted = isMuted || forceMuted || !isMutexActive || !shouldPlay || !hasStartedPlaying || internalMuted;


  // Sync shouldPlay strictly when autoplay prop changes
  useEffect(() => {
    setShouldPlay(autoplay);
  }, [autoplay]);

  // Handle internal muted state transition
  useEffect(() => {
    if (hasStartedPlaying) {
      // Once it started, we follow the store's muted state
      setInternalMuted(isMuted);
    } else {
      // Before starting, we MUST be muted to satisfy browser policies
      setInternalMuted(true);
    }
  }, [hasStartedPlaying, isMuted]);

  // Command Sync (v24.1) - Extreme manual enforcement for YouTube Iframe
  useEffect(() => {
    if (playerRef.current && isMounted) {
      const internal = playerRef.current.getInternalPlayer();
      if (internal) {
        if (finalPlaying) {

          if (typeof internal.playVideo === 'function') internal.playVideo();
          if (typeof internal.unMute === 'function') internal.unMute();
          if (typeof internal.setVolume === 'function') internal.setVolume(localVolume * 100);
        } else {

          if (typeof internal.pauseVideo === 'function') internal.pauseVideo();
          if (typeof internal.mute === 'function') internal.mute();
          // Force volume 0 even if not muted
          if (typeof internal.setVolume === 'function') internal.setVolume(0);
        }
      }
    }
  }, [finalPlaying, isMounted, id, localVolume]);

  // Sync external audio
  useEffect(() => {
    if (audioRef.current) {
      if (finalPlaying) {
        audioRef.current.play().catch(() => { });
        audioRef.current.muted = finalMuted;
      } else {
        audioRef.current.pause();
        audioRef.current.muted = true;
      }
    }
  }, [finalPlaying, finalMuted]);

  // RESET STATE ON VIDEO SWAP (Smart Slots Support)
  useEffect(() => {
    // Cleanup any active intervals from previous video
    if (fadeIntervalRef.current) clearInterval(fadeIntervalRef.current);
    if (fadeOutIntervalRef.current) clearInterval(fadeOutIntervalRef.current);
    if (kickIntervalRef.current) clearInterval(kickIntervalRef.current);

    setLocalVolume(0);
    setIsFadingOut(false);
    playStartTimeRef.current = null;
    hasSeeked.current = false;
    sessionStartPlayedSecondsRef.current = null;
    setHasStartedPlaying(false); // Reset this state on video swap
    setInternalMuted(true); // Ensure it's muted on new video load

    if (startAt && startAt > 0 && playerRef.current) {
      playerRef.current.seekTo(startAt, 'seconds');
    }

    return () => {
      // --- CHEMICAL DEATH (v23.8) ---
      // Force kill internal YouTube processes before React unmounts
      if (playerRef.current) {
        const internal = playerRef.current.getInternalPlayer();
        if (internal) {
          try {
            if (typeof internal.pauseVideo === 'function') internal.pauseVideo();
            if (typeof internal.mute === 'function') internal.mute();
            // Try to stop video to free resources
            if (typeof internal.stopVideo === 'function') internal.stopVideo();
          } catch (e) {
            console.warn("Error during internal player cleanup:", e);
          }
        }
      }

      if (fadeIntervalRef.current) clearInterval(fadeIntervalRef.current);
      if (fadeOutIntervalRef.current) clearInterval(fadeOutIntervalRef.current);
      if (kickIntervalRef.current) clearInterval(kickIntervalRef.current);
    };
  }, [videoUrl, startAt]);

  // Base volume logic
  const baseVolume = typeof playerVolume === 'number' ? playerVolume : volume;
  const effectiveVolume = Math.min(1, baseVolume * (volumen_extra || 1));

  useEffect(() => {
    const clampedVolume = Math.max(0, Math.min(1, effectiveVolume));
    if (!isFadingIn.current && !isFadingOut && isPresent && localVolume !== clampedVolume) {
      setLocalVolume(clampedVolume);
    }
  }, [effectiveVolume, localVolume, isFadingOut, isPresent]);

  // Sync Fade Out when and component is leaving (AnimatePresence exit)
  useEffect(() => {
    if (!isPresent && isPresentRef.current) {
      // Component is starting its exit transition
      setIsFadingOut(true);
      const fadeDuration = 750; // 0.75s per user request
      const fadeSteps = 15;
      const decrement = localVolume / fadeSteps;
      let currentFadeVolume = localVolume;
      let step = 0;

      if (fadeOutIntervalRef.current) clearInterval(fadeOutIntervalRef.current);
      fadeOutIntervalRef.current = setInterval(() => {
        step++;
        currentFadeVolume = Math.max(0, currentFadeVolume - decrement);
        setLocalVolume(currentFadeVolume);
        if (step >= fadeSteps || currentFadeVolume <= 0) {
          if (fadeOutIntervalRef.current) clearInterval(fadeOutIntervalRef.current);
          setLocalVolume(0);
        }
      }, fadeDuration / fadeSteps);
    }
    isPresentRef.current = isPresent;
  }, [isPresent, localVolume]);

  // Sync Fade In when becoming unmuted or starts playing while unmuted (v25.1)
  const prevMutedRef = useRef(finalMuted);
  const prevPlayingRef = useRef(isPlayingInternal);

  useEffect(() => {
    const shouldStartFade = (
      (prevMutedRef.current && !finalMuted && isPlayingInternal) || // Case A: Unmuted while playing
      (!finalMuted && isPlayingInternal && !prevPlayingRef.current) // Case B: Starts playing while already unmuted
    );

    if (shouldStartFade && !isFadingIn.current) {
      isFadingIn.current = true;
      const fadeDuration = 1000;
      const fadeSteps = 20;
      const targetVol = effectiveVolume;
      const increment = targetVol / fadeSteps;
      let currentVol = 0;
      let step = 0;

      if (fadeIntervalRef.current) clearInterval(fadeIntervalRef.current);
      fadeIntervalRef.current = setInterval(() => {
        step++;
        currentVol = Math.min(targetVol, currentVol + increment);
        setLocalVolume(currentVol);
        if (step >= fadeSteps) {
          if (fadeIntervalRef.current) clearInterval(fadeIntervalRef.current);
          isFadingIn.current = false;
          setLocalVolume(targetVol);
        }
      }, fadeDuration / fadeSteps);
    }
    prevMutedRef.current = finalMuted;
    prevPlayingRef.current = isPlayingInternal;
  }, [finalMuted, isPlayingInternal, effectiveVolume]);

  // Autoplay Kick for YouTube (v25.4)
  useEffect(() => {
    if (isMounted && finalPlaying && isYouTubeVideo(videoUrl)) {
      kickIntervalRef.current = setInterval(() => {
        if (playerRef.current) {
          try {
            const internal = playerRef.current.getInternalPlayer();
            if (internal && typeof internal.getPlayerState === 'function') {
              const state = internal.getPlayerState();
              // Si está pausado (2) o cued (5) o no iniciado (-1) o terminado (0) mientras debería sonar: KICK!
              if (state === 2 || state === 5 || state === -1 || state === 0) {
                internal.playVideo();
              }
            }
          } catch (e) {
            // Silencio en errores de API de YouTube
          }
        }
      }, 1000);
      return () => {
        if (kickIntervalRef.current) clearInterval(kickIntervalRef.current);
      }
    }
  }, [isMounted, finalPlaying, videoUrl]);

  const handleProgressInternal = (state: { playedSeconds: number, loadedSeconds: number }) => {
    if (onProgress) onProgress(state);

    if (id !== 'live-stream' && isYouTubeVideo(videoUrl) && durationRef.current > 0 && !isFadingOut) {
      const timeLeft = durationRef.current - state.playedSeconds;
      if (timeLeft <= 0.75 && timeLeft > 0) { // Adjusted to 0.75s (v27)
        setIsFadingOut(true);
        const fadeDuration = 750; // Adjusted to 0.75s (v27)
        const fadeSteps = 15;
        const decrement = localVolume / fadeSteps;
        let currentFadeVolume = localVolume;
        let step = 0;

        if (fadeOutIntervalRef.current) clearInterval(fadeOutIntervalRef.current);
        fadeOutIntervalRef.current = setInterval(() => {
          step++;
          currentFadeVolume = Math.max(0, currentFadeVolume - decrement);
          setLocalVolume(currentFadeVolume);
          if (step >= fadeSteps || currentFadeVolume <= 0) {
            if (fadeOutIntervalRef.current) clearInterval(fadeOutIntervalRef.current);
            setLocalVolume(0);
          }
        }, fadeDuration / fadeSteps);
      }
    }
  };

  const handleDurationInternal = (duration: number) => {
    durationRef.current = duration;
    if (onDuration) onDuration(duration);
  };

  const handleReady = useCallback(() => {
    if (finalPlaying && playerRef.current) {
      const internalPlayer = playerRef.current.getInternalPlayer();
      if (internalPlayer && typeof internalPlayer.playVideo === 'function') {
        internalPlayer.playVideo();
      }
    }
    if (startAt && startAt > 0 && playerRef.current) {
      playerRef.current.seekTo(startAt, 'seconds');
      hasSeeked.current = true;
    }
  }, [finalPlaying, startAt]);

  const handleError = useCallback((e: any) => {
    console.error("VideoPlayer Error:", videoUrl, e);
    if (onClose) onClose();
  }, [videoUrl, onClose]);

  if (!isMounted) return null;

  return (
    <div className="relative w-full h-full bg-black overflow-hidden">
      <div className="absolute inset-0 z-10 bg-transparent" />
      <div className="w-full h-full transform-gpu overflow-hidden">
        <ReactPlayer
          ref={playerRef}
          url={videoUrl}
          playing={finalPlaying}
          controls={false}
          volume={finalMuted ? 0 : localVolume}
          muted={finalMuted}
          width="100%"
          height="100%"
          progressInterval={500}
          onEnded={() => {
            // Solo permitir que onEnded dispare onClose si el jugador está reproduciendo activamente.
            // Cuando hay un slide de noticias activo, finalPlaying es false y no debemos
            // reanudar/interrumpir el reproductor principal (evita que YouTube se reinicie).
            if (finalPlaying && id !== 'live-stream' && onClose) {
              onClose();
            }
          }}
          onProgress={handleProgressInternal}
          onDuration={handleDurationInternal}
          onReady={handleReady}
          onError={handleError}
          onPlay={() => {
            setHasStartedPlaying(true);
            setIsPlayingInternal(true);
            if (playStartTimeRef.current === null) playStartTimeRef.current = Date.now();
            if (startAt && startAt > 0 && !hasSeeked.current && playerRef.current) {
              playerRef.current.seekTo(startAt, 'seconds');
              hasSeeked.current = true;
            }
          }}
          onPause={() => {
            // Si el video se pausa solo en los primeros segundos de vida, 
            // es probable que sea el navegador bloqueando el autoplay.
            // NO cambiamos el estado global de isPlaying para no mostrar el botón de play.
            if (finalPlaying) {
              const internal = playerRef.current?.getInternalPlayer();
              if (internal && typeof internal.playVideo === 'function') {
                setTimeout(() => internal.playVideo(), 500);
              }
            }
            setIsPlayingInternal(false);
          }}
          config={{
            youtube: {
              playerVars: {
                showinfo: 0,
                modestbranding: 1,
                rel: 0,
                playsinline: 1,
                controls: 0,
                disablekb: 1,
                fs: 0,
                iv_load_policy: 3,
                cc_load_policy: 0,
                enablejsapi: 1,
                mute: 1,
                autoplay: 1
              }
            }
          }}
        />

        {audioUrl && (
          <audio
            ref={audioRef}
            src={audioUrl}
            autoPlay={finalPlaying}
            muted={finalMuted}
            className="hidden"
          />
        )}
      </div>
    </div>
  );
}