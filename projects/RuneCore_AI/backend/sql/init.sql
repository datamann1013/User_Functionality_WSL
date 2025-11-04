-- AI Service Database Initialization
-- PostgreSQL schema with improved indexing and constraints

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Agents table with enhanced structure
CREATE TABLE IF NOT EXISTS agents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    avatar_image TEXT,
    model_name VARCHAR(100) NOT NULL,
    temperature DECIMAL(3,2) DEFAULT 0.7 CHECK (temperature >= 0 AND temperature <= 2),
    top_p DECIMAL(3,2) DEFAULT 0.9 CHECK (top_p >= 0 AND top_p <= 1),
    system_prompt TEXT DEFAULT 'You are a helpful AI assistant.',
    max_tokens INTEGER DEFAULT 2048 CHECK (max_tokens > 0),
    status VARCHAR(20) DEFAULT 'offline' CHECK (status IN ('online', 'offline', 'busy', 'idle')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_active TIMESTAMP WITH TIME ZONE,
    metadata JSONB DEFAULT '{}',
    
    -- Indexes for performance
    CONSTRAINT agents_name_check CHECK (length(name) >= 1),
    CONSTRAINT agents_model_check CHECK (length(model_name) >= 1)
);

-- Conversation logs with enhanced tracking
CREATE TABLE IF NOT EXISTS conversation_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    user_message TEXT NOT NULL,
    ai_response TEXT NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    response_time_ms INTEGER,
    token_count INTEGER,
    metadata JSONB DEFAULT '{}'
);

-- Memory storage for conversation context
CREATE TABLE IF NOT EXISTS agent_memories (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    importance DECIMAL(3,2) DEFAULT 0.5 CHECK (importance >= 0 AND importance <= 1),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_accessed TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    access_count INTEGER DEFAULT 0,
    metadata JSONB DEFAULT '{}'
);

-- Session tokens for authentication (no user accounts yet)
CREATE TABLE IF NOT EXISTS session_tokens (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    token_hash VARCHAR(255) NOT NULL UNIQUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    last_used TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}'
);

-- Model registry for tracking available models
CREATE TABLE IF NOT EXISTS model_registry (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL UNIQUE,
    size_gb DECIMAL(5,2),
    status VARCHAR(20) DEFAULT 'available' CHECK (status IN ('available', 'downloading', 'unavailable')),
    download_progress INTEGER DEFAULT 0 CHECK (download_progress >= 0 AND download_progress <= 100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_checked TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}'
);

-- Performance indexes
CREATE INDEX IF NOT EXISTS idx_agents_status ON agents(status);
CREATE INDEX IF NOT EXISTS idx_agents_model ON agents(model_name);
CREATE INDEX IF NOT EXISTS idx_agents_active ON agents(last_active DESC);

CREATE INDEX IF NOT EXISTS idx_conversations_agent ON conversation_logs(agent_id);
CREATE INDEX IF NOT EXISTS idx_conversations_time ON conversation_logs(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_conversations_agent_time ON conversation_logs(agent_id, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_memories_agent ON agent_memories(agent_id);
CREATE INDEX IF NOT EXISTS idx_memories_importance ON agent_memories(importance DESC);
CREATE INDEX IF NOT EXISTS idx_memories_accessed ON agent_memories(last_accessed DESC);
CREATE INDEX IF NOT EXISTS idx_memories_agent_importance ON agent_memories(agent_id, importance DESC);

CREATE INDEX IF NOT EXISTS idx_tokens_hash ON session_tokens(token_hash);
CREATE INDEX IF NOT EXISTS idx_tokens_expires ON session_tokens(expires_at);

CREATE INDEX IF NOT EXISTS idx_models_status ON model_registry(status);
CREATE INDEX IF NOT EXISTS idx_models_name ON model_registry(name);

-- Insert default models
INSERT INTO model_registry (name, size_gb, status, metadata) VALUES
    ('llama3.2:1b', 1.3, 'available', '{"description": "Lightweight Llama model", "recommended": true}'),
    ('gemma:2b', 1.6, 'available', '{"description": "Google Gemma model", "recommended": false}'),
    ('codellama:7b', 3.8, 'available', '{"description": "Code-specialized model", "recommended": false}')
ON CONFLICT (name) DO NOTHING;

-- Create a function to cleanup expired tokens
CREATE OR REPLACE FUNCTION cleanup_expired_tokens()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM session_tokens WHERE expires_at < CURRENT_TIMESTAMP;
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Create a function to update agent last_active
CREATE OR REPLACE FUNCTION update_agent_activity()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE agents 
    SET last_active = CURRENT_TIMESTAMP 
    WHERE id = NEW.agent_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to auto-update agent activity on conversation
CREATE TRIGGER trigger_update_agent_activity
    AFTER INSERT ON conversation_logs
    FOR EACH ROW
    EXECUTE FUNCTION update_agent_activity();

-- Grant permissions (if needed for application user)
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO ai_user;
-- GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO ai_user;
