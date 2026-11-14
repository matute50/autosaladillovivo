import { createBrowserClient } from '@supabase/ssr'
import type { Session } from '@supabase/supabase-js'
import { useEffect, useState } from 'react'

let browserClient: ReturnType<typeof createBrowserClient> | null = null

export function createSupabaseBrowserClient() {
  if (!browserClient) {
    browserClient = createBrowserClient(
      process.env.NEXT_PUBLIC_SUPABASE_URL!,
      process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
    )
  }
  return browserClient
}

// Hook for use inside React components
export function useSupabaseClient() {
  const [client] = useState(createSupabaseBrowserClient)
  return client
}

// Auth state hook
export function useAuth() {
  const [session, setSession] = useState<Session | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const client = createSupabaseBrowserClient()

    // Get initial session
    client.auth.getSession().then(({ data: { session } }: { data: { session: Session | null } }) => {
      setSession(session)
      setLoading(false)
    })

    // Listen for auth changes
    const { data: { subscription } } = client.auth.onAuthStateChange((_event: string, session: Session | null) => {
      setSession(session)
    })

    return () => subscription.unsubscribe()
  }, [])

  return { session, loading }
}
