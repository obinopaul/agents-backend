# Excalidraw System - User Guide

> Complete guide for creating diagrams and sketches using the AI agent's Excalidraw tools.

---

## Overview

Excalidraw is a hand-drawn style whiteboard system that enables AI agents to create diagrams, flowcharts, wireframes, and sketches. The sketchy aesthetic makes it ideal for:

- **Brainstorming sessions**
- **Quick wireframes**
- **System architecture sketches**
- **Flowcharts and process diagrams**
- **Mind maps**

### Excalidraw vs Draw.io (Design Mode)

| Feature | Excalidraw | Draw.io |
|---------|------------|---------|
| **Style** | Hand-drawn/sketchy | Professional/structured |
| **Best for** | Brainstorming, wireframes | Complex flowcharts, UML |
| **Port** | 6003 | 6002 |
| **Real-time sync** | ✅ WebSocket | ❌ Page refresh |

---

## Quick Start

### 1. Initialize a Canvas

The agent first creates a canvas session:

```
Agent: I'll create a new Excalidraw canvas for you.

→ excalidraw_init(canvas_name="architecture")

Session ID: excalidraw-a1b2c3d4
Viewer URL: http://localhost:6003/
```

### 2. View the Canvas

The sandbox server exposes port 6003:

```
POST /sandboxes/expose-port
{
  "sandbox_id": "sandbox-123",
  "port": 6003
}

Response:
{
  "url": "https://sandbox-123-6003.e2b.dev"
}
```

Open this URL in your browser to see the canvas in real-time.

### 3. Create Elements

The agent creates shapes, text, and connectors:

```python
# Create a rectangle
excalidraw_create_element(
    type="rectangle",
    x=100, y=100,
    width=200, height=100,
    backgroundColor="#a5d8ff"
)

# Add text label
excalidraw_create_element(
    type="text",
    x=130, y=140,
    text="Web Server"
)
```

### 4. Real-time Updates

Any changes made by the agent appear instantly in the browser via WebSocket.

---

## Available Tools

The agent has access to **13 Excalidraw tools**:

### Session
| Tool | Description |
|------|-------------|
| `excalidraw_init` | Initialize a new canvas session |

### CRUD Operations
| Tool | Description |
|------|-------------|
| `excalidraw_create_element` | Create a new element |
| `excalidraw_update_element` | Modify an existing element |
| `excalidraw_delete_element` | Remove an element |
| `excalidraw_query_elements` | List elements on the canvas |

### Batch Operations
| Tool | Description |
|------|-------------|
| `excalidraw_batch_create` | Create multiple elements at once |

### Organization
| Tool | Description |
|------|-------------|
| `excalidraw_group_elements` | Group elements together |
| `excalidraw_ungroup_elements` | Ungroup elements |
| `excalidraw_align_elements` | Align elements (left/center/right/top/middle/bottom) |
| `excalidraw_distribute_elements` | Distribute elements evenly |

### State Management
| Tool | Description |
|------|-------------|
| `excalidraw_lock_element` | Lock an element from editing |
| `excalidraw_unlock_element` | Unlock an element |

### Export
| Tool | Description |
|------|-------------|
| `excalidraw_get_resource` | Export canvas as JSON/SVG/PNG |

---

## Element Types

### Shapes

| Type | Description | Example |
|------|-------------|---------|
| `rectangle` | Rectangle/square | Boxes, containers |
| `ellipse` | Ellipse/circle | Nodes, icons |
| `diamond` | Diamond shape | Decision points |

### Connectors

| Type | Description | Example |
|------|-------------|---------|
| `line` | Straight line | Connections |
| `arrow` | Arrow with arrowhead | Data flow, direction |

### Text & Drawing

| Type | Description | Example |
|------|-------------|---------|
| `text` | Text label | Labels, titles |
| `freedraw` | Freehand drawing | Annotations |

---

## Styling Options

### Colors

```json
{
  "backgroundColor": "#a5d8ff",  // Fill color (hex)
  "strokeColor": "#1971c2"       // Border color (hex)
}
```

**Common color palettes:**

| Purpose | Background | Stroke |
|---------|------------|--------|
| Primary | `#a5d8ff` | `#1971c2` |
| Success | `#d3f9d8` | `#2b8a3e` |
| Warning | `#ffec99` | `#f59f00` |
| Danger | `#ffc9c9` | `#e03131` |
| Neutral | `#e9ecef` | `#495057` |

### Roughness (Hand-drawn style)

```json
{
  "roughness": 0  // Clean lines
  "roughness": 1  // Low roughness (default)
  "roughness": 2  // High roughness (very sketchy)
}
```

### Fonts

```json
{
  "fontFamily": 1,  // Hand-drawn (Virgil)
  "fontFamily": 2,  // Normal (Helvetica)
  "fontFamily": 3   // Code (monospace)
}
```

---

## Common Diagram Patterns

### 1. Flowchart

