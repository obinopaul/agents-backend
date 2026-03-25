# Skills System API Contract

This document defines the technical specifications for the Agent Skills System, including file formats, data models, and API events.

## 1. File Format (`SKILL.md`)

Each skill MUST define a `SKILL.md` file in its root directory. This file serves as both the metadata source and the primary instruction content for the agent.

### Schema

The file MUST begin with a YAML frontmatter block enclosed by `---`.

```markdown
---
name: <string> [Required] machine-readable-identifier (e.g., "web-research")
description: <string> [Required] Short description for system prompt (max 100 chars recommended)
version: <string> [Optional] Semantic version (e.g., "1.0.0")
---

<markdown content>
```

### Example

```markdown
---
name: data-analysis
description: Analyze CSV structure and generate Python pandas code
version: 1.0.0
---

# Data Analysis Skill
...
```

---

## 2. Internal Data Models

### SkillMetadata

Represents the parsed metadata of a skill.

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Unique identifier from frontmatter |
| `description` | `str` | Short description from frontmatter |
| `path` | `str` | Absolute path to `SKILL.md` in sandbox (e.g., `/workspace/.deepagents/skills/foo/SKILL.md`) |
| `version` | `str?` | Optional version string |

---

## 3. Streaming API Events

When using the `/agent/agent/stream` endpoint, the system emits Server-Sent Events (SSE). The skills system adds a specific event to this stream.

### event: `status`

Emitted when skills are successfully loaded from the sandbox.

**Data Schema:**

```json
{
  "type": "skills_loaded",
  "message": "Loaded {count} skills",
  "skill_count": <integer>,
  "skill_names": ["<name1>", "<name2>", ...]
}
```

**Example:**

```sse
event: status
data: {"type": "skills_loaded", "message": "Loaded 2 skills", "skill_count": 2, "skill_names": ["web-research", "coding"]}
```

---

## 4. Sandbox Paths

| Component | Path | Description |
|-----------|------|-------------|
| **Injection Source** | `/app/skills/` | Location of baked-in skills (read-only) |
| **Injection Script** | `/app/inject-skills.sh` | Orchestrator script |
| **Runtime Skills** | `/workspace/.deepagents/skills/` | Location of active skills for the session |

## 5. Environment Variables

| Variable | Context | Description |
|----------|---------|-------------|
| `AGENT_CATEGORY` | Sandbox Creation | Determines which skills to inject (mapped in `skill_config.py`) |

