import { NextResponse } from 'next/server'
import { createSupabaseServerClient } from '@/lib/supabase/server'

// GET /api/locations
export async function GET(request: Request) {
  const { searchParams } = new URL(request.url)
  const presenterId = searchParams.get('presenter_id') || undefined

  const supabase = await createSupabaseServerClient()

  let query = supabase.from('video_locations').select('*').order('nombre')
  if (presenterId) {
    query = query.eq('presenter_id', presenterId)
  }

  const { data, error } = await query
  if (error) return NextResponse.json({ error: error.message }, { status: 500 })
  return NextResponse.json(data ?? [])
}

// POST /api/locations
export async function POST(request: Request) {
  const body = await request.json()
  const supabase = await createSupabaseServerClient()

  const { data, error } = await supabase
    .from('video_locations')
    .insert(body)
    .select()
    .single()

  if (error) return NextResponse.json({ error: error.message }, { status: 400 })
  return NextResponse.json(data, { status: 201 })
}
