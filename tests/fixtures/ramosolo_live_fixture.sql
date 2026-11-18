-- SYNTHETIC LOCAL FIXTURE generated from metadata-only production snapshot.

-- No production data values are present. Apply only to a disposable local database.

-- Canonical constraint fingerprint (UTF-8 byte-length-prefixed): 6e42b7f83cb9357f5abc713146cc4d22.

-- PG17.11 EDB fixture profile fingerprint: 0ecc63c7f166d59e8d2a4c94de7aa685.

DO $$ BEGIN CREATE ROLE postgres NOLOGIN; EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN CREATE ROLE anon NOLOGIN; EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN CREATE ROLE authenticated NOLOGIN; EXCEPTION WHEN duplicate_object THEN NULL; END $$;

CREATE SCHEMA ramosolo AUTHORIZATION postgres;

GRANT USAGE, CREATE ON SCHEMA ramosolo TO postgres;

SET search_path TO ramosolo, public;

CREATE SEQUENCE ramosolo."admissions_id_seq" AS integer INCREMENT BY 1 MINVALUE 1 MAXVALUE 2147483647 START WITH 1 CACHE 1 NO CYCLE;

CREATE SEQUENCE ramosolo."appointment_attendance_events_id_seq" AS integer INCREMENT BY 1 MINVALUE 1 MAXVALUE 2147483647 START WITH 1 CACHE 1 NO CYCLE;

CREATE SEQUENCE ramosolo."appointment_confirmation_requests_id_seq" AS integer INCREMENT BY 1 MINVALUE 1 MAXVALUE 2147483647 START WITH 1 CACHE 1 NO CYCLE;

CREATE SEQUENCE ramosolo."appointments_id_seq" AS integer INCREMENT BY 1 MINVALUE 1 MAXVALUE 2147483647 START WITH 1 CACHE 1 NO CYCLE;

CREATE SEQUENCE ramosolo."attendance_followup_reviews_id_seq" AS integer INCREMENT BY 1 MINVALUE 1 MAXVALUE 2147483647 START WITH 1 CACHE 1 NO CYCLE;

CREATE SEQUENCE ramosolo."attendance_followups_id_seq" AS integer INCREMENT BY 1 MINVALUE 1 MAXVALUE 2147483647 START WITH 1 CACHE 1 NO CYCLE;

CREATE SEQUENCE ramosolo."audit_events_id_seq" AS integer INCREMENT BY 1 MINVALUE 1 MAXVALUE 2147483647 START WITH 1 CACHE 1 NO CYCLE;

CREATE SEQUENCE ramosolo."availability_exceptions_id_seq" AS integer INCREMENT BY 1 MINVALUE 1 MAXVALUE 2147483647 START WITH 1 CACHE 1 NO CYCLE;

CREATE SEQUENCE ramosolo."availability_policies_id_seq" AS integer INCREMENT BY 1 MINVALUE 1 MAXVALUE 2147483647 START WITH 1 CACHE 1 NO CYCLE;

CREATE SEQUENCE ramosolo."availability_sessions_id_seq" AS integer INCREMENT BY 1 MINVALUE 1 MAXVALUE 2147483647 START WITH 1 CACHE 1 NO CYCLE;

CREATE SEQUENCE ramosolo."booking_rate_limits_id_seq" AS integer INCREMENT BY 1 MINVALUE 1 MAXVALUE 2147483647 START WITH 1 CACHE 1 NO CYCLE;

CREATE SEQUENCE ramosolo."booking_requests_id_seq" AS integer INCREMENT BY 1 MINVALUE 1 MAXVALUE 2147483647 START WITH 1 CACHE 1 NO CYCLE;

CREATE SEQUENCE ramosolo."calendar_blocks_id_seq" AS integer INCREMENT BY 1 MINVALUE 1 MAXVALUE 2147483647 START WITH 1 CACHE 1 NO CYCLE;

CREATE SEQUENCE ramosolo."care_assignments_id_seq" AS integer INCREMENT BY 1 MINVALUE 1 MAXVALUE 2147483647 START WITH 1 CACHE 1 NO CYCLE;

CREATE SEQUENCE ramosolo."communication_preferences_id_seq" AS integer INCREMENT BY 1 MINVALUE 1 MAXVALUE 2147483647 START WITH 1 CACHE 1 NO CYCLE;

CREATE SEQUENCE ramosolo."demo_datasets_id_seq" AS integer INCREMENT BY 1 MINVALUE 1 MAXVALUE 2147483647 START WITH 1 CACHE 1 NO CYCLE;

CREATE SEQUENCE ramosolo."followup_policies_id_seq" AS integer INCREMENT BY 1 MINVALUE 1 MAXVALUE 2147483647 START WITH 1 CACHE 1 NO CYCLE;

CREATE SEQUENCE ramosolo."in_app_notifications_id_seq" AS integer INCREMENT BY 1 MINVALUE 1 MAXVALUE 2147483647 START WITH 1 CACHE 1 NO CYCLE;

CREATE SEQUENCE ramosolo."institutions_id_seq" AS integer INCREMENT BY 1 MINVALUE 1 MAXVALUE 2147483647 START WITH 1 CACHE 1 NO CYCLE;

CREATE SEQUENCE ramosolo."medical_invoices_id_seq" AS integer INCREMENT BY 1 MINVALUE 1 MAXVALUE 2147483647 START WITH 1 CACHE 1 NO CYCLE;

CREATE SEQUENCE ramosolo."medical_payment_entries_id_seq" AS integer INCREMENT BY 1 MINVALUE 1 MAXVALUE 2147483647 START WITH 1 CACHE 1 NO CYCLE;

CREATE SEQUENCE ramosolo."memberships_id_seq" AS integer INCREMENT BY 1 MINVALUE 1 MAXVALUE 2147483647 START WITH 1 CACHE 1 NO CYCLE;

CREATE SEQUENCE ramosolo."notification_attempts_id_seq" AS integer INCREMENT BY 1 MINVALUE 1 MAXVALUE 2147483647 START WITH 1 CACHE 1 NO CYCLE;

CREATE SEQUENCE ramosolo."notification_outbox_id_seq" AS integer INCREMENT BY 1 MINVALUE 1 MAXVALUE 2147483647 START WITH 1 CACHE 1 NO CYCLE;

CREATE SEQUENCE ramosolo."patients_id_seq" AS integer INCREMENT BY 1 MINVALUE 1 MAXVALUE 2147483647 START WITH 1 CACHE 1 NO CYCLE;

CREATE SEQUENCE ramosolo."public_holidays_id_seq" AS integer INCREMENT BY 1 MINVALUE 1 MAXVALUE 2147483647 START WITH 1 CACHE 1 NO CYCLE;

CREATE SEQUENCE ramosolo."reminder_leads_id_seq" AS integer INCREMENT BY 1 MINVALUE 1 MAXVALUE 2147483647 START WITH 1 CACHE 1 NO CYCLE;

CREATE SEQUENCE ramosolo."reminder_policies_id_seq" AS integer INCREMENT BY 1 MINVALUE 1 MAXVALUE 2147483647 START WITH 1 CACHE 1 NO CYCLE;

CREATE SEQUENCE ramosolo."users_id_seq" AS integer INCREMENT BY 1 MINVALUE 1 MAXVALUE 2147483647 START WITH 1 CACHE 1 NO CYCLE;

CREATE TABLE ramosolo."admissions" (
  "id" integer DEFAULT nextval('ramosolo.admissions_id_seq'::regclass) NOT NULL,
  "patient_id" integer NOT NULL,
  "facility" character varying(120) NOT NULL,
  "admitted_at" timestamp without time zone NOT NULL,
  "discharged_at" timestamp without time zone
);

CREATE TABLE ramosolo."appointment_attendance_events" (
  "id" integer DEFAULT nextval('ramosolo.appointment_attendance_events_id_seq'::regclass) NOT NULL,
  "institution_id" integer NOT NULL,
  "appointment_id" integer NOT NULL,
  "appointment_version" integer NOT NULL,
  "kind" character varying(32) NOT NULL,
  "previous_status" character varying(20),
  "status" character varying(20) NOT NULL,
  "previous_start" timestamp without time zone,
  "starts_at" timestamp without time zone NOT NULL,
  "actor_id" integer,
  "recorded_at" timestamp without time zone NOT NULL
);

CREATE TABLE ramosolo."appointment_confirmation_requests" (
  "id" integer DEFAULT nextval('ramosolo.appointment_confirmation_requests_id_seq'::regclass) NOT NULL,
  "institution_id" integer NOT NULL,
  "appointment_id" integer NOT NULL,
  "appointment_version" integer NOT NULL,
  "scheduled_start" timestamp without time zone NOT NULL,
  "deadline" timestamp without time zone NOT NULL,
  "requested_at" timestamp without time zone NOT NULL,
  "requested_by" integer NOT NULL,
  "policy_version" integer NOT NULL,
  "confirmed_at" timestamp without time zone,
  "confirmed_by" integer
);

CREATE TABLE ramosolo."appointments" (
  "id" integer DEFAULT nextval('ramosolo.appointments_id_seq'::regclass) NOT NULL,
  "patient_id" integer,
  "doctor_id" integer NOT NULL,
  "starts_at" timestamp without time zone NOT NULL,
  "status" character varying(20) NOT NULL,
  "service" character varying(100) NOT NULL,
  "institution_id" integer NOT NULL,
  "booking_request_id" integer,
  "submission_key" character varying(64),
  "submission_fingerprint" character varying(64),
  "ends_at" timestamp without time zone,
  "occupied_until" timestamp without time zone,
  "hold_expires_at" timestamp without time zone,
  "care_type" character varying(20),
  "visit_kind" character varying(20),
  "schedule_version" integer DEFAULT 1 NOT NULL,
  "calendar_uid" character varying(36) DEFAULT (gen_random_uuid())::text NOT NULL,
  "was_confirmed" boolean
);

CREATE TABLE ramosolo."attendance_followup_reviews" (
  "id" integer DEFAULT nextval('ramosolo.attendance_followup_reviews_id_seq'::regclass) NOT NULL,
  "institution_id" integer NOT NULL,
  "followup_id" integer NOT NULL,
  "actor_id" integer NOT NULL,
  "action" character varying(20) NOT NULL,
  "created_at" timestamp without time zone NOT NULL
);

CREATE TABLE ramosolo."attendance_followups" (
  "id" integer DEFAULT nextval('ramosolo.attendance_followups_id_seq'::regclass) NOT NULL,
  "institution_id" integer NOT NULL,
  "appointment_id" integer NOT NULL,
  "appointment_version" integer NOT NULL,
  "rule" character varying(32) NOT NULL,
  "policy_version" integer NOT NULL,
  "rule_version" character varying(32) NOT NULL,
  "reason" character varying(350) NOT NULL,
  "suggested_action" character varying(250) NOT NULL,
  "evidence" json NOT NULL,
  "state" character varying(20) NOT NULL,
  "revision" integer NOT NULL,
  "created_at" timestamp without time zone NOT NULL,
  "checked_at" timestamp without time zone NOT NULL,
  "obsolete_at" timestamp without time zone
);

CREATE TABLE ramosolo."audit_events" (
  "id" integer DEFAULT nextval('ramosolo.audit_events_id_seq'::regclass) NOT NULL,
  "institution_id" integer NOT NULL,
  "actor_id" integer NOT NULL,
  "action" character varying(80) NOT NULL,
  "resource_type" character varying(40) NOT NULL,
  "resource_id" integer NOT NULL,
  "created_at" timestamp without time zone NOT NULL
);

CREATE TABLE ramosolo."availability_exceptions" (
  "id" integer DEFAULT nextval('ramosolo.availability_exceptions_id_seq'::regclass) NOT NULL,
  "policy_id" integer NOT NULL,
  "day" date NOT NULL,
  "kind" character varying(20) NOT NULL,
  "care_type" character varying(20),
  "opens_at" time without time zone,
  "closes_at" time without time zone,
  "duration_minutes" integer,
  "first_minutes" integer,
  "assessment_minutes" integer,
  "break_minutes" integer,
  "override_closure" boolean NOT NULL,
  "approved_by" integer NOT NULL,
  "reason" character varying(200) NOT NULL,
  "approved_at" timestamp without time zone NOT NULL
);

CREATE TABLE ramosolo."availability_policies" (
  "id" integer DEFAULT nextval('ramosolo.availability_policies_id_seq'::regclass) NOT NULL,
  "institution_id" integer NOT NULL,
  "doctor_id" integer NOT NULL,
  "daily_limit" integer NOT NULL,
  "enabled" boolean NOT NULL,
  "holidays_confirmed" boolean NOT NULL,
  "horizon_days" integer NOT NULL,
  "hold_minutes" integer NOT NULL
);

CREATE TABLE ramosolo."availability_sessions" (
  "id" integer DEFAULT nextval('ramosolo.availability_sessions_id_seq'::regclass) NOT NULL,
  "policy_id" integer NOT NULL,
  "weekday" integer NOT NULL,
  "care_type" character varying(20) NOT NULL,
  "opens_at" time without time zone NOT NULL,
  "closes_at" time without time zone NOT NULL,
  "duration_minutes" integer NOT NULL,
  "first_minutes" integer NOT NULL,
  "assessment_minutes" integer NOT NULL,
  "break_minutes" integer NOT NULL
);

CREATE TABLE ramosolo."booking_rate_limits" (
  "id" integer DEFAULT nextval('ramosolo.booking_rate_limits_id_seq'::regclass) NOT NULL,
  "digest" character varying(64) NOT NULL,
  "window_start" timestamp without time zone NOT NULL,
  "attempts" integer NOT NULL
);

CREATE TABLE ramosolo."booking_requests" (
  "id" integer DEFAULT nextval('ramosolo.booking_requests_id_seq'::regclass) NOT NULL,
  "institution_id" integer NOT NULL,
  "name" character varying(120) NOT NULL,
  "email" character varying(254) NOT NULL,
  "phone" character varying(40) NOT NULL,
  "service" character varying(100) NOT NULL,
  "preferred_at" timestamp without time zone NOT NULL,
  "consent_at" timestamp without time zone NOT NULL,
  "status" character varying(20) NOT NULL,
  "submission_key" character varying(64),
  "submission_fingerprint" character varying(64),
  "token_digest" character varying(64),
  "token_expires_at" timestamp without time zone,
  "code_digest" character varying(64),
  "code_expires_at" timestamp without time zone,
  "verification_attempts" integer DEFAULT 0 NOT NULL,
  "requested_doctor_id" integer,
  "care_type" character varying(20),
  "visit_kind" character varying(20),
  "emergency_requested" boolean DEFAULT false NOT NULL
);

CREATE TABLE ramosolo."calendar_blocks" (
  "id" integer DEFAULT nextval('ramosolo.calendar_blocks_id_seq'::regclass) NOT NULL,
  "institution_id" integer NOT NULL,
  "doctor_id" integer NOT NULL,
  "starts_at" timestamp without time zone NOT NULL,
  "ends_at" timestamp without time zone NOT NULL,
  "reason" character varying(20) NOT NULL,
  "enabled" boolean NOT NULL,
  "released_by" integer,
  "released_at" timestamp without time zone,
  "created_by" integer NOT NULL,
  "created_at" timestamp without time zone NOT NULL
);

CREATE TABLE ramosolo."care_assignments" (
  "id" integer DEFAULT nextval('ramosolo.care_assignments_id_seq'::regclass) NOT NULL,
  "patient_id" integer NOT NULL,
  "nurse_id" integer NOT NULL
);

CREATE TABLE ramosolo."communication_preferences" (
  "id" integer DEFAULT nextval('ramosolo.communication_preferences_id_seq'::regclass) NOT NULL,
  "institution_id" integer NOT NULL,
  "patient_id" integer,
  "booking_request_id" integer,
  "in_app_enabled" boolean NOT NULL,
  "in_app_consent_at" timestamp without time zone,
  "email_enabled" boolean NOT NULL,
  "sms_enabled" boolean NOT NULL,
  "version" integer NOT NULL,
  "guest_verified_digest" character varying(64),
  "changed_by" integer,
  "changed_at" timestamp without time zone NOT NULL
);

CREATE TABLE ramosolo."demo_datasets" (
  "id" integer DEFAULT nextval('ramosolo.demo_datasets_id_seq'::regclass) NOT NULL,
  "name" character varying(80) NOT NULL,
  "anchor_date" date NOT NULL,
  "created_at" timestamp without time zone NOT NULL,
  "complete" boolean NOT NULL,
  "manifest" json NOT NULL
);

CREATE TABLE ramosolo."followup_policies" (
  "id" integer DEFAULT nextval('ramosolo.followup_policies_id_seq'::regclass) NOT NULL,
  "institution_id" integer NOT NULL,
  "enabled" boolean NOT NULL,
  "confirmation_enabled" boolean NOT NULL,
  "failure_enabled" boolean NOT NULL,
  "history_enabled" boolean NOT NULL,
  "version" integer NOT NULL,
  "confirmation_hours" integer NOT NULL,
  "lookahead_days" integer NOT NULL,
  "history_days" integer NOT NULL,
  "minimum_history" integer NOT NULL,
  "no_show_count" integer NOT NULL,
  "updated_by" integer NOT NULL,
  "updated_at" timestamp without time zone NOT NULL
);

