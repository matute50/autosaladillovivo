import { NextResponse } from 'next/server'
import { createSupabaseAdminClient } from '@/lib/supabase/admin'

// GET /api/presenters
export async function GET() {
  const supabase = createSupabaseAdminClient()
  const { data, error } = await supabase
    .from('video_presenters')
    .select('*')
    .order('slug')

  if (error) return NextResponse.json({ error: error.message }, { status: 500 })
  return NextResponse.json(data ?? [])
}

// POST /api/presenters
export async function POST(request: Request) {
  const body = await request.json()
  const supabase = createSupabaseAdminClient()

  const { data, error } = await supabase
    .from('video_presenters')
    .insert(body)
    .select()
    .single()

  if (error) return NextResponse.json({ error: error.message }, { status: 400 })
  return NextResponse.json(data, { status: 201 })
}
