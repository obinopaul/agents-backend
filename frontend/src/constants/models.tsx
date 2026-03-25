import { IModel } from '@/typings/settings'

// Provider display names - matches backend PROVIDER_DISPLAY_NAMES
export const PROVIDERS_NAME: { [key: string]: string } = {
    openai: 'OpenAI',
    anthropic: 'Anthropic',
    gemini: 'Google Gemini',
    deepseek: 'DeepSeek',
    groq: 'Groq',
    huggingface: 'HuggingFace',
    ollama: 'Ollama',
    openai_compat: 'OpenAI Compatible',
    vertex: 'Vertex',
    azure: 'Azure',
    custom: 'Custom'
}

// Provider icon paths
export const PROVIDER_ICONS: { [key: string]: string } = {
    openai: '/images/openai.svg',
    anthropic: '/images/anthropic.svg',
    gemini: '/images/gemini.svg',
    deepseek: '/images/deepseek.svg',
    groq: '/images/groq.svg',
    huggingface: '/images/huggingface.svg',
    ollama: '/images/ollama.svg',
    openai_compat: '/images/openai_compat.svg',
    vertex: '/images/vertex.svg',
    azure: '/images/azure.svg',
    google: '/images/google.svg',
    custom: '/images/custom.svg'
}

// Dark mode variants for providers that have them
export const PROVIDER_ICONS_DARK: { [key: string]: string } = {
    openai: '/images/openai-dark.svg',
    anthropic: '/images/anthropic-dark.svg'
}

