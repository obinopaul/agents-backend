import { Check, Eye, Wrench, Sparkles } from 'lucide-react'
import { cn } from '@/lib/utils'
import { IModel } from '@/typings/settings'
import { getModelDisplayName, formatContextLength } from './utils'

interface ModelItemProps {
    model: IModel
    isSelected: boolean
    onSelect: (model: IModel) => void
    providerIcon: string
}

export function ModelItem({ model, isSelected, onSelect, providerIcon }: ModelItemProps) {
    const displayName = getModelDisplayName(model)
    const contextLength = formatContextLength(model.context_length)
    const isConfigured = model.is_configured !== false // Default to true if not specified
    
    return (
        <button
            onClick={() => onSelect(model)}
            disabled={!isConfigured}
            className={cn(
                'w-full flex items-center gap-2 px-2 py-1.5 rounded-md text-left transition-all duration-150',
                'hover:bg-sky-blue/10 dark:hover:bg-sky-blue-2/10',
                isSelected && 'bg-sky-blue/20 dark:bg-sky-blue-2/20 border border-sky-blue dark:border-sky-blue-2',
                !isConfigured && 'opacity-50 cursor-not-allowed'
            )}
        >
            {/* Provider Icon */}
            <div className="flex-shrink-0 w-4 h-4 rounded-full overflow-hidden bg-white dark:bg-gray-800 flex items-center justify-center">
                <img 
                    src={providerIcon} 
                    alt="" 
                    className="w-3.5 h-3.5 object-contain"
                    onError={(e) => {
                        (e.target as HTMLImageElement).style.display = 'none'
                    }}
                />
            </div>
            
            {/* Model Info */}
            <div className="flex-1 min-w-0">
                <div className="flex items-center gap-1.5">
                    <span className={cn(
                        'font-medium text-xs truncate',
                        'text-gray-900 dark:text-white'
                    )}>
                        {displayName}
                    </span>
                    
                    {/* Capability badges */}
                    <div className="flex items-center gap-0.5">
                        {model.supports_vision && (
                            <Eye className="w-2.5 h-2.5 text-blue-500" />
                        )}
                        {model.supports_function_calling && (
                            <Wrench className="w-2.5 h-2.5 text-green-500" />
                        )}
                        {model.is_active && (
                            <Sparkles className="w-2.5 h-2.5 text-yellow-500" />
                        )}
                    </div>
                </div>
                
                {/* Context length */}
                {contextLength && (
                    <span className="text-[10px] text-gray-500 dark:text-gray-400">
                        {contextLength}
                    </span>
                )}
            </div>
            
            {/* Selection indicator */}
            {isSelected && (
                <div className="flex-shrink-0">
                    <Check className="w-3 h-3 text-sky-blue dark:text-sky-blue-2" />
                </div>
            )}
            
            {/* Not configured indicator */}
            {!isConfigured && (
                <span className="flex-shrink-0 text-[10px] text-gray-400 dark:text-gray-500">
                    Coming soon
                </span>
            )}
        </button>
    )
}

export default ModelItem
