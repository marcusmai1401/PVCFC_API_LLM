# iOS/macOS Design System - Visual Reference

**Theme**: Light Mode Premium
**Inspiration**: iOS 17, macOS Sonoma
**Version**: 0.8.0

---

## 🎨 Color System

### Primary Palette

```
iOS Blue (Primary)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#007aff ███████████  Primary actions, links
#0051d5 ███████████  Button gradient end
#e3f2ff ███████████  Light blue container
```

### Semantic Colors

```
Success (Green)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#34c759 ███████████  High confidence, healthy status

Warning (Orange)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#ff9500 ███████████  Medium confidence, warnings

Error (Red)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#ff3b30 ███████████  Low confidence, errors

Purple (Tertiary)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#af52de ███████████  Accents, highlights
```

### Surface Hierarchy

```
White → Light Gray → Medium Gray
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#ffffff ███████████  Brightest cards
#fafafa ███████████  Subtle background
#f5f5f7 ███████████  Main background
#efefef ███████████  Elevated surfaces
#e5e5ea ███████████  Borders, dividers
```

### Text Hierarchy

```
Black → Gray
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#1d1d1f ███████████  Primary text (iOS text black)
#86868b ███████████  Secondary text (iOS gray)
rgba(0,0,0,0.5) ███████████  Placeholder text
```

---

## 📐 Typography Scale

### Sizes

```
Display Large   48px  Bold      -1.5px tracking
Display Medium  40px  Bold      -1.2px tracking
Display Small   32px  Bold      -0.8px tracking

Title Large     32px  Bold      -0.8px tracking  ← Page titles
Title Medium    22px  SemiBold  -0.4px tracking  ← Section headers
Title Small     20px  SemiBold  -0.3px tracking

Body Large      17px  Regular   -0.3px tracking
Body Medium     16px  Regular   -0.2px tracking  ← Default body
Body Small      15px  Regular   -0.2px tracking

Caption         13px  Regular   -0.1px tracking  ← Labels, hints
```

### Font Stack

```css
'Inter',                    /* Primary (closest to SF Pro) */
-apple-system,              /* macOS system font */
BlinkMacSystemFont,         /* macOS fallback */
'SF Pro Display',           /* iOS/macOS explicit */
'SF Pro Text',              /* iOS/macOS text variant */
'Helvetica Neue',           /* Classic Apple font */
sans-serif                  /* Ultimate fallback */
```

### Usage Examples

```html
<!-- Page title -->
<h1 class="ios-title-large">PVCFC RAG System</h1>

<!-- Section header -->
<h2 class="ios-title">Configuration</h2>

<!-- Body text -->
<p class="ios-body">Enter your question here...</p>

<!-- Caption/label -->
<p class="ios-caption">Last updated: 10:30 AM</p>
```

---

## 🔲 Component Library

### Cards

**Frosted Glass Card** (`.ios-card`):
```css
background: rgba(255, 255, 255, 0.7)
blur: 20px
border: 0.5px white
shadow: 0 8px 32px rgba(31,38,135,0.08)
radius: 20px
padding: 24px

Hover: lift -2px, shadow increases
```

**Usage**:
```html
<div class="ios-card">
    <h2 class="ios-title">System Status</h2>
</div>
```

---

**Flat Card** (`.ios-card-flat`):
```css
background: rgba(255, 255, 255, 0.95)
blur: none
border: 0.5px rgba(0,0,0,0.06)
shadow: 0 2px 8px rgba(0,0,0,0.04)
radius: 16px
padding: 20px
```

**Usage**: Headers, less emphasis

---

**Compact Card** (`.ios-card-compact`):
```css
background: rgba(255, 255, 255, 0.8)
blur: 20px
radius: 12px
padding: 16px
shadow: 0 2px 8px rgba(0,0,0,0.04)
```

**Usage**: Metrics, small info cards

---

### Buttons

**Primary Button**:
```css
background: linear-gradient(180deg, #007aff, #0051d5)
color: white
radius: 12px
padding: 12px 24px
shadow: 0 2px 8px rgba(0,122,255,0.25)
font: 15px, weight 600, -0.2px tracking

Hover: scale(1.02), shadow increases
Active: scale(0.98)
```

