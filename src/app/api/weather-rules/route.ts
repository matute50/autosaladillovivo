import { NextResponse } from 'next/server'
import { createSupabaseAdminClient } from '@/lib/supabase/admin'

// GET /api/weather-rules
export async function GET() {
  const supabase = createSupabaseAdminClient()
  const { data, error } = await supabase
    .from('video_weather_rules')
    .select('*')
    .order('temp_min')

  if (error) return NextResponse.json({ error: error.message }, { status: 500 })
  return NextResponse.json(data ?? [])
}

// POST /api/weather-rules
export async function POST(request: Request) {
  const body = await request.json()
  const supabase = createSupabaseAdminClient()

  const { data, error } = await supabase
    .from('video_weather_rules')
    .insert(body)
    .select()
    .single()

  if (error) return NextResponse.json({ error: error.message }, { status: 400 })
  return NextResponse.json(data, { status: 201 })
}
