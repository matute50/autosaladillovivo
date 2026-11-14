'use server'

import { revalidatePath } from 'next/cache'
import { createSupabaseServerClient } from '@/lib/supabase/server'
import { redirect } from 'next/navigation'

export async function signIn(formData: FormData) {
  const email = formData.get('email') as string
  const password = formData.get('password') as string

  if (!email || !password) {
    return { error: 'Email y contraseña son requeridos' }
  }

  const supabase = await createSupabaseServerClient()
  const { data, error } = await supabase.auth.signInWithPassword({
    email,
    password,
  })

  if (error) {
    return { error: error.message }
  }

  // Revalidate to pick up session changes
  revalidatePath('/studio-fabrica', 'layout')

  // Redirect based on origin or default
  const redirectTo = formData.get('redirectTo') as string || '/studio-fabrica'
  redirect(redirectTo)
}

export async function signOut() {
  const supabase = await createSupabaseServerClient()
  await supabase.auth.signOut()
  revalidatePath('/studio-fabrica', 'layout')
  redirect('/studio-fabrica/login')
}
