import axiosInstance from '@/lib/axios'
import {
    GetAvailableModelsResponse,
    GetMcpSettingsResponse,
    IMcpSettings,
    IModel,
    UpdateMcpSettingsPayload
} from '@/typings/settings'

/**
 * Settings service for user LLM and MCP configurations.
 * 
 * Backend endpoint mapping:
 * - Model settings: /agent/user-settings/models
 * - MCP settings: /agent/user-settings/mcp
 * 
 * Note: Backend wraps responses in { code, data, msg } format.
 */
class SettingsService {
    // =========================================================================
    // Model Settings (LLM Configuration)
    // =========================================================================

    /**
     * Get available LLM models from backend configuration.
     */
    async getAvailableModels(): Promise<GetAvailableModelsResponse> {
        const response = await axiosInstance.get<GetAvailableModelsResponse>(
            `/agent/user-settings/models`
        )
        const data = response.data as any
        // Handle wrapped response
        if (data && data.data) {
            return data.data
        }
        return response.data
    }

    /**
     * Create a new model configuration.
     */
    async createModel(payload: IModel): Promise<IModel> {
        const response = await axiosInstance.post<IModel>(
            '/agent/user-settings/models',
            payload
        )
        const data = response.data as any
        return data?.data || response.data
    }

    /**
     * Update an existing model configuration.
     */
    async updateModel(id: string, payload: Partial<IModel>): Promise<IModel> {
        const response = await axiosInstance.put<IModel>(
            `/agent/user-settings/models/${id}`,
            payload
        )
        const data = response.data as any
        return data?.data || response.data
    }

    /**
     * Delete a model configuration.
     */
    async deleteModel(id: string): Promise<void> {
        await axiosInstance.delete(`/agent/user-settings/models/${id}`)
    }

    /**
     * Get a specific model by ID.
     */
    async getModelById(id: string): Promise<IModel> {
        const response = await axiosInstance.get<IModel>(
            `/agent/user-settings/models/${id}`
        )
        const data = response.data as any
        return data?.data || response.data
    }

    // =========================================================================
    // MCP Settings (Tool Configuration)
    // =========================================================================

    /**
     * Get user's MCP tool configurations.
     */
    async getMcpSettings(): Promise<GetMcpSettingsResponse> {
        const response = await axiosInstance.get<GetMcpSettingsResponse>(
            '/agent/user-settings/mcp'
        )
        const data = response.data as any
        if (data && data.data) {
            return { settings: data.data.settings || data.data || [] }
        }
        return response.data
    }

    /**
     * Create MCP settings.
     */
    async createMcpSettings(
        payload: UpdateMcpSettingsPayload
    ): Promise<IMcpSettings> {
        const response = await axiosInstance.post<IMcpSettings>(
            '/agent/user-settings/mcp',
            payload
        )
        const data = response.data as any
        return data?.data || response.data
    }

    /**
     * Update MCP settings.
     */
    async updateMcpSettings(
        id: string,
        payload: UpdateMcpSettingsPayload
    ): Promise<IMcpSettings> {
        const response = await axiosInstance.put<IMcpSettings>(
            `/agent/user-settings/mcp/${id}`,
            payload
        )
        const data = response.data as any
        return data?.data || response.data
    }

    /**
     * Delete MCP settings.
     */
    async deleteMcpSettings(id: string): Promise<void> {
        await axiosInstance.delete(`/agent/user-settings/mcp/${id}`)
    }

    /**
     * Get Codex MCP configuration.
     */
    async getCodexSettings(): Promise<IMcpSettings | null> {
        const response = await axiosInstance.get<IMcpSettings | null>(
            '/agent/user-settings/mcp/codex'
        )
        const data = response.data as any
        return data?.data || response.data
    }

    /**
     * Get Claude Code MCP configuration.
     */
    async getClaudeCodeSettings(): Promise<IMcpSettings | null> {
        const response = await axiosInstance.get<IMcpSettings | null>(
            '/agent/user-settings/mcp/claude-code'
        )
        const data = response.data as any
        return data?.data || response.data
    }

    /**
     * Configure Codex MCP with API key and settings.
     */
    async configureCodex(payload: {
        auth_json?: object
        model?: string
        apikey?: string
        model_reasoning_effort?: string
        search?: boolean
    }): Promise<IMcpSettings> {
        const response = await axiosInstance.post<IMcpSettings>(
            '/agent/user-settings/mcp/codex',
            payload
        )
        const data = response.data as any
        return data?.data || response.data
    }

    /**
     * Configure Claude Code MCP via OAuth.
     */
    async configureClaudeCode(payload: {
        authorization_code?: string
    }): Promise<IMcpSettings> {
        const response = await axiosInstance.post<IMcpSettings>(
            '/agent/user-settings/mcp/claude-code',
            payload
        )
        const data = response.data as any
        return data?.data || response.data
    }
}

export const settingsService = new SettingsService()
