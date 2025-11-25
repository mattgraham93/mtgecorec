"""
user_manager.py - User authentication and management for MTG EcoRec

This module provides user registration, authentication, and session management
for protecting access to AI-powered features.
"""

import os
import hashlib
import secrets
import datetime
from typing import Optional, Dict, Any
from pymongo.errors import DuplicateKeyError
from core.data_engine.cosmos_driver import get_mongo_client, get_collection


class User:
    """User model for authentication system."""
    
    def __init__(self, username: str, email: str, password_hash: str, 
                 created_at: datetime.datetime = None, user_id: str = None):
        self.user_id = user_id or secrets.token_hex(16)
        self.username = username
        self.email = email
        self.password_hash = password_hash
        self.created_at = created_at or datetime.datetime.utcnow()
        self.is_active = True
        self.last_login = None
        self.ai_queries_count = 0
        self.ai_queries_limit = int(os.environ.get('AI_QUERIES_LIMIT', '50'))  # Monthly limit
        self.queries_reset_date = self._get_next_reset_date()
    
    def _get_next_reset_date(self):
        """Calculate next monthly reset date."""
        now = datetime.datetime.utcnow()
        if now.month == 12:
            return datetime.datetime(now.year + 1, 1, 1)
        else:
            return datetime.datetime(now.year, now.month + 1, 1)
    
    def to_dict(self):
        """Convert user to dictionary for database storage."""
        return {
            'user_id': self.user_id,
            'username': self.username,
            'email': self.email,
            'password_hash': self.password_hash,
            'created_at': self.created_at,
            'is_active': self.is_active,
            'last_login': self.last_login,
            'ai_queries_count': self.ai_queries_count,
            'ai_queries_limit': self.ai_queries_limit,
            'queries_reset_date': self.queries_reset_date
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        """Create User instance from database document."""
        user = cls(
            username=data['username'],
            email=data['email'],
            password_hash=data['password_hash'],
            created_at=data.get('created_at'),
            user_id=data.get('user_id')
        )
        user.is_active = data.get('is_active', True)
        user.last_login = data.get('last_login')
        user.ai_queries_count = data.get('ai_queries_count', 0)
        user.ai_queries_limit = data.get('ai_queries_limit', 50)
        user.queries_reset_date = data.get('queries_reset_date', user._get_next_reset_date())
        return user


class UserManager:
    """Handles user authentication and management operations."""
    
    def __init__(self):
        self.client = get_mongo_client()
        self.collection = get_collection(self.client, 'users', 'mtgecorec_users')
        # Create unique indexes for username and email
        self._create_indexes()
    
    def _create_indexes(self):
        """Create database indexes for efficient queries."""
        try:
            self.collection.create_index("username", unique=True)
            self.collection.create_index("email", unique=True)
            self.collection.create_index("user_id", unique=True)
        except Exception as e:
            print(f"Index creation note: {e}")  # May already exist
    
    def hash_password(self, password: str) -> str:
        """Hash a password with salt for secure storage."""
        # Generate a random salt
        salt = secrets.token_hex(32)
        # Hash password with salt
        password_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
        # Return salt + hash for storage
        return salt + password_hash.hex()
    
    def verify_password(self, password: str, stored_hash: str) -> bool:
        """Verify a password against its stored hash."""
        try:
            # Extract salt (first 64 characters) and hash
            salt = stored_hash[:64]
            stored_password_hash = stored_hash[64:]
            # Hash provided password with same salt
            password_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
            return password_hash.hex() == stored_password_hash
        except Exception:
            return False
    
    def register_user(self, username: str, email: str, password: str) -> Dict[str, Any]:
        """Register a new user."""
        try:
            # Validate input
            if not username or len(username.strip()) < 3:
                return {'success': False, 'error': 'Username must be at least 3 characters long'}
            
            if not email or '@' not in email:
                return {'success': False, 'error': 'Valid email address is required'}
            
            if not password or len(password) < 6:
                return {'success': False, 'error': 'Password must be at least 6 characters long'}
            
            # Create user
            user = User(
                username=username.strip(),
                email=email.strip().lower(),
                password_hash=self.hash_password(password)
            )
            
            # Insert into database
            self.collection.insert_one(user.to_dict())
            
            return {
                'success': True,
                'user_id': user.user_id,
                'message': 'User registered successfully'
            }
            
        except DuplicateKeyError as e:
            if 'username' in str(e):
                return {'success': False, 'error': 'Username already exists'}
            elif 'email' in str(e):
                return {'success': False, 'error': 'Email already registered'}
            else:
                return {'success': False, 'error': 'User already exists'}
        except Exception as e:
            print(f"Registration error: {e}")
            return {'success': False, 'error': 'Registration failed. Please try again.'}
    
    def authenticate_user(self, username: str, password: str) -> Dict[str, Any]:
        """Authenticate a user login."""
        try:
            # Find user by username or email
            user_doc = self.collection.find_one({
                '$or': [
                    {'username': username},
                    {'email': username.lower()}
                ]
            })
            
            if not user_doc:
                return {'success': False, 'error': 'Invalid username or password'}
            
            user = User.from_dict(user_doc)
            
            if not user.is_active:
                return {'success': False, 'error': 'Account is disabled'}
            
            if not self.verify_password(password, user.password_hash):
                return {'success': False, 'error': 'Invalid username or password'}
            
            # Update last login
            self.collection.update_one(
                {'user_id': user.user_id},
                {'$set': {'last_login': datetime.datetime.utcnow()}}
            )
            
            return {
                'success': True,
                'user': user.to_dict(),
                'message': 'Login successful'
            }
            
        except Exception as e:
            print(f"Authentication error: {e}")
            return {'success': False, 'error': 'Authentication failed. Please try again.'}
    
    def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Get user by ID."""
        try:
            user_doc = self.collection.find_one({'user_id': user_id})
            if user_doc:
                return User.from_dict(user_doc)
            return None
        except Exception as e:
            print(f"Error fetching user: {e}")
            return None
    
    def can_make_ai_query(self, user_id: str) -> Dict[str, Any]:
        """Check if user can make an AI query."""
        user = self.get_user_by_id(user_id)
        if not user:
            return {'allowed': False, 'reason': 'User not found'}
        
        # Reset counter if it's a new month
        now = datetime.datetime.utcnow()
        if now >= user.queries_reset_date:
            self.collection.update_one(
                {'user_id': user_id},
                {
                    '$set': {
                        'ai_queries_count': 0,
                        'queries_reset_date': user._get_next_reset_date()
                    }
                }
            )
            user.ai_queries_count = 0
        
        if user.ai_queries_count >= user.ai_queries_limit:
            return {
                'allowed': False,
                'reason': f'Monthly AI query limit ({user.ai_queries_limit}) reached',
                'reset_date': user.queries_reset_date
            }
        
        return {
            'allowed': True,
            'remaining_queries': user.ai_queries_limit - user.ai_queries_count
        }
    
    def increment_ai_query_count(self, user_id: str) -> bool:
        """Increment user's AI query count."""
        try:
            result = self.collection.update_one(
                {'user_id': user_id},
                {'$inc': {'ai_queries_count': 1}}
            )
            return result.modified_count > 0
        except Exception as e:
            print(f"Error incrementing query count: {e}")
            return False
    
    def get_user_stats(self, user_id: str) -> Dict[str, Any]:
        """Get user statistics."""
        user = self.get_user_by_id(user_id)
        if not user:
            return {'error': 'User not found'}
        
        query_check = self.can_make_ai_query(user_id)
        
        return {
            'username': user.username,
            'email': user.email,
            'member_since': user.created_at,
            'last_login': user.last_login,
            'ai_queries_used': user.ai_queries_count,
            'ai_queries_limit': user.ai_queries_limit,
            'ai_queries_remaining': query_check.get('remaining_queries', 0),
            'queries_reset_date': user.queries_reset_date
        }


if __name__ == '__main__':
    # Test the user manager
    print("Testing User Manager...")
    
    user_manager = UserManager()
    
    # Test registration
    result = user_manager.register_user('testuser', 'test@example.com', 'password123')
    print(f"Registration result: {result}")
    
    # Test authentication
    if result['success']:
        auth_result = user_manager.authenticate_user('testuser', 'password123')
        print(f"Authentication result: {auth_result}")
        
        if auth_result['success']:
            user_id = auth_result['user']['user_id']
            stats = user_manager.get_user_stats(user_id)
            print(f"User stats: {stats}")