#!/usr/bin/env python3
"""
Token-based authentication and encryption for AI Service
Simple, secure, no user accounts - perfect for local use with future expansion
"""
import os
import sys
import jwt
import secrets
import hashlib
from datetime import datetime, timedelta
from cryptography.fernet import Fernet
from typing import Optional, Dict, Any
from functools import wraps
from flask import request, jsonify, current_app

# Import project-wide ErrorLogger
sys.path.append('/home/administrator/gitcontrol/User_Functionality_WSL/projects')
from ErrorLogger.logger import log_error_remote

class TokenAuth:
    def __init__(self, secret_key: str = None, encryption_key: str = None):
        """Initialize authentication with secure defaults"""
        self.secret_key = secret_key or os.environ.get(
            'JWT_SECRET_KEY', 
            'jwt_super_secure_key_2025_change_in_production'
        )
        
        # Generate or use encryption key for sensitive data
        if encryption_key:
            self.cipher = Fernet(encryption_key.encode())
        else:
            # Generate a key if none provided (store this securely in production)
            key = os.environ.get('ENCRYPTION_KEY')
            if not key:
                key = Fernet.generate_key().decode()
                log_error_remote('WAAT01', 'Generated new encryption key - store securely!', 
                               extra={'service': 'ai_service', 'key_length': len(key)})
            self.cipher = Fernet(key.encode())
    
    def generate_session_token(self, expires_hours: int = 24) -> Dict[str, Any]:
        """Generate a session token for local use (no user ID needed)"""
        try:
            # Create unique session ID
            session_id = secrets.token_hex(16)
            
            # Token payload (minimal for local use)
            payload = {
                'session_id': session_id,
                'iat': datetime.utcnow(),
                'exp': datetime.utcnow() + timedelta(hours=expires_hours),
                'type': 'session',
                'version': '1.0'
            }
            
            # Generate JWT token
            token = jwt.encode(payload, self.secret_key, algorithm='HS256')
            
            # Create hash for storage (never store plain tokens)
            token_hash = hashlib.sha256(token.encode()).hexdigest()
            
            log_error_remote('IAAT01', 'Session token generated successfully', 
                           extra={'service': 'ai_service', 'session_id': session_id})
            
            return {
                'token': token,
                'token_hash': token_hash,
                'session_id': session_id,
                'expires_at': payload['exp'].isoformat()
            }
            
        except Exception as e:
            log_error_remote('EAAT01', 'Failed to generate session token', 
                           exception=e, extra={'service': 'ai_service'})
            raise
    
    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify and decode JWT token"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=['HS256'])
            
            # Basic validation
            if payload.get('type') != 'session':
                log_error_remote('WAAT02', 'Invalid token type received', 
                               extra={'service': 'ai_service', 'type': payload.get('type')})
                return None
            
            return payload
            
        except jwt.ExpiredSignatureError:
            log_error_remote('WAAT03', 'Expired token received', 
                           extra={'service': 'ai_service'})
            return None
        except jwt.InvalidTokenError as e:
            log_error_remote('EAAT02', 'Invalid token received', 
                           exception=e, extra={'service': 'ai_service'})
            return None
        except Exception as e:
            log_error_remote('EAAT03', 'Token verification failed', 
                           exception=e, extra={'service': 'ai_service'})
            return None
    
    def encrypt_data(self, data: str) -> str:
        """Encrypt sensitive data (conversations, etc.)"""
        try:
            encrypted = self.cipher.encrypt(data.encode())
            return encrypted.decode()
        except Exception as e:
            log_error_remote('EAAT04', 'Data encryption failed', 
                           exception=e, extra={'service': 'ai_service'})
            raise
    
    def decrypt_data(self, encrypted_data: str) -> str:
        """Decrypt sensitive data"""
        try:
            decrypted = self.cipher.decrypt(encrypted_data.encode())
            return decrypted.decode()
        except Exception as e:
            log_error_remote('EAAT05', 'Data decryption failed', 
                           exception=e, extra={'service': 'ai_service'})
            raise

# Global auth instance
auth = TokenAuth()

def require_auth(f):
    """Decorator to require valid authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            # Get token from Authorization header
            auth_header = request.headers.get('Authorization')
            if not auth_header:
                log_error_remote('WAAT04', 'Missing Authorization header', 
                               extra={'service': 'ai_service', 'endpoint': request.endpoint})
                return jsonify({'error': 'Authorization required'}), 401
            
            # Extract token (format: "Bearer <token>")
            try:
                bearer, token = auth_header.split(' ', 1)
                if bearer.lower() != 'bearer':
                    raise ValueError("Invalid authorization format")
            except ValueError:
                log_error_remote('WAAT05', 'Invalid Authorization header format', 
                               extra={'service': 'ai_service', 'header': auth_header[:20]})
                return jsonify({'error': 'Invalid authorization format'}), 401
            
            # Verify token
            payload = auth.verify_token(token)
            if not payload:
                return jsonify({'error': 'Invalid or expired token'}), 401
            
            # Add session info to request context
            request.session_info = payload
            
            return f(*args, **kwargs)
            
        except Exception as e:
            log_error_remote('EAAT06', 'Authentication check failed', 
                           exception=e, extra={'service': 'ai_service'})
            return jsonify({'error': 'Authentication failed'}), 500
    
    return decorated_function

def optional_auth(f):
    """Decorator for optional authentication (graceful degradation)"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            auth_header = request.headers.get('Authorization')
            request.session_info = None
            
            if auth_header:
                try:
                    bearer, token = auth_header.split(' ', 1)
                    if bearer.lower() == 'bearer':
                        payload = auth.verify_token(token)
                        if payload:
                            request.session_info = payload
                except (ValueError, AttributeError, jwt.InvalidTokenError):
                    pass  # Graceful degradation - continue without auth
            
            return f(*args, **kwargs)
            
        except Exception as e:
            log_error_remote('EAAT07', 'Optional authentication failed', 
                           exception=e, extra={'service': 'ai_service'})
            # Continue without auth on error
            request.session_info = None
            return f(*args, **kwargs)
    
    return decorated_function

# Utility functions for token management
def create_session() -> Dict[str, Any]:
    """Create a new session (for local use)"""
    token_data = auth.generate_session_token()
    
    # In a real application, you'd store the token_hash in the database
    # For now, we'll use in-memory storage (Redis in Docker setup)
    
    return {
        'token': token_data['token'],
        'expires_at': token_data['expires_at']
    }

def validate_session(token: str) -> bool:
    """Validate session token"""
    return auth.verify_token(token) is not None

# Health check for auth system
def auth_health_check() -> Dict[str, Any]:
    """Check authentication system health"""
    try:
        # Test token generation and verification
        test_token = auth.generate_session_token(expires_hours=1)
        test_verify = auth.verify_token(test_token['token'])
        
        # Test encryption/decryption
        test_data = "test_encryption_string"
        encrypted = auth.encrypt_data(test_data)
        decrypted = auth.decrypt_data(encrypted)
        
        encryption_works = decrypted == test_data
        token_works = test_verify is not None
        
        status = "healthy" if (encryption_works and token_works) else "degraded"
        
        return {
            'status': status,
            'token_system': 'working' if token_works else 'failed',
            'encryption_system': 'working' if encryption_works else 'failed',
            'timestamp': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        log_error_remote('EAAT08', 'Auth health check failed', 
                       exception=e, extra={'service': 'ai_service'})
        return {
            'status': 'failed',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }
