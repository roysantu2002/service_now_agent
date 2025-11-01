"""
Database Schema for Feedback Service

This file contains the SQL schema for creating the necessary tables
to support the feedback service for recording human validation of
AI routing decisions.

Run this script to set up the database before using the feedback service.
"""

# Create ai_routing_decisions table
AI_ROUTING_DECISIONS_SCHEMA = """
CREATE TABLE IF NOT EXISTS ai_routing_decisions (
    decision_id UUID PRIMARY KEY,
    original_query TEXT NOT NULL,
    ai_routed_to VARCHAR(255) NOT NULL,
    ai_confidence DECIMAL(3,2) CHECK (ai_confidence >= 0.0 AND ai_confidence <= 1.0),
    ai_reasoning TEXT,
    routing_criteria JSONB,
    context JSONB,
    metadata JSONB,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX idx_ai_decisions_timestamp ON ai_routing_decisions(timestamp);
CREATE INDEX idx_ai_decisions_routed_to ON ai_routing_decisions(ai_routed_to);
CREATE INDEX idx_ai_decisions_confidence ON ai_routing_decisions(ai_confidence);
"""

# Create feedback_records table
FEEDBACK_RECORDS_SCHEMA = """
CREATE TABLE IF NOT EXISTS feedback_records (
    feedback_id UUID PRIMARY KEY,
    decision_id UUID NOT NULL REFERENCES ai_routing_decisions(decision_id),
    feedback_type VARCHAR(50) CHECK (feedback_type IN ('validation', 'correction', 'rating', 'comment', 'escalation')),
    priority VARCHAR(20) CHECK (priority IN ('critical', 'high', 'medium', 'low')) DEFAULT 'medium',
    tags JSONB DEFAULT '[]'::jsonb,
    status VARCHAR(50) DEFAULT 'pending' CHECK (status IN ('pending', 'validated', 'needs_review', 'escalated', 'closed')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP WITH TIME ZONE
);

-- Indexes for performance
CREATE INDEX idx_feedback_records_status ON feedback_records(status);
CREATE INDEX idx_feedback_records_priority ON feedback_records(priority);
CREATE INDEX idx_feedback_records_created ON feedback_records(created_at);
CREATE INDEX idx_feedback_records_feedback_type ON feedback_records(feedback_type);
CREATE INDEX idx_feedback_records_decision ON feedback_records(decision_id);

-- Triggers for updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_feedback_records_updated_at 
    BEFORE UPDATE ON feedback_records 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
"""

# Create human_validations table
HUMAN_VALIDATIONS_SCHEMA = """
CREATE TABLE IF NOT EXISTS human_validations (
    validation_id UUID PRIMARY KEY,
    decision_id UUID NOT NULL REFERENCES ai_routing_decisions(decision_id),
    validator_id VARCHAR(255) NOT NULL,
    validation_decision VARCHAR(50) CHECK (validation_decision IN ('approved', 'rejected', 'corrected', 'escalated', 'partially_correct')),
    validation_score DECIMAL(2,1) CHECK (validation_score >= 1.0 AND validation_score <= 5.0),
    correct_routing VARCHAR(255),
    validation_comments TEXT,
    time_spent_seconds INTEGER CHECK (time_spent_seconds >= 0),
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX idx_validations_decision ON human_validations(decision_id);
CREATE INDEX idx_validations_validator ON human_validations(validator_id);
CREATE INDEX idx_validations_decision_type ON human_validations(validation_decision);
CREATE INDEX idx_validations_timestamp ON human_validations(timestamp);

CREATE TRIGGER update_validations_updated_at 
    BEFORE UPDATE ON human_validations 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
"""

# Create validation_metrics table for analytics
VALIDATION_METRICS_SCHEMA = """
CREATE TABLE IF NOT EXISTS validation_metrics (
    metric_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    metric_date DATE NOT NULL,
    total_decisions INTEGER DEFAULT 0,
    total_validations INTEGER DEFAULT 0,
    approval_rate DECIMAL(5,2) DEFAULT 0.0,
    average_confidence DECIMAL(3,2) DEFAULT 0.0,
    average_validation_score DECIMAL(2,1) DEFAULT 0.0,
    average_time_spent INTEGER DEFAULT 0,
    most_incorrect_routing VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(metric_date)
);

-- Indexes for analytics
CREATE INDEX idx_metrics_date ON validation_metrics(metric_date);

CREATE TRIGGER update_metrics_updated_at 
    BEFORE UPDATE ON validation_metrics 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
"""

