'use server'

import { revalidatePath } from 'next/cache'
import { createSupabaseServerClient } from '@/lib/supabase/server'
import { redirect } from 'next/navigation'

// Firm-compatible: useActionState la invoca como (prevState, formData).
// El form debe bindear con signIn.bind(null, null) para que formData no sea null.
export async function signIn(_prevState: unknown, formData: FormData) {
  const email = ((formData?.get('email') as string) || '').trim()
  const password = (formData?.get('password') as string) || ''

  if (!email || !password) {
    return { error: 'Email y contraseña son requeridos' }
  }

  const supabase = await createSupabaseServerClient()
  const { error } = await supabase.auth.signInWithPassword({
    email,
    password,
  })

  if (error) {
    return { error: error.message }
  }

  // Revalidate to pick up session changes
  revalidatePath('/studio-fabrica', 'layout')

  // Redirect relativo: funciona igual por localhost, LAN o IP remota.
  const redirectTo = (formData?.get('redirectTo') as string) || '/studio-fabrica'
  redirect(redirectTo)
}

export async function signOut() {
  const supabase = await createSupabaseServerClient()
  await supabase.auth.signOut()
  revalidatePath('/studio-fabrica', 'layout')
  redirect('/studio-fabrica/login')
}
