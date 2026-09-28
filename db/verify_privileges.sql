DO $$
BEGIN
    IF has_table_privilege('kops_worker', 'kops.documents', 'INSERT') THEN
        RAISE EXCEPTION 'worker unexpectedly has publication write authority';
    END IF;
    IF has_table_privilege('kops_worker', 'kops.sources', 'UPDATE') THEN
        RAISE EXCEPTION 'worker unexpectedly has policy/source administration authority';
    END IF;
    IF has_table_privilege('kops_publisher', 'kops.memberships', 'UPDATE') THEN
        RAISE EXCEPTION 'publisher unexpectedly has membership administration authority';
    END IF;
    IF has_table_privilege('kops_publisher', 'kops.audit_events', 'INSERT') THEN
        RAISE EXCEPTION 'publisher unexpectedly bypasses the audit collector';
    END IF;
    IF has_table_privilege('kops_audit', 'kops.audit_events', 'UPDATE')
       OR has_table_privilege('kops_audit', 'kops.audit_events', 'DELETE') THEN
        RAISE EXCEPTION 'audit collector can rewrite or delete audit events';
    END IF;
    IF has_table_privilege('kops_api', 'kops.page_versions', 'INSERT') THEN
        RAISE EXCEPTION 'API unexpectedly bypasses the sole publication writer';
    END IF;
    IF has_table_privilege('kops_content', 'kops.sources', 'UPDATE')
       OR has_table_privilege('kops_content', 'kops.page_versions', 'SELECT') THEN
        RAISE EXCEPTION 'content broker has authority beyond admitted source reads';
    END IF;
END $$;

SELECT 'database privilege boundaries verified' AS result;
