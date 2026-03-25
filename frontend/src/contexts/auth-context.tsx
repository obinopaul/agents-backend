import { ACCESS_TOKEN } from '@/constants/auth'
import { authService } from '@/services/auth.service'
import { settingsService } from '@/services/settings.service'
import {
    selectAvailableModels,
    selectSelectedModel,
    setAvailableModels,
    setSelectedModel,
    store,
    userApi,
    sessionApi
} from '@/state'
import { useAppDispatch, useAppSelector } from '@/state/store'
import { setUser, clearUser, setLoading } from '@/state/slice/user'
import type { User } from '@/state/slice/user'
import { fetchWishlist, clearFavorites } from '@/state/slice/favorites'
import { createContext, useContext, useEffect, ReactNode, useCallback } from 'react'
import { RegisterRequest, LoginRequest } from '@/typings/auth'

interface AuthContextType {
    user: User | null
    isAuthenticated: boolean
    loginWithAuthCode: (authCode: string) => Promise<void>
    loginWithGitHub: (code: string) => Promise<void>
    loginWithCredentials: (credentials: LoginRequest) => Promise<void>
    register: (data: RegisterRequest) => Promise<void>
    logout: () => void
    isLoading: boolean
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

/**
 * Check if a JWT token is expired by decoding its payload.
 * This is a client-side check for fast validation without API calls.
 * 
 * @param token - JWT access token string
 * @returns true if expired or malformed, false if still valid
 */
const isTokenExpired = (token: string): boolean => {
    try {
        // JWT structure: header.payload.signature
        const parts = token.split('.')
        if (parts.length !== 3) {
            return true // Malformed token
        }
        
        // Decode base64url payload (handle URL-safe base64)
        const base64 = parts[1].replace(/-/g, '+').replace(/_/g, '/')
        const payload = JSON.parse(atob(base64))
        
        // Check expiration claim (exp is in seconds, Date.now() is in ms)
        if (!payload.exp) {
            return false // No expiration claim, treat as not expired
        }
        
        // Add 30 second buffer to avoid edge cases
        const expirationMs = payload.exp * 1000
        const bufferMs = 30 * 1000
        return Date.now() >= (expirationMs - bufferMs)
    } catch (error) {
        console.warn('Failed to decode JWT token:', error)
        return true // Treat decode failures as expired for security
    }
}

export function AuthProvider({ children }: { children: ReactNode }) {
    const dispatch = useAppDispatch()
    const { user, isLoading } = useAppSelector((state) => state.user)

    // PRODUCTION FIX: isAuthenticated now derives from BOTH:
    // 1. Token exists in localStorage
    // 2. User has been validated (either via API or cached)
    // This prevents redirect loops when token exists but is invalid
    const isAuthenticated = !!user && !!localStorage.getItem(ACCESS_TOKEN)

    const fetchAvailableModels = useCallback(async () => {
        try {
            const data = await settingsService.getAvailableModels()
            dispatch(setAvailableModels(data?.models || []))

            if (data?.models?.length) {
                const firstModel = data.models[0]

                const state = store.getState()
                const currentSelectedModel = selectSelectedModel(state)
                const currentAvailableModels = selectAvailableModels(state)

                const selectedModelStillAvailable = currentAvailableModels.find(
                    (model) => model.id === currentSelectedModel
                )

                if (!currentSelectedModel || !selectedModelStillAvailable) {
                    dispatch(setSelectedModel(firstModel.id))
                }
            }
        } catch (error) {
            console.log('Failed to fetch llm models', error)
        }
    }, [dispatch])

    useEffect(() => {
        const initializeAuth = async () => {
            try {
                const accessToken = localStorage.getItem(ACCESS_TOKEN)

                // No token - definitely not authenticated
                if (!accessToken) {
                    dispatch(setLoading(false))
                    return
                }

                // STEP 1: Client-side JWT expiration check (fast, no network)
                // This catches obviously expired tokens without waiting for API
                if (isTokenExpired(accessToken)) {
                    console.warn('Auth: Token expired, clearing stale session')
                    localStorage.removeItem(ACCESS_TOKEN)
                    localStorage.removeItem('user')
                    dispatch(clearUser())
                    dispatch(setLoading(false))
                    return
                }

                // STEP 2: Server-side validation (authoritative)
                // Even if token looks valid client-side, backend is the source of truth
                try {
                    const userRes = await authService.getCurrentUser()
                    dispatch(setUser(userRes))
                    await fetchAvailableModels()
                    // Fetch user's wishlist after successful authentication
                    dispatch(fetchWishlist())
                } catch (apiError) {
                    console.error('Auth: Token validation failed:', apiError)
                    
                    // CRITICAL FIX: Clear stale token so user can access /login
                    // Without this, user gets stuck in redirect loop
                    localStorage.removeItem(ACCESS_TOKEN)
                    localStorage.removeItem('user')
                    dispatch(clearUser())
                    dispatch(setLoading(false))
                    
                    // Note: axios interceptor will also handle 401 redirect,
                    // but we clear here for immediate effect on auth state
                }
            } catch (error) {
                console.error('Error initializing auth:', error)
                // On any unexpected error, ensure loading state is resolved
                dispatch(setLoading(false))
            }
        }

        initializeAuth()
    }, [dispatch, fetchAvailableModels])

    /**
     * Helper function to complete login flow after receiving token
     */
    const completeLogin = async (accessToken: string) => {
        // Store the access token immediately to trigger WebSocket connection
        localStorage.setItem(ACCESS_TOKEN, accessToken)
        // Dispatch a custom event to notify WebSocket to connect immediately
        window.dispatchEvent(new CustomEvent('auth-token-set'))

        // Get user information using the access token
        const userRes = await authService.getCurrentUser()
        dispatch(setUser(userRes))
        await fetchAvailableModels()
        // Fetch user's wishlist after successful login
        dispatch(fetchWishlist())
    }

    /**
     * Login with Google OAuth authorization code
     * Uses 'postmessage' as redirect_uri for @react-oauth/google popup flow
     */
    const loginWithAuthCode = async (code: string) => {
        try {
            const res = await authService.googleAuth({
                code,
                redirect_uri: 'postmessage'  // Special value for @react-oauth/google popup flow
            })
            await completeLogin(res.access_token)
        } catch (error) {
            console.error('Error handling Google auth code:', error)
            throw error
        }
    }

    /**
     * Login with GitHub OAuth authorization code
     * Uses the /oauth/github/callback path for the popup flow
     */
    const loginWithGitHub = async (code: string) => {
        try {
            const res = await authService.githubAuth({
                code,
                redirect_uri: window.location.origin + '/oauth/github/callback'
            })
            await completeLogin(res.access_token)
        } catch (error) {
            console.error('Error handling GitHub auth code:', error)
            throw error
        }
    }

    /**
     * Login with email/username and password
     */
    const loginWithCredentials = async (credentials: LoginRequest) => {
        try {
            const res = await authService.login(credentials)
            await completeLogin(res.access_token)
        } catch (error) {
            console.error('Error handling credential login:', error)
            throw error
        }
    }

    /**
     * Register a new user account with email and password
     */
    const register = async (data: RegisterRequest) => {
        try {
            const res = await authService.register(data)
            await completeLogin(res.access_token)
        } catch (error) {
            console.error('Error handling registration:', error)
            throw error
        }
    }

    const logout = () => {
        localStorage.removeItem(ACCESS_TOKEN)
        dispatch(clearUser())
        dispatch(clearFavorites())
        // Reset all RTK Query cache to prevent data leakage between users
        dispatch(userApi.util.resetApiState())
        dispatch(sessionApi.util.resetApiState())
    }

    const value: AuthContextType = {
        user,
        isAuthenticated,
        loginWithAuthCode,
        loginWithGitHub,
        loginWithCredentials,
        register,
        logout,
        isLoading
    }

    return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
    const context = useContext(AuthContext)
    if (context === undefined) {
        throw new Error('useAuth must be used within an AuthProvider')
    }
    return context
}