CREATE TABLE ramosolo."in_app_notifications" (
  "id" integer DEFAULT nextval('ramosolo.in_app_notifications_id_seq'::regclass) NOT NULL,
  "public_id" character varying(36) NOT NULL,
  "institution_id" integer NOT NULL,
  "job_id" integer NOT NULL,
  "body" character varying(350) NOT NULL,
  "token_digest" character varying(64) NOT NULL,
  "expires_at" timestamp without time zone NOT NULL,
  "created_at" timestamp without time zone NOT NULL
);

CREATE TABLE ramosolo."institutions" (
  "id" integer DEFAULT nextval('ramosolo.institutions_id_seq'::regclass) NOT NULL,
  "name" character varying(150) NOT NULL,
  "kind" character varying(20) NOT NULL,
  "address" character varying(350),
  "demo_dataset_id" integer
);

CREATE TABLE ramosolo."medical_invoices" (
  "id" integer DEFAULT nextval('ramosolo.medical_invoices_id_seq'::regclass) NOT NULL,
  "institution_id" integer NOT NULL,
  "doctor_id" integer NOT NULL,
  "appointment_id" integer NOT NULL,
  "total" numeric(12,2) NOT NULL,
  "currency" character varying(3) NOT NULL,
  "state" character varying(12) NOT NULL,
  "voided_by" integer,
  "voided_at" timestamp without time zone,
  "created_by" integer NOT NULL,
  "created_at" timestamp without time zone NOT NULL
);

CREATE TABLE ramosolo."medical_payment_entries" (
  "id" integer DEFAULT nextval('ramosolo.medical_payment_entries_id_seq'::regclass) NOT NULL,
  "invoice_id" integer NOT NULL,
  "institution_id" integer NOT NULL,
  "kind" character varying(12) NOT NULL,
  "amount" numeric(12,2) NOT NULL,
  "method" character varying(20) NOT NULL,
  "original_receipt_id" integer,
  "reason" character varying(20) NOT NULL,
  "effective_at" timestamp without time zone NOT NULL,
  "recorded_at" timestamp without time zone NOT NULL,
  "actor_id" integer NOT NULL,
  "submission_key" character varying(64) NOT NULL,
  "submission_fingerprint" character varying(64) NOT NULL
);

CREATE TABLE ramosolo."memberships" (
  "id" integer DEFAULT nextval('ramosolo.memberships_id_seq'::regclass) NOT NULL,
  "user_id" integer NOT NULL,
  "institution_id" integer NOT NULL,
  "role" character varying(20) NOT NULL,
  "enabled" boolean NOT NULL,
  "supervising_doctor_id" integer
);

CREATE TABLE ramosolo."notification_attempts" (
  "id" integer DEFAULT nextval('ramosolo.notification_attempts_id_seq'::regclass) NOT NULL,
  "institution_id" integer NOT NULL,
  "job_id" integer NOT NULL,
  "number" integer NOT NULL,
  "outcome" character varying(24) NOT NULL,
  "result_code" character varying(40) NOT NULL,
  "created_at" timestamp without time zone NOT NULL
);

CREATE TABLE ramosolo."notification_outbox" (
  "id" integer DEFAULT nextval('ramosolo.notification_outbox_id_seq'::regclass) NOT NULL,
  "public_id" character varying(36) NOT NULL,
  "institution_id" integer NOT NULL,
  "appointment_id" integer NOT NULL,
  "appointment_version" integer NOT NULL,
  "scheduled_start" timestamp without time zone NOT NULL,
  "preference_id" integer NOT NULL,
  "recipient_user_id" integer,
  "preference_version" integer NOT NULL,
  "consent_at" timestamp without time zone NOT NULL,
  "policy_id" integer NOT NULL,
  "policy_version" integer NOT NULL,
  "lead_minutes" integer NOT NULL,
  "channel" character varying(16) NOT NULL,
  "due_at" timestamp without time zone NOT NULL,
  "next_attempt_at" timestamp without time zone NOT NULL,
  "state" character varying(16) NOT NULL,
  "attempt_count" integer NOT NULL,
  "max_attempts" integer NOT NULL,
  "sent_at" timestamp without time zone,
  "invalidated_at" timestamp without time zone,
  "result_code" character varying(40),
  "created_at" timestamp without time zone NOT NULL
);

CREATE TABLE ramosolo."patients" (
  "id" integer DEFAULT nextval('ramosolo.patients_id_seq'::regclass) NOT NULL,
  "institution_id" integer NOT NULL,
  "user_id" integer,
  "doctor_id" integer NOT NULL,
  "name" character varying(120) NOT NULL,
  "email" character varying(254),
  "phone" character varying(40)
);

CREATE TABLE ramosolo."public_holidays" (
  "id" integer DEFAULT nextval('ramosolo.public_holidays_id_seq'::regclass) NOT NULL,
  "institution_id" integer NOT NULL,
  "day" date NOT NULL,
  "label" character varying(120) NOT NULL
);

CREATE TABLE ramosolo."reminder_leads" (
  "id" integer DEFAULT nextval('ramosolo.reminder_leads_id_seq'::regclass) NOT NULL,
  "policy_id" integer NOT NULL,
  "minutes" integer NOT NULL
);

CREATE TABLE ramosolo."reminder_policies" (
  "id" integer DEFAULT nextval('ramosolo.reminder_policies_id_seq'::regclass) NOT NULL,
  "institution_id" integer NOT NULL,
  "enabled" boolean NOT NULL,
  "version" integer NOT NULL,
  "max_attempts" integer NOT NULL,
  "retry_seconds" integer NOT NULL,
  "link_minutes" integer NOT NULL,
  "catchup_minutes" integer NOT NULL,
  "updated_by" integer NOT NULL,
  "updated_at" timestamp without time zone NOT NULL
);

CREATE TABLE ramosolo."schema_versions" (
  "version" integer NOT NULL,
  "applied_at" timestamp with time zone DEFAULT now() NOT NULL
);

CREATE TABLE ramosolo."users" (
  "id" integer DEFAULT nextval('ramosolo.users_id_seq'::regclass) NOT NULL,
  "name" character varying(120) NOT NULL,
  "email" character varying(254) NOT NULL,
  "password_hash" character varying(255) NOT NULL,
  "enabled" boolean NOT NULL,
  "session_version" integer NOT NULL,
  "failed_logins" integer NOT NULL,
  "locked_until" timestamp without time zone
);

ALTER TABLE ramosolo."admissions" ADD CONSTRAINT "admissions_pkey" PRIMARY KEY (id);

ALTER TABLE ramosolo."admissions" ADD CONSTRAINT "admissions_check" CHECK (((discharged_at IS NULL) OR (discharged_at >= admitted_at)));

ALTER TABLE ramosolo."memberships" ADD CONSTRAINT "memberships_pkey" PRIMARY KEY (id);

ALTER TABLE ramosolo."memberships" ADD CONSTRAINT "memberships_role_check" CHECK (((role)::text = ANY ((ARRAY['dr'::character varying, 'nurse'::character varying, 'admin'::character varying, 'dr_assist'::character varying, 'patient'::character varying])::text[])));

ALTER TABLE ramosolo."memberships" ADD CONSTRAINT "memberships_user_id_institution_id_key" UNIQUE (user_id, institution_id);

ALTER TABLE ramosolo."appointments" ADD CONSTRAINT "appointments_pkey" PRIMARY KEY (id);

ALTER TABLE ramosolo."appointments" ADD CONSTRAINT "appointment_identity" CHECK (((patient_id IS NOT NULL) <> (booking_request_id IS NOT NULL)));

ALTER TABLE ramosolo."appointments" ADD CONSTRAINT "appointment_interval" CHECK (((ends_at IS NULL) OR ((ends_at > starts_at) AND (occupied_until >= ends_at))));

ALTER TABLE ramosolo."appointments" ADD CONSTRAINT "appointments_status_check" CHECK (((status)::text = ANY ((ARRAY['scheduled'::character varying, 'held'::character varying, 'expired'::character varying, 'completed'::character varying, 'cancelled'::character varying, 'no_show'::character varying])::text[])));

ALTER TABLE ramosolo."appointments" ADD CONSTRAINT "appointments_calendar_uid_key" UNIQUE (calendar_uid);

ALTER TABLE ramosolo."appointments" ADD CONSTRAINT "appointments_submission_key_key" UNIQUE (submission_key);

ALTER TABLE ramosolo."appointments" ADD CONSTRAINT "appointments_booking_request_id_key" UNIQUE (booking_request_id);

ALTER TABLE ramosolo."audit_events" ADD CONSTRAINT "audit_events_pkey" PRIMARY KEY (id);

ALTER TABLE ramosolo."institutions" ADD CONSTRAINT "institutions_pkey" PRIMARY KEY (id);

ALTER TABLE ramosolo."institutions" ADD CONSTRAINT "institutions_kind_check" CHECK (((kind)::text = ANY ((ARRAY['medical'::character varying, 'education'::character varying])::text[])));

ALTER TABLE ramosolo."demo_datasets" ADD CONSTRAINT "demo_datasets_pkey" PRIMARY KEY (id);

ALTER TABLE ramosolo."demo_datasets" ADD CONSTRAINT "demo_datasets_name_key" UNIQUE (name);

ALTER TABLE ramosolo."reminder_leads" ADD CONSTRAINT "reminder_leads_pkey" PRIMARY KEY (id);

ALTER TABLE ramosolo."reminder_leads" ADD CONSTRAINT "reminder_leads_minutes_check" CHECK (((minutes >= 1) AND (minutes <= 43200)));

ALTER TABLE ramosolo."reminder_leads" ADD CONSTRAINT "reminder_leads_policy_id_minutes_key" UNIQUE (policy_id, minutes);

ALTER TABLE ramosolo."calendar_blocks" ADD CONSTRAINT "calendar_blocks_pkey" PRIMARY KEY (id);

ALTER TABLE ramosolo."calendar_blocks" ADD CONSTRAINT "calendar_blocks_check" CHECK ((ends_at > starts_at));

ALTER TABLE ramosolo."calendar_blocks" ADD CONSTRAINT "calendar_blocks_reason_check" CHECK (((reason)::text = ANY ((ARRAY['administration'::character varying, 'unavailable'::character varying, 'leave'::character varying])::text[])));

ALTER TABLE ramosolo."public_holidays" ADD CONSTRAINT "public_holidays_pkey" PRIMARY KEY (id);

ALTER TABLE ramosolo."public_holidays" ADD CONSTRAINT "public_holidays_institution_id_day_key" UNIQUE (institution_id, day);

ALTER TABLE ramosolo."schema_versions" ADD CONSTRAINT "schema_versions_pkey" PRIMARY KEY (version);

ALTER TABLE ramosolo."booking_requests" ADD CONSTRAINT "booking_requests_pkey" PRIMARY KEY (id);

ALTER TABLE ramosolo."booking_requests" ADD CONSTRAINT "booking_requests_token_digest_key" UNIQUE (token_digest);

ALTER TABLE ramosolo."booking_requests" ADD CONSTRAINT "booking_requests_submission_key_key" UNIQUE (submission_key);

ALTER TABLE ramosolo."care_assignments" ADD CONSTRAINT "care_assignments_pkey" PRIMARY KEY (id);

ALTER TABLE ramosolo."care_assignments" ADD CONSTRAINT "care_assignments_patient_id_nurse_id_key" UNIQUE (patient_id, nurse_id);

ALTER TABLE ramosolo."medical_invoices" ADD CONSTRAINT "medical_invoices_pkey" PRIMARY KEY (id);

ALTER TABLE ramosolo."medical_invoices" ADD CONSTRAINT "medical_invoices_check" CHECK ((((currency)::text = 'ZAR'::text) AND (total > (0)::numeric)));

ALTER TABLE ramosolo."medical_invoices" ADD CONSTRAINT "medical_invoices_state_check" CHECK (((state)::text = ANY ((ARRAY['issued'::character varying, 'void'::character varying])::text[])));

ALTER TABLE ramosolo."medical_invoices" ADD CONSTRAINT "medical_invoices_appointment_id_key" UNIQUE (appointment_id);

ALTER TABLE ramosolo."followup_policies" ADD CONSTRAINT "followup_policies_pkey" PRIMARY KEY (id);

ALTER TABLE ramosolo."followup_policies" ADD CONSTRAINT "followup_policies_check" CHECK (((version > 0) AND ((confirmation_hours >= 1) AND (confirmation_hours <= 720)) AND ((lookahead_days >= 1) AND (lookahead_days <= 90)) AND ((history_days >= 1) AND (history_days <= 730)) AND ((minimum_history >= 1) AND (minimum_history <= 100)) AND ((no_show_count >= 1) AND (no_show_count <= 100)) AND (no_show_count <= minimum_history)));

ALTER TABLE ramosolo."followup_policies" ADD CONSTRAINT "followup_policies_institution_id_key" UNIQUE (institution_id);

ALTER TABLE ramosolo."reminder_policies" ADD CONSTRAINT "reminder_policies_pkey" PRIMARY KEY (id);

ALTER TABLE ramosolo."reminder_policies" ADD CONSTRAINT "reminder_policies_check" CHECK ((((max_attempts >= 1) AND (max_attempts <= 10)) AND ((retry_seconds >= 1) AND (retry_seconds <= 3600)) AND ((link_minutes >= 1) AND (link_minutes <= 10080)) AND ((catchup_minutes >= 0) AND (catchup_minutes <= 1440))));

ALTER TABLE ramosolo."reminder_policies" ADD CONSTRAINT "reminder_policies_institution_id_key" UNIQUE (institution_id);

ALTER TABLE ramosolo."booking_rate_limits" ADD CONSTRAINT "booking_rate_limits_pkey" PRIMARY KEY (id);

ALTER TABLE ramosolo."booking_rate_limits" ADD CONSTRAINT "booking_rate_limits_digest_window_start_key" UNIQUE (digest, window_start);

ALTER TABLE ramosolo."notification_outbox" ADD CONSTRAINT "notification_outbox_pkey" PRIMARY KEY (id);

ALTER TABLE ramosolo."notification_outbox" ADD CONSTRAINT "notification_outbox_check" CHECK (((attempt_count >= 0) AND ((max_attempts >= 1) AND (max_attempts <= 10)) AND (attempt_count <= max_attempts)));

ALTER TABLE ramosolo."notification_outbox" ADD CONSTRAINT "notification_outbox_check1" CHECK (((((state)::text = 'sent'::text) AND (sent_at IS NOT NULL)) OR (((state)::text <> 'sent'::text) AND (sent_at IS NULL))));

ALTER TABLE ramosolo."notification_outbox" ADD CONSTRAINT "notification_outbox_state_check" CHECK (((state)::text = ANY ((ARRAY['pending'::character varying, 'sent'::character varying, 'failed'::character varying, 'cancelled'::character varying])::text[])));

ALTER TABLE ramosolo."notification_outbox" ADD CONSTRAINT "notification_outbox_channel_check" CHECK (((channel)::text = 'in_app'::text));

ALTER TABLE ramosolo."notification_outbox" ADD CONSTRAINT "notification_outbox_public_id_key" UNIQUE (public_id);

ALTER TABLE ramosolo."notification_outbox" ADD CONSTRAINT "notification_outbox_appointment_id_appointment_version_pref_key" UNIQUE (appointment_id, appointment_version, preference_id, preference_version, policy_version, lead_minutes, channel);

ALTER TABLE ramosolo."attendance_followups" ADD CONSTRAINT "attendance_followups_pkey" PRIMARY KEY (id);

ALTER TABLE ramosolo."attendance_followups" ADD CONSTRAINT "attendance_followups_rule_check" CHECK (((rule)::text = ANY ((ARRAY['confirmation_due'::character varying, 'delivery_failed'::character varying, 'attendance_history'::character varying])::text[])));

ALTER TABLE ramosolo."attendance_followups" ADD CONSTRAINT "attendance_followups_state_check" CHECK (((state)::text = ANY ((ARRAY['open'::character varying, 'acknowledged'::character varying, 'dismissed'::character varying, 'resolved'::character varying, 'obsolete'::character varying])::text[])));

ALTER TABLE ramosolo."attendance_followups" ADD CONSTRAINT "attendance_followups_appointment_id_appointment_version_rul_key" UNIQUE (appointment_id, appointment_version, rule, policy_version);

ALTER TABLE ramosolo."in_app_notifications" ADD CONSTRAINT "in_app_notifications_pkey" PRIMARY KEY (id);

ALTER TABLE ramosolo."in_app_notifications" ADD CONSTRAINT "in_app_notifications_job_id_key" UNIQUE (job_id);

ALTER TABLE ramosolo."in_app_notifications" ADD CONSTRAINT "in_app_notifications_public_id_key" UNIQUE (public_id);

ALTER TABLE ramosolo."in_app_notifications" ADD CONSTRAINT "in_app_notifications_token_digest_key" UNIQUE (token_digest);

