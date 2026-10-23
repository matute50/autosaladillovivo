import { create } from 'zustand';
import { devtools } from 'zustand/middleware';

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
    openSlide: (slideUrl: string) => void;
    closeSlide: () => void;
    playSlide: (slide: SlideData | string) => void;
    stopSlide: () => void;
    setIsNewsIntroActive: (active: boolean) => void;
}

export const useNewsPlayerStore = create<NewsPlayerState>()(
    devtools(
        (set) => ({
            currentSlide: null,
            isSlideOpen: false,
            isPlaying: false,
            isNewsIntroActive: false,

            openSlide: (slideUrl: string) => set({
                currentSlide: {
                    url: slideUrl,
                    type: 'html',
                    embedsAudio: true
                },
                isSlideOpen: true,
                isPlaying: true,
                isNewsIntroActive: true
            }),

            closeSlide: () => set({
                currentSlide: null,
                isSlideOpen: false,
                isPlaying: false,
                isNewsIntroActive: false
            }),

            playSlide: (slide) => {
                if (typeof slide === 'string') {
                    set({
                        currentSlide: {
                            url: slide,
                            type: 'html',
                            embedsAudio: true
                        },
                        isSlideOpen: true,
                        isPlaying: true,
                        isNewsIntroActive: true
                    });
                } else {
                    const normalizedSlide: SlideData = {
                        ...slide,
                        audioUrl: slide.audioUrl === undefined ? null : slide.audioUrl,
                        embedsAudio: slide.embedsAudio ?? (slide.type === 'html')
                    };
                    set({
                        currentSlide: normalizedSlide,
                        isSlideOpen: true,
                        isPlaying: true,
                        isNewsIntroActive: true
                    });
                }
            },

            stopSlide: () => set({
                currentSlide: null,
                isSlideOpen: false,
                isPlaying: false,
                isNewsIntroActive: false
            }),

            setIsNewsIntroActive: (active: boolean) => set({ isNewsIntroActive: active }),
        }),
        { name: 'NewsPlayerStore' }
    )
);
