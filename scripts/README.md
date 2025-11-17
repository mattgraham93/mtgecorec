# Scripts Directory

This directory contains utility scripts for the MTG Card Explorer project.

## Files

- `convert_notebook.py`: Converts the Jupyter notebook (`notebooks/card_explore.ipynb`) to HTML format for web display. The HTML is saved to `static/card_explore.html` and served via the `/analysis` route in the Flask app.

## Usage

### Command Line
```bash
python scripts/convert_notebook.py
```

### From Flask App
Visit `/regenerate-analysis` endpoint to regenerate the HTML from the web interface.

### From Notebook
The notebook imports and runs the conversion function automatically in its last cell.