# Create validator_performance table
VALIDATOR_PERFORMANCE_SCHEMA = """
CREATE TABLE IF NOT EXISTS validator_performance (
    performance_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    validator_id VARCHAR(255) NOT NULL,
    metric_date DATE NOT NULL,
    total_validations INTEGER DEFAULT 0,
    approval_decisions INTEGER DEFAULT 0,
    rejection_decisions INTEGER DEFAULT 0,
    correction_decisions INTEGER DEFAULT 0,
    escalation_decisions INTEGER DEFAULT 0,
    average_score DECIMAL(2,1) DEFAULT 0.0,
    average_time_spent INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(validator_id, metric_date)
);

-- Indexes for validator analytics
CREATE INDEX idx_validator_performance_validator ON validator_performance(validator_id);
CREATE INDEX idx_validator_performance_date ON validator_performance(metric_date);

CREATE TRIGGER update_validator_performance_updated_at 
    BEFORE UPDATE ON validator_performance 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
"""

# Create routing_accuracy table for tracking AI routing performance
ROUTING_ACCURACY_SCHEMA = """
CREATE TABLE IF NOT EXISTS routing_accuracy (
    accuracy_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    decision_id UUID NOT NULL REFERENCES ai_routing_decisions(decision_id),
    ai_routed_to VARCHAR(255) NOT NULL,
    human_routed_to VARCHAR(255),
    was_correct BOOLEAN,
    confidence_score DECIMAL(3,2),
    validation_decision VARCHAR(50),
    calculated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB
);

-- Indexes for accuracy tracking
CREATE INDEX idx_routing_accuracy_ai_routed ON routing_accuracy(ai_routed_to);
CREATE INDEX idx_routing_accuracy_human_routed ON routing_accuracy(human_routed_to);
CREATE INDEX idx_routing_accuracy_correct ON routing_accuracy(was_correct);
CREATE INDEX idx_routing_accuracy_decision ON routing_accuracy(decision_id);
"""

# Create full schema
FULL_SCHEMA = f"""
-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- AI Routing Decisions Table
{AI_ROUTING_DECISIONS_SCHEMA}

-- Feedback Records Table
{FEEDBACK_RECORDS_SCHEMA}

-- Human Validations Table
{HUMAN_VALIDATIONS_SCHEMA}

-- Validation Metrics Table
{VALIDATION_METRICS_SCHEMA}

-- Validator Performance Table
{VALIDATOR_PERFORMANCE_SCHEMA}

-- Routing Accuracy Table
{ROUTING_ACCURACY_SCHEMA}

-- Views for easier querying

-- View for feedback with validation details
CREATE OR REPLACE VIEW feedback_with_validations AS
SELECT 
    fr.feedback_id,
    fr.decision_id,
    ard.original_query,
    ard.ai_routed_to,
    ard.ai_confidence,
    ard.ai_reasoning,
    fr.feedback_type,
    fr.priority,
    fr.status,
    hv.validation_decision,
    hv.validation_score,
    hv.correct_routing,
    hv.validation_comments,
    hv.time_spent_seconds,
    hv.validator_id,
    fr.created_at,
    fr.updated_at
FROM feedback_records fr
JOIN ai_routing_decisions ard ON fr.decision_id = ard.decision_id
LEFT JOIN human_validations hv ON ard.decision_id = hv.decision_id;

-- View for validation statistics
CREATE OR REPLACE VIEW validation_statistics AS
SELECT 
    DATE(hv.timestamp) as validation_date,
    COUNT(*) as total_validations,
    COUNT(CASE WHEN hv.validation_decision = 'approved' THEN 1 END) as approvals,
    COUNT(CASE WHEN hv.validation_decision = 'rejected' THEN 1 END) as rejections,
    COUNT(CASE WHEN hv.validation_decision = 'corrected' THEN 1 END) as corrections,
    COUNT(CASE WHEN hv.validation_decision = 'escalated' THEN 1 END) as escalations,
    AVG(hv.validation_score) as average_score,
    AVG(hv.time_spent_seconds) as average_time_spent,
    AVG(ard.ai_confidence) as average_ai_confidence
FROM human_validations hv
JOIN ai_routing_decisions ard ON hv.decision_id = ard.decision_id
GROUP BY DATE(hv.timestamp)
ORDER BY validation_date DESC;

-- View for routing accuracy by category
CREATE OR REPLACE VIEW routing_accuracy_summary AS
SELECT 
    ai_routed_to,
    COUNT(*) as total_decisions,
    COUNT(CASE WHEN was_correct = true THEN 1 END) as correct_decisions,
    COUNT(CASE WHEN was_correct = false THEN 1 END) as incorrect_decisions,
    ROUND(COUNT(CASE WHEN was_correct = true THEN 1 END) * 100.0 / COUNT(*), 2) as accuracy_percentage,
    AVG(confidence_score) as average_confidence
FROM routing_accuracy
GROUP BY ai_routed_to
ORDER BY accuracy_percentage DESC;
"""

