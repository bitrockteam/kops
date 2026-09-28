BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE SCHEMA IF NOT EXISTS kops AUTHORIZATION kops_owner;
SET search_path TO kops, public;

CREATE TABLE IF NOT EXISTS personas (
    subject_id text PRIMARY KEY,
    display_name text NOT NULL,
    action_grants jsonb NOT NULL DEFAULT '[]'::jsonb,
    is_operator boolean NOT NULL DEFAULT false,
    active boolean NOT NULL DEFAULT true
);

CREATE TABLE IF NOT EXISTS memberships (
    subject_id text NOT NULL REFERENCES personas(subject_id),
    group_id text NOT NULL,
    active boolean NOT NULL DEFAULT true,
    revision bigint NOT NULL DEFAULT 1,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (subject_id, group_id)
);

CREATE TABLE IF NOT EXISTS audiences (
    audience_id text PRIMARY KEY,
    display_name text NOT NULL,
    required_groups jsonb NOT NULL,
    policy_revision bigint NOT NULL DEFAULT 1,
    active boolean NOT NULL DEFAULT true,
    CHECK (jsonb_typeof(required_groups) = 'array'),
    CHECK (jsonb_array_length(required_groups) BETWEEN 1 AND 4)
);

CREATE TABLE IF NOT EXISTS model_configs (
    config_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    revision bigint GENERATED ALWAYS AS IDENTITY UNIQUE,
    adapter text NOT NULL CHECK (adapter IN ('openai', 'ollama')),
    endpoint text NOT NULL,
    model_name text NOT NULL,
    limits jsonb NOT NULL,
    connection_status text NOT NULL CHECK (connection_status IN ('untested', 'reachable', 'failed')),
    diagnostic text,
    created_by text NOT NULL REFERENCES personas(subject_id),
    created_at timestamptz NOT NULL DEFAULT now(),
    active boolean NOT NULL DEFAULT true
);
CREATE UNIQUE INDEX IF NOT EXISTS one_active_model_config ON model_configs(active) WHERE active;

CREATE TABLE IF NOT EXISTS sources (
    source_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    title text NOT NULL,
    audience_id text NOT NULL REFERENCES audiences(audience_id),
    current_revision bigint NOT NULL DEFAULT 0,
    policy_revision bigint NOT NULL DEFAULT 1,
    synthetic boolean NOT NULL DEFAULT false,
    created_by text NOT NULL REFERENCES personas(subject_id),
    created_at timestamptz NOT NULL DEFAULT now(),
    active boolean NOT NULL DEFAULT true
);

CREATE TABLE IF NOT EXISTS source_versions (
    source_id uuid NOT NULL REFERENCES sources(source_id),
    revision bigint NOT NULL,
    object_key text NOT NULL,
    content_hash text NOT NULL CHECK (length(content_hash) = 64),
    origin text NOT NULL,
    created_by text NOT NULL REFERENCES personas(subject_id),
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (source_id, revision),
    UNIQUE (object_key)
);

