---
name: excalidraw
description: |
  Advanced Excalidraw diagram building skill for creating hand-drawn style diagrams in JSON format.
  Use when the agent needs to CREATE diagrams with sketch/whiteboard aesthetic including: architecture diagrams,
  flowcharts, mind maps, wireframes, system design diagrams, C4 models, cloud architecture (AWS/Azure/GCP),
  sequence diagrams, entity relationships, Kubernetes deployments, network topologies, Gantt charts,
  and any diagram where a hand-drawn, informal visual style is preferred over precise technical drawings.
  Excalidraw's distinctive "rough" appearance makes diagrams feel more approachable and creative.
---

# Excalidraw Diagram Building Skill

This skill teaches how to build advanced Excalidraw diagrams from scratch using JSON format.
The library files in this skill folder contain 97+ component libraries with patterns to learn from.

## Core Concept

Excalidraw diagrams are JSON files with an `elements` array containing shape objects.
Unlike draw.io (XML-based), Excalidraw uses a straightforward JSON structure.

### Complete Diagram Format
```json
{
  "type": "excalidraw",
  "version": 2,
  "source": "https://excalidraw.com",
  "elements": [
    // Array of element objects
  ],
  "appState": {
    "viewBackgroundColor": "#ffffff",
    "gridSize": null
  }
}
```

### Library Format (`.excalidrawlib`)
Libraries contain reusable component groups:
```json
{
  "type": "excalidrawlib",
  "version": 1,
  "source": "https://excalidraw.com",
  "library": [
    [ /* element group 1 - array of elements */ ],
    [ /* element group 2 */ ]
  ]
}
```

---

## Element Types

### Rectangle
The most common shape for boxes, containers, and cards.

```json
{
  "type": "rectangle",
  "id": "rect1",
  "x": 100,
  "y": 50,
  "width": 200,
  "height": 100,
  "angle": 0,
  "strokeColor": "#000000",
  "backgroundColor": "#a5d8ff",
  "fillStyle": "solid",
  "strokeWidth": 1,
  "strokeStyle": "solid",
  "roughness": 1,
  "opacity": 100,
  "groupIds": [],
  "strokeSharpness": "sharp",
  "seed": 12345,
  "version": 1,
  "versionNonce": 67890,
  "isDeleted": false,
  "boundElementIds": null
}
```

### Ellipse
For circles, ovals, and rounded shapes.

```json
{
  "type": "ellipse",
  "id": "ellipse1",
  "x": 300,
  "y": 100,
  "width": 120,
  "height": 120,
  "angle": 0,
  "strokeColor": "#1971c2",
  "backgroundColor": "#a5d8ff",
  "fillStyle": "solid",
  "strokeWidth": 2,
  "strokeStyle": "solid",
  "roughness": 2,
  "opacity": 100,
  "groupIds": [],
  "strokeSharpness": "round",
  "seed": 11111,
  "version": 1,
  "versionNonce": 22222,
  "isDeleted": false,
  "boundElementIds": []
}
```

### Diamond
For decision nodes, special markers, and emphasis.

```json
{
  "type": "diamond",
  "id": "diamond1",
  "x": 500,
  "y": 100,
  "width": 100,
  "height": 100,
  "angle": 0,
  "strokeColor": "#e67700",
  "backgroundColor": "#ffec99",
  "fillStyle": "hachure",
  "strokeWidth": 1,
  "strokeStyle": "solid",
  "roughness": 1,
  "opacity": 100,
  "groupIds": [],
  "strokeSharpness": "sharp",
  "seed": 33333,
  "version": 1,
  "versionNonce": 44444,
  "isDeleted": false,
  "boundElementIds": null
}
```

### Text
For labels, annotations, and descriptions.

