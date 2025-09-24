# 🚀 RAG Pipeline Demo & Annotation Tool

An interactive Streamlit application for testing RAG queries, creating evaluation datasets, and analyzing pipeline performance.

## 🌟 Features

### 🔍 **RAG Demo**
- Interactive query testing with real-time responses
- Detailed pipeline visualization showing retrieval and generation steps
- Performance metrics and timing breakdowns
- Citation analysis and quality scoring
- Configurable model parameters and settings

### ✏️ **Data Annotation**
- Create and edit QA pairs for evaluation datasets
- Quality validation and scoring system
- Bulk import/export in multiple formats (JSON, JSONL, CSV, Excel)
- Advanced filtering and search capabilities
- Data quality assessment and cleanup tools

### 📊 **Evaluation Results**
- Interactive dashboards with performance metrics
- Detailed analysis with filtering and comparison tools
- Results browser for individual query inspection
- Trend analysis and performance tracking
- Export capabilities for further analysis

### ⚙️ **Configuration**
- Model settings (GPT-4, Claude, Gemini, etc.)
- Retrieval configuration (vector DB, embeddings, HyDE, reranking)
- Evaluation criteria and thresholds
- Preset configurations for different use cases
- Import/export configuration files

### 📁 **Data Management**
- Dataset validation and cleaning utilities
- Document collection management
- Batch operations for large-scale processing
- Backup and restore functionality
- Integration with popular benchmark datasets

## 🚀 Quick Start

### Prerequisites
- Python 3.8 or higher
- Required packages listed in `requirements.txt`

### Installation

1. **Clone or download the project**
   ```bash
   git clone <repository-url>
   cd streamlit_app
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the application**
   ```bash
   streamlit run app.py
   ```

4. **Open your browser**
   Navigate to `http://localhost:8501` to access the demo.

## 📖 Usage Guide

### 🏠 Home Page
- Overview of all features and capabilities
- Quick statistics and system status
- Navigation to different modules

### 🔍 Using the RAG Demo
1. Navigate to the "RAG Demo" tab
2. Configure model settings in the sidebar
3. Enter your query in the text area
4. Click "Generate Answer" to see results
5. Explore the detailed tabs for process breakdown

### ✏️ Creating Annotations
1. Go to the "Data Annotation" tab
2. Fill in the QA pair creation form
3. Use validation tools to ensure quality
4. Export your dataset when ready

### 📊 Viewing Evaluation Results
1. Upload evaluation results in the "Evaluation Results" tab
2. Use the dashboard for quick insights
3. Explore detailed analysis with filters
4. Compare different evaluation runs

### ⚙️ Configuration Management
1. Visit the "Configuration" tab
2. Adjust model and retrieval settings
3. Save configurations for later use
4. Use presets for common scenarios

## 🏗️ Architecture

### Directory Structure
```
streamlit_app/
├── app.py                 # Main application entry point
├── components/            # UI components
│   ├── rag_demo.py       # RAG testing interface
│   ├── annotation.py     # Data annotation tools
│   ├── evaluation_results.py  # Results analysis
│   ├── configuration.py  # Settings management
│   └── data_management.py # Data utilities
├── utils/                # Utility functions (future)
├── data/                 # Sample data files
├── requirements.txt      # Python dependencies
└── README.md            # This file
```

### Key Components

- **Main App**: Navigation and layout management
- **RAG Demo**: Interactive testing with mock pipeline simulation
- **Annotation**: QA pair creation and dataset management
- **Evaluation Results**: Performance analysis and visualization
- **Configuration**: Settings management with presets
- **Data Management**: Import/export and data utilities

## 🎯 Use Cases

### For Developers
- Test RAG queries interactively
- Debug pipeline performance issues
- Compare different configuration settings
- Create evaluation datasets efficiently

### For Researchers
- Analyze evaluation results comprehensively
- Compare different RAG approaches
- Create benchmark datasets
- Export data for research publications

### For Product Teams
- Demonstrate RAG capabilities to stakeholders
- Create training datasets for specific domains
- Monitor pipeline performance over time
- Configure systems for different use cases

## 🔧 Customization

### Adding New Components
1. Create a new Python file in `components/`
2. Implement the main interface function
3. Import and integrate in `app.py`
4. Add navigation entry in the sidebar

### Extending Data Formats
- Modify import/export functions in `data_management.py`
- Add new format options to UI components
- Update validation logic as needed

### Custom Evaluation Metrics
- Extend evaluation result analysis in `evaluation_results.py`
- Add new metric calculations and visualizations
- Update export formats to include new metrics

## 📋 Requirements

### Core Dependencies
- `streamlit`: Web app framework
- `pandas`: Data manipulation and analysis
- `plotly`: Interactive visualizations
- `numpy`: Numerical computing
- `python-dateutil`: Date/time utilities

### Optional Dependencies
For full RAG pipeline integration:
- OpenAI API client
- Vector database libraries (ChromaDB, Pinecone, etc.)
- Embedding model libraries
- Document processing libraries

## 🐛 Troubleshooting

### Common Issues

**Application won't start:**
- Check Python version (3.8+)
- Ensure all dependencies are installed
- Verify port 8501 is available

**Import errors:**
- Make sure you're in the correct directory
- Check that all required packages are installed
- Try reinstalling dependencies

**Performance issues:**
- Large datasets may cause slowdowns
- Consider using sampling for initial testing
- Monitor system resources

### Getting Help

1. Check the console output for error messages
2. Verify all dependencies are properly installed
3. Ensure you have the latest version of Streamlit
4. Check the GitHub issues page for known problems

## 🚀 Deployment

### Local Development
```bash
streamlit run app.py
```

### Streamlit Cloud
1. Push code to GitHub repository
2. Connect to Streamlit Cloud
3. Deploy directly from the repository

### Docker Deployment
Create a `Dockerfile`:
```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 8501
CMD ["streamlit", "run", "app.py"]
```

## 📄 License

This project is part of the RAG Pipeline evaluation framework. Please refer to the main project license for terms of use.

## 🤝 Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## 📞 Support

For issues, questions, or feature requests:
- Open an issue on GitHub
- Check existing documentation
- Review troubleshooting section above

---

**Happy RAG Testing!** 🎉
