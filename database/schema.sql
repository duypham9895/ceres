-- CERES Database Schema
-- Indonesian bank loan programs crawler

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Trigger function for auto-updating updated_at timestamps
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 1. Banks
CREATE TABLE banks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    bank_code VARCHAR(20) NOT NULL UNIQUE,
    bank_name VARCHAR(255) NOT NULL,
    name_indonesia VARCHAR(255),
    website_url VARCHAR(500),
    bank_category VARCHAR(30) NOT NULL CHECK (bank_category IN ('BUMN', 'SWASTA_NASIONAL', 'BPD', 'ASING', 'SYARIAH')),
    bank_type VARCHAR(20) NOT NULL CHECK (bank_type IN ('KONVENSIONAL', 'SYARIAH')),
    is_partner_ringkas BOOLEAN DEFAULT false,
    website_status VARCHAR(20) DEFAULT 'unknown',
    api_available BOOLEAN DEFAULT false,
    last_crawled_at TIMESTAMPTZ,
    crawl_streak INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TRIGGER banks_updated_at
    BEFORE UPDATE ON banks
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- 2. Bank Strategies
CREATE TABLE bank_strategies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    bank_id UUID NOT NULL REFERENCES banks(id) ON DELETE CASCADE,
    version INTEGER NOT NULL DEFAULT 1,
    anti_bot_detected BOOLEAN DEFAULT false,
    anti_bot_type VARCHAR(100),
    bypass_method VARCHAR(100),
    selectors JSONB DEFAULT '{}',
    loan_page_urls JSONB DEFAULT '[]',
    rate_limit_ms INTEGER DEFAULT 2000,
    success_rate NUMERIC(5, 2) DEFAULT 0.00,
    is_active BOOLEAN DEFAULT true,
    is_primary BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TRIGGER bank_strategies_updated_at
    BEFORE UPDATE ON bank_strategies
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE INDEX idx_bank_strategies_bank_id ON bank_strategies(bank_id);
CREATE INDEX idx_bank_strategies_active ON bank_strategies(is_active) WHERE is_active = true;

-- Only one primary active strategy per bank
CREATE UNIQUE INDEX idx_bank_strategies_primary_active
    ON bank_strategies(bank_id)
    WHERE (is_primary = true AND is_active = true);

-- 3. Loan Programs
CREATE TABLE loan_programs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    bank_id UUID NOT NULL REFERENCES banks(id) ON DELETE CASCADE,
    program_name VARCHAR(255) NOT NULL,
    loan_type VARCHAR(30) NOT NULL CHECK (loan_type IN (
        'KPR', 'KPA', 'KPT', 'MULTIGUNA', 'KENDARAAN',
        'MODAL_KERJA', 'INVESTASI', 'PENDIDIKAN', 'PMI',
        'TAKE_OVER', 'REFINANCING', 'OTHER'
    )),
    rate_fixed NUMERIC(6, 2),
    rate_floating NUMERIC(6, 2),
    rate_promo NUMERIC(6, 2),
    rate_promo_duration_months INTEGER,
    min_interest_rate NUMERIC(6, 2),
    max_interest_rate NUMERIC(6, 2),
    min_amount NUMERIC(15, 2),
    max_amount NUMERIC(15, 2),
    min_tenor_months INTEGER,
    max_tenor_months INTEGER,
    min_age INTEGER,
    max_age INTEGER,
    min_income NUMERIC(15, 2),
    employment_types JSONB DEFAULT '[]',
    required_documents JSONB DEFAULT '[]',
    admin_fee_pct NUMERIC(5, 2),
    provision_fee_pct NUMERIC(5, 2),
    insurance_required BOOLEAN,
    features JSONB DEFAULT '[]',
    data_confidence NUMERIC(5, 2) DEFAULT 0.00,
    completeness_score NUMERIC(5, 2) DEFAULT 0.00,
    raw_data JSONB DEFAULT '{}',
    is_latest BOOLEAN DEFAULT true,
    source_url VARCHAR(500),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TRIGGER loan_programs_updated_at
    BEFORE UPDATE ON loan_programs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE INDEX idx_loan_programs_bank_id ON loan_programs(bank_id);
