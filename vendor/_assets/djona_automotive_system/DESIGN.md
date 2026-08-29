---
name: Djona Automotive System
colors:
  surface: '#f8f9f9'
  surface-dim: '#d9dada'
  surface-bright: '#f8f9f9'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f3f4f4'
  surface-container: '#edeeee'
  surface-container-high: '#e7e8e8'
  surface-container-highest: '#e1e3e3'
  on-surface: '#191c1c'
  on-surface-variant: '#41474e'
  inverse-surface: '#2e3131'
  inverse-on-surface: '#f0f1f1'
  outline: '#72787f'
  outline-variant: '#c1c7cf'
  surface-tint: '#2f6388'
  primary: '#003b5a'
  on-primary: '#ffffff'
  primary-container: '#1a5276'
  on-primary-container: '#94c5ee'
  inverse-primary: '#9bccf6'
  secondary: '#865300'
  on-secondary: '#ffffff'
  secondary-container: '#fea520'
  on-secondary-container: '#694000'
  tertiary: '#26384b'
  on-tertiary: '#ffffff'
  tertiary-container: '#3d4f63'
  on-tertiary-container: '#aec1d8'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#cbe6ff'
  primary-fixed-dim: '#9bccf6'
  on-primary-fixed: '#001e30'
  on-primary-fixed-variant: '#0e4b6e'
  secondary-fixed: '#ffddb9'
  secondary-fixed-dim: '#ffb961'
  on-secondary-fixed: '#2b1700'
  on-secondary-fixed-variant: '#663e00'
  tertiary-fixed: '#d1e4fc'
  tertiary-fixed-dim: '#b5c8e0'
  on-tertiary-fixed: '#091d2e'
  on-tertiary-fixed-variant: '#36485c'
  background: '#f8f9f9'
  on-background: '#191c1c'
  surface-variant: '#e1e3e3'
typography:
  display-lg:
    fontFamily: Montserrat
    fontSize: 48px
    fontWeight: '700'
    lineHeight: 56px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Montserrat
    fontSize: 32px
    fontWeight: '700'
    lineHeight: 40px
  headline-lg-mobile:
    fontFamily: Montserrat
    fontSize: 24px
    fontWeight: '700'
    lineHeight: 32px
  headline-md:
    fontFamily: Montserrat
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
  body-lg:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '400'
    lineHeight: 28px
  body-md:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  label-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '600'
    lineHeight: 20px
    letterSpacing: 0.01em
  label-sm:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  base: 8px
  container-margin-mobile: 16px
  container-margin-desktop: 32px
  gutter: 16px
  section-gap: 48px
---

## Brand & Style

This design system is engineered to position the product as the most reliable and premium automotive marketplace in Côte d'Ivoire. The brand personality is **Professional, Efficient, and Trustworthy**, bridging the gap between digital convenience and high-value physical assets.

The visual style is **Corporate / Modern**, characterized by:
- **Mobile-First Utility:** Optimized for high-speed browsing and one-handed interactions common in urban Ivorian environments.
- **Premium Trust:** A reliance on clean, structured layouts and generous whitespace to distinguish the platform from cluttered classified sites.
- **Action-Oriented:** Strategic use of high-contrast accents to guide users toward the primary transactional differentiator: "Acheter via Djona."

## Colors

The palette is derived directly from the brand's visual identity to ensure immediate recognition and professional consistency.

- **Primary (Deep Navy):** Used for headers, primary navigation, and core branding elements. It evokes stability and institutional trust.
- **Accent (Vibrant Orange):** Reserved strictly for primary Call-to-Actions (CTAs), special "Djona Verified" badges, and critical interactive highlights.
- **Secondary (Slate):** Used for iconography and secondary UI elements to maintain a sophisticated tonal balance.
- **Neutrals:** A range of cool grays and off-whites are used to define surface levels and provide a clean backdrop that makes vehicle photography stand out.

## Typography

The typographic hierarchy uses a dual-font approach to balance impact with legibility.

- **Headlines (Montserrat):** Used for marketing copy and major headings. The geometric nature of Montserrat conveys modernism and confidence.
- **Body & Interface (Inter):** Used for all functional text, specifications, and data-heavy tables. Inter ensures maximum readability across varied screen qualities and sizes.
- **Hierarchy:** Maintain a clear distinction between vehicle pricing (Headline-MD) and technical specifications (Label-SM) to allow users to scan listings quickly.

## Layout & Spacing

This design system utilizes a **fluid grid** with a strong emphasis on vertical rhythm to support "Mobile First" browsing.

- **Grid Model:** A 4-column grid for mobile and a 12-column grid for desktop.
- **Margins:** 16px lateral margins on mobile devices to maximize real estate for vehicle imagery, expanding to 32px or fixed-max-width (1280px) on desktop.
- **Spacing Rhythm:** Based on an 8px baseline. Use larger 48px or 64px gaps between major sections (e.g., "Featured Listings" vs "Search by Category") to provide the requested "generous whitespace."

## Elevation & Depth

To achieve a premium, trustworthy feel, the system uses **Tonal Layers** combined with **Ambient Shadows**.

- **Surfaces:** The main background is neutral-light (#F8F9F9). Cards and containers are pure white (#FFFFFF) to pop against the background.
- **Shadows:** Use a "Soft Signature" shadow for cards: `0px 4px 12px rgba(26, 82, 118, 0.08)`. The blue tint in the shadow creates a more cohesive, professional look than pure black.
- **Interactive States:** On hover or active states, the elevation should increase slightly with a more pronounced shadow to provide tactile feedback.

## Shapes

The shape language reflects the stability of the automotive industry.

- **Standard Radius:** 8px (0.5rem) is the default for buttons and input fields, providing a modern but grounded feel.
- **Large Radius:** 16px (1rem) for listing cards and modal containers to create a softer, approachable container for high-quality photography.
- **Icons:** Use linear icons with a 2px stroke weight to match the clean, professional aesthetic of the typography.

## Components

### Buttons
- **Primary:** Deep Navy background with White text. Bold and authoritative.
- **Accent (Acheter via Djona):** Vibrant Orange background with White text. Used exclusively for the main conversion goal.
- **Secondary:** Transparent background with Deep Navy border.

### Cards (Vehicle Listings)
- Use a vertical stack on mobile: Image (Top) -> Info (Bottom). 
- Images should have a subtle inner glow or border to ensure white cars don't bleed into white cards.
- Price should always be the most prominent text element after the vehicle title.

### Input Fields
- High-contrast labels (Text Main).
- 8px rounded corners with a 1px border (#D5DBDB). 
- Active state uses a 2px Primary Deep Navy border.

### Chips & Badges
- **Verified Badge:** Small, secondary-colored (Orange) pill with a check icon.
- **Condition Tags:** Light gray background with Slate text (e.g., "Occasion", "Neuf").

### Lists
- Use horizontal dividers with a low-opacity (#EBEDEF) to separate specifications (Mileage, Fuel, Year) in car detail views.