```json
{
  "type": "text",
  "id": "text1",
  "x": 150,
  "y": 80,
  "width": 100,
  "height": 25,
  "angle": 0,
  "strokeColor": "#1e1e1e",
  "backgroundColor": "transparent",
  "fillStyle": "hachure",
  "strokeWidth": 1,
  "strokeStyle": "solid",
  "roughness": 1,
  "opacity": 100,
  "groupIds": [],
  "strokeSharpness": "sharp",
  "seed": 55555,
  "version": 1,
  "versionNonce": 66666,
  "isDeleted": false,
  "boundElementIds": null,
  "text": "Hello World",
  "fontSize": 20,
  "fontFamily": 1,
  "textAlign": "left",
  "verticalAlign": "top",
  "baseline": 18
}
```

**Font Family Values:**
- `1` = Virgil (hand-drawn, default)
- `2` = Helvetica (clean sans-serif)
- `3` = Cascadia (monospace/code)

### Line
For custom paths, decorations, and complex shapes.

```json
{
  "type": "line",
  "id": "line1",
  "x": 100,
  "y": 200,
  "width": 200,
  "height": 100,
  "angle": 0,
  "strokeColor": "#2f9e44",
  "backgroundColor": "#b2f2bb",
  "fillStyle": "solid",
  "strokeWidth": 2,
  "strokeStyle": "solid",
  "roughness": 1,
  "opacity": 100,
  "groupIds": [],
  "strokeSharpness": "round",
  "seed": 77777,
  "version": 1,
  "versionNonce": 88888,
  "isDeleted": false,
  "boundElementIds": [],
  "startBinding": null,
  "endBinding": null,
  "points": [
    [0, 0],
    [100, 50],
    [200, 0]
  ],
  "lastCommittedPoint": null,
  "startArrowhead": null,
  "endArrowhead": null
}
```

### Arrow
For connections, flows, and directed relationships.

```json
{
  "type": "arrow",
  "id": "arrow1",
  "x": 300,
  "y": 150,
  "width": 150,
  "height": 50,
  "angle": 0,
  "strokeColor": "#1971c2",
  "backgroundColor": "transparent",
  "fillStyle": "hachure",
  "strokeWidth": 2,
  "strokeStyle": "solid",
  "roughness": 1,
  "opacity": 100,
  "groupIds": [],
  "strokeSharpness": "round",
  "seed": 99999,
  "version": 1,
  "versionNonce": 10101,
  "isDeleted": false,
  "boundElementIds": null,
  "startBinding": {
    "elementId": "rect1",
    "focus": 0.5,
    "gap": 5
  },
  "endBinding": {
    "elementId": "rect2",
    "focus": 0.5,
    "gap": 5
  },
  "points": [
    [0, 0],
    [150, 50]
  ],
  "lastCommittedPoint": null,
  "startArrowhead": null,
  "endArrowhead": "arrow"
}
```

**Arrowhead Values:**
- `null` = no arrowhead
- `"arrow"` = standard arrow
- `"bar"` = perpendicular bar
- `"dot"` = filled circle
- `"triangle"` = filled triangle

---

## Styling Properties Reference

### Fill Styles
| Value | Description |
|-------|-------------|
| `"solid"` | Solid color fill |
| `"hachure"` | Diagonal line pattern (hand-drawn look) |
| `"cross-hatch"` | Crossed diagonal lines |

### Roughness (Hand-drawn Effect)
| Value | Description |
|-------|-------------|
| `0` | Clean, precise lines (architect style) |
| `1` | Slight wobble (default) |
| `2` | Very rough, sketchy lines |

### Stroke Styles
| Value | Description |
|-------|-------------|
| `"solid"` | Continuous line |
| `"dashed"` | Dashed line |
| `"dotted"` | Dotted line |

### Stroke Width
| Value | Description |
|-------|-------------|
| `1` | Thin (default) |
| `2` | Medium |
| `4` | Bold |

### Stroke Sharpness
| Value | Description |
|-------|-------------|
| `"sharp"` | Pointed corners |
| `"round"` | Rounded corners |

