-- Opt-in ownership verification only. No phone values are backfilled.
BEGIN;
SET LOCAL lock_timeout = '5s';
CREATE TABLE ramosolo.verified_phones (
    user_id integer PRIMARY KEY REFERENCES ramosolo.users(id) ON DELETE CASCADE,
    encrypted_number bytea NOT NULL,
    verified_at bigint NOT NULL
);
CREATE TABLE ramosolo.phone_challenges (
    user_id integer PRIMARY KEY REFERENCES ramosolo.users(id) ON DELETE CASCADE,
    challenge_id varchar(43) NOT NULL UNIQUE,
    institution_id integer NOT NULL REFERENCES ramosolo.institutions(id),
    session_hash varchar(64) NOT NULL,
    purpose varchar(24) NOT NULL,
    encrypted_number bytea NOT NULL,
    destination_key varchar(64) NOT NULL,
    reference varchar(64),
    provider varchar(16) NOT NULL,
    state varchar(16) NOT NULL,
    expires_at bigint NOT NULL,
    resend_after bigint NOT NULL,
    sends integer NOT NULL,
    attempts integer NOT NULL
);
CREATE INDEX ix_phone_challenges_expires_at ON ramosolo.phone_challenges (expires_at);
ALTER TABLE ramosolo.verified_phones ENABLE ROW LEVEL SECURITY;
ALTER TABLE ramosolo.phone_challenges ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON ramosolo.verified_phones, ramosolo.phone_challenges FROM PUBLIC, anon, authenticated;
COMMIT;
