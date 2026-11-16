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
                    // Los slides HTML no tienen <audio> interno; el audio es
                    // centralizado por VideoSection.tsx via postMessage.
                    // Debe ser false para evitar montaje redundante.
                    embedsAudio: false
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
                            // Los slides HTML son centralizados por VideoSection.
                            embedsAudio: false
                        },
                        isSlideOpen: false,
                        isPlaying: true,
                        isNewsIntroActive: true
                    });
                } else {
                    const normalizedSlide: SlideData = {
                        ...slide,
                        type: slide.type || 'html',
                        audioUrl: slide.audioUrl === undefined ? null : slide.audioUrl,
                        // Default: slides HTML son centralizados, no embebidos.
                        embedsAudio: slide.embedsAudio ?? false
                    };
                    set({
                        currentSlide: normalizedSlide,
                        isSlideOpen: false,
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