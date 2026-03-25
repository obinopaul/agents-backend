import { useGoogleLogin } from '@react-oauth/google'
import { Link, useNavigate } from 'react-router'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { zodResolver } from '@hookform/resolvers/zod'
import { useState, useCallback } from 'react'

import { useAuth } from '@/contexts/auth-context'
import { Button } from '@/components/ui/button'
import { Icon } from '@/components/ui/icon'
import { Form, FormControl, FormField, FormItem, FormMessage } from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { toast } from 'sonner'

const FormSchema = z.object({
    name: z.string().min(1, {
        message: 'Name is required'
    }),
    email: z.string().email({ message: 'Invalid email address' }),
    password: z.string().min(6, {
        message: 'Password must be at least 6 characters'
    }),
    confirmPassword: z.string().min(6, {
        message: 'Please confirm your password'
    })
}).refine((data) => data.password === data.confirmPassword, {
    message: "Passwords don't match",
    path: ['confirmPassword']
})

// GitHub OAuth configuration
const GITHUB_CLIENT_ID = import.meta.env.VITE_GITHUB_CLIENT_ID || ''

export function SignupPage() {
    const navigate = useNavigate()
    const { loginWithAuthCode, loginWithGitHub, register: registerUser } = useAuth()
    const [isSubmitting, setIsSubmitting] = useState(false)

    const form = useForm<z.infer<typeof FormSchema>>({
        resolver: zodResolver(FormSchema),
        defaultValues: {
            name: '',
            email: '',
            password: '',
            confirmPassword: ''
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
                toast.error(errorMessage)
            }
        },
        onError: (errorResponse) => {
            console.log('Google Login Failed:', errorResponse)
            toast.error('Google signup failed. Please try again.')
        }
    })

    /**
     * GitHub OAuth signup handler
     * Opens GitHub OAuth authorization in a popup window
     */
    const handleGitHubSignup = useCallback(() => {
        if (!GITHUB_CLIENT_ID) {
            toast.error('GitHub signup is not configured. Please contact support.')
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
                    toast.error(`GitHub signup failed: ${data.error}`)
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
                                : 'GitHub signup failed. Please try again.'
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

    /**
     * Email/password registration handler
     */
    const onSubmit = async (data: z.infer<typeof FormSchema>) => {
        setIsSubmitting(true)
        try {
            await registerUser({
                email: data.email,
                password: data.password,
                name: data.name,
                confirm_password: data.confirmPassword
            })
            toast.success('Account created successfully!')
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
                    : 'Registration failed. Please try again.'
            toast.error(errorMessage)
        } finally {
            setIsSubmitting(false)
        }
    }

    return (
        <div className="flex flex-col items-center justify-center w-full h-full">
            <h1 className="text-[25px] md:text-[32px] font-semibold dark:text-sky-blue">
                Create your account
            </h1>
            <p className="text-[20px] md:text-[28px] dark:text-sky-blue mb-12">
                Join II-Agent today
            </p>

            <div className="flex flex-col w-full justify-center max-w-[510px]">
                <Form {...form}>
                    <form
                        onSubmit={form.handleSubmit(onSubmit)}
                        className="flex flex-col gap-6"
                    >
                        <div className="space-y-4">
                            <FormField
                                control={form.control}
                                name="name"
                                render={({ field }) => (
                                    <FormItem>
                                        <FormControl>
                                            <div className="space-y-2 relative">
                                                <Icon
                                                    name="user"
                                                    className="absolute top-3 left-4 fill-black dark:fill-white"
                                                />
                                                <Input
                                                    id="name"
                                                    className="pl-[56px]"
                                                    type="text"
                                                    placeholder="Enter your name"
                                                    {...field}
                                                />
                                            </div>
                                        </FormControl>
                                        <FormMessage />
                                    </FormItem>
                                )}
                            />
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
                                                    placeholder="Create a password"
                                                    {...field}
                                                />
                                            </div>
                                        </FormControl>
                                        <FormMessage />
                                    </FormItem>
                                )}
                            />
                            <FormField
                                control={form.control}
                                name="confirmPassword"
                                render={({ field }) => (
                                    <FormItem>
                                        <FormControl>
                                            <div className="space-y-2 relative">
                                                <Icon
                                                    name="lock"
                                                    className="absolute top-3 left-4 fill-black dark:fill-white"
                                                />
                                                <Input
                                                    id="confirmPassword"
                                                    className="pl-[56px]"
                                                    type="password"
                                                    placeholder="Confirm your password"
                                                    {...field}
                                                />
                                            </div>
                                        </FormControl>
                                        <FormMessage />
                                    </FormItem>
                                )}
                            />
                        </div>
                        <div className="w-full flex justify-center">
                            <Button
                                type="submit"
                                size="xl"
                                className="bg-firefly text-sky-blue-2 dark:bg-sky-blue dark:text-black font-semibold w-full max-w-[247px]"
                                disabled={!form.formState.isValid || isSubmitting}
                            >
                                {isSubmitting ? 'Creating account...' : 'Sign up'}
                            </Button>
                        </div>
                    </form>
                </Form>
                
                <div className="flex justify-center items-center gap-2 dark:text-white text-sm mt-6">
                    <span>Already have an account?</span>
                    <Link
                        to="/login"
                        className="dark:text-white text-sm font-semibold underline"
                    >
                        Sign in
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
                            onClick={handleGitHubSignup}
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

export const Component = SignupPage
