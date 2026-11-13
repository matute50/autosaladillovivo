// src/utils/postMessageBridge.ts

export interface ParentToIframeMessage {
  type: 'START_NEWS_PLAYBACK';
  payload: {
    duration: number;
  };
}

export interface ParentToIframeMessageA {
  type: 'AUDIO_TIME_UPDATE';
  payload: {
    currentTime: number;
    duration: number;
  };
}

export interface ParentToIframeMessageB {
  type: 'SLIDE_CLOSE';
  payload: {};
}

export interface IframeToParentMessage {
  type: 'SLIDE_READY';
  payload: {
    slideDuration: number;
  };
  type: 'SLIDE_ERROR';
  payload: {
    message: string;
  };
}

export const sendParentToIframe = (message: ParentToIframeMessage | ParentToIframeMessageA | ParentToIframeMessageB) => {
  const iframe = document.querySelector('.video-universe iframe');
  if (iframe && iframe.contentWindow) {
    iframe.contentWindow.postMessage(message, '*');
  }
};

export const onParentMessage = (callback: (message: IframeToParentMessage) => void) => {
  const handler = (event: MessageEvent) => {
    if (event.data && typeof event.data === 'object' && 'type' in event.data) {
      callback(event.data as IframeToParentMessage);
    }
  };
  
  window.addEventListener('message', handler);
  return () => window.removeEventListener('message', handler);
};