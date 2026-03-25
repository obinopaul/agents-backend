interface ImportMetaEnv {
  VITE_LATEX_API_URL: string;
  VITE_WORKSPACE_PATH: string;  // Path to documents in sandbox (e.g., /workspace/documents)
  VITE_API_BASE_URL: string;    // Base URL for file operations API
}

interface ImportMeta {
  env: ImportMetaEnv;
}