import { redirect } from 'next/navigation'
import { createSupabaseServerClient } from '@/lib/supabase/server'

export default async function StudioFabricaLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const supabase = await createSupabaseServerClient()
  const { data: { session } } = await supabase.auth.getSession()

  if (!session) {
    // Get the callback URL from the request — defaults to /studio-fabrica
    const url = new URL(`http://localhost${'/studio-fabrica'}`)
    redirect(`/studio-fabrica/login?next=${encodeURIComponent(url.pathname + url.search)}`)
  }

  return <>{children}</>
}
