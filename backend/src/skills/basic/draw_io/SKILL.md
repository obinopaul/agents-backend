---
name: draw_io
description: |
  Advanced draw.io diagram building skill for creating professional-grade diagrams in XML format.
  Use when the agent needs to CREATE any type of diagram including: system architecture diagrams, flowcharts, UML diagrams (class, sequence, activity, component, use case), network/infrastructure diagrams, cloud architecture (AWS/GCP/Azure), BPMN workflows, ER diagrams, Gantt charts, infographics, org charts, mind maps, C4 model diagrams, and any technical or business diagram.
  This skill teaches the complete draw.io XML syntax for building complex, publication-quality diagrams.
---

# Draw.io Diagram Building Skill

This skill teaches how to build advanced draw.io diagrams from scratch using the mxGraph XML format.
The diagram files in this skill folder contain hundreds of patterns to learn from.

## Core Concept

Draw.io diagrams are XML files with `mxCell` elements that define shapes (vertices) and connections (edges).
Every diagram follows this structure:

```xml
<mxfile host="app.diagrams.net" pages="1">
  <diagram id="unique_id" name="Page Name">
    <mxGraphModel dx="1426" dy="1935" grid="1" gridSize="10" guides="1" tooltips="1" 
                  connect="1" arrows="1" fold="1" page="1" pageScale="1" 
                  pageWidth="827" pageHeight="1169" math="0" shadow="0">
      <root>
        <mxCell id="0" />
        <mxCell id="1" parent="0" />
        <!-- All shapes and edges defined here with parent="1" -->
      </root>
    </mxGraphModel>
  </diagram>
</mxfile>
```

Key attributes:
- `dx`, `dy`: Canvas offset/scroll position
- `pageWidth`, `pageHeight`: Page dimensions in pixels
- `grid`, `gridSize`: Grid settings for snapping
- Cell `id="0"` is the root, `id="1"` is the default layer, all elements use `parent="1"`

---

## Creating Shapes (Vertices)

Shapes are `mxCell` elements with `vertex="1"`. The `style` attribute controls appearance.

### Basic Rectangle
```xml
<mxCell id="shape1" parent="1" vertex="1" value="My Label"
    style="rounded=0;whiteSpace=wrap;html=1;fillColor=#dae8fc;strokeColor=#6c8ebf;">
  <mxGeometry x="100" y="50" width="120" height="60" as="geometry" />
</mxCell>
```

### Rounded Rectangle (Most Common)
```xml
<mxCell id="shape2" parent="1" vertex="1" value="Transformer Block"
    style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ffe6cc;strokeColor=#000000;">
  <mxGeometry x="435" y="190" width="105" height="24" as="geometry" />
</mxCell>
```

### Ellipse/Circle
```xml
<mxCell id="circle1" parent="1" vertex="1" value=""
    style="ellipse;whiteSpace=wrap;html=1;fillColor=#d5e8d4;strokeColor=#82b366;">
  <mxGeometry x="200" y="100" width="80" height="80" as="geometry" />
</mxCell>
```

### Diamond (Decision)
```xml
<mxCell id="diamond1" parent="1" vertex="1" value="Decision?"
    style="rhombus;whiteSpace=wrap;html=1;fillColor=#fff2cc;strokeColor=#d6b656;">
  <mxGeometry x="150" y="200" width="100" height="80" as="geometry" />
</mxCell>
```

