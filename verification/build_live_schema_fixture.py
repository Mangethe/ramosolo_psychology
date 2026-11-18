"""Rebuild the checked-in metadata-only production catalog fixture.

The output contains DDL/catalog metadata and explicitly synthetic sentinel rows.
It must only be used by isolated local PostgreSQL tests.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from verification.constraint_fingerprint import constraint_fingerprint, constraint_record

SNAPSHOT = ROOT / "tests" / "fixtures" / "ramosolo_live_catalog.json"
FIXTURE_PROFILE = ROOT / "tests" / "fixtures" / "ramosolo_pg17_fixture_profile.json"
TARGET = ROOT / "tests" / "fixtures" / "ramosolo_live_fixture.sql"
IDENT = re.compile(r"^[a-z_][a-z0-9_]*$")


def ident(value: str) -> str:
    if not IDENT.fullmatch(value):
        raise ValueError(f"Unexpected catalog identifier: {value!r}")
    return '"' + value.replace('"', '""') + '"'


def identity_types(arguments: str) -> str:
    """Reduce a pg_get_functiondef argument list to ALTER FUNCTION types."""
    parts: list[str] = []
    start = depth = 0
    for index, char in enumerate(arguments):
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        elif char == "," and depth == 0:
            parts.append(arguments[start:index].strip())
            start = index + 1
    if arguments[start:].strip():
        parts.append(arguments[start:].strip())
    result = []
    for part in parts:
        part = re.split(r"\s+DEFAULT\s+", part, maxsplit=1, flags=re.I)[0]
        tokens = part.split()
        if tokens and tokens[0].upper() in {"IN", "OUT", "INOUT", "VARIADIC"}:
            tokens = tokens[1:]
        if len(tokens) > 1:
            tokens = tokens[1:]
        if not tokens:
            raise ValueError(f"Cannot parse identity argument type from {arguments!r}")
        result.append(" ".join(tokens))
    return ", ".join(result)


def preserve_function_body(definition: str) -> str:
    """Use an E-string so PostgreSQL retains snapshot CR/LF bytes in prosrc."""
    match = re.search(r"AS (\$[a-zA-Z_0-9]*\$)(.*?)\1\s*;?\s*$", definition, re.S)
    if not match:
        raise ValueError("Cannot extract dollar-quoted routine body")
    body = match.group(2)
    escaped = body.replace("\\", "\\\\").replace("'", "\\'")
    escaped = escaped.replace("\r", "\\r").replace("\n", "\\n")
    return definition[:match.start()] + "AS E'" + escaped + "'" + definition[match.end():]


def main() -> None:
    source = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    if source.get("schema") != "ramosolo" or "no table rows" not in source.get("source", ""):
        raise ValueError("Expected the reviewed, metadata-only ramosolo snapshot")
    catalog = source["snapshot"]
    fixture_profile = json.loads(FIXTURE_PROFILE.read_text(encoding="utf-8"))
    if fixture_profile.get("server_version_num") != 170011:
        raise ValueError("Expected the reviewed PostgreSQL 17.11 synthetic fixture profile")
    sections: list[str] = [
        "-- SYNTHETIC LOCAL FIXTURE generated from metadata-only production snapshot.",
        "-- No production data values are present. Apply only to a disposable local database.",
        f"-- Canonical constraint fingerprint (UTF-8 byte-length-prefixed): {constraint_fingerprint(catalog['constraints'])}.",
        f"-- PG17.11 EDB fixture profile fingerprint: {fixture_profile['constraint_fingerprint']}.",
        "DO $$ BEGIN CREATE ROLE postgres NOLOGIN; EXCEPTION WHEN duplicate_object THEN NULL; END $$;",
        "DO $$ BEGIN CREATE ROLE anon NOLOGIN; EXCEPTION WHEN duplicate_object THEN NULL; END $$;",
        "DO $$ BEGIN CREATE ROLE authenticated NOLOGIN; EXCEPTION WHEN duplicate_object THEN NULL; END $$;",
        "CREATE SCHEMA ramosolo AUTHORIZATION postgres;",
        "GRANT USAGE, CREATE ON SCHEMA ramosolo TO postgres;",
        "SET search_path TO ramosolo, public;",
    ]
    sequences = {row["name"]: row for row in catalog["sequences"]}
    for name, row in sorted(sequences.items(), key=lambda item: item[0].encode("utf-8")):
        ident(name)
        sections.append(
            f"CREATE SEQUENCE ramosolo.{ident(name)} AS {row['type']} "
            f"INCREMENT BY {int(row['increment'])} MINVALUE {int(row['min'])} "
            f"MAXVALUE {int(row['max'])} START WITH {int(row['start'])} "
            f"CACHE {int(row['cache'])} {'CYCLE' if row['cycle'] else 'NO CYCLE'};"
        )

    columns_by_table: dict[str, list[dict]] = {}
    for col in catalog["columns"]:
        columns_by_table.setdefault(col["table"], []).append(col)
    tables = sorted(catalog["tables"], key=lambda row: row["name"].encode("utf-8"))
    for table in tables:
        name = table["name"]
        ident(name)
        definitions = []
        for col in sorted(columns_by_table[name], key=lambda row: row["position"]):
            col_name = ident(col["name"])
            definition = f"{col_name} {col['type']}"
            if col["identity"]:
                definition += f" GENERATED {col['identity']} AS IDENTITY"
            if col["generated"]:
                definition += f" GENERATED ALWAYS AS ({col['generated']}) STORED"
            if col["default"] is not None and not col["identity"] and not col["generated"]:
                definition += f" DEFAULT {col['default']}"
            if col["not_null"]:
                definition += " NOT NULL"
            definitions.append(definition)
        sections.append(f"CREATE TABLE ramosolo.{ident(name)} (\n  " + ",\n  ".join(definitions) + "\n);")

    constraints = sorted(
        catalog["constraints"],
        key=lambda row: constraint_record(row).encode("utf-8"),
    )
    for row in constraints:
        if row["type"] == "f":
            continue
        table, name = row["table"], row["name"]
        ident(table)
        ident(name)
        definition = row["definition"]
        if row["deferrable"]:
            definition += " DEFERRABLE"
            definition += " INITIALLY DEFERRED" if row["initially_deferred"] else " INITIALLY IMMEDIATE"
        if not row["validated"]:
            definition += " NOT VALID"
        sections.append(f"ALTER TABLE ramosolo.{ident(table)} ADD CONSTRAINT {ident(name)} {definition};")

    indexed_constraint_names = {
        row["name"] for row in catalog["constraints"] if row["type"] in ("p", "u")
    }
    for row in sorted(catalog["indexes"], key=lambda item: item["name"].encode("utf-8")):
        if row["name"] in indexed_constraint_names:
            continue
        sections.append(row["definition"] + ";")

    for row in constraints:
        if row["type"] != "f":
            continue
        table, name = row["table"], row["name"]
        ident(table)
        ident(name)
        definition = row["definition"]
        if row["deferrable"]:
            definition += " DEFERRABLE"
            definition += " INITIALLY DEFERRED" if row["initially_deferred"] else " INITIALLY IMMEDIATE"
        if not row["validated"]:
            definition += " NOT VALID"
        sections.append(f"ALTER TABLE ramosolo.{ident(table)} ADD CONSTRAINT {ident(name)} {definition};")

    # PostgreSQL stores trigger routine source separately from pg_get_functiondef;
    # the source hash in the fixture is useful to detect reconstruction drift.
    for function in sorted(catalog["functions"], key=lambda item: item["name"].encode("utf-8")):
        body = re.search(r"AS (\$[a-zA-Z_0-9]*\$)(.*?)\1\s*;?\s*$", function["definition"], re.S)
        if not body or __import__("hashlib").md5(body.group(2).encode()).hexdigest() != function["source_md5"]:
            raise ValueError(f"Function body hash mismatch while rebuilding {function['name']}")
        sections.append(preserve_function_body(function["definition"]).rstrip(";") + ";")
        header = re.match(
            r"CREATE OR REPLACE FUNCTION\s+ramosolo\.([a-z_][a-z0-9_]*)\((.*?)\)\s+RETURNS",
            function["definition"], re.S | re.I,
        )
        if not header:
            raise ValueError(f"Cannot parse function signature: {function['name']}")
        sections.append(
            f"ALTER FUNCTION ramosolo.{ident(header.group(1))}({identity_types(header.group(2))}) OWNER TO postgres;"
        )

    trigger_sections = []
    enabled_statements = {"D": "DISABLE", "R": "ENABLE REPLICA", "A": "ENABLE ALWAYS"}
    ordered_triggers = sorted(
        catalog["triggers"],
        key=lambda row: (row["table"].encode("utf-8"), row["name"].encode("utf-8")),
    )
    for row in ordered_triggers:
        if row.get("enabled", "O") not in {"O", *enabled_statements}:
            raise ValueError(f"Unexpected trigger enablement state: {row['table']}.{row['name']}")
        trigger_sections.append(row["definition"].rstrip(";") + ";")
        if row.get("enabled", "O") != "O":
            trigger_sections.append(
                f"ALTER TABLE ramosolo.{ident(row['table'])} {enabled_statements[row['enabled']]} TRIGGER {ident(row['name'])};"
            )

    for table in tables:
        name = table["name"]
        if table["rls"]:
            sections.append(f"ALTER TABLE ramosolo.{ident(name)} ENABLE ROW LEVEL SECURITY;")
        if table["force_rls"]:
            sections.append(f"ALTER TABLE ramosolo.{ident(name)} FORCE ROW LEVEL SECURITY;")

    for table in tables:
        sections.append(f"ALTER TABLE ramosolo.{ident(table['name'])} OWNER TO postgres;")
    for sequence in sorted(catalog["sequences"], key=lambda item: item["name"].encode("utf-8")):
        name = sequence["name"]
        sections.append(f"ALTER SEQUENCE ramosolo.{ident(name)} OWNER TO postgres;")
        match = re.fullmatch(r"(.+)_id_seq", name)
        if not match or match.group(1) not in columns_by_table:
            raise ValueError(f"Cannot resolve owned sequence table: {name}")
        sections.append(f"ALTER SEQUENCE ramosolo.{ident(name)} OWNED BY ramosolo.{ident(match.group(1))}.id;")
    for function in sorted(catalog["functions"], key=lambda item: item["name"].encode("utf-8")):
        header = re.match(
            r"CREATE OR REPLACE FUNCTION\s+ramosolo\.([a-z_][a-z0-9_]*)\((.*?)\)\s+RETURNS",
            function["definition"], re.S | re.I,
        )
        assert header
        sections.append(
            f"REVOKE ALL ON FUNCTION ramosolo.{ident(header.group(1))}({identity_types(header.group(2))}) "
            "FROM PUBLIC, anon, authenticated;"
        )
    sections.extend([
        "REVOKE ALL ON ALL TABLES IN SCHEMA ramosolo FROM PUBLIC, anon, authenticated;",
        "REVOKE ALL ON ALL SEQUENCES IN SCHEMA ramosolo FROM PUBLIC, anon, authenticated;",
        "REVOKE ALL ON ALL FUNCTIONS IN SCHEMA ramosolo FROM PUBLIC, anon, authenticated;",
    ])

    sections.extend([
        "-- Synthetic preserved sentinels, inserted before trigger installation so fixture setup itself does not simulate application writes.",
        "INSERT INTO ramosolo.schema_versions(version) VALUES (1),(2),(3),(4),(5),(6);",
        "INSERT INTO ramosolo.institutions(id,name,kind) VALUES (1,'Synthetic fixture practice A','medical'),(2,'Synthetic fixture practice B','medical');",
        "INSERT INTO ramosolo.users(id,name,email,password_hash,enabled,session_version,failed_logins) VALUES "
        "(1,'Synthetic fixture doctor A','fixture-doctor-a@example.test','disabled-synthetic-login',true,1,0),"
        "(2,'Synthetic fixture doctor B','fixture-doctor-b@example.test','disabled-synthetic-login',true,1,0),"
        "(3,'Synthetic fixture assistant','fixture-assistant@example.test','disabled-synthetic-login',true,1,0),"
        "(4,'Synthetic fixture patient','fixture-patient@example.test','disabled-synthetic-login',true,1,0);",
        "INSERT INTO ramosolo.memberships(id,user_id,institution_id,role,enabled,supervising_doctor_id) VALUES "
        "(1,1,1,'dr',true,NULL),(2,2,1,'dr',true,NULL),(3,3,1,'dr_assist',true,1),"
        "(4,4,1,'patient',true,NULL),(5,2,2,'dr',true,NULL);",
        "INSERT INTO ramosolo.patients(id,institution_id,user_id,doctor_id,name,email,phone) VALUES "
        "(1,1,4,1,'Synthetic fixture patient A','fixture-patient@example.test','0000000000'),"
        "(2,1,NULL,2,'Synthetic fixture patient B',NULL,NULL),"
        "(3,2,NULL,2,'Synthetic fixture patient C',NULL,NULL);",
        "INSERT INTO ramosolo.appointments(id,patient_id,doctor_id,starts_at,ends_at,occupied_until,status,service,institution_id,care_type,visit_kind,schedule_version) "
        "VALUES (1,1,1,timestamp '2030-01-02 08:00',timestamp '2030-01-02 08:30',timestamp '2030-01-02 08:35','scheduled','Synthetic fixture service',1,'outpatient','followup',1);",
        "SELECT setval('ramosolo.institutions_id_seq',2,true), setval('ramosolo.users_id_seq',4,true), "
        "setval('ramosolo.memberships_id_seq',5,true), setval('ramosolo.patients_id_seq',3,true), setval('ramosolo.appointments_id_seq',1,true);",
    ])
    sections.extend(trigger_sections)
    # Preserve pg_get_functiondef body bytes, including the snapshot's line endings.
    TARGET.write_text("\n\n".join(sections) + "\n", encoding="utf-8", newline="\n")
    print(f"Wrote {TARGET.relative_to(ROOT)} ({TARGET.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
