import { create } from 'zustand';
import { devtools } from 'zustand/middleware';

// Types
export type SlideType = 'html' | 'video' | 'image';

export interface SlideData {
  url: string;
  type?: SlideType;
  duration?: number;
  title?: string;
  subtitle?: string;
  audioUrl?: string | null;
  /** P2-fix: true si el HTML ya embebe su propio <audio>. */
  embedsAudio?: boolean;
}

export type CurrentSlideValue = SlideData | null;

export interface NewsPlayerState {
  currentSlide: CurrentSlideValue;
  isSlideOpen: boolean;
  isPlaying: boolean;
  isNewsIntroActive: boolean;

  // Actions
  playSlide: (slide: SlideData | string) => void;
  stopSlide: () => void;
  setIsNewsIntroActive: (active: boolean) => void;
  openSlide: (slideUrl: string) => void;
  closeSlide: () => void;
}

export const useNewsPlayerStore = create<NewsPlayerState>()(
  devtools(
    (set) => ({
      // Estado inicial
      currentSlide: null,
      isSlideOpen: false,
      isPlaying: false,
      isNewsIntroActive: false,

      // Acciones
      playSlide: (slide) => {
        set({
          currentSlide: typeof slide === 'string' ? { url: slide, type: 'html' } : slide,
          isPlaying: true,
          isNewsIntroActive: true, // activa el video introductorio antes del slide
        });
      },

      stopSlide: () => {
        set({
          isPlaying: false,
          isNewsIntroActive: false,
        });
      },

      setIsNewsIntroActive: (active) => {
        set({ isNewsIntroActive: active });
      },

      openSlide: (slideUrl) => {
        set({
          currentSlide: { url: slideUrl, type: 'html' },
          isSlideOpen: true,
        });
      },

      closeSlide: () => {
        set({ isSlideOpen: false });
      },
    }),
    { name: 'NewsPlayerStore' }
  )
);
