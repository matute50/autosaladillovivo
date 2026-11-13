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
  openSlide: (slideUrl: string) => void;
  closeSlide: () => void;
  playSlide: (slide: SlideData | string) => void;
  stopSlide: () => void;
  setIsNewsIntroActive: (active: boolean) => void;
}

// Initial state
const initialState: NewsPlayerState = {
  currentSlide: null,
  isSlideOpen: false,
  isPlaying: false,
  isNewsIntroActive: false,
};

export const useNewsPlayerStore = create<NewsPlayerState>()(
  devtools(
    (set) => ({
      ...initialState,
    })
  )
);