-- Run through the existing protected connection AS THE DEPLOYED APPLICATION ROLE.
-- SELECT only. Never paste connection URLs or passwords into a result/report.
-- Running through the management connector identifies the connector, not Flask.
SELECT current_user AS effective_role, session_user AS connection_role,
       r.rolsuper, r.rolbypassrls, r.rolcreaterole, r.rolcreatedb
FROM pg_roles r WHERE r.rolname=current_user;

SELECT n.nspname, c.relname, c.relrowsecurity, c.relforcerowsecurity,
       pg_get_userbyid(c.relowner)=current_user AS runtime_owns_table,
       has_table_privilege(current_user,c.oid,'SELECT') AS can_select,
       has_table_privilege(current_user,c.oid,'INSERT') AS can_insert,
       has_table_privilege(current_user,c.oid,'UPDATE') AS can_update,
       has_table_privilege(current_user,c.oid,'DELETE') AS can_delete,
       has_table_privilege(current_user,c.oid,'TRUNCATE') AS can_truncate
FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
WHERE n.nspname='ramosolo' AND c.relkind IN ('r','p','v','m')
ORDER BY c.relname;

SELECT r.rolname, has_schema_privilege(r.rolname,'ramosolo','USAGE') AS schema_usage,
       has_schema_privilege(r.rolname,'ramosolo','CREATE') AS schema_create,
       count(*) FILTER(WHERE has_table_privilege(r.rolname,c.oid,'SELECT,INSERT,UPDATE,DELETE')) AS accessible_tables
FROM pg_roles r CROSS JOIN pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
WHERE n.nspname='ramosolo' AND c.relkind='r'
  AND r.rolname IN ('anon','authenticated','service_role','authenticator')
GROUP BY r.rolname ORDER BY r.rolname;