ALTER TABLE ramosolo."availability_policies" ADD CONSTRAINT "availability_policies_pkey" PRIMARY KEY (id);

ALTER TABLE ramosolo."availability_policies" ADD CONSTRAINT "availability_policies_check" CHECK (((daily_limit > 0) AND ((horizon_days >= 1) AND (horizon_days <= 366)) AND ((hold_minutes >= 1) AND (hold_minutes <= 30))));

ALTER TABLE ramosolo."availability_policies" ADD CONSTRAINT "availability_policies_institution_id_doctor_id_key" UNIQUE (institution_id, doctor_id);

ALTER TABLE ramosolo."availability_sessions" ADD CONSTRAINT "availability_sessions_pkey" PRIMARY KEY (id);

ALTER TABLE ramosolo."availability_sessions" ADD CONSTRAINT "availability_sessions_check" CHECK (((((care_type)::text = 'outpatient'::text) AND (weekday = 2)) OR (((care_type)::text = 'inpatient'::text) AND (weekday = ANY (ARRAY[0, 1, 2, 4])))));

ALTER TABLE ramosolo."availability_sessions" ADD CONSTRAINT "availability_sessions_check1" CHECK ((opens_at < closes_at));

ALTER TABLE ramosolo."availability_sessions" ADD CONSTRAINT "availability_sessions_check2" CHECK (((((care_type)::text = 'outpatient'::text) AND ((duration_minutes >= 30) AND (duration_minutes <= 60))) OR (((care_type)::text = 'inpatient'::text) AND ((duration_minutes >= 20) AND (duration_minutes <= 30)))));

ALTER TABLE ramosolo."availability_sessions" ADD CONSTRAINT "availability_sessions_check3" CHECK ((((first_minutes >= 60) AND (first_minutes <= 120)) AND ((assessment_minutes >= 1) AND (assessment_minutes <= 240)) AND ((break_minutes >= 5) AND (break_minutes <= 10))));

ALTER TABLE ramosolo."notification_attempts" ADD CONSTRAINT "positive_attempt_number" CHECK ((number >= 1));

ALTER TABLE ramosolo."notification_attempts" ADD CONSTRAINT "notification_attempts_pkey" PRIMARY KEY (id);

ALTER TABLE ramosolo."notification_attempts" ADD CONSTRAINT "notification_attempts_outcome_check" CHECK (((outcome)::text = ANY ((ARRAY['sent'::character varying, 'transient_failure'::character varying, 'permanent_failure'::character varying])::text[])));

ALTER TABLE ramosolo."notification_attempts" ADD CONSTRAINT "notification_attempts_job_id_number_key" UNIQUE (job_id, number);

ALTER TABLE ramosolo."availability_exceptions" ADD CONSTRAINT "availability_exceptions_pkey" PRIMARY KEY (id);

ALTER TABLE ramosolo."availability_exceptions" ADD CONSTRAINT "availability_exceptions_check" CHECK ((((kind)::text <> 'opening'::text) OR (((care_type)::text = ANY ((ARRAY['inpatient'::character varying, 'outpatient'::character varying])::text[])) AND (opens_at IS NOT NULL) AND (closes_at IS NOT NULL) AND (opens_at < closes_at) AND (duration_minutes IS NOT NULL) AND (first_minutes IS NOT NULL) AND (assessment_minutes IS NOT NULL) AND (break_minutes IS NOT NULL) AND ((first_minutes >= 60) AND (first_minutes <= 120)) AND ((assessment_minutes >= 1) AND (assessment_minutes <= 240)) AND ((break_minutes >= 5) AND (break_minutes <= 10)) AND ((((care_type)::text = 'outpatient'::text) AND ((duration_minutes >= 30) AND (duration_minutes <= 60))) OR (((care_type)::text = 'inpatient'::text) AND ((duration_minutes >= 20) AND (duration_minutes <= 30)))))));

ALTER TABLE ramosolo."availability_exceptions" ADD CONSTRAINT "availability_exceptions_kind_check" CHECK (((kind)::text = ANY ((ARRAY['opening'::character varying, 'leave'::character varying, 'closure'::character varying])::text[])));

ALTER TABLE ramosolo."medical_payment_entries" ADD CONSTRAINT "medical_payment_entries_pkey" PRIMARY KEY (id);

ALTER TABLE ramosolo."medical_payment_entries" ADD CONSTRAINT "medical_payment_entries_check" CHECK (((((kind)::text = 'receipt'::text) AND (original_receipt_id IS NULL) AND ((reason)::text = 'received'::text)) OR (((kind)::text = 'refund'::text) AND (original_receipt_id IS NOT NULL) AND ((reason)::text <> 'received'::text))));

ALTER TABLE ramosolo."medical_payment_entries" ADD CONSTRAINT "medical_payment_entries_kind_check" CHECK (((kind)::text = ANY ((ARRAY['receipt'::character varying, 'refund'::character varying])::text[])));

ALTER TABLE ramosolo."medical_payment_entries" ADD CONSTRAINT "medical_payment_entries_amount_check" CHECK ((amount > (0)::numeric));

ALTER TABLE ramosolo."medical_payment_entries" ADD CONSTRAINT "medical_payment_entries_method_check" CHECK (((method)::text = ANY ((ARRAY['cash'::character varying, 'eft'::character varying, 'medical_aid'::character varying, 'other'::character varying])::text[])));

ALTER TABLE ramosolo."medical_payment_entries" ADD CONSTRAINT "medical_payment_entries_reason_check" CHECK (((reason)::text = ANY ((ARRAY['received'::character varying, 'refund'::character varying, 'correction'::character varying, 'duplicate'::character varying])::text[])));

ALTER TABLE ramosolo."medical_payment_entries" ADD CONSTRAINT "medical_payment_entries_submission_key_key" UNIQUE (submission_key);

ALTER TABLE ramosolo."communication_preferences" ADD CONSTRAINT "communication_preferences_pkey" PRIMARY KEY (id);

ALTER TABLE ramosolo."communication_preferences" ADD CONSTRAINT "communication_preferences_check" CHECK (((patient_id IS NOT NULL) <> (booking_request_id IS NOT NULL)));

ALTER TABLE ramosolo."communication_preferences" ADD CONSTRAINT "communication_preferences_check1" CHECK (((NOT in_app_enabled) OR (in_app_consent_at IS NOT NULL)));

ALTER TABLE ramosolo."communication_preferences" ADD CONSTRAINT "communication_preferences_check2" CHECK (((NOT email_enabled) AND (NOT sms_enabled)));

ALTER TABLE ramosolo."communication_preferences" ADD CONSTRAINT "communication_preferences_institution_id_patient_id_key" UNIQUE (institution_id, patient_id);

ALTER TABLE ramosolo."communication_preferences" ADD CONSTRAINT "communication_preferences_institution_id_booking_request_id_key" UNIQUE (institution_id, booking_request_id);

ALTER TABLE ramosolo."attendance_followup_reviews" ADD CONSTRAINT "attendance_followup_reviews_pkey" PRIMARY KEY (id);

ALTER TABLE ramosolo."attendance_followup_reviews" ADD CONSTRAINT "attendance_followup_reviews_action_check" CHECK (((action)::text = ANY ((ARRAY['acknowledged'::character varying, 'dismissed'::character varying, 'resolved'::character varying])::text[])));

ALTER TABLE ramosolo."appointment_attendance_events" ADD CONSTRAINT "appointment_attendance_events_pkey" PRIMARY KEY (id);

ALTER TABLE ramosolo."appointment_attendance_events" ADD CONSTRAINT "appointment_attendance_events_kind_check" CHECK (((kind)::text = ANY ((ARRAY['baseline'::character varying, 'created'::character varying, 'changed'::character varying, 'confirmation_requested'::character varying, 'response_recorded'::character varying])::text[])));

ALTER TABLE ramosolo."appointment_confirmation_requests" ADD CONSTRAINT "appointment_confirmation_requests_pkey" PRIMARY KEY (id);

ALTER TABLE ramosolo."appointment_confirmation_requests" ADD CONSTRAINT "appointment_confirmation_requests_check" CHECK (((deadline < scheduled_start) AND (requested_at <= deadline)));

ALTER TABLE ramosolo."appointment_confirmation_requests" ADD CONSTRAINT "appointment_confirmation_requests_check1" CHECK (((confirmed_at IS NULL) = (confirmed_by IS NULL)));

ALTER TABLE ramosolo."appointment_confirmation_requests" ADD CONSTRAINT "appointment_confirmation_requ_appointment_id_appointment_ve_key" UNIQUE (appointment_id, appointment_version);

ALTER TABLE ramosolo."users" ADD CONSTRAINT "users_pkey" PRIMARY KEY (id);

ALTER TABLE ramosolo."users" ADD CONSTRAINT "users_email_key" UNIQUE (email);

ALTER TABLE ramosolo."patients" ADD CONSTRAINT "patients_pkey" PRIMARY KEY (id);

ALTER TABLE ramosolo."patients" ADD CONSTRAINT "patients_institution_id_user_id_key" UNIQUE (institution_id, user_id);

CREATE INDEX booking_capacity ON ramosolo.appointments USING btree (doctor_id, starts_at, status, hold_expires_at);

CREATE INDEX doctor_calendar_blocks ON ramosolo.calendar_blocks USING btree (doctor_id, starts_at, ends_at);

CREATE INDEX ix_admissions_patient_id ON ramosolo.admissions USING btree (patient_id);

CREATE INDEX ix_appointment_attendance_events_appointment_id ON ramosolo.appointment_attendance_events USING btree (appointment_id);

CREATE INDEX ix_appointments_patient_id ON ramosolo.appointments USING btree (patient_id);

CREATE INDEX ix_appointments_starts_at ON ramosolo.appointments USING btree (starts_at);

CREATE INDEX ix_attendance_followup_reviews_followup_id ON ramosolo.attendance_followup_reviews USING btree (followup_id);

CREATE INDEX ix_attendance_followups_appointment_id ON ramosolo.attendance_followups USING btree (appointment_id);

CREATE INDEX ix_medical_payment_entries_invoice_id ON ramosolo.medical_payment_entries USING btree (invoice_id);

CREATE INDEX notification_due ON ramosolo.notification_outbox USING btree (institution_id, state, next_attempt_at);

CREATE UNIQUE INDEX one_doctor_slot ON ramosolo.appointments USING btree (doctor_id, starts_at) WHERE ((status)::text = 'scheduled'::text);

CREATE UNIQUE INDEX one_open_admission ON ramosolo.admissions USING btree (patient_id) WHERE (discharged_at IS NULL);

CREATE UNIQUE INDEX one_patient_slot ON ramosolo.appointments USING btree (patient_id, starts_at) WHERE ((status)::text = 'scheduled'::text);

CREATE UNIQUE INDEX one_sent_appointment_reminder ON ramosolo.notification_outbox USING btree (appointment_id, appointment_version, lead_minutes, channel) WHERE ((state)::text = 'sent'::text);

ALTER TABLE ramosolo."admissions" ADD CONSTRAINT "admissions_patient_id_fkey" FOREIGN KEY (patient_id) REFERENCES ramosolo.patients(id);

ALTER TABLE ramosolo."memberships" ADD CONSTRAINT "memberships_user_id_fkey" FOREIGN KEY (user_id) REFERENCES ramosolo.users(id);

ALTER TABLE ramosolo."memberships" ADD CONSTRAINT "memberships_institution_id_fkey" FOREIGN KEY (institution_id) REFERENCES ramosolo.institutions(id);

ALTER TABLE ramosolo."memberships" ADD CONSTRAINT "memberships_supervising_doctor_id_fkey" FOREIGN KEY (supervising_doctor_id) REFERENCES ramosolo.users(id);

ALTER TABLE ramosolo."appointments" ADD CONSTRAINT "appointments_doctor_id_fkey" FOREIGN KEY (doctor_id) REFERENCES ramosolo.users(id);

ALTER TABLE ramosolo."appointments" ADD CONSTRAINT "appointments_patient_id_fkey" FOREIGN KEY (patient_id) REFERENCES ramosolo.patients(id);

ALTER TABLE ramosolo."appointments" ADD CONSTRAINT "appointments_institution_id_fkey" FOREIGN KEY (institution_id) REFERENCES ramosolo.institutions(id);

ALTER TABLE ramosolo."appointments" ADD CONSTRAINT "appointments_booking_request_id_fkey" FOREIGN KEY (booking_request_id) REFERENCES ramosolo.booking_requests(id);

ALTER TABLE ramosolo."audit_events" ADD CONSTRAINT "audit_events_actor_id_fkey" FOREIGN KEY (actor_id) REFERENCES ramosolo.users(id);

ALTER TABLE ramosolo."audit_events" ADD CONSTRAINT "audit_events_institution_id_fkey" FOREIGN KEY (institution_id) REFERENCES ramosolo.institutions(id);

ALTER TABLE ramosolo."institutions" ADD CONSTRAINT "institutions_demo_dataset_id_fkey" FOREIGN KEY (demo_dataset_id) REFERENCES ramosolo.demo_datasets(id);

ALTER TABLE ramosolo."reminder_leads" ADD CONSTRAINT "reminder_leads_policy_id_fkey" FOREIGN KEY (policy_id) REFERENCES ramosolo.reminder_policies(id);

ALTER TABLE ramosolo."calendar_blocks" ADD CONSTRAINT "calendar_blocks_doctor_id_fkey" FOREIGN KEY (doctor_id) REFERENCES ramosolo.users(id);

ALTER TABLE ramosolo."calendar_blocks" ADD CONSTRAINT "calendar_blocks_created_by_fkey" FOREIGN KEY (created_by) REFERENCES ramosolo.users(id);

ALTER TABLE ramosolo."calendar_blocks" ADD CONSTRAINT "calendar_blocks_released_by_fkey" FOREIGN KEY (released_by) REFERENCES ramosolo.users(id);

ALTER TABLE ramosolo."calendar_blocks" ADD CONSTRAINT "calendar_blocks_institution_id_fkey" FOREIGN KEY (institution_id) REFERENCES ramosolo.institutions(id);

ALTER TABLE ramosolo."public_holidays" ADD CONSTRAINT "public_holidays_institution_id_fkey" FOREIGN KEY (institution_id) REFERENCES ramosolo.institutions(id);

ALTER TABLE ramosolo."booking_requests" ADD CONSTRAINT "booking_requests_institution_id_fkey" FOREIGN KEY (institution_id) REFERENCES ramosolo.institutions(id);

ALTER TABLE ramosolo."booking_requests" ADD CONSTRAINT "booking_requests_requested_doctor_id_fkey" FOREIGN KEY (requested_doctor_id) REFERENCES ramosolo.users(id);

ALTER TABLE ramosolo."care_assignments" ADD CONSTRAINT "care_assignments_nurse_id_fkey" FOREIGN KEY (nurse_id) REFERENCES ramosolo.users(id);

ALTER TABLE ramosolo."care_assignments" ADD CONSTRAINT "care_assignments_patient_id_fkey" FOREIGN KEY (patient_id) REFERENCES ramosolo.patients(id);

ALTER TABLE ramosolo."medical_invoices" ADD CONSTRAINT "medical_invoices_doctor_id_fkey" FOREIGN KEY (doctor_id) REFERENCES ramosolo.users(id);

ALTER TABLE ramosolo."medical_invoices" ADD CONSTRAINT "medical_invoices_voided_by_fkey" FOREIGN KEY (voided_by) REFERENCES ramosolo.users(id);

ALTER TABLE ramosolo."medical_invoices" ADD CONSTRAINT "medical_invoices_created_by_fkey" FOREIGN KEY (created_by) REFERENCES ramosolo.users(id);

ALTER TABLE ramosolo."medical_invoices" ADD CONSTRAINT "medical_invoices_appointment_id_fkey" FOREIGN KEY (appointment_id) REFERENCES ramosolo.appointments(id);

ALTER TABLE ramosolo."medical_invoices" ADD CONSTRAINT "medical_invoices_institution_id_fkey" FOREIGN KEY (institution_id) REFERENCES ramosolo.institutions(id);

ALTER TABLE ramosolo."followup_policies" ADD CONSTRAINT "followup_policies_updated_by_fkey" FOREIGN KEY (updated_by) REFERENCES ramosolo.users(id);

ALTER TABLE ramosolo."followup_policies" ADD CONSTRAINT "followup_policies_institution_id_fkey" FOREIGN KEY (institution_id) REFERENCES ramosolo.institutions(id);

ALTER TABLE ramosolo."reminder_policies" ADD CONSTRAINT "reminder_policies_updated_by_fkey" FOREIGN KEY (updated_by) REFERENCES ramosolo.users(id);

ALTER TABLE ramosolo."reminder_policies" ADD CONSTRAINT "reminder_policies_institution_id_fkey" FOREIGN KEY (institution_id) REFERENCES ramosolo.institutions(id);

ALTER TABLE ramosolo."notification_outbox" ADD CONSTRAINT "notification_outbox_policy_id_fkey" FOREIGN KEY (policy_id) REFERENCES ramosolo.reminder_policies(id);

