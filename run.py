#!/usr/bin/env python3
"""
MTG ECOREC - Magic: The Gathering Economic Recommendation Engine
Main Flask application entry point.
"""

from app import app

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)