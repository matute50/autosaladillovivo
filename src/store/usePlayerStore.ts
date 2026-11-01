import { create } from 'zustand';
import { devtools } from 'zustand/middleware';
import { getVideosForHome, getNewRandomVideo, getVideoByUrl } from '@/lib/data';
import { SlideMedia } from '@/lib/types';

import { useNewsPlayerStore } from './useNewsPlayerStore';
import { useVolumeStore } from './useVolumeStore';

const INTRO_VIDEOS = [
    '/videos_intro/intro1.mp4',
    '/videos_intro/intro2.mp4',
    '/videos_intro/intro3.mp4',
    '/videos_intro/intro4.mp4',
    '/videos_intro/intro5.mp4',
];

type PlaybackSource = 'INTRO' | 'DB_RANDOM' | 'USER_SELECTED' | 'RESUMING';

interface PlayerState {
    currentVideo: SlideMedia | null;
    nextVideo: SlideMedia | null;
    playlist: SlideMedia[];
    isPlaying: boolean;
    viewMode: 'diario' | 'tv';
    streamStatus: any;

    // Zero-Branding States
    isPreRollOverlayActive: boolean;
    overlayIntroVideo: SlideMedia | null;
    isContentPlaying: boolean;

    // Refs equivalents
    playbackState: PlaybackSource;
    savedProgress: number;
    savedVideo: SlideMedia | null;
    savedVolume: number;
    lastKnownVolume: number;
    historyVolume: number;

    // Actions
    setViewMode: (mode: 'diario' | 'tv') => void;
    setIsPlaying: (isPlaying: boolean) => void;
    togglePlayPause: () => void;
    setStreamStatus: (status: any) => void;

    playMedia: (media: SlideMedia) => void;
    playSpecificVideo: (media: SlideMedia, currentVolume?: number, setVolume?: (v: number) => void) => void;
    playTemporaryVideo: (media: SlideMedia, currentVolume?: number, setVolume?: (v: number) => void) => void;
    playLiveStream: (streamData: any) => void;
    playNextVideoInQueue: () => void;
    loadInitialPlaylist: (videoUrlToPlay: string | null) => Promise<void>;
    handleOnEnded: (setVolume?: (v: number) => void, unmute?: () => void) => Promise<void>;

    // Resume Logic for Slides
    pauseForSlide: (currentTime?: number) => void;
    resumeAfterSlide: () => void;

    saveCurrentProgress: (seconds: number, volume: number) => void;
    playRandomSequence: () => Promise<void>;

    // Helpers
    getRandomIntro: () => SlideMedia;
    fetchRandomDbVideo: (excludeId?: string, excludeCategory?: string) => Promise<SlideMedia | null>;
    preloadNextVideo: (currentId: string) => Promise<void>;
    finishIntro: () => void;
    activeContentId: string | null;
    setActiveContentId: (id: string | null) => void;
}

// Next intro video preloaded
let nextDataVideo: SlideMedia | null = null;

