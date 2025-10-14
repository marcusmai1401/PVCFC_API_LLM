# Material Design 3 Theming Guide
## PVCFC RAG System UI

### Overview
This guide explains how the Material Design 3 (Expressive) theme system is implemented in the PVCFC RAG Streamlit UI.

### Architecture

#### 1. Design Tokens (`styles/tokens.json` & `styles/tokens.css`)
- **Color Roles**: Primary, Secondary, Tertiary, Error, Surface variants
- **Typography Scale**: Display, Headline, Title, Label, Body (15 variants)
- **Shape Scale**: 7 corner radius values (none → full/pill)
- **Elevation**: 6 levels (0-5) with shadow definitions
- **Motion**: Duration and easing curves for transitions

**Seed Color**: `#0E7B55` (PVCFC brand green)

#### 2. Component Styles (`styles/m3.css`)
Provides:
- Global base styles applying tokens
- Component classes (buttons, chips, cards, text fields)
- Streamlit overrides for native widgets
- State layers (hover, focus, pressed)
- Focus-visible rings (WCAG AA compliant)
- Utility classes (spacing, elevation, surfaces)

#### 3. Material Symbols (`styles/material-symbols.css`)
Icon system:
- Google Fonts Material Symbols Outlined
- 35+ pre-defined icon classes
- Size variants (18-48px)
- Weight and fill variants
- Icon buttons with state layers
- Color roles integration

#### 4. Component Library
- **Side Sheet** (`components/side_sheet.py`): Modal drawer for citations
- **Query Lab** (`components/query_lab_improved.py`): Main QA interface
- **System Status** (`components/system_status.py`): Health dashboard

#### 5. Theme Utilities (`utils/theme.py`)
Python helpers for:
- Loading and injecting CSS
- Theme switching (light/dark/system)
- Theme persistence in session state
- System theme detection

### Usage

#### Initializing the Theme
In your main app file:

```python
from streamlit_app.utils.theme import initialize_m3_theme

# Call once at app startup (after st.set_page_config)
initialize_m3_theme()
```

#### Using Typography Classes
```python
st.markdown('<h1 class="md-typescale-headline-medium">Page Title</h1>', unsafe_allow_html=True)
st.markdown('<p class="md-typescale-body-large">Body text here</p>', unsafe_allow_html=True)
```

#### Using Component Classes

**Cards:**
```python
st.markdown('''
<div class="md-card md-card-elevated md-spacing-md">
    <div class="md-typescale-title-medium">Card Title</div>
    <div class="md-typescale-body-medium">Card content</div>
</div>
''', unsafe_allow_html=True)
```

**Buttons** (Streamlit buttons automatically styled):
```python
# Primary filled button
st.button("Submit", type="primary")

# Secondary button
st.button("Cancel", type="secondary")
```

**Chips** (simulated with buttons):
```python
col1, col2 = st.columns(2)
with col1:
    if st.button("Option A", key="chip_a", type="primary" if selected == "a" else "secondary"):
        selected = "a"
```

#### Using Color Tokens
```python
st.markdown('''
<div style="background-color: var(--md-sys-color-surface-container);
            color: var(--md-sys-color-on-surface);
            padding: 16px;
            border-radius: var(--md-sys-shape-corner-medium);">
    Content with M3 colors
</div>
''', unsafe_allow_html=True)
```

#### Theme Switcher Widget
```python
from streamlit_app.utils.theme import render_theme_switcher

# In sidebar or main area
render_theme_switcher()
```

#### Material Icons
```python
# Basic icon in HTML
st.markdown('<span class="material-symbols-outlined">search</span>', unsafe_allow_html=True)

# Icon with size and color
st.markdown('''
<span class="material-symbols-outlined md-24 md-icon-primary">check_circle</span>
''', unsafe_allow_html=True)

# Icon button
st.markdown('''
<button class="md-icon-button" onclick="alert('Clicked!')">
    <span class="material-symbols-outlined">settings</span>
</button>
''', unsafe_allow_html=True)

# Icon with text (aligned)
st.markdown('''
<div class="md-icon-text">
    <span class="material-symbols-outlined">picture_as_pdf</span>
    <span>View PDF</span>
</div>
''', unsafe_allow_html=True)
```