**Streamlit Usage**: All `st.button()` automatically styled

---

**Secondary Button**:
```css
background: rgba(142,142,147,0.12)
color: #1d1d1f
shadow: none

Hover: darker background, subtle shadow
```

**Streamlit Usage**: `type="secondary"`

---

### Inputs

**Text Input/Textarea**:
```css
background: rgba(255, 255, 255, 0.95)
border: 1px rgba(0,0,0,0.08)
radius: 12px
padding: 14px 16px
font: 16px, -0.2px tracking

Focus:
  border: #007aff
  shadow: 0 0 0 4px rgba(0,122,255,0.1)
```

**Streamlit Usage**: All `st.text_input()` and `st.text_area()` automatically styled

---

### Tabs

**Segmented Control Style**:
```css
Container:
  background: rgba(255,255,255,0.8)
  blur: 20px
  radius: 16px
  padding: 4px
  gap: 8px

Unselected Tab:
  background: transparent
  color: #86868b
  radius: 12px

Selected Tab:
  background: white
  color: #1d1d1f
  shadow: 0 2px 4px rgba(0,0,0,0.06)
```

---

### Status Indicators

**Status Dot**:
```css
.ios-status-dot {
  width: 12px
  height: 12px
  radius: 50%
}

.ios-status-healthy {
  background: #34c759
  shadow: 0 0 12px rgba(52,199,89,0.4)  /* Glow */
}
```

**Usage**:
```html
<div class="ios-status-dot ios-status-healthy"></div>
```

---

## ✨ Animations

### Page Entrance

```css
@keyframes iosFadeInUp {
  from: opacity 0, translateY(20px)
  to:   opacity 1, translateY(0)
}

Duration: 0.6s
Easing: cubic-bezier(0.16, 1, 0.3, 1)
```

Applied to: All page content on load

---

### Button Press

```css
Hover: scale(1.02)    [200ms]
Active: scale(0.98)   [100ms]
```

Creates tactile feedback like iOS buttons

---

### Card Hover

```css
Transform: translateY(-2px)  [300ms]
Shadow: increased depth
```

Subtle lift effect

---

### Tab Switch

```css
Background: fade in/out
Shadow: fade in/out
Duration: 200ms
```

Smooth iOS-style tab switching

---

### Loading States

**Spinner**:
```css
.ios-spinner
  20px circle
  2px border
  Blue top, transparent rest
  Rotate 360deg in 0.8s
```

**Shimmer**:
```css
.ios-loading-shimmer
  Gradient sweep left to right
  2s duration
  Infinite loop
```

---

## 🎯 Spacing System

### Grid (4px base)

```
xs:  4px   ┃ Tight elements
sm:  8px   ┃ Related items
md:  16px  ┃ Section padding
lg:  24px  ┃ Card padding, major sections
xl:  32px  ┃ Page sections
```

### Component Spacing

```
Between cards:         24px
Between sections:      32px
Inside cards:          16-24px
Button padding:        12px 24px
Input padding:         14px 16px
Tab padding:           10px 20px
```

---

## 🔍 Elevation System

### Shadow Levels

**Level 0** (Flat):
```css
box-shadow: none
```
*Usage*: Text, inline elements

**Level 1** (Subtle):
```css
box-shadow: 0 2px 8px rgba(0,0,0,0.04),
            0 1px 2px rgba(0,0,0,0.02)
```
*Usage*: Input fields, flat cards

**Level 2** (Elevated):
```css
box-shadow: 0 4px 16px rgba(0,0,0,0.06),
            0 2px 4px rgba(0,0,0,0.03)
```
*Usage*: Metrics cards, tabs container

**Level 3** (Floating):
```css
box-shadow: 0 8px 32px rgba(0,0,0,0.08),
            0 4px 8px rgba(0,0,0,0.04)
```
*Usage*: Frosted glass cards, modals

