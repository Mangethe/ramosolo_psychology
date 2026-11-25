-- Stage 3 draft. Existing password hashes and memberships are preserved.
BEGIN;
SET LOCAL lock_timeout = '5s';
ALTER TABLE ramosolo.portal_sessions ADD COLUMN mfa_method varchar(12);
ALTER TABLE ramosolo.account_verifications ADD COLUMN mfa_reenroll_required boolean NOT NULL DEFAULT false;
CREATE TABLE ramosolo.account_recoveries (
    ticket varchar(64) PRIMARY KEY,
    institution_id integer NOT NULL REFERENCES ramosolo.institutions(id),
    user_id integer NOT NULL REFERENCES ramosolo.users(id),
    requestor_id integer NOT NULL REFERENCES ramosolo.users(id),
    approver_id integer NOT NULL REFERENCES ramosolo.users(id),
    started_at bigint NOT NULL,
    CHECK (requestor_id <> approver_id AND user_id <> requestor_id AND user_id <> approver_id)
);
CREATE INDEX ix_account_recoveries_user_id ON ramosolo.account_recoveries (user_id);
CREATE TABLE ramosolo.authenticators (
    user_id integer PRIMARY KEY REFERENCES ramosolo.users(id) ON DELETE CASCADE,
    encrypted_secret bytea NOT NULL,
    last_counter bigint NOT NULL,
    attempts integer NOT NULL DEFAULT 0,
    blocked_until bigint NOT NULL DEFAULT 0
);
CREATE TABLE ramosolo.auth_recovery_codes (
    user_id integer REFERENCES ramosolo.authenticators(user_id) ON DELETE CASCADE,
    code_hash varchar(64),
    PRIMARY KEY (user_id, code_hash)
);
CREATE TABLE ramosolo.pending_authentications (
    token_hash varchar(64) PRIMARY KEY,
    user_id integer NOT NULL UNIQUE REFERENCES ramosolo.users(id) ON DELETE CASCADE,
    account_version integer NOT NULL,
    privileges varchar(64) NOT NULL,
    expires_at bigint NOT NULL,
    mode varchar(16) NOT NULL,
    encrypted_secret bytea,
    attempts integer NOT NULL DEFAULT 0
);
CREATE INDEX ix_pending_authentications_expires_at ON ramosolo.pending_authentications (expires_at);
ALTER TABLE ramosolo.authenticators ENABLE ROW LEVEL SECURITY;
ALTER TABLE ramosolo.account_recoveries ENABLE ROW LEVEL SECURITY;
ALTER TABLE ramosolo.auth_recovery_codes ENABLE ROW LEVEL SECURITY;
ALTER TABLE ramosolo.pending_authentications ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON ramosolo.authenticators, ramosolo.auth_recovery_codes, ramosolo.pending_authentications,
  ramosolo.account_recoveries
  FROM PUBLIC, anon, authenticated;
COMMIT;