ALTER TABLE ramosolo."notification_outbox" ADD CONSTRAINT "notification_outbox_preference_id_fkey" FOREIGN KEY (preference_id) REFERENCES ramosolo.communication_preferences(id);

ALTER TABLE ramosolo."notification_outbox" ADD CONSTRAINT "notification_outbox_appointment_id_fkey" FOREIGN KEY (appointment_id) REFERENCES ramosolo.appointments(id);

ALTER TABLE ramosolo."notification_outbox" ADD CONSTRAINT "notification_outbox_institution_id_fkey" FOREIGN KEY (institution_id) REFERENCES ramosolo.institutions(id);

ALTER TABLE ramosolo."notification_outbox" ADD CONSTRAINT "notification_outbox_recipient_user_id_fkey" FOREIGN KEY (recipient_user_id) REFERENCES ramosolo.users(id);

ALTER TABLE ramosolo."attendance_followups" ADD CONSTRAINT "attendance_followups_appointment_id_fkey" FOREIGN KEY (appointment_id) REFERENCES ramosolo.appointments(id);

ALTER TABLE ramosolo."attendance_followups" ADD CONSTRAINT "attendance_followups_institution_id_fkey" FOREIGN KEY (institution_id) REFERENCES ramosolo.institutions(id);

ALTER TABLE ramosolo."in_app_notifications" ADD CONSTRAINT "in_app_notifications_job_id_fkey" FOREIGN KEY (job_id) REFERENCES ramosolo.notification_outbox(id);

ALTER TABLE ramosolo."in_app_notifications" ADD CONSTRAINT "in_app_notifications_institution_id_fkey" FOREIGN KEY (institution_id) REFERENCES ramosolo.institutions(id);

ALTER TABLE ramosolo."availability_policies" ADD CONSTRAINT "availability_policies_doctor_id_fkey" FOREIGN KEY (doctor_id) REFERENCES ramosolo.users(id);

ALTER TABLE ramosolo."availability_policies" ADD CONSTRAINT "availability_policies_institution_id_fkey" FOREIGN KEY (institution_id) REFERENCES ramosolo.institutions(id);

ALTER TABLE ramosolo."availability_sessions" ADD CONSTRAINT "availability_sessions_policy_id_fkey" FOREIGN KEY (policy_id) REFERENCES ramosolo.availability_policies(id);

ALTER TABLE ramosolo."notification_attempts" ADD CONSTRAINT "notification_attempts_job_id_fkey" FOREIGN KEY (job_id) REFERENCES ramosolo.notification_outbox(id);

ALTER TABLE ramosolo."notification_attempts" ADD CONSTRAINT "notification_attempts_institution_id_fkey" FOREIGN KEY (institution_id) REFERENCES ramosolo.institutions(id);

ALTER TABLE ramosolo."availability_exceptions" ADD CONSTRAINT "availability_exceptions_policy_id_fkey" FOREIGN KEY (policy_id) REFERENCES ramosolo.availability_policies(id);

ALTER TABLE ramosolo."availability_exceptions" ADD CONSTRAINT "availability_exceptions_approved_by_fkey" FOREIGN KEY (approved_by) REFERENCES ramosolo.users(id);

ALTER TABLE ramosolo."medical_payment_entries" ADD CONSTRAINT "medical_payment_entries_actor_id_fkey" FOREIGN KEY (actor_id) REFERENCES ramosolo.users(id);

ALTER TABLE ramosolo."medical_payment_entries" ADD CONSTRAINT "medical_payment_entries_invoice_id_fkey" FOREIGN KEY (invoice_id) REFERENCES ramosolo.medical_invoices(id);

ALTER TABLE ramosolo."medical_payment_entries" ADD CONSTRAINT "medical_payment_entries_institution_id_fkey" FOREIGN KEY (institution_id) REFERENCES ramosolo.institutions(id);

ALTER TABLE ramosolo."medical_payment_entries" ADD CONSTRAINT "medical_payment_entries_original_receipt_id_fkey" FOREIGN KEY (original_receipt_id) REFERENCES ramosolo.medical_payment_entries(id);

ALTER TABLE ramosolo."communication_preferences" ADD CONSTRAINT "communication_preferences_changed_by_fkey" FOREIGN KEY (changed_by) REFERENCES ramosolo.users(id);

ALTER TABLE ramosolo."communication_preferences" ADD CONSTRAINT "communication_preferences_patient_id_fkey" FOREIGN KEY (patient_id) REFERENCES ramosolo.patients(id);

ALTER TABLE ramosolo."communication_preferences" ADD CONSTRAINT "communication_preferences_institution_id_fkey" FOREIGN KEY (institution_id) REFERENCES ramosolo.institutions(id);

ALTER TABLE ramosolo."communication_preferences" ADD CONSTRAINT "communication_preferences_booking_request_id_fkey" FOREIGN KEY (booking_request_id) REFERENCES ramosolo.booking_requests(id);

ALTER TABLE ramosolo."attendance_followup_reviews" ADD CONSTRAINT "attendance_followup_reviews_actor_id_fkey" FOREIGN KEY (actor_id) REFERENCES ramosolo.users(id);

ALTER TABLE ramosolo."attendance_followup_reviews" ADD CONSTRAINT "attendance_followup_reviews_followup_id_fkey" FOREIGN KEY (followup_id) REFERENCES ramosolo.attendance_followups(id);

ALTER TABLE ramosolo."attendance_followup_reviews" ADD CONSTRAINT "attendance_followup_reviews_institution_id_fkey" FOREIGN KEY (institution_id) REFERENCES ramosolo.institutions(id);

ALTER TABLE ramosolo."appointment_attendance_events" ADD CONSTRAINT "appointment_attendance_events_actor_id_fkey" FOREIGN KEY (actor_id) REFERENCES ramosolo.users(id);

ALTER TABLE ramosolo."appointment_attendance_events" ADD CONSTRAINT "appointment_attendance_events_appointment_id_fkey" FOREIGN KEY (appointment_id) REFERENCES ramosolo.appointments(id);

ALTER TABLE ramosolo."appointment_attendance_events" ADD CONSTRAINT "appointment_attendance_events_institution_id_fkey" FOREIGN KEY (institution_id) REFERENCES ramosolo.institutions(id);

ALTER TABLE ramosolo."appointment_confirmation_requests" ADD CONSTRAINT "appointment_confirmation_requests_confirmed_by_fkey" FOREIGN KEY (confirmed_by) REFERENCES ramosolo.users(id);

ALTER TABLE ramosolo."appointment_confirmation_requests" ADD CONSTRAINT "appointment_confirmation_requests_requested_by_fkey" FOREIGN KEY (requested_by) REFERENCES ramosolo.users(id);

ALTER TABLE ramosolo."appointment_confirmation_requests" ADD CONSTRAINT "appointment_confirmation_requests_appointment_id_fkey" FOREIGN KEY (appointment_id) REFERENCES ramosolo.appointments(id);

ALTER TABLE ramosolo."appointment_confirmation_requests" ADD CONSTRAINT "appointment_confirmation_requests_institution_id_fkey" FOREIGN KEY (institution_id) REFERENCES ramosolo.institutions(id);

ALTER TABLE ramosolo."patients" ADD CONSTRAINT "patients_user_id_fkey" FOREIGN KEY (user_id) REFERENCES ramosolo.users(id);

ALTER TABLE ramosolo."patients" ADD CONSTRAINT "patients_doctor_id_fkey" FOREIGN KEY (doctor_id) REFERENCES ramosolo.users(id);

ALTER TABLE ramosolo."patients" ADD CONSTRAINT "patients_institution_id_fkey" FOREIGN KEY (institution_id) REFERENCES ramosolo.institutions(id);

CREATE OR REPLACE FUNCTION ramosolo.appointment_attendance_event()
 RETURNS trigger
 LANGUAGE plpgsql
 SET search_path TO 'ramosolo', 'pg_temp'
AS E'\r\nBEGIN\r\n IF TG_OP=\'INSERT\' THEN\r\n  INSERT INTO appointment_attendance_events(institution_id,appointment_id,appointment_version,kind,status,starts_at,recorded_at)\r\n   VALUES(NEW.institution_id,NEW.id,NEW.schedule_version,\'created\',NEW.status,NEW.starts_at,timezone(\'UTC\',clock_timestamp()));\r\n ELSIF ROW(NEW.status,NEW.starts_at,NEW.schedule_version) IS DISTINCT FROM ROW(OLD.status,OLD.starts_at,OLD.schedule_version) THEN\r\n  INSERT INTO appointment_attendance_events(institution_id,appointment_id,appointment_version,kind,previous_status,status,previous_start,starts_at,recorded_at)\r\n   VALUES(NEW.institution_id,NEW.id,NEW.schedule_version,\'changed\',OLD.status,NEW.status,OLD.starts_at,NEW.starts_at,timezone(\'UTC\',clock_timestamp()));\r\n END IF;\r\n RETURN NEW;\r\nEND ';

ALTER FUNCTION ramosolo."appointment_attendance_event"() OWNER TO postgres;

CREATE OR REPLACE FUNCTION ramosolo.booking_appointment_guard()
 RETURNS trigger
 LANGUAGE plpgsql
 SET search_path TO 'ramosolo', 'pg_temp'
AS E'\r\nDECLARE d integer; p integer; old_doctor integer; old_patient integer; pol availability_policies%ROWTYPE;\r\n now_utc timestamp; local_start timestamp; local_end timestamp; local_date date; session_window record;\r\n duration integer; matched boolean:=false; closed boolean; has_opening boolean; used integer;\r\nBEGIN\r\n IF current_setting(\'transaction_isolation\') <> \'read committed\' THEN RAISE EXCEPTION \'Booking writes require READ COMMITTED isolation\'; END IF;\r\n IF TG_OP IN (\'UPDATE\',\'DELETE\') THEN old_doctor:=OLD.doctor_id; old_patient:=OLD.patient_id; END IF;\r\n IF TG_OP=\'DELETE\' THEN d:=OLD.doctor_id; ELSE d:=NEW.doctor_id; END IF;\r\n FOR d IN SELECT DISTINCT v FROM unnest(ARRAY[d,old_doctor]) AS v WHERE v IS NOT NULL ORDER BY v LOOP\r\n  PERFORM pg_advisory_xact_lock(7001,d);\r\n END LOOP;\r\n IF TG_OP=\'DELETE\' THEN RETURN OLD; END IF;\r\n FOR p IN SELECT DISTINCT v FROM unnest(ARRAY[NEW.patient_id,old_patient]) AS v WHERE v IS NOT NULL ORDER BY v LOOP\r\n  PERFORM pg_advisory_xact_lock(7002,p);\r\n END LOOP;\r\n -- Identity and institution invariants also apply when releasing capacity.\r\n IF NEW.patient_id IS NOT NULL THEN\r\n  IF NOT EXISTS(SELECT 1 FROM patients WHERE id=NEW.patient_id AND institution_id=NEW.institution_id) THEN\r\n   RAISE EXCEPTION \'Patient belongs to a different institution\';\r\n  END IF;\r\n ELSE\r\n  IF NOT EXISTS(SELECT 1 FROM booking_requests WHERE id=NEW.booking_request_id AND institution_id=NEW.institution_id) THEN\r\n   RAISE EXCEPTION \'Guest request belongs to a different institution\';\r\n  END IF;\r\n END IF;\r\n IF TG_OP=\'UPDATE\' AND NEW.institution_id<>OLD.institution_id THEN RAISE EXCEPTION \'Appointment ownership cannot change\'; END IF;\r\n IF NEW.status NOT IN (\'scheduled\',\'held\') THEN RETURN NEW; END IF;\r\n IF TG_OP=\'UPDATE\' AND NEW.status=OLD.status AND\r\n  ROW(NEW.patient_id,NEW.booking_request_id,NEW.doctor_id,NEW.starts_at,NEW.ends_at,NEW.occupied_until,NEW.hold_expires_at,NEW.care_type,NEW.visit_kind)\r\n  IS NOT DISTINCT FROM ROW(OLD.patient_id,OLD.booking_request_id,OLD.doctor_id,OLD.starts_at,OLD.ends_at,OLD.occupied_until,OLD.hold_expires_at,OLD.care_type,OLD.visit_kind) THEN\r\n  RETURN NEW; -- Preserve unchanged legacy appointments without guessing a duration.\r\n END IF;\r\n now_utc:=timezone(\'UTC\',clock_timestamp());\r\n IF TG_OP=\'UPDATE\' AND OLD.status=\'held\' AND (OLD.hold_expires_at IS NULL OR OLD.hold_expires_at<=now_utc) THEN\r\n  RAISE EXCEPTION \'Temporary hold has expired\';\r\n END IF;\r\n SELECT * INTO pol FROM availability_policies WHERE institution_id=NEW.institution_id AND doctor_id=NEW.doctor_id;\r\n IF NOT FOUND OR NOT pol.enabled OR NOT pol.holidays_confirmed THEN RAISE EXCEPTION \'Availability is not configured\'; END IF;\r\n IF NOT EXISTS(SELECT 1 FROM memberships m JOIN users u ON u.id=m.user_id JOIN institutions i ON i.id=m.institution_id\r\n  WHERE m.user_id=NEW.doctor_id AND m.institution_id=NEW.institution_id AND m.role=\'dr\' AND m.enabled AND u.enabled AND i.kind=\'medical\') THEN\r\n  RAISE EXCEPTION \'Doctor is not enabled in this institution\';\r\n END IF;\r\n IF NEW.patient_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM patients WHERE id=NEW.patient_id AND doctor_id=NEW.doctor_id) THEN\r\n  RAISE EXCEPTION \'Patient is not assigned to this doctor\';\r\n END IF;\r\n IF NEW.care_type IS NULL OR NEW.care_type NOT IN (\'inpatient\',\'outpatient\') OR NEW.visit_kind IS NULL OR NEW.visit_kind NOT IN (\'routine\',\'first\',\'assessment\')\r\n  OR NEW.ends_at IS NULL OR NEW.occupied_until IS NULL THEN RAISE EXCEPTION \'Complete typed appointment interval is required\'; END IF;\r\n IF NEW.status=\'held\' AND (NEW.booking_request_id IS NULL OR NEW.hold_expires_at IS NULL\r\n  OR NEW.hold_expires_at<=now_utc OR NEW.hold_expires_at>now_utc+make_interval(mins=>pol.hold_minutes)) THEN\r\n  RAISE EXCEPTION \'Invalid temporary hold expiry\';\r\n END IF;\r\n local_start:=NEW.starts_at AT TIME ZONE \'UTC\' AT TIME ZONE \'Africa/Johannesburg\';\r\n local_end:=NEW.occupied_until AT TIME ZONE \'UTC\' AT TIME ZONE \'Africa/Johannesburg\';\r\n local_date:=local_start::date;\r\n IF NEW.starts_at<=now_utc OR local_date>(now_utc AT TIME ZONE \'UTC\' AT TIME ZONE \'Africa/Johannesburg\')::date+pol.horizon_days THEN\r\n  RAISE EXCEPTION \'Appointment is outside the future booking window\';\r\n END IF;\r\n closed:=extract(isodow FROM local_date)::integer IN (4,6,7)\r\n  OR EXISTS(SELECT 1 FROM public_holidays WHERE institution_id=NEW.institution_id AND day=local_date)\r\n  OR EXISTS(SELECT 1 FROM availability_exceptions WHERE policy_id=pol.id AND day=local_date AND kind IN (\'leave\',\'closure\'));\r\n has_opening:=EXISTS(SELECT 1 FROM availability_exceptions WHERE policy_id=pol.id AND day=local_date AND kind=\'opening\');\r\n FOR session_window IN\r\n  SELECT e.opens_at,e.closes_at,e.duration_minutes,e.first_minutes,e.assessment_minutes,e.break_minutes,e.care_type\r\n   FROM availability_exceptions e WHERE e.policy_id=pol.id AND e.day=local_date AND e.kind=\'opening\' AND (NOT closed OR e.override_closure)\r\n  UNION ALL\r\n  SELECT s.opens_at,s.closes_at,s.duration_minutes,s.first_minutes,s.assessment_minutes,s.break_minutes,s.care_type\r\n   FROM availability_sessions s WHERE s.policy_id=pol.id AND s.weekday=extract(isodow FROM local_date)::integer-1 AND NOT has_opening AND NOT closed\r\n LOOP\r\n  duration:=CASE NEW.visit_kind WHEN \'routine\' THEN session_window.duration_minutes WHEN \'first\' THEN session_window.first_minutes ELSE session_window.assessment_minutes END;\r\n  IF session_window.care_type=NEW.care_type AND local_start>=local_date+session_window.opens_at AND local_end<=local_date+session_window.closes_at\r\n   AND NEW.ends_at=NEW.starts_at+make_interval(mins=>duration)\r\n   AND NEW.occupied_until=NEW.ends_at+make_interval(mins=>session_window.break_minutes)\r\n   AND mod(extract(epoch FROM (local_start-(local_date+session_window.opens_at))),((duration+session_window.break_minutes)*60)::numeric)=0 THEN\r\n   matched:=true; EXIT;\r\n  END IF;\r\n END LOOP;\r\n IF NOT matched THEN RAISE EXCEPTION \'Appointment is outside configured sessions or breaks\'; END IF;\r\n IF EXISTS(SELECT 1 FROM calendar_blocks b WHERE b.doctor_id=NEW.doctor_id AND b.enabled AND b.starts_at<NEW.occupied_until AND NEW.starts_at<b.ends_at) THEN RAISE EXCEPTION \'Appointment overlaps blocked time\'; END IF;\r\n SELECT count(*) INTO used FROM appointments a WHERE a.id<>COALESCE(NEW.id,-1) AND a.doctor_id=NEW.doctor_id\r\n  AND a.institution_id=NEW.institution_id AND (a.starts_at AT TIME ZONE \'UTC\' AT TIME ZONE \'Africa/Johannesburg\')::date=local_date\r\n  AND (a.status=\'scheduled\' OR (a.status=\'held\' AND a.hold_expires_at>now_utc));\r\n IF used>=pol.daily_limit THEN RAISE EXCEPTION \'Daily appointment limit reached\'; END IF;\r\n IF EXISTS(SELECT 1 FROM appointments a WHERE a.id<>COALESCE(NEW.id,-1)\r\n  AND (a.doctor_id=NEW.doctor_id OR (NEW.patient_id IS NOT NULL AND a.patient_id=NEW.patient_id))\r\n  AND (a.status=\'scheduled\' OR (a.status=\'held\' AND a.hold_expires_at>now_utc))\r\n  AND ((a.occupied_until IS NULL AND (a.starts_at AT TIME ZONE \'UTC\' AT TIME ZONE \'Africa/Johannesburg\')::date=local_date)\r\n   OR (a.starts_at<NEW.occupied_until AND NEW.starts_at<a.occupied_until))) THEN RAISE EXCEPTION \'Appointment intervals overlap\'; END IF;\r\n RETURN NEW;\r\nEND ';