# Sample data for testing
SAMPLE_DATA = """
-- Insert sample AI routing decisions
INSERT INTO ai_routing_decisions (decision_id, original_query, ai_routed_to, ai_confidence, ai_reasoning, routing_criteria, context) VALUES
('550e8400-e29b-41d4-a716-446655440001', 'Need password reset', 'support_team', 0.95, 'Contains password reset keywords', '{"keywords": ["password", "reset"]}', '{"user_type": "employee"}'),
('550e8400-e29b-41d4-a716-446655440002', 'System is down', 'devops_team', 0.90, 'Infrastructure issue detected', '{"keywords": ["system", "down"]}', '{"severity": "high"}'),
('550e8400-e29b-41d4-a716-446655440003', 'Unauthorized access attempt', 'security_team', 0.98, 'Security incident keywords', '{"keywords": ["unauthorized", "access"]}', '{"severity": "critical"}'),
('550e8400-e29b-41d4-a716-446655440004', 'Bug in the application', 'development_team', 0.85, 'Application bug reported', '{"keywords": ["bug", "application"]}', '{"environment": "production"}'),
('550e8400-e29b-41d4-a716-446655440005', 'Performance issues', 'performance_team', 0.88, 'Performance degradation', '{"keywords": ["performance", "slow"]}', '{"impact": "high"}');

-- Insert sample feedback records
INSERT INTO feedback_records (feedback_id, decision_id, feedback_type, priority, status) VALUES
('650e8400-e29b-41d4-a716-446655440001', '550e8400-e29b-41d4-a716-446655440001', 'validation', 'low', 'pending'),
('650e8400-e29b-41d4-a716-446655440002', '550e8400-e29b-41d4-a716-446655440002', 'validation', 'high', 'validated'),
('650e8400-e29b-41d4-a716-446655440003', '550e8400-e29b-41d4-a716-446655440003', 'validation', 'critical', 'validated'),
('650e8400-e29b-41d4-a716-446655440004', '550e8400-e29b-41d4-a716-446655440004', 'validation', 'medium', 'needs_review'),
('650e8400-e29b-41d4-a716-446655440005', '550e8400-e29b-41d4-a716-446655440005', 'validation', 'high', 'pending');

-- Insert sample human validations
INSERT INTO human_validations (validation_id, decision_id, validator_id, validation_decision, validation_score, correct_routing, validation_comments, time_spent_seconds) VALUES
('750e8400-e29b-41d4-a716-446655440001', '550e8400-e29b-41d4-a716-446655440002', 'validator_001', 'approved', 5.0, NULL, 'Correct routing to devops', 30),
('750e8400-e29b-41d4-a716-446655440002', '550e8400-e29b-41d4-a716-446655440003', 'validator_002', 'approved', 4.8, NULL, 'Security team is correct', 45),
('750e8400-e29b-41d4-a716-446655440003', '550e8400-e29b-41d4-a716-446655440004', 'validator_003', 'corrected', 3.5, 'qa_team', 'This is a QA issue, not dev', 60);

-- Insert sample routing accuracy
INSERT INTO routing_accuracy (decision_id, ai_routed_to, human_routed_to, was_correct, confidence_score, validation_decision) VALUES
('550e8400-e29b-41d4-a716-446655440002', 'devops_team', 'devops_team', true, 0.90, 'approved'),
('550e8400-e29b-41d4-a716-446655440003', 'security_team', 'security_team', true, 0.98, 'approved'),
('550e8400-e29b-41d4-a716-446655440004', 'development_team', 'qa_team', false, 0.85, 'corrected');
"""