### Special Shapes
```xml
<!-- Database/Cylinder -->
<mxCell id="db1" parent="1" vertex="1" value="Database"
    style="shape=cylinder3;whiteSpace=wrap;html=1;boundedLbl=1;backgroundOutline=1;
           size=15;fillColor=#f8cecc;strokeColor=#b85450;">
  <mxGeometry x="300" y="100" width="60" height="80" as="geometry" />
</mxCell>

<!-- Datastore -->
<mxCell id="store1" parent="1" vertex="1" value="Memory Cache"
    style="shape=datastore;whiteSpace=wrap;html=1;fillColor=#e1d5e7;strokeColor=#000000;">
  <mxGeometry x="660" y="108" width="89" height="98" as="geometry" />
</mxCell>

<!-- Document -->
<mxCell id="doc1" parent="1" vertex="1" value="Report"
    style="shape=document;whiteSpace=wrap;html=1;boundedLbl=1;fillColor=#f5f5f5;strokeColor=#666666;">
  <mxGeometry x="400" y="150" width="100" height="70" as="geometry" />
</mxCell>

<!-- Process -->
<mxCell id="proc1" parent="1" vertex="1" value="Process"
    style="shape=process;whiteSpace=wrap;html=1;backgroundOutline=1;">
  <mxGeometry x="100" y="300" width="120" height="60" as="geometry" />
</mxCell>

<!-- XOR/OR Circle -->
<mxCell id="xor1" parent="1" vertex="1" value=""
    style="shape=orEllipse;perimeter=ellipsePerimeter;whiteSpace=wrap;html=1;backgroundOutline=1;">
  <mxGeometry x="292" y="98" width="14" height="14" as="geometry" />
</mxCell>
```

### Container/Group Box
```xml
<!-- Container that groups other elements visually -->
<mxCell id="container1" parent="1" vertex="1" value=""
    style="rounded=1;whiteSpace=wrap;html=1;fillColor=#f5f5f5;fontColor=#333333;strokeColor=#000000;">
  <mxGeometry x="90" y="20" width="102" height="219" as="geometry" />
</mxCell>
<!-- Child elements can reference container as parent for grouping -->
```

---

## Creating Connections (Edges)

Edges are `mxCell` elements with `edge="1"`. They connect shapes using `source` and `target` attributes.

### Basic Arrow
```xml
<mxCell id="edge1" parent="1" edge="1" source="shape1" target="shape2" value=""
    style="endArrow=classic;html=1;rounded=0;strokeColor=default;endFill=1;endSize=4;">
  <mxGeometry relative="1" as="geometry" />
</mxCell>
```

### Styled Connector with Auto-routing
```xml
<mxCell id="edge2" parent="1" edge="1" source="source_id" target="target_id" value=""
    style="edgeStyle=none;shape=connector;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;
           strokeColor=default;align=center;verticalAlign=middle;fontFamily=Helvetica;
           fontSize=11;fontColor=default;labelBackgroundColor=default;
           startSize=3;endArrow=classic;endFill=1;endSize=4;">
  <mxGeometry relative="1" as="geometry" />
</mxCell>
```

### Dashed Line
```xml
<mxCell id="edge3" parent="1" edge="1" source="a" target="b" value=""
    style="endArrow=classic;dashed=1;html=1;rounded=0;strokeWidth=1;endFill=1;">
  <mxGeometry relative="1" as="geometry" />
</mxCell>
```

### Bidirectional Arrow
```xml
<mxCell id="edge4" parent="1" edge="1" source="a" target="b" value=""
    style="endArrow=open;startArrow=open;html=1;rounded=0;startFill=0;endFill=0;dashed=1;">
  <mxGeometry relative="1" as="geometry" />
</mxCell>
```

### Edge with Waypoints (Custom Path)
```xml
<mxCell id="edge5" parent="1" edge="1" value=""
    style="endArrow=classic;html=1;rounded=1;strokeColor=default;endSize=4;curved=0;">
  <mxGeometry height="50" relative="1" width="50" as="geometry">
    <mxPoint x="144" y="160" as="sourcePoint" />
    <mxPoint x="134" y="107" as="targetPoint" />
    <Array as="points">
      <mxPoint x="98" y="160" />
      <mxPoint x="98" y="107" />
    </Array>
  </mxGeometry>
</mxCell>
```

### Edge with Label
```xml
<mxCell id="edge6" parent="1" edge="1" source="a" target="b" value=""
    style="endArrow=open;html=1;rounded=0;dashed=1;endFill=0;">
  <mxGeometry relative="1" as="geometry" />
</mxCell>
<!-- Label as child of edge -->
<mxCell id="label1" parent="edge6" vertex="1" connectable="0" value="&lt;b&gt;API Call&lt;/b&gt;"
    style="edgeLabel;html=1;align=center;verticalAlign=middle;resizable=0;points=[];
           fontFamily=Helvetica;fontSize=11;fontColor=default;labelBackgroundColor=default;">
  <mxGeometry relative="1" x="-0.04" as="geometry">
    <mxPoint x="-2" as="offset" />
  </mxGeometry>
</mxCell>
```