ALTER FUNCTION ramosolo."booking_appointment_guard"() OWNER TO postgres;

CREATE OR REPLACE FUNCTION ramosolo.booking_config_guard()
 RETURNS trigger
 LANGUAGE plpgsql
 SET search_path TO 'ramosolo', 'pg_temp'
AS E'\r\nDECLARE d integer; inst integer; policy integer; row_id integer;\r\nBEGIN\r\n IF current_setting(\'transaction_isolation\') <> \'read committed\' THEN\r\n  RAISE EXCEPTION \'Booking writes require READ COMMITTED isolation\';\r\n END IF;\r\n IF TG_TABLE_NAME=\'public_holidays\' THEN\r\n  IF TG_OP=\'DELETE\' THEN inst:=OLD.institution_id; ELSE inst:=NEW.institution_id; END IF;\r\n  IF TG_OP=\'UPDATE\' AND NEW.institution_id<>OLD.institution_id THEN RAISE EXCEPTION \'Holiday ownership cannot change\'; END IF;\r\n  FOR d IN SELECT doctor_id FROM availability_policies WHERE institution_id=inst ORDER BY doctor_id LOOP\r\n   PERFORM pg_advisory_xact_lock(7001,d);\r\n  END LOOP;\r\n  IF TG_OP=\'DELETE\' THEN RETURN OLD; ELSE RETURN NEW; END IF;\r\n ELSIF TG_TABLE_NAME=\'availability_policies\' THEN\r\n  IF TG_OP=\'DELETE\' THEN d:=OLD.doctor_id; inst:=OLD.institution_id;\r\n  ELSE d:=NEW.doctor_id; inst:=NEW.institution_id; END IF;\r\n  IF TG_OP=\'UPDATE\' AND (NEW.doctor_id<>OLD.doctor_id OR NEW.institution_id<>OLD.institution_id) THEN\r\n   RAISE EXCEPTION \'Policy ownership cannot change\';\r\n  END IF;\r\n ELSE\r\n  IF TG_OP=\'DELETE\' THEN policy:=OLD.policy_id; ELSE policy:=NEW.policy_id; END IF;\r\n  IF TG_OP=\'UPDATE\' AND NEW.policy_id<>OLD.policy_id THEN RAISE EXCEPTION \'Session ownership cannot change\'; END IF;\r\n  SELECT doctor_id,institution_id INTO d,inst FROM availability_policies WHERE id=policy;\r\n END IF;\r\n IF d IS NULL THEN RAISE EXCEPTION \'Unknown scheduling policy\'; END IF;\r\n PERFORM pg_advisory_xact_lock(7001,d);\r\n IF TG_OP=\'DELETE\' THEN RETURN OLD; END IF;\r\n IF NOT EXISTS (SELECT 1 FROM memberships m JOIN users u ON u.id=m.user_id JOIN institutions i ON i.id=m.institution_id\r\n  WHERE m.user_id=d AND m.institution_id=inst AND m.role=\'dr\' AND m.enabled AND u.enabled AND i.kind=\'medical\') THEN\r\n  RAISE EXCEPTION \'Doctor must have an enabled medical institution membership\';\r\n END IF;\r\n IF TG_TABLE_NAME IN (\'availability_sessions\',\'availability_exceptions\') THEN\r\n  IF extract(second FROM NEW.opens_at)<>0 OR extract(second FROM NEW.closes_at)<>0 THEN\r\n   RAISE EXCEPTION \'Session hours require whole minutes\';\r\n  END IF;\r\n END IF;\r\n IF TG_TABLE_NAME=\'availability_sessions\' THEN\r\n  IF EXISTS (SELECT 1 FROM availability_sessions s WHERE s.policy_id=NEW.policy_id\r\n   AND s.weekday=NEW.weekday AND s.id<>COALESCE(NEW.id,-1) AND s.opens_at<NEW.closes_at AND NEW.opens_at<s.closes_at) THEN\r\n   RAISE EXCEPTION \'Weekly sessions overlap\';\r\n  END IF;\r\n ELSIF TG_TABLE_NAME=\'availability_exceptions\' THEN\r\n  IF NOT EXISTS (SELECT 1 FROM memberships m JOIN users u ON u.id=m.user_id WHERE m.user_id=NEW.approved_by\r\n   AND m.institution_id=inst AND m.enabled AND u.enabled AND (m.role=\'admin\' OR (m.role=\'dr\' AND m.user_id=d))) THEN\r\n   RAISE EXCEPTION \'Exception requires authorized staff approval\';\r\n  END IF;\r\n  IF length(trim(NEW.reason))<3 OR NEW.approved_at IS NULL THEN RAISE EXCEPTION \'Approval reason is required\'; END IF;\r\n  IF NEW.kind=\'opening\' AND EXISTS (SELECT 1 FROM availability_exceptions e WHERE e.policy_id=NEW.policy_id\r\n   AND e.day=NEW.day AND e.kind=\'opening\' AND e.id<>COALESCE(NEW.id,-1)\r\n   AND e.opens_at<NEW.closes_at AND NEW.opens_at<e.closes_at) THEN\r\n   RAISE EXCEPTION \'Dated sessions overlap\';\r\n  END IF;\r\n END IF;\r\n RETURN NEW;\r\nEND ';

ALTER FUNCTION ramosolo."booking_config_guard"() OWNER TO postgres;

CREATE OR REPLACE FUNCTION ramosolo.booking_exception_audit()
 RETURNS trigger
 LANGUAGE plpgsql
 SET search_path TO 'ramosolo', 'pg_temp'
AS E'\r\nBEGIN\r\n INSERT INTO audit_events(institution_id,actor_id,action,resource_type,resource_id,created_at)\r\n SELECT institution_id,NEW.approved_by,\'approve_exception\',\'availability_exception\',NEW.id,timezone(\'UTC\',clock_timestamp())\r\n FROM availability_policies WHERE id=NEW.policy_id;\r\n RETURN NEW;\r\nEND ';

ALTER FUNCTION ramosolo."booking_exception_audit"() OWNER TO postgres;

CREATE OR REPLACE FUNCTION ramosolo.calendar_appointment_metadata()
 RETURNS trigger
 LANGUAGE plpgsql
 SET search_path TO 'ramosolo', 'pg_temp'
AS E'\r\nBEGIN\r\n IF NEW.calendar_uid !~ \'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$\' THEN RAISE EXCEPTION \'Invalid calendar reference\'; END IF;\r\n IF TG_OP=\'UPDATE\' THEN\r\n  IF NEW.calendar_uid<>OLD.calendar_uid OR ROW(NEW.institution_id,NEW.doctor_id,NEW.patient_id,NEW.booking_request_id)\r\n    IS DISTINCT FROM ROW(OLD.institution_id,OLD.doctor_id,OLD.patient_id,OLD.booking_request_id) THEN\r\n   RAISE EXCEPTION \'Appointment identity and calendar reference are immutable\';\r\n  END IF;\r\n  NEW.was_confirmed:=CASE WHEN OLD.was_confirmed IS TRUE OR OLD.status IN (\'scheduled\',\'completed\',\'no_show\')\r\n    OR NEW.status IN (\'scheduled\',\'completed\',\'no_show\') THEN true ELSE OLD.was_confirmed END;\r\n  NEW.schedule_version:=OLD.schedule_version+CASE WHEN ROW(NEW.starts_at,NEW.ends_at,NEW.occupied_until,NEW.status,NEW.care_type,NEW.visit_kind,NEW.hold_expires_at)\r\n    IS DISTINCT FROM ROW(OLD.starts_at,OLD.ends_at,OLD.occupied_until,OLD.status,OLD.care_type,OLD.visit_kind,OLD.hold_expires_at) THEN 1 ELSE 0 END;\r\n ELSE\r\n  NEW.was_confirmed:=NEW.status IN (\'scheduled\',\'completed\',\'no_show\');\r\n  NEW.schedule_version:=1;\r\n END IF;\r\n RETURN NEW;\r\nEND ';

ALTER FUNCTION ramosolo."calendar_appointment_metadata"() OWNER TO postgres;

CREATE OR REPLACE FUNCTION ramosolo.calendar_block_guard()
 RETURNS trigger
 LANGUAGE plpgsql
 SET search_path TO 'ramosolo', 'pg_temp'
AS E'\r\nDECLARE actor integer; now_utc timestamp;\r\nBEGIN\r\n IF current_setting(\'transaction_isolation\')<>\'read committed\' THEN RAISE EXCEPTION \'Calendar writes require READ COMMITTED isolation\'; END IF;\r\n IF TG_OP=\'DELETE\' THEN RAISE EXCEPTION \'Release calendar blocks instead of deleting their history\'; END IF;\r\n PERFORM pg_advisory_xact_lock(7001,NEW.doctor_id);\r\n actor:=NEW.created_by;\r\n IF TG_OP=\'UPDATE\' THEN\r\n  IF NOT OLD.enabled THEN RAISE EXCEPTION \'Released block history is immutable\'; END IF;\r\n  IF ROW(NEW.institution_id,NEW.doctor_id,NEW.starts_at,NEW.ends_at,NEW.reason,NEW.created_by,NEW.created_at)\r\n    IS DISTINCT FROM ROW(OLD.institution_id,OLD.doctor_id,OLD.starts_at,OLD.ends_at,OLD.reason,OLD.created_by,OLD.created_at)\r\n    OR (NOT OLD.enabled AND NEW.enabled) THEN RAISE EXCEPTION \'Calendar block history is immutable\'; END IF;\r\n  actor:=NEW.released_by;\r\n  IF NEW.enabled OR NEW.released_by IS NULL OR NEW.released_at IS NULL THEN RAISE EXCEPTION \'Release approval is required\'; END IF;\r\n END IF;\r\n IF NOT EXISTS(SELECT 1 FROM memberships m JOIN users u ON u.id=m.user_id JOIN institutions i ON i.id=m.institution_id\r\n  WHERE m.institution_id=NEW.institution_id AND m.user_id=actor AND m.enabled AND u.enabled AND i.kind=\'medical\'\r\n   AND (m.role=\'admin\' OR (m.role=\'dr\' AND m.user_id=NEW.doctor_id))) THEN RAISE EXCEPTION \'Calendar block requires authorized staff\'; END IF;\r\n IF TG_OP=\'UPDATE\' THEN RETURN NEW; END IF;\r\n IF NOT EXISTS(SELECT 1 FROM memberships m JOIN users u ON u.id=m.user_id WHERE m.institution_id=NEW.institution_id\r\n   AND m.user_id=NEW.doctor_id AND m.role=\'dr\' AND m.enabled AND u.enabled) THEN RAISE EXCEPTION \'Doctor is not enabled\'; END IF;\r\n now_utc:=timezone(\'UTC\',clock_timestamp());\r\n IF NEW.starts_at<=now_utc OR NEW.ends_at<=NEW.starts_at THEN RAISE EXCEPTION \'Choose a future calendar block\'; END IF;\r\n IF EXISTS(SELECT 1 FROM calendar_blocks b WHERE b.doctor_id=NEW.doctor_id AND b.enabled AND b.starts_at<NEW.ends_at AND NEW.starts_at<b.ends_at) THEN\r\n  RAISE EXCEPTION \'Calendar blocks overlap\'; END IF;\r\n IF EXISTS(SELECT 1 FROM appointments a WHERE a.doctor_id=NEW.doctor_id\r\n   AND (a.status=\'scheduled\' OR (a.status=\'held\' AND a.hold_expires_at>now_utc))\r\n   AND ((a.occupied_until IS NOT NULL AND a.starts_at<NEW.ends_at AND NEW.starts_at<a.occupied_until)\r\n    OR (a.occupied_until IS NULL AND\r\n     (((a.starts_at AT TIME ZONE \'UTC\' AT TIME ZONE \'Africa/Johannesburg\')::date::timestamp AT TIME ZONE \'Africa/Johannesburg\') AT TIME ZONE \'UTC\')<NEW.ends_at\r\n     AND NEW.starts_at<((((a.starts_at AT TIME ZONE \'UTC\' AT TIME ZONE \'Africa/Johannesburg\')::date+1)::timestamp AT TIME ZONE \'Africa/Johannesburg\') AT TIME ZONE \'UTC\')))) THEN\r\n  RAISE EXCEPTION \'Calendar block overlaps an active appointment\'; END IF;\r\n RETURN NEW;\r\nEND ';

ALTER FUNCTION ramosolo."calendar_block_guard"() OWNER TO postgres;

CREATE OR REPLACE FUNCTION ramosolo.financial_audit()
 RETURNS trigger
 LANGUAGE plpgsql
 SET search_path TO 'ramosolo', 'pg_temp'
AS E'\r\nDECLARE actor integer; action_name text; resource text;\r\nBEGIN\r\n IF TG_TABLE_NAME=\'medical_invoices\' THEN\r\n  actor:=CASE WHEN TG_OP=\'INSERT\' THEN NEW.created_by ELSE NEW.voided_by END;\r\n  action_name:=CASE WHEN TG_OP=\'INSERT\' THEN \'issue_invoice\' ELSE \'void_invoice\' END;resource:=\'invoice\';\r\n ELSE actor:=NEW.actor_id;action_name:=\'manual_\'||NEW.kind;resource:=\'payment_entry\';END IF;\r\n INSERT INTO audit_events(institution_id,actor_id,action,resource_type,resource_id,created_at)\r\n VALUES(NEW.institution_id,actor,action_name,resource,NEW.id,timezone(\'UTC\',clock_timestamp()));\r\n RETURN NEW;\r\nEND ';

ALTER FUNCTION ramosolo."financial_audit"() OWNER TO postgres;

CREATE OR REPLACE FUNCTION ramosolo.followup_actor_allowed(inst integer, doctor integer, actor integer, admin_only boolean DEFAULT false)
 RETURNS boolean
 LANGUAGE sql
 STABLE
 SET search_path TO 'ramosolo', 'pg_temp'
AS E'\r\n SELECT EXISTS(SELECT 1 FROM memberships m JOIN users u ON u.id=m.user_id JOIN institutions i ON i.id=m.institution_id\r\n WHERE m.institution_id=inst AND i.kind=\'medical\' AND m.user_id=actor AND m.enabled AND u.enabled\r\n AND (m.role=\'admin\' OR (NOT admin_only AND (m.role=\'dr\' AND m.user_id=doctor OR m.role=\'dr_assist\' AND m.supervising_doctor_id=doctor)\r\n AND EXISTS(SELECT 1 FROM memberships d JOIN users du ON du.id=d.user_id WHERE d.institution_id=inst AND d.user_id=doctor AND d.role=\'dr\' AND d.enabled AND du.enabled))))\r\n';

ALTER FUNCTION ramosolo."followup_actor_allowed"(integer, integer, integer, boolean) OWNER TO postgres;

CREATE OR REPLACE FUNCTION ramosolo.followup_guard()
 RETURNS trigger
 LANGUAGE plpgsql
 SET search_path TO 'ramosolo', 'pg_temp'
