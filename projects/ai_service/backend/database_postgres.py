#!/usr/bin/env python3
"""
PostgreSQL Database management for AI Service
Enhanced with connection pooling, proper error handling, and UUID support
"""
import os
import sys
import json
import uuid
import psycopg2
from psycopg2 import pool, sql
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from contextlib import contextmanager

# Import project-wide ErrorLogger
sys.path.append('/app')
from ErrorLogger.logger import log_error_remote

class PostgreSQLDatabase:
    def __init__(self, database_url: str = None):
        """Initialize PostgreSQL connection pool"""
        if database_url is None:
            database_url = os.environ.get(
                'DATABASE_URL', 
                'postgresql://ai_user:ai_secure_pass_2025@localhost:5432/ai_service'
            )
        
        self.database_url = database_url
        self.connection_pool = None
        self._init_connection_pool()
    
    def _init_connection_pool(self):
        """Initialize connection pool with proper error handling"""
        try:
            self.connection_pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=2,
                maxconn=10,
                dsn=self.database_url,
                cursor_factory=RealDictCursor
            )
            log_error_remote('IADB01', 'PostgreSQL connection pool initialized successfully', 
                           extra={'service': 'ai_service', 'pool_size': '2-10'})
        except Exception as e:
            log_error_remote('EADB01', 'Failed to initialize PostgreSQL connection pool', 
                           exception=e, extra={'service': 'ai_service'})
            raise
    
    @contextmanager
    def get_connection(self):
        """Get connection from pool with automatic cleanup"""
        conn = None
        try:
            conn = self.connection_pool.getconn()
            yield conn
        except Exception as e:
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                self.connection_pool.putconn(conn)
    
    def get_agent(self, agent_id: str) -> Optional[Dict]:
        """Get agent by ID"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT * FROM agents WHERE id = %s",
                        (agent_id,)
                    )
                    result = cur.fetchone()
                    return dict(result) if result else None
        except Exception as e:
            log_error_remote('EADB02', f'Failed to get agent {agent_id}', 
                           exception=e, extra={'service': 'ai_service', 'agent_id': agent_id})
            return None
    
    def list_agents(self) -> List[Dict]:
        """List all agents with their current status"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT a.*, 
                               COUNT(cl.id) as conversation_count,
                               MAX(cl.timestamp) as last_conversation
                        FROM agents a
                        LEFT JOIN conversation_logs cl ON a.id = cl.agent_id
                        GROUP BY a.id
                        ORDER BY a.last_active DESC NULLS LAST, a.created_at DESC
                    """)
                    results = cur.fetchall()
                    return [dict(row) for row in results]
        except Exception as e:
            log_error_remote('EADB03', 'Failed to list agents', 
                           exception=e, extra={'service': 'ai_service'})
            return []
    
    def create_agent(self, agent_data: Dict) -> Dict:
        """Create a new agent with validation"""
        try:
            # Validate required fields
            required_fields = ['name', 'model_name']
            for field in required_fields:
                if field not in agent_data or not agent_data[field]:
                    raise ValueError(f"Missing required field: {field}")
            
            agent_id = str(uuid.uuid4())
            
            # Set defaults for optional fields
            agent = {
                'id': agent_id,
                'name': agent_data['name'],
                'model_name': agent_data['model_name'],
                'avatar_image': agent_data.get('avatar_image'),
                'temperature': float(agent_data.get('temperature', 0.7)),
                'top_p': float(agent_data.get('top_p', 0.9)),
                'system_prompt': agent_data.get('system_prompt', 'You are a helpful AI assistant.'),
                'max_tokens': int(agent_data.get('max_tokens', 2048)),
                'status': 'idle',
                'metadata': json.dumps(agent_data.get('metadata', {}))
            }
            
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO agents (
                            id, name, model_name, avatar_image, temperature, 
                            top_p, system_prompt, max_tokens, status, metadata
                        ) VALUES (
                            %(id)s, %(name)s, %(model_name)s, %(avatar_image)s, 
                            %(temperature)s, %(top_p)s, %(system_prompt)s, 
                            %(max_tokens)s, %(status)s, %(metadata)s
                        ) RETURNING *
                    """, agent)
                    
                    result = cur.fetchone()
                    conn.commit()
                    
                    created_agent = dict(result)
                    log_error_remote('IADB02', f'Agent created successfully: {agent["name"]}', 
                                   extra={'service': 'ai_service', 'agent_id': agent_id})
                    return created_agent
                    
        except Exception as e:
            log_error_remote('EADB04', f'Failed to create agent: {agent_data.get("name", "unknown")}', 
                           exception=e, extra={'service': 'ai_service'})
            raise
    
    def update_agent(self, agent_id: str, update_data: Dict) -> bool:
        """Update agent with partial data"""
        try:
            # Build dynamic update query
            update_fields = []
            params = {'agent_id': agent_id}
            
            allowed_fields = ['name', 'model_name', 'avatar_image', 'temperature', 
                            'top_p', 'system_prompt', 'max_tokens', 'status', 'metadata']
            
            for field in allowed_fields:
                if field in update_data:
                    update_fields.append(f"{field} = %({field})s")
                    if field == 'metadata':
                        params[field] = json.dumps(update_data[field])
                    else:
                        params[field] = update_data[field]
            
            if not update_fields:
                return False
            
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    query = f"""
                        UPDATE agents 
                        SET {', '.join(update_fields)}, last_active = CURRENT_TIMESTAMP
                        WHERE id = %(agent_id)s
                    """
                    cur.execute(query, params)
                    conn.commit()
                    
                    updated = cur.rowcount > 0
                    if updated:
                        log_error_remote('IADB03', f'Agent updated: {agent_id}', 
                                       extra={'service': 'ai_service', 'agent_id': agent_id})
                    return updated
                    
        except Exception as e:
            log_error_remote('EADB05', f'Failed to update agent {agent_id}', 
                           exception=e, extra={'service': 'ai_service', 'agent_id': agent_id})
            return False
    
    def delete_agent(self, agent_id: str) -> bool:
        """Delete agent and all associated data"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM agents WHERE id = %s", (agent_id,))
                    conn.commit()
                    
                    deleted = cur.rowcount > 0
                    if deleted:
                        log_error_remote('IADB04', f'Agent deleted: {agent_id}', 
                                       extra={'service': 'ai_service', 'agent_id': agent_id})
                    return deleted
                    
        except Exception as e:
            log_error_remote('EADB06', f'Failed to delete agent {agent_id}', 
                           exception=e, extra={'service': 'ai_service', 'agent_id': agent_id})
            return False
    
    def update_agent_status(self, agent_id: str, status: str) -> bool:
        """Update agent status (online, offline, busy, idle)"""
        return self.update_agent(agent_id, {'status': status})
    
    def log_conversation(self, agent_id: str, user_message: str, ai_response: str, 
                        response_time_ms: int = None, token_count: int = None) -> str:
        """Log conversation with performance metrics"""
        try:
            conversation_id = str(uuid.uuid4())
            
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO conversation_logs (
                            id, agent_id, user_message, ai_response, 
                            response_time_ms, token_count
                        ) VALUES (%s, %s, %s, %s, %s, %s)
                        RETURNING id
                    """, (conversation_id, agent_id, user_message, ai_response, 
                         response_time_ms, token_count))
                    
                    result = cur.fetchone()
                    conn.commit()
                    return result['id']
                    
        except Exception as e:
            log_error_remote('EADB07', f'Failed to log conversation for agent {agent_id}', 
                           exception=e, extra={'service': 'ai_service', 'agent_id': agent_id})
            return None
    
    def get_conversation_history(self, agent_id: str, limit: int = 50) -> List[Dict]:
        """Get conversation history for an agent"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT * FROM conversation_logs 
                        WHERE agent_id = %s 
                        ORDER BY timestamp DESC 
                        LIMIT %s
                    """, (agent_id, limit))
                    
                    results = cur.fetchall()
                    return [dict(row) for row in reversed(results)]  # Chronological order
                    
        except Exception as e:
            log_error_remote('EADB08', f'Failed to get conversation history for agent {agent_id}', 
                           exception=e, extra={'service': 'ai_service', 'agent_id': agent_id})
            return []
    
    def store_memory(self, agent_id: str, content: str, importance: float = 0.5) -> str:
        """Store important conversation context as memory"""
        try:
            memory_id = str(uuid.uuid4())
            
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO agent_memories (id, agent_id, content, importance)
                        VALUES (%s, %s, %s, %s)
                        RETURNING id
                    """, (memory_id, agent_id, content, importance))
                    
                    result = cur.fetchone()
                    conn.commit()
                    return result['id']
                    
        except Exception as e:
            log_error_remote('EADB09', f'Failed to store memory for agent {agent_id}', 
                           exception=e, extra={'service': 'ai_service', 'agent_id': agent_id})
            return None
    
    def get_agent_memories(self, agent_id: str, min_importance: float = 0.0, limit: int = 10) -> List[Dict]:
        """Get agent memories by importance"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT * FROM agent_memories 
                        WHERE agent_id = %s AND importance >= %s
                        ORDER BY importance DESC, last_accessed DESC
                        LIMIT %s
                    """, (agent_id, min_importance, limit))
                    
                    results = cur.fetchall()
                    return [dict(row) for row in results]
                    
        except Exception as e:
            log_error_remote('EADB10', f'Failed to get memories for agent {agent_id}', 
                           exception=e, extra={'service': 'ai_service', 'agent_id': agent_id})
            return []
    
    def update_memory_access(self, memory_id: str):
        """Update memory access timestamp and count"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE agent_memories 
                        SET last_accessed = CURRENT_TIMESTAMP, 
                            access_count = access_count + 1
                        WHERE id = %s
                    """, (memory_id,))
                    conn.commit()
                    
        except Exception as e:
            log_error_remote('EADB11', f'Failed to update memory access {memory_id}', 
                           exception=e, extra={'service': 'ai_service'})
    
    def cleanup_old_data(self, days: int = 30):
        """Cleanup old conversation logs and unused memories"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    # Clean old conversation logs
                    cur.execute(
                        "DELETE FROM conversation_logs WHERE timestamp < %s",
                        (cutoff_date,)
                    )
                    conversations_deleted = cur.rowcount
                    
                    # Clean unused memories (low importance, not accessed recently)
                    cur.execute("""
                        DELETE FROM agent_memories 
                        WHERE importance < 0.3 
                        AND last_accessed < %s 
                        AND access_count < 2
                    """, (cutoff_date,))
                    memories_deleted = cur.rowcount
                    
                    # Clean expired tokens
                    cur.execute("SELECT cleanup_expired_tokens()")
                    tokens_deleted = cur.fetchone()[0]
                    
                    conn.commit()
                    
                    log_error_remote('IADB05', 'Database cleanup completed', 
                                   extra={
                                       'service': 'ai_service',
                                       'conversations_deleted': conversations_deleted,
                                       'memories_deleted': memories_deleted,
                                       'tokens_deleted': tokens_deleted
                                   })
                    
        except Exception as e:
            log_error_remote('EADB12', 'Database cleanup failed', 
                           exception=e, extra={'service': 'ai_service'})

# Global database instance
db = PostgreSQLDatabase()
