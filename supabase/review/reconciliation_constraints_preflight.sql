-- Run against the ledger 1–6 baseline before reviewing migration 010 for execution.
-- This read-only check covers the definition fingerprint on both PostgreSQL majors.
BEGIN READ ONLY;
SET LOCAL search_path TO public;

DO $preflight$
DECLARE
    fingerprint text;
BEGIN
    SELECT md5(coalesce(string_agg(
        'V' || octet_length(convert_to(signature, 'UTF8')) || ':' || signature,
        '' ORDER BY signature COLLATE "C"), ''))
    INTO fingerprint
    FROM (
        SELECT string_agg(CASE WHEN field IS NULL THEN 'N;' ELSE
            'V' || octet_length(convert_to(field, 'UTF8')) || ':' || field END,
            '' ORDER BY position) AS signature
        FROM pg_constraint AS c
        JOIN pg_class AS t ON t.oid = c.conrelid
        CROSS JOIN LATERAL unnest(ARRAY[t.relname::text, c.conname::text, c.contype::text,
            pg_get_constraintdef(c.oid), c.condeferrable::text, c.condeferred::text,
            c.convalidated::text]) WITH ORDINALITY AS fields(field, position)
        WHERE t.relnamespace = 'ramosolo'::regnamespace AND c.contype <> 'n'
        GROUP BY c.oid
    ) AS constraint_rows;

    IF fingerprint NOT IN ('6e42b7f83cb9357f5abc713146cc4d22', '0ecc63c7f166d59e8d2a4c94de7aa685') THEN
        RAISE EXCEPTION 'Existing constraint definition drift';
    END IF;
END;
$preflight$;

COMMIT;
