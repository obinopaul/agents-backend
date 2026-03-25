import { Icon } from '@/components/ui/icon'
import {
    Sheet,
    SheetClose,
    SheetContent,
    SheetHeader
} from '@/components/ui/sheet'
import ToolSetting from './tool-setting'
import { selectQuestionMode, useAppSelector } from '@/state'
import { QUESTION_MODE } from '@/typings'

interface AgentSettingProps {
    isOpen: boolean
    onOpenChange: (open: boolean) => void
}

const AgentSetting = ({ isOpen, onOpenChange }: AgentSettingProps) => {
    const questionMode = useAppSelector(selectQuestionMode)

    return (
        <Sheet open={isOpen} onOpenChange={onOpenChange}>
            <SheetContent className="pt-0 md:pt-12 w-full !max-w-[560px]">
                <SheetHeader className="px-3 md:px-6 gap-6 pb-4">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-x-3">
                            <SheetClose className="md:hidden cursor-pointer">
                                <Icon
                                    name="close"
                                    className="fill-grey-2 dark:fill-grey"
                                />
                            </SheetClose>
                            <p className="text-2xl font-semibold">
                                {questionMode === QUESTION_MODE.AGENT
                                    ? 'Tool Settings'
                                    : 'Chat Settings'}
                            </p>
                        </div>
                        <div className="hidden md:flex items-center gap-x-4">
                            <SheetClose className="cursor-pointer">
                                <Icon
                                    name="close"
                                    className="fill-grey-2 dark:fill-grey"
                                />
                            </SheetClose>
                        </div>
                    </div>
                </SheetHeader>
                <div className="space-y-4 flex-1 overflow-auto px-3 md:px-6 md:pb-12">
                    <ToolSetting />
                </div>
            </SheetContent>
        </Sheet>
    )
}

export default AgentSetting
