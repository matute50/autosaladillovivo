# [Slide Generator Refactor] Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the news slide generation and playback pipeline from scratch to eliminate complex, error-prone state synchronization issues, implementing Option A audio architecture with centralized audio in VideoSection.tsx and passive iframe.

**Architecture:** 
- Centralized `<audio>` element in VideoSection.tsx for all audio playback
- Passive iframe for slides that receives START_NEWS_PLAYBACK and AUDIO_TIME_UPDATE messages
- Simplified state machine with 6 steps (0-6) as defined in PREGUNTA 5, removing post-news clips
- Fallback image generation for news without images
- Strict image sourcing: only use images from the specific news article
- Karaoke subtitles with 2-line max, red for active word, yellow for rest, promo in .is-promo-line style
- Image Ken Burns with proper timing based on audio duration

**Tech Stack:** 
- Next.js 15.5.13
- Zustand (useNewsPlayerStore)
- React + Framer Motion
- Supabase Storage (audios bucket, slides bucket)
- Edge TTS (Gemini 2.5 Flash) with SOUL.md phonetic rules
- Jinja2 templates for slide generation

**Spec:** 
- [VideoSection.tsx] - Refactor audio management and state machine
- [useNewsPlayerStore.ts] - Simplify state management, remove clips logic
- [slide_generator_agent.py] - Rewrite from scratch with new architecture
- [image_fallback_generator.py] - New fallback image generator
- [postMessageBridge.ts] - New messaging protocol between parent and iframe
- [useNewsSlideAudio.ts] - New hook for audio-slide synchronization

**Global Constraints:**
- Use only free-tier models (tier :free)
- No post-news musical clips (direct resume to original YouTube video)
- Images must be from the specific news article (no cross-news usage)
- Audio duration = body_dur + 1.0s + promo_dur
- Promo phrase randomly selected from INSTITUTIONAL_CLOSING_PHRASES
- Subtitles capped at 2 lines, karaoke-style word sync (red for active word, yellow for rest)
- No duplicate audio elements - VideoSection controls all audio
- Slides must use only article-specific images (4 photos max)
- Fallback image generation when no images exist
- Watchdog timer with +5s buffer and data-slide-audio="true" marker
- CSS for .is-promo-line to distinguish institutional phrase visually
- Red #ff0000 for active word and progress bar (exact logo color)

**Review Focus:**
- [ ] Audio element management prevents redundant src reassignment
- [ ] Post-news flow is direct resume without musical clips
- [ ] Slide iframe is passive and receives messages, doesn't control audio
- [ ] Image sourcing restricted to article-specific images
- [ ] Subtitle generation handles 2-line layout properly
- [ ] Fallback image generation works when no images exist
- [ ] Watchdog timer prevents premature slide closure
- [ ] CSS styling for .is-promo-line implements visual differentiation
- [ ] Progress bar and active word use exact #ff0000 logo color
- [ ] State machine simplified to 6 steps with direct resume (step 6)
- [ ] No dual audio elements causing race conditions
- [ ] Post-news flow: fade out slide → fade in original video directly