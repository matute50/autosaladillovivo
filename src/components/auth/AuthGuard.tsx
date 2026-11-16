'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/lib/supabase/client'

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const { session, loading } = useAuth()
  const router = useRouter()

  useEffect(() => {
    if (!loading && !session) {
      router.replace('/studio-fabrica/login?next=' + encodeURIComponent(window.location.pathname))
    }
  }, [session, loading, router])

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[200px]">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    )
  }

  if (!session) {
    return null
  }

  return <>{children}</>
}

// Hook to get current session status in server components
export async function getUser() {
  const { createSupabaseServerClient } = await import('@/lib/supabase/server')
  const supabase = await createSupabaseServerClient()
  const { data: { session } } = await supabase.auth.getSession()
  return session
}
