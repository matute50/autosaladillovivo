'use client'

import { useState } from 'react'
import { useActionState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { signIn } from './actions'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { toast } from '@/components/ui/use-toast'
import { useEffect } from 'react'

export default function LoginPage() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const redirectTo = searchParams.get('next') || '/studio-fabrica'
  const [state, formAction, pending] = useActionState(signIn, null)

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
  }

  // Show error toast when there's an error
  useEffect(() => {
    if (state?.error) {
      toast({
        variant: 'destructive',
        title: 'Error de autenticación',
        description: state.error,
      })
    }
  }, [state])

  return (
    <div className="min-h-screen flex items-center justify-center bg-background p-4">
      <Card className="w-full max-w-sm">
        <CardHeader className="space-y-1">
          <CardTitle className="text-2xl font-bold text-center">Fábrica de Videos</CardTitle>
          <CardDescription className="text-center">
            Ingresá con tu cuenta de Saladillo Vivo
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form action={formAction} onSubmit={handleSubmit} className="space-y-4">
            <input type="hidden" name="redirectTo" value={redirectTo} />
            <div className="space-y-2">
              <label htmlFor="email" className="text-sm font-medium leading-none">
                Email
              </label>
              <input
                id="email"
                name="email"
                type="email"
                placeholder="tu@email.com"
                required
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
              />
            </div>
            <div className="space-y-2">
              <label htmlFor="password" className="text-sm font-medium leading-none">
                Contraseña
              </label>
              <input
                id="password"
                name="password"
                type="password"
                required
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
              />
            </div>
            <Button type="submit" className="w-full" disabled={pending}>
              {pending ? 'Ingresando...' : 'Iniciar Sesión'}
            </Button>
          </form>
          <p className="mt-4 text-center text-xs text-muted-foreground">
            Acceso solo para personal autorizado
          </p>
        </CardContent>
      </Card>
    </div>
  )
}