### Entry/Exit Points
Control where edges connect to shapes:
- `entryX=0` (left), `entryX=1` (right), `entryX=0.5` (center)
- `entryY=0` (top), `entryY=1` (bottom), `entryY=0.5` (middle)
- Same for `exitX`, `exitY`

```xml
<mxCell id="edge7" parent="1" edge="1" source="a" target="b" value=""
    style="endArrow=classic;html=1;entryX=0.5;entryY=1;entryDx=0;entryDy=0;
           exitX=0.5;exitY=0;exitDx=0;exitDy=0;">
  <mxGeometry relative="1" as="geometry" />
</mxCell>
```

---

## Text Elements

### Standalone Text
```xml
<mxCell id="text1" parent="1" vertex="1" 
    value="&lt;div style=&quot;line-height: 150%;&quot;&gt;&lt;b&gt;Section Title&lt;/b&gt;&lt;/div&gt;"
    style="text;whiteSpace=wrap;html=1;fontFamily=Helvetica;fontSize=11;fontColor=default;
           labelBackgroundColor=default;align=center;">
  <mxGeometry x="477" y="272" width="111" height="34" as="geometry" />
</mxCell>
```

### Rich Text with HTML
The `value` attribute supports HTML:
- `&lt;b&gt;bold&lt;/b&gt;` for **bold**
- `&lt;i&gt;italic&lt;/i&gt;` for *italic*
- `&lt;br&gt;` for line breaks
- `&lt;font style=&quot;font-size: 14px;&quot;&gt;` for sizing

---

## Style Property Reference

### Fill Colors (Common Palette)
| Color | Hex Code | Use Case |
|-------|----------|----------|
| Light Blue | `#dae8fc` | General boxes, info |
| Light Green | `#d5e8d4` | Success, positive |
| Light Yellow | `#fff2cc` | Warning, attention |
| Light Orange/Peach | `#ffe6cc` | Process, action |
| Light Red/Pink | `#f8cecc` | Error, critical |
| Light Purple | `#e1d5e7` | Special, emphasis |
| Light Gray | `#f5f5f5` | Background, container |

### Stroke Colors (Matching)
| Color | Hex Code |
|-------|----------|
| Blue | `#6c8ebf` |
| Green | `#82b366` |
| Yellow | `#d6b656` |
| Orange | `#d79b00` |
| Red | `#b85450` |
| Purple | `#9673a6` |
| Black | `#000000` |
| Gray | `#666666` |

### Shape Properties
| Property | Values | Description |
|----------|--------|-------------|
| `rounded` | `0`, `1` | Rounded corners |
| `dashed` | `0`, `1` | Dashed border |
| `strokeWidth` | `1`, `2`, `3`... | Line thickness |
| `opacity` | `0-100` | Transparency |
| `shadow` | `0`, `1` | Drop shadow |
| `flipV` | `0`, `1` | Flip vertical |
| `flipH` | `0`, `1` | Flip horizontal |

### Arrow Types
| Property | Values |
|----------|--------|
| `endArrow` | `none`, `classic`, `classicThin`, `block`, `open`, `oval`, `diamond`, `diamondThin` |
| `startArrow` | Same as endArrow |
| `endFill` | `0` (hollow), `1` (filled) |
| `startFill` | `0` (hollow), `1` (filled) |

### Edge Styles
| Property | Values | Description |
|----------|--------|-------------|
| `edgeStyle` | `none`, `orthogonalEdgeStyle`, `elbowEdgeStyle` | Routing style |
| `curved` | `0`, `1` | Curved routing |
| `orthogonalLoop` | `0`, `1` | Loop handling |
| `jettySize` | `auto`, number | Connection spacing |

### Typography
| Property | Values |
|----------|--------|
| `fontFamily` | `Helvetica`, `Arial`, `Times New Roman` |
| `fontSize` | `10`, `11`, `12`, `14`... |
| `fontColor` | Hex color or `default` |
| `fontStyle` | `0` (normal), `1` (bold), `2` (italic), `3` (bold+italic) |
| `align` | `left`, `center`, `right` |
| `verticalAlign` | `top`, `middle`, `bottom` |