**Available Icons**: search, close, menu, settings, home, info, error, check_circle, warning, visibility, download, upload, refresh, delete, edit, add, remove, expand_more, expand_less, arrow_forward, arrow_back, play_arrow, stop, picture_as_pdf, article, folder, description, link, open_in_new, filter_list, sort, light_mode, dark_mode, contrast

**Icon Sizes**: `md-18`, `md-20`, `md-24` (default), `md-36`, `md-48`

**Icon Colors**: `md-icon-primary`, `md-icon-secondary`, `md-icon-tertiary`, `md-icon-error`, `md-icon-on-surface`, `md-icon-on-surface-variant`

#### Citation Side Sheet
```python
from streamlit_app.components.side_sheet import render_citation_side_sheet

# Render side sheet with citations
if st.session_state.get("show_citations_sheet", False):
    render_citation_side_sheet(
        citations=citations_list,
        api_base_url=st.session_state.api_base_url,
        selected_citation_idx=0,  # Opens the sheet
    )

# Trigger button
if st.button("📋 View Citations"):
    st.session_state.show_citations_sheet = True
    st.rerun()
```

**Side Sheet Features**:
- 480px wide (90vw on mobile)
- Slide-in animation from right
- Scrim overlay (click to close)
- Escape key to close
- Sticky header with close button
- Citation cards with PDF links

### Color Roles Reference

| Role | Light | Dark | Usage |
|------|-------|------|-------|
| `primary` | Green-60 | Green-80 | Primary actions, key UI elements |
| `on-primary` | White | Green-20 | Text/icons on primary |
| `primary-container` | Green-90 | Green-30 | Containers with primary emphasis |
| `secondary` | Blue-50 | Blue-80 | Secondary actions |
| `tertiary` | Purple-60 | Purple-80 | Tertiary actions, accents |
| `error` | Red-60 | Red-80 | Errors, destructive actions |
| `surface` | Neutral-98 | Neutral-6 | Default background |
| `surface-variant` | Neutral-90 | Neutral-30 | Alternate backgrounds |
| `surface-container` | Neutral-94 | Neutral-12 | Card/container backgrounds |
| `outline` | Neutral-50 | Neutral-60 | Borders, dividers |

### Typography Scale

| Role | Size | Weight | Line Height | Usage |
|------|------|--------|-------------|-------|
| `display-large` | 57px | 400 | 64px | Hero text |
| `headline-medium` | 28px | 400 | 36px | Page titles |
| `title-large` | 22px | 500 | 28px | Section headers |
| `title-medium` | 16px | 500 | 24px | Subsection headers |
| `body-large` | 16px | 400 | 24px | Primary body text |
| `body-medium` | 14px | 400 | 20px | Secondary body text |
| `label-large` | 14px | 500 | 20px | Button labels |
| `label-small` | 11px | 500 | 16px | Captions, metadata |

### Accessibility (WCAG AA)

#### Contrast Requirements
- **Text < 18px**: Minimum 4.5:1 contrast
- **Text ≥ 18px**: Minimum 3:1 contrast
- **UI components**: Minimum 3:1 contrast

All M3 color roles are pre-validated for AA compliance.

#### Focus Indicators
- **Focus-visible rings**: 2px solid primary color, 2px offset
- Applied automatically via `:focus-visible` pseudo-class
- Keyboard navigation fully supported

#### Hit Targets
- Minimum 44×44px for interactive elements
- Buttons and chips meet this requirement by default

### Motion & Transitions

#### Duration Tokens
- `short1`: 50ms (micro-interactions)
- `short2`: 100ms (state changes)
- `medium1`: 250ms (component transitions)
- `medium2`: 300ms (layout shifts)
- `long1`: 400ms (page transitions)
- `long2`: 500ms (complex animations)

