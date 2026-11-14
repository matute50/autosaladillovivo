import { NextResponse } from 'next/server'
import { createSupabaseServerClient } from '@/lib/supabase/server'

// GET /api/factory/settings
export async function GET() {
  const supabase = await createSupabaseServerClient()
  const { data, error } = await supabase
    .from('video_factory_settings')
    .select('*')

  if (error) return NextResponse.json({ error: error.message }, { status: 500 })
  // The table is constrained to a single row; return as array
  return NextResponse.json(data ?? [])
}

// PATCH /api/factory/settings
export async function PATCH(request: Request) {
  const body = await request.json()
  const supabase = await createSupabaseServerClient()

  const { data, error } = await supabase
    .from('video_factory_settings')
    .update(body)
    .select()
    .single()

  if (error) return NextResponse.json({ error: error.message }, { status: 400 })
  return NextResponse.json(data)
}
