-- Stage 4 draft. Creates no links and leaves SSO configuration disabled.
BEGIN;
SET LOCAL lock_timeout = '5s';
CREATE TABLE ramosolo.federated_identities (
    issuer varchar(350),
    subject varchar(255),
    user_id integer NOT NULL REFERENCES ramosolo.users(id) ON DELETE CASCADE,
    PRIMARY KEY (issuer, subject),
    UNIQUE (issuer, user_id)
);
CREATE INDEX ix_federated_identities_user_id ON ramosolo.federated_identities (user_id);
CREATE TABLE ramosolo.oidc_exchanges (
    token_hash varchar(64) PRIMARY KEY,
    expires_at bigint NOT NULL,
    session_hash varchar(64),
    code_verifier varchar(128),
    nonce varchar(128),
    issuer varchar(350) NOT NULL,
    subject varchar(255)
);
CREATE INDEX ix_oidc_exchanges_expires_at ON ramosolo.oidc_exchanges (expires_at);
ALTER TABLE ramosolo.federated_identities ENABLE ROW LEVEL SECURITY;
ALTER TABLE ramosolo.oidc_exchanges ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON ramosolo.federated_identities, ramosolo.oidc_exchanges FROM PUBLIC, anon, authenticated;
COMMIT;
