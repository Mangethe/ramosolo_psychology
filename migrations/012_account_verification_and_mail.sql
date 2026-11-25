-- Stage 2 draft. No backfill and no change to existing accounts or memberships.
BEGIN;
SET LOCAL lock_timeout = '5s';
CREATE TABLE ramosolo.account_verifications (
    user_id integer PRIMARY KEY REFERENCES ramosolo.users(id) ON DELETE CASCADE,
    verified_email varchar(254),
    verified_at bigint,
    requested_email varchar(254),
    verification_id varchar(43) UNIQUE,
    token_hash varchar(64),
    expires_at bigint,
    resend_after bigint NOT NULL DEFAULT 0,
    window_started_at bigint NOT NULL DEFAULT 0,
    send_count integer NOT NULL DEFAULT 0
);
CREATE TABLE ramosolo.security_emails (
    dedupe_key varchar(96) PRIMARY KEY,
    user_id integer NOT NULL REFERENCES ramosolo.users(id) ON DELETE CASCADE,
    recipient varchar(254) NOT NULL,
    kind varchar(24) NOT NULL,
    detail varchar(100),
    created_at bigint NOT NULL,
    next_attempt_at bigint NOT NULL,
    attempts integer NOT NULL DEFAULT 0,
    state varchar(16) NOT NULL DEFAULT 'pending'
);
CREATE INDEX ix_security_emails_due ON ramosolo.security_emails (state, next_attempt_at);
CREATE INDEX ix_security_emails_user_id ON ramosolo.security_emails (user_id);
ALTER TABLE ramosolo.account_verifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE ramosolo.security_emails ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON ramosolo.account_verifications, ramosolo.security_emails FROM PUBLIC, anon, authenticated;
COMMIT;
