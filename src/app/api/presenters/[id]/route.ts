import { NextResponse } from 'next/server'
import { createSupabaseAdminClient } from '@/lib/supabase/admin'

function isValidUUID(str: string): boolean {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(str)
}

// PATCH /api/presenters/[id]
export async function PATCH(request: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params
  if (!isValidUUID(id)) {
    return NextResponse.json({ error: 'Invalid presenter ID' }, { status: 400 })
  }
  const body = await request.json()
  const supabase = createSupabaseAdminClient()

  const { data, error } = await supabase
    .from('video_presenters')
    .update(body as Record<string, unknown>)
    .eq('id', id)
    .select()
    .single()

  if (error) return NextResponse.json({ error: error.message }, { status: 400 })
  return NextResponse.json(data)
}

// DELETE /api/presenters/[id]
export async function DELETE(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params
  if (!isValidUUID(id)) {
    return NextResponse.json({ error: 'Invalid presenter ID' }, { status: 400 })
  }
  const supabase = createSupabaseAdminClient()

  const { error } = await supabase.from('video_presenters').delete().eq('id', id)
  if (error) return NextResponse.json({ error: error.message }, { status: 400 })
  return NextResponse.json({ ok: true })
}