---

## Multi-Page Diagrams

For complex documentation, create multiple pages:

```xml
<mxfile host="app.diagrams.net" pages="3">
  <diagram id="page1" name="Overview">
    <mxGraphModel ...>
      <root>...</root>
    </mxGraphModel>
  </diagram>
  <diagram id="page2" name="Details">
    <mxGraphModel ...>
      <root>...</root>
    </mxGraphModel>
  </diagram>
  <diagram id="page3" name="Implementation">
    <mxGraphModel ...>
      <root>...</root>
    </mxGraphModel>
  </diagram>
</mxfile>
```

---

## Diagram Type Patterns

### Flowchart Pattern
```xml
<!-- Start -->
<mxCell id="start" parent="1" vertex="1" value="Start"
    style="ellipse;whiteSpace=wrap;html=1;fillColor=#d5e8d4;strokeColor=#82b366;">
  <mxGeometry x="200" y="50" width="80" height="40" as="geometry" />
</mxCell>

<!-- Process -->
<mxCell id="process1" parent="1" vertex="1" value="Process Step"
    style="rounded=1;whiteSpace=wrap;html=1;fillColor=#dae8fc;strokeColor=#6c8ebf;">
  <mxGeometry x="175" y="120" width="130" height="50" as="geometry" />
</mxCell>

<!-- Decision -->
<mxCell id="decision" parent="1" vertex="1" value="Condition?"
    style="rhombus;whiteSpace=wrap;html=1;fillColor=#fff2cc;strokeColor=#d6b656;">
  <mxGeometry x="190" y="200" width="100" height="80" as="geometry" />
</mxCell>

<!-- End -->
<mxCell id="end" parent="1" vertex="1" value="End"
    style="ellipse;whiteSpace=wrap;html=1;fillColor=#f8cecc;strokeColor=#b85450;">
  <mxGeometry x="200" y="320" width="80" height="40" as="geometry" />
</mxCell>

<!-- Connections -->
<mxCell id="e1" parent="1" edge="1" source="start" target="process1"
    style="endArrow=classic;html=1;">
  <mxGeometry relative="1" as="geometry" />
</mxCell>
```

### UML Class Diagram Pattern
```xml
<!-- Class Box with Compartments -->
<mxCell id="class1" parent="1" vertex="1" 
    value="&lt;b&gt;ClassName&lt;/b&gt;&lt;hr&gt;- field1: type&lt;br&gt;- field2: type&lt;hr&gt;+ method1()&lt;br&gt;+ method2()"
    style="swimlane;fontStyle=0;childLayout=stackLayout;horizontal=1;startSize=26;
           fillColor=#dae8fc;horizontalStack=0;resizeParent=1;resizeParentMax=0;
           resizeLast=0;collapsible=0;marginBottom=0;strokeColor=#6c8ebf;">
  <mxGeometry x="100" y="100" width="160" height="120" as="geometry" />
</mxCell>

<!-- Inheritance Arrow -->
<mxCell id="inherit" parent="1" edge="1" source="child" target="parent"
    style="endArrow=block;endFill=0;html=1;">
  <mxGeometry relative="1" as="geometry" />
</mxCell>

<!-- Composition -->
<mxCell id="compose" parent="1" edge="1" source="whole" target="part"
    style="endArrow=diamondThin;endFill=1;html=1;">
  <mxGeometry relative="1" as="geometry" />
</mxCell>
```

### Sequence Diagram Pattern
```xml
<!-- Lifeline -->
<mxCell id="actor1" parent="1" vertex="1" value="Actor"
    style="shape=umlLifeline;perimeter=lifelinePerimeter;whiteSpace=wrap;html=1;
           container=1;collapsible=0;recursiveResize=0;outlineConnect=0;">
  <mxGeometry x="100" y="50" width="100" height="300" as="geometry" />
</mxCell>

<!-- Message -->
<mxCell id="msg1" parent="1" edge="1" source="actor1" target="actor2"
    style="html=1;verticalAlign=bottom;startArrow=none;endArrow=block;
           startSize=8;curved=0;rounded=0;">
  <mxGeometry relative="1" as="geometry">
    <mxPoint y="30" as="offset" />
  </mxGeometry>
</mxCell>
```