### Common Colors (Excalidraw Palette)
| Color | Hex | Use Case |
|-------|-----|----------|
| Light Blue | `#a5d8ff` | Info, neutral |
| Light Green | `#b2f2bb` | Success, positive |
| Light Yellow | `#ffec99` | Warning, attention |
| Light Orange | `#ffc078` | Highlights |
| Light Red | `#ffc9c9` | Error, critical |
| Light Purple | `#d0bfff` | Special, emphasis |
| Light Gray | `#ced4da` | Background, disabled |

### Stroke Colors (Matching)
| Color | Hex |
|-------|-----|
| Blue | `#1971c2` |
| Green | `#2f9e44` |
| Yellow | `#e67700` |
| Orange | `#d9480f` |
| Red | `#c92a2a` |
| Purple | `#7048e8` |
| Black | `#1e1e1e` |
| Gray | `#495057` |

---

## Creating Connections

### Arrow with Bindings
Connect shapes using `startBinding` and `endBinding`:

```json
{
  "type": "arrow",
  "id": "connection1",
  "x": 250,
  "y": 100,
  "width": 100,
  "height": 0,
  "strokeColor": "#1e1e1e",
  "backgroundColor": "transparent",
  "fillStyle": "hachure",
  "strokeWidth": 2,
  "roughness": 1,
  "points": [
    [0, 0],
    [100, 0]
  ],
  "startBinding": {
    "elementId": "sourceShape",
    "focus": 0,
    "gap": 1
  },
  "endBinding": {
    "elementId": "targetShape",
    "focus": 0,
    "gap": 1
  },
  "startArrowhead": null,
  "endArrowhead": "arrow"
}
```

**Binding Properties:**
- `elementId`: ID of the shape to connect to
- `focus`: Position along edge (-1 to 1, 0 = center)
- `gap`: Space between arrow and shape edge

### Curved Arrows (Multiple Points)
```json
{
  "type": "arrow",
  "points": [
    [0, 0],
    [50, -30],
    [100, 0]
  ],
  "strokeSharpness": "round"
}
```

---

## Grouping Elements

Use `groupIds` to logically group elements that should move/scale together:

```json
[
  {
    "type": "rectangle",
    "id": "card-bg",
    "groupIds": ["card-group-1"],
    "x": 100,
    "y": 100,
    "width": 200,
    "height": 150,
    "backgroundColor": "#f8f9fa"
  },
  {
    "type": "text",
    "id": "card-title",
    "groupIds": ["card-group-1"],
    "x": 120,
    "y": 120,
    "text": "Card Title",
    "fontSize": 20
  },
  {
    "type": "text",
    "id": "card-body",
    "groupIds": ["card-group-1"],
    "x": 120,
    "y": 160,
    "text": "Card content here",
    "fontSize": 16
  }
]
```

### Nested Groups
Elements can belong to multiple groups for hierarchical organization:

```json
{
  "groupIds": ["inner-group", "outer-group"]
}
```

---

## Rotation and Positioning

### Angle Property
Rotate elements using radians (not degrees):

```json
{
  "type": "rectangle",
  "angle": 0.785398,  // 45 degrees in radians
  "x": 200,
  "y": 200
}
```

**Angle Conversion:**
- 45° = 0.785398 radians
- 90° = 1.5708 radians
- 180° = 3.14159 radians
- 270° = 4.71239 radians

### Coordinate System
- Origin (0, 0) is top-left
- X increases rightward
- Y increases downward
- All positions are absolute canvas coordinates

---

## Diagram Pattern Examples

