import { IModel, APIType } from '@/typings/settings'

/**
 * Provider information for display in the model selector
 */
export interface ProviderInfo {
    id: string
    name: string
    icon: string
    iconDark?: string
    models: IModel[]
    isConfigured: boolean
}

/**
 * Grouped models by provider for display
 */
export interface GroupedModels {
    [provider: string]: ProviderInfo
}

/**
 * Selected model state
 */
export interface SelectedModel {
    id: string
    model: string
    provider: APIType
    displayName: string
}

/**
 * Model selector props
 */
export interface ModelSelectorProps {
    className?: string
    onSelect?: (model: IModel) => void
    disabled?: boolean
}

/**
 * Provider item props
 */
export interface ProviderItemProps {
    provider: ProviderInfo
    isExpanded: boolean
    onToggle: () => void
    selectedModelId?: string
    onSelectModel: (model: IModel) => void
    searchQuery: string
}

/**
 * Model item props
 */
export interface ModelItemProps {
    model: IModel
    isSelected: boolean
    onSelect: (model: IModel) => void
    providerIcon: string
}
