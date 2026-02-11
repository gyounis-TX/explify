-- Add severity_score column to history table (matches SQLite migration)
ALTER TABLE history ADD COLUMN IF NOT EXISTS severity_score REAL;
