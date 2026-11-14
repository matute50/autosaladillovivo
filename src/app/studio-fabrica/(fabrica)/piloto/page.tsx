export default function PilotoPage() {
  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">Cabina de Piloto Automático, Cola y Salud</h2>
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {/* Status bar placeholder — Tasks 4-6 will wire this up */}
        <div className="col-span-full rounded-lg border bg-card p-6 text-center text-muted-foreground">
          Panel de estado del piloto automático — llegando en la Fase 1
        </div>
      </div>
    </div>
  )
}
