import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

export function middleware(request: NextRequest) {
  const { nextUrl: url, headers } = request
  const hostname = url.hostname

  const userAgent = headers.get('user-agent') || ''

  // Detección de TV (Simplificada para Middleware potente)
  const isTV = /TV|Large Screen|SmartTV|GoogleTV|AppleTV|HbbTV|CrKey|Tizen|WebOS/i.test(userAgent)

  // Detección de Móvil (Sin incluir tablets para mantener experiencia Desktop en ellas si se prefiere, o incluirlo si es necesario)
  const isMobile = /Android|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(userAgent) && !isTV

  // --- LÓGICA DE REDIRECCIÓN ---

  // 1. Si es TV
  if (isTV) {
    if (hostname === 'saladillovivo.com.ar' || hostname === 'www.saladillovivo.com.ar' || hostname === 'm.saladillovivo.com.ar') {
      const tvUrl = new URL(url.pathname, 'https://tv.saladillovivo.com.ar')
      tvUrl.search = url.search
      return NextResponse.redirect(tvUrl, { status: 307 })
    }
  }

  // 2. Si es Móvil
  if (isMobile) {
    if (hostname === 'saladillovivo.com.ar' || hostname === 'www.saladillovivo.com.ar' || hostname === 'tv.saladillovivo.com.ar') {
      const mobileUrl = new URL(url.pathname, 'https://m.saladillovivo.com.ar')
      mobileUrl.search = url.search
      return NextResponse.redirect(mobileUrl, { status: 307 })
    }
  }

  // 3. Si es Desktop (Cualquier otro caso)
  const isDesktop = !isTV && !isMobile
  if (isDesktop) {
    if (hostname === 'm.saladillovivo.com.ar' || hostname === 'tv.saladillovivo.com.ar') {
      const desktopUrl = new URL(url.pathname, 'https://www.saladillovivo.com.ar')
      desktopUrl.search = url.search
      return NextResponse.redirect(desktopUrl, { status: 307 })
    }
  }

  return NextResponse.next()
}

export const config = {
  matcher: [
    /*
     * Matcher actualizado para excluir explícitamente _next/data y archivos estáticos.
     * Esto permite que la versión de PC cargue sus noticias y configuraciones.
     */
    '/((?!api|_next/static|_next/data|_next/image|favicon.ico|robots.txt|sitemap.xml|.*\\.[\\w]+$).*)',
  ],
}