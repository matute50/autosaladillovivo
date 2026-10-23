// src/app/noticia/[slug]/NoticiaClient.tsx
"use client";

import Image from 'next/image';
import React, { useState, useRef, useEffect } from 'react';
import { Play, Pause, Volume2, RotateCcw } from 'lucide-react';
import { Article } from '@/lib/types';

export default function NoticiaClient({ article }: { article: Article }) {
  const [isPlaying, setIsPlaying] = useState(false);
  const [progress, setProgress] = useState(0);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const audioRef = useRef<HTMLAudioElement>(null);
  const progressBarRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;

    const handleTimeUpdate = () => {
      if (audio.duration && audio.duration > 0) {
        setProgress((audio.currentTime / audio.duration) * 100);
        setCurrentTime(audio.currentTime);
      }
    };

    const handleLoadedMetadata = () => {
      if (audio.duration && !isNaN(audio.duration)) {
        setDuration(audio.duration);
      }
    };

    const handleEnded = () => {
      setIsPlaying(false);
      setProgress(0);
      setCurrentTime(0);
    };

    const handlePlay = () => setIsPlaying(true);
    const handlePause = () => setIsPlaying(false);

    audio.addEventListener('timeupdate', handleTimeUpdate);
    audio.addEventListener('loadedmetadata', handleLoadedMetadata);
    audio.addEventListener('ended', handleEnded);
    audio.addEventListener('play', handlePlay);
    audio.addEventListener('pause', handlePause);

    return () => {
      audio.removeEventListener('timeupdate', handleTimeUpdate);
      audio.removeEventListener('loadedmetadata', handleLoadedMetadata);
      audio.removeEventListener('ended', handleEnded);
      audio.removeEventListener('play', handlePlay);
      audio.removeEventListener('pause', handlePause);
    };
  }, []);

  const togglePlay = () => {
    const audio = audioRef.current;
    if (!audio) return;

    if (isPlaying) {
      audio.pause();
    } else {
      audio.play().catch(console.error);
    }
  };

  const handleSeek = (e: React.MouseEvent<HTMLDivElement>) => {
    const bar = progressBarRef.current;
    const audio = audioRef.current;
    if (!bar || !audio || !audio.duration) return;

    const rect = bar.getBoundingClientRect();
    const clickX = e.clientX - rect.left;
    const clickRatio = Math.max(0, Math.min(1, clickX / rect.width));
    const newTime = clickRatio * audio.duration;
    audio.currentTime = newTime;
    setCurrentTime(newTime);
    setProgress(clickRatio * 100);
  };

  const formatTime = (secs: number): string => {
    if (isNaN(secs) || secs < 0) return "0:00";
    const minutes = Math.floor(secs / 60);
    const seconds = Math.floor(secs % 60);
    return `${minutes}:${seconds < 10 ? '0' : ''}${seconds}`;
  };

  // Helper para procesar la URL de la imagen
  const getSafeImageUrl = (inputUrl: string | undefined | null): string => {
    const cleanUrl = (inputUrl || '').trim();

    if (!cleanUrl) {
      return 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=';
    }

    if (cleanUrl.includes('youtube.com') || cleanUrl.includes('youtu.be')) {
      return cleanUrl;
    }

    if (cleanUrl.match(/^(http|https):\/\//)) {
      return cleanUrl;
    }

    const mediaUrl = process.env.NEXT_PUBLIC_MEDIA_URL || 'https://media.saladillovivo.com.ar';
    return `${mediaUrl}${cleanUrl.startsWith('/') ? '' : '/'}${cleanUrl}`;
  };

  const finalImageUrl = getSafeImageUrl(article.imageUrl);

  return (
    <main className="container mx-auto max-w-4xl px-4 py-8">
      <article>
        {/* Categoría / Fecha */}
        <div className="flex items-center gap-3 text-sm font-medium text-sky-600 dark:text-sky-400 mb-2">
          {article.categoria && (
            <span className="uppercase tracking-wider px-2 py-0.5 bg-sky-50 dark:bg-sky-950/50 rounded">
              {article.categoria}
            </span>
          )}
          {article.fecha && (
            <time className="text-gray-500 dark:text-gray-400">
              {new Date(article.fecha).toLocaleDateString('es-AR', { day: 'numeric', month: 'long', year: 'numeric' })}
            </time>
          )}
        </div>

        {/* Título */}
        <h1 className="text-3xl font-bold leading-tight text-gray-900 dark:text-white md:text-4xl mb-4">
          {article.titulo}
        </h1>

        {/* Reproductor de Audio si la noticia tiene audio_url */}
        {article.audio_url && (
          <div className="audio-player mb-6">
            <button
              onClick={togglePlay}
              className="play-button"
              aria-label={isPlaying ? "Pausar narración en audio" : "Reproducir narración en audio"}
              type="button"
            >
              {isPlaying ? <Pause size={20} /> : <Play size={20} className="ml-0.5" />}
            </button>

            <div className="progress-bar-container">
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-semibold text-gray-700 dark:text-gray-200 flex items-center gap-1.5">
                  <Volume2 size={15} className="text-sky-600 dark:text-sky-400 animate-pulse" />
                  Escuchar noticia con locución IA
                </span>
                <span className="audio-time">
                  {formatTime(currentTime)} / {formatTime(duration || 0)}
                </span>
              </div>

              <div
                ref={progressBarRef}
                onClick={handleSeek}
                className="progress-bar"
                role="progressbar"
                aria-valuenow={progress}
                aria-valuemin={0}
                aria-valuemax={100}
              >
                <div
                  className="progress-fill"
                  style={{ width: `${progress}%` }}
                />
              </div>
            </div>

            <audio
              ref={audioRef}
              src={article.audio_url}
              preload="metadata"
            />
          </div>
        )}

        {/* Imagen Destacada */}
        {article.imageUrl && (
          <div
            className="max-w-2xl mx-auto rounded-lg shadow-lg mb-6 relative overflow-hidden"
            style={{ aspectRatio: '16 / 9' }}
          >
            <Image
              src={finalImageUrl}
              alt={article.titulo}
              fill
              className="w-full h-full object-cover rounded-lg"
              priority
            />
            <div className="absolute inset-0 z-10 pointer-events-none rounded-lg bg-black/10 [mask-image:radial-gradient(circle,transparent_30%,black_100%)] shadow-[inset_0_0_120px_rgba(0,0,0,0.8)]" />
            <div className="absolute inset-x-0 top-0 h-[40%] bg-gradient-to-b from-black/95 via-black/40 to-transparent z-10 pointer-events-none rounded-t-lg" />
          </div>
        )}

        {/* Cuerpo de la noticia */}
        {article.contenido ? (
          <div
            className="prose prose-lg dark:prose-invert max-w-none text-gray-800 dark:text-gray-200 leading-relaxed"
            dangerouslySetInnerHTML={{ __html: article.contenido }}
          />
        ) : (
          <p className="text-lg text-gray-800 dark:text-gray-300 leading-relaxed">{article.description}</p>
        )}
      </article>
    </main>
  );
}
