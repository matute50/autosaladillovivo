'use client';

import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import VideoIntro from './VideoIntro';
import VideoPlayer from './VideoPlayer';
import { SlideMedia, Article } from '@/lib/types';
import { usePlayerStore } from '@/store/usePlayerStore';

interface ReproductorMultimediaProps {
  onComplete: () => void;
  videoToPlay?: SlideMedia | null;
}

export default function ReproductorMultimedia({ onComplete, videoToPlay }: ReproductorMultimediaProps) {
  const { currentVideo, isPlaying } = usePlayerStore();
  const videoPlayerRef = React.useRef<HTMLVideoElement>(null!);

  const handleVideoEnd = () => {
    onComplete();
  };

  return (
    <div
      className="relative w-full max-w-4xl aspect-video bg-black/20 backdrop-blur-sm overflow-hidden rounded-xl shadow-2xl dark:shadow-none mx-auto"
      aria-live="polite"
    >
      {/* Cinematic Bars Overlay */}
      <AnimatePresence>
        {!isPlaying && !videoToPlay && (
          <>
            <motion.div
              key="top-bar"
              className="absolute top-0 left-0 w-full h-[12%] bg-black z-50 pointer-events-none"
              initial={{ y: "-100%" }}
              animate={{ y: "0%" }}
              exit={{ y: "-100%" }}
              transition={{ duration: 0.5, ease: "easeInOut" }}
            />
            <motion.div
              key="bottom-bar"
              className="absolute bottom-0 left-0 w-full h-[12%] bg-black z-50 pointer-events-none"
              initial={{ y: "100%" }}
              animate={{ y: "0%" }}
              exit={{ y: "100%" }}
              transition={{ duration: 0.5, ease: "easeInOut" }}
            />
          </>
        )}
      </AnimatePresence>

      {videoToPlay ? (
        <VideoPlayer
          videoUrl={videoToPlay?.url || ""}
          imageUrl={
            videoToPlay?.imageSourceUrl ||
            (videoToPlay as unknown as Article)?.imageUrl ||
            (videoToPlay as any)?.image_url ||
            videoToPlay?.imagen ||
            null
          }
          audioUrl={
            videoToPlay?.audioSourceUrl ||
            (videoToPlay as unknown as Article)?.audio_url ||
            (videoToPlay as any)?.audioUrl ||
            null
          }
          id={videoToPlay.id}
          autoplay={isPlaying}
          onClose={onComplete}
        />
      ) : (
        <motion.div
          key="intro"
          className="absolute inset-0 w-full h-full"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.5 }}
        >
          <VideoIntro
            onEnd={handleVideoEnd}
            videoSrc={currentVideo?.url || ""}
            videoRef={videoPlayerRef}
          />
        </motion.div>
      )}
    </div>
  );
}