### Network Diagram Pattern
```xml
<!-- Server -->
<mxCell id="server" parent="1" vertex="1" value="Web Server"
    style="image;aspect=fixed;perimeter=ellipsePerimeter;html=1;align=center;
           shadow=0;dashed=0;image=img/lib/allied_telesis/computer_and_terminals/Server.svg;">
  <mxGeometry x="200" y="100" width="50" height="62" as="geometry" />
</mxCell>

<!-- Cloud -->
<mxCell id="cloud" parent="1" vertex="1" value="Internet"
    style="ellipse;shape=cloud;whiteSpace=wrap;html=1;fillColor=#f5f5f5;strokeColor=#666666;">
  <mxGeometry x="300" y="80" width="120" height="80" as="geometry" />
</mxCell>
```

---

## Grouping and Hierarchy

### Visual Grouping with Container
```xml
<!-- Background container -->
<mxCell id="group1" parent="1" vertex="1" value=""
    style="rounded=1;whiteSpace=wrap;html=1;fillColor=#f5f5f5;strokeColor=#000000;">
  <mxGeometry x="50" y="50" width="200" height="150" as="geometry" />
</mxCell>

<!-- Elements inside (same parent="1" but positioned within container) -->
<mxCell id="item1" parent="1" vertex="1" value="Item 1"
    style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ffe6cc;strokeColor=#000000;">
  <mxGeometry x="70" y="70" width="80" height="30" as="geometry" />
</mxCell>
```

### Logical Grouping with Parent Reference
```xml
<!-- Group container -->
<mxCell id="groupContainer" parent="1" vertex="1" connectable="0"
    style="group">
  <mxGeometry x="50" y="50" width="200" height="150" as="geometry" />
</mxCell>

<!-- Child elements reference group as parent -->
<mxCell id="child1" parent="groupContainer" vertex="1" value="Child"
    style="rounded=1;whiteSpace=wrap;html=1;">
  <mxGeometry x="10" y="10" width="80" height="30" as="geometry" />
</mxCell>
```

---

## Reference Files

When building specific diagram types, study these patterns:

### By Diagram Category
| Type | Reference Path | Key Patterns |
|------|----------------|--------------|
| UML | `templates/uml/`, `templates/software/` | Class, sequence, activity diagrams |
| Cloud Architecture | `templates/cloud/`, `templates/gcp/`, `examples/aws-*.drawio` | AWS/GCP/Azure components |
| Flowcharts | `templates/flowcharts/`, `examples/WorkflowFlowchart.xml` | Process flows, decisions |
| Network | `templates/network/` | Infrastructure, topology |
| BPMN | `examples/bpmn-*.drawio` | Business process modeling |
| C4 Model | `blog/C4.drawio` | Context, Container, Component, Code |
| Infographics | `templates/infographic/`, `examples/infographic-*.drawio` | Visual data presentation |
| Gantt Charts | `examples/GanttChart.xml`, `blog/gantt-*.drawio` | Project timelines |

### Advanced Examples
| File | Description |
|------|-------------|
| `Engram.drawio` | Multi-page system architecture with advanced styling |
| `blog/C4.drawio` | Complete C4 model with 4 pages (Context, Container, Component, Class) |
| `blog/dependency-graphs.drawio` | Complex node relationships |
| `blog/salesforce-diagram-example.drawio` | Enterprise integration patterns |

---

## Best Practices

1. **Use consistent IDs**: Prefix IDs by type (`shape_`, `edge_`, `text_`)
2. **Layer backgrounds first**: Draw container shapes before content
3. **Align to grid**: Use coordinates divisible by 10 for clean alignment
4. **Color coding**: Use consistent colors for element types
5. **Font consistency**: Stick to Helvetica 11px for most text
6. **Edge routing**: Use `edgeStyle=orthogonalEdgeStyle` for clean right-angle connections
7. **Labels on edges**: Add context to connections with edge labels
8. **Multiple pages**: Break complex diagrams into logical pages