```python
# Start node
excalidraw_create_element(type="ellipse", x=100, y=50, width=100, height=50, 
    backgroundColor="#d3f9d8", strokeColor="#2b8a3e")
excalidraw_create_element(type="text", x=125, y=65, text="Start")

# Arrow down
excalidraw_create_element(type="arrow", x=150, y=100, width=0, height=50)

# Process box
excalidraw_create_element(type="rectangle", x=75, y=150, width=150, height=60,
    backgroundColor="#a5d8ff", strokeColor="#1971c2")
excalidraw_create_element(type="text", x=100, y=170, text="Process")

# Arrow down
excalidraw_create_element(type="arrow", x=150, y=210, width=0, height=50)

# Decision diamond
excalidraw_create_element(type="diamond", x=75, y=260, width=150, height=80,
    backgroundColor="#ffec99", strokeColor="#f59f00")
excalidraw_create_element(type="text", x=115, y=290, text="Decision?")
```

### 2. Architecture Diagram

```python
# Web tier
excalidraw_create_element(type="rectangle", x=50, y=50, width=150, height=80,
    backgroundColor="#a5d8ff")
excalidraw_create_element(type="text", x=85, y=80, text="Web Server")

# API tier
excalidraw_create_element(type="rectangle", x=250, y=50, width=150, height=80,
    backgroundColor="#d3f9d8")
excalidraw_create_element(type="text", x=285, y=80, text="API Server")

# Database
excalidraw_create_element(type="ellipse", x=450, y=50, width=150, height=80,
    backgroundColor="#ffc9c9")
excalidraw_create_element(type="text", x=490, y=80, text="Database")

# Connect with arrows
excalidraw_create_element(type="arrow", x=200, y=90, width=50, height=0)
excalidraw_create_element(type="arrow", x=400, y=90, width=50, height=0)
```

### 3. Mind Map

```python
# Central topic
excalidraw_create_element(type="ellipse", x=250, y=200, width=150, height=80,
    backgroundColor="#7950f2", strokeColor="#5f3dc4")
excalidraw_create_element(type="text", x=285, y=230, text="Main Idea", 
    fontSize=20, strokeColor="#ffffff")

# Branches (use batch for efficiency)
excalidraw_batch_create(elements=[
    {"type": "line", "x": 325, "y": 200, "width": 100, "height": -100},
    {"type": "line", "x": 325, "y": 280, "width": 100, "height": 100},
    {"type": "line", "x": 250, "y": 240, "width": -100, "height": 0},
    {"type": "line", "x": 400, "y": 240, "width": 100, "height": 0}
])
```

---

## Layout & Organization

### Aligning Elements

```python
# Get element IDs first
elements = excalidraw_query_elements()
ids = [e["id"] for e in elements["elements"]]

# Align all elements to the left
excalidraw_align_elements(element_ids=ids, alignment="left")

# Center align
excalidraw_align_elements(element_ids=ids, alignment="center")
```

### Distributing Elements

```python
# Distribute horizontally with equal spacing
excalidraw_distribute_elements(element_ids=ids, direction="horizontal")

# Distribute vertically
excalidraw_distribute_elements(element_ids=ids, direction="vertical")
```

### Grouping

```python
# Group related elements
box_id = "abc123"
label_id = "def456"
icon_id = "ghi789"

excalidraw_group_elements(element_ids=[box_id, label_id, icon_id])
# Now they move together as one unit
```

---

## Exporting

### Export as JSON (for editing later)

```python
data = excalidraw_get_resource(format="json")
# Returns Excalidraw scene JSON
```

### Export as SVG (for documents)

```python
svg = excalidraw_get_resource(format="svg")
# Returns SVG string
```

### Export as PNG (for images)

```python
png = excalidraw_get_resource(format="png")
# Returns base64-encoded PNG
```

---

## Troubleshooting

### Canvas Server Not Running

**Symptoms:**
- "Excalidraw server not available" error
- Viewer URL returns 404

**Solution:**
```bash
# Check server logs
cat /tmp/excalidraw.log

# Verify process is running
pgrep -f "excalidraw"

# Restart server manually
cd /app/agents_backend/excalidraw-server
node dist/index.js
```

### WebSocket Not Connecting

**Symptoms:**
- Browser shows canvas but doesn't update

**Solution:**
- Check browser console for WebSocket errors
- Verify port 6003 is exposed
- Try refreshing the page

### Elements Not Appearing

**Symptoms:**
- Tool returns success but canvas is empty

**Solution:**
```python
# Check current elements
elements = excalidraw_query_elements()
print(f"Total elements: {elements['total_count']}")
```

---

## Best Practices

1. **Use batch_create for multiple elements** - More efficient than individual calls

2. **Keep canvas organized** - Use group, align, and distribute tools

3. **Use consistent colors** - Pick a palette and stick to it

4. **Add labels to shapes** - Create text elements overlaid on shapes

5. **Lock finalized elements** - Use lock/unlock to prevent accidental changes

6. **Export regularly** - Use get_resource to save your work

---

## Related Documentation

- [Excalidraw API Contracts](../api-contracts/excalidraw-system.md)
- [Tool Server API](../api-contracts/tool-server.md)
- [Sandbox Guide](./sandbox-guide.md)