AS E'\r\nDECLARE ap appointments; alert attendance_followups; actor integer;\r\nBEGIN\r\n IF TG_OP=\'DELETE\' THEN RAISE EXCEPTION \'Administrative history cannot be deleted\'; END IF;\r\n IF TG_TABLE_NAME=\'followup_policies\' THEN\r\n  IF NOT followup_actor_allowed(NEW.institution_id,NULL,NEW.updated_by,true) THEN RAISE EXCEPTION \'Follow-up policy requires institution administrator\'; END IF;\r\n  IF TG_OP=\'UPDATE\' AND (NEW.institution_id<>OLD.institution_id OR NEW.version<>OLD.version+1) THEN RAISE EXCEPTION \'Policy updates require a new version\'; END IF;\r\n  RETURN NEW;\r\n END IF;\r\n IF TG_TABLE_NAME=\'attendance_followup_reviews\' THEN\r\n  IF TG_OP<>\'INSERT\' THEN RAISE EXCEPTION \'Review history is append-only\'; END IF;\r\n  SELECT * INTO alert FROM attendance_followups WHERE id=NEW.followup_id;\r\n  SELECT * INTO ap FROM appointments WHERE id=alert.appointment_id;\r\n  IF alert.institution_id IS DISTINCT FROM NEW.institution_id OR NOT followup_actor_allowed(NEW.institution_id,ap.doctor_id,NEW.actor_id)\r\n    OR alert.state<>NEW.action THEN RAISE EXCEPTION \'Review must match an authorized scoped alert action\'; END IF;\r\n  RETURN NEW;\r\n END IF;\r\n SELECT * INTO ap FROM appointments WHERE id=NEW.appointment_id;\r\n IF ap.id IS NULL OR ap.institution_id<>NEW.institution_id THEN RAISE EXCEPTION \'Administrative record institution mismatch\'; END IF;\r\n IF TG_TABLE_NAME=\'appointment_attendance_events\' THEN\r\n  IF TG_OP<>\'INSERT\' THEN RAISE EXCEPTION \'Attendance event history is append-only\'; END IF;\r\n  IF NEW.actor_id IS NOT NULL AND NOT followup_actor_allowed(NEW.institution_id,ap.doctor_id,NEW.actor_id) THEN RAISE EXCEPTION \'Unauthorized event actor\'; END IF;\r\n ELSIF TG_TABLE_NAME=\'appointment_confirmation_requests\' THEN\r\n  IF ap.schedule_version<>NEW.appointment_version OR ap.starts_at<>NEW.scheduled_start OR ap.status<>\'scheduled\'\r\n    OR ap.starts_at<=timezone(\'UTC\',clock_timestamp()) THEN RAISE EXCEPTION \'Confirmation requires current upcoming appointment\'; END IF;\r\n  actor=CASE WHEN TG_OP=\'INSERT\' THEN NEW.requested_by ELSE NEW.confirmed_by END;\r\n  IF NOT followup_actor_allowed(NEW.institution_id,ap.doctor_id,actor) THEN RAISE EXCEPTION \'Unauthorized confirmation actor\'; END IF;\r\n  IF TG_OP=\'UPDATE\' AND (ROW(NEW.institution_id,NEW.appointment_id,NEW.appointment_version,NEW.scheduled_start,NEW.deadline,NEW.requested_at,NEW.requested_by,NEW.policy_version)\r\n    IS DISTINCT FROM ROW(OLD.institution_id,OLD.appointment_id,OLD.appointment_version,OLD.scheduled_start,OLD.deadline,OLD.requested_at,OLD.requested_by,OLD.policy_version)\r\n    OR OLD.confirmed_at IS NOT NULL OR NEW.confirmed_at IS NULL) THEN RAISE EXCEPTION \'Confirmation requests are immutable except for first response\'; END IF;\r\n ELSIF TG_TABLE_NAME=\'attendance_followups\' THEN\r\n  IF TG_OP=\'INSERT\' AND (NEW.appointment_version<>ap.schedule_version OR NOT EXISTS(SELECT 1 FROM followup_policies p WHERE p.institution_id=NEW.institution_id AND p.version=NEW.policy_version AND p.enabled)) THEN RAISE EXCEPTION \'Follow-up generation mismatch\'; END IF;\r\n  IF TG_OP=\'UPDATE\' AND ROW(NEW.institution_id,NEW.appointment_id,NEW.appointment_version,NEW.rule,NEW.policy_version,NEW.rule_version,NEW.reason,NEW.suggested_action,NEW.evidence::text,NEW.created_at)\r\n    IS DISTINCT FROM ROW(OLD.institution_id,OLD.appointment_id,OLD.appointment_version,OLD.rule,OLD.policy_version,OLD.rule_version,OLD.reason,OLD.suggested_action,OLD.evidence::text,OLD.created_at) THEN RAISE EXCEPTION \'Follow-up evidence snapshots are immutable\'; END IF;\r\n END IF;\r\n RETURN NEW;\r\nEND ';

ALTER FUNCTION ramosolo."followup_guard"() OWNER TO postgres;

CREATE OR REPLACE FUNCTION ramosolo.invalidate_reminder_jobs(appointment integer, preference integer, policy integer, why text)
 RETURNS void
 LANGUAGE plpgsql
 SET search_path TO 'ramosolo', 'pg_temp'
AS E'\r\nBEGIN\r\n UPDATE notification_outbox j SET invalidated_at=timezone(\'UTC\',clock_timestamp()),\r\n  state=CASE WHEN state=\'pending\' THEN \'cancelled\' ELSE state END,\r\n  result_code=CASE WHEN state=\'pending\' THEN why ELSE result_code END\r\n WHERE j.invalidated_at IS NULL AND ((appointment IS NOT NULL AND j.appointment_id=appointment)\r\n  OR (preference IS NOT NULL AND j.preference_id=preference) OR (policy IS NOT NULL AND j.policy_id=policy));\r\nEND ';

ALTER FUNCTION ramosolo."invalidate_reminder_jobs"(integer, integer, integer, text) OWNER TO postgres;

CREATE OR REPLACE FUNCTION ramosolo.medical_assignment_guard()
 RETURNS trigger
 LANGUAGE plpgsql
 SET search_path TO 'ramosolo', 'pg_temp'
AS E'\nDECLARE inst integer; doctor integer;\nBEGIN\n IF TG_TABLE_NAME=\'memberships\' THEN\n  IF NEW.role=\'dr_assist\' AND NOT EXISTS (\n   SELECT 1 FROM memberships m JOIN users u ON u.id=m.user_id\n   WHERE m.user_id=NEW.supervising_doctor_id AND m.institution_id=NEW.institution_id\n    AND m.role=\'dr\' AND m.enabled AND u.enabled\n  ) THEN RAISE EXCEPTION \'Assistant requires an enabled doctor in the same institution\'; END IF;\n ELSIF TG_TABLE_NAME=\'patients\' THEN\n  IF NOT EXISTS (SELECT 1 FROM memberships m JOIN users u ON u.id=m.user_id\n   JOIN institutions i ON i.id=m.institution_id WHERE m.user_id=NEW.doctor_id\n    AND m.institution_id=NEW.institution_id AND m.role=\'dr\' AND m.enabled AND u.enabled AND i.kind=\'medical\')\n  THEN RAISE EXCEPTION \'Patient requires an enabled doctor in the same medical institution\'; END IF;\n  IF NEW.user_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM memberships m\n   WHERE m.user_id=NEW.user_id AND m.institution_id=NEW.institution_id AND m.role=\'patient\')\n  THEN RAISE EXCEPTION \'Patient account requires a patient membership in the same institution\'; END IF;\n ELSIF TG_TABLE_NAME=\'care_assignments\' THEN\n  SELECT institution_id INTO inst FROM patients WHERE id=NEW.patient_id;\n  IF NOT EXISTS (SELECT 1 FROM memberships m JOIN users u ON u.id=m.user_id\n   WHERE m.user_id=NEW.nurse_id AND m.institution_id=inst AND m.role=\'nurse\' AND m.enabled AND u.enabled)\n  THEN RAISE EXCEPTION \'Nurse requires membership in the patient institution\'; END IF;\n ELSIF TG_TABLE_NAME=\'appointments\' AND NEW.patient_id IS NOT NULL THEN\n  IF NOT EXISTS (SELECT 1 FROM patients p WHERE p.id=NEW.patient_id\n   AND p.institution_id=NEW.institution_id AND p.doctor_id=NEW.doctor_id)\n  THEN RAISE EXCEPTION \'Appointment requires the assigned patient doctor and institution\'; END IF;\n END IF;\n RETURN NEW;\nEND ';

ALTER FUNCTION ramosolo."medical_assignment_guard"() OWNER TO postgres;

CREATE OR REPLACE FUNCTION ramosolo.medical_invoice_guard()
 RETURNS trigger
 LANGUAGE plpgsql
 SET search_path TO 'ramosolo', 'pg_temp'
AS E'\r\nDECLARE appt appointments%ROWTYPE; net numeric; actor integer;\r\nBEGIN\r\n IF current_setting(\'transaction_isolation\')<>\'read committed\' THEN RAISE EXCEPTION \'Financial writes require READ COMMITTED isolation\'; END IF;\r\n IF TG_OP=\'DELETE\' THEN RAISE EXCEPTION \'Invoice history cannot be deleted\'; END IF;\r\n IF TG_OP=\'INSERT\' THEN\r\n  SELECT * INTO appt FROM appointments WHERE id=NEW.appointment_id FOR UPDATE;\r\n  IF NOT FOUND OR appt.institution_id<>NEW.institution_id OR appt.doctor_id<>NEW.doctor_id OR appt.was_confirmed IS NOT TRUE THEN\r\n   RAISE EXCEPTION \'Invoice needs a confirmed appointment with matching ownership\'; END IF;\r\n  IF NEW.state<>\'issued\' OR NEW.voided_by IS NOT NULL OR NEW.voided_at IS NOT NULL THEN RAISE EXCEPTION \'New invoices must be issued\'; END IF;\r\n  IF NEW.total::text=\'NaN\' OR NEW.total<=0 OR NEW.currency<>\'ZAR\' THEN RAISE EXCEPTION \'Invoice requires a positive ZAR total\'; END IF;\r\n  actor:=NEW.created_by;\r\n  NEW.created_at:=timezone(\'UTC\',clock_timestamp());\r\n ELSE\r\n  IF ROW(NEW.institution_id,NEW.doctor_id,NEW.appointment_id,NEW.total,NEW.currency,NEW.created_by,NEW.created_at)\r\n    IS DISTINCT FROM ROW(OLD.institution_id,OLD.doctor_id,OLD.appointment_id,OLD.total,OLD.currency,OLD.created_by,OLD.created_at)\r\n    OR OLD.state=\'void\' OR NEW.state<>\'void\' OR NEW.voided_by IS NULL OR NEW.voided_at IS NULL THEN RAISE EXCEPTION \'Invoice values and history are immutable\'; END IF;\r\n  SELECT coalesce(sum(CASE WHEN kind=\'receipt\' THEN amount ELSE -amount END),0) INTO net FROM medical_payment_entries WHERE invoice_id=OLD.id;\r\n  IF net<>0 THEN RAISE EXCEPTION \'Refund received funds before voiding\'; END IF;\r\n  actor:=NEW.voided_by;NEW.voided_at:=timezone(\'UTC\',clock_timestamp());\r\n END IF;\r\n IF NOT EXISTS(SELECT 1 FROM memberships m JOIN users u ON u.id=m.user_id JOIN institutions i ON i.id=m.institution_id\r\n  WHERE m.institution_id=NEW.institution_id AND m.user_id=actor AND m.enabled AND u.enabled AND i.kind=\'medical\'\r\n   AND (m.role=\'admin\' OR (TG_OP=\'INSERT\' AND m.role=\'dr\' AND m.user_id=NEW.doctor_id))) THEN RAISE EXCEPTION \'Invoice action requires authorized staff\'; END IF;\r\n RETURN NEW;\r\nEND ';

ALTER FUNCTION ramosolo."medical_invoice_guard"() OWNER TO postgres;

CREATE OR REPLACE FUNCTION ramosolo.medical_payment_guard()
 RETURNS trigger
 LANGUAGE plpgsql
 SET search_path TO 'ramosolo', 'pg_temp'
AS E'\r\nDECLARE inv medical_invoices%ROWTYPE; original medical_payment_entries%ROWTYPE; net numeric; refunded numeric;\r\nBEGIN\r\n IF TG_OP<>\'INSERT\' THEN RAISE EXCEPTION \'Payment entries are append-only; record a linked refund to correct them\'; END IF;\r\n IF current_setting(\'transaction_isolation\')<>\'read committed\' THEN RAISE EXCEPTION \'Financial writes require READ COMMITTED isolation\'; END IF;\r\n SELECT * INTO inv FROM medical_invoices WHERE id=NEW.invoice_id FOR UPDATE;\r\n IF NOT FOUND OR inv.institution_id<>NEW.institution_id OR inv.state<>\'issued\' THEN RAISE EXCEPTION \'Invoice ownership or state is invalid\'; END IF;\r\n IF NOT EXISTS(SELECT 1 FROM memberships m JOIN users u ON u.id=m.user_id WHERE m.institution_id=inv.institution_id\r\n  AND m.user_id=NEW.actor_id AND m.enabled AND u.enabled AND (m.role=\'admin\' OR (NEW.kind=\'receipt\' AND m.role=\'dr\' AND m.user_id=inv.doctor_id))) THEN\r\n  RAISE EXCEPTION \'Money movement requires authorized staff\'; END IF;\r\n IF NEW.amount::text=\'NaN\' OR NEW.amount<=0 OR NEW.effective_at>timezone(\'UTC\',clock_timestamp()) OR length(NEW.submission_key)<>64 OR length(NEW.submission_fingerprint)<>64 THEN\r\n  RAISE EXCEPTION \'Invalid money movement\'; END IF;\r\n SELECT coalesce(sum(CASE WHEN kind=\'receipt\' THEN amount ELSE -amount END),0) INTO net FROM medical_payment_entries WHERE invoice_id=inv.id;\r\n IF NEW.kind=\'receipt\' THEN\r\n  IF NEW.amount>inv.total-net THEN RAISE EXCEPTION \'Receipt exceeds outstanding balance\'; END IF;\r\n ELSE\r\n  SELECT * INTO original FROM medical_payment_entries WHERE id=NEW.original_receipt_id AND invoice_id=inv.id AND kind=\'receipt\';\r\n  IF NOT FOUND OR NEW.method<>original.method OR NEW.effective_at<original.effective_at THEN RAISE EXCEPTION \'Refund requires its original receipt\'; END IF;\r\n  SELECT coalesce(sum(amount),0) INTO refunded FROM medical_payment_entries WHERE original_receipt_id=original.id AND kind=\'refund\';\r\n  IF NEW.amount>original.amount-refunded OR NEW.amount>net THEN RAISE EXCEPTION \'Refund exceeds unrefunded receipts\'; END IF;\r\n END IF;\r\n NEW.recorded_at:=timezone(\'UTC\',clock_timestamp());\r\n RETURN NEW;\r\nEND ';

ALTER FUNCTION ramosolo."medical_payment_guard"() OWNER TO postgres;

CREATE OR REPLACE FUNCTION ramosolo.notification_outbox_guard()
 RETURNS trigger
 LANGUAGE plpgsql
 SET search_path TO 'ramosolo', 'pg_temp'
AS E'\r\nDECLARE doctor integer;\r\nBEGIN\r\n IF TG_OP=\'DELETE\' THEN RAISE EXCEPTION \'Reminder job history cannot be deleted\'; END IF;\r\n IF TG_OP=\'INSERT\' THEN\r\n  PERFORM pg_advisory_xact_lock(7010,NEW.institution_id);\r\n  SELECT doctor_id INTO doctor FROM appointments WHERE id=NEW.appointment_id AND institution_id=NEW.institution_id;\r\n  IF doctor IS NULL THEN RAISE EXCEPTION \'Unknown scoped appointment\'; END IF;\r\n  PERFORM pg_advisory_xact_lock(7001,doctor);\r\n  IF NOT reminder_job_current(NEW) OR NEW.state<>\'pending\' OR NEW.attempt_count<>0 OR NEW.sent_at IS NOT NULL OR NEW.invalidated_at IS NOT NULL THEN\r\n   RAISE EXCEPTION \'Reminder jobs require current appointment, policy and recipient consent\'; END IF;\r\n ELSE\r\n  IF ROW(NEW.public_id,NEW.institution_id,NEW.appointment_id,NEW.appointment_version,NEW.scheduled_start,NEW.preference_id,\r\n    NEW.preference_version,NEW.recipient_user_id,NEW.consent_at,NEW.policy_id,NEW.policy_version,NEW.lead_minutes,NEW.channel,NEW.due_at,NEW.max_attempts,NEW.created_at)\r\n   IS DISTINCT FROM ROW(OLD.public_id,OLD.institution_id,OLD.appointment_id,OLD.appointment_version,OLD.scheduled_start,OLD.preference_id,\r\n    OLD.preference_version,OLD.recipient_user_id,OLD.consent_at,OLD.policy_id,OLD.policy_version,OLD.lead_minutes,OLD.channel,OLD.due_at,OLD.max_attempts,OLD.created_at) THEN\r\n    RAISE EXCEPTION \'Reminder job snapshots are immutable\'; END IF;\r\n  IF OLD.state<>\'pending\' AND (NEW.state<>OLD.state OR NEW.attempt_count<>OLD.attempt_count OR NEW.sent_at IS DISTINCT FROM OLD.sent_at OR NEW.result_code IS DISTINCT FROM OLD.result_code) THEN\r\n   RAISE EXCEPTION \'Terminal delivery history is immutable\'; END IF;\r\n  IF NEW.attempt_count<OLD.attempt_count OR NEW.attempt_count>OLD.attempt_count+1 THEN RAISE EXCEPTION \'Invalid reminder attempt count\'; END IF;\r\n  IF OLD.state=\'pending\' AND NEW.state=\'sent\' THEN\r\n   IF NOT reminder_job_current(NEW) OR NEW.invalidated_at IS NOT NULL OR NEW.attempt_count<1 OR NEW.due_at>timezone(\'UTC\',clock_timestamp())\r\n    OR NOT EXISTS(SELECT 1 FROM in_app_notifications WHERE job_id=NEW.id AND institution_id=NEW.institution_id) THEN\r\n    RAISE EXCEPTION \'A sent state requires actual in-app publication with current consent\'; END IF;\r\n  END IF;\r\n END IF;\r\n RETURN NEW;\r\nEND ';