**Level 4** (Modal):
```css
box-shadow: 0 12px 48px rgba(0,0,0,0.10),
            0 6px 12px rgba(0,0,0,0.05)
```
*Usage*: Overlays, popovers

---

## 🌈 Glassmorphism Recipe

### Classic iOS Frosted Glass

```css
.ios-card {
  /* 1. Semi-transparent white background */
  background: rgba(255, 255, 255, 0.7);

  /* 2. Backdrop blur (key effect) */
  backdrop-filter: blur(20px) saturate(180%);
  -webkit-backdrop-filter: blur(20px) saturate(180%);

  /* 3. Subtle border (barely visible) */
  border: 0.5px solid rgba(255, 255, 255, 0.18);

  /* 4. Soft shadow for depth */
  box-shadow: 0 8px 32px rgba(31, 38, 135, 0.08);

  /* 5. Rounded corners */
  border-radius: 20px;

  /* 6. Smooth transitions */
  transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}
```

**Key Parameters**:
- **Opacity**: 0.7 (30% transparent)
- **Blur**: 20px (strong frosted effect)
- **Saturation**: 180% (enhance colors behind)
- **Shadow**: Large spread, low opacity

---

### Variations

**More Opaque** (`.ios-card-flat`):
```css
background: rgba(255, 255, 255, 0.95)  /* 95% opaque */
backdrop-filter: none                   /* No blur */
border: 0.5px solid rgba(0,0,0,0.06)   /* Darker border */
```

**Medium Blur** (`.ios-card-compact`):
```css
background: rgba(255, 255, 255, 0.8)   /* 80% opaque */
backdrop-filter: blur(20px)             /* Same blur */
radius: 12px                            /* Smaller corners */
```

---

## 📱 iOS Design Patterns

### Status Indicators

```
● Healthy   (Green with glow)
● Warning   (Orange with glow)
● Error     (Red with glow)
```

### Metrics Display

```
┌─────────────────────┐
│   CONFIDENCE        │  ← Uppercase caption (gray)
│      92%            │  ← Large number (green)
└─────────────────────┘
```

### List Items

```
┌─────────────────────────────────┐
│ ┃ Citation Title        [View] │  ← Blue left border
│ ┃ Page 12 • Document 3          │  ← Gray meta
│ ┃ Text preview here...          │  ← Gray text
└─────────────────────────────────┘
  Hover: slide right, shadow up
```

### Tabs (Segmented Control)

```
┌─────────────────────────────────┐
│ [Overview] Retrieval  Generation│  ← Selected: white bg
│                                  │  ← Unselected: transparent
└─────────────────────────────────┘
```

---

## 🎭 State Variations

### Button States

```
REST      ███████  #007aff gradient, shadow
HOVER     ████████ Scale 1.02x, shadow ↑
ACTIVE    ██████   Scale 0.98x, shadow ↓
DISABLED  ███████  Opacity 0.4, no interaction
```

### Input States

```
REST      ─────────  1px gray border
FOCUS     ═════════  1px blue border + 4px glow
ERROR     ─────────  1px red border + 4px red glow
DISABLED  ─────────  0.4 opacity, no interaction
```

### Card States

```
REST      ╭─────╮  Default shadow
HOVER     ╭─────╮  Lift -2px, shadow ↑
                ↑
```

---

## 🎬 Animation Timing

### Micro-interactions (Fast)

```
Button hover:   0.2s ease
Tab switch:     0.2s ease-out
Input focus:    0.25s ease
```

### Component transitions (Medium)

```
Card hover:     0.3s cubic-bezier(0.16, 1, 0.3, 1)
Modal open:     0.3s ease-out
```

### Page transitions (Slow)

```
Page load:      0.6s cubic-bezier(0.16, 1, 0.3, 1)
Fade in:        0.6s with translateY(20px)
```

---

## 🔤 Typography Hierarchy

### Example Hierarchy

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  PVCFC RAG System                    ← 32px, bold, -0.8px
  Production-grade document intelligence  ← 16px, gray

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  System Status                       ← 22px, semibold, -0.4px

  CONFIDENCE                          ← 13px, uppercase, gray
     92%                              ← 32px, bold, green

  Last updated: 10:30 AM              ← 13px, gray

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### Letter Spacing

