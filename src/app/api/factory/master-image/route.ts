import { NextResponse } from 'next/server'
import { createSupabaseAdminClient } from '@/lib/supabase/admin'

/**
 * GET /api/factory/master-image?articleId=N
 * Devuelve el job de imagen maestra asociado a una noticia (si existe).
 */
export async function GET(req: Request) {
  try {
    const url = new URL(req.url)
    const articleId = Number(url.searchParams.get('articleId'))

    if (!articleId || !Number.isInteger(articleId) || articleId <= 0) {
      return NextResponse.json({ success: false, error: 'articleId inválido' }, { status: 400 })
    }

    const supabase = createSupabaseAdminClient()

    const { data, error } = await supabase
      .from('ara_video_jobs')
      .select('id, article_id, tipo, estado, master_image_url, prompt_imagen, updated_at')
      .eq('article_id', articleId)
      .eq('tipo', 'imagen')
      .order('created_at', { ascending: false })
      .limit(1)
      .maybeSingle()

    if (error) {
      console.error('[MASTER_IMAGE_QUERY_ERROR]', error)
      return NextResponse.json({ success: false, error: error.message }, { status: 500 })
    }

    return NextResponse.json({ success: true, job: data ?? null })
  } catch (e: any) {
    console.error('[MASTER_IMAGE_CRASH]', e)
    return NextResponse.json({ success: false, error: e.message }, { status: 500 })
  }
}

/**
 * POST /api/factory/master-image  body { articleId: number }
 * Encola un trabajo de "imagen maestra" (tipo='imagen') en ara_video_jobs.
 * El worker de Python lo toma con --image / modo poll.
 */
export async function POST(request: Request) {
  try {
    const body = await request.json()
    const articleId = Number(body?.articleId)

    if (!articleId || !Number.isInteger(articleId) || articleId <= 0) {
      return NextResponse.json({ success: false, error: 'articleId inválido' }, { status: 400 })
    }

    const supabase = createSupabaseAdminClient()

    // El artículo debe existir y tener ara_json (prompt listo)
    const { data: article, error: articleErr } = await supabase
      .from('articles')
      .select('id, ara_json')
      .eq('id', articleId)
      .single()

    if (articleErr || !article) {
      return NextResponse.json({ success: false, error: 'Artículo no encontrado' }, { status: 404 })
    }
    if (!article.ara_json) {
      return NextResponse.json({ success: false, error: 'El artículo aún no tiene ara_json (guión)' }, { status: 409 })
    }

    // Reusar job existente o crear uno nuevo
    const { data: existing } = await supabase
      .from('ara_video_jobs')
      .select('id, article_id')
      .eq('article_id', articleId)
      .maybeSingle()

    let row: { id: string | number } | null = existing ?? null
    if (!row) {
      const { data: created, error: insertErr } = await supabase
        .from('ara_video_jobs')
        .insert({
          article_id: articleId,
          tipo: 'imagen',
          estado: 'pendiente_imagen',
        })
        .select('id')
        .single()
      if (insertErr) {
        console.error('[MASTER_IMAGE_INSERT_ERROR]', insertErr)
        return NextResponse.json({ success: false, error: insertErr.message }, { status: 500 })
      }
      row = created
    } else {
      const jobId = row.id
      // Reabrir el job existente para regenerar la imagen
      const { error: updateErr } = await supabase
        .from('ara_video_jobs')
        .update({ tipo: 'imagen', estado: 'pendiente_imagen', master_image_url: null })
        .eq('id', jobId)
      if (updateErr) {
        console.error('[MASTER_IMAGE_REOPEN_ERROR]', updateErr)
        return NextResponse.json({ success: false, error: updateErr.message }, { status: 500 })
      }
      row = { id: jobId }
    }

    return NextResponse.json({ success: true, jobId: row!.id, articleId })
  } catch (e: any) {
    console.error('[MASTER_IMAGE_CRASH]', e)
    return NextResponse.json({ success: false, error: e.message }, { status: 500 })
  }
}