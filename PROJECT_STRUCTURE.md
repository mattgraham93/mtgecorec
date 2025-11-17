
# MTG ECOREC Project Structure

```
mtgecorec/
├── core/                   # Core business logic
│   └── data_engine/        # Database and AI logic
├── static/                 # CSS, JS, images
├── templates/              # Jinja2 HTML templates
├── tests/                  # All test files
│   └── unit/               # Unit tests
├── scripts/                # Utility scripts and debug tools
├── notebooks/              # Jupyter notebooks for analysis
├── infra/                  # Infrastructure as Code (Bicep)
├── app.py                  # Main Flask application
├── run.py                  # Alternative entry point
├── requirements.txt        # Python dependencies
└── README.md               # Project documentation
```

## Key Changes Made:
- ✅ Moved all test_*.py files to tests/unit/
- ✅ Moved debug_*.py files to scripts/  
- ✅ Removed duplicate src/ directory and redundant mtgecorec/ nesting
- ✅ Cleaned up __pycache__ directories
- ✅ Removed empty directories (data/, docs/, tests/integration/)
- ✅ Fixed misplaced files (moved card_explore.html to templates/)
- ✅ Removed unused API blueprints and cleanup scripts
- ✅ Organized into clean, flat Python structure

## To Run:
```bash
python run.py
```
