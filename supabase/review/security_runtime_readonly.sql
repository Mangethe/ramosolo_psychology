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
       count(*) FILTER(WHERE has_table_privilege(r.rolname,c.oid,'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')
          OR has_any_column_privilege(r.rolname,c.oid,'SELECT,INSERT,UPDATE,REFERENCES')) AS relations_with_grants
FROM pg_roles r CROSS JOIN pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
WHERE n.nspname='ramosolo' AND c.relkind IN ('r','p','v','m','f')
  AND r.rolname IN ('anon','authenticated','service_role','authenticator')
GROUP BY r.rolname ORDER BY r.rolname;

SELECT r.rolname, 'sequence' AS object_kind, c.relname AS object_name
FROM pg_roles r CROSS JOIN pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
WHERE n.nspname='ramosolo' AND c.relkind='S'
  AND r.rolname IN ('anon','authenticated','service_role','authenticator')
  AND has_sequence_privilege(r.oid,c.oid,'USAGE,SELECT,UPDATE')
UNION ALL
SELECT r.rolname, 'routine', p.oid::regprocedure::text
FROM pg_roles r CROSS JOIN pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
WHERE n.nspname='ramosolo'
  AND r.rolname IN ('anon','authenticated','service_role','authenticator')
  AND has_function_privilege(r.oid,p.oid,'EXECUTE')
ORDER BY 1,2,3;

-- Review both schema-specific and global defaults of each actual object creator.
SELECT pg_get_userbyid(d.defaclrole) AS object_creator, n.nspname, d.defaclobjtype,
       CASE a.grantee WHEN 0 THEN 'PUBLIC' ELSE pg_get_userbyid(a.grantee) END AS grantee,
       a.privilege_type, a.is_grantable
FROM pg_default_acl d LEFT JOIN pg_namespace n ON n.oid=d.defaclnamespace
CROSS JOIN LATERAL aclexplode(d.defaclacl) a
WHERE n.nspname='ramosolo' OR d.defaclnamespace=0
ORDER BY 1,2,3,4,5;

SELECT pubname, schemaname, tablename FROM pg_publication_tables
WHERE schemaname='ramosolo' ORDER BY 1,3;