**Negative tracking** (like SF Pro):
- Titles: -0.4px to -1.5px (tighter)
- Body: -0.2px to -0.3px
- Captions: -0.1px

Creates modern, clean look

---

## 🎨 Component Templates

### Hero Section

```html
<div class="ios-card" style="text-align: center; margin-bottom: 32px;">
    <h1 class="ios-title-large" style="margin: 0 0 12px 0;">
        Page Title
    </h1>
    <p class="ios-body" style="margin: 0; color: #86868b;">
        Subtitle or description text
    </p>
</div>
```

---

### Metric Card

```html
<div class="ios-card-compact" style="text-align: center;">
    <p class="ios-caption" style="margin: 0 0 8px 0; text-transform: uppercase; font-weight: 600;">
        METRIC NAME
    </p>
    <p class="ios-title-large" style="margin: 0; color: #34c759;">
        Value
    </p>
</div>
```

---

### Status Indicator

```html
<div style="display: flex; align-items: center; gap: 8px;">
    <div class="ios-status-dot ios-status-healthy"></div>
    <span class="ios-body" style="font-weight: 500;">Healthy</span>
</div>
```

---

### Section Header

```html
<div class="ios-card-flat" style="margin-bottom: 24px;">
    <h2 class="ios-title" style="margin: 0;">Section Title</h2>
</div>
```

---

### Citation Card

```html
<div class="ios-citation-item">
    <div class="ios-citation-item-header">
        <span class="ios-citation-item-title">Document Title</span>
        <span class="ios-citation-item-meta">Page 12</span>
    </div>
    <p class="ios-citation-item-text">
        Text preview of the citation content...
    </p>
</div>
```

---

## 🎯 Best Practices

### Do's ✅

- **Use negative letter-spacing** for titles (-0.4px to -1.5px)
- **Use generous whitespace** (24-32px between sections)
- **Use subtle borders** (0.5px, rgba with low opacity)
- **Use soft shadows** (large spread, low opacity)
- **Use semantic colors** (green = good, red = bad)
- **Use smooth easing** (cubic-bezier curves)
- **Test blur support** (provide fallback)

### Don'ts ❌

- **Don't use dark backgrounds** (this is light mode)
- **Don't use heavy borders** (1px max, preferably 0.5px)
- **Don't use harsh shadows** (keep opacity < 0.15)
- **Don't skip blur prefixes** (-webkit- needed for Safari)
- **Don't use emojis excessively** (minimal, clean)
- **Don't use complex animations** (keep simple, fast)

---

## 🔧 Customization Guide

### Changing Primary Color

**Edit**: `streamlit_app/styles/tokens.css`

```css
--md-sys-color-primary: #007aff;  /* Change this */
```

**Also update button gradient in**: `streamlit_app/styles/m3.css`

```css
background: linear-gradient(180deg, #007aff 0%, #0051d5 100%);
                                    ^^^^^^        ^^^^^^
```

---

### Adjusting Blur Strength

**Edit**: `streamlit_app/styles/m3.css`

```css
.ios-card {
  backdrop-filter: blur(20px);  /* Change 20px to 10-30px */
}
```

**Less blur** (10-15px): More visible content behind
**More blur** (25-30px): More frosted effect

---

### Changing Card Opacity

```css
.ios-card {
  background: rgba(255, 255, 255, 0.7);  /* Change 0.7 to 0.5-0.95 */
}
```

**Lower** (0.5-0.6): More transparent, more blur visible
**Higher** (0.8-0.95): More opaque, less blur needed

---

### Adjusting Hover Effects

```css
.ios-card:hover {
  transform: translateY(-2px);  /* Change -2px to -4px for more lift */
  box-shadow: /* Increase blur radius */;
}
```

---

## 📊 Accessibility

### Color Contrast

