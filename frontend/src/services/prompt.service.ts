import axiosInstance from '@/lib/axios'

interface EnhancePromptPayload {
    prompt: string
    context?: string
}

interface EnhancePromptResponse {
    original_prompt: string
    enhanced_prompt: string
    reasoning?: string
}

class PromptService {
    async enhancePrompt(
        payload: EnhancePromptPayload
    ): Promise<EnhancePromptResponse> {
        const response = await axiosInstance.post<EnhancePromptResponse>(
            `/agent/enhance-prompt`,
            payload
        )
        // Handle wrapped response format
        const data = response.data as any
        return data?.data || response.data
    }
}

export const promptService = new PromptService()
