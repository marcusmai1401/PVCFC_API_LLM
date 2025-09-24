# 🔧 Troubleshooting Guide - RAG Pipeline Streamlit Demo

## 🚨 Common Issues and Solutions

### 1. **App keeps restarting/crashing (Stop/Deploy flickering)**

**Symptoms:**
- The "Stop" button keeps appearing and disappearing
- App restarts repeatedly
- Console error: `preventOverflow` modifier warning

**Solutions:**

1. **Use the stable version:**
   ```bash
   streamlit run app_stable.py
   ```
   Or:
   ```bash
   python run_safe.py
   # Then choose option 1 (Stable version)
   ```

2. **Disable file watcher:**
   ```bash
   streamlit run app_stable.py --server.fileWatcherType none
   ```

3. **Clear Streamlit cache:**
   ```bash
   streamlit cache clear
   ```

4. **Use specific port:**
   ```bash
   streamlit run app_stable.py --server.port 8502
   ```

---

### 2. **Import Errors / Module Not Found**

**Solutions:**

1. **Install all dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Use virtual environment:**
   ```bash
   python -m venv venv
   venv\Scripts\activate  # On Windows
   pip install -r requirements.txt
   ```

3. **Check Python version:**
   ```bash
   python --version  # Should be 3.8 or higher
   ```

---

### 3. **JavaScript Console Errors**

**Error:** `preventOverflow` modifier is required by `hide` modifier

**Solutions:**

1. **Update Streamlit:**
   ```bash
   pip install streamlit==1.29.0
   ```

2. **Clear browser cache:**
   - Chrome: Ctrl+Shift+Delete
   - Firefox: Ctrl+Shift+Delete
   - Edge: Ctrl+Shift+Delete

3. **Try different browser:**
   - Chrome (recommended)
   - Firefox
   - Edge

---

### 4. **High Memory Usage / Slow Performance**

**Solutions:**

1. **Limit upload size:**
   Already configured in `.streamlit/config.toml`

2. **Run with resource limits:**
   ```bash
   streamlit run app_stable.py --server.maxUploadSize 50
   ```

3. **Use debug mode to identify issues:**
   ```bash
   streamlit run debug_app.py
   ```

---

### 5. **Session State Issues**

**Symptoms:**
- Data not persisting between pages
- Forms not working correctly

**Solutions:**

1. **Use app_stable.py** which has better session state handling

2. **Clear session state:**
   - Refresh the browser (F5)
   - Or restart the app

---

### 6. **File Upload Not Working**

**Solutions:**

1. **Check file size:**
   - Maximum: 200MB (configured)

2. **Check file type:**
   - Supported: JSON, JSONL, CSV, XLSX

3. **Use smaller test files first**

---

## 🚀 Quick Fixes

### **Reset Everything:**
```bash
# 1. Stop Streamlit (Ctrl+C)
# 2. Clear cache
streamlit cache clear

# 3. Reinstall dependencies
pip install -r requirements.txt --upgrade

# 4. Run stable version
python run_safe.py
```

### **Minimal Test:**
```bash
# Run debug script to check setup
streamlit run debug_app.py
```

### **Safe Mode:**
```bash
# Run with minimal features
streamlit run app_stable.py --server.fileWatcherType none --browser.gatherUsageStats false
```

---

## 📋 Recommended Setup

### **For Development:**
```bash
# 1. Create virtual environment
python -m venv venv
venv\Scripts\activate

# 2. Install exact versions
pip install -r requirements.txt

# 3. Run stable version
streamlit run app_stable.py
```

### **For Production:**
```bash
# Use specific configuration
streamlit run app_stable.py \
  --server.port 8501 \
  --server.fileWatcherType none \
  --server.maxUploadSize 200 \
  --browser.gatherUsageStats false
```

---

## 🔍 Diagnostic Commands

### **Check Installation:**
```python
python -c "import streamlit; print(streamlit.__version__)"
python -c "import pandas; print(pandas.__version__)"
python -c "import plotly; print(plotly.__version__)"
```

### **Check Port Availability:**
```bash
netstat -an | findstr :8501
```

### **Check Python Path:**
```python
python -c "import sys; print('\n'.join(sys.path))"
```

---

## 💡 Tips

1. **Always use `app_stable.py`** for production/demo
2. **Keep file uploads small** for testing (< 10MB)
3. **Use Chrome browser** for best compatibility
4. **Run from `streamlit_app` directory**
5. **Use virtual environment** to avoid conflicts

---

## 📞 Still Having Issues?

1. **Check the debug output:**
   ```bash
   streamlit run debug_app.py
   ```

2. **Run with verbose logging:**
   ```bash
   streamlit run app_stable.py --logger.level debug
   ```

3. **Check system resources:**
   - RAM usage
   - CPU usage
   - Disk space

4. **Try minimal example:**
   ```python
   # test.py
   import streamlit as st
   st.write("Hello World")
   ```
   ```bash
   streamlit run test.py
   ```

---

## ✅ Working Configuration

If everything else fails, use this exact setup:

```bash
# 1. Clean install
pip uninstall streamlit pandas plotly numpy -y
pip install streamlit==1.29.0 pandas==2.0.3 plotly==5.17.0 numpy==1.24.3

# 2. Run with specific settings
streamlit run app_stable.py \
  --server.port 8501 \
  --server.fileWatcherType none \
  --server.maxUploadSize 200 \
  --browser.gatherUsageStats false \
  --server.headless true
```

This configuration has been tested and works reliably!
