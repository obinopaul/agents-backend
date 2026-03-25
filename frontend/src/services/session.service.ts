import axiosInstance from '@/lib/axios'
import {
    ISession,
    PresentationListResponse,
    UpdateSlideRequest,
    UpdateSlideResponse
} from '@/typings/agent'
import {
    SessionsResponse,
    SessionEventsResponse,
    CreateSessionRequest,
    UpdateSessionRequest,
    SessionFile
} from '@/typings/session'

/**
 * Session management service for chat sessions.
 * 
 * Backend endpoint mapping:
 * - All session endpoints: /agent/chat-sessions/*
 * - Slides: /agent/sandboxes/db/presentations
 * 
 * Note: Backend wraps responses in { code, data, msg } format.
 */
class SessionService {
    /**
     * Get paginated list of user's sessions.
     */
    async getSessions({
        page = 1,
        limit = 20,
        public_only = false
    }): Promise<ISession[]> {
        const response = await axiosInstance.get<SessionsResponse>(
            `/agent/chat-sessions`,
            {
                params: { page, per_page: limit, public_only }
            }
        )
        // Handle wrapped response
        const data = response.data as any
        if (data && data.data) {
            return data.data.sessions || data.data || []
        }
        return response.data.sessions || []
    }

    /**
     * Get a specific session by ID.
     */
    async getSession(sessionId: string): Promise<ISession> {
        const response = await axiosInstance.get<ISession>(
            `/agent/chat-sessions/${sessionId}`
        )
        const data = response.data as any
        return data?.data || response.data
    }

    /**
     * Get a public session (no auth required).
     */
    async getPublicSession(sessionId: string): Promise<ISession> {
        const response = await axiosInstance.get<ISession>(
            `/agent/chat-sessions/${sessionId}/public`
        )
        const data = response.data as any
        return data?.data || response.data
    }

    /**
     * Get events (message history) for a session.
     */
    async getSessionEvents(sessionId: string): Promise<SessionEventsResponse> {
        const response = await axiosInstance.get<SessionEventsResponse>(
            `/agent/chat-sessions/${sessionId}/events`
        )
        const data = response.data as any
        return data?.data || response.data
    }

    /**
     * Get events for a public session.
     */
    async getPublicSessionEvents(
        sessionId: string
    ): Promise<SessionEventsResponse> {
        const response = await axiosInstance.get<SessionEventsResponse>(
            `/agent/chat-sessions/${sessionId}/public/events`
        )
        const data = response.data as any
        return data?.data || response.data
    }

    /**
     * Get files associated with a session.
     */
    async getSessionFiles(sessionId: string): Promise<SessionFile[]> {
        const response = await axiosInstance.get<SessionFile[]>(
            `/agent/chat-sessions/${sessionId}/files`
        )
        const data = response.data as any
        return data?.data || response.data
    }

    /**
     * Create a new chat session.
     */
    async createSession(data: CreateSessionRequest): Promise<ISession> {
        const response = await axiosInstance.post<ISession>(
            '/agent/chat-sessions',
            data
        )
        const responseData = response.data as any
        return responseData?.data || response.data
    }

    /**
     * Delete a session.
     */
    async deleteSession(sessionId: string): Promise<void> {
        await axiosInstance.delete(`/agent/chat-sessions/${sessionId}`)
    }

    /**
     * Update session metadata.
     */
    async updateSession(
        sessionId: string,
        data: UpdateSessionRequest
    ): Promise<ISession> {
        const response = await axiosInstance.patch<ISession>(
            `/agent/chat-sessions/${sessionId}`,
            data
        )
        const responseData = response.data as any
        return responseData?.data || response.data
    }

    /**
     * Get slides/presentations for a session.
     */
    async getSessionSlides(
        sessionId: string
    ): Promise<PresentationListResponse> {
        const response = await axiosInstance.get<PresentationListResponse>(
            `/agent/sandboxes/db/presentations`,
            { params: { thread_id: sessionId } }
        )
        const data = response.data as any
        return data?.data || response.data
    }

    /**
     * Get public slides for a session.
     */
    async getPublicSessionSlides(
        sessionId: string
    ): Promise<PresentationListResponse> {
        const response = await axiosInstance.get<PresentationListResponse>(
            `/agent/sandboxes/db/presentations`,
            { params: { thread_id: sessionId, public: true } }
        )
        const data = response.data as any
        return data?.data || response.data
    }

    /**
     * Update a slide.
     */
    async updateSlide(
        sessionId: string,
        data: UpdateSlideRequest
    ): Promise<UpdateSlideResponse> {
        const response = await axiosInstance.post<UpdateSlideResponse>(
            `/agent/sandboxes/db/slide`,
            { ...data, thread_id: sessionId }
        )
        const responseData = response.data as any
        return responseData?.data || response.data
    }

    /**
     * Publish a session (make it publicly accessible).
     */
    async publishSession(sessionId: string): Promise<void> {
        await axiosInstance.post(`/agent/chat-sessions/${sessionId}/publish`)
    }

    /**
     * Unpublish a session (make it private).
     */
    async unpublishSession(sessionId: string): Promise<void> {
        await axiosInstance.post(`/agent/chat-sessions/${sessionId}/unpublish`)
    }
}

export const sessionService = new SessionService()