#### Easing Curves
- `standard`: General purpose
- `emphasized`: Expressive, attention-drawing
- `emphasized-decelerate`: Enter animations
- `emphasized-accelerate`: Exit animations

#### Usage Example
```css
.my-element {
    transition: all var(--md-sys-motion-duration-medium1) var(--md-sys-motion-easing-emphasized);
}
```

### Best Practices

#### 1. Use Semantic Color Roles
❌ **Don't:**
```python
st.markdown('<div style="background: #0E7B55;">...</div>')
```

✅ **Do:**
```python
st.markdown('<div style="background-color: var(--md-sys-color-primary);">...</div>')
```

#### 2. Use Typography Roles
❌ **Don't:**
```python
st.markdown('<h2 style="font-size: 28px; font-weight: 400;">Title</h2>')
```

✅ **Do:**
```python
st.markdown('<h2 class="md-typescale-headline-medium">Title</h2>')
```

#### 3. Maintain 8dp Grid
- Use spacing utilities: `md-spacing-xs` (4px), `md-spacing-sm` (8px), `md-spacing-md` (16px), `md-spacing-lg` (24px)
- Align elements to 8px grid for visual rhythm

#### 4. Elevation Hierarchy
- **Level 0**: Flat surfaces (default)
- **Level 1**: Cards, list items
- **Level 2**: App bars (scrolled), hover states
- **Level 3**: Modals, dialogs
- **Level 4**: Menus, tooltips
- **Level 5**: Dragged elements

### Customization

#### Changing the Seed Color
1. Edit `streamlit_app/styles/tokens.json` → `seedColor`
2. Regenerate tonal palettes (use Material Theme Builder or script)
3. Update light/dark color roles
4. Validate contrast ratios

#### Adding Custom Components
1. Define in `styles/m3.css` using tokens
2. Follow M3 component specs
3. Include all states (hover, focus, pressed, disabled)
4. Test in both light and dark themes

### Troubleshooting

#### Theme Not Applying
- Ensure `initialize_m3_theme()` is called after `st.set_page_config()`
- Check browser console for CSS loading errors
- Verify `styles/` directory exists and files are readable

#### Colors Look Wrong
- Confirm `data-theme` attribute is set on `<html>` element
- Check if custom CSS is overriding M3 tokens
- Validate token values in browser DevTools

#### Focus Rings Not Showing
- Ensure `:focus-visible` is supported (modern browsers)
- Check if other CSS is removing outlines
- Test with keyboard navigation (Tab key)

### Migration from Old UI

#### Step 1: Replace Custom CSS
Remove ad-hoc color values and replace with tokens:
```python
# Old
st.markdown('<div style="background: #1a1f2e; color: #e2e8f0;">...</div>')

# New
st.markdown('<div class="md-surface-container">...</div>')
```

#### Step 2: Update Typography
```python
# Old
st.markdown('<h1 style="font-size: 2rem; font-weight: bold;">Title</h1>')

# New
st.markdown('<h1 class="md-typescale-headline-medium">Title</h1>')
```

#### Step 3: Refactor Components
Use M3 card/chip/button classes instead of custom markup.

### Resources
- [Material Design 3 Guidelines](https://m3.material.io/)
- [Color System](https://m3.material.io/styles/color/overview)
- [Typography](https://m3.material.io/styles/typography/overview)
- [Elevation](https://m3.material.io/styles/elevation/overview)
- [Motion](https://m3.material.io/styles/motion/overview)

### Support
For questions or issues with the M3 theme system, consult:
1. This guide
2. `styles/tokens.json` for available tokens
3. `styles/m3.css` for component classes
4. `utils/theme.py` for theme utilities

---

**Version**: 0.7.0
**Last Updated**: 2025-01-13
**Maintained By**: PVCFC RAG Team