# Helper functions for schema management
SCHEMA_UTILS = """
-- Function to clean all feedback data (for testing)
CREATE OR REPLACE FUNCTION clean_feedback_data()
RETURNS void AS $$
BEGIN
    DELETE FROM routing_accuracy;
    DELETE FROM human_validations;
    DELETE FROM feedback_records;
    DELETE FROM validation_metrics;
    DELETE FROM validator_performance;
    DELETE FROM ai_routing_decisions;
END;
$$ LANGUAGE plpgsql;

-- Function to get next business day
CREATE OR REPLACE FUNCTION get_next_business_day(input_date DATE)
RETURNS DATE AS $$
DECLARE
    result_date DATE := input_date;
BEGIN
    WHILE EXTRACT(dow FROM result_date) IN (0, 6) LOOP
        result_date := result_date + INTERVAL '1 day';
    END LOOP;
    RETURN result_date;
END;
$$ LANGUAGE plpgsql;

-- Function to calculate validation rate
CREATE OR REPLACE FUNCTION calculate_validation_rate(
    start_date DATE,
    end_date DATE
) RETURNS DECIMAL AS $$
DECLARE
    total_decisions INTEGER;
    validated_decisions INTEGER;
    rate DECIMAL;
BEGIN
    SELECT COUNT(*) INTO total_decisions
    FROM ai_routing_decisions
    WHERE DATE(timestamp) BETWEEN start_date AND end_date;
    
    SELECT COUNT(*) INTO validated_decisions
    FROM human_validations hv
    WHERE DATE(hv.timestamp) BETWEEN start_date AND end_date;
    
    IF total_decisions = 0 THEN
        RETURN 0.0;
    END IF;
    
    rate := (validated_decisions::DECIMAL / total_decisions::DECIMAL) * 100;
    RETURN ROUND(rate, 2);
END;
$$ LANGUAGE plpgsql;
"""


def get_schema_sql(schema_type: str = "full") -> str:
    """
    Get SQL schema based on type
    
    Args:
        schema_type: Type of schema ('full', 'tables_only', 'sample_data', 'utils')
        
    Returns:
        SQL string for the requested schema
    """
    if schema_type == "full":
        return FULL_SCHEMA
    elif schema_type == "tables_only":
        return AI_ROUTING_DECISIONS_SCHEMA + "\n" + FEEDBACK_RECORDS_SCHEMA + "\n" + HUMAN_VALIDATIONS_SCHEMA + "\n" + VALIDATION_METRICS_SCHEMA + "\n" + VALIDATOR_PERFORMANCE_SCHEMA + "\n" + ROUTING_ACCURACY_SCHEMA
    elif schema_type == "sample_data":
        return SAMPLE_DATA
    elif schema_type == "utils":
        return SCHEMA_UTILS
    else:
        raise ValueError(f"Unknown schema type: {schema_type}")


# Migration management functions
def create_migration_sql(migration_name: str, sql_commands: List[str]) -> str:
    """
    Create a migration SQL file content
    
    Args:
        migration_name: Name of the migration
        sql_commands: List of SQL commands
        
    Returns:
        Formatted migration SQL
    """
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    migration_sql = f"-- Migration: {migration_name}\n"
    migration_sql += f"-- Created: {datetime.utcnow().isoformat()}\n\n"
    
    for i, command in enumerate(sql_commands, 1):
        migration_sql += f"-- Step {i}\n"
        migration_sql += command + "\n\n"
    
    return migration_sql


def execute_schema_setup(database_url: str, schema_type: str = "full") -> bool:
    """
    Execute schema setup (placeholder for actual execution)
    
    Args:
        database_url: Database connection URL
        schema_type: Type of schema to create
        
    Returns:
        True if successful, False otherwise
    """
    # In a real implementation, this would execute the SQL
    # using async database connections
    try:
        sql = get_schema_sql(schema_type)
        logger.info(f"Would execute schema setup: {schema_type}")
        logger.debug(f"SQL length: {len(sql)} characters")
        return True
    except Exception as e:
        logger.error(f"Schema setup failed: {e}")
        return False


# Example usage
if __name__ == "__main__":
    import logging
    
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    print("Feedback Service Database Schema")
    print("=" * 60)
    
    # Display available schema types
    print("\nAvailable schema types:")
    print("1. full - Complete schema with all tables and views")
    print("2. tables_only - Just the table definitions")
    print("3. sample_data - Sample data for testing")
    print("4. utils - Utility functions and procedures")
    
    # Display full schema
    print("\n" + "=" * 60)
    print("Full Schema SQL:")
    print("=" * 60)
    print(get_schema_sql("full"))
    
    print("\n" + "=" * 60)
    print("To set up the database:")
    print("1. Create a PostgreSQL database")
    print("2. Execute the SQL from get_schema_sql('full')")
    print("3. Optionally insert sample data using get_schema_sql('sample_data')")
    print("4. Use the feedback service with the database URL")
    print("=" * 60)
