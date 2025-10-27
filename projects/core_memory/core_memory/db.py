import os
from sqlalchemy import create_engine, Column, String, Text, JSON, DateTime, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import uuid
from sqlalchemy import ForeignKey, Float
from sqlalchemy.dialects.postgresql import JSONB

DB_DSN = os.environ.get("POSTGRES_DSN", "postgresql://core:core@localhost:5432/corememory")

engine = create_engine(DB_DSN, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class Memory(Base):
    __tablename__ = "memories"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    namespace = Column(String, nullable=False, default="global")
    agent_id = Column(String, nullable=True)
    text = Column(Text, nullable=False)
    metadata = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    size_bytes = Column(Integer, nullable=True)
    # embedding column (pgvector) will be added via migration when pgvector is enabled


class Embedding(Base):
    __tablename__ = "embeddings"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    memory_id = Column(UUID(as_uuid=True), ForeignKey("memories.id"), nullable=False)
    vector = Column(JSONB, nullable=False)



def init_db():
    Base.metadata.create_all(bind=engine)
