'use client';

import React, { useState, useEffect } from 'react';
import { X } from 'lucide-react';

interface NewsSlidePlayerProps {
  slideUrl: string;
  onClose: () => void;
}

export function NewsSlidePlayer({ slideUrl, onClose }: NewsSlidePlayerProps) {
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [htmlContent, setHtmlContent] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;

    const loadSlide = async () => {
      if (!slideUrl) {
        if (isMounted) {
          setError('URL de slide no provista');
          setIsLoading(false);
        }
        return;
      }

      try {
        const response = await fetch(slideUrl);
        if (!response.ok) {
          if (isMounted) {
            setError('No se pudo cargar el slide');
            setIsLoading(false);
          }
          return;
        }
        const text = await response.text();
        if (isMounted) {
          setHtmlContent(text);
          setIsLoading(false);
        }
      } catch (err) {
        // En caso de restricción CORS en fetch, permitir carga directa vía iframe src
        if (isMounted) {
          setIsLoading(false);
        }
      }
    };

    loadSlide();

    return () => {
      isMounted = false;
    };
  }, [slideUrl]);

  if (isLoading) {
    return (
      <div className="slide-modal-overlay" onClick={onClose} role="dialog" aria-modal="true">
        <div className="slide-modal" onClick={(e) => e.stopPropagation()}>
          <button className="close-button" onClick={onClose} aria-label="Cerrar modal">
            <X size={24} />
          </button>
          <div className="loading-spinner">
            <div className="spinner"></div>
            <p>Cargando slide interactivo...</p>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="slide-modal-overlay" onClick={onClose} role="dialog" aria-modal="true">
        <div className="slide-modal" onClick={(e) => e.stopPropagation()}>
          <div className="error-content">
            <X className="close-icon" onClick={onClose} style={{ cursor: 'pointer', marginBottom: 16 }} size={32} />
            <h3>Error al cargar el slide</h3>
            <p>{error}</p>
            <button onClick={onClose} className="close-button">
              Cerrar
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="slide-modal-overlay" onClick={onClose} role="dialog" aria-modal="true">
      <div className="slide-modal" onClick={(e) => e.stopPropagation()}>
        <button className="close-button" onClick={onClose} aria-label="Cerrar slide">
          <X size={24} />
        </button>
        <div className="slide-container">
          <iframe
            src={htmlContent ? undefined : slideUrl}
            srcDoc={htmlContent || undefined}
            className="slide-iframe"
            title="Noticia en formato slide"
            sandbox="allow-same-origin allow-scripts allow-forms"
            allow="autoplay; fullscreen"
          />
        </div>
      </div>
    </div>
  );
}

export default NewsSlidePlayer;
