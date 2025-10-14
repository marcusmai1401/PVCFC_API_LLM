# PVCFC RAG Streamlit UI

Material Design 3 (Expressive) themed interface for the PVCFC RAG system.

## Quick Start

### Running the UI

```powershell
# From project root
.\launchers\start_ui.ps1
```

The UI will be available at `http://localhost:8502`

### Prerequisites
- Python 3.9+
- Virtual environment with dependencies installed
- Backend API running at `http://localhost:8000` (or configured URL)

## Features

- **🏠 Home**: System status dashboard with health checks and index statistics
- **🔬 RAG QA**: Interactive query interface with:
  - Material Design 3 styled components
  - Real-time query execution
  - **Citation side sheet** with PDF page viewer
  - **Material Symbols** icons (35+ icons)
  - Performance metrics visualization
  - Light/Dark/System theme support

## Architecture

### File Structure
```
streamlit_app/
├── app.py                      # Main application entry point
├── components/
│   ├── query_lab_improved.py   # RAG QA interface (M3 styled)
│   ├── system_status.py        # System health component
│   └── side_sheet.py           # Citation side sheet modal (NEW)
├── styles/
│   ├── tokens.json             # M3 design tokens (colors, typography, etc.)
│   ├── tokens.css              # CSS variables from tokens
│   ├── m3.css                  # M3 component styles
│   └── material-symbols.css    # Material Symbols icons (NEW)
├── utils/
│   └── theme.py                # Theme management utilities
├── tests/
│   └── test_ui_smoke.py        # Automated smoke tests
├── M3_THEMING_GUIDE.md         # Comprehensive theming documentation
├── M3_FINAL_FEATURES.md        # Final feature summary (NEW)
└── README.md                   # This file
```

### Theme System

The UI uses Material Design 3 (Material You) with:
- **Seed Color**: `#0E7B55` (PVCFC brand green)
- **Light/Dark Themes**: Automatic tonal palette generation
- **Typography Scale**: 15 semantic type roles
- **Component Library**: Buttons, Cards, Chips, Text Fields, Side Sheets
- **Icon System**: Material Symbols (35+ icons, multiple sizes/weights)
- **Accessibility**: WCAG AA compliant (4.5:1 contrast for text)

See [M3_THEMING_GUIDE.md](./M3_THEMING_GUIDE.md) for detailed documentation.

## Configuration

### Environment Variables
- `PVCFC_API_BASE_URL`: Backend API endpoint (default: `http://127.0.0.1:8000`)
- `API_BASE_URL`: Alternative API endpoint variable

### Runtime Configuration
- **API URL**: Configurable in sidebar
- **Theme**: Light/Dark/System (persisted in session)
- **Language**: Vietnamese/English toggle

## Development

### Adding New Components

1. **Use M3 Tokens**:
```python
st.markdown('''
<div class="md-card md-card-elevated md-spacing-md">
    <h2 class="md-typescale-title-large">Component Title</h2>
    <p class="md-typescale-body-medium">Component content</p>
</div>
''', unsafe_allow_html=True)
```

2. **Follow Typography Scale**:
- `headline-medium`: Page titles
- `title-large`: Section headers
- `body-large`: Primary content
- `label-large`: Button/chip labels

3. **Use Semantic Colors**:
- `--md-sys-color-primary`: Primary actions
- `--md-sys-color-surface-container`: Card backgrounds
- `--md-sys-color-on-surface`: Text on surfaces

### Testing

Run the UI smoke test:
```bash
python streamlit_app/tests/test_ui_smoke.py
```

Tests:
- Theme initialization
- API connectivity
- Basic query execution
- Component rendering

### Debugging

Enable verbose logging in sidebar settings or set:
```python
st.session_state.enable_verbose_logging = True
```

Logs are written to `logs/ui_events/` with structured JSON format.

## Troubleshooting

### Theme Not Loading
- Ensure `styles/` directory exists with `tokens.css` and `m3.css`
- Check browser console for CSS loading errors
- Verify `initialize_m3_theme()` is called after `st.set_page_config()`

### API Connection Issues
- Verify backend is running: `http://localhost:8000/healthz`
- Check API URL in sidebar configuration
- Review launcher script output for connection test results

### Dark Theme Issues
- Confirm `data-theme="dark"` attribute on `<html>` element
- Check if custom CSS is overriding M3 tokens
- Try system theme detection: Settings → Theme → System

## Performance

### Optimization Tips
- Use `@st.cache_data` for expensive computations
- Minimize st.rerun() calls
- Lazy-load heavy components (PDF viewer, charts)
- Enable query result caching in backend

### Metrics
- Typical page load: < 1s
- Query execution: 2-5s (depends on backend)
- Theme switch: < 100ms

## Accessibility

- **Keyboard Navigation**: Full support (Tab, Enter, Escape)
- **Focus Indicators**: 2px visible rings on all interactive elements
- **Screen Readers**: Semantic HTML with ARIA labels
- **Contrast**: WCAG AA compliant (4.5:1 for text, 3:1 for UI)
- **Hit Targets**: Minimum 44×44px for buttons/chips

## Browser Support

- **Chrome/Edge**: 90+ (recommended)
- **Firefox**: 88+
- **Safari**: 14+

Requires modern CSS support (CSS variables, oklch colors, :focus-visible).

## Deployment

### Production Checklist
- [ ] Set `PVCFC_API_BASE_URL` to production API
- [ ] Disable debug features (verbose logging, dev tools)
- [ ] Test theme switching in both modes
- [ ] Validate API connectivity
- [ ] Run smoke tests
- [ ] Check browser console for errors

### Docker
```dockerfile
# In Dockerfile
COPY streamlit_app /app/streamlit_app
WORKDIR /app
CMD ["streamlit", "run", "streamlit_app/app.py", "--server.port=8502"]
```

## Contributing

### Code Style
- Follow M3 design system guidelines
- Use semantic color roles (not hex values)
- Apply typography scale consistently
- Include focus-visible states
- Test in both light and dark themes

### Pull Request Checklist
- [ ] M3 tokens used (no hardcoded colors)
- [ ] Typography roles applied
- [ ] Accessibility validated (contrast, focus, keyboard)
- [ ] Tested in light and dark themes
- [ ] Documentation updated
- [ ] Smoke tests pass

## Resources

- [Material Design 3](https://m3.material.io/)
- [Material Symbols](https://fonts.google.com/icons)
- [Streamlit Documentation](https://docs.streamlit.io/)
- [M3 Theming Guide](./M3_THEMING_GUIDE.md)
- [M3 Final Features](./M3_FINAL_FEATURES.md)
- [PVCFC RAG API Docs](../README.md)

## Support

For issues or questions:
1. Check [M3_THEMING_GUIDE.md](./M3_THEMING_GUIDE.md)
2. Review browser console for errors
3. Check `logs/ui_events/` for detailed logs
4. Consult backend API logs if query issues persist

---

**Version**: 0.7.0
**License**: Internal Use
**Maintained By**: PVCFC RAG Team
