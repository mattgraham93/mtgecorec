"""
auth_decorators.py - Authentication decorators and session management

This module provides Flask decorators and utilities for protecting routes
and managing user sessions.
"""

import functools
from flask import session, request, jsonify, redirect, url_for, flash
from core.data_engine.user_manager import UserManager

# Create a global user manager instance
user_manager = UserManager()


def login_required(f):
    """Decorator to require user login for a route."""
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            if request.is_json:
                return jsonify({'error': 'Authentication required', 'login_required': True}), 401
            flash('Please log in to access this feature.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def ai_query_required(f):
    """Decorator to check if user can make AI queries."""
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            if request.is_json:
                return jsonify({'error': 'Authentication required', 'login_required': True}), 401
            flash('Please log in to access AI features.', 'warning')
            return redirect(url_for('login'))
        
        user_id = session['user_id']
        query_check = user_manager.can_make_ai_query(user_id)
        
        if not query_check['allowed']:
            if request.is_json:
                return jsonify({
                    'error': query_check['reason'],
                    'quota_exceeded': True,
                    'reset_date': query_check.get('reset_date')
                }), 429
            flash(f"AI Query Limit Exceeded: {query_check['reason']}", 'error')
            return redirect(url_for('commander_deck_builder'))
        
        # Store remaining queries in request context for display
        request.remaining_queries = query_check.get('remaining_queries', 0)
        
        return f(*args, **kwargs)
    return decorated_function


def get_current_user():
    """Get current authenticated user."""
    if 'user_id' not in session:
        return None
    return user_manager.get_user_by_id(session['user_id'])


def increment_user_query_count():
    """Increment the current user's AI query count."""
    if 'user_id' in session:
        return user_manager.increment_ai_query_count(session['user_id'])
    return False