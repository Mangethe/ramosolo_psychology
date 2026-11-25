-- Stage 1 draft. Additive; independently review and apply only to the intended schema.
BEGIN;
SET LOCAL lock_timeout = '5s';
CREATE TABLE ramosolo.portal_sessions (
    token_hash varchar(64) PRIMARY KEY,
    user_id integer NOT NULL REFERENCES ramosolo.users(id) ON DELETE CASCADE,
    account_version integer NOT NULL,
    privileges varchar(64) NOT NULL,
    started_at bigint NOT NULL,
    last_seen_at bigint NOT NULL,
    idle_expires_at bigint NOT NULL,
    absolute_expires_at bigint NOT NULL,
    mfa_at bigint
);
CREATE INDEX ix_portal_sessions_user_id ON ramosolo.portal_sessions (user_id);
CREATE INDEX ix_portal_sessions_idle_expires_at ON ramosolo.portal_sessions (idle_expires_at);
CREATE INDEX ix_portal_sessions_absolute_expires_at ON ramosolo.portal_sessions (absolute_expires_at);
ALTER TABLE ramosolo.portal_sessions ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON ramosolo.portal_sessions FROM PUBLIC, anon, authenticated;
COMMIT;
