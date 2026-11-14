import { redirect } from 'next/navigation'
import { createSupabaseServerClient } from '@/lib/supabase/server'
import StudioLayout from '@/components/studio/StudioLayout'
import type { ReactNode } from 'react'

export default async function FabricaLayout({ children }: { children: ReactNode }) {
  const supabase = await createSupabaseServerClient()
  const { data: { session } } = await supabase.auth.getSession()

  if (!session) {
    redirect('/studio-fabrica/login')
  }

  return <StudioLayout>{children}</StudioLayout>
}