ALTER FUNCTION ramosolo."notification_outbox_guard"() OWNER TO postgres;

CREATE OR REPLACE FUNCTION ramosolo.reminder_configuration_guard()
 RETURNS trigger
 LANGUAGE plpgsql
 SET search_path TO 'ramosolo', 'pg_temp'
AS E'\r\nDECLARE inst integer; owner integer; pol reminder_policies%ROWTYPE; patient patients%ROWTYPE; guest booking_requests%ROWTYPE;\r\nBEGIN\r\n IF current_setting(\'transaction_isolation\')<>\'read committed\' THEN RAISE EXCEPTION \'Reminder writes require READ COMMITTED isolation\'; END IF;\r\n IF TG_TABLE_NAME=\'reminder_leads\' THEN\r\n  IF TG_OP=\'DELETE\' THEN SELECT * INTO pol FROM reminder_policies WHERE id=OLD.policy_id;\r\n  ELSE SELECT * INTO pol FROM reminder_policies WHERE id=NEW.policy_id; END IF;\r\n  inst:=pol.institution_id;\r\n ELSE\r\n  IF TG_OP=\'DELETE\' THEN RAISE EXCEPTION \'Disable reminder configuration instead of deleting its history\'; END IF;\r\n  inst:=NEW.institution_id;\r\n END IF;\r\n PERFORM pg_advisory_xact_lock(7010,inst);\r\n IF NOT EXISTS(SELECT 1 FROM institutions WHERE id=inst AND kind=\'medical\') THEN RAISE EXCEPTION \'Medical institution required\'; END IF;\r\n IF TG_TABLE_NAME=\'reminder_policies\' THEN\r\n  IF NOT EXISTS(SELECT 1 FROM memberships m JOIN users u ON u.id=m.user_id WHERE m.user_id=NEW.updated_by\r\n   AND m.institution_id=inst AND m.role=\'admin\' AND m.enabled AND u.enabled) THEN RAISE EXCEPTION \'Reminder configuration requires institution administrator\'; END IF;\r\n  IF TG_OP=\'UPDATE\' THEN\r\n   IF NEW.institution_id<>OLD.institution_id THEN RAISE EXCEPTION \'Reminder policy ownership is immutable\'; END IF;\r\n   NEW.version:=OLD.version+1;\r\n  ELSE NEW.version:=1;END IF;\r\n  NEW.updated_at:=timezone(\'UTC\',clock_timestamp());\r\n ELSIF TG_TABLE_NAME=\'reminder_leads\' THEN\r\n  IF TG_OP=\'UPDATE\' AND NEW.policy_id<>OLD.policy_id THEN RAISE EXCEPTION \'Reminder lead ownership is immutable\'; END IF;\r\n  -- Updating the policy serializes configuration and invalidates the old generation.\r\n  UPDATE reminder_policies SET version=version+1 WHERE id=pol.id;\r\n ELSE\r\n  IF TG_OP=\'UPDATE\' THEN\r\n   IF ROW(NEW.institution_id,NEW.patient_id,NEW.booking_request_id) IS DISTINCT FROM ROW(OLD.institution_id,OLD.patient_id,OLD.booking_request_id) THEN\r\n    RAISE EXCEPTION \'Communication preference ownership is immutable\'; END IF;\r\n   NEW.version:=OLD.version+1;\r\n  ELSE NEW.version:=1;END IF;\r\n  IF NEW.email_enabled OR NEW.sms_enabled THEN RAISE EXCEPTION \'External reminder delivery is disabled\'; END IF;\r\n  IF NEW.patient_id IS NOT NULL THEN\r\n   SELECT * INTO patient FROM patients WHERE id=NEW.patient_id AND institution_id=inst;\r\n   IF NOT FOUND OR patient.user_id IS NULL OR NEW.changed_by IS DISTINCT FROM patient.user_id OR NEW.guest_verified_digest IS NOT NULL\r\n    OR NOT EXISTS(SELECT 1 FROM memberships m JOIN users u ON u.id=m.user_id WHERE m.user_id=patient.user_id\r\n     AND m.institution_id=inst AND m.role=\'patient\' AND m.enabled AND u.enabled) THEN RAISE EXCEPTION \'Patient must set their own preferences\'; END IF;\r\n  ELSE\r\n   SELECT * INTO guest FROM booking_requests WHERE id=NEW.booking_request_id AND institution_id=inst;\r\n   IF NOT FOUND OR NEW.changed_by IS NOT NULL THEN RAISE EXCEPTION \'Invalid verified booking preference\'; END IF;\r\n   IF NEW.in_app_enabled AND (guest.token_expires_at<=timezone(\'UTC\',clock_timestamp()) OR NEW.guest_verified_digest IS DISTINCT FROM guest.token_digest\r\n    OR NOT EXISTS(SELECT 1 FROM appointments WHERE booking_request_id=guest.id AND institution_id=inst AND status=\'scheduled\'\r\n     AND starts_at>timezone(\'UTC\',clock_timestamp()))) THEN RAISE EXCEPTION \'Verified future booking required\'; END IF;\r\n  END IF;\r\n  IF NEW.in_app_enabled AND (NEW.in_app_consent_at IS NULL OR NEW.in_app_consent_at>timezone(\'UTC\',clock_timestamp())) THEN RAISE EXCEPTION \'Explicit reminder consent is required\'; END IF;\r\n  NEW.changed_at:=timezone(\'UTC\',clock_timestamp());\r\n END IF;\r\n IF TG_OP=\'DELETE\' THEN RETURN OLD; ELSE RETURN NEW; END IF;\r\nEND ';

ALTER FUNCTION ramosolo."reminder_configuration_guard"() OWNER TO postgres;

CREATE OR REPLACE FUNCTION ramosolo.reminder_delivery_guard()
 RETURNS trigger
 LANGUAGE plpgsql
 SET search_path TO 'ramosolo', 'pg_temp'
AS E'\r\nDECLARE job notification_outbox%ROWTYPE; pol reminder_policies%ROWTYPE;\r\nBEGIN\r\n IF TG_OP<>\'INSERT\' THEN RAISE EXCEPTION \'Delivery and attempt history is append-only\'; END IF;\r\n SELECT * INTO job FROM notification_outbox WHERE id=NEW.job_id AND institution_id=NEW.institution_id;\r\n IF NOT FOUND THEN RAISE EXCEPTION \'Invalid scoped reminder job\'; END IF;\r\n IF TG_TABLE_NAME=\'in_app_notifications\' THEN\r\n  SELECT * INTO pol FROM reminder_policies WHERE id=job.policy_id;\r\n  IF NOT reminder_job_current(job) OR job.state<>\'pending\' OR job.attempt_count<1 OR job.due_at>timezone(\'UTC\',clock_timestamp())\r\n   OR NEW.expires_at<=timezone(\'UTC\',clock_timestamp()) OR NEW.expires_at>job.scheduled_start\r\n   OR NEW.expires_at>timezone(\'UTC\',clock_timestamp())+make_interval(mins=>pol.link_minutes) THEN\r\n    RAISE EXCEPTION \'In-app publication is not currently eligible\'; END IF;\r\n ELSE\r\n  IF NEW.number<1 OR NEW.number<>job.attempt_count OR (NEW.outcome=\'sent\' AND job.state<>\'sent\')\r\n   OR (NEW.outcome=\'transient_failure\' AND job.state NOT IN (\'pending\',\'failed\'))\r\n   OR (NEW.outcome=\'permanent_failure\' AND job.state<>\'failed\') THEN RAISE EXCEPTION \'Attempt result does not match delivery state\'; END IF;\r\n END IF;\r\n RETURN NEW;\r\nEND ';

ALTER FUNCTION ramosolo."reminder_delivery_guard"() OWNER TO postgres;

CREATE OR REPLACE FUNCTION ramosolo.reminder_job_current(j ramosolo.notification_outbox)
 RETURNS boolean
 LANGUAGE plpgsql
 SET search_path TO 'ramosolo', 'pg_temp'
AS E'\r\nDECLARE appt appointments%ROWTYPE; pref communication_preferences%ROWTYPE; pol reminder_policies%ROWTYPE;\r\nBEGIN\r\n SELECT * INTO appt FROM appointments WHERE id=j.appointment_id AND institution_id=j.institution_id;\r\n IF NOT FOUND OR appt.status<>\'scheduled\' OR appt.starts_at<=timezone(\'UTC\',clock_timestamp()) OR appt.schedule_version<>j.appointment_version\r\n  OR appt.starts_at<>j.scheduled_start THEN RETURN false; END IF;\r\n SELECT * INTO pref FROM communication_preferences WHERE id=j.preference_id AND institution_id=j.institution_id;\r\n IF NOT FOUND OR NOT pref.in_app_enabled OR pref.in_app_consent_at IS NULL OR pref.version<>j.preference_version OR pref.in_app_consent_at<>j.consent_at\r\n  OR pref.patient_id IS DISTINCT FROM appt.patient_id OR pref.booking_request_id IS DISTINCT FROM appt.booking_request_id THEN RETURN false; END IF;\r\n IF pref.patient_id IS NOT NULL THEN\r\n  IF pref.changed_by IS DISTINCT FROM j.recipient_user_id OR NOT EXISTS(SELECT 1 FROM patients p JOIN users u ON u.id=p.user_id\r\n   JOIN memberships m ON m.user_id=u.id AND m.institution_id=p.institution_id WHERE p.id=pref.patient_id\r\n    AND p.institution_id=j.institution_id AND p.user_id=j.recipient_user_id AND m.role=\'patient\' AND m.enabled AND u.enabled) THEN RETURN false; END IF;\r\n ELSE\r\n  IF j.recipient_user_id IS NOT NULL OR NOT EXISTS(SELECT 1 FROM booking_requests WHERE id=pref.booking_request_id AND institution_id=j.institution_id\r\n   AND token_digest=pref.guest_verified_digest AND token_expires_at>timezone(\'UTC\',clock_timestamp())) THEN RETURN false; END IF;\r\n END IF;\r\n SELECT * INTO pol FROM reminder_policies WHERE id=j.policy_id AND institution_id=j.institution_id;\r\n IF NOT FOUND OR NOT pol.enabled OR pol.version<>j.policy_version OR pol.max_attempts<>j.max_attempts THEN RETURN false; END IF;\r\n RETURN EXISTS(SELECT 1 FROM reminder_leads WHERE policy_id=pol.id AND minutes=j.lead_minutes)\r\n  AND j.due_at=appt.starts_at-make_interval(mins=>j.lead_minutes) AND j.channel=\'in_app\';\r\nEND ';

ALTER FUNCTION ramosolo."reminder_job_current"(ramosolo.notification_outbox) OWNER TO postgres;

CREATE OR REPLACE FUNCTION ramosolo.reminder_source_invalidation()
 RETURNS trigger
 LANGUAGE plpgsql
 SET search_path TO 'ramosolo', 'pg_temp'
AS E'\r\nBEGIN\r\n IF TG_TABLE_NAME=\'appointments\' THEN\r\n  IF NEW.schedule_version<>OLD.schedule_version OR NEW.status<>OLD.status OR NEW.starts_at<>OLD.starts_at THEN\r\n   PERFORM invalidate_reminder_jobs(NEW.id,NULL,NULL,\'appointment_changed\'); END IF;\r\n ELSIF TG_TABLE_NAME=\'communication_preferences\' THEN\r\n  PERFORM invalidate_reminder_jobs(NULL,NEW.id,NULL,\'consent_changed\');\r\n ELSIF TG_TABLE_NAME=\'reminder_policies\' THEN\r\n  PERFORM invalidate_reminder_jobs(NULL,NULL,NEW.id,\'policy_changed\');\r\n ELSE\r\n  IF NEW.user_id IS DISTINCT FROM OLD.user_id OR NEW.institution_id<>OLD.institution_id THEN\r\n   UPDATE notification_outbox j SET invalidated_at=timezone(\'UTC\',clock_timestamp()),\r\n    state=CASE WHEN j.state=\'pending\' THEN \'cancelled\' ELSE j.state END,\r\n    result_code=CASE WHEN j.state=\'pending\' THEN \'recipient_changed\' ELSE j.result_code END\r\n   WHERE j.preference_id IN (SELECT id FROM communication_preferences WHERE patient_id=NEW.id) AND j.invalidated_at IS NULL;\r\n  END IF;\r\n END IF;\r\n RETURN NEW;\r\nEND ';

ALTER FUNCTION ramosolo."reminder_source_invalidation"() OWNER TO postgres;

ALTER TABLE ramosolo."admissions" OWNER TO postgres;

ALTER TABLE ramosolo."appointment_attendance_events" OWNER TO postgres;

ALTER TABLE ramosolo."appointment_confirmation_requests" OWNER TO postgres;

ALTER TABLE ramosolo."appointments" OWNER TO postgres;

ALTER TABLE ramosolo."attendance_followup_reviews" OWNER TO postgres;

ALTER TABLE ramosolo."attendance_followups" OWNER TO postgres;

ALTER TABLE ramosolo."audit_events" OWNER TO postgres;

ALTER TABLE ramosolo."availability_exceptions" OWNER TO postgres;

ALTER TABLE ramosolo."availability_policies" OWNER TO postgres;

ALTER TABLE ramosolo."availability_sessions" OWNER TO postgres;

ALTER TABLE ramosolo."booking_rate_limits" OWNER TO postgres;

ALTER TABLE ramosolo."booking_requests" OWNER TO postgres;

ALTER TABLE ramosolo."calendar_blocks" OWNER TO postgres;

ALTER TABLE ramosolo."care_assignments" OWNER TO postgres;

ALTER TABLE ramosolo."communication_preferences" OWNER TO postgres;

ALTER TABLE ramosolo."demo_datasets" OWNER TO postgres;

ALTER TABLE ramosolo."followup_policies" OWNER TO postgres;

ALTER TABLE ramosolo."in_app_notifications" OWNER TO postgres;

ALTER TABLE ramosolo."institutions" OWNER TO postgres;

ALTER TABLE ramosolo."medical_invoices" OWNER TO postgres;

ALTER TABLE ramosolo."medical_payment_entries" OWNER TO postgres;

ALTER TABLE ramosolo."memberships" OWNER TO postgres;

ALTER TABLE ramosolo."notification_attempts" OWNER TO postgres;

ALTER TABLE ramosolo."notification_outbox" OWNER TO postgres;

ALTER TABLE ramosolo."patients" OWNER TO postgres;

ALTER TABLE ramosolo."public_holidays" OWNER TO postgres;

ALTER TABLE ramosolo."reminder_leads" OWNER TO postgres;

ALTER TABLE ramosolo."reminder_policies" OWNER TO postgres;

ALTER TABLE ramosolo."schema_versions" OWNER TO postgres;

ALTER TABLE ramosolo."users" OWNER TO postgres;

ALTER SEQUENCE ramosolo."admissions_id_seq" OWNER TO postgres;

ALTER SEQUENCE ramosolo."admissions_id_seq" OWNED BY ramosolo."admissions".id;

ALTER SEQUENCE ramosolo."appointment_attendance_events_id_seq" OWNER TO postgres;

ALTER SEQUENCE ramosolo."appointment_attendance_events_id_seq" OWNED BY ramosolo."appointment_attendance_events".id;

ALTER SEQUENCE ramosolo."appointment_confirmation_requests_id_seq" OWNER TO postgres;

ALTER SEQUENCE ramosolo."appointment_confirmation_requests_id_seq" OWNED BY ramosolo."appointment_confirmation_requests".id;

ALTER SEQUENCE ramosolo."appointments_id_seq" OWNER TO postgres;

ALTER SEQUENCE ramosolo."appointments_id_seq" OWNED BY ramosolo."appointments".id;

ALTER SEQUENCE ramosolo."attendance_followup_reviews_id_seq" OWNER TO postgres;

ALTER SEQUENCE ramosolo."attendance_followup_reviews_id_seq" OWNED BY ramosolo."attendance_followup_reviews".id;

