# Agent Skills System Guide

The Agent Skills System allows you to inject specialized capabilities into the agent's sandbox environment. These skills are directory-based packages containing instructions (`SKILL.md`) and resource files that the agent can read and utilize at runtime.

## Overview

Unlike standard tools (which are Python functions exposed via MCP), **Skills** are knowledge bundles injected into the sandbox filesystem. They provide the agent with:
1. **Procedural Knowledge**: Step-by-step guides in `SKILL.md`.
2. **Context**: Reference files, templates, or code snippets.
3. **Discoverability**: Skills are automatically listed in the system prompt.

### Workflow

1. **Definition**: You create a skill folder with a `SKILL.md` file.
2. **Injection**: At sandbox creation time, skills are injected into `/workspace/.deepagents/skills/`.
3. **Loading**: When the agent starts, the backend reads these skills and injects distinct descriptions into the system prompt.
4. **Usage**: The agent sees available skills and reads the relevant `SKILL.md` when needed.

---

## Defining a New Skill

Skills are located in `backend/src/skills/`. Each skill is a directory.

### Directory Structure

Skills are organized by **Category**. You must place your skill folder inside one of the category directories.

```text
backend/src/skills/
├── <category>/                # e.g., "basic", "scientific_skills"
│   └── web-research/          # Skill Name
│       ├── SKILL.md           # Required: Main instruction file
│       ├── search_tips.txt    # Optional: Helper file
│       └── templates/         # Optional: Subdirectories
```

**Existing Categories:**
- `basic`: General purpose skills
- `scientific_skills`: Research and analysis skills
- `academic`: Writing and editing skills

### SKILL.md Format

The `SKILL.md` file MUST contain YAML frontmatter with `name` and `description`.

```markdown
---
name: web-research
description: Conduct simplified web research and summarization
---

# Web Research Skill

## Goal
Perform efficient web searches to answer user questions.

## Steps
1. unexpected results? Try refining queries.
2. Summarize findings in bullet points.
...
```

---

## System Architecture

### 1. Build Time (Docker)
The `e2b.Dockerfile` copies the entire `backend/src/skills` directory to `/app/skills` inside the sandbox template image.
Structure in Sandbox Image: `/app/skills/<category>/<skill>/`

### 2. Runtime Injection (Sandbox Creation)
When a sandbox is created via `SandboxService`, the `inject-skills.sh` script runs.
- It accepts an `agent_category` argument (e.g., `scientific`).
- It looks up the corresponding folders in `backend/src/config/skill_config.py`.
- It copies **contents** of the selected category folders from `/app/skills/<category>/` to `/workspace/.deepagents/skills/`.

### 3. Agent Execution (Runtime)
In `agent.py`, immediately after the sandbox is ready:
1. The backend calls `list_skills_from_sandbox(sandbox)`.
2. It executes `ls` and `cat` commands inside the sandbox to read skill metadata.
3. It formats this metadata into a prompt section (e.g., `## Available Skills...`).
4. This section is injected into the agent's `workflow_input`.

---

## Configuration

### Skill Mapping (`skill_config.py`)

You can map agent categories to specific skills in `backend/src/config/skill_config.py`.

```python
AGENT_CATEGORY_SKILLS = {
    AgentCategory.GENERAL: ["basic_skills"],
    AgentCategory.SCIENTIFIC: ["scientific_skills"],
    # ...
}
```

### Injection Script (`inject-skills.sh`)
Locations:
- Source: `backend/docker/sandbox/inject-skills.sh`
- Sandbox: `/app/inject-skills.sh`

---

## Troubleshooting

### Agent doesn't see skills
1. **Check Logs**: Look for `skills_loaded` event in the agent stream logs.
2. **Verify Sandbox**: Open a shell in the sandbox and check `/workspace/.deepagents/skills/`.
   ```bash
   ls -R /workspace/.deepagents/skills/
   ```
3. **Check SKILL.md**: Ensure valid YAML frontmatter is present.

### Skill update not applied
- **Rebuild Template**: Skills are baked into the Docker image. If you modify a skill locally, you MUST rebuild the E2B template.
  ```bash
  e2b template build -c backend
  ```
