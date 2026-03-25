import { useMemo, useCallback, useEffect, useState } from 'react'
import { ChevronDown, Check, Sparkles, Search, X } from 'lucide-react'
import { cn } from '@/lib/utils'
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuTrigger,
    DropdownMenuSub,
    DropdownMenuSubTrigger,
    DropdownMenuSubContent,
    DropdownMenuItem,
    DropdownMenuSeparator,
} from '@/components/ui/dropdown-menu'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Button } from '@/components/ui/button'
import { IModel } from '@/typings/settings'
import { 
    selectAvailableModels, 
    selectSelectedModel, 
    setSelectedModel,
    useAppDispatch,
    useAppSelector 
} from '@/state'
import { getProviderIcon, PROVIDERS_NAME } from '@/constants/models'
import { groupModelsByProvider, getModelDisplayName, sortModels, filterModels } from './utils'

interface ModelSelectorDropdownProps {
    className?: string
    onModelChange?: (model: IModel) => void
    disabled?: boolean
    compact?: boolean
}

export function ModelSelectorDropdown({ 
    className,
    onModelChange,
    disabled = false,
    compact = false
}: ModelSelectorDropdownProps) {
    const dispatch = useAppDispatch()
    const availableModels = useAppSelector(selectAvailableModels)
    const selectedModelId = useAppSelector(selectSelectedModel)
    
    const [isOpen, setIsOpen] = useState(false)
    const [searchQuery, setSearchQuery] = useState('')
    
    // Check for dark mode
    const [isDarkMode, setIsDarkMode] = useState(false)
    
    useEffect(() => {
        const checkDarkMode = () => {
            setIsDarkMode(document.documentElement.classList.contains('dark'))
        }
        checkDarkMode()
        
        const observer = new MutationObserver(checkDarkMode)
        observer.observe(document.documentElement, { 
            attributes: true, 
            attributeFilter: ['class'] 
        })
        
        return () => observer.disconnect()
    }, [])
    
    // Group models by provider
    const groupedModels = useMemo(() => {
        return groupModelsByProvider(availableModels)
    }, [availableModels])
    
    // Filter models based on search query
    const filteredModels = useMemo(() => {
        if (!searchQuery.trim()) return []
        return filterModels(availableModels, searchQuery)
    }, [availableModels, searchQuery])
    
    // Get selected model info
    const selectedModel = useMemo(() => {
        return availableModels.find(m => m.id === selectedModelId)
    }, [availableModels, selectedModelId])
    
    // Handle model selection
    const handleSelectModel = useCallback((model: IModel) => {
        dispatch(setSelectedModel(model.id))
        onModelChange?.(model)
        setIsOpen(false)
        setSearchQuery('')
    }, [dispatch, onModelChange])
    
    // Clear search when dropdown closes
    useEffect(() => {
        if (!isOpen) {
            setSearchQuery('')
        }
    }, [isOpen])
    
    // Get display info for trigger button
    const triggerDisplayName = selectedModel 
        ? getModelDisplayName(selectedModel) 
        : 'Select Model'
    
    const triggerIcon = selectedModel 
        ? getProviderIcon(selectedModel.api_type, isDarkMode)
        : null
    
    // Provider order for display
    const providerOrder = ['openai', 'anthropic', 'gemini', 'deepseek', 'groq', 'huggingface', 'ollama', 'openai_compat']

    return (
        <DropdownMenu open={isOpen} onOpenChange={setIsOpen}>
            <DropdownMenuTrigger asChild disabled={disabled}>
                <Button
                    variant="secondary"
                    size={compact ? "sm" : "default"}
                    className={cn(
                        'gap-2 font-normal transition-all duration-200',
                        compact 
                            ? 'h-7 px-2 text-xs rounded-full'
                            : 'h-9 px-3 rounded-xl',
                        // Light mode: white bg, dark text
                        // Dark mode: sky-blue bg, black text
                        'bg-white hover:bg-grey/50',
                        'dark:bg-sky-blue dark:hover:bg-sky-blue/80',
                        'text-black dark:text-black',
                        'border border-grey dark:border-transparent',
                        isOpen && 'ring-2 ring-firefly/20 dark:ring-sky-blue-2/30',
                        className
                    )}
                >
                    {/* Provider Icon */}
                    {triggerIcon && (
                        <img 
                            src={triggerIcon}
                            alt=""
                            className={cn(
                                'object-contain',
                                compact ? 'w-4 h-4' : 'w-5 h-5'
                            )}
                            onError={(e) => {
                                (e.target as HTMLImageElement).style.display = 'none'
                            }}
                        />
                    )}
                    
                    {/* Model Name */}
                    <span className="truncate max-w-[120px]">
                        {triggerDisplayName}
                    </span>
                    
                    {/* Dropdown Arrow */}
                    <ChevronDown className={cn(
                        'flex-shrink-0 transition-transform duration-200',
                        compact ? 'w-3 h-3' : 'w-4 h-4',
                        isOpen && 'rotate-180'
                    )} />
                </Button>
            </DropdownMenuTrigger>
            
            <DropdownMenuContent 
                className={cn(
                    'min-w-[220px] p-1',
                    // Light mode: white bg
                    // Dark mode: charcoal bg with light text
                    'bg-white dark:bg-charcoal',
                    'border border-grey dark:border-slate/30',
                    'shadow-lg'
                )}
                align="start"
                sideOffset={8}
                onCloseAutoFocus={(e) => e.preventDefault()}
            >
                {/* Search Bar */}
                <div className="px-1 pb-1">
                    <div className="relative">
                        <Search className="absolute left-2 top-1/2 -translate-y-1/2 w-3 h-3 text-slate dark:text-pewter" />
                        <input
                            type="text"
                            placeholder="Search models..."
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            className={cn(
                                'w-full pl-7 pr-6 py-1.5 text-xs rounded-md',
                                'bg-grey/30 dark:bg-slate/20',
                                'border border-grey/50 dark:border-slate/30',
                                'text-black dark:text-white',
                                'placeholder:text-slate dark:placeholder:text-pewter',
                                'focus:outline-none focus:ring-1 focus:ring-firefly/30 dark:focus:ring-sky-blue-2/30',
                                'transition-all duration-150'
                            )}
                            onClick={(e) => e.stopPropagation()}
                            onKeyDown={(e) => e.stopPropagation()}
                        />
                        {searchQuery && (
                            <button
                                onClick={(e) => {
                                    e.stopPropagation()
                                    setSearchQuery('')
                                }}
                                className="absolute right-1.5 top-1/2 -translate-y-1/2 p-0.5 rounded hover:bg-grey/50 dark:hover:bg-slate/30"
                            >
                                <X className="w-2.5 h-2.5 text-slate dark:text-pewter" />
                            </button>
                        )}
                    </div>
                </div>
                
                <DropdownMenuSeparator className="bg-grey dark:bg-slate/30" />
                
                {/* Current Selection Header */}
                {selectedModel && (
                    <>
                        <div className="flex items-center gap-2 px-2 py-1.5 mb-1">
                            <Sparkles className="w-3 h-3 text-firefly dark:text-sky-blue-2" />
                            <span className="text-[10px] text-slate dark:text-pewter">
                                Current: <span className="font-medium text-black dark:text-white">{triggerDisplayName}</span>
                            </span>
                        </div>
                        <DropdownMenuSeparator className="bg-grey dark:bg-slate/30" />
                    </>
                )}
                
                {/* Search Results (when searching) */}
                {searchQuery.trim() ? (
                    <ScrollArea className="max-h-[300px]">
                        {filteredModels.length > 0 ? (
                            <div className="p-1">
                                {filteredModels.map(model => {
                                    const isSelected = model.id === selectedModelId
                                    const displayName = getModelDisplayName(model)
                                    const providerName = PROVIDERS_NAME[model.api_type] || model.api_type
                                    const providerIcon = getProviderIcon(model.api_type, isDarkMode)
                                    
                                    return (
                                        <DropdownMenuItem
                                            key={model.id}
                                            onClick={() => handleSelectModel(model)}
                                            className={cn(
                                                'flex items-center gap-2 px-2 py-1.5 rounded-md cursor-pointer text-xs',
                                                'text-black dark:text-white',
                                                'hover:bg-grey/50 dark:hover:bg-slate/30',
                                                'focus:bg-grey/50 dark:focus:bg-slate/30',
                                                isSelected && 'bg-firefly/10 dark:bg-sky-blue-2/10'
                                            )}
                                        >
                                            {/* Provider Icon */}
                                            <div className="flex-shrink-0 w-4 h-4 rounded-full overflow-hidden bg-grey/50 dark:bg-slate/30 flex items-center justify-center">
                                                <img 
                                                    src={providerIcon} 
                                                    alt={providerName}
                                                    className="w-3 h-3 object-contain"
                                                    onError={(e) => {
                                                        (e.target as HTMLImageElement).style.display = 'none'
                                                    }}
                                                />
                                            </div>
                                            
                                            {/* Model Info */}
                                            <div className="flex-1 min-w-0">
                                                <span className={cn(
                                                    'block truncate',
                                                    isSelected && 'font-medium'
                                                )}>
                                                    {displayName}
                                                </span>
                                                <span className="block text-[9px] text-slate dark:text-pewter truncate">
                                                    {providerName}
                                                </span>
                                            </div>
                                            
                                            {/* Checkmark for selected */}
                                            {isSelected && (
                                                <Check className="w-3 h-3 text-firefly dark:text-sky-blue-2 flex-shrink-0" />
                                            )}
                                        </DropdownMenuItem>
                                    )
                                })}
                            </div>
                        ) : (
                            <div className="py-6 text-center">
                                <p className="text-xs text-slate dark:text-pewter">
                                    No models found for &ldquo;{searchQuery}&rdquo;
                                </p>
                                <button 
                                    onClick={(e) => {
                                        e.stopPropagation()
                                        setSearchQuery('')
                                    }}
                                    className="mt-1 text-[10px] text-firefly dark:text-sky-blue-2 hover:underline"
                                >
                                    Clear search
                                </button>
                            </div>
                        )}
                    </ScrollArea>
                ) : (
                    /* Provider List with Hover Submenus (when not searching) */
                    <>
                        {providerOrder.map(providerId => {
                    const provider = groupedModels[providerId]
                    if (!provider) return null
                    
                    const providerIcon = isDarkMode && provider.iconDark ? provider.iconDark : provider.icon
                    const models = sortModels(provider.models)
                    const hasSelectedModel = models.some(m => m.id === selectedModelId)
                    
                    return (
                        <DropdownMenuSub key={providerId}>
                            <DropdownMenuSubTrigger 
                                className={cn(
                                    'flex items-center gap-2 px-2 py-1.5 rounded-md cursor-pointer text-xs',
                                    // Light: dark text, hover shows light gray
                                    // Dark: white text, hover shows slate
                                    'text-black dark:text-white',
                                    'hover:bg-grey/50 dark:hover:bg-slate/30',
                                    'focus:bg-grey/50 dark:focus:bg-slate/30',
                                    'data-[state=open]:bg-grey/50 dark:data-[state=open]:bg-slate/30',
                                    hasSelectedModel && 'font-medium'
                                )}
                            >
                                {/* Provider Icon */}
                                <div className="flex-shrink-0 w-5 h-5 rounded-full overflow-hidden bg-grey/50 dark:bg-slate/30 flex items-center justify-center">
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
                                <span className="flex-1">{provider.name}</span>
                                
                                {/* Model Count Badge */}
                                <span className="text-[10px] text-slate dark:text-pewter bg-grey/70 dark:bg-slate/30 px-1.5 py-0.5 rounded-full">
                                    {models.length}
                                </span>
                                
                                {/* Selected indicator */}
                                {hasSelectedModel && (
                                    <span className="w-1.5 h-1.5 rounded-full bg-firefly dark:bg-sky-blue-2 flex-shrink-0" />
                                )}
                            </DropdownMenuSubTrigger>
                            
                            <DropdownMenuSubContent 
                                className={cn(
                                    'min-w-[220px] max-h-[300px] p-1',
                                    'bg-white dark:bg-charcoal',
                                    'border border-grey dark:border-slate/30',
                                    'shadow-lg overflow-hidden'
                                )}
                                sideOffset={4}
                            >
                                <ScrollArea className="max-h-[280px]">
                                    {models.map(model => {
                                        const isSelected = model.id === selectedModelId
                                        const displayName = getModelDisplayName(model)
                                        
                                        return (
                                            <DropdownMenuItem
                                                key={model.id}
                                                onClick={() => handleSelectModel(model)}
                                                className={cn(
                                                    'flex items-center gap-2 px-2 py-1.5 rounded-md cursor-pointer text-xs',
                                                    'text-black dark:text-white',
                                                    'hover:bg-grey/50 dark:hover:bg-slate/30',
                                                    'focus:bg-grey/50 dark:focus:bg-slate/30',
                                                    isSelected && 'bg-firefly/10 dark:bg-sky-blue-2/10'
                                                )}
                                            >
                                                {/* Checkmark for selected */}
                                                <div className="w-4 h-4 flex items-center justify-center flex-shrink-0">
                                                    {isSelected && (
                                                        <Check className="w-3 h-3 text-firefly dark:text-sky-blue-2" />
                                                    )}
                                                </div>
                                                
                                                {/* Model Name */}
                                                <span className={cn(
                                                    'flex-1 truncate',
                                                    isSelected && 'font-medium'
                                                )}>
                                                    {displayName}
                                                </span>
                                                
                                                {/* Vision indicator */}
                                                {model.supports_vision && (
                                                    <span className="text-[9px] text-slate dark:text-pewter bg-grey/70 dark:bg-slate/30 px-1 py-0.5 rounded">
                                                        Vision
                                                    </span>
                                                )}
                                            </DropdownMenuItem>
                                        )
                                    })}
                                </ScrollArea>
                            </DropdownMenuSubContent>
                        </DropdownMenuSub>
                    )
                })}
                </>
                )}
                
                {/* Footer */}
                <DropdownMenuSeparator className="bg-grey dark:bg-slate/30" />
                <div className="px-2 py-1">
                    <p className="text-[9px] text-slate dark:text-pewter text-center">
                        {availableModels.length} models • {Object.keys(groupedModels).length} providers
                    </p>
                </div>
            </DropdownMenuContent>
        </DropdownMenu>
    )
}

export default ModelSelectorDropdown
