import { redirect } from 'next/navigation'
import { createSupabaseServerClient } from '@/lib/supabase/server'

export default async function StudioFabricaLayout({
  children,
}: {
  children: React.ReactNode
}) {
  // Auth is handled by middleware.ts for route protection
  // This layout just renders children
  return <>{children}</>
}
