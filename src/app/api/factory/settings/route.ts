import { NextResponse } from 'next/server'
import { createSupabaseAdminClient } from '@/lib/supabase/admin'

export async function GET() {
  try {
    const supabase = createSupabaseAdminClient()
    const { data, error } = await supabase
      .from('video_factory_settings')
      .select('*')

    if (error) {
      console.error('[SETTINGS_GET_ERROR]', error)
      return NextResponse.json({ error: error.message }, { status: 500 })
    }
    return NextResponse.json(data ?? [])
  } catch (e: any) {
    console.error('[SETTINGS_GET_CRASH]', e)
    return NextResponse.json({ error: e.message }, { status: 500 })
  }
}

export async function PATCH(request: Request) {
  try {
    const body = await request.json()
    const { id, ...updates } = body

    if (!id) {
      return NextResponse.json({ error: 'Missing id' }, { status: 400 })
    }

    const supabase = createSupabaseAdminClient()
    
    const { data, error } = await supabase
      .from('video_factory_settings')
      .update(updates)
      .eq('id', id)
      .select()
      .single()

    if (error) {
      console.error('[SETTINGS_PATCH_ERROR]', error)
      return NextResponse.json({ error: error.message }, { status: 400 })
    }

    return NextResponse.json(data)
  } catch (e: any) {
    console.error('[SETTINGS_PATCH_CRASH]', e)
    return NextResponse.json({ error: e.message }, { status: 500 })
  }
}