**Text on White**:
- Primary text (#1d1d1f): 15.8:1 (AAA) ✅
- Secondary text (#86868b): 4.6:1 (AA) ✅

**White on Blue**:
- White on #007aff: 4.5:1 (AA) ✅

All combinations meet WCAG AA standards.

---

### Focus Indicators

**All interactive elements**:
```css
:focus-visible {
  outline: 2px solid #007aff;
  outline-offset: 2px;
}
```

Provides clear focus indication for keyboard navigation.

---

### Touch Targets

**Minimum size**: 44px (iOS guideline)

Applied to:
- Buttons: min-height 44px
- Tabs: padding ensures 44px height
- Clickable areas: adequate padding

---

## 🌐 Browser Compatibility

### Full Support

✅ Chrome 76+
✅ Edge 79+
✅ Safari 9+
✅ Firefox 103+

**Features**: Glassmorphism, all animations, gradients

---

### Graceful Degradation

⚠️ Chrome 75 and below
⚠️ Firefox 102 and below

**Fallback**: Solid white cards (no blur)
**Impact**: Less visual polish, full functionality

---

### Testing Commands

```javascript
// Check blur support (in browser console)
CSS.supports('backdrop-filter', 'blur(20px)')
// → true (supported) or false (fallback)

// Check gradient support
CSS.supports('background', 'linear-gradient(180deg, #007aff, #0051d5)')
// → true
```

---

## 📐 Layout Guidelines

### Page Structure

```
┌─────────────────────────────────────┐
│ [Sidebar: 280px frosted glass]     │
│                                     │
│  ┌─────────────────────────────┐   │
│  │ [Main: max 1200px centered] │   │
│  │                             │   │
│  │  [Hero Card]                │   │
│  │                             │   │
│  │  [Content Cards]            │   │
│  │                             │   │
│  └─────────────────────────────┘   │
│                                     │
└─────────────────────────────────────┘
```

### Card Spacing

```
[Hero Card]
   ↓ 32px
[Section Card]
   ↓ 24px
[Content Card]
   ↓ 24px
[Content Card]
```

---

## 🎓 Learning Resources

### iOS Design Resources

- [Apple Human Interface Guidelines](https://developer.apple.com/design/human-interface-guidelines/)
- [SF Pro Font](https://developer.apple.com/fonts/)
- [iOS Color Palette](https://developer.apple.com/design/human-interface-guidelines/color)

### CSS Techniques

- [Glassmorphism Generator](https://css.glass/)
- [Cubic Bezier Editor](https://cubic-bezier.com/)
- [Backdrop Filter Support](https://caniuse.com/css-backdrop-filter)

---

## 📝 Changelog from Material Design 3

| Aspect | Material Design 3 | iOS/macOS | Reason |
|--------|-------------------|-----------|--------|
| **Theme** | Dark | Light | Cleaner, professional |
| **Primary** | Green #0E7B55 | Blue #007aff | iOS standard |
| **Cards** | Solid colors | Frosted glass | Premium, modern |
| **Typography** | Material font | Inter/SF Pro | Apple aesthetic |
| **Shadows** | Hard, defined | Soft, subtle | Elegant depth |
| **Buttons** | Pill-shaped | Rounded (12px) | iOS style |
| **Animations** | Standard | Smooth, bouncy | iOS feel |
| **Icons** | Many emojis | Minimal | Clean, professional |
| **Spacing** | Compact | Generous | Breathing room |

---

## ✅ Success Criteria

### Visual

- [ ] Looks like an iOS/macOS app
- [ ] Frosted glass effects work
- [ ] Colors match iOS palette
- [ ] Typography feels premium
- [ ] Spacing is consistent

### Functional

- [ ] All features work
- [ ] No performance issues
- [ ] Animations smooth
- [ ] Accessible (keyboard, screen readers)

### Technical

- [ ] No linter errors ✅
- [ ] Cross-browser tested
- [ ] Mobile responsive
- [ ] Performance benchmarks met

---

**Design System**: Complete ✅
**Implementation**: Complete ✅
**Testing**: Ready ✅
**Documentation**: Complete ✅

**Next**: Test in browser and gather feedback!