export const usePlayerStore = create<PlayerState>()(
    devtools(
        (set, get) => ({
            currentVideo: null,
            nextVideo: null,
            playlist: [],
            isPlaying: true,
            viewMode: 'diario',
            streamStatus: null,
            isPreRollOverlayActive: false,
            overlayIntroVideo: null,
            isContentPlaying: false,

            playbackState: 'DB_RANDOM',
            savedProgress: 0,
            savedVideo: null,
            savedVolume: 1,
            lastKnownVolume: 1,
            historyVolume: 1,
            activeContentId: null,

            setActiveContentId: (id) => set({ activeContentId: id }),

            setViewMode: (mode) => set({ viewMode: mode }),
            setIsPlaying: (isPlaying) => set({ isPlaying }),

            togglePlayPause: () => set((state) => ({ isPlaying: !state.isPlaying })),
            setStreamStatus: (status) => set({ streamStatus: status }),

            getRandomIntro: () => {
                const randomIndex = Math.floor(Math.random() * INTRO_VIDEOS.length);
                const url = INTRO_VIDEOS[randomIndex];
                return {
                    id: `intro-${url}-${Date.now()}`,
                    nombre: 'ESPACIO PUBLICITARIO',
                    url,
                    categoria: 'Institucional',
                    createdAt: new Date().toISOString(),
                    type: 'video' as const,
                    imagen: '',
                    novedad: false
                };
            },

            fetchRandomDbVideo: async (excludeId, excludeCategory) => {
                try {
                    return await getNewRandomVideo(excludeId, excludeCategory);
                } catch (error) {
                    console.error("Error fetching DB video:", error);
                    return null;
                }
            },

            // User clicks a video in carousel
            playSpecificVideo: (media, currentVolume, setVolume) => {
                // Stop News Slide if active
                useNewsPlayerStore.getState().stopSlide();

                if (currentVolume !== undefined) set({ savedVolume: currentVolume });

                // Rule: Manual selection starts at 20% volume (v24.8)
                if (setVolume) {
                    setVolume(0.2);
                }

                set({ playbackState: 'USER_SELECTED', savedVolume: 0.2 });

                const introToPlay = get().getRandomIntro();
                set({
                    currentVideo: media,
                    isPlaying: true,
                    overlayIntroVideo: introToPlay,
                    isPreRollOverlayActive: true,
                    isContentPlaying: false,
                    activeContentId: media.id
                });

                get().preloadNextVideo(media.id);
            },

            playTemporaryVideo: (media, currentVolume, setVolume) => {
                useNewsPlayerStore.getState().stopSlide();
                const { currentVideo, playbackState, getRandomIntro } = get();

                if (currentVideo && playbackState !== 'INTRO') {
                    set({ savedVideo: currentVideo, savedProgress: get().savedProgress });
                }

                set({ savedVolume: 0.7 });

                const introToPlay = getRandomIntro();
                set({
                    currentVideo: media,
                    isPlaying: true,
                    overlayIntroVideo: introToPlay,
                    isPreRollOverlayActive: true,
                    isContentPlaying: false,
                    playbackState: 'USER_SELECTED',
                    activeContentId: media.id
                });

                get().preloadNextVideo(media.id);
            },

            playLiveStream: (streamData) => {
                const volStore = useVolumeStore.getState();
                // Rule: Live stream starts (v24.8) - Stay muted initially for autoplay
                set({ savedVolume: 0.4 });

                set({ 
                    currentVideo: streamData, 
                    isPlaying: true, 
                    playbackState: 'USER_SELECTED',
                    activeContentId: streamData.id,
                    isPreRollOverlayActive: false, // Forzar eliminación de intro
                    isContentPlaying: true
                });
            },

            saveCurrentProgress: (seconds, volume) => {
                set({ savedProgress: seconds, savedVolume: volume });
            },


            loadInitialPlaylist: async (videoUrlToPlay) => {
                const { currentVideo } = get();
                
                // CRITICAL: If a live stream is already playing (detected by StreamListener), do NOT reload.
                if (currentVideo?.id === 'live-stream') {
                    console.log('[PlayerStore] Stream already active, skipping initial load');
                    return;
                }

                const intro = get().getRandomIntro();

                if (videoUrlToPlay) {
                    // Deep Linking Logic
                    let requested = (await getVideosForHome(10)).allVideos.find(v => v.url === videoUrlToPlay) as SlideMedia | null | undefined;
                    if (!requested) requested = await getVideoByUrl(videoUrlToPlay);

                    if (requested) {
                        set({
                            currentVideo: requested,
                            isPlaying: true,
                            overlayIntroVideo: intro,
                            isPreRollOverlayActive: true,
                            isContentPlaying: false,
                            playbackState: 'USER_SELECTED'
                        });
                        get().preloadNextVideo(requested.id);
                        return;
                    }
                }

                // Random Start
                const randomDbVideo = await get().fetchRandomDbVideo();
                if (randomDbVideo) {
                    set({
                        currentVideo: randomDbVideo,
                        isPlaying: true,
                        overlayIntroVideo: intro,
                        isPreRollOverlayActive: true,
                        isContentPlaying: false,
                        playbackState: 'DB_RANDOM'
                    });
                    get().preloadNextVideo(randomDbVideo.id);
                }
            },

            handleOnEnded: async (setVolume, unmute) => {
                const { savedVolume } = get();
                const restoredVolume = savedVolume > 0 ? savedVolume : 0.7;
                set({ historyVolume: restoredVolume });

                const { currentVideo } = get();
                const intro = get().getRandomIntro();

                let nextV = nextDataVideo || await get().fetchRandomDbVideo(currentVideo?.id, currentVideo?.categoria);
                if (!nextV) nextV = await get().fetchRandomDbVideo();

                if (nextV) {
                    set({
                        currentVideo: nextV,
                        isPlaying: true,
                        overlayIntroVideo: intro,
                        isPreRollOverlayActive: true,
                        isContentPlaying: false,
                        playbackState: 'DB_RANDOM',
                        activeContentId: nextV.id
                    });

                    if (setVolume) setVolume(restoredVolume);
                    if (unmute) unmute();

                    nextDataVideo = null;
                    get().preloadNextVideo(nextV.id);
                }
            },

            pauseForSlide: (currentTime) => {
                const { currentVideo, savedProgress } = get();
                if (currentVideo) {
                    set({
                        savedVideo: currentVideo,
                        savedProgress: currentTime || savedProgress,
                        isPlaying: false,
                        isContentPlaying: false
                    });
                }
            },

            resumeAfterSlide: () => {
                const { savedVideo, savedProgress, getRandomIntro } = get();
                if (savedVideo) {
                    const intro = getRandomIntro();
                    const videoWithStart = { ...savedVideo, startAt: savedProgress };

                    set({
                        currentVideo: videoWithStart as any,
                        isPlaying: true,
                        overlayIntroVideo: intro,
                        isPreRollOverlayActive: true,
                        isContentPlaying: false,
                        savedVideo: null // Limpiar después de usar
                    });
                } else {
                    get().playRandomSequence();
                }
            },

            playNextVideoInQueue: async () => {
                get().handleOnEnded();
            },


            preloadNextVideo: async (currentId) => {
                const { currentVideo } = get();
                const video = await get().fetchRandomDbVideo(currentId, currentVideo?.categoria);
                if (video) {
                    nextDataVideo = video;
                    set({ nextVideo: video });
                }
            },

            playRandomSequence: async () => {
                // Re-start loop
                get().handleOnEnded();
            },

            finishIntro: () => {
                set({
                    isPreRollOverlayActive: false,
                    overlayIntroVideo: null,
                    isContentPlaying: true
                });
            }
        }),
        { name: 'PlayerStore' }
    )
);
