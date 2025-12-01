-- RAG Setup for Voice Agent
-- Run this in Supabase SQL Editor after initial setup

-- Enable pgvector extension if not already enabled
CREATE EXTENSION IF NOT EXISTS vector;

-- Drop and recreate documents table with status tracking
DROP TABLE IF EXISTS documents CASCADE;

-- Create documents table for RAG with status tracking
CREATE TABLE IF NOT EXISTS documents (
  id BIGSERIAL PRIMARY KEY,
  content TEXT,
  embedding vector(768),  -- Adjust dimension based on embedding model (nomic-embed-text = 768)
  file_path TEXT,
  file_name TEXT NOT NULL,
  file_type TEXT,
  file_size BIGINT DEFAULT 0,
  status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'indexed', 'error')),
  error_message TEXT,
  indexed_at DOUBLE PRECISION,
  created_at DOUBLE PRECISION DEFAULT EXTRACT(EPOCH FROM NOW()),
  updated_at DOUBLE PRECISION DEFAULT EXTRACT(EPOCH FROM NOW())
);

-- Create index for vector similarity search
CREATE INDEX IF NOT EXISTS documents_embedding_idx ON documents 
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- Create index for status queries
CREATE INDEX IF NOT EXISTS documents_status_idx ON documents(status);

-- Create function for similarity search
CREATE OR REPLACE FUNCTION match_documents(
  query_embedding vector(768),
  match_threshold float DEFAULT 0.5,
  match_count int DEFAULT 5
)
RETURNS TABLE (
  id bigint,
  content text,
  file_path text,
  file_name text,
  similarity float
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  SELECT
    documents.id,
    documents.content,
    documents.file_path,
    documents.file_name,
    1 - (documents.embedding <=> query_embedding) AS similarity
  FROM documents
  WHERE documents.status = 'indexed'
    AND documents.embedding IS NOT NULL
    AND 1 - (documents.embedding <=> query_embedding) > match_threshold
  ORDER BY documents.embedding <=> query_embedding
  LIMIT match_count;
END;
$$;

-- Grant permissions
GRANT USAGE ON SCHEMA public TO anon, authenticated;
GRANT ALL ON documents TO anon, authenticated;
GRANT EXECUTE ON FUNCTION match_documents TO anon, authenticated;
GRANT USAGE, SELECT ON SEQUENCE documents_id_seq TO anon, authenticated;
