import { useGoogleLogin } from '@react-oauth/google'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { zodResolver } from '@hookform/resolvers/zod'

import { useAuth } from '@/contexts/auth-context'
import { Button } from '@/components/ui/button'
import { Icon } from '@/components/ui/icon'
import { Form, FormControl, FormField, FormItem, FormMessage } from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { ACCESS_TOKEN } from '@/constants/auth'
import { authService } from '@/services/auth.service'
import { useAppDispatch } from '@/state/store'
import { setUser } from '@/state/slice/user'
import { fetchWishlist } from '@/state/slice/favorites'
import { toast } from 'sonner'

const FormSchema = z.object({
    email: z.string().email({ message: 'Invalid email address' }),
    password: z.string().min(6, {
        message: 'Password must be at least 6 characters'
    })
})

type IiAuthPayload = {
    access_token: string
    refresh_token?: string
    token_type?: string
    expires_in?: number
}

// GitHub OAuth configuration
const GITHUB_CLIENT_ID = import.meta.env.VITE_GITHUB_CLIENT_ID || ''

export function LoginPage() {
    const navigate = useNavigate()
    const { loginWithAuthCode, loginWithGitHub, loginWithCredentials } = useAuth()
    const dispatch = useAppDispatch()
    const [isSubmitting, setIsSubmitting] = useState(false)

    const form = useForm<z.infer<typeof FormSchema>>({
        resolver: zodResolver(FormSchema),
        defaultValues: {
            email: '',
            password: ''
        }
    })

    const googleLogin = useGoogleLogin({
        flow: 'auth-code',
        onSuccess: async (codeResponse) => {
            try {
                await loginWithAuthCode(codeResponse.code)
                navigate('/')
            } catch (error: unknown) {
                const apiError = error as {
                    response: { data: { detail: string; msg?: string } }
                }
                const errorMessage =
                    typeof apiError?.response?.data?.msg === 'string'
                        ? apiError.response.data.msg
                        : typeof apiError?.response?.data?.detail === 'string'
                        ? apiError.response.data.detail
                        : 'Login failed. Please try again.'
                if (errorMessage?.includes('beta')) {
                    toast.info(errorMessage)
                } else {
                    toast.error(errorMessage)
                }
            }
        },
        onError: (errorResponse) => {
            console.log('Google Login Failed:', errorResponse)
            toast.error('Google login failed. Please try again.')
        }
    })

    /**
     * GitHub OAuth login handler
     * Opens GitHub OAuth authorization in a popup window
     */
    const handleGitHubLogin = useCallback(() => {
        if (!GITHUB_CLIENT_ID) {
            toast.error('GitHub login is not configured. Please contact support.')
            return
        }

        // Generate a random state for CSRF protection
        const state = Math.random().toString(36).substring(2, 15)
        sessionStorage.setItem('github_oauth_state', state)

        // GitHub OAuth authorization URL
        const redirectUri = window.location.origin + '/oauth/github/callback'
        const scope = 'user:email'
        const githubAuthUrl = `https://github.com/login/oauth/authorize?client_id=${GITHUB_CLIENT_ID}&redirect_uri=${encodeURIComponent(redirectUri)}&scope=${encodeURIComponent(scope)}&state=${state}`

        // Open in popup
        const width = 600
        const height = 700
        const left = window.screenX + (window.outerWidth - width) / 2
        const top = window.screenY + (window.outerHeight - height) / 2
        const popup = window.open(
            githubAuthUrl,
            'github-oauth',
            `width=${width},height=${height},left=${left},top=${top}`
        )

        // Listen for the callback from the popup
        const handleMessage = async (event: MessageEvent) => {
            if (event.origin !== window.location.origin) return
            
            const data = event.data as { type?: string; code?: string; error?: string }
            if (data.type === 'github-oauth-callback') {
                window.removeEventListener('message', handleMessage)
                popup?.close()

                if (data.error) {
                    toast.error(`GitHub login failed: ${data.error}`)
                    return
                }

                if (data.code) {
                    try {
                        await loginWithGitHub(data.code)
                        navigate('/')
                    } catch (error: unknown) {
                        const apiError = error as {
                            response: { data: { detail: string; msg?: string } }
                        }
                        const errorMessage =
                            typeof apiError?.response?.data?.msg === 'string'
                                ? apiError.response.data.msg
                                : typeof apiError?.response?.data?.detail === 'string'
                                ? apiError.response.data.detail
                                : 'GitHub login failed. Please try again.'
                        toast.error(errorMessage)
                    }
                }
            }
        }

        window.addEventListener('message', handleMessage)

        // Clean up if popup is closed manually
        const checkClosed = setInterval(() => {
            if (popup?.closed) {
                clearInterval(checkClosed)
                window.removeEventListener('message', handleMessage)
            }
        }, 1000)
    }, [loginWithGitHub, navigate])

    const apiBaseUrl = useMemo(
        () => import.meta.env.VITE_API_URL || 'http://localhost:8000',
        []
    )
    const apiOrigin = useMemo(() => {
        try {
            return new URL(apiBaseUrl).origin
        } catch (error) {
            console.error('Invalid API base URL:', error)
            return apiBaseUrl
        }
    }, [apiBaseUrl])

    const authHandledRef = useRef(false)

    const handleAuthSuccess = useCallback(
        async (payload: IiAuthPayload | null | undefined) => {
            if (!payload || typeof payload.access_token !== 'string') {
                authHandledRef.current = false
                return
            }

            if (authHandledRef.current) {
                return
            }
            authHandledRef.current = true

            try {
                localStorage.setItem(ACCESS_TOKEN, payload.access_token)
                window.dispatchEvent(new CustomEvent('auth-token-set'))

                const userRes = await authService.getCurrentUser()
                dispatch(setUser(userRes))
                dispatch(fetchWishlist())

                navigate('/')
            } catch (error) {
                console.error('Failed to finalize login:', error)
                authHandledRef.current = false
            }
        },
        [dispatch, navigate]
    )

    useEffect(() => {
        const handler = (event: MessageEvent) => {
            if (event.origin !== apiOrigin) {
                return
            }

            const data = event.data as {
                type?: string
                payload?: IiAuthPayload
            }

            if (!data || data.type !== 'ii-auth-success') {
                return
            }

            void handleAuthSuccess(data.payload)
        }

        window.addEventListener('message', handler)
        return () => window.removeEventListener('message', handler)
    }, [apiOrigin, handleAuthSuccess])

    useEffect(() => {
        const hash = window.location.hash
        if (!hash || !hash.includes('ii-auth=')) {
            return
        }

        const params = new URLSearchParams(hash.slice(1))
        const encoded = params.get('ii-auth')
        params.delete('ii-auth')

        const cleanHash = params.toString()
        const cleanUrl = `${window.location.pathname}${window.location.search}${cleanHash ? `#${cleanHash}` : ''}`
        window.history.replaceState(null, '', cleanUrl)

        if (!encoded) {
            return
        }

        try {
            const payload = JSON.parse(
                decodeURIComponent(encoded)
            ) as IiAuthPayload
            void handleAuthSuccess(payload)
        } catch (error) {
            console.error('Failed to parse auth payload from hash:', error)
            authHandledRef.current = false
        }
    }, [handleAuthSuccess])

    /**
     * Email/password login handler
     */
    const onSubmit = async (data: z.infer<typeof FormSchema>) => {
        setIsSubmitting(true)
        try {
            await loginWithCredentials({
                username: data.email, // Backend accepts email as username
                password: data.password
            })
            navigate('/')
        } catch (error: unknown) {
            const apiError = error as {
                response: { data: { detail: string; msg?: string } }
            }
            const errorMessage =
                typeof apiError?.response?.data?.msg === 'string'
                    ? apiError.response.data.msg
                    : typeof apiError?.response?.data?.detail === 'string'
                    ? apiError.response.data.detail
                    : 'Login failed. Please check your credentials and try again.'
            toast.error(errorMessage)
        } finally {
            setIsSubmitting(false)
        }
    }

    return (
        <div className="flex flex-col items-center justify-center w-full h-full">
            <h1 className="text-[25px] md:text-[32px] font-semibold dark:text-sky-blue">
                Welcome to II-Agent
            </h1>
            <p className="text-[20px] md:text-[28px] dark:text-sky-blue mb-12">
                Helping you with your task today
            </p>

            <div className="flex flex-col w-full justify-center max-w-[510px]">
                {/* Email/Password Form */}
                <Form {...form}>
                    <form
                        onSubmit={form.handleSubmit(onSubmit)}
                        className="flex flex-col gap-6"
                    >
                        <div className="space-y-4">
                            <FormField
                                control={form.control}
                                name="email"
                                render={({ field }) => (
                                    <FormItem>
                                        <FormControl>
                                            <div className="space-y-2 relative">
                                                <Icon
                                                    name="email"
                                                    className="absolute top-3 left-4 fill-black dark:fill-white"
                                                />
                                                <Input
                                                    id="email"
                                                    className="pl-[56px]"
                                                    type="text"
                                                    placeholder="Enter your email address"
                                                    {...field}
                                                />
                                            </div>
                                        </FormControl>
                                        <FormMessage />
                                    </FormItem>
                                )}
                            />
                            <div className="space-y-2 text-right">
                                <FormField
                                    control={form.control}
                                    name="password"
                                    render={({ field }) => (
                                        <FormItem>
                                            <FormControl>
                                                <div className="space-y-2 relative">
                                                    <Icon
                                                        name="key"
                                                        className="absolute top-3 left-4 fill-black dark:fill-white"
                                                    />
                                                    <Input
                                                        id="password"
                                                        className="pl-[56px]"
                                                        type="password"
                                                        placeholder="Enter your password"
                                                        {...field}
                                                    />
                                                </div>
                                            </FormControl>
                                            <FormMessage />
                                        </FormItem>
                                    )}
                                />
                                <Link
                                    to="/forgot-password"
                                    className="text-sm underline dark:text-white/70 hover:dark:text-white"
                                >
                                    Forgot your password?
                                </Link>
                            </div>
                        </div>
                        <div className="w-full flex justify-center">
                            <Button
                                type="submit"
                                size="xl"
                                className="bg-firefly text-sky-blue-2 dark:bg-sky-blue dark:text-black font-semibold w-full max-w-[247px]"
                                disabled={!form.formState.isValid || isSubmitting}
                            >
                                {isSubmitting ? 'Signing in...' : 'Sign in'}
                            </Button>
                        </div>
                    </form>
                </Form>
                
                <div className="flex justify-center items-center gap-2 dark:text-white text-sm mt-6">
                    <span>Don&apos;t have an account yet?</span>
                    <Link
                        to="/signup"
                        className="dark:text-white text-sm font-semibold underline"
                    >
                        Sign up
                    </Link>
                </div>
                
                <div className="flex w-full items-center gap-4 my-8">
                    <p className="flex-1 dark:bg-white/[0.31] bg-gray-300 h-[1px]"></p>
                    <span className="text-sm dark:text-white font-semibold">
                        OR
                    </span>
                    <p className="flex-1 dark:bg-white/[0.31] bg-gray-300 h-[1px]"></p>
                </div>

                {/* OAuth Buttons */}
                <div className="space-y-3">
                    <Button
                        size="xl"
                        onClick={() => googleLogin()}
                        className="w-full bg-white text-black font-semibold shadow-btn hover:bg-gray-100"
                    >
                        <Icon name="google" className="size-[22px]" />
                        Continue with Google
                    </Button>
                    
                    {GITHUB_CLIENT_ID && (
                        <Button
                            size="xl"
                            onClick={handleGitHubLogin}
                            className="w-full bg-[#24292e] text-white font-semibold shadow-btn hover:bg-[#3d4449]"
                        >
                            <Icon name="github" className="size-[22px]" />
                            Continue with GitHub
                        </Button>
                    )}
                </div>
            </div>
        </div>
    )
}

export const Component = LoginPage
