"""Generate the local-only forward reconciliation draft from reviewed migrations.

Generation reads migration sources, the metadata-only production catalog fixture,
and the current ORM metadata. It never connects to a database.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from verification.constraint_fingerprint import (
    constraint_fingerprint,
    ordered_constraint_records,
    sql_constraint_fingerprint_expression,
    sql_constraint_rows,
)

FILES = ROOT / "migrations"
CATALOG = ROOT / "tests" / "fixtures" / "ramosolo_live_catalog.json"
FIXTURE_PROFILE = ROOT / "tests" / "fixtures" / "ramosolo_pg17_fixture_profile.json"
TARGET = FILES / "010_ramosolo_live_reconciliation_draft.sql"


def block(path: Path, start: str, end: str) -> str:
    source = path.read_text(encoding="utf-8")
    return source[source.index(start):source.index(end)]


def literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def sql_array(values: list[str]) -> str:
    return "ARRAY[" + ",".join(literal(value) for value in values) + "]::text[]"


def body_md5(definition: str) -> str:
    match = re.search(r"AS\s+(\$[a-zA-Z_0-9]*\$)(.*?)\1\s*;?\s*$", definition, re.S | re.I)
    if not match:
        raise ValueError("Unable to extract PostgreSQL routine body")
    return hashlib.md5(match.group(2).encode("utf-8")).hexdigest()


def main() -> None:
    catalog_doc = json.loads(CATALOG.read_text(encoding="utf-8"))
    if catalog_doc.get("schema") != "ramosolo" or "no table rows" not in catalog_doc.get("source", ""):
        raise ValueError("Expected the reviewed metadata-only production snapshot")
    catalog = catalog_doc["snapshot"]
    fixture_profile = json.loads(FIXTURE_PROFILE.read_text(encoding="utf-8"))
    if fixture_profile.get("server_version_num") != 170011:
        raise ValueError("Expected the reviewed PostgreSQL 17.11 synthetic fixture profile")
    fixture_constraint_md5 = fixture_profile["constraint_fingerprint"]

    chunks = [
        block(FILES / "007_ramosolo_care_foundation.sql", "CREATE TABLE care_plans", "INSERT INTO schema_versions(version) VALUES (7);"),
        block(FILES / "008_ramosolo_care_coordination.sql", "CREATE UNIQUE INDEX IF NOT EXISTS admission_patient_identity", "INSERT INTO schema_versions(version) VALUES (8);"),
        block(FILES / "009_assistant_calendar.sql", "CREATE TABLE IF NOT EXISTS calendar_delegations", "INSERT INTO schema_versions(version) VALUES (9);"),
    ]
    target_tables = [
        "appointment_proposals", "calendar_delegations", "calendar_history", "care_plan_reviews",
        "care_plans", "care_referrals", "care_review_signoffs", "clinical_records",
        "communication_decisions", "continuity_events", "continuity_history",
        "continuity_notifications", "coordination_coverage", "coordination_history",
        "coordination_policies", "discharge_followups", "external_practitioners",
        "nursing_observations", "patient_permissions", "patient_preferences",
        "referral_clinical_records",
    ]
    target_sequences = [f"{table}_id_seq" for table in target_tables]
    target_objects = target_tables + target_sequences
    target_set = set(target_tables)
    baseline_tables = sorted(row["name"] for row in catalog["tables"])
    baseline_sequences = sorted(row["name"] for row in catalog["sequences"])
    baseline_functions = sorted(row["name"] for row in catalog["functions"])
    functions = {row["name"]: row for row in catalog["functions"]}
    triggers = sorted(catalog["triggers"], key=lambda row: (row["table"], row["name"]))
    constraint_signatures = ordered_constraint_records(
        catalog["constraints"], include_definition=False
    )
    expected_constraint_md5 = constraint_fingerprint(catalog["constraints"])
    constraint_signature_rows = sql_constraint_rows(include_definition=False)
    constraint_fingerprint_expression = sql_constraint_fingerprint_expression()
    index_names = sorted(row["name"] for row in catalog["indexes"])
    index_definition_lines = sorted(f"{row['name']}|{row['definition']}" for row in catalog["indexes"])
    expected_index_md5 = hashlib.md5("\n".join(index_definition_lines).encode("utf-8")).hexdigest()
    column_lines = []
    for row in sorted(catalog["columns"], key=lambda item: (item["table"], item["position"])):
        column_lines.append("|".join((
            row["table"], str(row["position"]), row["name"], row["type"],
            row["default"] or "", row["identity"] or "", row["generated"] or "",
            str(bool(row["not_null"])).lower(),
        )))
    expected_column_md5 = hashlib.md5("\n".join(column_lines).encode("utf-8")).hexdigest()

    # Importing declarative models does not construct the app or read dotenv/database config.
    import models  # noqa: F401
    from extensions import db
    orm_columns = sorted(
        (table.name, column.name)
        for table in db.metadata.tables.values()
        for column in table.columns
    )

    guard = [
        "-- LOCAL REVIEW DRAFT generated from migrations 007-009 and the reviewed metadata snapshot.",
        "-- Not applied to production. Preserves existing scheduling, assignment, audit, and reminder safeguards.",
        "-- Constraint fingerprint: UTF-8 byte-length-prefixed fields and records, ordered by serialized bytes.",
        "-- PG17 accepts the exact production snapshot fingerprint or the reviewed PG17.11 fixture serialization profile.",
        "BEGIN;",
        "SET LOCAL search_path TO ramosolo, public;",
        "SET LOCAL lock_timeout='5s';",
        "SET LOCAL statement_timeout='5min';",
        "SELECT pg_advisory_xact_lock(hashtext('ramosolo_live_reconciliation'));",
        "DO $preflight$ DECLARE versions integer[]; original_search_path text; constraint_fingerprint text; BEGIN",
        " IF current_setting('server_version_num')::integer / 10000 NOT IN (17,18) THEN RAISE EXCEPTION 'Unsupported PostgreSQL major version for reviewed catalog snapshot'; END IF;",
        " original_search_path := current_setting('search_path');",
        " PERFORM set_config('search_path','public',true);",
        " SELECT array_agg(version ORDER BY version) INTO versions FROM ramosolo.schema_versions;",
        " IF versions IS DISTINCT FROM ARRAY[1,2,3,4,5,6] THEN RAISE EXCEPTION 'Expected ramosolo ledger 1-6; stop and reconcile the ledger'; END IF;",
        f" IF (SELECT array_agg(c.relname::text ORDER BY c.relname COLLATE \"C\") FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='ramosolo' AND c.relkind='r') IS DISTINCT FROM {sql_array(baseline_tables)} THEN RAISE EXCEPTION 'Unexpected existing table inventory'; END IF;",
        f" IF (SELECT array_agg(c.relname::text ORDER BY c.relname COLLATE \"C\") FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='ramosolo' AND c.relkind='S') IS DISTINCT FROM {sql_array(baseline_sequences)} THEN RAISE EXCEPTION 'Unexpected existing sequence inventory'; END IF;",
        f" IF (SELECT array_agg(p.proname::text ORDER BY p.proname COLLATE \"C\") FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='ramosolo') IS DISTINCT FROM {sql_array(baseline_functions)} THEN RAISE EXCEPTION 'Unexpected existing routine inventory'; END IF;",
        f" IF (SELECT count(*) FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='ramosolo' AND NOT t.tgisinternal) <> {len(triggers)} THEN RAISE EXCEPTION 'Unexpected existing trigger inventory'; END IF;",
        f" IF (SELECT count(*) FROM information_schema.columns WHERE table_schema='ramosolo') <> {len(catalog['columns'])} THEN RAISE EXCEPTION 'Unexpected existing column inventory'; END IF;",
        " IF (SELECT md5(coalesce(string_agg(concat_ws('|',t.relname,a.attnum::text,a.attname,format_type(a.atttypid,a.atttypmod),coalesce(pg_get_expr(d.adbin,d.adrelid),''),coalesce(a.attidentity::text,''),coalesce(a.attgenerated::text,''),a.attnotnull::text), E'\\n' ORDER BY t.relname,a.attnum),'')) FROM pg_attribute a JOIN pg_class t ON t.oid=a.attrelid JOIN pg_namespace n ON n.oid=t.relnamespace LEFT JOIN pg_attrdef d ON d.adrelid=a.attrelid AND d.adnum=a.attnum WHERE n.nspname='ramosolo' AND t.relkind IN ('r','p') AND a.attnum>0 AND NOT a.attisdropped) IS DISTINCT FROM '" + expected_column_md5 + "' THEN RAISE EXCEPTION 'Existing column definition drift'; END IF;",
        f" IF (SELECT count(*) FROM pg_constraint c JOIN pg_class t ON t.oid=c.conrelid JOIN pg_namespace n ON n.oid=t.relnamespace WHERE n.nspname='ramosolo' AND c.contype <> 'n') <> {len(catalog['constraints'])} THEN RAISE EXCEPTION 'Unexpected existing constraint inventory'; END IF;",
        f" IF (SELECT array_agg(signature ORDER BY signature COLLATE \"C\") FROM ({constraint_signature_rows}) AS constraint_rows) IS DISTINCT FROM {sql_array(constraint_signatures)} THEN RAISE EXCEPTION 'Unexpected existing constraint definitions'; END IF;",
        f" constraint_fingerprint := {constraint_fingerprint_expression};",
        f" IF current_setting('server_version_num')::integer / 10000 = 17 AND constraint_fingerprint IS DISTINCT FROM '{expected_constraint_md5}' AND constraint_fingerprint IS DISTINCT FROM '{fixture_constraint_md5}' THEN RAISE EXCEPTION 'Existing constraint definition drift'; END IF;",
        f" IF (SELECT array_agg(indexname::text ORDER BY indexname COLLATE \"C\") FROM pg_indexes WHERE schemaname='ramosolo') IS DISTINCT FROM {sql_array(index_names)} THEN RAISE EXCEPTION 'Unexpected existing index inventory'; END IF;",
        " IF (SELECT md5(coalesce(string_agg(indexname||'|'||indexdef, E'\\n' ORDER BY indexname COLLATE \"C\"),'')) FROM pg_indexes WHERE schemaname='ramosolo') IS DISTINCT FROM '" + expected_index_md5 + "' THEN RAISE EXCEPTION 'Existing index definition drift'; END IF;",
        f" IF (SELECT array_agg(c.relname::text ORDER BY c.relname) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='ramosolo' AND c.relkind='r' AND c.relname IN ({','.join(literal(t) for t in target_tables)})) IS NOT NULL THEN RAISE EXCEPTION 'Expected all reconciliation target tables absent'; END IF;",
        " IF (SELECT data_type||':'||is_nullable||':'||coalesce(column_default,'') FROM information_schema.columns WHERE table_schema='ramosolo' AND table_name='appointments' AND column_name='institution_id') IS DISTINCT FROM 'integer:NO:' THEN RAISE EXCEPTION 'appointments.institution_id definition drift'; END IF;",
        " IF (SELECT data_type||':'||is_nullable||':'||coalesce(column_default,'') FROM information_schema.columns WHERE table_schema='ramosolo' AND table_name='appointments' AND column_name='schedule_version') IS DISTINCT FROM 'integer:NO:1' THEN RAISE EXCEPTION 'appointments.schedule_version definition drift'; END IF;",
        " IF (SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid='ramosolo.appointments'::regclass AND conname='appointment_identity') IS DISTINCT FROM 'CHECK (((patient_id IS NOT NULL) <> (booking_request_id IS NOT NULL)))' THEN RAISE EXCEPTION 'appointments.appointment_identity definition drift'; END IF;",
        " IF (SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid='ramosolo.appointments'::regclass AND conname='appointment_interval') IS DISTINCT FROM 'CHECK (((ends_at IS NULL) OR ((ends_at > starts_at) AND (occupied_until >= ends_at))))' THEN RAISE EXCEPTION 'appointments.appointment_interval definition drift'; END IF;",
        " IF (SELECT indexdef FROM pg_indexes WHERE schemaname='ramosolo' AND indexname='booking_capacity') IS DISTINCT FROM 'CREATE INDEX booking_capacity ON ramosolo.appointments USING btree (doctor_id, starts_at, status, hold_expires_at)' THEN RAISE EXCEPTION 'appointments.booking_capacity definition drift'; END IF;",
        " IF to_regclass('ramosolo.admission_patient_identity') IS NOT NULL AND (SELECT indexdef FROM pg_indexes WHERE schemaname='ramosolo' AND indexname='admission_patient_identity') IS DISTINCT FROM 'CREATE UNIQUE INDEX admission_patient_identity ON ramosolo.admissions USING btree (id, patient_id)' THEN RAISE EXCEPTION 'admission_patient_identity definition drift'; END IF;",
        " IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='ramosolo' AND table_name='attendance_followups' AND column_name IN ('owner_id','cover_id','due_at','escalated')) THEN RAISE EXCEPTION 'attendance_followups has a partial 008 upgrade'; END IF;",
        " IF (SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid='ramosolo.appointments'::regclass AND conname='appointment_identity') IS NULL THEN RAISE EXCEPTION 'Missing appointment identity constraint'; END IF;",
        " IF EXISTS (SELECT 1 FROM pg_trigger WHERE tgrelid='ramosolo.notification_outbox'::regclass AND tgname='coordination_outbox_permission_guard') THEN RAISE EXCEPTION 'Coordination outbox trigger name already occupied'; END IF;",
        " IF (SELECT pg_get_userbyid(n.nspowner) FROM pg_namespace n WHERE n.nspname='ramosolo') IS DISTINCT FROM 'postgres' THEN RAISE EXCEPTION 'ramosolo schema owner drift'; END IF;",
        " IF EXISTS (SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='ramosolo' AND c.relkind IN ('r','S') AND pg_get_userbyid(c.relowner) IS DISTINCT FROM 'postgres') THEN RAISE EXCEPTION 'Existing table or sequence owner drift'; END IF;",
        " IF EXISTS (SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='ramosolo' AND (pg_get_userbyid(p.proowner) IS DISTINCT FROM 'postgres' OR p.prosecdef OR p.proconfig IS DISTINCT FROM ARRAY['search_path=ramosolo, pg_temp']::text[])) THEN RAISE EXCEPTION 'Existing routine owner or execution configuration drift'; END IF;",
        " IF EXISTS (SELECT 1 FROM pg_default_acl d LEFT JOIN pg_namespace n ON n.oid=d.defaclnamespace WHERE d.defaclrole='postgres'::regrole AND (d.defaclnamespace=0 OR n.nspname='ramosolo')) THEN RAISE EXCEPTION 'Unexpected postgres default privileges'; END IF;",
    ]
    for table in target_tables:
        guard.append(f" IF to_regclass('ramosolo.{table}') IS NOT NULL THEN RAISE EXCEPTION 'Expected absent target table: {table}'; END IF;")
    for name, function in sorted(functions.items()):
        digest = function["source_md5"]
        guard.append(
            f" IF (SELECT md5(p.prosrc) FROM pg_proc p WHERE p.pronamespace='ramosolo'::regnamespace AND p.proname={literal(name)}) IS DISTINCT FROM {literal(digest)} THEN RAISE EXCEPTION 'Existing routine source drift: {name}'; END IF;"
        )
    for trigger in triggers:
        digest = hashlib.md5(trigger["definition"].encode("utf-8")).hexdigest()
        guard.append(
            f" IF (SELECT md5(pg_get_triggerdef(t.oid)) FROM pg_trigger t WHERE t.tgrelid='ramosolo.{trigger['table']}'::regclass AND t.tgname={literal(trigger['name'])} AND NOT t.tgisinternal) IS DISTINCT FROM {literal(digest)} THEN RAISE EXCEPTION 'Existing trigger definition drift: {trigger['table']}.{trigger['name']}'; END IF;"
        )
        guard.append(
            f" IF (SELECT t.tgenabled::text FROM pg_trigger t WHERE t.tgrelid='ramosolo.{trigger['table']}'::regclass AND t.tgname={literal(trigger['name'])} AND NOT t.tgisinternal) IS DISTINCT FROM {literal(trigger.get('enabled', 'O'))} THEN RAISE EXCEPTION 'Existing trigger enablement drift: {trigger['table']}.{trigger['name']}'; END IF;"
        )
    guard += [
        " PERFORM set_config('search_path',original_search_path,true);",
        " IF EXISTS (SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace CROSS JOIN LATERAL aclexplode(coalesce(c.relacl,acldefault(CASE WHEN c.relkind='S' THEN 'S'::\"char\" ELSE 'r'::\"char\" END,c.relowner))) x WHERE n.nspname='ramosolo' AND c.relkind IN ('r','S') AND x.grantee<>c.relowner) THEN RAISE EXCEPTION 'Unexpected table or sequence grants'; END IF;",
        " IF EXISTS (SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace CROSS JOIN LATERAL aclexplode(coalesce(p.proacl,acldefault('f'::\"char\",p.proowner))) x WHERE n.nspname='ramosolo' AND x.grantee<>p.proowner) THEN RAISE EXCEPTION 'Unexpected routine grants'; END IF;",
        " IF EXISTS (SELECT 1 FROM pg_namespace n CROSS JOIN LATERAL aclexplode(coalesce(n.nspacl,acldefault('n'::\"char\",n.nspowner))) x WHERE n.nspname='ramosolo' AND x.grantee<>n.nspowner) THEN RAISE EXCEPTION 'Unexpected schema grants'; END IF;",
        "END $preflight$;",
    ]

    # Verify all required ORM columns and migration objects before recording versions.
    post = [
        "DO $postcondition$ DECLARE original_search_path text; BEGIN",
        f" IF (SELECT count(*) FROM information_schema.tables WHERE table_schema='ramosolo' AND table_type='BASE TABLE' AND table_name = ANY({sql_array(target_tables)})) <> {len(target_tables)} THEN RAISE EXCEPTION 'Target table postcondition failed'; END IF;",
    ]
    pairs = ",".join(f"({literal(table)},{literal(column)})" for table, column in orm_columns)
    post += [
        f" IF EXISTS (SELECT 1 FROM (VALUES {pairs}) AS required(table_name,column_name) LEFT JOIN information_schema.columns c ON c.table_schema='ramosolo' AND c.table_name=required.table_name AND c.column_name=required.column_name WHERE c.column_name IS NULL) THEN RAISE EXCEPTION 'ORM column postcondition failed'; END IF;",
        " IF (SELECT count(*) FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='ramosolo' AND NOT t.tgisinternal) <> 34 THEN RAISE EXCEPTION 'Trigger inventory postcondition failed'; END IF;",
        " IF (SELECT indexdef FROM pg_indexes WHERE schemaname='ramosolo' AND indexname='admission_patient_identity') IS DISTINCT FROM 'CREATE UNIQUE INDEX admission_patient_identity ON ramosolo.admissions USING btree (id, patient_id)' THEN RAISE EXCEPTION 'admission_patient_identity postcondition failed'; END IF;",
        " IF NOT (SELECT relrowsecurity FROM pg_class WHERE oid='ramosolo.appointment_proposals'::regclass) OR NOT (SELECT relrowsecurity FROM pg_class WHERE oid='ramosolo.calendar_history'::regclass) OR NOT (SELECT relrowsecurity FROM pg_class WHERE oid='ramosolo.calendar_delegations'::regclass) THEN RAISE EXCEPTION 'Calendar RLS postcondition failed'; END IF;",
        " IF (SELECT array_agg(version ORDER BY version) FROM ramosolo.schema_versions) IS DISTINCT FROM ARRAY[1,2,3,4,5,6] THEN RAISE EXCEPTION 'Ledger changed before all postconditions'; END IF;",
    ]

    # Use source hashes of the two new routines from the copied historical block.
    coordination_source = "\n\n".join(chunks)
    new_function_hashes = {}
    for name in ("coordination_guard_outbox", "coordination_suppress_withdrawn"):
        match = re.search(
            rf"CREATE FUNCTION ramosolo\.{name}\(\).*?AS\s+(\$\$)(.*?)\1",
            coordination_source, re.S,
        )
        if not match:
            raise ValueError(f"Cannot find historical routine {name}")
        new_function_hashes[name] = hashlib.md5(match.group(2).encode("utf-8")).hexdigest()
    for name, digest in new_function_hashes.items():
        post.append(
            f" IF (SELECT md5(p.prosrc) FROM pg_proc p WHERE p.pronamespace='ramosolo'::regnamespace AND p.proname={literal(name)}) IS DISTINCT FROM {literal(digest)} THEN RAISE EXCEPTION 'New routine postcondition failed: {name}'; END IF;"
        )
    post.extend([
        " IF (SELECT count(*) FROM pg_trigger t JOIN pg_proc p ON p.oid=t.tgfoid WHERE (t.tgrelid='ramosolo.notification_outbox'::regclass AND t.tgname='coordination_outbox_permission_guard' AND p.proname='coordination_guard_outbox' AND t.tgtype=23 AND t.tgenabled='O') OR (t.tgrelid='ramosolo.communication_decisions'::regclass AND t.tgname='coordination_consent_withdrawal' AND p.proname='coordination_suppress_withdrawn' AND t.tgtype=5 AND t.tgenabled='O')) <> 2 THEN RAISE EXCEPTION 'Coordination trigger postcondition failed'; END IF;",
    ])

    post.append(" original_search_path := current_setting('search_path');")
    post.append(" PERFORM set_config('search_path','public',true);")
    for name, function in sorted(functions.items()):
        post.append(
            f" IF (SELECT md5(p.prosrc) FROM pg_proc p WHERE p.pronamespace='ramosolo'::regnamespace AND p.proname={literal(name)}) IS DISTINCT FROM {literal(function['source_md5'])} THEN RAISE EXCEPTION 'Existing routine changed during reconciliation: {name}'; END IF;"
        )
    for trigger in triggers:
        digest = hashlib.md5(trigger["definition"].encode("utf-8")).hexdigest()
        post.append(
            f" IF (SELECT md5(pg_get_triggerdef(t.oid)) FROM pg_trigger t WHERE t.tgrelid='ramosolo.{trigger['table']}'::regclass AND t.tgname={literal(trigger['name'])} AND NOT t.tgisinternal) IS DISTINCT FROM {literal(digest)} THEN RAISE EXCEPTION 'Existing trigger changed during reconciliation: {trigger['table']}.{trigger['name']}'; END IF;"
        )
        post.append(
            f" IF (SELECT t.tgenabled::text FROM pg_trigger t WHERE t.tgrelid='ramosolo.{trigger['table']}'::regclass AND t.tgname={literal(trigger['name'])} AND NOT t.tgisinternal) IS DISTINCT FROM {literal(trigger.get('enabled', 'O'))} THEN RAISE EXCEPTION 'Existing trigger enablement changed during reconciliation: {trigger['table']}.{trigger['name']}'; END IF;"
        )
    post.extend([
        " PERFORM set_config('search_path',original_search_path,true);",
        " IF EXISTS (SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='ramosolo' AND c.relname IN (" + ",".join(literal(t) for t in target_objects) + ") AND pg_get_userbyid(c.relowner) IS DISTINCT FROM 'postgres') THEN RAISE EXCEPTION 'Target table or sequence owner postcondition failed'; END IF;",
        " IF EXISTS (SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace CROSS JOIN LATERAL aclexplode(coalesce(c.relacl,acldefault(CASE WHEN c.relkind='S' THEN 'S'::\"char\" ELSE 'r'::\"char\" END,c.relowner))) x WHERE n.nspname='ramosolo' AND c.relname IN (" + ",".join(literal(t) for t in target_objects) + ") AND x.grantee IN (0,'anon'::regrole,'authenticated'::regrole)) THEN RAISE EXCEPTION 'Target table or sequence grants postcondition failed'; END IF;",
        " IF EXISTS (SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace CROSS JOIN LATERAL aclexplode(coalesce(p.proacl,acldefault('f'::\"char\",p.proowner))) x WHERE n.nspname='ramosolo' AND p.proname IN ('coordination_guard_outbox','coordination_suppress_withdrawn') AND x.grantee IN (0,'anon'::regrole,'authenticated'::regrole)) THEN RAISE EXCEPTION 'Coordination routine grants postcondition failed'; END IF;",
        " IF (SELECT array_agg(version ORDER BY version) FROM ramosolo.schema_versions) IS DISTINCT FROM ARRAY[1,2,3,4,5,6] THEN RAISE EXCEPTION 'Ledger changed before all postconditions'; END IF;",
        " INSERT INTO ramosolo.schema_versions(version) VALUES (7),(8),(9);",
        " IF (SELECT array_agg(version ORDER BY version) FROM ramosolo.schema_versions) IS DISTINCT FROM ARRAY[1,2,3,4,5,6,7,8,9] THEN RAISE EXCEPTION 'Ledger postcondition failed'; END IF;",
        "END $postcondition$;",
    ])

    TARGET.write_text("\n".join(guard + chunks + post + ["COMMIT;"]) + "\n", encoding="utf-8", newline="\n")
    print(f"Wrote {TARGET.relative_to(ROOT)} ({TARGET.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
