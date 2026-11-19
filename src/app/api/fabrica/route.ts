import { NextRequest, NextResponse } from 'next/server'
import { createSupabaseAdminClient } from '@/lib/supabase/admin'

export const dynamic = 'force-dynamic'

interface WorkflowRequest {
  action: 'update_location' | 'update_script' | 'generate_workflow'
  article_id: number
  location_category?: string
  video_script?: string
  bloques?: string[]
}

export async function GET(req: NextRequest) {
  try {
    const supabase = createSupabaseAdminClient()
    const { searchParams } = new URL(req.url)
    const status = searchParams.get('status')
    const limit = parseInt(searchParams.get('limit') || '50', 10)

    let query = supabase
      .from('articles')
      .select('id, title, category, video_script, video_status, video_location_category, video_path, video_generated_at, created_at')
      .order('created_at', { ascending: false })
      .limit(limit)

    if (status) {
      query = query.eq('video_status', status)
    }

    const { data, error } = await query

    if (error) {
      return NextResponse.json({ error: error.message }, { status: 500 })
    }

    return NextResponse.json({ articles: data || [] })
  } catch (err: any) {
    return NextResponse.json({ error: err.message }, { status: 500 })
  }
}

export async function POST(req: NextRequest) {
  try {
    const supabase = createSupabaseAdminClient()
    const body: WorkflowRequest = await req.json()
    const { action, article_id } = body

    if (!article_id) {
      return NextResponse.json({ error: 'article_id es obligatorio' }, { status: 400 })
    }

    if (action === 'update_location') {
      const { error } = await supabase
        .from('articles')
        .update({ video_location_category: body.location_category })
        .eq('id', article_id)

      if (error) throw error
      return NextResponse.json({ success: true, location_category: body.location_category })
    }

    if (action === 'update_script') {
      const { error } = await supabase
        .from('articles')
        .update({ video_script: body.video_script, video_status: 'pendiente' })
        .eq('id', article_id)

      if (error) throw error
      return NextResponse.json({ success: true })
    }

    if (action === 'generate_workflow') {
      // Ensamblar workflow JSON en memoria para descarga directa
      const bloques = body.bloques || []
      const characterName = 'Ara'
      const nodes: any[] = []
      const links: any[] = []
      let nodeId = 1

      // 1. Upload image
      const uploadId = nodeId++
      nodes.push({
        id: uploadId,
        type: 'UploadImage',
        title: 'Locación de Fondo',
        pos: [100, 200],
        properties: {
          category: body.location_category || 'general'
        },
        outputs: [{ name: 'image', type: 'image', links: [1] }]
      })

      // 2. Prompt inicial
      const promptId = nodeId++
      nodes.push({
        id: promptId,
        type: 'EnterPrompt',
        title: `Prompt Fotograma (${characterName})`,
        pos: [100, 420],
        properties: {
          text: `Retrato cinematográfico de ${characterName}, presentadora de noticias mirando a cámara, plano medio vertical 9:16.`,
          character: characterName
        },
        outputs: [{ name: 'prompt', type: 'string', links: [2] }]
      })

      // 3. Generate Image
      const genImgId = nodeId++
      nodes.push({
        id: genImgId,
        type: 'GenerateImage',
        title: `Fotograma Maestro (${characterName})`,
        pos: [450, 300],
        properties: {
          character: characterName,
          model: 'Nano Banana 2.1',
          aspect_ratio: '9:16',
          auto_add_character: true
        },
        inputs: [
          { name: 'image_input', type: 'image', link: 1 },
          { name: 'prompt_input', type: 'string', link: 2 }
        ],
        outputs: [{ name: 'image_output', type: 'image', links: [3] }]
      })

      links.push({ id: 1, from_node: uploadId, from_port: 'image', to_node: genImgId, to_port: 'image_input' })
      links.push({ id: 2, from_node: promptId, from_port: 'prompt', to_node: genImgId, to_port: 'prompt_input' })

      let prevVideoId: number | null = null
      let linkId = 4

      bloques.forEach((b: string, index: number) => {
        const vidId = nodeId++
        const isFirst = index === 0
        const videoNode: any = {
          id: vidId,
          type: 'GenerateVideo',
          title: `Bloque ${index + 1} (8s) - ${characterName}`,
          pos: [800 + index * 360, 300],
          properties: {
            character: characterName,
            model: 'Veo 3.1',
            duration: '8s',
            prompt: `${characterName} hablando a cámara con dicción natural: "${b}". Gesto sobrio, plano vertical 9:16.`,
            auto_add_character: true,
            auto_add_voice_by_speaker: true,
            save_name: `${String(index + 1).padStart(2, '0')}_prompt.mp4`
          },
          inputs: [],
          outputs: [
            { name: 'video_output', type: 'video', links: [] },
            { name: 'last_frame', type: 'image', links: [] }
          ]
        }

        if (isFirst) {
          videoNode.inputs.push({ name: 'initial_frame', type: 'image', link: 3 })
          links.push({ id: 3, from_node: genImgId, from_port: 'image_output', to_node: vidId, to_port: 'initial_frame' })
        } else {
          const curLink = linkId++
          videoNode.inputs.push({ name: 'last_frame_input', type: 'image', link: curLink })
          links.push({ id: curLink, from_node: prevVideoId!, from_port: 'last_frame', to_node: vidId, to_port: 'last_frame_input' })
        }

        nodes.push(videoNode)
        prevVideoId = vidId
      })

      const workflowOutput = {
        metadata: {
          article_id,
          character: characterName,
          aspect_ratio: '9:16',
          total_blocks: bloques.length,
          total_duration_sec: bloques.length * 8
        },
        workflow: {
          nodes,
          links
        }
      }

      return NextResponse.json({ workflow: workflowOutput })
    }

    return NextResponse.json({ error: 'Acción no reconocida' }, { status: 400 })
  } catch (err: any) {
    return NextResponse.json({ error: err.message }, { status: 500 })
  }
}
