import { IModel } from '@/typings/settings'
import { 
    PROVIDERS_NAME, 
    PROVIDER_ICONS, 
    PROVIDER_ICONS_DARK,
    getProviderIcon 
} from '@/constants/models'
import { GroupedModels } from './types'

/**
 * Group models by their provider
 */
export function groupModelsByProvider(models: IModel[]): GroupedModels {
    const grouped: GroupedModels = {}
    
    // Define provider order for display
    const providerOrder = [
        'openai', 'anthropic', 'gemini', 'deepseek', 
        'groq', 'huggingface', 'ollama', 'openai_compat', 'custom'
    ]
    
    // Initialize empty groups in order
    providerOrder.forEach(provider => {
        grouped[provider] = {
            id: provider,
            name: PROVIDERS_NAME[provider] || provider,
            icon: PROVIDER_ICONS[provider] || PROVIDER_ICONS.custom,
            iconDark: PROVIDER_ICONS_DARK[provider],
            models: [],
            isConfigured: false
        }
    })
    
    // Populate groups with models
    models.forEach(model => {
        const provider = model.api_type
        if (grouped[provider]) {
            grouped[provider].models.push(model)
            // Mark as configured if any model is configured
            if (model.is_configured) {
                grouped[provider].isConfigured = true
            }
        }
    })
    
    // Remove empty providers
    Object.keys(grouped).forEach(key => {
        if (grouped[key].models.length === 0) {
            delete grouped[key]
        }
    })
    
    return grouped
}

/**
 * Filter models based on search query
 */
export function filterModels(models: IModel[], query: string): IModel[] {
    if (!query.trim()) return models
    
    const lowerQuery = query.toLowerCase().trim()
    
    return models.filter(model => {
        const modelName = model.model.toLowerCase()
        const displayName = (model.display_name || '').toLowerCase()
        const provider = model.api_type.toLowerCase()
        const providerName = (PROVIDERS_NAME[model.api_type] || '').toLowerCase()
        
        return (
            modelName.includes(lowerQuery) ||
            displayName.includes(lowerQuery) ||
            provider.includes(lowerQuery) ||
            providerName.includes(lowerQuery)
        )
    })
}

/**
 * Get display name for a model
 */
export function getModelDisplayName(model: IModel): string {
    return model.display_name || model.model
}

/**
 * Get provider display name
 */
export function getProviderDisplayName(provider: string): string {
    return PROVIDERS_NAME[provider] || provider.charAt(0).toUpperCase() + provider.slice(1)
}

/**
 * Get icon for a provider with dark mode support
 */
export function getProviderIconPath(provider: string, isDarkMode: boolean = false): string {
    return getProviderIcon(provider, isDarkMode)
}

/**
 * Check if a model matches search criteria
 */
export function modelMatchesSearch(model: IModel, query: string): boolean {
    if (!query.trim()) return true
    
    const lowerQuery = query.toLowerCase().trim()
    const modelName = model.model.toLowerCase()
    const displayName = (model.display_name || '').toLowerCase()
    
    return modelName.includes(lowerQuery) || displayName.includes(lowerQuery)
}

/**
 * Get the currently selected model from a list
 */
export function getSelectedModelFromList(models: IModel[], selectedId?: string): IModel | undefined {
    if (!selectedId) return undefined
    return models.find(m => m.id === selectedId)
}

/**
 * Sort models by configured status and display name
 */
export function sortModels(models: IModel[]): IModel[] {
    return [...models].sort((a, b) => {
        // Configured models first
        if (a.is_configured && !b.is_configured) return -1
        if (!a.is_configured && b.is_configured) return 1
        
        // Active model first
        if (a.is_active && !b.is_active) return -1
        if (!a.is_active && b.is_active) return 1
        
        // Then alphabetically by display name
        const nameA = a.display_name || a.model
        const nameB = b.display_name || b.model
        return nameA.localeCompare(nameB)
    })
}

/**
 * Format context length for display
 */
export function formatContextLength(contextLength?: number): string {
    if (!contextLength) return ''
    
    if (contextLength >= 1000000) {
        return `${(contextLength / 1000000).toFixed(1)}M tokens`
    }
    if (contextLength >= 1000) {
        return `${(contextLength / 1000).toFixed(0)}K tokens`
    }
    return `${contextLength} tokens`
}
