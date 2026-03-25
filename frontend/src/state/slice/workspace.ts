import { createSlice, PayloadAction } from '@reduxjs/toolkit'

interface WorkspaceState {
    workspaceInfo: string
    browserUrl: string
    vscodeUrl: string
    currentQuestion: string
    // Additional sandbox service URLs
    excalidrawUrl: string
    latexUrl: string
    graphitiUrl: string
    designUrl: string
    codexUrl: string
    mcpUrl: string
}

const initialState: WorkspaceState = {
    workspaceInfo: '',
    browserUrl: '',
    vscodeUrl: '',
    currentQuestion: '',
    // Initialize new URLs as empty
    excalidrawUrl: '',
    latexUrl: '',
    graphitiUrl: '',
    designUrl: '',
    codexUrl: '',
    mcpUrl: ''
}

const workspaceSlice = createSlice({
    name: 'workspace',
    initialState,
    reducers: {
        setWorkspaceInfo: (state, action: PayloadAction<string>) => {
            state.workspaceInfo = action.payload
        },
        setBrowserUrl: (state, action: PayloadAction<string>) => {
            state.browserUrl = action.payload
        },
        setVscodeUrl: (state, action: PayloadAction<string>) => {
            state.vscodeUrl = action.payload
        },
        setCurrentQuestion: (state, action: PayloadAction<string>) => {
            state.currentQuestion = action.payload
        },
        // Reducers for new sandbox service URLs
        setExcalidrawUrl: (state, action: PayloadAction<string>) => {
            state.excalidrawUrl = action.payload
        },
        setLatexUrl: (state, action: PayloadAction<string>) => {
            state.latexUrl = action.payload
        },
        setGraphitiUrl: (state, action: PayloadAction<string>) => {
            state.graphitiUrl = action.payload
        },
        setDesignUrl: (state, action: PayloadAction<string>) => {
            state.designUrl = action.payload
        },
        setCodexUrl: (state, action: PayloadAction<string>) => {
            state.codexUrl = action.payload
        },
        setMcpUrl: (state, action: PayloadAction<string>) => {
            state.mcpUrl = action.payload
        }
    }
})

export const {
    setWorkspaceInfo,
    setBrowserUrl,
    setVscodeUrl,
    setCurrentQuestion,
    setExcalidrawUrl,
    setLatexUrl,
    setGraphitiUrl,
    setDesignUrl,
    setCodexUrl,
    setMcpUrl
} = workspaceSlice.actions
export const workspaceReducer = workspaceSlice.reducer

// Selectors
export const selectWorkspaceInfo = (state: { workspace: WorkspaceState }) => state.workspace.workspaceInfo
export const selectBrowserUrl = (state: { workspace: WorkspaceState }) => state.workspace.browserUrl
export const selectVscodeUrl = (state: { workspace: WorkspaceState }) => state.workspace.vscodeUrl
export const selectCurrentQuestion = (state: { workspace: WorkspaceState }) => state.workspace.currentQuestion
export const selectExcalidrawUrl = (state: { workspace: WorkspaceState }) => state.workspace.excalidrawUrl
export const selectLatexUrl = (state: { workspace: WorkspaceState }) => state.workspace.latexUrl
export const selectGraphitiUrl = (state: { workspace: WorkspaceState }) => state.workspace.graphitiUrl
export const selectDesignUrl = (state: { workspace: WorkspaceState }) => state.workspace.designUrl
export const selectCodexUrl = (state: { workspace: WorkspaceState }) => state.workspace.codexUrl
export const selectMcpUrl = (state: { workspace: WorkspaceState }) => state.workspace.mcpUrl