// src/hooks/useNewsSlideAudio.ts

import { useEffect, useRef, useState, useCallback } from 'react';
import { sendParentToIframe } from '@/utils/postMessageBridge';

export const useNewsSlideAudio = (
  isNewsSlide: boolean,
  currentSlideUrl: string | null,
  audioUrl: string | null,
  audioDuration: number,
  isMuted: boolean,
  volume: number,
  isHtmlSlideActive: boolean
) => {
  const audioRef = useRef<HTMLAudioElement>(null);
  const [audioDurationSec, setAudioDurationSec] = useState<number | null>(null);
  const [hasStartedAudio, setHasStartedAudio] = useState(false);
  const [slideFadeOut, setSlideFadeOut] = useState(false);
  const slideCloseTimerRef = useRef<NodeJS.Timeout | null>(null);

  const initializeAudio = useCallback(() => {
    if (!audioUrl || audioDurationSec === null) return;

    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.src = '';
    }

    const audioElement = new Audio();
    audioElement.src = audioUrl;
    audioElement.volume = isMuted ? 0 : volume;
    audioElement.muted = false;
    audioElement.preload = 'auto';
    audioElement.crossOrigin = 'anonymous';
    audioElement.playsInline = true;

    audioElement.addEventListener('loadedmetadata', () => {
      setAudioDurationSec(audioElement.duration);
      
      // Schedule slide close after audio ends + 5s buffer
      const closeTimer = setTimeout(() => {
        const remainingTime = audioElement.duration - audioElement.currentTime;
        if (remainingTime > 1) {
          // Still more than 1s of audio left
          return;
        }
        // Close the slide
        stopSlide();
        resumeAfterSlide();
      }, (audioElement.duration + 5) * 1000);

      // Cleanup on unmount
      return () => clearTimeout(slideCloseTimerRef.current);
    }, { once: true });

    // Handle audio time updates
    const updateTime = (e: Event) => {
      const target = e.target as HTMLAudioElement;
      setAudioDurationSec(target.duration);
      
      // Fade out slide in last 0.5s of audio
      if (target.duration - target.currentTime <= 0.5 && target.duration > 0) {
        setSlideFadeOut(true);
      }
      
      // Send message to iframe
      if (iframe && iframe.contentWindow) {
        iframe.contentWindow.postMessage({
          type: 'AUDIO_TIME_UPDATE',
          payload: {
            currentTime: target.currentTime,
            duration: target.duration || 0
          }
        }, '*');
      }
    };

    audioElement.addEventListener('timeupdate', updateTime);
    audioElement.addEventListener('ended', () => {
      setHasStartedAudio(false);
      if (slideCloseTimerRef.current) clearTimeout(slideCloseTimerRef.current);
      stopSlide();
      resumeAfterSlide();
    });

    audioRef.current = audioElement;
    setHasStartedAudio(true);
  }, [audioUrl, isMuted, volume, isHtmlSlideActive]);

  const stopSlide = useCallback(() => {
    // Stop the slide playback
    if (slideFadeOut) {
      setSlideFadeOut(false);
    }
    // Send message to close slide
    sendParentToIframe({ type: 'SLIDE_CLOSE', payload: {} });
  }, []);

  const stopSlideAndResume = useCallback(() => {
    stopSlide();
    // Resume the original video
    // This would be handled by the parent component's resumeAfterSlide function
  }, []);

  useEffect(() => {
    if (isNewsSlide && currentSlideUrl && audioUrl && audioDuration > 0) {
      initializeAudio();
    } else {
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current.src = '';
      }
      setHasStartedAudio(false);
      setAudioDurationSec(null);
      setSlideFadeOut(false);
    }
  }, [isNewsSlide, currentSlideUrl, audioUrl, audioDuration, isMuted, volume, isHtmlSlideActive]);

  return {
    hasStartedAudio,
    audioDurationSec,
    slideFadeOut,
    stopSlide,
  };
};