-- Migration 006: Add Quizzes, Questions, Attempts, and Document Summaries Tables
-- Implements secure separated public/private quiz answers and cache indexing.

-- ── 1. QUIZZES METADATA ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS quizzes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    difficulty TEXT NOT NULL CHECK (difficulty IN ('easy', 'medium', 'hard')),
    size TEXT NOT NULL CHECK (size IN ('small', 'medium', 'large')),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_quizzes_user_doc ON quizzes(user_id, document_id);

-- ── 2. PUBLIC QUIZ QUESTIONS ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS quiz_questions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    quiz_id UUID NOT NULL REFERENCES quizzes(id) ON DELETE CASCADE,
    question_text TEXT NOT NULL,
    options JSONB NOT NULL CHECK (jsonb_typeof(options) = 'array' AND jsonb_array_length(options) = 4),
    difficulty TEXT NOT NULL CHECK (difficulty IN ('easy', 'medium', 'hard')),
    concept TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_quiz_questions_quiz ON quiz_questions(quiz_id);

-- ── 3. PRIVATE QUIZ ANSWERS ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS quiz_question_answers (
    question_id UUID PRIMARY KEY REFERENCES quiz_questions(id) ON DELETE CASCADE,
    correct_option_id INTEGER NOT NULL CHECK (correct_option_id >= 0 AND correct_option_id <= 3),
    explanation TEXT NOT NULL,
    verifier_metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ── 4. QUIZ ATTEMPTS ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS quiz_attempts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    quiz_id UUID NOT NULL REFERENCES quizzes(id) ON DELETE CASCADE,
    started_at TIMESTAMPTZ DEFAULT NOW(),
    submitted_at TIMESTAMPTZ, -- Nullable until status is 'completed'
    status TEXT NOT NULL CHECK (status IN ('started', 'completed')),
    total_questions INTEGER NOT NULL CHECK (total_questions > 0),
    correct_count INTEGER CHECK (correct_count >= 0 AND correct_count <= total_questions), -- Nullable until completed
    score_percentage NUMERIC CHECK (score_percentage >= 0 AND score_percentage <= 100), -- Nullable until completed
    attempt_number INTEGER NOT NULL CHECK (attempt_number > 0),
    idempotency_key TEXT NOT NULL,
    CONSTRAINT unique_attempt_idempotency UNIQUE (quiz_id, user_id, idempotency_key),
    CONSTRAINT unique_attempt_number UNIQUE (user_id, quiz_id, attempt_number)
);
CREATE INDEX IF NOT EXISTS idx_quiz_attempts_lookup ON quiz_attempts(quiz_id, user_id);

-- ── 5. QUESTION RESPONSES ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS question_responses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    attempt_id UUID NOT NULL REFERENCES quiz_attempts(id) ON DELETE CASCADE,
    question_id UUID NOT NULL REFERENCES quiz_questions(id) ON DELETE CASCADE,
    selected_option_id INTEGER NOT NULL CHECK (selected_option_id >= 0 AND selected_option_id <= 3),
    is_correct BOOLEAN NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT unique_attempt_question UNIQUE (attempt_id, question_id)
);

-- ── 6. DOCUMENT SUMMARIES ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS document_summaries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    summary_size TEXT NOT NULL CHECK (summary_size IN ('concise', 'medium', 'detailed', 'custom')),
    target_word_count INT,
    actual_word_count INT,
    content TEXT NOT NULL,
    language TEXT NOT NULL DEFAULT 'ar',
    document_hash TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    citations JSONB DEFAULT '[]'::jsonb,
    verifier_result JSONB DEFAULT '{}'::jsonb,
    model_name TEXT NOT NULL,
    summary_status TEXT NOT NULL DEFAULT 'completed' CHECK (summary_status IN ('pending', 'processing', 'completed', 'partial', 'failed')),
    failure_metadata JSONB DEFAULT '{}'::jsonb,
    generation_config_hash TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE UNIQUE INDEX unique_document_summary_cache_idx ON document_summaries (
    document_id, user_id, summary_size, COALESCE(target_word_count, -1), language, prompt_version, document_hash, generation_config_hash
);

-- ── 7. SECURITY & PRIVILEGE HARDENING ──────────────────────────────────────────

-- Disable SELECT on private answers completely
ALTER TABLE quiz_question_answers ENABLE ROW LEVEL SECURITY;
REVOKE ALL PRIVILEGES ON quiz_question_answers FROM authenticated, anon;

-- Disable direct mutations on quizzes, public questions, attempts, responses, and summaries
REVOKE INSERT, UPDATE, DELETE ON quizzes, quiz_questions, quiz_attempts, question_responses, document_summaries FROM authenticated, anon;

-- Enable Row-Level Security on public entities
ALTER TABLE quizzes ENABLE ROW LEVEL SECURITY;
ALTER TABLE quiz_questions ENABLE ROW LEVEL SECURITY;
ALTER TABLE quiz_attempts ENABLE ROW LEVEL SECURITY;
ALTER TABLE question_responses ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_summaries ENABLE ROW LEVEL SECURITY;

-- Apply SELECT Row-Level Security Policies for the authenticated owner
DROP POLICY IF EXISTS quizzes_select_policy ON quizzes;
CREATE POLICY quizzes_select_policy ON quizzes FOR SELECT TO authenticated USING (auth.uid() = user_id);

DROP POLICY IF EXISTS quiz_questions_select_policy ON quiz_questions;
CREATE POLICY quiz_questions_select_policy ON quiz_questions FOR SELECT TO authenticated USING (
    EXISTS (SELECT 1 FROM quizzes q WHERE q.id = quiz_id AND q.user_id = auth.uid())
);

DROP POLICY IF EXISTS quiz_attempts_select_policy ON quiz_attempts;
CREATE POLICY quiz_attempts_select_policy ON quiz_attempts FOR SELECT TO authenticated USING (auth.uid() = user_id);

DROP POLICY IF EXISTS question_responses_select_policy ON question_responses;
CREATE POLICY question_responses_select_policy ON question_responses FOR SELECT TO authenticated USING (
    EXISTS (SELECT 1 FROM quiz_attempts a WHERE a.id = attempt_id AND a.user_id = auth.uid())
);

DROP POLICY IF EXISTS document_summaries_select_policy ON document_summaries;
CREATE POLICY document_summaries_select_policy ON document_summaries FOR SELECT TO authenticated USING (auth.uid() = user_id);
