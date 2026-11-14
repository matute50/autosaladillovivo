'use client'

import { useState } from 'react'
import { signOut } from '@/app/studio-fabrica/login/actions'
import { Button } from '@/components/ui/button'
import { useAuth } from '@/lib/supabase/client'
import Link from 'next/link'
import { Video, Users, Cloud, MonitorPlay, LogOut } from 'lucide-react'

type TabId = 'piloto' | 'presentadores' | 'clima' | 'inspector'

export default function StudioLayout({ children }: { children: React.ReactNode }) {
  const [activeTab, setActiveTab] = useState<TabId>('piloto')
  const { session, loading } = useAuth()

  const tabs: { id: TabId; label: string; icon: React.ReactNode }[] = [
    { id: 'piloto', label: 'Piloto Automático', icon: <MonitorPlay className="w-4 h-4" /> },
    { id: 'presentadores', label: 'Presentadores', icon: <Users className="w-4 h-4" /> },
    { id: 'clima', label: 'Clima', icon: <Cloud className="w-4 h-4" /> },
    { id: 'inspector', label: 'Inspector', icon: <Video className="w-4 h-4" /> },
  ]

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b bg-card">
        <div className="max-w-screen-2xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Video className="w-6 h-6 text-primary" />
            <h1 className="text-lg font-bold hidden sm:block">Fábrica de Videos</h1>
            <h1 className="text-lg font-bold sm:hidden">Fab. Videos</h1>
          </div>
          <div className="flex items-center gap-2">
            {session?.user?.email && (
              <span className="text-xs text-muted-foreground hidden md:inline">
                {session.user.email.split('@')[0]}
              </span>
            )}
            <form action={signOut}>
              <Button variant="ghost" size="sm" type="submit" className="gap-2">
                <LogOut className="w-4 h-4" />
                <span className="hidden sm:inline">Salir</span>
              </Button>
            </form>
          </div>
        </div>
      </header>

      {/* Tab Navigation */}
      <nav className="border-b bg-muted/30 overflow-x-auto">
        <div className="max-w-screen-2xl mx-auto px-4">
          <div className="flex gap-1 min-w-max">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === tab.id
                    ? 'border-primary text-primary'
                    : 'border-transparent text-muted-foreground hover:text-foreground hover:border-muted'
                }`}
              >
                {tab.icon}
                {tab.label}
              </button>
            ))}
          </div>
        </div>
      </nav>

      {/* Content */}
      <main className="max-w-screen-2xl mx-auto px-4 py-6">
        {loading ? (
          <div className="flex items-center justify-center py-20">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
          </div>
        ) : (
          <TabContent activeTab={activeTab}>{children}</TabContent>
        )}
      </main>
    </div>
  )
}

// Re-export children through this wrapper to inject layout logic
function TabContent({ activeTab, children }: { activeTab: TabId; children: React.ReactNode }) {
  return children
}
