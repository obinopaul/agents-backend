/**
 * Settings Service
 *
 * API client for MCP settings endpoints
 */

import axios from "axios";

const api = axios.create({
  baseURL: "http://localhost:8000/api/v1/agent",
  headers: { "Content-Type": "application/json" },
});

// Add auth interceptor
api.interceptors.request.use((config) => {
  const token = localStorage.getItem("access_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Types
export interface MCPSetting {
  id: number;
  user_id: number;
  tool_type: string;
  mcp_config: Record<string, any>;
  metadata_json?: Record<string, any>;
  is_active: boolean;
  store_path?: string;
  created_time: string;
  updated_time?: string;
}

export interface CodexConfigRequest {
  auth_json?: Record<string, any>;
  apikey?: string;
  model?: string;
  model_reasoning_effort?: "low" | "medium" | "high";
  search?: boolean;
}

export interface ClaudeCodeConfigRequest {
  authorization_code: string; // Format: code#verifier
}

export interface CustomMCPConfigRequest {
  name: string;
  command: string;
  args: string[];
  transport?: "stdio" | "sse";
  env?: Record<string, string>;
}

// Service
export const settingsService = {
  /**
   * Get all MCP settings for current user
   */
  async getMcpSettings(onlyActive = false): Promise<MCPSetting[]> {
    const params = onlyActive ? { only_active: true } : {};
    const { data } = await api.get("/user-settings/mcp", { params });
    return data.settings;
  },

  /**
   * Get Codex settings
   */
  async getCodexSettings(): Promise<MCPSetting | null> {
    const { data } = await api.get("/user-settings/mcp/codex");
    return data;
  },

  /**
   * Configure Codex
   */
  async configureCodex(payload: CodexConfigRequest): Promise<MCPSetting> {
    const { data } = await api.post("/user-settings/mcp/codex", payload);
    return data;
  },

  /**
   * Get Claude Code settings
   */
  async getClaudeCodeSettings(): Promise<MCPSetting | null> {
    const { data } = await api.get("/user-settings/mcp/claude-code");
    return data;
  },

  /**
   * Configure Claude Code with OAuth
   *
   * @param payload.authorization_code - Format: "code#verifier"
   */
  async configureClaudeCode(
    payload: ClaudeCodeConfigRequest
  ): Promise<MCPSetting> {
    const { data } = await api.post("/user-settings/mcp/claude-code", payload);
    return data;
  },

  /**
   * Configure custom MCP server
   */
  async configureCustomMcp(
    payload: CustomMCPConfigRequest
  ): Promise<MCPSetting> {
    const { data } = await api.post("/user-settings/mcp/custom", payload);
    return data;
  },

  /**
   * Delete MCP setting
   */
  async deleteMcpSetting(toolType: string): Promise<void> {
    await api.delete(`/user-settings/mcp/${toolType}`);
  },

  /**
   * Toggle MCP setting active status
   */
  async toggleMcpSetting(
    toolType: string,
    isActive: boolean
  ): Promise<MCPSetting> {
    const { data } = await api.patch(
      `/user-settings/mcp/${toolType}/toggle`,
      null,
      { params: { is_active: isActive } }
    );
    return data;
  },
};

export default settingsService;
