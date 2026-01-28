"""
Data engine module for MTG ECOREC containing database drivers, AI clients, and data processing logic.
"""

# Import new Phase 2 scoring engine (optional, loaded only if available)
try:
    from .card_scoring import CardScorer
except ImportError:
    CardScorer = None

try:
    from .scoring_adapter import ScoringAdapter
except ImportError:
    ScoringAdapter = None
