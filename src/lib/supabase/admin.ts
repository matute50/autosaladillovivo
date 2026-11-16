import { createClient } from '@supabase/supabase-js'

/**
 * Supabase admin client — usa la service role key para saltar RLS.
 * Usar SOLO en API routes del lado del servidor (POST/PATCH/DELETE).
 * NUNCA exponer este client al lado del cliente.
 *
 * Se tipa como `any` porque el proyecto no tiene tipos generados de la DB
 * (database.types.ts). Con un client sin tipo, `.from().update()` queda como
 * `never`; el cast evita falsos negativos de TypeScript.
 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function createSupabaseAdminClient(): any {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL!
  const serviceKey = process.env.SUPABASE_SERVICE_ROLE_KEY!
  return createClient(url, serviceKey)
}