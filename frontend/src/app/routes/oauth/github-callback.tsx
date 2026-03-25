import { useEffect } from 'react'
import { useSearchParams } from 'react-router'

/**
 * GitHub OAuth Callback Page
 * 
 * This page handles the OAuth callback from GitHub when using popup-based authentication.
 * It receives the authorization code and state from GitHub, validates the state,
 * and sends the code back to the parent window via postMessage.
 */
export function GitHubCallback() {
    const [searchParams] = useSearchParams()

    useEffect(() => {
        const code = searchParams.get('code')
        const state = searchParams.get('state')
        const error = searchParams.get('error')
        const errorDescription = searchParams.get('error_description')

        // Validate state to prevent CSRF attacks
        const savedState = sessionStorage.getItem('github_oauth_state')
        
        if (error) {
            // Send error back to parent window
            if (window.opener) {
                window.opener.postMessage(
                    {
                        type: 'github-oauth-callback',
                        error: errorDescription || error
                    },
                    window.location.origin
                )
            }
            return
        }

        if (!code) {
            if (window.opener) {
                window.opener.postMessage(
                    {
                        type: 'github-oauth-callback',
                        error: 'No authorization code received from GitHub'
                    },
                    window.location.origin
                )
            }
            return
        }

        if (state && savedState && state !== savedState) {
            if (window.opener) {
                window.opener.postMessage(
                    {
                        type: 'github-oauth-callback',
                        error: 'Invalid state parameter. Please try again.'
                    },
                    window.location.origin
                )
            }
            return
        }

        // Clear saved state
        sessionStorage.removeItem('github_oauth_state')

        // Send the code back to the parent window
        if (window.opener) {
            window.opener.postMessage(
                {
                    type: 'github-oauth-callback',
                    code
                },
                window.location.origin
            )
        } else {
            // If no opener (user navigated directly), redirect to login
            window.location.href = '/login?error=github_popup_closed'
        }
    }, [searchParams])

    return (
        <div className="flex flex-col items-center justify-center w-full h-full min-h-screen">
            <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-sky-blue"></div>
            <p className="mt-4 text-lg dark:text-white">
                Completing GitHub authentication...
            </p>
        </div>
    )
}

export const Component = GitHubCallback
