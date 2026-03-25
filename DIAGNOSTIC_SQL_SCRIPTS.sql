-- =============================================================================
-- DIAGNOSTIC SQL SCRIPTS FOR SUPABASE DATABASE
-- =============================================================================
-- Run these scripts in Supabase SQL Editor to diagnose issues.
-- =============================================================================

-- ============================================================================
-- STEP 1: CHECK IF ALL REQUIRED TABLES EXIST
-- ============================================================================
-- This query lists all tables in the public schema

SELECT
    table_name,
    table_type
FROM information_schema.tables
WHERE table_schema = 'public'
ORDER BY table_name;

-- Expected tables for chat functionality:
-- - agent_chat_sessions
-- - agent_chat_events
-- - sys_user (or similar user table)
-- - agent_connectors (for Google Drive)


-- ============================================================================
-- STEP 2: CHECK agent_chat_sessions TABLE STRUCTURE
-- ============================================================================

SELECT
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_name = 'agent_chat_sessions'
ORDER BY ordinal_position;


-- ============================================================================
-- STEP 3: COUNT RECORDS IN KEY TABLES
-- ============================================================================

SELECT 'sys_user' as table_name, COUNT(*) as row_count FROM sys_user
UNION ALL
SELECT 'agent_chat_sessions', COUNT(*) FROM agent_chat_sessions
UNION ALL
SELECT 'agent_chat_events', COUNT(*) FROM agent_chat_events;


-- ============================================================================
-- STEP 4: VIEW ALL CHAT SESSIONS (MOST RECENT FIRST)
-- ============================================================================

SELECT
    id,
    uuid,
    user_id,
    name,
    status,
    agent_type,
    message_count,
    created_time,
    updated_time,
    deleted_at
FROM agent_chat_sessions
ORDER BY created_time DESC
LIMIT 20;


-- ============================================================================
-- STEP 5: VIEW YOUR SPECIFIC USER'S SESSIONS
-- ============================================================================
-- First, find your user_id by email or username

SELECT id, username, email, nickname FROM sys_user
WHERE email LIKE '%YOUR_EMAIL%'
   OR username LIKE '%YOUR_USERNAME%'
LIMIT 5;

-- Then view sessions for that user (replace YOUR_USER_ID with actual ID)
-- Uncomment and modify the query below:

-- SELECT
--     uuid,
--     name,
--     status,
--     agent_type,
--     message_count,
--     created_time
-- FROM agent_chat_sessions
-- WHERE user_id = YOUR_USER_ID
--   AND deleted_at IS NULL
-- ORDER BY created_time DESC;


-- ============================================================================
-- STEP 6: CHECK IF agent_chat_sessions TABLE EXISTS (ALTERNATIVE)
-- ============================================================================

SELECT EXISTS (
    SELECT FROM pg_tables
    WHERE schemaname = 'public'
    AND tablename = 'agent_chat_sessions'
) as table_exists;


-- ============================================================================
-- STEP 7: CHECK CONNECTORS TABLE (for Google Drive)
-- ============================================================================

SELECT
    column_name,
    data_type
FROM information_schema.columns
WHERE table_name = 'agent_connectors'
ORDER BY ordinal_position;

-- View all connectors
SELECT
    id,
    user_id,
    connector_type,
    token_expiry,
    created_time
FROM agent_connectors
ORDER BY created_time DESC
LIMIT 10;


-- ============================================================================
-- STEP 8: CHECK IF SESSIONS ARE BEING CREATED PROPERLY
-- ============================================================================
-- This checks for any sessions created in the last 24 hours

SELECT
    uuid,
    user_id,
    name,
    status,
    agent_type,
    created_time
FROM agent_chat_sessions
WHERE created_time > NOW() - INTERVAL '24 hours'
ORDER BY created_time DESC;


-- ============================================================================
-- STEP 9: CHECK FOR ORPHANED/PROBLEMATIC SESSIONS
-- ============================================================================
-- Sessions without a valid user_id

SELECT
    cs.uuid,
    cs.user_id,
    cs.name,
    cs.created_time
FROM agent_chat_sessions cs
LEFT JOIN sys_user u ON cs.user_id = u.id
WHERE u.id IS NULL;


-- ============================================================================
-- STEP 10: CHECK USER TABLE STRUCTURE
-- ============================================================================

SELECT
    column_name,
    data_type,
    is_nullable
FROM information_schema.columns
WHERE table_name = 'sys_user'
ORDER BY ordinal_position;


-- ============================================================================
-- STEP 11: DEBUG - Check a specific session UUID
-- ============================================================================
-- Replace 'YOUR_SESSION_UUID' with the actual UUID from your 404 error

-- SELECT * FROM agent_chat_sessions
-- WHERE uuid = 'YOUR_SESSION_UUID';


-- ============================================================================
-- STEP 12: Check if migrations have run properly
-- ============================================================================

SELECT version_num, installed_on
FROM alembic_version
ORDER BY installed_on DESC
LIMIT 5;


-- ============================================================================
-- QUICK SUMMARY QUERY - RUN THIS FIRST
-- ============================================================================
-- This gives you a quick overview of the database state

SELECT
    'Tables' as category,
    (SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public')::text as count
UNION ALL
SELECT 'Users', COUNT(*)::text FROM sys_user
UNION ALL
SELECT 'Chat Sessions', COUNT(*)::text FROM agent_chat_sessions
UNION ALL
SELECT 'Chat Events', COUNT(*)::text FROM agent_chat_events
UNION ALL
SELECT 'Active Sessions', COUNT(*)::text FROM agent_chat_sessions WHERE status = 'active' AND deleted_at IS NULL;
