import axiosInstance from '@/lib/axios'
import { User } from '@/state/slice/user'
import {
    GoogleAuthResponse,
    RefreshTokenResponse,
    GoogleAuthRequest,
    GitHubAuthRequest,
    GitHubAuthResponse,
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    RegisterResponse
} from '@/typings/auth'

/**
 * Authentication service for handling user authentication.
 * 
 * Backend endpoint mapping:
 * - Google OAuth: /api/v1/oauth2/google/callback/code (frontend auth-code flow)
 * - GitHub OAuth: /api/v1/oauth2/github/callback/code (frontend auth-code flow)
 * - Email/Password Login: /api/v1/auth/login
 * - Email/Password Register: /api/v1/auth/register
 * - Current User: /api/v1/sys/users/me
 * - Logout: /api/v1/auth/logout
 * - Refresh Token: /api/v1/auth/refresh
 */
class AuthService {
    /**
     * Exchange Google OAuth authorization code for access token.
     * Uses the frontend auth-code endpoint that handles @react-oauth/google flow.
     * Backend handles user creation if not exists and returns JWT tokens.
     */
    async googleAuth(params: GoogleAuthRequest): Promise<GoogleAuthResponse> {
        const response = await axiosInstance.get<any>(
            '/api/v1/oauth2/google/callback/code',
            {
                params
            }
        )
        // Handle wrapped response { code: 200, data: {...}, msg: "Success" }
        const data = response.data
        if (data && data.data) {
            return data.data
        }
        return data
    }

    /**
     * Exchange GitHub OAuth authorization code for access token.
     * Uses the frontend auth-code endpoint that handles GitHub OAuth flow.
     * Backend handles user creation if not exists and returns JWT tokens.
     */
    async githubAuth(params: GitHubAuthRequest): Promise<GitHubAuthResponse> {
        const response = await axiosInstance.get<any>(
            '/api/v1/oauth2/github/callback/code',
            {
                params
            }
        )
        // Handle wrapped response { code: 200, data: {...}, msg: "Success" }
        const data = response.data
        if (data && data.data) {
            return data.data
        }
        return data
    }

    /**
     * Login with email/username and password.
     * Returns JWT access token and user info.
     */
    async login(params: LoginRequest): Promise<LoginResponse> {
        const response = await axiosInstance.post<any>(
            '/api/v1/auth/login',
            params
        )
        // Handle wrapped response { code: 200, data: {...}, msg: "Success" }
        const data = response.data
        if (data && data.data) {
            return data.data
        }
        return data
    }

    /**
     * Register a new user with email and password.
     * Returns JWT access token for immediate login after successful registration.
     */
    async register(params: RegisterRequest): Promise<RegisterResponse> {
        const response = await axiosInstance.post<any>(
            '/api/v1/auth/register',
            params
        )
        // Handle wrapped response { code: 200, data: {...}, msg: "Success" }
        const data = response.data
        if (data && data.data) {
            return data.data
        }
        return data
    }

    /**
     * Logout the current user and invalidate tokens.
     */
    async logout(): Promise<void> {
        await axiosInstance.post('/api/v1/auth/logout')
    }

    /**
     * Get the currently authenticated user's information.
     * Returns user profile from the system API.
     */
    async getCurrentUser(): Promise<User> {
        // Backend returns { code: 200, data: user, msg: "Success" }
        // Axios interceptor or wrapper should handle unwrapping
        const response = await axiosInstance.get<User>('/api/v1/sys/users/me')
        // Handle wrapped response if needed
        const data = response.data as any
        if (data && data.data) {
            return data.data
        }
        return response.data
    }

    /**
     * Refresh the access token using the refresh token.
     * The refresh token is stored in an HttpOnly cookie.
     */
    async refreshToken(): Promise<RefreshTokenResponse> {
        const response = await axiosInstance.post<RefreshTokenResponse>(
            '/api/v1/auth/refresh'
        )
        // Handle wrapped response if needed
        const data = response.data as any
        if (data && data.data) {
            return data.data
        }
        return response.data
    }
}

export const authService = new AuthService()