CREATE TABLE IF NOT EXISTS runs (
    run_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    label text NOT NULL,
    created_by text NOT NULL REFERENCES personas(subject_id),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS jobs (
    job_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id uuid NOT NULL REFERENCES runs(run_id),
    requested_by text NOT NULL REFERENCES personas(subject_id),
    workload_principal text NOT NULL DEFAULT 'compilation-worker',
    audience_id text NOT NULL REFERENCES audiences(audience_id),
    task_text text NOT NULL,
    model_config_snapshot jsonb,
    model_config_revision bigint,
    limits jsonb NOT NULL,
    status text NOT NULL CHECK (status IN ('queued', 'running', 'cancelled', 'failed', 'blocked', 'ready')),
    cancel_requested boolean NOT NULL DEFAULT false,
    error_code text,
    error_sanitized text,
    input_bytes bigint NOT NULL DEFAULT 0,
    output_bytes bigint NOT NULL DEFAULT 0,
    model_latency_ms bigint,
    started_at timestamptz,
    completed_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS one_active_compilation ON jobs ((1))
    WHERE status IN ('queued', 'running');

CREATE TABLE IF NOT EXISTS job_inputs (
    job_id uuid NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE,
    source_id uuid NOT NULL,
    source_revision bigint NOT NULL,
    source_policy_revision bigint NOT NULL,
    object_key text NOT NULL,
    content_hash text NOT NULL,
    admission_decision text NOT NULL,
    PRIMARY KEY (job_id, source_id),
    FOREIGN KEY (source_id, source_revision) REFERENCES source_versions(source_id, revision)
);

CREATE TABLE IF NOT EXISTS job_events (
    event_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    job_id uuid NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE,
    state text NOT NULL,
    detail text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS candidates (
    candidate_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id uuid NOT NULL REFERENCES jobs(job_id),
    audience_id text NOT NULL REFERENCES audiences(audience_id),
    candidate_hash text NOT NULL CHECK (length(candidate_hash) = 64),
    manifest_hash text NOT NULL CHECK (length(manifest_hash) = 64),
    payload jsonb NOT NULL,
    validation_findings jsonb NOT NULL DEFAULT '[]'::jsonb,
    state text NOT NULL CHECK (state IN ('draft', 'independently_verified', 'authorized', 'published', 'stale', 'blocked', 'superseded', 'rejected')),
    created_by text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS verifications (
    verification_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    candidate_id uuid NOT NULL REFERENCES candidates(candidate_id),
    candidate_hash text NOT NULL,
    reviewer_id text NOT NULL REFERENCES personas(subject_id),
    decision text NOT NULL CHECK (decision IN ('verified', 'rejected')),
    findings jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS publication_authorizations (
    authorization_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    candidate_id uuid NOT NULL REFERENCES candidates(candidate_id),
    candidate_hash text NOT NULL,
    audience_id text NOT NULL REFERENCES audiences(audience_id),
    authorized_by text NOT NULL REFERENCES personas(subject_id),
    expected_versions jsonb NOT NULL,
    dependency_revisions jsonb NOT NULL,
    policy_revisions jsonb NOT NULL,
    expires_at timestamptz NOT NULL,
    status text NOT NULL CHECK (status IN ('active', 'consumed', 'invalidated', 'expired')),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS operations (
    operation_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    authorization_id uuid NOT NULL REFERENCES publication_authorizations(authorization_id),
    operation_type text NOT NULL CHECK (operation_type IN ('publish_document', 'apply_document_edit', 'block_document')),
    idempotency_key text NOT NULL UNIQUE,
    requested_by text NOT NULL REFERENCES personas(subject_id),
    status text NOT NULL CHECK (status IN ('pending', 'executing', 'committed', 'refused', 'uncertain')),
    result jsonb,
    error_code text,
    created_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz
);

CREATE TABLE IF NOT EXISTS documents (
    document_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    slug text NOT NULL,
    title text NOT NULL,
    audience_id text NOT NULL REFERENCES audiences(audience_id),
    current_version bigint NOT NULL DEFAULT 0,
    publication_state text NOT NULL CHECK (publication_state IN ('published', 'stale', 'blocked', 'superseded')),
    UNIQUE (audience_id, slug)
);

CREATE TABLE IF NOT EXISTS page_versions (
    document_id uuid NOT NULL REFERENCES documents(document_id),
    version bigint NOT NULL,
    candidate_id uuid NOT NULL REFERENCES candidates(candidate_id),
    title text NOT NULL,
    object_key text NOT NULL,
    content_hash text NOT NULL,
    published_by text NOT NULL,
    operation_id uuid NOT NULL REFERENCES operations(operation_id),
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (document_id, version),
    UNIQUE (operation_id, document_id)
);

CREATE TABLE IF NOT EXISTS dependencies (
    document_id uuid NOT NULL,
    document_version bigint NOT NULL,
    source_id uuid NOT NULL,
    source_revision bigint NOT NULL,
    source_policy_revision bigint NOT NULL,
    PRIMARY KEY (document_id, document_version, source_id),
    FOREIGN KEY (document_id, document_version) REFERENCES page_versions(document_id, version),
    FOREIGN KEY (source_id, source_revision) REFERENCES source_versions(source_id, revision)
);

CREATE TABLE IF NOT EXISTS query_responses (
    response_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id uuid NOT NULL REFERENCES runs(run_id),
    subject_id text NOT NULL REFERENCES personas(subject_id),
    audience_id text NOT NULL REFERENCES audiences(audience_id),
    question text NOT NULL,
    answer_object_key text,
    answer_hash text,
    citations jsonb NOT NULL,
    evaluation text NOT NULL CHECK (evaluation IN ('supported', 'contradictory', 'unsupported', 'failed')),
    model_config_revision bigint,
    error_sanitized text,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS demo_controls (
    control_name text PRIMARY KEY,
    enabled boolean NOT NULL,
    updated_by text,
    updated_at timestamptz NOT NULL DEFAULT now()
);
INSERT INTO demo_controls(control_name, enabled) VALUES ('audit_available', true)
ON CONFLICT (control_name) DO NOTHING;

CREATE TABLE IF NOT EXISTS audit_events (
    event_id uuid PRIMARY KEY,
    correlation_id text NOT NULL,
    occurred_at timestamptz NOT NULL DEFAULT now(),
    initiator text,
    actor text NOT NULL,
    delegation_ref text,
    action text NOT NULL,
    resource_type text NOT NULL,
    resource_id text,
    audience_id text,
    decision text NOT NULL,
    reason_code text NOT NULL,
    policy_revision bigint,
    outcome text NOT NULL,
    authorization_ref text,
    operation_ref text,
    details jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS audit_outbox (
    outbox_id uuid PRIMARY KEY,
    operation_id uuid NOT NULL REFERENCES operations(operation_id),
    event_payload jsonb NOT NULL,
    delivery_status text NOT NULL CHECK (delivery_status IN ('pending', 'delivered', 'failed')),
    created_at timestamptz NOT NULL DEFAULT now(),
    delivered_at timestamptz
);

CREATE OR REPLACE FUNCTION kops.invalidate_for_source_change() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = kops, pg_temp AS $$
BEGIN
    IF NEW.policy_revision IS DISTINCT FROM OLD.policy_revision
       OR NEW.audience_id IS DISTINCT FROM OLD.audience_id THEN
        UPDATE documents d SET publication_state = 'blocked'
        WHERE EXISTS (
            SELECT 1 FROM dependencies dep
            WHERE dep.document_id = d.document_id AND dep.document_version = d.current_version
              AND dep.source_id = NEW.source_id
        );
        UPDATE candidates SET state = 'blocked'
        WHERE state IN ('draft', 'independently_verified', 'authorized')
          AND job_id IN (SELECT job_id FROM job_inputs WHERE source_id = NEW.source_id);
    ELSIF NEW.current_revision IS DISTINCT FROM OLD.current_revision THEN
        UPDATE documents d SET publication_state = 'stale'
        WHERE EXISTS (
            SELECT 1 FROM dependencies dep
            WHERE dep.document_id = d.document_id AND dep.document_version = d.current_version
              AND dep.source_id = NEW.source_id
        );
        UPDATE candidates SET state = 'stale'
        WHERE state IN ('draft', 'independently_verified', 'authorized')
          AND job_id IN (SELECT job_id FROM job_inputs WHERE source_id = NEW.source_id);
    END IF;
    IF NEW.policy_revision IS DISTINCT FROM OLD.policy_revision
       OR NEW.audience_id IS DISTINCT FROM OLD.audience_id
       OR NEW.current_revision IS DISTINCT FROM OLD.current_revision THEN
        UPDATE publication_authorizations pa SET status = 'invalidated'
        WHERE status = 'active' AND candidate_id IN (
            SELECT c.candidate_id FROM candidates c
            JOIN job_inputs ji ON ji.job_id = c.job_id WHERE ji.source_id = NEW.source_id
        );
    END IF;
    RETURN NEW;
END $$;

DROP TRIGGER IF EXISTS source_change_invalidation ON kops.sources;
CREATE TRIGGER source_change_invalidation
AFTER UPDATE OF audience_id, policy_revision, current_revision ON kops.sources
FOR EACH ROW EXECUTE FUNCTION kops.invalidate_for_source_change();

CREATE OR REPLACE FUNCTION kops.invalidate_for_audience_change() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = kops, pg_temp AS $$
BEGIN
    IF NEW.policy_revision IS DISTINCT FROM OLD.policy_revision
       OR NEW.required_groups IS DISTINCT FROM OLD.required_groups THEN
        UPDATE documents SET publication_state = 'blocked' WHERE audience_id = NEW.audience_id;
        UPDATE candidates SET state = 'blocked'
        WHERE audience_id = NEW.audience_id AND state IN ('draft', 'independently_verified', 'authorized');
        UPDATE publication_authorizations SET status = 'invalidated'
        WHERE audience_id = NEW.audience_id AND status = 'active';
    END IF;
    RETURN NEW;
END $$;

DROP TRIGGER IF EXISTS audience_change_invalidation ON kops.audiences;
CREATE TRIGGER audience_change_invalidation
AFTER UPDATE OF policy_revision, required_groups ON kops.audiences
FOR EACH ROW EXECUTE FUNCTION kops.invalidate_for_audience_change();

DO $$
DECLARE item record;
BEGIN
    FOR item IN SELECT tablename FROM pg_tables WHERE schemaname = 'kops' LOOP
        EXECUTE format('ALTER TABLE kops.%I OWNER TO kops_owner', item.tablename);
    END LOOP;
    FOR item IN SELECT sequencename FROM pg_sequences WHERE schemaname = 'kops' LOOP
        EXECUTE format('ALTER SEQUENCE kops.%I OWNER TO kops_owner', item.sequencename);
    END LOOP;
END $$;

REVOKE ALL ON SCHEMA kops FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA kops FROM PUBLIC;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA kops FROM PUBLIC;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA kops FROM PUBLIC;

GRANT USAGE ON SCHEMA kops TO kops_api, kops_worker, kops_publisher, kops_audit, kops_content;

GRANT SELECT, INSERT, UPDATE ON personas, memberships, audiences, model_configs, sources,
    source_versions, runs, jobs, job_inputs, job_events, candidates, verifications,
    publication_authorizations, operations, query_responses, demo_controls TO kops_api;
GRANT SELECT ON documents, page_versions, dependencies, audit_events, audit_outbox TO kops_api;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA kops TO kops_api;

GRANT SELECT ON personas, memberships, audiences, model_configs, sources, source_versions,
    runs, job_inputs, demo_controls TO kops_worker;
GRANT SELECT, UPDATE ON jobs TO kops_worker;
GRANT SELECT, INSERT ON candidates, job_events TO kops_worker;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA kops TO kops_worker;

GRANT SELECT ON personas, memberships, audiences, sources, source_versions, jobs, job_inputs,
    candidates, verifications, publication_authorizations, demo_controls, documents,
    page_versions, dependencies, audit_outbox TO kops_publisher;
GRANT SELECT, UPDATE ON operations TO kops_publisher;
GRANT INSERT, UPDATE ON documents, page_versions, dependencies, audit_outbox TO kops_publisher;
GRANT UPDATE ON publication_authorizations, candidates TO kops_publisher;
GRANT INSERT ON job_events TO kops_publisher;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA kops TO kops_publisher;

GRANT SELECT ON demo_controls TO kops_audit;
GRANT INSERT ON audit_events TO kops_audit;

GRANT SELECT ON jobs, job_inputs, sources, source_versions TO kops_content;

COMMIT;
