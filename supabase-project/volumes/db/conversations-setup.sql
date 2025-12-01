-- Conversations Setup for Voice Agent
-- Run this in Supabase SQL Editor

-- Create conversations table
CREATE TABLE IF NOT EXISTS conversations (
  id BIGSERIAL PRIMARY KEY,
  title TEXT NOT NULL,
  created_at DOUBLE PRECISION DEFAULT EXTRACT(EPOCH FROM NOW()),
  updated_at DOUBLE PRECISION DEFAULT EXTRACT(EPOCH FROM NOW())
);

-- Create conversation_messages table
CREATE TABLE IF NOT EXISTS conversation_messages (
  id BIGSERIAL PRIMARY KEY,
  conversation_id BIGINT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
  content TEXT NOT NULL,
  created_at DOUBLE PRECISION DEFAULT EXTRACT(EPOCH FROM NOW())
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_conversation_messages_conversation_id 
  ON conversation_messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_conversations_created_at 
  ON conversations(created_at DESC);

-- Grant permissions
GRANT ALL ON conversations TO anon, authenticated;
GRANT ALL ON conversation_messages TO anon, authenticated;
GRANT USAGE, SELECT ON SEQUENCE conversations_id_seq TO anon, authenticated;
GRANT USAGE, SELECT ON SEQUENCE conversation_messages_id_seq TO anon, authenticated;

