-- Create chat_logs table for storing Q&A interactions
CREATE TABLE IF NOT EXISTS public.chat_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    question TEXT NOT NULL,
    answer TEXT,
    source VARCHAR(20) DEFAULT 'ai' CHECK (source IN ('ai', 'dataset', 'fallback', 'error')),
    timestamp TIMESTAMPTZ DEFAULT now(),
    answered_at TIMESTAMPTZ,
    user_ip INET,
    response_time_ms INTEGER,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_chat_logs_timestamp ON public.chat_logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_chat_logs_source ON public.chat_logs(source);
CREATE INDEX IF NOT EXISTS idx_chat_logs_created_at ON public.chat_logs(created_at);

-- Enable Row Level Security (RLS)
ALTER TABLE public.chat_logs ENABLE ROW LEVEL SECURITY;

-- Create policy to allow API service to insert and select
CREATE POLICY "Allow API service access" ON public.chat_logs
    FOR ALL USING (true);

-- Create function to update updated_at column automatically
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create trigger to auto-update updated_at
CREATE TRIGGER update_chat_logs_updated_at 
    BEFORE UPDATE ON public.chat_logs 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- Create view for analytics (optional)
CREATE OR REPLACE VIEW public.chat_analytics AS
SELECT 
    DATE(timestamp) as date,
    source,
    COUNT(*) as question_count,
    AVG(response_time_ms) as avg_response_time_ms,
    COUNT(CASE WHEN answer IS NOT NULL THEN 1 END) as answered_count
FROM public.chat_logs
GROUP BY DATE(timestamp), source
ORDER BY date DESC, source;

-- Grant permissions to authenticated users (adjust as needed)
GRANT SELECT ON public.chat_analytics TO authenticated;
GRANT ALL ON public.chat_logs TO service_role;
