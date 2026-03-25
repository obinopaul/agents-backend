import { create } from "zustand";
import { persist } from "zustand/middleware";
import { AIProviderType } from "../types/ai";
import { CompilationResult } from "../services/latexCompiler";

export interface ProjectFile {
  name: string;
  content: string;
  type: "tex" | "bib" | "image" | "other";
}

// Workspace mode: No default template. Files are loaded from /workspace/documents/
// Agent initializes templates using document_template_init tool

interface EditorState {
  // Editor content
  latexCode: string;
  setLatexCode: (code: string) => void;

  // Workspace mode - current document folder from /workspace/documents/
  currentDocument: string; // Document folder name (e.g., "paul_cv")
  setCurrentDocument: (name: string) => void;

  // Multi-file project support
  projectFiles: ProjectFile[];
  addProjectFile: (file: ProjectFile) => void;
  updateProjectFile: (name: string, content: string) => void;
  removeProjectFile: (name: string) => void;
  setProjectFiles: (files: ProjectFile[]) => void; // Replace all files (for workspace sync)
  currentFile: string; // Currently active file name
  setCurrentFile: (name: string) => void;

  // Code suggestions
  suggestedCode: string | null;
  setSuggestedCode: (code: string | null) => void;
  suggestionPrompt: string | null;
  setSuggestionPrompt: (prompt: string | null) => void;

  // Compilation
  compilationResult: CompilationResult | null;
  setCompilationResult: (result: CompilationResult | null) => void;
  isCompiling: boolean;
  setIsCompiling: (compiling: boolean) => void;
  autoCompile: boolean;
  setAutoCompile: (auto: boolean) => void;
  compilationError: string | null;
  setCompilationError: (error: string | null) => void;
  compilationLogs: Array<{
    timestamp: number;
    type: "success" | "error";
    message: string;
  }>;
  addCompilationLog: (type: "success" | "error", message: string) => void;
  clearCompilationLogs: () => void;

  // AI Provider
  selectedProvider: AIProviderType | null;
  setSelectedProvider: (provider: AIProviderType | null) => void;

  // UI State
  showSettings: boolean;
  setShowSettings: (show: boolean) => void;
  aiPanelOpen: boolean;
  setAiPanelOpen: (open: boolean) => void;
  aiLoading: boolean;
  setAiLoading: (loading: boolean) => void;

  // Fullscreen modes
  editorFullscreen: boolean;
  setEditorFullscreen: (fullscreen: boolean) => void;
  previewFullscreen: boolean;
  setPreviewFullscreen: (fullscreen: boolean) => void;

  // Resizable panel
  editorWidth: number; // percentage (0-100)
  setEditorWidth: (width: number) => void;
  aiPanelWidth: number; // percentage (0-100)
  setAiPanelWidth: (width: number) => void;

  // Editor preferences
  fontSize: number;
  setFontSize: (size: number) => void;
  showMinimap: boolean;
  setShowMinimap: (show: boolean) => void;
  showLineNumbers: boolean;
  setShowLineNumbers: (show: boolean) => void;

  // AI Chat
  aiMessages: Array<{ role: "user" | "assistant"; content: string }>;
  addAiMessage: (role: "user" | "assistant", content: string) => void;
  clearAiMessages: () => void;
}

export const useEditorStore = create<EditorState>()(
  persist(
    (set) => ({
      // Editor content - empty by default in workspace mode
      latexCode: "",
      setLatexCode: (code) => set({ latexCode: code }),

      // Workspace mode - current document folder
      currentDocument: "",
      setCurrentDocument: (name) => set({ currentDocument: name }),

      // Multi-file project support - populated from workspace
      projectFiles: [],
      addProjectFile: (file) =>
        set((state) => ({
          projectFiles: [...state.projectFiles, file],
        })),
      updateProjectFile: (name, content) =>
        set((state) => ({
          projectFiles: state.projectFiles.map((f) =>
            f.name === name ? { ...f, content } : f
          ),
        })),
      removeProjectFile: (name) =>
        set((state) => ({
          projectFiles: state.projectFiles.filter((f) => f.name !== name),
        })),
      setProjectFiles: (files) => set({ projectFiles: files }),
      // Current file - empty until workspace files are loaded
      currentFile: "",
      setCurrentFile: (name) => set({ currentFile: name }),

      // Code suggestions
      suggestedCode: null,
      setSuggestedCode: (code) => set({ suggestedCode: code }),
      suggestionPrompt: null,
      setSuggestionPrompt: (prompt) => set({ suggestionPrompt: prompt }),

      // Compilation
      compilationResult: null,
      setCompilationResult: (result) => set({ compilationResult: result }),
      isCompiling: false,
      setIsCompiling: (compiling) => set({ isCompiling: compiling }),
      autoCompile: true,
      setAutoCompile: (auto) => set({ autoCompile: auto }),
      compilationError: null,
      setCompilationError: (error) => set({ compilationError: error }),
      compilationLogs: [],
      addCompilationLog: (type, message) =>
        set((state) => ({
          compilationLogs: [
            { timestamp: Date.now(), type, message },
            ...state.compilationLogs,
          ].slice(0, 50), // Keep last 50 logs
        })),
      clearCompilationLogs: () => set({ compilationLogs: [] }),

      // AI Provider
      selectedProvider: null,
      setSelectedProvider: (provider) => set({ selectedProvider: provider }),

      // UI State
      showSettings: false,
      setShowSettings: (show) => set({ showSettings: show }),
      aiPanelOpen: false,
      setAiPanelOpen: (open) => set({ aiPanelOpen: open }),
      aiLoading: false,
      setAiLoading: (loading) => set({ aiLoading: loading }),

      // Fullscreen modes
      editorFullscreen: false,
      setEditorFullscreen: (fullscreen) =>
        set({ editorFullscreen: fullscreen }),
      previewFullscreen: false,
      setPreviewFullscreen: (fullscreen) =>
        set({ previewFullscreen: fullscreen }),

      // Resizable panel
      editorWidth: 50, // Default 50%
      setEditorWidth: (width) => set({ editorWidth: width }),
      aiPanelWidth: 30, // Default 30%
      setAiPanelWidth: (width) => set({ aiPanelWidth: width }),

      // Editor preferences
      fontSize: 14,
      setFontSize: (size) => set({ fontSize: size }),
      showMinimap: true,
      setShowMinimap: (show) => set({ showMinimap: show }),
      showLineNumbers: true,
      setShowLineNumbers: (show) => set({ showLineNumbers: show }),

      // AI Chat
      aiMessages: [],
      addAiMessage: (role, content) =>
        set((state) => ({
          aiMessages: [...state.aiMessages, { role, content }],
        })),
      clearAiMessages: () => set({ aiMessages: [] }),
    }),
    {
      name: "latex-editor-storage", // localStorage key
      partialize: (state) => ({
        // Only persist these fields
        latexCode: state.latexCode,
        autoCompile: state.autoCompile,
        selectedProvider: state.selectedProvider,
        editorWidth: state.editorWidth,
        aiPanelWidth: state.aiPanelWidth,
        aiPanelOpen: state.aiPanelOpen,
        fontSize: state.fontSize,
        showMinimap: state.showMinimap,
        showLineNumbers: state.showLineNumbers,
        projectFiles: state.projectFiles,
        currentFile: state.currentFile,
      }),
    }
  )
);
