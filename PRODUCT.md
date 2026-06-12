# Product

## Register

product

## Users

Fellow engineers and researchers in chemistry, physics, and materials science. They know spectrometry intimately — PL, absorbance, XRD are their daily vocabulary. They're running on lab machines, shared workstations, or their own laptops. They care about data fidelity and reproducibility. They will notice if the plot renders incorrectly or a unit is wrong.

## Product Purpose

A cross-platform desktop application (PyQt6) for spectrometry data visualization: upload raw data files, visualize PL / Absorbance / XRD spectra, customize traces, and export publication-ready figures. The tool runs locally — no server, no install friction beyond Python dependencies.

## Brand Personality

Precise · Technical · Confident. The interface speaks the user's language (wavelength, 2θ, intensity) with no softening for a general audience. The UI doesn't perform personality — it earns trust by working exactly as expected.

## Anti-references

- **Excel / spreadsheet UI** — grid-heavy, no visual identity, zero brand presence. This tool is not a spreadsheet.
- **Legacy academic software (OriginLab aesthetic)** — cluttered toolbars, icon overload, dated chrome. The desktop era is not a reference.
- **Consumer SaaS softness (Notion / Airtable)** — pastel palette, rounded-everything, playful micro-copy. Wrong register for a research tool.

## Design Principles

1. **The instrument disappears** — UI chrome compresses to give the plot maximum room. Controls are present but never competing with the data.
2. **Data over decoration** — no gradient fills, no decorative motion, no visual noise that doesn't carry information.
3. **Trust through precision** — exact values, tight labels, no rounding that hides significance. The tool is calibration-grade in its own layout.
4. **Shared by default** — every state is linkable; the share action is always one step away, never buried.
5. **State is never ambiguous** — loading, error, empty, and success states are fully designed, not afterthoughts. A researcher with pending results cannot be left guessing.

## Accessibility & Inclusion

- WCAG AA minimum throughout. Plot overlays and axis labels must hit ≥ 4.5:1.
- Full keyboard navigation. Researchers are keyboard-first users.
- `prefers-reduced-motion` respected: no ambient animations.
- Colorblind-safe trace palette as default (distinguishable without hue alone).
