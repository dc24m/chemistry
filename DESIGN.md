<!-- SEED: re-run /impeccable document once there's code to capture the actual tokens and components. -->

---
name: SPECTRAplot
description: Desktop spectrometry visualization for PL, Absorbance, and XRD analysis.
colors:
  bg: "#FFFFFF"
  surface: "#F7F7F7"
  surface-2: "#EDEDED"
  ink: "#171717"
  muted: "#5F5F5F"
  primary: "#2F2F2F"
  border: "#DADADA"
  hover: "#E8E8E8"
  mode-pl: "#F472B6"
  mode-abs: "#38BDF8"
  mode-xrd: "#A78BFA"
typography:
  body:
    fontFamily: "'IBM Plex Sans', 'Inter', system-ui, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.5
  label:
    fontFamily: "'IBM Plex Sans', 'Inter', system-ui, sans-serif"
    fontSize: "12px"
    fontWeight: 500
    lineHeight: 1.4
    letterSpacing: "0.01em"
  mono:
    fontFamily: "'IBM Plex Mono', 'Fira Code', monospace"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.6
rounded:
  sm: "4px"
  md: "8px"
  lg: "12px"
---

# Design System: SPECTRAplot

## 1. Overview

**Creative North Star: "The Monochrome Instrument"**

SPECTRAplot reads as engineered, not merely styled. The interface carries the quiet authority of a precision measurement instrument: white plotting surfaces, neutral gray control chrome, upright technical typography, and no decorative color in the application frame.

The palette is restrained by doctrine. White is the stage; neutral grays define hierarchy and interaction. The PL, Absorbance, and XRD colors are data vocabulary only. They are available for traces and scientific distinction, but they do not tint tabs, buttons, progress bars, sidebars, or focus states.

This system explicitly rejects: Excel's grid-weight visual anonymity and zero brand presence; the cluttered toolbar heritage and icon overload of legacy academic software; and consumer SaaS softness such as pastel fills, playful micro-copy, and rounded-everything controls. The spectrometry data is the product. The interface is the instrument that presents it.

**Key Characteristics:**
- Pure white canvas with neutral gray panels
- Monochrome UI chrome for active, hover, selected, and focus states
- Three fixed mode colors (PL, Absorbance, XRD) as data vocabulary only
- IBM Plex Sans for UI labels; IBM Plex Mono for measured values
- Flat-by-default elevation with tonal layers before shadows
- State-change-only motion at 150-200ms ease-out; no choreography

## 2. Colors: The Instrument Palette

A restrained monochrome palette: pure white ground, two neutral surface depths, near-black text, gray borders, and gray active states. Color is reserved for semantic alerts and plotted data.

### Primary
- **Graphite** (`#2F2F2F`): Primary actions, current selection, checked controls, focus borders, active toolbar buttons, and progress indicators. Always paired with white text when used as a fill.

### Data Colors
- **Mode Colors** - fixed data vocabulary:
  - **PL Pink** (`#F472B6`): Default trace color in PL mode
  - **Absorbance Blue** (`#38BDF8`): Default trace color in Absorbance mode
  - **XRD Violet** (`#A78BFA`): Default trace color in XRD mode

### Neutral
- **Canvas White** (`#FFFFFF`): App and plot background.
- **Panel Gray** (`#F7F7F7`): Sidebar, toolbar tray, secondary panel backgrounds.
- **Raised Gray** (`#EDEDED`): Dock and elevated neutral surfaces.
- **Near Black** (`#171717`): Body text, headings, UI labels.
- **Mid Gray** (`#5F5F5F`): Secondary labels, metadata, coordinate readouts.
- **Light Border** (`#DADADA`): Panel dividers, input stroke at rest, card outlines.
- **Hover Gray** (`#E8E8E8`): Hover and pressed neutral states.

**The Monochrome Chrome Rule.** App chrome uses only white, gray, and near-black. A control can be active, selected, or focused without changing hue.

**The Data Color Fence.** PL Pink, Absorbance Blue, and XRD Violet are fenced to plotted traces and trace defaults. They do not appear as button fills, tab borders, progress bars, badge backgrounds, status indicators, or decorative accents.

## 3. Typography

**Body / UI Font:** IBM Plex Sans (with Inter, system-ui fallback)  
**Mono / Data Font:** IBM Plex Mono (with Fira Code, monospace fallback)

IBM Plex Sans has a precise, slightly narrow, upright personality built for technical documentation and data interfaces. IBM Plex Mono distinguishes measured values from prose without adding decoration.

### Hierarchy
- **Headline** (600, 18px, 1.3): Section headings, dialog titles, mode name in active tab. Rare; most of the UI uses Title or Label.
- **Title** (500, 15px, 1.4): Panel section headers, group box labels, primary file name in the file list.
- **Body** (400, 14px, 1.5): Instructional prose, dialog body text, empty-state copy. 65-75ch max line length.
- **Label** (500, 12px, 1.4, +0.01em tracking): UI control labels, form field keys, dock labels.
- **Mono / Data** (400, 13px, 1.6): Coordinate readout, axis tick labels, wavelength, intensity, 2theta, absorbance, d-spacing, and file paths.

**The Mono Data Rule.** Any number that represents a measured scientific value uses IBM Plex Mono. Prose numbers use IBM Plex Sans.

**The One Family Rule.** IBM Plex Sans covers every UI role. Technical precision comes from weight and scale discipline, not font variety.

## 4. Elevation

The system is flat by default. Depth is expressed through tonal layering: white canvas, panel gray, raised gray, and borders. Shadows are allowed only for existing large canvas/dock framing where they help separate dense desktop panels without becoming decorative.

**The Flat-at-Rest Rule.** Hover states shift background tint. Cards and panels are distinguished primarily by background color and border.

## 5. Components

*Omitted. Re-run `/impeccable document` after implementation changes if component documentation is needed.*

## 6. Do's and Don'ts

### Do:
- **Do** hold the canvas background at exactly `#FFFFFF`.
- **Do** use IBM Plex Mono for every measured scientific value.
- **Do** keep active UI chrome monochrome: graphite fill, graphite border, or neutral hover.
- **Do** restrict mode colors to trace identity and plot defaults.
- **Do** keep transitions at 150-200ms ease-out. State changes only.
- **Do** design interactive components with default, hover, focus, active, disabled, and loading states.
- **Do** use sentence case for labels, buttons, and headings where product copy allows it.

### Don't:
- **Don't** introduce ochre, amber, cream, sand, paper, or other warm-tinted UI chrome.
- **Don't** build grid-heavy, spreadsheet-structured layouts. SPECTRAplot is not Excel.
- **Don't** stack icon-heavy toolbars with unclear visual hierarchy.
- **Don't** use pastel fills, large-radius pill buttons, playful micro-copy, or consumer SaaS softness.
- **Don't** let mode colors appear in UI chrome. They are data colors, not interface accents.
- **Don't** animate anything except state changes.
- **Don't** use gradient text. One solid color per text node.
- **Don't** render measured values in IBM Plex Sans.
