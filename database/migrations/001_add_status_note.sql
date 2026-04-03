-- Migration: Add status_note column to ringkas_recommendations
-- Allows users to add a reason/note when dismissing recommendations

ALTER TABLE ringkas_recommendations ADD COLUMN IF NOT EXISTS status_note VARCHAR(500);