### Flowchart Pattern
```json
{
  "type": "excalidraw",
  "elements": [
    {
      "type": "ellipse",
      "id": "start",
      "x": 200,
      "y": 50,
      "width": 100,
      "height": 50,
      "backgroundColor": "#b2f2bb",
      "strokeColor": "#2f9e44"
    },
    {
      "type": "rectangle",
      "id": "process1",
      "x": 175,
      "y": 150,
      "width": 150,
      "height": 60,
      "backgroundColor": "#a5d8ff",
      "strokeColor": "#1971c2"
    },
    {
      "type": "diamond",
      "id": "decision",
      "x": 190,
      "y": 260,
      "width": 120,
      "height": 80,
      "backgroundColor": "#ffec99",
      "strokeColor": "#e67700"
    },
    {
      "type": "arrow",
      "id": "flow1",
      "points": [[0, 0], [0, 50]],
      "x": 250,
      "y": 100,
      "endArrowhead": "arrow"
    }
  ]
}
```

### System Design Card
```json
{
  "type": "excalidraw",
  "elements": [
    {
      "type": "rectangle",
      "id": "service-box",
      "x": 100,
      "y": 100,
      "width": 180,
      "height": 80,
      "backgroundColor": "#a5d8ff",
      "strokeColor": "#1971c2",
      "fillStyle": "solid",
      "roughness": 1,
      "strokeWidth": 2
    },
    {
      "type": "text",
      "id": "service-name",
      "x": 130,
      "y": 125,
      "text": "API Gateway",
      "fontSize": 18,
      "fontFamily": 1
    }
  ]
}
```

---

## Library Resources

When building specific diagram types, study these patterns:

### By Category
| Category | Library Path | Description |
|----------|--------------|-------------|
| AWS | `libraries/childishgirl/aws-architecture-icons.excalidrawlib` | AWS service icons |
| Azure | `libraries/7demonsrising/azure-*.excalidrawlib` | Azure compute, containers, network, storage |
| GCP | `libraries/clementbosc/gcp-icons.excalidrawlib` | Google Cloud icons |
| Kubernetes | `libraries/boemska-nik/kubernetes-icons.excalidrawlib` | K8s components |
| C4 Model | `libraries/dmitry-burnyshev/c4-architecture.excalidrawlib` | C4 architecture patterns |
| UML/ER | `libraries/BjoernKW/UML-ER-library.excalidrawlib` | Entity relationships |
| System Design | `libraries/arach/systems-design-components.excalidrawlib` | Common system components |
| Network | `libraries/dwelle/network-topology-icons.excalidrawlib` | Network diagrams |
| Gantt | `libraries/ferminrp/gantt.excalidrawlib` | Project timelines |
| Wireframe | `libraries/dhaval_godwani/webpage-frames.excalidrawlib` | UI mockups |
| Domain-Driven | `libraries/cespin/domain-driven-design.excalidrawlib` | DDD patterns |
| Hexagonal | `libraries/corlaez/hexagonal-architecture.excalidrawlib` | Ports & adapters |
| Logic Gates | `libraries/aarondiel/logic-gates.excalidrawlib` | Digital circuits |
| Data Viz | `libraries/dbssticky/data-viz.excalidrawlib` | Charts and graphs |

### Icon Libraries
| Library | Path |
|---------|------|
| Awesome Icons | `libraries/ferminrp/awesome-icons.excalidrawlib` |
| Code Essentials | `libraries/cengizhanparlak/code-essentials.excalidrawlib` |
| GitHub Actions | `libraries/devdaejungyoon/github-actions.excalidrawlib` |

---

## Best Practices

1. **Use consistent roughness**: Pick 0, 1, or 2 and stick with it throughout
2. **Color coordination**: Use matching stroke/fill colors from the palette
3. **Group related elements**: Use `groupIds` for components that move together
4. **Unique IDs**: Generate unique IDs for each element
5. **Seed values**: Use random `seed` values for consistent hand-drawn rendering
6. **Font family**: Use `1` (Virgil) for informal, `2` (Helvetica) for clean
7. **Arrow bindings**: Connect arrows to shapes for dynamic updates
8. **Stroke width**: Use `2` or `4` for emphasis, `1` for regular elements
9. **Fill styles**: Use `hachure` for more hand-drawn look, `solid` for emphasis
10. **Grid alignment**: Position elements at multiples of 10 for cleaner layouts
