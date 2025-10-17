# iOS/macOS UI - Testing Guide

**Version**: 0.8.0
**Theme**: iOS/macOS Light Mode
**Date**: 2025-10-16

---

## 🚀 Quick Start

### 1. Start the Application

```powershell
# Navigate to project directory
cd "C:\Users\Admin\Desktop\Code - API_LLM_PVCFC"

# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Start Streamlit
streamlit run streamlit_app/app.py
```

The app should open in your browser at `http://localhost:8501`

---

## ✅ Visual Checklist

### Global Appearance

**Background**:
- [ ] Light gradient background (subtle #f5f5f7 to #fafafa)
- [ ] Clean, airy feel
- [ ] No dark colors

**Sidebar**:
- [ ] Frosted glass effect (semi-transparent with blur)
- [ ] Subtle border on right side
- [ ] "PVCFC RAG" title without emoji
- [ ] "Document Intelligence" subtitle in gray
- [ ] Clean navigation buttons
- [ ] Status dot with glow effect
- [ ] Footer with v0.8.0 and "iOS/macOS Design"

**Scrollbar**:
- [ ] Thin, minimalist scrollbar (8px)
- [ ] Transparent track
- [ ] Gray thumb that darkens on hover

---

### Home Page

**Hero Card**:
- [ ] Centered frosted glass card
- [ ] "PVCFC RAG System" in large, bold text
- [ ] Subtitle in gray
- [ ] Subtle shadow around card
- [ ] Hover effect: card lifts up slightly

**System Status**:
- [ ] "System Status" header in iOS card
- [ ] Four metric cards in a row (Status, Environment, Version, Uptime)
- [ ] Cards have frosted glass effect
- [ ] Centered text alignment
- [ ] Proper color coding (green for healthy)

---

### RAG Query Page

**Header**:
- [ ] "Ask a Question" centered in frosted glass card
- [ ] Subtitle in gray
- [ ] Clean, no emojis

**Query Input**:
- [ ] "YOUR QUESTION" label (uppercase, small, gray)
- [ ] Clean textarea with subtle border
- [ ] Border turns blue on focus
- [ ] 4px blue glow ring on focus
- [ ] Placeholder text visible and gray

**Configuration Section**:
- [ ] "Configuration" header in card
- [ ] Three columns: Language, Context Chunks, Active Features
- [ ] Language buttons (Vietnamese/English without flags)
- [ ] Selected button has blue background
- [ ] Number input for context chunks
- [ ] Active Features compact card

**Advanced Options**:
- [ ] Expander with clean disclosure style
- [ ] "P&ID Tag Filter" section
- [ ] "Citation Format" section
- [ ] "System Information" compact card
- [ ] Clean dividers between sections

**Run Button**:
- [ ] "Run Query" text (no rocket emoji)
- [ ] Blue gradient (lighter at top, darker at bottom)
- [ ] Shadow underneath
- [ ] Hover: scales up 2%, shadow increases
- [ ] Click: scales down to 98%
- [ ] Full width button

---

### Results Display

**Results Header**:
- [ ] "Results" in flat iOS card
- [ ] Proper spacing above and below

**Tabs**:
- [ ] Seven tabs: Overview, Retrieval, Rerank, Generation, Vision, Metrics, Raw Data
- [ ] Tabs in frosted glass container
- [ ] Selected tab: white background with shadow
- [ ] Unselected tabs: transparent, gray text
- [ ] Hover: slight gray background
- [ ] Smooth transitions between tabs

**Overview Tab - Metrics**:
- [ ] Three metric cards in a row
- [ ] **Confidence**:
  - Green if > 70%
  - Orange if > 50%
  - Red if ≤ 50%
  - Large number, centered
- [ ] **Citations**:
  - Blue color
  - Number of citations
- [ ] **Latency**:
  - Green if < 3s
  - Orange if < 5s
  - Red if ≥ 5s
  - Shows "ms" suffix

**Overview Tab - Answer**:
- [ ] Clean markdown rendering
- [ ] IEEE-style citations if enabled: [1], [2], etc.
- [ ] Proper text formatting

**Overview Tab - References**:
- [ ] "References" header
- [ ] "View Panel" button to open side sheet
- [ ] Each reference with citation number
- [ ] File name displayed
- [ ] Page numbers with links (if available)
- [ ] "View Page" buttons

---

## 🎨 Style Verification

### Glassmorphism Effects

**Test**: Open Developer Tools → Inspect a card

**Should see**:
```css
background: rgba(255, 255, 255, 0.7);
backdrop-filter: blur(20px) saturate(180%);
-webkit-backdrop-filter: blur(20px) saturate(180%);
```

**Browser Support**:
- Chrome/Edge: Full support
- Safari: Full support (webkit prefix)
- Firefox 103+: Full support

**Fallback**: If blur not supported, cards show as solid white (still functional)

---

### Hover Effects

**Test each interactive element**:

1. **Cards**:
   - Hover over hero card
   - Should lift 2-4px
   - Shadow should increase
   - Smooth transition (0.3s)

2. **Buttons**:
   - Hover over "Run Query"
   - Should scale to 1.02x
   - Shadow should intensify
   - Click: should scale to 0.98x
   - Smooth (0.2s)

3. **Tabs**:
   - Hover over unselected tab
   - Should show light gray background
   - Selected tab should have white bg + shadow

4. **Citations** (if available):
   - Hover over citation card
   - Should slide right 4px
   - Blue border should darken
   - Shadow increases

---

### Typography Check

**Inspect any text element**:

**Font Family Should Be**:
```
Inter, -apple-system, BlinkMacSystemFont,
SF Pro Display, SF Pro Text, Helvetica Neue, sans-serif
```

**Letter Spacing**:
- Large titles: -0.8px to -1.5px (tight)
- Body: -0.2px to -0.3px
- Captions: -0.1px

**Weights**:
- Display/Large Titles: 700 (bold)
- Titles: 600 (semibold)
- Body: 400 (regular)
- All have proper anti-aliasing

---

### Color Accuracy

**Primary Blue**: `#007aff`
- Run Query button
- Selected tab indicators
- Citations count
- Links

**Success Green**: `#34c759`
- High confidence (>70%)
- Healthy status
- Fast latency (<3s)

**Warning Orange**: `#ff9500`
- Medium confidence (50-70%)
- Medium latency (3-5s)

**Error Red**: `#ff3b30`
- Low confidence (<50%)
- Slow latency (>5s)
- Error states

**Gray Hierarchy**:
- Text: `#1d1d1f` (almost black)
- Secondary: `#86868b` (iOS gray)
- Surfaces: `#f5f5f7`, `#fafafa`, `#ffffff`

---

## 🐛 Known Issues & Limitations

### Browser Compatibility

**Optimal Experience**:
- Chrome 76+
- Edge 79+
- Safari 9+
- Firefox 103+

**Degraded Experience** (older browsers):
- No blur effects (solid cards instead)
- Standard shadows instead of layered
- Still fully functional

### Streamlit Limitations

**Cannot fully override**:
- Some widget internal padding
- Radio button inner circles (might show default blue)
- Some hover states on native widgets

**Workarounds Applied**:
- Used `!important` flags
- Targeted deep selectors
- Custom HTML/CSS where needed

---

## 📱 Testing on Different Screen Sizes

### Desktop (1920x1080)
- [ ] Cards should be max 1200px wide
- [ ] Generous whitespace on sides
- [ ] All elements easily clickable

### Laptop (1366x768)
- [ ] Layout should adapt
- [ ] Cards still readable
- [ ] No horizontal scrolling

### Tablet (768px)
- [ ] Sidebar should auto-collapse
- [ ] Single column layout
- [ ] Touch-friendly targets (44px minimum)

---

## 🎯 User Acceptance Criteria

### Visual Quality
- [ ] Design looks clean and professional
- [ ] Frosted glass effects visible
- [ ] Colors match iOS palette
- [ ] Typography feels polished
- [ ] Spacing is generous and consistent

### Interactions
- [ ] Hover states responsive and smooth
- [ ] Buttons provide tactile feedback
- [ ] Transitions feel natural (not too fast/slow)
- [ ] Focus states clearly visible

### Functionality
- [ ] All features still work
- [ ] No console errors
- [ ] Forms submit correctly
- [ ] Results display properly
- [ ] Citations render correctly

### Performance
- [ ] Page loads quickly (<2s)
- [ ] Animations smooth (60fps)
- [ ] No lag on interactions
- [ ] Blur effects don't slow down scrolling

---

## 🔍 Debugging

### If Styles Don't Apply

**1. Clear Browser Cache**:
```
Ctrl + Shift + Delete → Clear cached images and files
```

**2. Hard Refresh**:
```
Ctrl + Shift + R (Windows)
Cmd + Shift + R (Mac)
```

**3. Check Developer Tools**:
```
F12 → Elements tab → Inspect element
Verify CSS classes are present
Check if styles are being overridden
```

**4. Restart Streamlit**:
```powershell
# Stop: Ctrl + C
# Start again:
streamlit run streamlit_app/app.py
```

### If Blur Effects Missing

**Check Browser Support**:
```javascript
// In browser console:
CSS.supports('backdrop-filter', 'blur(20px)')
// Should return: true
```

**Fallback**: Cards will show as solid white if blur not supported.

---

## 📊 Performance Verification

### Load Time
- **Target**: < 2 seconds for initial page load
- **Actual**: Test with browser DevTools Network tab

### Animation FPS
- **Target**: 60fps for all transitions
- **Test**: DevTools → Performance → Record interactions

### Memory Usage
- **Target**: < 150MB for UI
- **Test**: DevTools → Memory tab

---

## 🎨 Design Comparison

### Side-by-Side Test

**Open in two browser windows**:
1. Production UI (before redesign)
2. New iOS UI (current)

**Compare**:
- Color: Dark vs Light
- Cards: Solid vs Frosted glass
- Spacing: Compact vs Airy
- Typography: Standard vs Tight tracking
- Buttons: Material vs iOS gradient
- Overall: Technical vs Premium

---

## ✅ Final Checklist

Before declaring success, verify:

- [ ] Home page loads with iOS styling
- [ ] Sidebar has frosted glass effect
- [ ] Navigation works (Home / RAG Query)
- [ ] Query input accepts text
- [ ] Configuration controls work
- [ ] Run Query button functional
- [ ] Results display correctly
- [ ] Metrics show with proper colors
- [ ] Citations render properly
- [ ] All hover effects work
- [ ] No console errors
- [ ] No linter errors
- [ ] Performance is good

**If all checked → Success! 🎉**

---

## 🆘 Rollback Instructions

If you need to revert to old design:

```powershell
# Restore from git
git checkout streamlit_app/styles/tokens.css
git checkout streamlit_app/styles/m3.css
git checkout streamlit_app/app.py
git checkout streamlit_app/components/system_status.py
git checkout streamlit_app/components/query_lab_improved.py

# Restart Streamlit
streamlit run streamlit_app/app.py
```

---

**Testing completed**: __________
**Tested by**: __________
**Issues found**: __________
**Status**: ✅ Approved / ⚠️ Needs work / ❌ Rejected