CREATE INDEX idx_loan_programs_loan_type ON loan_programs(loan_type);
CREATE INDEX idx_loan_programs_latest ON loan_programs(is_latest) WHERE is_latest = true;

-- 4. Crawl Logs
CREATE TABLE crawl_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    bank_id UUID NOT NULL REFERENCES banks(id) ON DELETE CASCADE,
    strategy_id UUID REFERENCES bank_strategies(id) ON DELETE SET NULL,
    status VARCHAR(20) NOT NULL CHECK (status IN (
        'queued', 'running', 'success', 'partial', 'failed', 'blocked', 'timeout'
    )),
    programs_found INTEGER DEFAULT 0,
    programs_new INTEGER DEFAULT 0,
    programs_updated INTEGER DEFAULT 0,
    pages_crawled INTEGER DEFAULT 0,
    duration_ms INTEGER,
    error_type VARCHAR(100),
    error_message TEXT,
    error_stack TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TRIGGER crawl_logs_updated_at
    BEFORE UPDATE ON crawl_logs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE INDEX idx_crawl_logs_bank_id ON crawl_logs(bank_id);
CREATE INDEX idx_crawl_logs_strategy_id ON crawl_logs(strategy_id);
CREATE INDEX idx_crawl_logs_status ON crawl_logs(status);
CREATE INDEX idx_crawl_logs_created_at ON crawl_logs(created_at);

-- 5. Crawl Raw Data
CREATE TABLE crawl_raw_data (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    crawl_log_id UUID NOT NULL REFERENCES crawl_logs(id) ON DELETE CASCADE,
    bank_id UUID NOT NULL REFERENCES banks(id) ON DELETE CASCADE,
    page_url VARCHAR(500) NOT NULL,
    raw_html TEXT,
    parsed BOOLEAN DEFAULT false,
    programs_produced INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_crawl_raw_data_crawl_log_id ON crawl_raw_data(crawl_log_id);
CREATE INDEX idx_crawl_raw_data_bank_id ON crawl_raw_data(bank_id);

-- Partial index for unparsed rows
CREATE INDEX idx_crawl_raw_data_unparsed
    ON crawl_raw_data(bank_id)
    WHERE parsed = false;

-- 6. Strategy Feedback
CREATE TABLE strategy_feedback (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    strategy_id UUID NOT NULL REFERENCES bank_strategies(id) ON DELETE CASCADE,
    test_approach VARCHAR(255),
    result VARCHAR(20) NOT NULL CHECK (result IN ('success', 'partial', 'failure')),
    improvement_score NUMERIC(5, 2),
    recommended_changes JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_strategy_feedback_strategy_id ON strategy_feedback(strategy_id);

-- 7. Ringkas Recommendations
CREATE TABLE ringkas_recommendations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    rec_type VARCHAR(50) NOT NULL,
    priority INTEGER NOT NULL CHECK (priority >= 1 AND priority <= 5),
    impact_score NUMERIC(5, 2),
    title VARCHAR(255) NOT NULL,
    summary TEXT,
    suggested_actions JSONB DEFAULT '[]',
    status VARCHAR(20) DEFAULT 'pending',
    status_note VARCHAR(500),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TRIGGER ringkas_recommendations_updated_at
    BEFORE UPDATE ON ringkas_recommendations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- 8. Proxies
CREATE TABLE proxies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    proxy_url VARCHAR(500) NOT NULL UNIQUE,
    proxy_type VARCHAR(20) NOT NULL,
    country VARCHAR(5) DEFAULT 'ID',
    success_rate NUMERIC(5, 2) DEFAULT 100.00,
    status VARCHAR(20) DEFAULT 'active',
    rotation_weight NUMERIC(5, 2) DEFAULT 1.00,
    last_used_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TRIGGER proxies_updated_at
    BEFORE UPDATE ON proxies
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- 9. Agent Runs (observability tracking)
CREATE TABLE agent_runs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_name VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'running',
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    error_message TEXT,
    result JSONB,
    rows_written INTEGER DEFAULT 0
);

CREATE INDEX idx_agent_runs_agent_name ON agent_runs(agent_name, started_at DESC);

CREATE INDEX idx_proxies_status ON proxies(status);
