-- Migration: Create UI UI Relational Table

CREATE TABLE IF NOT EXISTS public.sessions (
    id TEXT PRIMARY KEY,
    user_id UUID NOT NULL,
    title TEXT NOT NULL DEFAULT 'New Conversation',
    is_ended BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    last_active TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- Optimize UI Queries (The fix for O(N) RAM scaling)
CREATE INDEX idx_sessions_user_active ON public.sessions (user_id, last_active DESC);

-- Secure the UI Table
ALTER TABLE public.sessions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can only read their own sessions" 
    ON public.sessions FOR SELECT 
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own sessions" 
    ON public.sessions FOR INSERT 
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own sessions" 
    ON public.sessions FOR UPDATE 
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);
