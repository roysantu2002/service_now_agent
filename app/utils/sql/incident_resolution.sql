-- incident_resolution.sql

CREATE TABLE IF NOT EXISTS incident_resolution (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Top-level metadata
    success BOOLEAN,
    sys_id VARCHAR(100) NOT NULL UNIQUE,
    analysis_type VARCHAR(50),
    ai_model VARCHAR(100),
    usage JSONB,

    -- Data object mirrored
    data_id UUID,
    issue TEXT,
    issue_category VARCHAR(200),
    category VARCHAR(200),
    level VARCHAR(100),
    description TEXT,
    steps_to_resolve JSONB,
    technical_details TEXT,
    complete_description TEXT,
    analyzed_at TIMESTAMPTZ,
    confidence_score DECIMAL(5,4),

    -- Output generated files
    pdf_path TEXT,
    json_path TEXT,
    md_path TEXT,
    raw_ai_output_path TEXT,

    parsing_error TEXT,
    validation_error TEXT,

    -- ✅ Added to match safe_response
    metadata JSONB,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
