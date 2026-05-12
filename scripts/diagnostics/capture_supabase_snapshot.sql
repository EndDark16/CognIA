-- CognIA A4 diagnostic snapshot for Supabase/PostgreSQL.
-- Safety: no clinical payloads, no user emails, no questionnaire responses.
-- Usage example:
--   psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f scripts/diagnostics/capture_supabase_snapshot.sql > supabase_snapshot.txt

\echo 'timestamp_utc'
SELECT now() AT TIME ZONE 'UTC' AS timestamp_utc;

\echo 'server_version'
SELECT version();

\echo 'database_and_connection_limits'
SELECT
    current_database() AS database_name,
    current_user AS execution_user,
    (SELECT setting::int FROM pg_settings WHERE name = 'max_connections') AS max_connections,
    COUNT(*) FILTER (WHERE datname = current_database()) AS active_connections_current_db,
    COUNT(*) AS active_connections_all_dbs
FROM pg_stat_activity;

\echo 'pg_stat_activity_by_state'
SELECT
    COALESCE(state, 'unknown') AS state,
    COUNT(*) AS connections
FROM pg_stat_activity
GROUP BY COALESCE(state, 'unknown')
ORDER BY connections DESC;

\echo 'pg_stat_activity_wait_events'
SELECT
    COALESCE(wait_event_type, 'none') AS wait_event_type,
    COALESCE(wait_event, 'none') AS wait_event,
    COUNT(*) AS waiting_connections
FROM pg_stat_activity
GROUP BY COALESCE(wait_event_type, 'none'), COALESCE(wait_event, 'none')
ORDER BY waiting_connections DESC, wait_event_type, wait_event;

\echo 'long_running_activity_safe'
SELECT
    pid,
    usename,
    application_name,
    state,
    NOW() - query_start AS query_age,
    wait_event_type,
    wait_event,
    md5(COALESCE(query, '')) AS query_hash,
    LEFT(REGEXP_REPLACE(COALESCE(query, ''), '\s+', ' ', 'g'), 160) AS query_truncated
FROM pg_stat_activity
WHERE datname = current_database()
  AND query_start IS NOT NULL
  AND pid <> pg_backend_pid()
ORDER BY query_age DESC
LIMIT 25;

\echo 'lock_inventory'
SELECT
    l.locktype,
    l.mode,
    l.granted,
    COUNT(*) AS lock_count
FROM pg_locks l
GROUP BY l.locktype, l.mode, l.granted
ORDER BY lock_count DESC, l.locktype, l.mode;

\echo 'blocking_relationships'
SELECT
    a.pid AS blocked_pid,
    a.usename AS blocked_user,
    ka.pid AS blocking_pid,
    ka.usename AS blocking_user,
    a.wait_event_type AS blocked_wait_type,
    a.wait_event AS blocked_wait_event,
    NOW() - a.query_start AS blocked_query_age,
    LEFT(REGEXP_REPLACE(COALESCE(a.query, ''), '\s+', ' ', 'g'), 120) AS blocked_query_truncated
FROM pg_catalog.pg_locks bl
JOIN pg_catalog.pg_stat_activity a ON a.pid = bl.pid
JOIN pg_catalog.pg_locks kl
  ON kl.locktype = bl.locktype
 AND kl.database IS NOT DISTINCT FROM bl.database
 AND kl.relation IS NOT DISTINCT FROM bl.relation
 AND kl.page IS NOT DISTINCT FROM bl.page
 AND kl.tuple IS NOT DISTINCT FROM bl.tuple
 AND kl.virtualxid IS NOT DISTINCT FROM bl.virtualxid
 AND kl.transactionid IS NOT DISTINCT FROM bl.transactionid
 AND kl.classid IS NOT DISTINCT FROM bl.classid
 AND kl.objid IS NOT DISTINCT FROM bl.objid
 AND kl.objsubid IS NOT DISTINCT FROM bl.objsubid
 AND kl.pid <> bl.pid
JOIN pg_catalog.pg_stat_activity ka ON ka.pid = kl.pid
WHERE NOT bl.granted
ORDER BY blocked_query_age DESC
LIMIT 25;

\echo 'pg_stat_database_current'
SELECT
    datname,
    numbackends,
    xact_commit,
    xact_rollback,
    blks_read,
    blks_hit,
    tup_returned,
    tup_fetched,
    tup_inserted,
    tup_updated,
    tup_deleted,
    temp_files,
    temp_bytes,
    deadlocks,
    checksum_failures,
    blk_read_time,
    blk_write_time,
    stats_reset
FROM pg_stat_database
WHERE datname = current_database();

\echo 'pg_stat_statements_available'
SELECT EXISTS (
    SELECT 1
    FROM pg_extension
    WHERE extname = 'pg_stat_statements'
) AS pg_stat_statements_enabled;

-- Optional: execute only when pg_stat_statements exists and permissions allow.
-- SELECT
--     calls,
--     total_exec_time,
--     mean_exec_time,
--     rows,
--     shared_blks_hit,
--     shared_blks_read,
--     temp_blks_read,
--     temp_blks_written,
--     md5(query) AS query_hash,
--     LEFT(REGEXP_REPLACE(query, '\s+', ' ', 'g'), 160) AS query_truncated
-- FROM pg_stat_statements
-- ORDER BY total_exec_time DESC
-- LIMIT 25;
