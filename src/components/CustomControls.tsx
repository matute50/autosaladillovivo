'use client';

import React from 'react';
import { usePlayerStore } from '@/store/usePlayerStore';
import { useVolumeStore } from '@/store/useVolumeStore';
import { Maximize, Minimize, Play, Pause, Volume2, VolumeX, Volume1 } from 'lucide-react';

interface CustomControlsProps {
  onToggleFullScreen: () => void;
  isFullScreen: boolean;
}

const CustomControls: React.FC<CustomControlsProps> = ({ onToggleFullScreen, isFullScreen }) => {
  const { isPlaying, togglePlayPause } = usePlayerStore();
  const { volume, setVolume, isMuted, toggleMute, unmute } = useVolumeStore();

  const handleVolumeChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newVol = parseFloat(e.target.value);
    setVolume(newVol);
    // Si el usuario mueve el slider y estaba muteado, forzamos el desmuteo
    if (isMuted && newVol > 0) unmute();
  };

  // Determinar icono de volumen
  const getVolumeIcon = () => {
    if (isMuted || volume === 0) return <VolumeX size={24} />;
    if (volume < 0.5) return <Volume1 size={24} />;
    return <Volume2 size={24} />;
  };

  return (
    <div
      className="w-full bg-gradient-to-t from-black/90 via-black/50 to-transparent px-4 pb-3 pt-10 flex items-center justify-between transition-opacity duration-300"
      onClick={(e) => e.stopPropagation()} // Regla de Oro: Bloqueamos clicks al fondo
    >

      {/* IZQUIERDA: Play/Pause */}
      <div className="flex items-center gap-4">
        <button
          onClick={(e) => { e.stopPropagation(); togglePlayPause(); }}
          className="text-white hover:text-[#6699ff] transition-colors p-1"
          title={isPlaying ? "Pausar" : "Reproducir"}
        >
          {isPlaying ? <Pause size={28} fill="currentColor" /> : <Play size={28} fill="currentColor" />}
        </button>

      </div>

      {/* DERECHA: Grupo Controles (Volumen + Fullscreen) */}
      <div className="flex items-center gap-4 bg-black/40 backdrop-blur-sm px-3 py-1.5 rounded-full border border-white/10">

        {/* GRUPO VOLUMEN (Horizontal) */}
        <div className="flex items-center gap-2">
          {/* Botón Mute */}
          <button
            onClick={(e) => { e.stopPropagation(); toggleMute(); }}
            className="text-white hover:text-[#6699ff] transition-colors"
            title={isMuted ? "Activar sonido" : "Silenciar"}
          >
            {getVolumeIcon()}
          </button>

          {/* Slider Horizontal Funcional */}
          <input
            type="range"
            min={0}
            max={1}
            step={0.01}
            value={isMuted ? 0 : volume}
            onChange={handleVolumeChange}
            // onInput eliminado: onChange cubre el evento en range inputs HTML5;
            // onInput espera InputEventHandler y provocaba error TS 2322.
            onClick={(e) => e.stopPropagation()} // Vital para no pausar el video al arrastrar
            className="
              w-20 h-1 
              appearance-none bg-white/30 rounded-full cursor-pointer 
              accent-[#6699ff] hover:accent-[#4d88ff]
            "
          />
        </div>

        {/* Separador Vertical */}
        <div className="h-5 w-px bg-white/20"></div>

        {/* Pantalla Completa */}
        <button
          onClick={(e) => { e.stopPropagation(); onToggleFullScreen(); }}
          className="text-white hover:text-[#6699ff] transition-colors"
          title={isFullScreen ? "Salir de pantalla completa" : "Pantalla completa"}
        >
          {isFullScreen ? <Minimize size={24} /> : <Maximize size={24} />}
        </button>
      </div>
    </div>
  );
};

export default React.memo(CustomControls);