ALTER SEQUENCE ramosolo."attendance_followups_id_seq" OWNER TO postgres;

ALTER SEQUENCE ramosolo."attendance_followups_id_seq" OWNED BY ramosolo."attendance_followups".id;

ALTER SEQUENCE ramosolo."audit_events_id_seq" OWNER TO postgres;

ALTER SEQUENCE ramosolo."audit_events_id_seq" OWNED BY ramosolo."audit_events".id;

ALTER SEQUENCE ramosolo."availability_exceptions_id_seq" OWNER TO postgres;

ALTER SEQUENCE ramosolo."availability_exceptions_id_seq" OWNED BY ramosolo."availability_exceptions".id;

ALTER SEQUENCE ramosolo."availability_policies_id_seq" OWNER TO postgres;

ALTER SEQUENCE ramosolo."availability_policies_id_seq" OWNED BY ramosolo."availability_policies".id;

ALTER SEQUENCE ramosolo."availability_sessions_id_seq" OWNER TO postgres;

ALTER SEQUENCE ramosolo."availability_sessions_id_seq" OWNED BY ramosolo."availability_sessions".id;

ALTER SEQUENCE ramosolo."booking_rate_limits_id_seq" OWNER TO postgres;

ALTER SEQUENCE ramosolo."booking_rate_limits_id_seq" OWNED BY ramosolo."booking_rate_limits".id;

ALTER SEQUENCE ramosolo."booking_requests_id_seq" OWNER TO postgres;

ALTER SEQUENCE ramosolo."booking_requests_id_seq" OWNED BY ramosolo."booking_requests".id;

ALTER SEQUENCE ramosolo."calendar_blocks_id_seq" OWNER TO postgres;

ALTER SEQUENCE ramosolo."calendar_blocks_id_seq" OWNED BY ramosolo."calendar_blocks".id;

ALTER SEQUENCE ramosolo."care_assignments_id_seq" OWNER TO postgres;

ALTER SEQUENCE ramosolo."care_assignments_id_seq" OWNED BY ramosolo."care_assignments".id;

ALTER SEQUENCE ramosolo."communication_preferences_id_seq" OWNER TO postgres;

ALTER SEQUENCE ramosolo."communication_preferences_id_seq" OWNED BY ramosolo."communication_preferences".id;

ALTER SEQUENCE ramosolo."demo_datasets_id_seq" OWNER TO postgres;

ALTER SEQUENCE ramosolo."demo_datasets_id_seq" OWNED BY ramosolo."demo_datasets".id;

ALTER SEQUENCE ramosolo."followup_policies_id_seq" OWNER TO postgres;

ALTER SEQUENCE ramosolo."followup_policies_id_seq" OWNED BY ramosolo."followup_policies".id;

ALTER SEQUENCE ramosolo."in_app_notifications_id_seq" OWNER TO postgres;

ALTER SEQUENCE ramosolo."in_app_notifications_id_seq" OWNED BY ramosolo."in_app_notifications".id;

ALTER SEQUENCE ramosolo."institutions_id_seq" OWNER TO postgres;

ALTER SEQUENCE ramosolo."institutions_id_seq" OWNED BY ramosolo."institutions".id;

ALTER SEQUENCE ramosolo."medical_invoices_id_seq" OWNER TO postgres;

ALTER SEQUENCE ramosolo."medical_invoices_id_seq" OWNED BY ramosolo."medical_invoices".id;

ALTER SEQUENCE ramosolo."medical_payment_entries_id_seq" OWNER TO postgres;

ALTER SEQUENCE ramosolo."medical_payment_entries_id_seq" OWNED BY ramosolo."medical_payment_entries".id;

ALTER SEQUENCE ramosolo."memberships_id_seq" OWNER TO postgres;

ALTER SEQUENCE ramosolo."memberships_id_seq" OWNED BY ramosolo."memberships".id;

ALTER SEQUENCE ramosolo."notification_attempts_id_seq" OWNER TO postgres;

ALTER SEQUENCE ramosolo."notification_attempts_id_seq" OWNED BY ramosolo."notification_attempts".id;

ALTER SEQUENCE ramosolo."notification_outbox_id_seq" OWNER TO postgres;

ALTER SEQUENCE ramosolo."notification_outbox_id_seq" OWNED BY ramosolo."notification_outbox".id;

ALTER SEQUENCE ramosolo."patients_id_seq" OWNER TO postgres;

ALTER SEQUENCE ramosolo."patients_id_seq" OWNED BY ramosolo."patients".id;

ALTER SEQUENCE ramosolo."public_holidays_id_seq" OWNER TO postgres;

ALTER SEQUENCE ramosolo."public_holidays_id_seq" OWNED BY ramosolo."public_holidays".id;

ALTER SEQUENCE ramosolo."reminder_leads_id_seq" OWNER TO postgres;

ALTER SEQUENCE ramosolo."reminder_leads_id_seq" OWNED BY ramosolo."reminder_leads".id;

ALTER SEQUENCE ramosolo."reminder_policies_id_seq" OWNER TO postgres;

ALTER SEQUENCE ramosolo."reminder_policies_id_seq" OWNED BY ramosolo."reminder_policies".id;

ALTER SEQUENCE ramosolo."users_id_seq" OWNER TO postgres;

ALTER SEQUENCE ramosolo."users_id_seq" OWNED BY ramosolo."users".id;

REVOKE ALL ON FUNCTION ramosolo."appointment_attendance_event"() FROM PUBLIC, anon, authenticated;

REVOKE ALL ON FUNCTION ramosolo."booking_appointment_guard"() FROM PUBLIC, anon, authenticated;

REVOKE ALL ON FUNCTION ramosolo."booking_config_guard"() FROM PUBLIC, anon, authenticated;

REVOKE ALL ON FUNCTION ramosolo."booking_exception_audit"() FROM PUBLIC, anon, authenticated;

REVOKE ALL ON FUNCTION ramosolo."calendar_appointment_metadata"() FROM PUBLIC, anon, authenticated;

REVOKE ALL ON FUNCTION ramosolo."calendar_block_guard"() FROM PUBLIC, anon, authenticated;

REVOKE ALL ON FUNCTION ramosolo."financial_audit"() FROM PUBLIC, anon, authenticated;

REVOKE ALL ON FUNCTION ramosolo."followup_actor_allowed"(integer, integer, integer, boolean) FROM PUBLIC, anon, authenticated;

REVOKE ALL ON FUNCTION ramosolo."followup_guard"() FROM PUBLIC, anon, authenticated;

REVOKE ALL ON FUNCTION ramosolo."invalidate_reminder_jobs"(integer, integer, integer, text) FROM PUBLIC, anon, authenticated;

REVOKE ALL ON FUNCTION ramosolo."medical_assignment_guard"() FROM PUBLIC, anon, authenticated;

REVOKE ALL ON FUNCTION ramosolo."medical_invoice_guard"() FROM PUBLIC, anon, authenticated;

REVOKE ALL ON FUNCTION ramosolo."medical_payment_guard"() FROM PUBLIC, anon, authenticated;

REVOKE ALL ON FUNCTION ramosolo."notification_outbox_guard"() FROM PUBLIC, anon, authenticated;

REVOKE ALL ON FUNCTION ramosolo."reminder_configuration_guard"() FROM PUBLIC, anon, authenticated;

REVOKE ALL ON FUNCTION ramosolo."reminder_delivery_guard"() FROM PUBLIC, anon, authenticated;

REVOKE ALL ON FUNCTION ramosolo."reminder_job_current"(ramosolo.notification_outbox) FROM PUBLIC, anon, authenticated;

REVOKE ALL ON FUNCTION ramosolo."reminder_source_invalidation"() FROM PUBLIC, anon, authenticated;

REVOKE ALL ON ALL TABLES IN SCHEMA ramosolo FROM PUBLIC, anon, authenticated;

REVOKE ALL ON ALL SEQUENCES IN SCHEMA ramosolo FROM PUBLIC, anon, authenticated;

REVOKE ALL ON ALL FUNCTIONS IN SCHEMA ramosolo FROM PUBLIC, anon, authenticated;

-- Synthetic preserved sentinels, inserted before trigger installation so fixture setup itself does not simulate application writes.

INSERT INTO ramosolo.schema_versions(version) VALUES (1),(2),(3),(4),(5),(6);

INSERT INTO ramosolo.institutions(id,name,kind) VALUES (1,'Synthetic fixture practice A','medical'),(2,'Synthetic fixture practice B','medical');

INSERT INTO ramosolo.users(id,name,email,password_hash,enabled,session_version,failed_logins) VALUES (1,'Synthetic fixture doctor A','fixture-doctor-a@example.test','disabled-synthetic-login',true,1,0),(2,'Synthetic fixture doctor B','fixture-doctor-b@example.test','disabled-synthetic-login',true,1,0),(3,'Synthetic fixture assistant','fixture-assistant@example.test','disabled-synthetic-login',true,1,0),(4,'Synthetic fixture patient','fixture-patient@example.test','disabled-synthetic-login',true,1,0);

INSERT INTO ramosolo.memberships(id,user_id,institution_id,role,enabled,supervising_doctor_id) VALUES (1,1,1,'dr',true,NULL),(2,2,1,'dr',true,NULL),(3,3,1,'dr_assist',true,1),(4,4,1,'patient',true,NULL),(5,2,2,'dr',true,NULL);

INSERT INTO ramosolo.patients(id,institution_id,user_id,doctor_id,name,email,phone) VALUES (1,1,4,1,'Synthetic fixture patient A','fixture-patient@example.test','0000000000'),(2,1,NULL,2,'Synthetic fixture patient B',NULL,NULL),(3,2,NULL,2,'Synthetic fixture patient C',NULL,NULL);

INSERT INTO ramosolo.appointments(id,patient_id,doctor_id,starts_at,ends_at,occupied_until,status,service,institution_id,care_type,visit_kind,schedule_version) VALUES (1,1,1,timestamp '2030-01-02 08:00',timestamp '2030-01-02 08:30',timestamp '2030-01-02 08:35','scheduled','Synthetic fixture service',1,'outpatient','followup',1);

SELECT setval('ramosolo.institutions_id_seq',2,true), setval('ramosolo.users_id_seq',4,true), setval('ramosolo.memberships_id_seq',5,true), setval('ramosolo.patients_id_seq',3,true), setval('ramosolo.appointments_id_seq',1,true);

CREATE TRIGGER attendance_event_guard BEFORE INSERT OR DELETE OR UPDATE ON ramosolo.appointment_attendance_events FOR EACH ROW EXECUTE FUNCTION ramosolo.followup_guard();

CREATE TRIGGER confirmation_request_guard BEFORE INSERT OR DELETE OR UPDATE ON ramosolo.appointment_confirmation_requests FOR EACH ROW EXECUTE FUNCTION ramosolo.followup_guard();

CREATE TRIGGER appointment_assignment_scope BEFORE INSERT OR UPDATE ON ramosolo.appointments FOR EACH ROW EXECUTE FUNCTION ramosolo.medical_assignment_guard();

CREATE TRIGGER appointment_attendance_history AFTER INSERT OR UPDATE ON ramosolo.appointments FOR EACH ROW EXECUTE FUNCTION ramosolo.appointment_attendance_event();

CREATE TRIGGER appointment_capacity_guard BEFORE INSERT OR DELETE OR UPDATE ON ramosolo.appointments FOR EACH ROW EXECUTE FUNCTION ramosolo.booking_appointment_guard();

CREATE TRIGGER appointment_metadata_guard BEFORE INSERT OR UPDATE ON ramosolo.appointments FOR EACH ROW EXECUTE FUNCTION ramosolo.calendar_appointment_metadata();

CREATE TRIGGER appointment_reminder_invalidation AFTER UPDATE ON ramosolo.appointments FOR EACH ROW EXECUTE FUNCTION ramosolo.reminder_source_invalidation();

CREATE TRIGGER followup_review_guard BEFORE INSERT OR DELETE OR UPDATE ON ramosolo.attendance_followup_reviews FOR EACH ROW EXECUTE FUNCTION ramosolo.followup_guard();

CREATE TRIGGER attendance_followup_guard BEFORE INSERT OR DELETE OR UPDATE ON ramosolo.attendance_followups FOR EACH ROW EXECUTE FUNCTION ramosolo.followup_guard();

CREATE TRIGGER exception_audit AFTER INSERT OR UPDATE ON ramosolo.availability_exceptions FOR EACH ROW EXECUTE FUNCTION ramosolo.booking_exception_audit();

CREATE TRIGGER exception_guard BEFORE INSERT OR DELETE OR UPDATE ON ramosolo.availability_exceptions FOR EACH ROW EXECUTE FUNCTION ramosolo.booking_config_guard();

CREATE TRIGGER policy_guard BEFORE INSERT OR DELETE OR UPDATE ON ramosolo.availability_policies FOR EACH ROW EXECUTE FUNCTION ramosolo.booking_config_guard();

CREATE TRIGGER session_guard BEFORE INSERT OR DELETE OR UPDATE ON ramosolo.availability_sessions FOR EACH ROW EXECUTE FUNCTION ramosolo.booking_config_guard();

CREATE TRIGGER calendar_block_protection BEFORE INSERT OR DELETE OR UPDATE ON ramosolo.calendar_blocks FOR EACH ROW EXECUTE FUNCTION ramosolo.calendar_block_guard();

CREATE TRIGGER nursing_assignment_scope BEFORE INSERT OR UPDATE ON ramosolo.care_assignments FOR EACH ROW EXECUTE FUNCTION ramosolo.medical_assignment_guard();

CREATE TRIGGER communication_preference_guard BEFORE INSERT OR DELETE OR UPDATE ON ramosolo.communication_preferences FOR EACH ROW EXECUTE FUNCTION ramosolo.reminder_configuration_guard();

CREATE TRIGGER preference_reminder_invalidation AFTER UPDATE ON ramosolo.communication_preferences FOR EACH ROW EXECUTE FUNCTION ramosolo.reminder_source_invalidation();

CREATE TRIGGER followup_policy_guard BEFORE INSERT OR DELETE OR UPDATE ON ramosolo.followup_policies FOR EACH ROW EXECUTE FUNCTION ramosolo.followup_guard();

CREATE TRIGGER in_app_notification_protection BEFORE INSERT OR DELETE OR UPDATE ON ramosolo.in_app_notifications FOR EACH ROW EXECUTE FUNCTION ramosolo.reminder_delivery_guard();

CREATE TRIGGER invoice_audit AFTER INSERT OR UPDATE ON ramosolo.medical_invoices FOR EACH ROW EXECUTE FUNCTION ramosolo.financial_audit();

CREATE TRIGGER invoice_protection BEFORE INSERT OR DELETE OR UPDATE ON ramosolo.medical_invoices FOR EACH ROW EXECUTE FUNCTION ramosolo.medical_invoice_guard();

CREATE TRIGGER payment_audit AFTER INSERT ON ramosolo.medical_payment_entries FOR EACH ROW EXECUTE FUNCTION ramosolo.financial_audit();

CREATE TRIGGER payment_protection BEFORE INSERT OR DELETE OR UPDATE ON ramosolo.medical_payment_entries FOR EACH ROW EXECUTE FUNCTION ramosolo.medical_payment_guard();

CREATE TRIGGER membership_assignment_scope BEFORE INSERT OR UPDATE ON ramosolo.memberships FOR EACH ROW EXECUTE FUNCTION ramosolo.medical_assignment_guard();

CREATE TRIGGER notification_attempt_protection BEFORE INSERT OR DELETE OR UPDATE ON ramosolo.notification_attempts FOR EACH ROW EXECUTE FUNCTION ramosolo.reminder_delivery_guard();

CREATE TRIGGER notification_outbox_protection BEFORE INSERT OR DELETE OR UPDATE ON ramosolo.notification_outbox FOR EACH ROW EXECUTE FUNCTION ramosolo.notification_outbox_guard();

CREATE TRIGGER patient_assignment_scope BEFORE INSERT OR UPDATE ON ramosolo.patients FOR EACH ROW EXECUTE FUNCTION ramosolo.medical_assignment_guard();

CREATE TRIGGER patient_reminder_invalidation AFTER UPDATE ON ramosolo.patients FOR EACH ROW EXECUTE FUNCTION ramosolo.reminder_source_invalidation();

CREATE TRIGGER holiday_guard BEFORE INSERT OR DELETE OR UPDATE ON ramosolo.public_holidays FOR EACH ROW EXECUTE FUNCTION ramosolo.booking_config_guard();

CREATE TRIGGER reminder_lead_guard BEFORE INSERT OR DELETE OR UPDATE ON ramosolo.reminder_leads FOR EACH ROW EXECUTE FUNCTION ramosolo.reminder_configuration_guard();

CREATE TRIGGER policy_reminder_invalidation AFTER UPDATE ON ramosolo.reminder_policies FOR EACH ROW EXECUTE FUNCTION ramosolo.reminder_source_invalidation();

CREATE TRIGGER reminder_policy_guard BEFORE INSERT OR DELETE OR UPDATE ON ramosolo.reminder_policies FOR EACH ROW EXECUTE FUNCTION ramosolo.reminder_configuration_guard();
