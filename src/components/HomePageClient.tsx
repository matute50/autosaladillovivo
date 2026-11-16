'use client';

import React, { useState, useEffect } from 'react';
import DesktopLayout from '@/components/layout/DesktopLayout';
import TvModeLayout from '@/components/layout/TvModeLayout';
import { PageData } from '@/lib/types';
import { usePlayerStore } from '@/store/usePlayerStore';
import { useSearchParams } from 'next/navigation';

/**
 * HomePageClient - Componente principal del lado del cliente.
 * Recibe 'initialData' desde page.tsx (Servidor).
 */
const HomePageClient = ({ initialData }: { initialData: PageData }) => {
  const [mounted, setMounted] = useState(false);
  const { viewMode, setViewMode } = usePlayerStore();
  const searchParams = useSearchParams();
  const resumenId = searchParams?.get('resumen') || undefined;

  useEffect(() => {
    setMounted(true);

    // Si viene con un resumenId, forzar modo TV
    if (resumenId) {
      setViewMode('tv');
    }
  }, [resumenId, setViewMode]);

  if (!mounted) {
    return <div className="min-h-screen bg-black" />;
  }

  if (!initialData) {
    return (
      <div className="min-h-screen bg-black flex items-center justify-center text-white">
        Cargando contenidos...
      </div>
    );
  }

  // Prioridad 1: Modo TV (si está activo, gana a todo)
  if (viewMode === 'tv') {
    return <TvModeLayout />;
  }

  // Prioridad 2: SIEMPRE Desktop
  return <DesktopLayout data={initialData} />;
};

export default HomePageClient;
