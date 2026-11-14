import { create } from 'zustand';
import {
    getArticlesForHome,
    getVideosForHome,
    getTickerTexts,
    getInterviews,
    getActiveBanners,
    getActiveAds,
    getCalendarEvents,
    fetchVideosBySearch
} from '@/lib/data';
import { Article, Video, Interview, Banner, Ad, CalendarEvent } from '@/lib/types';

interface NewsState {
    allNews: Article[];
    featuredNews: Article[];
    secondaryNews: Article[];
    tertiaryNews: Article[];
    otherNews: Article[];
    allTickerTexts: string[];
    galleryVideos: Video[];
    interviews: Interview[];
    activeBanners: Banner[];
    activeAds: Ad[];
    calendarEvents: CalendarEvent[];

    isLoading: boolean;
    isLoadingVideos: boolean;
    isLoadingInterviews: boolean;
    isLoadingBanners: boolean;
    adsLoading: boolean;
    eventsLoading: boolean;
    isLoadingConfig: boolean;

    // Search
    searchQuery: string;
    searchResults: Video[];
    isSearching: boolean;
    searchLoading: boolean;

    // Theme (keeping it here for now if needed, though a separate UI store might be better)
    isDarkTheme: boolean;

    // Actions
    fetchInitialData: () => Promise<void>;
    handleSearch: (query: string) => Promise<void>;
    setSearchQuery: (query: string) => void;
    setIsDarkTheme: (isDark: boolean) => void;
    hydrate: (data: any) => void;

    // Getters (functions that help access data)
    getNewsBySlug: (slug: string) => Article | undefined;
    getNewsById: (id: string | number) => Article | undefined;
}

export const useNewsStore = create<NewsState>((set, get) => ({
    allNews: [],
    featuredNews: [],
    secondaryNews: [],
    tertiaryNews: [],
    otherNews: [],
    allTickerTexts: [],
    galleryVideos: [],
    interviews: [],
    activeBanners: [],
    activeAds: [],
    calendarEvents: [],

    isLoading: true,
    isLoadingVideos: true,
    isLoadingInterviews: true,
    isLoadingBanners: true,
    adsLoading: true,
    eventsLoading: true,
    isLoadingConfig: true,

    searchQuery: '',
    searchResults: [],
    isSearching: false,
    searchLoading: false,

    isDarkTheme: false,

    fetchInitialData: async () => {
        set({
            isLoading: true,
            isLoadingVideos: true,
            isLoadingInterviews: true,
            isLoadingBanners: true,
            adsLoading: true,
            eventsLoading: true,
            isLoadingConfig: true
        });

        try {
            const [articlesResult, videosResult, tickerTexts, interviews, banners, ads, events] = await Promise.all([
                getArticlesForHome(),
                getVideosForHome(),
                getTickerTexts(),
                getInterviews(),
                getActiveBanners(),
                getActiveAds(),
                getCalendarEvents(),
            ]);

            get().hydrate({
                allNews: articlesResult?.allNews || [],
                allTickerTexts: tickerTexts,
                allVideos: videosResult?.allVideos || [],
                interviews,
                activeBanners: banners,
                activeAds: ads,
                calendarEvents: events,
            });

        } catch (error) {
            console.error("Error fetching data in NewsStore:", error);
        } finally {
            set({
                isLoading: false,
                isLoadingVideos: false,
                isLoadingInterviews: false,
                isLoadingBanners: false,
                adsLoading: false,
                eventsLoading: false,
                isLoadingConfig: false,
            });
        }
    },

    handleSearch: async (query: string) => {
        set({ searchQuery: query });

        if (!query.trim()) {
            set({ isSearching: false, searchResults: [] });
            return;
        }

        set({ isSearching: true, searchLoading: true });
        try {
            const results = await fetchVideosBySearch(query);
            set({ searchResults: results });
        } catch (err) {
            console.error("Error during search in NewsStore:", err);
            set({ searchResults: [] });
        } finally {
            set({ searchLoading: false });
        }
    },

    setSearchQuery: (query: string) => set({ searchQuery: query }),
    setIsDarkTheme: (isDark: boolean) => set({ isDarkTheme: isDark }),

    hydrate: (data: any) => {
        if (!data) return;
        const allNews = data.allNews || [];

        set({
            allNews,
            featuredNews: data.featuredNews || allNews[0] || null,
            secondaryNews: allNews.filter((n: any) => n.featureStatus === 'secondary'),
            tertiaryNews: allNews.filter((n: any) => n.featureStatus === 'tertiary'),
            otherNews: allNews.filter((n: any) => !['featured', 'secondary', 'tertiary'].includes(n.featureStatus || '')),
            allTickerTexts: data.allTickerTexts || [],
            galleryVideos: data.allVideos || [],
            interviews: data.interviews || [],
            activeBanners: data.activeBanners || [],
            activeAds: data.activeAds || [],
            calendarEvents: data.calendarEvents || [],
            isLoading: false,
            isLoadingVideos: false,
            isLoadingInterviews: false,
            isLoadingBanners: false,
            adsLoading: false,
            eventsLoading: false,
            isLoadingConfig: false
        });
    },

    getNewsBySlug: (slug: string) => get().allNews.find(item => item.slug === slug),
    getNewsById: (id: string | number) => get().allNews.find(item => item.id.toString() === id.toString()),
}));
