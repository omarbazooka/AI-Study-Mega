-- Migration: Add title column to chat_sessions table for custom session headers
ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS title TEXT;
