/**
 * WorkspaceService - Handles file operations for the LaTeX Editor in sandbox mode.
 * 
 * In sandbox mode, reads files from /workspace/documents/ directory.
 * In standalone mode (no API configured), falls back to localStorage.
 */

export interface WorkspaceFile {
  name: string;
  path: string;
  content: string;
  type: 'tex' | 'bib' | 'image' | 'other';
  isDirectory: boolean;
}

export interface WorkspaceConfig {
  workspacePath: string;
  apiBaseUrl: string;
  isEnabled: boolean;
}

// Configuration from environment
const config: WorkspaceConfig = {
  workspacePath: import.meta.env.VITE_WORKSPACE_PATH || '/workspace/documents',
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL || '',
  isEnabled: !!import.meta.env.VITE_API_BASE_URL,
};

/**
 * Get file type from filename extension
 */
function getFileType(filename: string): 'tex' | 'bib' | 'image' | 'other' {
  const ext = filename.split('.').pop()?.toLowerCase();
  if (ext === 'tex') return 'tex';
  if (ext === 'bib') return 'bib';
  if (['png', 'jpg', 'jpeg', 'gif', 'pdf', 'svg'].includes(ext || '')) return 'image';
  return 'other';
}

export class WorkspaceService {
  private static instance: WorkspaceService;
  private config: WorkspaceConfig;

  private constructor() {
    this.config = config;
  }

  static getInstance(): WorkspaceService {
    if (!WorkspaceService.instance) {
      WorkspaceService.instance = new WorkspaceService();
    }
    return WorkspaceService.instance;
  }

  /**
   * Check if workspace mode is enabled (sandbox mode)
   */
  isWorkspaceMode(): boolean {
    return this.config.isEnabled;
  }

  /**
   * Get the workspace path
   */
  getWorkspacePath(): string {
    return this.config.workspacePath;
  }

  /**
   * List all documents in the workspace
   */
  async listDocuments(): Promise<string[]> {
    if (!this.config.isEnabled) {
      return []; // Standalone mode - use localStorage
    }

    try {
      const response = await fetch(`${this.config.apiBaseUrl}/documents`);
      if (!response.ok) {
        throw new Error(`Failed to list documents: ${response.statusText}`);
      }
      const data = await response.json();
      // Backend returns [{name, path, file_count}], extract just the names
      const docs = data.documents || [];
      return docs.map((doc: { name: string }) => doc.name);
    } catch (error) {
      console.error('Failed to list documents:', error);
      return [];
    }
  }

  /**
   * List files in a document directory
   */
  async listFiles(documentName: string): Promise<WorkspaceFile[]> {
    if (!this.config.isEnabled) {
      return [];
    }

    try {
      const response = await fetch(
        `${this.config.apiBaseUrl}/documents/${documentName}/files`
      );
      if (!response.ok) {
        throw new Error(`Failed to list files: ${response.statusText}`);
      }
      const data = await response.json();
      return (data.files || []).map((file: any) => ({
        name: file.name,
        path: file.path,
        content: '',
        type: getFileType(file.name),
        isDirectory: file.isDirectory || false,
      }));
    } catch (error) {
      console.error('Failed to list files:', error);
      return [];
    }
  }

  /**
   * Read a file from the workspace
   */
  async readFile(documentName: string, fileName: string): Promise<string> {
    if (!this.config.isEnabled) {
      return '';
    }

    try {
      const response = await fetch(
        `${this.config.apiBaseUrl}/documents/${documentName}/files/${fileName}`
      );
      if (!response.ok) {
        throw new Error(`Failed to read file: ${response.statusText}`);
      }
      return await response.text();
    } catch (error) {
      console.error('Failed to read file:', error);
      return '';
    }
  }

  /**
   * Write a file to the workspace
   */
  async writeFile(
    documentName: string,
    fileName: string,
    content: string
  ): Promise<boolean> {
    if (!this.config.isEnabled) {
      return false;
    }

    try {
      const response = await fetch(
        `${this.config.apiBaseUrl}/documents/${documentName}/files/${fileName}`,
        {
          method: 'PUT',
          headers: { 'Content-Type': 'text/plain' },
          body: content,
        }
      );
      return response.ok;
    } catch (error) {
      console.error('Failed to write file:', error);
      return false;
    }
  }

  /**
   * Compile a document locally using pdflatex
   */
  async compileDocument(
    documentName: string,
    mainFile?: string
  ): Promise<{ success: boolean; pdf?: string; log?: string; errors?: any[] }> {
    if (!this.config.isEnabled) {
      return { success: false, log: 'Workspace mode not enabled' };
    }

    try {
      const response = await fetch(
        `${this.config.apiBaseUrl}/documents/${documentName}/compile`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ main_file: mainFile }),
        }
      );

      const data = await response.json();
      return {
        success: data.success,
        pdf: data.pdf_path,
        log: data.log,
        errors: data.errors,
      };
    } catch (error) {
      console.error('Failed to compile document:', error);
      return {
        success: false,
        log: error instanceof Error ? error.message : 'Compilation failed',
      };
    }
  }
}

export const workspaceService = WorkspaceService.getInstance();
