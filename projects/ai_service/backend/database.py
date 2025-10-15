#!/usr/bin/env python3
"""
Database management for AI Service
Handles agent storage and retrieval
"""
import sqlite3
import os
import json
from datetime import datetime
from typing import Dict, List, Optional

class AgentDatabase:
    def __init__(self, db_path: str = None):
        if db_path is None:
            # Store database in backend directory
            backend_dir = os.path.dirname(os.path.abspath(__file__))
            db_path = os.path.join(backend_dir, 'agents.db')
        
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize the database with required tables"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS agents (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    avatar_image TEXT,
                    model_name TEXT NOT NULL,
                    temperature REAL DEFAULT 0.7,
                    top_p REAL DEFAULT 0.9,
                    system_prompt TEXT DEFAULT 'You are a helpful AI assistant.',
                    max_tokens INTEGER DEFAULT 2048,
                    status TEXT DEFAULT 'offline',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_active TIMESTAMP,
                    metadata TEXT DEFAULT '{}'
                )
            ''')
            
            # Create index for faster lookups
            conn.execute('CREATE INDEX IF NOT EXISTS idx_agents_status ON agents(status)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_agents_name ON agents(name)')
            conn.commit()
    
    def create_agent(self, agent_data: Dict) -> Dict:
        """Create a new agent"""
        import uuid
        
        agent_id = str(uuid.uuid4())
        
        # Validate required fields
        required_fields = ['name', 'model_name']
        for field in required_fields:
            if field not in agent_data or not agent_data[field]:
                raise ValueError(f"Missing required field: {field}")
        
        # Set defaults
        agent = {
            'id': agent_id,
            'name': agent_data['name'],
            'avatar_image': agent_data.get('avatar_image', '🤖'),
            'model_name': agent_data['model_name'],
            'temperature': float(agent_data.get('temperature', 0.7)),
            'top_p': float(agent_data.get('top_p', 0.9)),
            'system_prompt': agent_data.get('system_prompt', 'You are a helpful AI assistant.'),
            'max_tokens': int(agent_data.get('max_tokens', 2048)),
            'status': 'offline',  # Will be updated based on model availability
            'created_at': datetime.now().isoformat(),
            'last_active': None,
            'metadata': json.dumps(agent_data.get('metadata', {}))
        }
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT INTO agents (
                    id, name, avatar_image, model_name, temperature, top_p,
                    system_prompt, max_tokens, status, created_at, last_active, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                agent['id'], agent['name'], agent['avatar_image'], agent['model_name'],
                agent['temperature'], agent['top_p'], agent['system_prompt'],
                agent['max_tokens'], agent['status'], agent['created_at'],
                agent['last_active'], agent['metadata']
            ))
            conn.commit()
        
        return agent
    
    def get_agent(self, agent_id: str) -> Optional[Dict]:
        """Get a specific agent by ID"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute('SELECT * FROM agents WHERE id = ?', (agent_id,))
            row = cursor.fetchone()
            
            if row:
                agent = dict(row)
                agent['metadata'] = json.loads(agent['metadata'])
                return agent
            return None
    
    def get_all_agents(self) -> List[Dict]:
        """Get all agents"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute('SELECT * FROM agents ORDER BY created_at DESC')
            rows = cursor.fetchall()
            
            agents = []
            for row in rows:
                agent = dict(row)
                agent['metadata'] = json.loads(agent['metadata'])
                agents.append(agent)
            
            return agents
    
    def update_agent(self, agent_id: str, updates: Dict) -> bool:
        """Update an existing agent"""
        if not self.get_agent(agent_id):
            return False
        
        # Build update query dynamically
        allowed_fields = [
            'name', 'avatar_image', 'model_name', 'temperature', 'top_p',
            'system_prompt', 'max_tokens', 'status', 'last_active', 'metadata'
        ]
        
        update_fields = []
        values = []
        
        for field, value in updates.items():
            if field in allowed_fields:
                update_fields.append(f"{field} = ?")
                if field == 'metadata':
                    values.append(json.dumps(value))
                else:
                    values.append(value)
        
        if not update_fields:
            return False
        
        values.append(agent_id)
        
        with sqlite3.connect(self.db_path) as conn:
            query = f"UPDATE agents SET {', '.join(update_fields)} WHERE id = ?"
            conn.execute(query, values)
            conn.commit()
        
        return True
    
    def delete_agent(self, agent_id: str) -> bool:
        """Delete an agent"""
        if not self.get_agent(agent_id):
            return False
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('DELETE FROM agents WHERE id = ?', (agent_id,))
            conn.commit()
        
        return True
    
    def update_agent_status(self, agent_id: str, status: str) -> bool:
        """Update agent status (online, offline, busy, idle)"""
        return self.update_agent(agent_id, {
            'status': status,
            'last_active': datetime.now().isoformat() if status != 'offline' else None
        })
    
    def get_agents_by_model(self, model_name: str) -> List[Dict]:
        """Get all agents using a specific model"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute('SELECT * FROM agents WHERE model_name = ?', (model_name,))
            rows = cursor.fetchall()
            
            agents = []
            for row in rows:
                agent = dict(row)
                agent['metadata'] = json.loads(agent['metadata'])
                agents.append(agent)
            
            return agents
    
    def get_agents_by_status(self, status: str) -> List[Dict]:
        """Get all agents with a specific status"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute('SELECT * FROM agents WHERE status = ?', (status,))
            rows = cursor.fetchall()
            
            agents = []
            for row in rows:
                agent = dict(row)
                agent['metadata'] = json.loads(agent['metadata'])
                agents.append(agent)
            
            return agents
    
    def search_agents(self, query: str) -> List[Dict]:
        """Search agents by name or model"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute('''
                SELECT * FROM agents 
                WHERE name LIKE ? OR model_name LIKE ?
                ORDER BY created_at DESC
            ''', (f'%{query}%', f'%{query}%'))
            rows = cursor.fetchall()
            
            agents = []
            for row in rows:
                agent = dict(row)
                agent['metadata'] = json.loads(agent['metadata'])
                agents.append(agent)
            
            return agents

# Global database instance
db = AgentDatabase()