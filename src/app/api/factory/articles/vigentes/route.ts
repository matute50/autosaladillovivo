import { NextResponse } from 'next/server'
import { createSupabaseAdminClient } from '@/lib/supabase/admin'

/**
 * GET /api/factory/articles/vigentes
 * Devuelve los últimos artículos que tienen ara_json y fueron enviados a Ara.
 */
export async function GET() {
  try {
    const supabase = createSupabaseAdminClient()

    const { data, error } = await supabase
      .from('articles')
      .select('id, title, slug, created_at, enviado_a_ara')
      .not('ara_json', 'is', null)
      .eq('enviado_a_ara', true)
      .order('created_at', { ascending: false })
      .limit(50)

    if (error) {
      console.error('[VIGENTES_QUERY_ERROR]', error)
      return NextResponse.json({ success: false, error: error.message }, { status: 500 })
    }

    const articles = (data || []).map((a: any) => ({
      id: a.id,
      title: a.title,
      slug: a.slug,
      created_at: a.created_at,
    }))

    return NextResponse.json({ success: true, articles })
  } catch (e: any) {
    console.error('[VIGENTES_CRASH]', e)
    return NextResponse.json({ success: false, error: e.message }, { status: 500 })
  }
}
