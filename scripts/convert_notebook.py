#!/usr/bin/env python3
import os
import nbconvert
import nbformat

def convert_notebook_to_html():
    """
    Convert the card_explore.ipynb notebook to HTML for web display.
    """
    # Get the project root directory (parent of scripts/)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)

    # Paths
    notebook_path = os.path.join(project_root, 'notebooks', 'card_explore.ipynb')
    html_output_path = os.path.join(project_root, 'static', 'card_explore.html')

    # Read the notebook
    with open(notebook_path, 'r', encoding='utf-8') as f:
        nb = nbformat.read(f, as_version=4)

    # Convert to HTML
    html_exporter = nbconvert.HTMLExporter()
    html_exporter.exclude_input_prompt = True
    html_exporter.exclude_output_prompt = True

    (body, resources) = html_exporter.from_notebook_node(nb)

    # Write to static directory
    with open(html_output_path, 'w', encoding='utf-8') as f:
        f.write(body)

    print("Notebook converted to HTML and saved to static/card_explore.html")

if __name__ == '__main__':
    convert_notebook_to_html()