// Define available models for each provider
export const PROVIDER_MODELS: { [key: string]: IModel[] } = {
    openai: [
        {
            id: 'openai:gpt-5',
            model: 'gpt-5',
            api_type: 'openai',
            display_name: 'GPT-5',
            context_length: 128000,
            supports_vision: true,
            supports_function_calling: true
        },
        {
            id: 'openai:gpt-5.1',
            model: 'gpt-5.1',
            api_type: 'openai',
            display_name: 'GPT-5.1',
            context_length: 128000,
            supports_vision: true,
            supports_function_calling: true
        },
        {
            id: 'openai:gpt-5.2',
            model: 'gpt-5.2',
            api_type: 'openai',
            display_name: 'GPT-5.2',
            context_length: 128000,
            supports_vision: true,
            supports_function_calling: true
        },
        {
            id: 'openai:o4-mini',
            model: 'o4-mini',
            api_type: 'openai',
            display_name: 'o4 Mini',
            context_length: 128000,
            supports_vision: false,
            supports_function_calling: true
        }
    ],
    anthropic: [
        {
            id: 'anthropic:claude-sonnet-4-5-20250929',
            model: 'claude-sonnet-4-5-20250929',
            api_type: 'anthropic',
            display_name: 'Claude Sonnet 4.5',
            context_length: 200000,
            supports_vision: true,
            supports_function_calling: true
        },
        {
            id: 'anthropic:claude-sonnet-4-20250514',
            model: 'claude-sonnet-4-20250514',
            api_type: 'anthropic',
            display_name: 'Claude Sonnet 4',
            context_length: 200000,
            supports_vision: true,
            supports_function_calling: true
        },
        {
            id: 'anthropic:claude-opus-4-20250514',
            model: 'claude-opus-4-20250514',
            api_type: 'anthropic',
            display_name: 'Claude Opus 4',
            context_length: 200000,
            supports_vision: true,
            supports_function_calling: true
        },
        {
            id: 'anthropic:claude-3-7-sonnet-20250219',
            model: 'claude-3-7-sonnet-20250219',
            api_type: 'anthropic',
            display_name: 'Claude 3.7 Sonnet',
            context_length: 200000,
            supports_vision: true,
            supports_function_calling: true
        }
    ],
    gemini: [
        {
            id: 'gemini:gemini-2.5-flash',
            model: 'gemini-2.5-flash',
            api_type: 'gemini',
            display_name: 'Gemini 2.5 Flash',
            context_length: 1000000,
            supports_vision: true,
            supports_function_calling: true
        },
        {
            id: 'gemini:gemini-2.5-pro',
            model: 'gemini-2.5-pro',
            api_type: 'gemini',
            display_name: 'Gemini 2.5 Pro',
            context_length: 1000000,
            supports_vision: true,
            supports_function_calling: true
        }
    ],
    deepseek: [
        {
            id: 'deepseek:deepseek-chat',
            model: 'deepseek-chat',
            api_type: 'deepseek',
            display_name: 'DeepSeek Chat',
            context_length: 64000,
            supports_vision: false,
            supports_function_calling: true
        },
        {
            id: 'deepseek:deepseek-reasoner',
            model: 'deepseek-reasoner',
            api_type: 'deepseek',
            display_name: 'DeepSeek Reasoner',
            context_length: 64000,
            supports_vision: false,
            supports_function_calling: true
        }
    ],
    groq: [
        {
            id: 'groq:llama-3.1-8b-instant',
            model: 'llama-3.1-8b-instant',
            api_type: 'groq',
            display_name: 'Llama 3.1 8B (Groq)',
            context_length: 131072,
            supports_vision: false,
            supports_function_calling: true
        },
        {
            id: 'groq:llama-3.1-70b-versatile',
            model: 'llama-3.1-70b-versatile',
            api_type: 'groq',
            display_name: 'Llama 3.1 70B (Groq)',
            context_length: 131072,
            supports_vision: false,
            supports_function_calling: true
        },
        {
            id: 'groq:mixtral-8x7b-32768',
            model: 'mixtral-8x7b-32768',
            api_type: 'groq',
            display_name: 'Mixtral 8x7B (Groq)',
            context_length: 32768,
            supports_vision: false,
            supports_function_calling: true
        }
    ],
    huggingface: [
        {
            id: 'huggingface:microsoft/Phi-3-mini-4k-instruct',
            model: 'microsoft/Phi-3-mini-4k-instruct',
            api_type: 'huggingface',
            display_name: 'Phi-3 Mini 4K',
            context_length: 4096,
            supports_vision: false,
            supports_function_calling: false
        },
        {
            id: 'huggingface:meta-llama/Meta-Llama-3-8B-Instruct',
            model: 'meta-llama/Meta-Llama-3-8B-Instruct',
            api_type: 'huggingface',
            display_name: 'Llama 3 8B (HF)',
            context_length: 8192,
            supports_vision: false,
            supports_function_calling: false
        }
    ],
    ollama: [
        {
            id: 'ollama:llama3',
            model: 'llama3',
            api_type: 'ollama',
            display_name: 'Llama 3 (Local)',
            context_length: 8192,
            supports_vision: false,
            supports_function_calling: true
        },
        {
            id: 'ollama:codellama',
            model: 'codellama',
            api_type: 'ollama',
            display_name: 'Code Llama (Local)',
            context_length: 16384,
            supports_vision: false,
            supports_function_calling: false
        },
        {
            id: 'ollama:mistral',
            model: 'mistral',
            api_type: 'ollama',
            display_name: 'Mistral (Local)',
            context_length: 8192,
            supports_vision: false,
            supports_function_calling: true
        }
    ],
    openai_compat: [
        {
            id: 'openai_compat:custom',
            model: 'custom',
            api_type: 'openai_compat',
            display_name: 'Custom Model',
            supports_function_calling: true
        }
    ],
    custom: []
}

// Get all models as a flat array
export const getAllModels = (): IModel[] => {
    return Object.values(PROVIDER_MODELS).flat()
}

// Get provider icon with dark mode support
export const getProviderIcon = (provider: string, isDarkMode: boolean = false): string => {
    if (isDarkMode && PROVIDER_ICONS_DARK[provider]) {
        return PROVIDER_ICONS_DARK[provider]
    }
    return PROVIDER_ICONS[provider] || PROVIDER_ICONS.custom
}

// Get provider display name
export const getProviderDisplayName = (provider: string): string => {
    return PROVIDERS_NAME[provider] || provider.charAt(0).toUpperCase() + provider.slice(1)
}
