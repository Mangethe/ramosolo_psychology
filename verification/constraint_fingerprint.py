"""Canonical constraint inventory serialization shared by draft and fixture builders.

Each text value is tagged and UTF-8 byte-length-prefixed. Each complete record
is framed the same way in the aggregate. PostgreSQL and Python sort the exact
serialized UTF-8 bytes, making ordering and field boundaries explicit.
"""
from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping
from typing import Any


def _text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def encode_field(value: Any) -> str:
    """Encode null distinctly and text with its UTF-8 byte length."""
    text = _text(value)
    if text is None:
        return "N;"
    return f"V{len(text.encode('utf-8'))}:{text}"


def constraint_record(row: Mapping[str, Any], *, include_definition: bool = True) -> str:
    fields: list[Any] = [row["table"], row["name"], row["type"]]
    if include_definition:
        fields.append(row["definition"])
    fields.extend((row["deferrable"], row["initially_deferred"], row["validated"]))
    return "".join(encode_field(value) for value in fields)


def ordered_constraint_records(
    rows: Iterable[Mapping[str, Any]], *, include_definition: bool = True
) -> list[str]:
    records = [constraint_record(row, include_definition=include_definition) for row in rows]
    return sorted(records, key=lambda record: record.encode("utf-8"))


def constraint_fingerprint(rows: Iterable[Mapping[str, Any]]) -> str:
    records = ordered_constraint_records(rows, include_definition=True)
    payload = "".join(encode_field(record) for record in records)
    return hashlib.md5(payload.encode("utf-8")).hexdigest()


def sql_field_expression(expression: str) -> str:
    """Return PostgreSQL SQL implementing :func:`encode_field` for an expression."""
    value = f"({expression})::text"
    return (
        f"CASE WHEN {value} IS NULL THEN 'N;' ELSE 'V'||"
        f"octet_length(convert_to({value},'UTF8'))::text||':'||{value} END"
    )


def sql_constraint_rows(*, include_definition: bool) -> str:
    fields = ["t.relname", "c.conname", "c.contype::text"]
    if include_definition:
        fields.append("pg_get_constraintdef(c.oid)")
    fields.extend(("c.condeferrable::text", "c.condeferred::text", "c.convalidated::text"))
    encoded = ",".join(sql_field_expression(field) for field in fields)
    return (
        f"SELECT concat({encoded}) AS signature "
        "FROM pg_constraint c "
        "JOIN pg_class t ON t.oid=c.conrelid "
        "JOIN pg_namespace n ON n.oid=t.relnamespace "
        "WHERE n.nspname='ramosolo' AND c.contype <> 'n'"
    )


def sql_constraint_fingerprint_expression() -> str:
    rows = sql_constraint_rows(include_definition=True)
    return (
        "(SELECT md5(coalesce(string_agg(" 
        "'V'||octet_length(convert_to(signature,'UTF8'))::text||':'||signature, "
        "'' ORDER BY signature COLLATE \"C\"),'')) "
        f"FROM ({rows}) AS constraint_rows)"
    )
