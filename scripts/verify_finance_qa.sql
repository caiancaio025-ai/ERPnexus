SELECT 'financial_entries' AS table_name, COUNT(*) AS records FROM financial_entries
UNION ALL
SELECT 'financial_transfers', COUNT(*) FROM financial_transfers
UNION ALL
SELECT 'financial_audit_events', COUNT(*) FROM financial_audit_events;
