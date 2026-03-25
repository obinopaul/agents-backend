import { useState } from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'
import { cn } from '@/lib/utils'
import { IModel } from '@/typings/settings'
import { ProviderInfo } from './types'
import { modelMatchesSearch, sortModels } from './utils'
import { ModelItem } from './model-item'

interface ProviderGroupProps {
    provider: ProviderInfo
    selectedModelId?: string
    onSelectModel: (model: IModel) => void
    searchQuery: string
    defaultExpanded?: boolean
    isDarkMode?: boolean
}

export function ProviderGroup({ 
    provider, 
    selectedModelId, 
    onSelectModel, 
    searchQuery,
    defaultExpanded = false,
    isDarkMode = false
}: ProviderGroupProps) {
    const [isExpanded, setIsExpanded] = useState(defaultExpanded)
    
    // Filter and sort models
    const filteredModels = sortModels(
        provider.models.filter(model => modelMatchesSearch(model, searchQuery))
    )
    
    // Don't render if no models match the search
    if (filteredModels.length === 0) {
        return null
    }
    
    // Check if any model in this provider is selected
    const hasSelectedModel = filteredModels.some(m => m.id === selectedModelId)
    
    // Auto-expand if search matches or has selected model
    const shouldExpand = isExpanded || (searchQuery && filteredModels.length > 0) || hasSelectedModel
    
    const providerIcon = isDarkMode && provider.iconDark ? provider.iconDark : provider.icon
    
    return (
        <div className="mb-1">
            {/* Provider Header */}
            <button
                onClick={() => setIsExpanded(!isExpanded)}
                className={cn(
                    'w-full flex items-center gap-2 px-2 py-1.5 rounded-md transition-all duration-150',
                    'hover:bg-gray-100 dark:hover:bg-gray-800',
                    shouldExpand && 'bg-gray-50 dark:bg-gray-800/50'
                )}
            >
                {/* Expand/Collapse Icon */}
                <div className="flex-shrink-0 w-3 h-3 flex items-center justify-center">
                    {shouldExpand ? (
                        <ChevronDown className="w-3 h-3 text-gray-500" />
                    ) : (
                        <ChevronRight className="w-3 h-3 text-gray-500" />
                    )}
                </div>
                
                {/* Provider Icon */}
                <div className="flex-shrink-0 w-5 h-5 rounded-full overflow-hidden bg-white dark:bg-gray-700 flex items-center justify-center shadow-sm">
                    <img 
                        src={providerIcon} 
                        alt={provider.name}
                        className="w-4 h-4 object-contain"
                        onError={(e) => {
                            (e.target as HTMLImageElement).style.display = 'none'
                        }}
                    />
                </div>
                
                {/* Provider Name */}
                <span className="flex-1 text-left font-medium text-xs text-gray-900 dark:text-white">
                    {provider.name}
                </span>
                
                {/* Model Count */}
                <span className="flex-shrink-0 text-[10px] text-gray-500 dark:text-gray-400 bg-gray-100 dark:bg-gray-700 px-1.5 py-0.5 rounded-full">
                    {filteredModels.length}
                </span>
                
                {/* Configured indicator */}
                {provider.isConfigured && (
                    <span className="flex-shrink-0 w-1.5 h-1.5 rounded-full bg-green-500" title="Configured" />
                )}
            </button>
            
            {/* Models List */}
            {shouldExpand && (
                <div className="ml-5 mt-0.5 space-y-0 border-l border-gray-100 dark:border-gray-700 pl-2">
                    {filteredModels.map(model => (
                        <ModelItem
                            key={model.id}
                            model={model}
                            isSelected={model.id === selectedModelId}
                            onSelect={onSelectModel}
                            providerIcon={providerIcon}
                        />
                    ))}
                </div>
            )}
        </div>
    )
}

export default ProviderGroup
