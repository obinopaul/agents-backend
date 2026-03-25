// ===== Google OAuth =====
export interface GoogleAuthRequest {
    code: string
    redirect_uri: string
}

export interface GoogleAuthResponse {
    access_token: string
    refresh_token: string
    token_type: string
    expires_in: number
}

// ===== GitHub OAuth =====
export interface GitHubAuthRequest {
    code: string
    redirect_uri: string
}

export interface GitHubAuthResponse {
    access_token: string
    refresh_token: string
    token_type: string
    expires_in: number
}

// ===== Email/Password Login =====
export interface LoginRequest {
    username: string  // Can be email or username
    password: string
    uuid?: string     // Captcha UUID (optional)
    captcha?: string  // Captcha code (optional)
}

export interface LoginResponse {
    access_token: string
    access_token_expire_time: string
    session_uuid: string
    password_expire_days_remaining?: number
    user: {
        id: number
        uuid: string
        username: string
        nickname: string
        email?: string
        avatar?: string
        status: number
        is_superuser: boolean
        is_staff: boolean
    }
}

// ===== Email/Password Registration =====
export interface RegisterRequest {
    email: string
    password: string
    name: string
    confirm_password?: string
}

export interface RegisterResponse {
    access_token: string
    token_type: string
    expires_in: number
    user_id: number
    username: string
}

// ===== Token Refresh =====
export interface RefreshTokenResponse {
    accessToken: string
}

// ===== User Info =====
export interface CurrentUserResponse {
    id: string
    name: string
    email: string
    picture?: string
}
