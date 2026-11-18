-- LOCAL REVIEW DRAFT generated from migrations 007-009 and the reviewed metadata snapshot.
-- Not applied to production. Preserves existing scheduling, assignment, audit, and reminder safeguards.
-- Constraint fingerprint: UTF-8 byte-length-prefixed fields and records, ordered by serialized bytes.
-- PG17 accepts the exact production snapshot fingerprint or the reviewed PG17.11 fixture serialization profile.
BEGIN;
SET LOCAL search_path TO ramosolo, public;
SET LOCAL lock_timeout='5s';
SET LOCAL statement_timeout='5min';
SELECT pg_advisory_xact_lock(hashtext('ramosolo_live_reconciliation'));
DO $preflight$ DECLARE versions integer[]; original_search_path text; constraint_fingerprint text; BEGIN
 IF current_setting('server_version_num')::integer / 10000 NOT IN (17,18) THEN RAISE EXCEPTION 'Unsupported PostgreSQL major version for reviewed catalog snapshot'; END IF;
 original_search_path := current_setting('search_path');
 PERFORM set_config('search_path','public',true);
 SELECT array_agg(version ORDER BY version) INTO versions FROM ramosolo.schema_versions;
 IF versions IS DISTINCT FROM ARRAY[1,2,3,4,5,6] THEN RAISE EXCEPTION 'Expected ramosolo ledger 1-6; stop and reconcile the ledger'; END IF;
 IF (SELECT array_agg(c.relname::text ORDER BY c.relname COLLATE "C") FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='ramosolo' AND c.relkind='r') IS DISTINCT FROM ARRAY['admissions','appointment_attendance_events','appointment_confirmation_requests','appointments','attendance_followup_reviews','attendance_followups','audit_events','availability_exceptions','availability_policies','availability_sessions','booking_rate_limits','booking_requests','calendar_blocks','care_assignments','communication_preferences','demo_datasets','followup_policies','in_app_notifications','institutions','medical_invoices','medical_payment_entries','memberships','notification_attempts','notification_outbox','patients','public_holidays','reminder_leads','reminder_policies','schema_versions','users']::text[] THEN RAISE EXCEPTION 'Unexpected existing table inventory'; END IF;
 IF (SELECT array_agg(c.relname::text ORDER BY c.relname COLLATE "C") FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='ramosolo' AND c.relkind='S') IS DISTINCT FROM ARRAY['admissions_id_seq','appointment_attendance_events_id_seq','appointment_confirmation_requests_id_seq','appointments_id_seq','attendance_followup_reviews_id_seq','attendance_followups_id_seq','audit_events_id_seq','availability_exceptions_id_seq','availability_policies_id_seq','availability_sessions_id_seq','booking_rate_limits_id_seq','booking_requests_id_seq','calendar_blocks_id_seq','care_assignments_id_seq','communication_preferences_id_seq','demo_datasets_id_seq','followup_policies_id_seq','in_app_notifications_id_seq','institutions_id_seq','medical_invoices_id_seq','medical_payment_entries_id_seq','memberships_id_seq','notification_attempts_id_seq','notification_outbox_id_seq','patients_id_seq','public_holidays_id_seq','reminder_leads_id_seq','reminder_policies_id_seq','users_id_seq']::text[] THEN RAISE EXCEPTION 'Unexpected existing sequence inventory'; END IF;
 IF (SELECT array_agg(p.proname::text ORDER BY p.proname COLLATE "C") FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='ramosolo') IS DISTINCT FROM ARRAY['appointment_attendance_event','booking_appointment_guard','booking_config_guard','booking_exception_audit','calendar_appointment_metadata','calendar_block_guard','financial_audit','followup_actor_allowed','followup_guard','invalidate_reminder_jobs','medical_assignment_guard','medical_invoice_guard','medical_payment_guard','notification_outbox_guard','reminder_configuration_guard','reminder_delivery_guard','reminder_job_current','reminder_source_invalidation']::text[] THEN RAISE EXCEPTION 'Unexpected existing routine inventory'; END IF;
 IF (SELECT count(*) FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='ramosolo' AND NOT t.tgisinternal) <> 32 THEN RAISE EXCEPTION 'Unexpected existing trigger inventory'; END IF;
 IF (SELECT count(*) FROM information_schema.columns WHERE table_schema='ramosolo') <> 283 THEN RAISE EXCEPTION 'Unexpected existing column inventory'; END IF;
 IF (SELECT md5(coalesce(string_agg(concat_ws('|',t.relname,a.attnum::text,a.attname,format_type(a.atttypid,a.atttypmod),coalesce(pg_get_expr(d.adbin,d.adrelid),''),coalesce(a.attidentity::text,''),coalesce(a.attgenerated::text,''),a.attnotnull::text), E'\n' ORDER BY t.relname,a.attnum),'')) FROM pg_attribute a JOIN pg_class t ON t.oid=a.attrelid JOIN pg_namespace n ON n.oid=t.relnamespace LEFT JOIN pg_attrdef d ON d.adrelid=a.attrelid AND d.adnum=a.attnum WHERE n.nspname='ramosolo' AND t.relkind IN ('r','p') AND a.attnum>0 AND NOT a.attisdropped) IS DISTINCT FROM 'ba6cbdc54b6f7d5556337e7e84ce57f4' THEN RAISE EXCEPTION 'Existing column definition drift'; END IF;
 IF (SELECT count(*) FROM pg_constraint c JOIN pg_class t ON t.oid=c.conrelid JOIN pg_namespace n ON n.oid=t.relnamespace WHERE n.nspname='ramosolo' AND c.contype <> 'n') <> 165 THEN RAISE EXCEPTION 'Unexpected existing constraint inventory'; END IF;
 IF (SELECT array_agg(signature ORDER BY signature COLLATE "C") FROM (SELECT concat(CASE WHEN (t.relname)::text IS NULL THEN 'N;' ELSE 'V'||octet_length(convert_to((t.relname)::text,'UTF8'))::text||':'||(t.relname)::text END,CASE WHEN (c.conname)::text IS NULL THEN 'N;' ELSE 'V'||octet_length(convert_to((c.conname)::text,'UTF8'))::text||':'||(c.conname)::text END,CASE WHEN (c.contype::text)::text IS NULL THEN 'N;' ELSE 'V'||octet_length(convert_to((c.contype::text)::text,'UTF8'))::text||':'||(c.contype::text)::text END,CASE WHEN (c.condeferrable::text)::text IS NULL THEN 'N;' ELSE 'V'||octet_length(convert_to((c.condeferrable::text)::text,'UTF8'))::text||':'||(c.condeferrable::text)::text END,CASE WHEN (c.condeferred::text)::text IS NULL THEN 'N;' ELSE 'V'||octet_length(convert_to((c.condeferred::text)::text,'UTF8'))::text||':'||(c.condeferred::text)::text END,CASE WHEN (c.convalidated::text)::text IS NULL THEN 'N;' ELSE 'V'||octet_length(convert_to((c.convalidated::text)::text,'UTF8'))::text||':'||(c.convalidated::text)::text END) AS signature FROM pg_constraint c JOIN pg_class t ON t.oid=c.conrelid JOIN pg_namespace n ON n.oid=t.relnamespace WHERE n.nspname='ramosolo' AND c.contype <> 'n') AS constraint_rows) IS DISTINCT FROM ARRAY['V10:admissionsV15:admissions_pkeyV1:pV5:falseV5:falseV4:true','V10:admissionsV16:admissions_checkV1:cV5:falseV5:falseV4:true','V10:admissionsV26:admissions_patient_id_fkeyV1:fV5:falseV5:falseV4:true','V11:membershipsV16:memberships_pkeyV1:pV5:falseV5:falseV4:true','V11:membershipsV22:memberships_role_checkV1:cV5:falseV5:falseV4:true','V11:membershipsV24:memberships_user_id_fkeyV1:fV5:falseV5:falseV4:true','V11:membershipsV31:memberships_institution_id_fkeyV1:fV5:falseV5:falseV4:true','V11:membershipsV38:memberships_supervising_doctor_id_fkeyV1:fV5:falseV5:falseV4:true','V11:membershipsV38:memberships_user_id_institution_id_keyV1:uV5:falseV5:falseV4:true','V12:appointmentsV17:appointments_pkeyV1:pV5:falseV5:falseV4:true','V12:appointmentsV20:appointment_identityV1:cV5:falseV5:falseV4:true','V12:appointmentsV20:appointment_intervalV1:cV5:falseV5:falseV4:true','V12:appointmentsV25:appointments_status_checkV1:cV5:falseV5:falseV4:true','V12:appointmentsV27:appointments_doctor_id_fkeyV1:fV5:falseV5:falseV4:true','V12:appointmentsV28:appointments_patient_id_fkeyV1:fV5:falseV5:falseV4:true','V12:appointmentsV29:appointments_calendar_uid_keyV1:uV5:falseV5:falseV4:true','V12:appointmentsV31:appointments_submission_key_keyV1:uV5:falseV5:falseV4:true','V12:appointmentsV32:appointments_institution_id_fkeyV1:fV5:falseV5:falseV4:true','V12:appointmentsV35:appointments_booking_request_id_keyV1:uV5:falseV5:falseV4:true','V12:appointmentsV36:appointments_booking_request_id_fkeyV1:fV5:falseV5:falseV4:true','V12:audit_eventsV17:audit_events_pkeyV1:pV5:falseV5:falseV4:true','V12:audit_eventsV26:audit_events_actor_id_fkeyV1:fV5:falseV5:falseV4:true','V12:audit_eventsV32:audit_events_institution_id_fkeyV1:fV5:falseV5:falseV4:true','V12:institutionsV17:institutions_pkeyV1:pV5:falseV5:falseV4:true','V12:institutionsV23:institutions_kind_checkV1:cV5:falseV5:falseV4:true','V12:institutionsV33:institutions_demo_dataset_id_fkeyV1:fV5:falseV5:falseV4:true','V13:demo_datasetsV18:demo_datasets_pkeyV1:pV5:falseV5:falseV4:true','V13:demo_datasetsV22:demo_datasets_name_keyV1:uV5:falseV5:falseV4:true','V14:reminder_leadsV19:reminder_leads_pkeyV1:pV5:falseV5:falseV4:true','V14:reminder_leadsV28:reminder_leads_minutes_checkV1:cV5:falseV5:falseV4:true','V14:reminder_leadsV29:reminder_leads_policy_id_fkeyV1:fV5:falseV5:falseV4:true','V14:reminder_leadsV36:reminder_leads_policy_id_minutes_keyV1:uV5:falseV5:falseV4:true','V15:calendar_blocksV20:calendar_blocks_pkeyV1:pV5:falseV5:falseV4:true','V15:calendar_blocksV21:calendar_blocks_checkV1:cV5:falseV5:falseV4:true','V15:calendar_blocksV28:calendar_blocks_reason_checkV1:cV5:falseV5:falseV4:true','V15:calendar_blocksV30:calendar_blocks_doctor_id_fkeyV1:fV5:falseV5:falseV4:true','V15:calendar_blocksV31:calendar_blocks_created_by_fkeyV1:fV5:falseV5:falseV4:true','V15:calendar_blocksV32:calendar_blocks_released_by_fkeyV1:fV5:falseV5:falseV4:true','V15:calendar_blocksV35:calendar_blocks_institution_id_fkeyV1:fV5:falseV5:falseV4:true','V15:public_holidaysV20:public_holidays_pkeyV1:pV5:falseV5:falseV4:true','V15:public_holidaysV35:public_holidays_institution_id_fkeyV1:fV5:falseV5:falseV4:true','V15:public_holidaysV38:public_holidays_institution_id_day_keyV1:uV5:falseV5:falseV4:true','V15:schema_versionsV20:schema_versions_pkeyV1:pV5:falseV5:falseV4:true','V16:booking_requestsV21:booking_requests_pkeyV1:pV5:falseV5:falseV4:true','V16:booking_requestsV33:booking_requests_token_digest_keyV1:uV5:falseV5:falseV4:true','V16:booking_requestsV35:booking_requests_submission_key_keyV1:uV5:falseV5:falseV4:true','V16:booking_requestsV36:booking_requests_institution_id_fkeyV1:fV5:falseV5:falseV4:true','V16:booking_requestsV41:booking_requests_requested_doctor_id_fkeyV1:fV5:falseV5:falseV4:true','V16:care_assignmentsV21:care_assignments_pkeyV1:pV5:falseV5:falseV4:true','V16:care_assignmentsV30:care_assignments_nurse_id_fkeyV1:fV5:falseV5:falseV4:true','V16:care_assignmentsV32:care_assignments_patient_id_fkeyV1:fV5:falseV5:falseV4:true','V16:care_assignmentsV40:care_assignments_patient_id_nurse_id_keyV1:uV5:falseV5:falseV4:true','V16:medical_invoicesV21:medical_invoices_pkeyV1:pV5:falseV5:falseV4:true','V16:medical_invoicesV22:medical_invoices_checkV1:cV5:falseV5:falseV4:true','V16:medical_invoicesV28:medical_invoices_state_checkV1:cV5:falseV5:falseV4:true','V16:medical_invoicesV31:medical_invoices_doctor_id_fkeyV1:fV5:falseV5:falseV4:true','V16:medical_invoicesV31:medical_invoices_voided_by_fkeyV1:fV5:falseV5:falseV4:true','V16:medical_invoicesV32:medical_invoices_created_by_fkeyV1:fV5:falseV5:falseV4:true','V16:medical_invoicesV35:medical_invoices_appointment_id_keyV1:uV5:falseV5:falseV4:true','V16:medical_invoicesV36:medical_invoices_appointment_id_fkeyV1:fV5:falseV5:falseV4:true','V16:medical_invoicesV36:medical_invoices_institution_id_fkeyV1:fV5:falseV5:falseV4:true','V17:followup_policiesV22:followup_policies_pkeyV1:pV5:falseV5:falseV4:true','V17:followup_policiesV23:followup_policies_checkV1:cV5:falseV5:falseV4:true','V17:followup_policiesV33:followup_policies_updated_by_fkeyV1:fV5:falseV5:falseV4:true','V17:followup_policiesV36:followup_policies_institution_id_keyV1:uV5:falseV5:falseV4:true','V17:followup_policiesV37:followup_policies_institution_id_fkeyV1:fV5:falseV5:falseV4:true','V17:reminder_policiesV22:reminder_policies_pkeyV1:pV5:falseV5:falseV4:true','V17:reminder_policiesV23:reminder_policies_checkV1:cV5:falseV5:falseV4:true','V17:reminder_policiesV33:reminder_policies_updated_by_fkeyV1:fV5:falseV5:falseV4:true','V17:reminder_policiesV36:reminder_policies_institution_id_keyV1:uV5:falseV5:falseV4:true','V17:reminder_policiesV37:reminder_policies_institution_id_fkeyV1:fV5:falseV5:falseV4:true','V19:booking_rate_limitsV24:booking_rate_limits_pkeyV1:pV5:falseV5:falseV4:true','V19:booking_rate_limitsV43:booking_rate_limits_digest_window_start_keyV1:uV5:falseV5:falseV4:true','V19:notification_outboxV24:notification_outbox_pkeyV1:pV5:falseV5:falseV4:true','V19:notification_outboxV25:notification_outbox_checkV1:cV5:falseV5:falseV4:true','V19:notification_outboxV26:notification_outbox_check1V1:cV5:falseV5:falseV4:true','V19:notification_outboxV31:notification_outbox_state_checkV1:cV5:falseV5:falseV4:true','V19:notification_outboxV33:notification_outbox_channel_checkV1:cV5:falseV5:falseV4:true','V19:notification_outboxV33:notification_outbox_public_id_keyV1:uV5:falseV5:falseV4:true','V19:notification_outboxV34:notification_outbox_policy_id_fkeyV1:fV5:falseV5:falseV4:true','V19:notification_outboxV38:notification_outbox_preference_id_fkeyV1:fV5:falseV5:falseV4:true','V19:notification_outboxV39:notification_outbox_appointment_id_fkeyV1:fV5:falseV5:falseV4:true','V19:notification_outboxV39:notification_outbox_institution_id_fkeyV1:fV5:falseV5:falseV4:true','V19:notification_outboxV42:notification_outbox_recipient_user_id_fkeyV1:fV5:falseV5:falseV4:true','V19:notification_outboxV63:notification_outbox_appointment_id_appointment_version_pref_keyV1:uV5:falseV5:falseV4:true','V20:attendance_followupsV25:attendance_followups_pkeyV1:pV5:falseV5:falseV4:true','V20:attendance_followupsV31:attendance_followups_rule_checkV1:cV5:falseV5:falseV4:true','V20:attendance_followupsV32:attendance_followups_state_checkV1:cV5:falseV5:falseV4:true','V20:attendance_followupsV40:attendance_followups_appointment_id_fkeyV1:fV5:falseV5:falseV4:true','V20:attendance_followupsV40:attendance_followups_institution_id_fkeyV1:fV5:falseV5:falseV4:true','V20:attendance_followupsV63:attendance_followups_appointment_id_appointment_version_rul_keyV1:uV5:falseV5:falseV4:true','V20:in_app_notificationsV25:in_app_notifications_pkeyV1:pV5:falseV5:falseV4:true','V20:in_app_notificationsV31:in_app_notifications_job_id_keyV1:uV5:falseV5:falseV4:true','V20:in_app_notificationsV32:in_app_notifications_job_id_fkeyV1:fV5:falseV5:falseV4:true','V20:in_app_notificationsV34:in_app_notifications_public_id_keyV1:uV5:falseV5:falseV4:true','V20:in_app_notificationsV37:in_app_notifications_token_digest_keyV1:uV5:falseV5:falseV4:true','V20:in_app_notificationsV40:in_app_notifications_institution_id_fkeyV1:fV5:falseV5:falseV4:true','V21:availability_policiesV26:availability_policies_pkeyV1:pV5:falseV5:falseV4:true','V21:availability_policiesV27:availability_policies_checkV1:cV5:falseV5:falseV4:true','V21:availability_policiesV36:availability_policies_doctor_id_fkeyV1:fV5:falseV5:falseV4:true','V21:availability_policiesV41:availability_policies_institution_id_fkeyV1:fV5:falseV5:falseV4:true','V21:availability_policiesV50:availability_policies_institution_id_doctor_id_keyV1:uV5:falseV5:falseV4:true','V21:availability_sessionsV26:availability_sessions_pkeyV1:pV5:falseV5:falseV4:true','V21:availability_sessionsV27:availability_sessions_checkV1:cV5:falseV5:falseV4:true','V21:availability_sessionsV28:availability_sessions_check1V1:cV5:falseV5:falseV4:true','V21:availability_sessionsV28:availability_sessions_check2V1:cV5:falseV5:falseV4:true','V21:availability_sessionsV28:availability_sessions_check3V1:cV5:falseV5:falseV4:true','V21:availability_sessionsV36:availability_sessions_policy_id_fkeyV1:fV5:falseV5:falseV4:true','V21:notification_attemptsV23:positive_attempt_numberV1:cV5:falseV5:falseV4:true','V21:notification_attemptsV26:notification_attempts_pkeyV1:pV5:falseV5:falseV4:true','V21:notification_attemptsV33:notification_attempts_job_id_fkeyV1:fV5:falseV5:falseV4:true','V21:notification_attemptsV35:notification_attempts_outcome_checkV1:cV5:falseV5:falseV4:true','V21:notification_attemptsV39:notification_attempts_job_id_number_keyV1:uV5:falseV5:falseV4:true','V21:notification_attemptsV41:notification_attempts_institution_id_fkeyV1:fV5:falseV5:falseV4:true','V23:availability_exceptionsV28:availability_exceptions_pkeyV1:pV5:falseV5:falseV4:true','V23:availability_exceptionsV29:availability_exceptions_checkV1:cV5:falseV5:falseV4:true','V23:availability_exceptionsV34:availability_exceptions_kind_checkV1:cV5:falseV5:falseV4:true','V23:availability_exceptionsV38:availability_exceptions_policy_id_fkeyV1:fV5:falseV5:falseV4:true','V23:availability_exceptionsV40:availability_exceptions_approved_by_fkeyV1:fV5:falseV5:falseV4:true','V23:medical_payment_entriesV28:medical_payment_entries_pkeyV1:pV5:falseV5:falseV4:true','V23:medical_payment_entriesV29:medical_payment_entries_checkV1:cV5:falseV5:falseV4:true','V23:medical_payment_entriesV34:medical_payment_entries_kind_checkV1:cV5:falseV5:falseV4:true','V23:medical_payment_entriesV36:medical_payment_entries_amount_checkV1:cV5:falseV5:falseV4:true','V23:medical_payment_entriesV36:medical_payment_entries_method_checkV1:cV5:falseV5:falseV4:true','V23:medical_payment_entriesV36:medical_payment_entries_reason_checkV1:cV5:falseV5:falseV4:true','V23:medical_payment_entriesV37:medical_payment_entries_actor_id_fkeyV1:fV5:falseV5:falseV4:true','V23:medical_payment_entriesV39:medical_payment_entries_invoice_id_fkeyV1:fV5:falseV5:falseV4:true','V23:medical_payment_entriesV42:medical_payment_entries_submission_key_keyV1:uV5:falseV5:falseV4:true','V23:medical_payment_entriesV43:medical_payment_entries_institution_id_fkeyV1:fV5:falseV5:falseV4:true','V23:medical_payment_entriesV48:medical_payment_entries_original_receipt_id_fkeyV1:fV5:falseV5:falseV4:true','V25:communication_preferencesV30:communication_preferences_pkeyV1:pV5:falseV5:falseV4:true','V25:communication_preferencesV31:communication_preferences_checkV1:cV5:falseV5:falseV4:true','V25:communication_preferencesV32:communication_preferences_check1V1:cV5:falseV5:falseV4:true','V25:communication_preferencesV32:communication_preferences_check2V1:cV5:falseV5:falseV4:true','V25:communication_preferencesV41:communication_preferences_changed_by_fkeyV1:fV5:falseV5:falseV4:true','V25:communication_preferencesV41:communication_preferences_patient_id_fkeyV1:fV5:falseV5:falseV4:true','V25:communication_preferencesV45:communication_preferences_institution_id_fkeyV1:fV5:falseV5:falseV4:true','V25:communication_preferencesV49:communication_preferences_booking_request_id_fkeyV1:fV5:falseV5:falseV4:true','V25:communication_preferencesV55:communication_preferences_institution_id_patient_id_keyV1:uV5:falseV5:falseV4:true','V25:communication_preferencesV63:communication_preferences_institution_id_booking_request_id_keyV1:uV5:falseV5:falseV4:true','V27:attendance_followup_reviewsV32:attendance_followup_reviews_pkeyV1:pV5:falseV5:falseV4:true','V27:attendance_followup_reviewsV40:attendance_followup_reviews_action_checkV1:cV5:falseV5:falseV4:true','V27:attendance_followup_reviewsV41:attendance_followup_reviews_actor_id_fkeyV1:fV5:falseV5:falseV4:true','V27:attendance_followup_reviewsV44:attendance_followup_reviews_followup_id_fkeyV1:fV5:falseV5:falseV4:true','V27:attendance_followup_reviewsV47:attendance_followup_reviews_institution_id_fkeyV1:fV5:falseV5:falseV4:true','V29:appointment_attendance_eventsV34:appointment_attendance_events_pkeyV1:pV5:falseV5:falseV4:true','V29:appointment_attendance_eventsV40:appointment_attendance_events_kind_checkV1:cV5:falseV5:falseV4:true','V29:appointment_attendance_eventsV43:appointment_attendance_events_actor_id_fkeyV1:fV5:falseV5:falseV4:true','V29:appointment_attendance_eventsV49:appointment_attendance_events_appointment_id_fkeyV1:fV5:falseV5:falseV4:true','V29:appointment_attendance_eventsV49:appointment_attendance_events_institution_id_fkeyV1:fV5:falseV5:falseV4:true','V33:appointment_confirmation_requestsV38:appointment_confirmation_requests_pkeyV1:pV5:falseV5:falseV4:true','V33:appointment_confirmation_requestsV39:appointment_confirmation_requests_checkV1:cV5:falseV5:falseV4:true','V33:appointment_confirmation_requestsV40:appointment_confirmation_requests_check1V1:cV5:falseV5:falseV4:true','V33:appointment_confirmation_requestsV51:appointment_confirmation_requests_confirmed_by_fkeyV1:fV5:falseV5:falseV4:true','V33:appointment_confirmation_requestsV51:appointment_confirmation_requests_requested_by_fkeyV1:fV5:falseV5:falseV4:true','V33:appointment_confirmation_requestsV53:appointment_confirmation_requests_appointment_id_fkeyV1:fV5:falseV5:falseV4:true','V33:appointment_confirmation_requestsV53:appointment_confirmation_requests_institution_id_fkeyV1:fV5:falseV5:falseV4:true','V33:appointment_confirmation_requestsV63:appointment_confirmation_requ_appointment_id_appointment_ve_keyV1:uV5:falseV5:falseV4:true','V5:usersV10:users_pkeyV1:pV5:falseV5:falseV4:true','V5:usersV15:users_email_keyV1:uV5:falseV5:falseV4:true','V8:patientsV13:patients_pkeyV1:pV5:falseV5:falseV4:true','V8:patientsV21:patients_user_id_fkeyV1:fV5:falseV5:falseV4:true','V8:patientsV23:patients_doctor_id_fkeyV1:fV5:falseV5:falseV4:true','V8:patientsV28:patients_institution_id_fkeyV1:fV5:falseV5:falseV4:true','V8:patientsV35:patients_institution_id_user_id_keyV1:uV5:falseV5:falseV4:true']::text[] THEN RAISE EXCEPTION 'Unexpected existing constraint definitions'; END IF;
 constraint_fingerprint := (SELECT md5(coalesce(string_agg('V'||octet_length(convert_to(signature,'UTF8'))::text||':'||signature, '' ORDER BY signature COLLATE "C"),'')) FROM (SELECT concat(CASE WHEN (t.relname)::text IS NULL THEN 'N;' ELSE 'V'||octet_length(convert_to((t.relname)::text,'UTF8'))::text||':'||(t.relname)::text END,CASE WHEN (c.conname)::text IS NULL THEN 'N;' ELSE 'V'||octet_length(convert_to((c.conname)::text,'UTF8'))::text||':'||(c.conname)::text END,CASE WHEN (c.contype::text)::text IS NULL THEN 'N;' ELSE 'V'||octet_length(convert_to((c.contype::text)::text,'UTF8'))::text||':'||(c.contype::text)::text END,CASE WHEN (pg_get_constraintdef(c.oid))::text IS NULL THEN 'N;' ELSE 'V'||octet_length(convert_to((pg_get_constraintdef(c.oid))::text,'UTF8'))::text||':'||(pg_get_constraintdef(c.oid))::text END,CASE WHEN (c.condeferrable::text)::text IS NULL THEN 'N;' ELSE 'V'||octet_length(convert_to((c.condeferrable::text)::text,'UTF8'))::text||':'||(c.condeferrable::text)::text END,CASE WHEN (c.condeferred::text)::text IS NULL THEN 'N;' ELSE 'V'||octet_length(convert_to((c.condeferred::text)::text,'UTF8'))::text||':'||(c.condeferred::text)::text END,CASE WHEN (c.convalidated::text)::text IS NULL THEN 'N;' ELSE 'V'||octet_length(convert_to((c.convalidated::text)::text,'UTF8'))::text||':'||(c.convalidated::text)::text END) AS signature FROM pg_constraint c JOIN pg_class t ON t.oid=c.conrelid JOIN pg_namespace n ON n.oid=t.relnamespace WHERE n.nspname='ramosolo' AND c.contype <> 'n') AS constraint_rows);
 IF current_setting('server_version_num')::integer / 10000 = 17 AND constraint_fingerprint IS DISTINCT FROM '6e42b7f83cb9357f5abc713146cc4d22' AND constraint_fingerprint IS DISTINCT FROM '0ecc63c7f166d59e8d2a4c94de7aa685' THEN RAISE EXCEPTION 'Existing constraint definition drift'; END IF;
 IF (SELECT array_agg(indexname::text ORDER BY indexname COLLATE "C") FROM pg_indexes WHERE schemaname='ramosolo') IS DISTINCT FROM ARRAY['admissions_pkey','appointment_attendance_events_pkey','appointment_confirmation_requ_appointment_id_appointment_ve_key','appointment_confirmation_requests_pkey','appointments_booking_request_id_key','appointments_calendar_uid_key','appointments_pkey','appointments_submission_key_key','attendance_followup_reviews_pkey','attendance_followups_appointment_id_appointment_version_rul_key','attendance_followups_pkey','audit_events_pkey','availability_exceptions_pkey','availability_policies_institution_id_doctor_id_key','availability_policies_pkey','availability_sessions_pkey','booking_capacity','booking_rate_limits_digest_window_start_key','booking_rate_limits_pkey','booking_requests_pkey','booking_requests_submission_key_key','booking_requests_token_digest_key','calendar_blocks_pkey','care_assignments_patient_id_nurse_id_key','care_assignments_pkey','communication_preferences_institution_id_booking_request_id_key','communication_preferences_institution_id_patient_id_key','communication_preferences_pkey','demo_datasets_name_key','demo_datasets_pkey','doctor_calendar_blocks','followup_policies_institution_id_key','followup_policies_pkey','in_app_notifications_job_id_key','in_app_notifications_pkey','in_app_notifications_public_id_key','in_app_notifications_token_digest_key','institutions_pkey','ix_admissions_patient_id','ix_appointment_attendance_events_appointment_id','ix_appointments_patient_id','ix_appointments_starts_at','ix_attendance_followup_reviews_followup_id','ix_attendance_followups_appointment_id','ix_medical_payment_entries_invoice_id','medical_invoices_appointment_id_key','medical_invoices_pkey','medical_payment_entries_pkey','medical_payment_entries_submission_key_key','memberships_pkey','memberships_user_id_institution_id_key','notification_attempts_job_id_number_key','notification_attempts_pkey','notification_due','notification_outbox_appointment_id_appointment_version_pref_key','notification_outbox_pkey','notification_outbox_public_id_key','one_doctor_slot','one_open_admission','one_patient_slot','one_sent_appointment_reminder','patients_institution_id_user_id_key','patients_pkey','public_holidays_institution_id_day_key','public_holidays_pkey','reminder_leads_pkey','reminder_leads_policy_id_minutes_key','reminder_policies_institution_id_key','reminder_policies_pkey','schema_versions_pkey','users_email_key','users_pkey']::text[] THEN RAISE EXCEPTION 'Unexpected existing index inventory'; END IF;
 IF (SELECT md5(coalesce(string_agg(indexname||'|'||indexdef, E'\n' ORDER BY indexname COLLATE "C"),'')) FROM pg_indexes WHERE schemaname='ramosolo') IS DISTINCT FROM '45d1bacda400cf0739382ce86a725090' THEN RAISE EXCEPTION 'Existing index definition drift'; END IF;
 IF (SELECT array_agg(c.relname::text ORDER BY c.relname) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='ramosolo' AND c.relkind='r' AND c.relname IN ('appointment_proposals','calendar_delegations','calendar_history','care_plan_reviews','care_plans','care_referrals','care_review_signoffs','clinical_records','communication_decisions','continuity_events','continuity_history','continuity_notifications','coordination_coverage','coordination_history','coordination_policies','discharge_followups','external_practitioners','nursing_observations','patient_permissions','patient_preferences','referral_clinical_records')) IS NOT NULL THEN RAISE EXCEPTION 'Expected all reconciliation target tables absent'; END IF;
 IF (SELECT data_type||':'||is_nullable||':'||coalesce(column_default,'') FROM information_schema.columns WHERE table_schema='ramosolo' AND table_name='appointments' AND column_name='institution_id') IS DISTINCT FROM 'integer:NO:' THEN RAISE EXCEPTION 'appointments.institution_id definition drift'; END IF;
 IF (SELECT data_type||':'||is_nullable||':'||coalesce(column_default,'') FROM information_schema.columns WHERE table_schema='ramosolo' AND table_name='appointments' AND column_name='schedule_version') IS DISTINCT FROM 'integer:NO:1' THEN RAISE EXCEPTION 'appointments.schedule_version definition drift'; END IF;
 IF (SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid='ramosolo.appointments'::regclass AND conname='appointment_identity') IS DISTINCT FROM 'CHECK (((patient_id IS NOT NULL) <> (booking_request_id IS NOT NULL)))' THEN RAISE EXCEPTION 'appointments.appointment_identity definition drift'; END IF;
 IF (SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid='ramosolo.appointments'::regclass AND conname='appointment_interval') IS DISTINCT FROM 'CHECK (((ends_at IS NULL) OR ((ends_at > starts_at) AND (occupied_until >= ends_at))))' THEN RAISE EXCEPTION 'appointments.appointment_interval definition drift'; END IF;
 IF (SELECT indexdef FROM pg_indexes WHERE schemaname='ramosolo' AND indexname='booking_capacity') IS DISTINCT FROM 'CREATE INDEX booking_capacity ON ramosolo.appointments USING btree (doctor_id, starts_at, status, hold_expires_at)' THEN RAISE EXCEPTION 'appointments.booking_capacity definition drift'; END IF;
 IF to_regclass('ramosolo.admission_patient_identity') IS NOT NULL AND (SELECT indexdef FROM pg_indexes WHERE schemaname='ramosolo' AND indexname='admission_patient_identity') IS DISTINCT FROM 'CREATE UNIQUE INDEX admission_patient_identity ON ramosolo.admissions USING btree (id, patient_id)' THEN RAISE EXCEPTION 'admission_patient_identity definition drift'; END IF;
 IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='ramosolo' AND table_name='attendance_followups' AND column_name IN ('owner_id','cover_id','due_at','escalated')) THEN RAISE EXCEPTION 'attendance_followups has a partial 008 upgrade'; END IF;
 IF (SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid='ramosolo.appointments'::regclass AND conname='appointment_identity') IS NULL THEN RAISE EXCEPTION 'Missing appointment identity constraint'; END IF;
 IF EXISTS (SELECT 1 FROM pg_trigger WHERE tgrelid='ramosolo.notification_outbox'::regclass AND tgname='coordination_outbox_permission_guard') THEN RAISE EXCEPTION 'Coordination outbox trigger name already occupied'; END IF;
 IF (SELECT pg_get_userbyid(n.nspowner) FROM pg_namespace n WHERE n.nspname='ramosolo') IS DISTINCT FROM 'postgres' THEN RAISE EXCEPTION 'ramosolo schema owner drift'; END IF;
 IF EXISTS (SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='ramosolo' AND c.relkind IN ('r','S') AND pg_get_userbyid(c.relowner) IS DISTINCT FROM 'postgres') THEN RAISE EXCEPTION 'Existing table or sequence owner drift'; END IF;
 IF EXISTS (SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='ramosolo' AND (pg_get_userbyid(p.proowner) IS DISTINCT FROM 'postgres' OR p.prosecdef OR p.proconfig IS DISTINCT FROM ARRAY['search_path=ramosolo, pg_temp']::text[])) THEN RAISE EXCEPTION 'Existing routine owner or execution configuration drift'; END IF;
 IF EXISTS (SELECT 1 FROM pg_default_acl d LEFT JOIN pg_namespace n ON n.oid=d.defaclnamespace WHERE d.defaclrole='postgres'::regrole AND (d.defaclnamespace=0 OR n.nspname='ramosolo')) THEN RAISE EXCEPTION 'Unexpected postgres default privileges'; END IF;
 IF to_regclass('ramosolo.appointment_proposals') IS NOT NULL THEN RAISE EXCEPTION 'Expected absent target table: appointment_proposals'; END IF;
 IF to_regclass('ramosolo.calendar_delegations') IS NOT NULL THEN RAISE EXCEPTION 'Expected absent target table: calendar_delegations'; END IF;
 IF to_regclass('ramosolo.calendar_history') IS NOT NULL THEN RAISE EXCEPTION 'Expected absent target table: calendar_history'; END IF;
 IF to_regclass('ramosolo.care_plan_reviews') IS NOT NULL THEN RAISE EXCEPTION 'Expected absent target table: care_plan_reviews'; END IF;
 IF to_regclass('ramosolo.care_plans') IS NOT NULL THEN RAISE EXCEPTION 'Expected absent target table: care_plans'; END IF;
 IF to_regclass('ramosolo.care_referrals') IS NOT NULL THEN RAISE EXCEPTION 'Expected absent target table: care_referrals'; END IF;
 IF to_regclass('ramosolo.care_review_signoffs') IS NOT NULL THEN RAISE EXCEPTION 'Expected absent target table: care_review_signoffs'; END IF;
 IF to_regclass('ramosolo.clinical_records') IS NOT NULL THEN RAISE EXCEPTION 'Expected absent target table: clinical_records'; END IF;
 IF to_regclass('ramosolo.communication_decisions') IS NOT NULL THEN RAISE EXCEPTION 'Expected absent target table: communication_decisions'; END IF;
 IF to_regclass('ramosolo.continuity_events') IS NOT NULL THEN RAISE EXCEPTION 'Expected absent target table: continuity_events'; END IF;
 IF to_regclass('ramosolo.continuity_history') IS NOT NULL THEN RAISE EXCEPTION 'Expected absent target table: continuity_history'; END IF;
 IF to_regclass('ramosolo.continuity_notifications') IS NOT NULL THEN RAISE EXCEPTION 'Expected absent target table: continuity_notifications'; END IF;
 IF to_regclass('ramosolo.coordination_coverage') IS NOT NULL THEN RAISE EXCEPTION 'Expected absent target table: coordination_coverage'; END IF;
 IF to_regclass('ramosolo.coordination_history') IS NOT NULL THEN RAISE EXCEPTION 'Expected absent target table: coordination_history'; END IF;
 IF to_regclass('ramosolo.coordination_policies') IS NOT NULL THEN RAISE EXCEPTION 'Expected absent target table: coordination_policies'; END IF;
 IF to_regclass('ramosolo.discharge_followups') IS NOT NULL THEN RAISE EXCEPTION 'Expected absent target table: discharge_followups'; END IF;
 IF to_regclass('ramosolo.external_practitioners') IS NOT NULL THEN RAISE EXCEPTION 'Expected absent target table: external_practitioners'; END IF;
 IF to_regclass('ramosolo.nursing_observations') IS NOT NULL THEN RAISE EXCEPTION 'Expected absent target table: nursing_observations'; END IF;
 IF to_regclass('ramosolo.patient_permissions') IS NOT NULL THEN RAISE EXCEPTION 'Expected absent target table: patient_permissions'; END IF;
 IF to_regclass('ramosolo.patient_preferences') IS NOT NULL THEN RAISE EXCEPTION 'Expected absent target table: patient_preferences'; END IF;
 IF to_regclass('ramosolo.referral_clinical_records') IS NOT NULL THEN RAISE EXCEPTION 'Expected absent target table: referral_clinical_records'; END IF;
 IF (SELECT md5(p.prosrc) FROM pg_proc p WHERE p.pronamespace='ramosolo'::regnamespace AND p.proname='appointment_attendance_event') IS DISTINCT FROM '9e91e5561f2cdafaeafb8a91bcbcf484' THEN RAISE EXCEPTION 'Existing routine source drift: appointment_attendance_event'; END IF;
 IF (SELECT md5(p.prosrc) FROM pg_proc p WHERE p.pronamespace='ramosolo'::regnamespace AND p.proname='booking_appointment_guard') IS DISTINCT FROM 'd9713aa1040af31189bb0e30e3115248' THEN RAISE EXCEPTION 'Existing routine source drift: booking_appointment_guard'; END IF;
 IF (SELECT md5(p.prosrc) FROM pg_proc p WHERE p.pronamespace='ramosolo'::regnamespace AND p.proname='booking_config_guard') IS DISTINCT FROM 'cd1ddad5ffab5ee73012a534ca9eebed' THEN RAISE EXCEPTION 'Existing routine source drift: booking_config_guard'; END IF;
 IF (SELECT md5(p.prosrc) FROM pg_proc p WHERE p.pronamespace='ramosolo'::regnamespace AND p.proname='booking_exception_audit') IS DISTINCT FROM '1a809621f31768c27022f14f1be4da69' THEN RAISE EXCEPTION 'Existing routine source drift: booking_exception_audit'; END IF;
 IF (SELECT md5(p.prosrc) FROM pg_proc p WHERE p.pronamespace='ramosolo'::regnamespace AND p.proname='calendar_appointment_metadata') IS DISTINCT FROM '8c7fa0f0431fbbcf41223cae5ea61d6c' THEN RAISE EXCEPTION 'Existing routine source drift: calendar_appointment_metadata'; END IF;
 IF (SELECT md5(p.prosrc) FROM pg_proc p WHERE p.pronamespace='ramosolo'::regnamespace AND p.proname='calendar_block_guard') IS DISTINCT FROM 'd349b9ab86c3429f53e439aa409d035e' THEN RAISE EXCEPTION 'Existing routine source drift: calendar_block_guard'; END IF;
 IF (SELECT md5(p.prosrc) FROM pg_proc p WHERE p.pronamespace='ramosolo'::regnamespace AND p.proname='financial_audit') IS DISTINCT FROM '6e2394f201f09e24e250fe95d501b985' THEN RAISE EXCEPTION 'Existing routine source drift: financial_audit'; END IF;
 IF (SELECT md5(p.prosrc) FROM pg_proc p WHERE p.pronamespace='ramosolo'::regnamespace AND p.proname='followup_actor_allowed') IS DISTINCT FROM '01c75ddc7bc63863c8db293884a0d2d5' THEN RAISE EXCEPTION 'Existing routine source drift: followup_actor_allowed'; END IF;
 IF (SELECT md5(p.prosrc) FROM pg_proc p WHERE p.pronamespace='ramosolo'::regnamespace AND p.proname='followup_guard') IS DISTINCT FROM 'd70963d85293a7ac5b6d2b39aedb87f9' THEN RAISE EXCEPTION 'Existing routine source drift: followup_guard'; END IF;
 IF (SELECT md5(p.prosrc) FROM pg_proc p WHERE p.pronamespace='ramosolo'::regnamespace AND p.proname='invalidate_reminder_jobs') IS DISTINCT FROM '27fe0e41e15fd3acd344daf9052fd35c' THEN RAISE EXCEPTION 'Existing routine source drift: invalidate_reminder_jobs'; END IF;
 IF (SELECT md5(p.prosrc) FROM pg_proc p WHERE p.pronamespace='ramosolo'::regnamespace AND p.proname='medical_assignment_guard') IS DISTINCT FROM 'df43c9d5a3008225990b7419aab40b86' THEN RAISE EXCEPTION 'Existing routine source drift: medical_assignment_guard'; END IF;
 IF (SELECT md5(p.prosrc) FROM pg_proc p WHERE p.pronamespace='ramosolo'::regnamespace AND p.proname='medical_invoice_guard') IS DISTINCT FROM 'd33780a803d1a24a7d737c8d9882daf0' THEN RAISE EXCEPTION 'Existing routine source drift: medical_invoice_guard'; END IF;
 IF (SELECT md5(p.prosrc) FROM pg_proc p WHERE p.pronamespace='ramosolo'::regnamespace AND p.proname='medical_payment_guard') IS DISTINCT FROM '2db24f785ca8a3140991480d323a991e' THEN RAISE EXCEPTION 'Existing routine source drift: medical_payment_guard'; END IF;
 IF (SELECT md5(p.prosrc) FROM pg_proc p WHERE p.pronamespace='ramosolo'::regnamespace AND p.proname='notification_outbox_guard') IS DISTINCT FROM '9e685225c72ec43064d55d53011329bd' THEN RAISE EXCEPTION 'Existing routine source drift: notification_outbox_guard'; END IF;
 IF (SELECT md5(p.prosrc) FROM pg_proc p WHERE p.pronamespace='ramosolo'::regnamespace AND p.proname='reminder_configuration_guard') IS DISTINCT FROM 'df4237a5ada4b48a7b9ec5f9a8ddc1ab' THEN RAISE EXCEPTION 'Existing routine source drift: reminder_configuration_guard'; END IF;
 IF (SELECT md5(p.prosrc) FROM pg_proc p WHERE p.pronamespace='ramosolo'::regnamespace AND p.proname='reminder_delivery_guard') IS DISTINCT FROM '4ca822b50eaf738e56516208c7518203' THEN RAISE EXCEPTION 'Existing routine source drift: reminder_delivery_guard'; END IF;
 IF (SELECT md5(p.prosrc) FROM pg_proc p WHERE p.pronamespace='ramosolo'::regnamespace AND p.proname='reminder_job_current') IS DISTINCT FROM 'f457d575e0b28d04dda55a446487660f' THEN RAISE EXCEPTION 'Existing routine source drift: reminder_job_current'; END IF;
 IF (SELECT md5(p.prosrc) FROM pg_proc p WHERE p.pronamespace='ramosolo'::regnamespace AND p.proname='reminder_source_invalidation') IS DISTINCT FROM 'c3aeea35cb0d1d9e61af94c70edbf111' THEN RAISE EXCEPTION 'Existing routine source drift: reminder_source_invalidation'; END IF;
 IF (SELECT md5(pg_get_triggerdef(t.oid)) FROM pg_trigger t WHERE t.tgrelid='ramosolo.appointment_attendance_events'::regclass AND t.tgname='attendance_event_guard' AND NOT t.tgisinternal) IS DISTINCT FROM '51801af62b0ae96af2ea2da8b025586a' THEN RAISE EXCEPTION 'Existing trigger definition drift: appointment_attendance_events.attendance_event_guard'; END IF;
 IF (SELECT t.tgenabled::text FROM pg_trigger t WHERE t.tgrelid='ramosolo.appointment_attendance_events'::regclass AND t.tgname='attendance_event_guard' AND NOT t.tgisinternal) IS DISTINCT FROM 'O' THEN RAISE EXCEPTION 'Existing trigger enablement drift: appointment_attendance_events.attendance_event_guard'; END IF;
 IF (SELECT md5(pg_get_triggerdef(t.oid)) FROM pg_trigger t WHERE t.tgrelid='ramosolo.appointment_confirmation_requests'::regclass AND t.tgname='confirmation_request_guard' AND NOT t.tgisinternal) IS DISTINCT FROM '012888ac8a5390ec7881428392ca748f' THEN RAISE EXCEPTION 'Existing trigger definition drift: appointment_confirmation_requests.confirmation_request_guard'; END IF;
 IF (SELECT t.tgenabled::text FROM pg_trigger t WHERE t.tgrelid='ramosolo.appointment_confirmation_requests'::regclass AND t.tgname='confirmation_request_guard' AND NOT t.tgisinternal) IS DISTINCT FROM 'O' THEN RAISE EXCEPTION 'Existing trigger enablement drift: appointment_confirmation_requests.confirmation_request_guard'; END IF;
 IF (SELECT md5(pg_get_triggerdef(t.oid)) FROM pg_trigger t WHERE t.tgrelid='ramosolo.appointments'::regclass AND t.tgname='appointment_assignment_scope' AND NOT t.tgisinternal) IS DISTINCT FROM '5e95327eb529bcfa19f7243a511140a8' THEN RAISE EXCEPTION 'Existing trigger definition drift: appointments.appointment_assignment_scope'; END IF;
 IF (SELECT t.tgenabled::text FROM pg_trigger t WHERE t.tgrelid='ramosolo.appointments'::regclass AND t.tgname='appointment_assignment_scope' AND NOT t.tgisinternal) IS DISTINCT FROM 'O' THEN RAISE EXCEPTION 'Existing trigger enablement drift: appointments.appointment_assignment_scope'; END IF;
 IF (SELECT md5(pg_get_triggerdef(t.oid)) FROM pg_trigger t WHERE t.tgrelid='ramosolo.appointments'::regclass AND t.tgname='appointment_attendance_history' AND NOT t.tgisinternal) IS DISTINCT FROM '5360d15de5aaa20cc0038f48d08133e6' THEN RAISE EXCEPTION 'Existing trigger definition drift: appointments.appointment_attendance_history'; END IF;
 IF (SELECT t.tgenabled::text FROM pg_trigger t WHERE t.tgrelid='ramosolo.appointments'::regclass AND t.tgname='appointment_attendance_history' AND NOT t.tgisinternal) IS DISTINCT FROM 'O' THEN RAISE EXCEPTION 'Existing trigger enablement drift: appointments.appointment_attendance_history'; END IF;
 IF (SELECT md5(pg_get_triggerdef(t.oid)) FROM pg_trigger t WHERE t.tgrelid='ramosolo.appointments'::regclass AND t.tgname='appointment_capacity_guard' AND NOT t.tgisinternal) IS DISTINCT FROM '12a302c5dadece5caedcc35306863bce' THEN RAISE EXCEPTION 'Existing trigger definition drift: appointments.appointment_capacity_guard'; END IF;
 IF (SELECT t.tgenabled::text FROM pg_trigger t WHERE t.tgrelid='ramosolo.appointments'::regclass AND t.tgname='appointment_capacity_guard' AND NOT t.tgisinternal) IS DISTINCT FROM 'O' THEN RAISE EXCEPTION 'Existing trigger enablement drift: appointments.appointment_capacity_guard'; END IF;
 IF (SELECT md5(pg_get_triggerdef(t.oid)) FROM pg_trigger t WHERE t.tgrelid='ramosolo.appointments'::regclass AND t.tgname='appointment_metadata_guard' AND NOT t.tgisinternal) IS DISTINCT FROM 'e4cb10c5b69970b86615012712dd398f' THEN RAISE EXCEPTION 'Existing trigger definition drift: appointments.appointment_metadata_guard'; END IF;
 IF (SELECT t.tgenabled::text FROM pg_trigger t WHERE t.tgrelid='ramosolo.appointments'::regclass AND t.tgname='appointment_metadata_guard' AND NOT t.tgisinternal) IS DISTINCT FROM 'O' THEN RAISE EXCEPTION 'Existing trigger enablement drift: appointments.appointment_metadata_guard'; END IF;
 IF (SELECT md5(pg_get_triggerdef(t.oid)) FROM pg_trigger t WHERE t.tgrelid='ramosolo.appointments'::regclass AND t.tgname='appointment_reminder_invalidation' AND NOT t.tgisinternal) IS DISTINCT FROM 'd105e40f87fa4d91dcbfb0a224ddd10b' THEN RAISE EXCEPTION 'Existing trigger definition drift: appointments.appointment_reminder_invalidation'; END IF;
 IF (SELECT t.tgenabled::text FROM pg_trigger t WHERE t.tgrelid='ramosolo.appointments'::regclass AND t.tgname='appointment_reminder_invalidation' AND NOT t.tgisinternal) IS DISTINCT FROM 'O' THEN RAISE EXCEPTION 'Existing trigger enablement drift: appointments.appointment_reminder_invalidation'; END IF;
 IF (SELECT md5(pg_get_triggerdef(t.oid)) FROM pg_trigger t WHERE t.tgrelid='ramosolo.attendance_followup_reviews'::regclass AND t.tgname='followup_review_guard' AND NOT t.tgisinternal) IS DISTINCT FROM 'ff8f4e1ea2cefa72f9c21919c3dd2ca7' THEN RAISE EXCEPTION 'Existing trigger definition drift: attendance_followup_reviews.followup_review_guard'; END IF;
 IF (SELECT t.tgenabled::text FROM pg_trigger t WHERE t.tgrelid='ramosolo.attendance_followup_reviews'::regclass AND t.tgname='followup_review_guard' AND NOT t.tgisinternal) IS DISTINCT FROM 'O' THEN RAISE EXCEPTION 'Existing trigger enablement drift: attendance_followup_reviews.followup_review_guard'; END IF;
 IF (SELECT md5(pg_get_triggerdef(t.oid)) FROM pg_trigger t WHERE t.tgrelid='ramosolo.attendance_followups'::regclass AND t.tgname='attendance_followup_guard' AND NOT t.tgisinternal) IS DISTINCT FROM '351e618dc60ac24fea159e0ff2b6af38' THEN RAISE EXCEPTION 'Existing trigger definition drift: attendance_followups.attendance_followup_guard'; END IF;
 IF (SELECT t.tgenabled::text FROM pg_trigger t WHERE t.tgrelid='ramosolo.attendance_followups'::regclass AND t.tgname='attendance_followup_guard' AND NOT t.tgisinternal) IS DISTINCT FROM 'O' THEN RAISE EXCEPTION 'Existing trigger enablement drift: attendance_followups.attendance_followup_guard'; END IF;
 IF (SELECT md5(pg_get_triggerdef(t.oid)) FROM pg_trigger t WHERE t.tgrelid='ramosolo.availability_exceptions'::regclass AND t.tgname='exception_audit' AND NOT t.tgisinternal) IS DISTINCT FROM '99830920711cd0aab5a8076d30dc0f01' THEN RAISE EXCEPTION 'Existing trigger definition drift: availability_exceptions.exception_audit'; END IF;
 IF (SELECT t.tgenabled::text FROM pg_trigger t WHERE t.tgrelid='ramosolo.availability_exceptions'::regclass AND t.tgname='exception_audit' AND NOT t.tgisinternal) IS DISTINCT FROM 'O' THEN RAISE EXCEPTION 'Existing trigger enablement drift: availability_exceptions.exception_audit'; END IF;
 IF (SELECT md5(pg_get_triggerdef(t.oid)) FROM pg_trigger t WHERE t.tgrelid='ramosolo.availability_exceptions'::regclass AND t.tgname='exception_guard' AND NOT t.tgisinternal) IS DISTINCT FROM 'd4b52244db06ed4b581c66aad232f097' THEN RAISE EXCEPTION 'Existing trigger definition drift: availability_exceptions.exception_guard'; END IF;
 IF (SELECT t.tgenabled::text FROM pg_trigger t WHERE t.tgrelid='ramosolo.availability_exceptions'::regclass AND t.tgname='exception_guard' AND NOT t.tgisinternal) IS DISTINCT FROM 'O' THEN RAISE EXCEPTION 'Existing trigger enablement drift: availability_exceptions.exception_guard'; END IF;
 IF (SELECT md5(pg_get_triggerdef(t.oid)) FROM pg_trigger t WHERE t.tgrelid='ramosolo.availability_policies'::regclass AND t.tgname='policy_guard' AND NOT t.tgisinternal) IS DISTINCT FROM '9d25ea68cb3339f7fc5e21b458184a68' THEN RAISE EXCEPTION 'Existing trigger definition drift: availability_policies.policy_guard'; END IF;
 IF (SELECT t.tgenabled::text FROM pg_trigger t WHERE t.tgrelid='ramosolo.availability_policies'::regclass AND t.tgname='policy_guard' AND NOT t.tgisinternal) IS DISTINCT FROM 'O' THEN RAISE EXCEPTION 'Existing trigger enablement drift: availability_policies.policy_guard'; END IF;
 IF (SELECT md5(pg_get_triggerdef(t.oid)) FROM pg_trigger t WHERE t.tgrelid='ramosolo.availability_sessions'::regclass AND t.tgname='session_guard' AND NOT t.tgisinternal) IS DISTINCT FROM '38f94d9d044b45b3363433bb2ead5e71' THEN RAISE EXCEPTION 'Existing trigger definition drift: availability_sessions.session_guard'; END IF;
 IF (SELECT t.tgenabled::text FROM pg_trigger t WHERE t.tgrelid='ramosolo.availability_sessions'::regclass AND t.tgname='session_guard' AND NOT t.tgisinternal) IS DISTINCT FROM 'O' THEN RAISE EXCEPTION 'Existing trigger enablement drift: availability_sessions.session_guard'; END IF;
 IF (SELECT md5(pg_get_triggerdef(t.oid)) FROM pg_trigger t WHERE t.tgrelid='ramosolo.calendar_blocks'::regclass AND t.tgname='calendar_block_protection' AND NOT t.tgisinternal) IS DISTINCT FROM 'f05ee14711574c13e976db45d8e0a7c5' THEN RAISE EXCEPTION 'Existing trigger definition drift: calendar_blocks.calendar_block_protection'; END IF;
 IF (SELECT t.tgenabled::text FROM pg_trigger t WHERE t.tgrelid='ramosolo.calendar_blocks'::regclass AND t.tgname='calendar_block_protection' AND NOT t.tgisinternal) IS DISTINCT FROM 'O' THEN RAISE EXCEPTION 'Existing trigger enablement drift: calendar_blocks.calendar_block_protection'; END IF;
 IF (SELECT md5(pg_get_triggerdef(t.oid)) FROM pg_trigger t WHERE t.tgrelid='ramosolo.care_assignments'::regclass AND t.tgname='nursing_assignment_scope' AND NOT t.tgisinternal) IS DISTINCT FROM 'd0dc14375a7d849cf5732f8cff3c6140' THEN RAISE EXCEPTION 'Existing trigger definition drift: care_assignments.nursing_assignment_scope'; END IF;
 IF (SELECT t.tgenabled::text FROM pg_trigger t WHERE t.tgrelid='ramosolo.care_assignments'::regclass AND t.tgname='nursing_assignment_scope' AND NOT t.tgisinternal) IS DISTINCT FROM 'O' THEN RAISE EXCEPTION 'Existing trigger enablement drift: care_assignments.nursing_assignment_scope'; END IF;
 IF (SELECT md5(pg_get_triggerdef(t.oid)) FROM pg_trigger t WHERE t.tgrelid='ramosolo.communication_preferences'::regclass AND t.tgname='communication_preference_guard' AND NOT t.tgisinternal) IS DISTINCT FROM '547aeb5b2c4d57c3cabe250249c721f6' THEN RAISE EXCEPTION 'Existing trigger definition drift: communication_preferences.communication_preference_guard'; END IF;
 IF (SELECT t.tgenabled::text FROM pg_trigger t WHERE t.tgrelid='ramosolo.communication_preferences'::regclass AND t.tgname='communication_preference_guard' AND NOT t.tgisinternal) IS DISTINCT FROM 'O' THEN RAISE EXCEPTION 'Existing trigger enablement drift: communication_preferences.communication_preference_guard'; END IF;
 IF (SELECT md5(pg_get_triggerdef(t.oid)) FROM pg_trigger t WHERE t.tgrelid='ramosolo.communication_preferences'::regclass AND t.tgname='preference_reminder_invalidation' AND NOT t.tgisinternal) IS DISTINCT FROM '93980af46ec7979c397ee05a07607365' THEN RAISE EXCEPTION 'Existing trigger definition drift: communication_preferences.preference_reminder_invalidation'; END IF;
 IF (SELECT t.tgenabled::text FROM pg_trigger t WHERE t.tgrelid='ramosolo.communication_preferences'::regclass AND t.tgname='preference_reminder_invalidation' AND NOT t.tgisinternal) IS DISTINCT FROM 'O' THEN RAISE EXCEPTION 'Existing trigger enablement drift: communication_preferences.preference_reminder_invalidation'; END IF;
 IF (SELECT md5(pg_get_triggerdef(t.oid)) FROM pg_trigger t WHERE t.tgrelid='ramosolo.followup_policies'::regclass AND t.tgname='followup_policy_guard' AND NOT t.tgisinternal) IS DISTINCT FROM 'd60a0feb9a990f2a9d3fbe15ba68639e' THEN RAISE EXCEPTION 'Existing trigger definition drift: followup_policies.followup_policy_guard'; END IF;
 IF (SELECT t.tgenabled::text FROM pg_trigger t WHERE t.tgrelid='ramosolo.followup_policies'::regclass AND t.tgname='followup_policy_guard' AND NOT t.tgisinternal) IS DISTINCT FROM 'O' THEN RAISE EXCEPTION 'Existing trigger enablement drift: followup_policies.followup_policy_guard'; END IF;
 IF (SELECT md5(pg_get_triggerdef(t.oid)) FROM pg_trigger t WHERE t.tgrelid='ramosolo.in_app_notifications'::regclass AND t.tgname='in_app_notification_protection' AND NOT t.tgisinternal) IS DISTINCT FROM '3ff666c30acf97879b87da82925766a8' THEN RAISE EXCEPTION 'Existing trigger definition drift: in_app_notifications.in_app_notification_protection'; END IF;
 IF (SELECT t.tgenabled::text FROM pg_trigger t WHERE t.tgrelid='ramosolo.in_app_notifications'::regclass AND t.tgname='in_app_notification_protection' AND NOT t.tgisinternal) IS DISTINCT FROM 'O' THEN RAISE EXCEPTION 'Existing trigger enablement drift: in_app_notifications.in_app_notification_protection'; END IF;
 IF (SELECT md5(pg_get_triggerdef(t.oid)) FROM pg_trigger t WHERE t.tgrelid='ramosolo.medical_invoices'::regclass AND t.tgname='invoice_audit' AND NOT t.tgisinternal) IS DISTINCT FROM 'b0635cee3c81fe6eadcd82ca5621ad4b' THEN RAISE EXCEPTION 'Existing trigger definition drift: medical_invoices.invoice_audit'; END IF;
 IF (SELECT t.tgenabled::text FROM pg_trigger t WHERE t.tgrelid='ramosolo.medical_invoices'::regclass AND t.tgname='invoice_audit' AND NOT t.tgisinternal) IS DISTINCT FROM 'O' THEN RAISE EXCEPTION 'Existing trigger enablement drift: medical_invoices.invoice_audit'; END IF;
 IF (SELECT md5(pg_get_triggerdef(t.oid)) FROM pg_trigger t WHERE t.tgrelid='ramosolo.medical_invoices'::regclass AND t.tgname='invoice_protection' AND NOT t.tgisinternal) IS DISTINCT FROM 'c3b6a2d31bbdf28b443d5c1f77173163' THEN RAISE EXCEPTION 'Existing trigger definition drift: medical_invoices.invoice_protection'; END IF;
 IF (SELECT t.tgenabled::text FROM pg_trigger t WHERE t.tgrelid='ramosolo.medical_invoices'::regclass AND t.tgname='invoice_protection' AND NOT t.tgisinternal) IS DISTINCT FROM 'O' THEN RAISE EXCEPTION 'Existing trigger enablement drift: medical_invoices.invoice_protection'; END IF;
 IF (SELECT md5(pg_get_triggerdef(t.oid)) FROM pg_trigger t WHERE t.tgrelid='ramosolo.medical_payment_entries'::regclass AND t.tgname='payment_audit' AND NOT t.tgisinternal) IS DISTINCT FROM 'cfcf5ba20510b999df420a68105d931c' THEN RAISE EXCEPTION 'Existing trigger definition drift: medical_payment_entries.payment_audit'; END IF;
 IF (SELECT t.tgenabled::text FROM pg_trigger t WHERE t.tgrelid='ramosolo.medical_payment_entries'::regclass AND t.tgname='payment_audit' AND NOT t.tgisinternal) IS DISTINCT FROM 'O' THEN RAISE EXCEPTION 'Existing trigger enablement drift: medical_payment_entries.payment_audit'; END IF;
 IF (SELECT md5(pg_get_triggerdef(t.oid)) FROM pg_trigger t WHERE t.tgrelid='ramosolo.medical_payment_entries'::regclass AND t.tgname='payment_protection' AND NOT t.tgisinternal) IS DISTINCT FROM '6bd02273edc00a36aa5bb493611ace02' THEN RAISE EXCEPTION 'Existing trigger definition drift: medical_payment_entries.payment_protection'; END IF;
 IF (SELECT t.tgenabled::text FROM pg_trigger t WHERE t.tgrelid='ramosolo.medical_payment_entries'::regclass AND t.tgname='payment_protection' AND NOT t.tgisinternal) IS DISTINCT FROM 'O' THEN RAISE EXCEPTION 'Existing trigger enablement drift: medical_payment_entries.payment_protection'; END IF;
 IF (SELECT md5(pg_get_triggerdef(t.oid)) FROM pg_trigger t WHERE t.tgrelid='ramosolo.memberships'::regclass AND t.tgname='membership_assignment_scope' AND NOT t.tgisinternal) IS DISTINCT FROM '68721a4b64189da3c1cd851149edf6fd' THEN RAISE EXCEPTION 'Existing trigger definition drift: memberships.membership_assignment_scope'; END IF;
 IF (SELECT t.tgenabled::text FROM pg_trigger t WHERE t.tgrelid='ramosolo.memberships'::regclass AND t.tgname='membership_assignment_scope' AND NOT t.tgisinternal) IS DISTINCT FROM 'O' THEN RAISE EXCEPTION 'Existing trigger enablement drift: memberships.membership_assignment_scope'; END IF;
 IF (SELECT md5(pg_get_triggerdef(t.oid)) FROM pg_trigger t WHERE t.tgrelid='ramosolo.notification_attempts'::regclass AND t.tgname='notification_attempt_protection' AND NOT t.tgisinternal) IS DISTINCT FROM '18b50cca3c2ce7f9cf4d728ca19ece4a' THEN RAISE EXCEPTION 'Existing trigger definition drift: notification_attempts.notification_attempt_protection'; END IF;
 IF (SELECT t.tgenabled::text FROM pg_trigger t WHERE t.tgrelid='ramosolo.notification_attempts'::regclass AND t.tgname='notification_attempt_protection' AND NOT t.tgisinternal) IS DISTINCT FROM 'O' THEN RAISE EXCEPTION 'Existing trigger enablement drift: notification_attempts.notification_attempt_protection'; END IF;
 IF (SELECT md5(pg_get_triggerdef(t.oid)) FROM pg_trigger t WHERE t.tgrelid='ramosolo.notification_outbox'::regclass AND t.tgname='notification_outbox_protection' AND NOT t.tgisinternal) IS DISTINCT FROM '0d99b5649c5fb7a287cbd0ebe6dccf39' THEN RAISE EXCEPTION 'Existing trigger definition drift: notification_outbox.notification_outbox_protection'; END IF;
 IF (SELECT t.tgenabled::text FROM pg_trigger t WHERE t.tgrelid='ramosolo.notification_outbox'::regclass AND t.tgname='notification_outbox_protection' AND NOT t.tgisinternal) IS DISTINCT FROM 'O' THEN RAISE EXCEPTION 'Existing trigger enablement drift: notification_outbox.notification_outbox_protection'; END IF;
 IF (SELECT md5(pg_get_triggerdef(t.oid)) FROM pg_trigger t WHERE t.tgrelid='ramosolo.patients'::regclass AND t.tgname='patient_assignment_scope' AND NOT t.tgisinternal) IS DISTINCT FROM 'cc335f883f30431306c84dc8ae7aaa29' THEN RAISE EXCEPTION 'Existing trigger definition drift: patients.patient_assignment_scope'; END IF;
 IF (SELECT t.tgenabled::text FROM pg_trigger t WHERE t.tgrelid='ramosolo.patients'::regclass AND t.tgname='patient_assignment_scope' AND NOT t.tgisinternal) IS DISTINCT FROM 'O' THEN RAISE EXCEPTION 'Existing trigger enablement drift: patients.patient_assignment_scope'; END IF;
 IF (SELECT md5(pg_get_triggerdef(t.oid)) FROM pg_trigger t WHERE t.tgrelid='ramosolo.patients'::regclass AND t.tgname='patient_reminder_invalidation' AND NOT t.tgisinternal) IS DISTINCT FROM '810f412ecec1b6d5fd34b419037bfac1' THEN RAISE EXCEPTION 'Existing trigger definition drift: patients.patient_reminder_invalidation'; END IF;
 IF (SELECT t.tgenabled::text FROM pg_trigger t WHERE t.tgrelid='ramosolo.patients'::regclass AND t.tgname='patient_reminder_invalidation' AND NOT t.tgisinternal) IS DISTINCT FROM 'O' THEN RAISE EXCEPTION 'Existing trigger enablement drift: patients.patient_reminder_invalidation'; END IF;
 IF (SELECT md5(pg_get_triggerdef(t.oid)) FROM pg_trigger t WHERE t.tgrelid='ramosolo.public_holidays'::regclass AND t.tgname='holiday_guard' AND NOT t.tgisinternal) IS DISTINCT FROM '284b28650fa809cba27805de7ea977db' THEN RAISE EXCEPTION 'Existing trigger definition drift: public_holidays.holiday_guard'; END IF;
 IF (SELECT t.tgenabled::text FROM pg_trigger t WHERE t.tgrelid='ramosolo.public_holidays'::regclass AND t.tgname='holiday_guard' AND NOT t.tgisinternal) IS DISTINCT FROM 'O' THEN RAISE EXCEPTION 'Existing trigger enablement drift: public_holidays.holiday_guard'; END IF;
 IF (SELECT md5(pg_get_triggerdef(t.oid)) FROM pg_trigger t WHERE t.tgrelid='ramosolo.reminder_leads'::regclass AND t.tgname='reminder_lead_guard' AND NOT t.tgisinternal) IS DISTINCT FROM '6ef97de0d2f4b3e581cce4803f406229' THEN RAISE EXCEPTION 'Existing trigger definition drift: reminder_leads.reminder_lead_guard'; END IF;
 IF (SELECT t.tgenabled::text FROM pg_trigger t WHERE t.tgrelid='ramosolo.reminder_leads'::regclass AND t.tgname='reminder_lead_guard' AND NOT t.tgisinternal) IS DISTINCT FROM 'O' THEN RAISE EXCEPTION 'Existing trigger enablement drift: reminder_leads.reminder_lead_guard'; END IF;
 IF (SELECT md5(pg_get_triggerdef(t.oid)) FROM pg_trigger t WHERE t.tgrelid='ramosolo.reminder_policies'::regclass AND t.tgname='policy_reminder_invalidation' AND NOT t.tgisinternal) IS DISTINCT FROM 'f6825bdcc0977a1816058688d7400a5e' THEN RAISE EXCEPTION 'Existing trigger definition drift: reminder_policies.policy_reminder_invalidation'; END IF;
 IF (SELECT t.tgenabled::text FROM pg_trigger t WHERE t.tgrelid='ramosolo.reminder_policies'::regclass AND t.tgname='policy_reminder_invalidation' AND NOT t.tgisinternal) IS DISTINCT FROM 'O' THEN RAISE EXCEPTION 'Existing trigger enablement drift: reminder_policies.policy_reminder_invalidation'; END IF;
 IF (SELECT md5(pg_get_triggerdef(t.oid)) FROM pg_trigger t WHERE t.tgrelid='ramosolo.reminder_policies'::regclass AND t.tgname='reminder_policy_guard' AND NOT t.tgisinternal) IS DISTINCT FROM '732e000ace5d9308f2341a44af29a245' THEN RAISE EXCEPTION 'Existing trigger definition drift: reminder_policies.reminder_policy_guard'; END IF;
 IF (SELECT t.tgenabled::text FROM pg_trigger t WHERE t.tgrelid='ramosolo.reminder_policies'::regclass AND t.tgname='reminder_policy_guard' AND NOT t.tgisinternal) IS DISTINCT FROM 'O' THEN RAISE EXCEPTION 'Existing trigger enablement drift: reminder_policies.reminder_policy_guard'; END IF;
 PERFORM set_config('search_path',original_search_path,true);
 IF EXISTS (SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace CROSS JOIN LATERAL aclexplode(coalesce(c.relacl,acldefault(CASE WHEN c.relkind='S' THEN 'S'::"char" ELSE 'r'::"char" END,c.relowner))) x WHERE n.nspname='ramosolo' AND c.relkind IN ('r','S') AND x.grantee<>c.relowner) THEN RAISE EXCEPTION 'Unexpected table or sequence grants'; END IF;
 IF EXISTS (SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace CROSS JOIN LATERAL aclexplode(coalesce(p.proacl,acldefault('f'::"char",p.proowner))) x WHERE n.nspname='ramosolo' AND x.grantee<>p.proowner) THEN RAISE EXCEPTION 'Unexpected routine grants'; END IF;
 IF EXISTS (SELECT 1 FROM pg_namespace n CROSS JOIN LATERAL aclexplode(coalesce(n.nspacl,acldefault('n'::"char",n.nspowner))) x WHERE n.nspname='ramosolo' AND x.grantee<>n.nspowner) THEN RAISE EXCEPTION 'Unexpected schema grants'; END IF;
END $preflight$;
CREATE TABLE care_plans (
	id SERIAL NOT NULL, 
	institution_id INTEGER NOT NULL, 
	patient_id INTEGER NOT NULL, 
	author_id INTEGER NOT NULL, 
	owner_id INTEGER NOT NULL, 
	goals TEXT NOT NULL, 
	warning_signs TEXT NOT NULL, 
	channels JSON NOT NULL, 
	communication_consent BOOLEAN NOT NULL, 
	planned_appointments TEXT NOT NULL, 
	review_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	response_steps TEXT NOT NULL, 
	urgent_help TEXT NOT NULL, 
	monitoring_hours VARCHAR(500) NOT NULL, 
	rules JSON NOT NULL, 
	clinical_definitions TEXT NOT NULL, 
	patient_visible BOOLEAN NOT NULL, 
	agreed_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT care_plan_patient_identity UNIQUE (id, patient_id), 
	FOREIGN KEY(institution_id) REFERENCES institutions (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id), 
	FOREIGN KEY(author_id) REFERENCES users (id), 
	FOREIGN KEY(owner_id) REFERENCES users (id)
);

CREATE INDEX ix_care_plans_patient_id ON care_plans (patient_id);

CREATE TABLE patient_permissions (
	id SERIAL NOT NULL, 
	institution_id INTEGER NOT NULL, 
	patient_id INTEGER NOT NULL, 
	membership_id INTEGER NOT NULL, 
	permission VARCHAR(40) NOT NULL, 
	approved_by_id INTEGER NOT NULL, 
	enabled BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (patient_id, membership_id, permission), 
	CHECK (permission IN ('care_plan','clinical_events','patient_concerns','diagnoses','clinical_notes','psychotherapy_notes','observations','external_practitioners','export')), 
	FOREIGN KEY(institution_id) REFERENCES institutions (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id), 
	FOREIGN KEY(membership_id) REFERENCES memberships (id), 
	FOREIGN KEY(approved_by_id) REFERENCES users (id)
);

CREATE INDEX ix_patient_permissions_patient_id ON patient_permissions (patient_id);

CREATE TABLE clinical_records (
	id SERIAL NOT NULL, 
	institution_id INTEGER NOT NULL, 
	patient_id INTEGER NOT NULL, 
	author_id INTEGER NOT NULL, 
	kind VARCHAR(40) NOT NULL, 
	content TEXT NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CHECK (kind IN ('diagnoses','clinical_notes','psychotherapy_notes')), 
	FOREIGN KEY(institution_id) REFERENCES institutions (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id), 
	FOREIGN KEY(author_id) REFERENCES users (id)
);

CREATE INDEX ix_clinical_records_patient_id ON clinical_records (patient_id);

CREATE TABLE nursing_observations (
	id SERIAL NOT NULL, 
	institution_id INTEGER NOT NULL, 
	patient_id INTEGER NOT NULL, 
	author_id INTEGER NOT NULL, 
	content TEXT NOT NULL, 
	concern_escalated BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(institution_id) REFERENCES institutions (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id), 
	FOREIGN KEY(author_id) REFERENCES users (id)
);

CREATE INDEX ix_nursing_observations_patient_id ON nursing_observations (patient_id);

CREATE TABLE external_practitioners (
	id SERIAL NOT NULL, 
	institution_id INTEGER NOT NULL, 
	patient_id INTEGER NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	registration_reference VARCHAR(120) NOT NULL, 
	email VARCHAR(254) NOT NULL, 
	phone VARCHAR(40) NOT NULL, 
	author_id INTEGER NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(institution_id) REFERENCES institutions (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id), 
	FOREIGN KEY(author_id) REFERENCES users (id)
);

CREATE INDEX ix_external_practitioners_patient_id ON external_practitioners (patient_id);

CREATE TABLE patient_preferences (
	id SERIAL NOT NULL, 
	patient_id INTEGER NOT NULL, 
	channels JSON NOT NULL, 
	communication_consent BOOLEAN NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (patient_id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id)
);

CREATE TABLE continuity_events (
	id SERIAL NOT NULL, 
	institution_id INTEGER NOT NULL, 
	patient_id INTEGER NOT NULL, 
	plan_id INTEGER NOT NULL, 
	author_id INTEGER NOT NULL, 
	owner_id INTEGER NOT NULL, 
	category VARCHAR(30) NOT NULL, 
	kind VARCHAR(40) NOT NULL, 
	source_key VARCHAR(100) NOT NULL, 
	appointment_id INTEGER, 
	reason TEXT NOT NULL, 
	definition TEXT NOT NULL, 
	due_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	state VARCHAR(20) NOT NULL, 
	PRIMARY KEY (id), 
	CHECK ((category = 'administrative' AND kind IN ('missed_appointment','unconfirmed_booking','failed_reminder','overdue_followup')) OR (category = 'patient_reported' AND kind IN ('contact_request','check_in')) OR (category = 'clinical' AND kind IN ('deterioration','lapse','relapse'))), 
	CHECK (state IN ('open','acknowledged','escalated','closed','archived')), 
	FOREIGN KEY(institution_id) REFERENCES institutions (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id), 
	FOREIGN KEY(plan_id) REFERENCES care_plans (id), 
	FOREIGN KEY(author_id) REFERENCES users (id), 
	FOREIGN KEY(owner_id) REFERENCES users (id), 
	FOREIGN KEY(appointment_id) REFERENCES appointments (id)
);

CREATE INDEX ix_continuity_events_patient_id ON continuity_events (patient_id);

CREATE UNIQUE INDEX one_live_continuity_event ON continuity_events (patient_id, kind, source_key) WHERE state NOT IN ('closed','archived');

CREATE TABLE continuity_history (
	id SERIAL NOT NULL, 
	event_id INTEGER NOT NULL, 
	actor_id INTEGER NOT NULL, 
	action VARCHAR(40) NOT NULL, 
	detail TEXT NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(event_id) REFERENCES continuity_events (id), 
	FOREIGN KEY(actor_id) REFERENCES users (id)
);

CREATE INDEX ix_continuity_history_event_id ON continuity_history (event_id);

CREATE TABLE continuity_notifications (
	id SERIAL NOT NULL, 
	event_id INTEGER NOT NULL, 
	channel VARCHAR(20) NOT NULL, 
	mode VARCHAR(20) NOT NULL, 
	body VARCHAR(250) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (event_id, channel), 
	CHECK (mode = 'sandbox'), 
	FOREIGN KEY(event_id) REFERENCES continuity_events (id)
);

REVOKE ALL ON care_plans, patient_permissions, clinical_records, nursing_observations, external_practitioners, patient_preferences, continuity_events, continuity_history, continuity_notifications FROM PUBLIC, anon, authenticated;

REVOKE ALL ON SEQUENCE care_plans_id_seq, patient_permissions_id_seq, clinical_records_id_seq, nursing_observations_id_seq, external_practitioners_id_seq, patient_preferences_id_seq, continuity_events_id_seq, continuity_history_id_seq, continuity_notifications_id_seq FROM PUBLIC, anon, authenticated;


CREATE UNIQUE INDEX IF NOT EXISTS admission_patient_identity ON admissions(id,patient_id);
CREATE UNIQUE INDEX IF NOT EXISTS care_plan_patient_identity ON care_plans(id,patient_id);


CREATE TABLE coordination_policies (
	id SERIAL NOT NULL, 
	institution_id INTEGER NOT NULL, 
	kind VARCHAR(20) NOT NULL, 
	version INTEGER NOT NULL, 
	deadline_hours INTEGER NOT NULL, 
	due_soon_days INTEGER NOT NULL, 
	instructions VARCHAR(1500) NOT NULL, 
	approved_by_id INTEGER NOT NULL, 
	approved_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (institution_id, kind, version), 
	CHECK (kind IN ('discharge','review')), 
	CHECK (deadline_hours > 0 AND due_soon_days >= 0), 
	FOREIGN KEY(institution_id) REFERENCES institutions (id), 
	FOREIGN KEY(approved_by_id) REFERENCES users (id)
);

CREATE TABLE communication_decisions (
	id SERIAL NOT NULL, 
	institution_id INTEGER NOT NULL, 
	patient_id INTEGER NOT NULL, 
	purpose VARCHAR(30) NOT NULL, 
	channel VARCHAR(20) NOT NULL, 
	scope VARCHAR(200) NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	destination VARCHAR(254) NOT NULL, 
	verified_at TIMESTAMP WITHOUT TIME ZONE, 
	verified_by_id INTEGER, 
	contact_start TIME WITHOUT TIME ZONE, 
	contact_end TIME WITHOUT TIME ZONE, 
	timezone VARCHAR(80) NOT NULL, 
	method VARCHAR(80) NOT NULL, 
	notice_version VARCHAR(120) NOT NULL, 
	recorded_by_id INTEGER NOT NULL, 
	recorded_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CHECK (purpose IN ('reminders','administrative_contact','referral_sharing','care_plan_sharing')), 
	CHECK (channel IN ('portal','phone','email','sms')), 
	CHECK (status IN ('granted','declined','withdrawn')), 
	FOREIGN KEY(institution_id) REFERENCES institutions (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id), 
	FOREIGN KEY(verified_by_id) REFERENCES users (id), 
	FOREIGN KEY(recorded_by_id) REFERENCES users (id)
);

CREATE INDEX communication_decision_lookup ON communication_decisions (institution_id, patient_id, purpose, channel, id);

CREATE TABLE discharge_followups (
	id SERIAL NOT NULL, 
	institution_id INTEGER NOT NULL, 
	patient_id INTEGER NOT NULL, 
	admission_id INTEGER NOT NULL, 
	owner_id INTEGER, 
	cover_id INTEGER, 
	team VARCHAR(120) NOT NULL, 
	due_at TIMESTAMP WITHOUT TIME ZONE, 
	policy_id INTEGER, 
	planning_complete BOOLEAN NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	outcome VARCHAR(1500) NOT NULL, 
	closure_reason VARCHAR(1000) NOT NULL, 
	escalated BOOLEAN NOT NULL, 
	owner_unavailable BOOLEAN NOT NULL, 
	patient_visible BOOLEAN NOT NULL, 
	agreed_action VARCHAR(1000) NOT NULL, 
	version INTEGER NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (admission_id), 
	CONSTRAINT discharge_episode_patient_match FOREIGN KEY(admission_id, patient_id) REFERENCES admissions (id, patient_id), 
	CHECK (status IN ('open','contacted','completed','cancelled')), 
	CHECK (NOT planning_complete OR (owner_id IS NOT NULL AND due_at IS NOT NULL AND policy_id IS NOT NULL)), 
	CHECK (status <> 'completed' OR (outcome <> '' AND closure_reason <> '')), 
	FOREIGN KEY(institution_id) REFERENCES institutions (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id), 
	FOREIGN KEY(admission_id) REFERENCES admissions (id), 
	FOREIGN KEY(owner_id) REFERENCES users (id), 
	FOREIGN KEY(cover_id) REFERENCES users (id), 
	FOREIGN KEY(policy_id) REFERENCES coordination_policies (id)
);

CREATE INDEX ix_discharge_followups_patient_id ON discharge_followups (patient_id);

CREATE TABLE care_referrals (
	id SERIAL NOT NULL, 
	institution_id INTEGER NOT NULL, 
	patient_id INTEGER NOT NULL, 
	direction VARCHAR(20) NOT NULL, 
	other_party VARCHAR(200) NOT NULL, 
	practitioner_id INTEGER, 
	referred_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	owner_id INTEGER, 
	cover_id INTEGER, 
	due_at TIMESTAMP WITHOUT TIME ZONE, 
	requested_action VARCHAR(1500) NOT NULL, 
	next_action VARCHAR(1000) NOT NULL, 
	outstanding_information VARCHAR(1000) NOT NULL, 
	consent_id INTEGER, 
	status VARCHAR(30) NOT NULL, 
	response_at TIMESTAMP WITHOUT TIME ZONE, 
	appointment_at TIMESTAMP WITHOUT TIME ZONE, 
	appointment_id INTEGER, 
	completed_at TIMESTAMP WITHOUT TIME ZONE, 
	closure_reason VARCHAR(1000) NOT NULL, 
	owner_unavailable BOOLEAN NOT NULL, 
	escalated BOOLEAN NOT NULL, 
	patient_visible BOOLEAN NOT NULL, 
	submission_key VARCHAR(64) NOT NULL, 
	version INTEGER NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (institution_id, patient_id, submission_key), 
	CHECK (direction IN ('incoming','outgoing')), 
	CHECK (status IN ('draft','sent','acknowledged','accepted','appointment_arranged','completed','declined','cancelled')), 
	FOREIGN KEY(institution_id) REFERENCES institutions (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id), 
	FOREIGN KEY(practitioner_id) REFERENCES external_practitioners (id), 
	FOREIGN KEY(owner_id) REFERENCES users (id), 
	FOREIGN KEY(cover_id) REFERENCES users (id), 
	FOREIGN KEY(consent_id) REFERENCES communication_decisions (id), 
	FOREIGN KEY(appointment_id) REFERENCES appointments (id)
);

CREATE INDEX ix_care_referrals_patient_id ON care_referrals (patient_id);

CREATE TABLE referral_clinical_records (
	id SERIAL NOT NULL, 
	referral_id INTEGER NOT NULL, 
	author_id INTEGER NOT NULL, 
	content TEXT NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(referral_id) REFERENCES care_referrals (id), 
	FOREIGN KEY(author_id) REFERENCES users (id)
);

CREATE INDEX ix_referral_clinical_records_referral_id ON referral_clinical_records (referral_id);

CREATE TABLE care_plan_reviews (
	id SERIAL NOT NULL, 
	institution_id INTEGER NOT NULL, 
	patient_id INTEGER NOT NULL, 
	plan_id INTEGER NOT NULL, 
	sequence INTEGER NOT NULL, 
	owner_id INTEGER, 
	cover_id INTEGER, 
	due_at TIMESTAMP WITHOUT TIME ZONE, 
	interval_days INTEGER, 
	policy_id INTEGER, 
	status VARCHAR(20) NOT NULL, 
	reviewed_at TIMESTAMP WITHOUT TIME ZONE, 
	reviewer_id INTEGER, 
	next_review_at TIMESTAMP WITHOUT TIME ZONE, 
	escalated BOOLEAN NOT NULL, 
	owner_unavailable BOOLEAN NOT NULL, 
	version INTEGER NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (plan_id, sequence), 
	CONSTRAINT review_plan_patient_match FOREIGN KEY(plan_id, patient_id) REFERENCES care_plans (id, patient_id), 
	CHECK (status IN ('pending','completed','superseded','cancelled')), 
	FOREIGN KEY(institution_id) REFERENCES institutions (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id), 
	FOREIGN KEY(plan_id) REFERENCES care_plans (id), 
	FOREIGN KEY(owner_id) REFERENCES users (id), 
	FOREIGN KEY(cover_id) REFERENCES users (id), 
	FOREIGN KEY(policy_id) REFERENCES coordination_policies (id), 
	FOREIGN KEY(reviewer_id) REFERENCES users (id)
);

CREATE INDEX ix_care_plan_reviews_patient_id ON care_plan_reviews (patient_id);

CREATE UNIQUE INDEX one_pending_care_review ON care_plan_reviews (plan_id) WHERE status = 'pending';

CREATE TABLE care_review_signoffs (
	id SERIAL NOT NULL, 
	review_id INTEGER NOT NULL, 
	outcome TEXT NOT NULL, 
	reviewer_id INTEGER NOT NULL, 
	reviewed_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (review_id), 
	FOREIGN KEY(review_id) REFERENCES care_plan_reviews (id), 
	FOREIGN KEY(reviewer_id) REFERENCES users (id)
);

CREATE TABLE coordination_history (
	id SERIAL NOT NULL, 
	institution_id INTEGER NOT NULL, 
	source_type VARCHAR(30) NOT NULL, 
	source_id INTEGER NOT NULL, 
	actor_id INTEGER NOT NULL, 
	action VARCHAR(40) NOT NULL, 
	previous_owner_id INTEGER, 
	owner_id INTEGER, 
	previous_cover_id INTEGER, 
	cover_id INTEGER, 
	outcome_code VARCHAR(50) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(institution_id) REFERENCES institutions (id), 
	FOREIGN KEY(actor_id) REFERENCES users (id), 
	FOREIGN KEY(previous_owner_id) REFERENCES users (id), 
	FOREIGN KEY(owner_id) REFERENCES users (id), 
	FOREIGN KEY(previous_cover_id) REFERENCES users (id), 
	FOREIGN KEY(cover_id) REFERENCES users (id)
);

ALTER TABLE continuity_notifications ADD COLUMN purpose varchar(30) NOT NULL DEFAULT 'administrative_contact';
ALTER TABLE continuity_notifications ADD COLUMN scope varchar(200) NOT NULL DEFAULT 'practice';
-- Historical previews have no purpose-specific consent evidence. Keep history, suppress any delivery eligibility.
ALTER TABLE continuity_notifications ADD COLUMN state varchar(20) NOT NULL DEFAULT 'suppressed';
ALTER TABLE continuity_notifications ALTER COLUMN state SET DEFAULT 'queued';
ALTER TABLE continuity_notifications ADD COLUMN result_code varchar(80) NOT NULL DEFAULT 'legacy_consent_unverified';
ALTER TABLE continuity_notifications ALTER COLUMN result_code SET DEFAULT '';
ALTER TABLE continuity_notifications ADD COLUMN decision_id integer REFERENCES communication_decisions(id);
ALTER TABLE IF EXISTS attendance_followups ADD COLUMN IF NOT EXISTS owner_id integer REFERENCES users(id);
ALTER TABLE IF EXISTS attendance_followups ADD COLUMN IF NOT EXISTS cover_id integer REFERENCES users(id);
ALTER TABLE IF EXISTS attendance_followups ADD COLUMN IF NOT EXISTS due_at timestamp without time zone;
ALTER TABLE IF EXISTS attendance_followups ADD COLUMN IF NOT EXISTS escalated boolean NOT NULL DEFAULT false;


REVOKE ALL ON coordination_policies, communication_decisions, discharge_followups, care_referrals, referral_clinical_records, care_plan_reviews, care_review_signoffs, coordination_history FROM PUBLIC, anon, authenticated;

REVOKE ALL ON SEQUENCE coordination_policies_id_seq, communication_decisions_id_seq, discharge_followups_id_seq, care_referrals_id_seq, referral_clinical_records_id_seq, care_plan_reviews_id_seq, care_review_signoffs_id_seq, coordination_history_id_seq FROM PUBLIC, anon, authenticated;

CREATE TABLE coordination_coverage (
	id SERIAL NOT NULL, 
	institution_id INTEGER NOT NULL, 
	patient_id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	kind VARCHAR(20) NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	valid_until TIMESTAMP WITHOUT TIME ZONE, 
	approved_by_id INTEGER NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CHECK (kind IN ('discharge','referral','review')), 
	CHECK (status IN ('granted','withdrawn')), 
	CHECK (status <> 'granted' OR valid_until IS NOT NULL), 
	FOREIGN KEY(institution_id) REFERENCES institutions (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id), 
	FOREIGN KEY(user_id) REFERENCES users (id), 
	FOREIGN KEY(approved_by_id) REFERENCES users (id)
);
CREATE INDEX coordination_coverage_lookup ON coordination_coverage (institution_id, patient_id, user_id, kind, id);
REVOKE ALL ON coordination_coverage FROM PUBLIC, anon, authenticated;
REVOKE ALL ON SEQUENCE coordination_coverage_id_seq FROM PUBLIC, anon, authenticated;

-- Outbox guard functions/triggers are appended below before the version is committed.
-- Included verbatim in migration 008. No external delivery or new outbox is introduced.
CREATE FUNCTION ramosolo.coordination_guard_outbox() RETURNS trigger
LANGUAGE plpgsql SET search_path = ramosolo, pg_catalog AS $$
DECLARE patient_identity integer; decision communication_decisions%ROWTYPE; local_clock time;
BEGIN
 SELECT patient_id INTO patient_identity FROM appointments
  WHERE id=NEW.appointment_id AND institution_id=NEW.institution_id;
 IF patient_identity IS NULL OR NEW.channel <> 'in_app' THEN RETURN NEW; END IF;
 SELECT * INTO decision FROM communication_decisions
  WHERE institution_id=NEW.institution_id AND patient_id=patient_identity
    AND purpose='reminders' AND channel='portal' AND scope IN ('practice','*')
  ORDER BY id DESC LIMIT 1;
 IF NOT FOUND THEN RETURN NEW; END IF; -- existing explicit legacy reminder consent remains authoritative
 IF decision.status <> 'granted' OR decision.verified_at IS NULL OR decision.destination='' THEN
  IF NEW.state='sent' THEN RAISE EXCEPTION 'Optional reminder consent or destination no longer permits delivery' USING ERRCODE='23514'; END IF;
  IF NEW.state IN ('pending','failed') THEN
   NEW.state='cancelled'; NEW.sent_at=NULL; NEW.invalidated_at=timezone('UTC',now());
   NEW.result_code='coordination_consent_or_destination_changed';
  END IF;
 ELSIF NEW.state='sent' AND decision.contact_start IS NOT NULL AND decision.contact_end IS NOT NULL THEN
  local_clock=(now() AT TIME ZONE decision.timezone)::time;
  IF (decision.contact_start<=decision.contact_end AND NOT (local_clock BETWEEN decision.contact_start AND decision.contact_end))
    OR (decision.contact_start>decision.contact_end AND NOT (local_clock>=decision.contact_start OR local_clock<=decision.contact_end)) THEN
   RAISE EXCEPTION 'Optional reminder outside agreed contact window' USING ERRCODE='23514';
  END IF;
 END IF;
 RETURN NEW;
END $$;

CREATE FUNCTION ramosolo.coordination_suppress_withdrawn() RETURNS trigger
LANGUAGE plpgsql SET search_path = ramosolo, pg_catalog AS $$
BEGIN
 IF NEW.purpose='reminders' AND NEW.channel='portal' AND NEW.scope IN ('practice','*')
   AND (NEW.status <> 'granted' OR NEW.verified_at IS NULL OR NEW.destination='') THEN
  IF to_regclass('ramosolo.communication_preferences') IS NOT NULL THEN
   UPDATE communication_preferences SET in_app_enabled=false,version=version+1,
     changed_at=timezone('UTC',now()),changed_by=NEW.recorded_by_id
    WHERE institution_id=NEW.institution_id AND patient_id=NEW.patient_id AND in_app_enabled;
  END IF;
  IF to_regclass('ramosolo.notification_outbox') IS NOT NULL THEN
   WITH affected AS (
    UPDATE notification_outbox o SET state='cancelled',invalidated_at=timezone('UTC',now()),
      result_code='coordination_consent_or_destination_changed'
    WHERE o.institution_id=NEW.institution_id AND o.state IN ('pending','failed') AND o.sent_at IS NULL
      AND o.appointment_id IN (SELECT id FROM appointments WHERE patient_id=NEW.patient_id AND institution_id=NEW.institution_id)
    RETURNING o.id
   ) INSERT INTO audit_events(institution_id,actor_id,action,resource_type,resource_id,created_at)
     SELECT NEW.institution_id,NEW.recorded_by_id,'suppress_optional_notice','notification_outbox',id,timezone('UTC',now()) FROM affected;
  END IF;
 END IF;
 RETURN NEW;
END $$;

DO $$ BEGIN
 IF to_regclass('ramosolo.notification_outbox') IS NOT NULL THEN
  CREATE TRIGGER coordination_outbox_permission_guard BEFORE INSERT OR UPDATE ON ramosolo.notification_outbox
    FOR EACH ROW EXECUTE FUNCTION ramosolo.coordination_guard_outbox();
 END IF;
END $$;
CREATE TRIGGER coordination_consent_withdrawal AFTER INSERT ON ramosolo.communication_decisions
 FOR EACH ROW EXECUTE FUNCTION ramosolo.coordination_suppress_withdrawn();
REVOKE ALL ON FUNCTION ramosolo.coordination_guard_outbox(), ramosolo.coordination_suppress_withdrawn() FROM PUBLIC, anon, authenticated;


CREATE TABLE IF NOT EXISTS calendar_delegations (
	id SERIAL NOT NULL, 
	institution_id INTEGER NOT NULL, 
	doctor_id INTEGER NOT NULL, 
	assistant_id INTEGER NOT NULL, 
	enabled BOOLEAN NOT NULL, 
	expires_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (institution_id, doctor_id, assistant_id), 
	FOREIGN KEY(institution_id) REFERENCES institutions (id), 
	FOREIGN KEY(doctor_id) REFERENCES users (id), 
	FOREIGN KEY(assistant_id) REFERENCES users (id)
)

;
ALTER TABLE calendar_delegations ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON calendar_delegations FROM PUBLIC, anon, authenticated;
REVOKE ALL ON SEQUENCE calendar_delegations_id_seq FROM PUBLIC, anon, authenticated;

CREATE TABLE IF NOT EXISTS appointment_proposals (
	id SERIAL NOT NULL, 
	institution_id INTEGER NOT NULL, 
	appointment_id INTEGER NOT NULL, 
	actor_id INTEGER NOT NULL, 
	base_version INTEGER NOT NULL, 
	original_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	proposed_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	reason VARCHAR(240) NOT NULL, 
	state VARCHAR(20) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	expires_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	responded_at TIMESTAMP WITHOUT TIME ZONE, 
	token_digest VARCHAR(64) NOT NULL, 
	code_digest VARCHAR(64) NOT NULL, 
	communication_decision_id INTEGER, 
	verification_attempts INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CHECK (state IN ('pending','accepted','declined','expired','superseded')), 
	FOREIGN KEY(institution_id) REFERENCES institutions (id), 
	FOREIGN KEY(appointment_id) REFERENCES appointments (id), 
	FOREIGN KEY(actor_id) REFERENCES users (id), 
	UNIQUE (token_digest), 
	FOREIGN KEY(communication_decision_id) REFERENCES communication_decisions (id)
)

;
CREATE UNIQUE INDEX IF NOT EXISTS one_pending_appointment_proposal ON appointment_proposals (appointment_id) WHERE state='pending';
ALTER TABLE appointment_proposals ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON appointment_proposals FROM PUBLIC, anon, authenticated;
REVOKE ALL ON SEQUENCE appointment_proposals_id_seq FROM PUBLIC, anon, authenticated;

CREATE TABLE IF NOT EXISTS calendar_history (
	id SERIAL NOT NULL, 
	institution_id INTEGER NOT NULL, 
	appointment_id INTEGER, 
	block_id INTEGER, 
	proposal_id INTEGER, 
	actor_id INTEGER, 
	action VARCHAR(40) NOT NULL, 
	original_at TIMESTAMP WITHOUT TIME ZONE, 
	new_at TIMESTAMP WITHOUT TIME ZONE, 
	reason VARCHAR(240) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(institution_id) REFERENCES institutions (id), 
	FOREIGN KEY(appointment_id) REFERENCES appointments (id), 
	FOREIGN KEY(block_id) REFERENCES calendar_blocks (id), 
	FOREIGN KEY(proposal_id) REFERENCES appointment_proposals (id), 
	FOREIGN KEY(actor_id) REFERENCES users (id)
)

;
ALTER TABLE calendar_history ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON calendar_history FROM PUBLIC, anon, authenticated;
REVOKE ALL ON SEQUENCE calendar_history_id_seq FROM PUBLIC, anon, authenticated;

DO $postcondition$ DECLARE original_search_path text; BEGIN
 IF (SELECT count(*) FROM information_schema.tables WHERE table_schema='ramosolo' AND table_type='BASE TABLE' AND table_name = ANY(ARRAY['appointment_proposals','calendar_delegations','calendar_history','care_plan_reviews','care_plans','care_referrals','care_review_signoffs','clinical_records','communication_decisions','continuity_events','continuity_history','continuity_notifications','coordination_coverage','coordination_history','coordination_policies','discharge_followups','external_practitioners','nursing_observations','patient_permissions','patient_preferences','referral_clinical_records']::text[])) <> 21 THEN RAISE EXCEPTION 'Target table postcondition failed'; END IF;
 IF EXISTS (SELECT 1 FROM (VALUES ('admissions','admitted_at'),('admissions','discharged_at'),('admissions','facility'),('admissions','id'),('admissions','patient_id'),('appointment_proposals','actor_id'),('appointment_proposals','appointment_id'),('appointment_proposals','base_version'),('appointment_proposals','code_digest'),('appointment_proposals','communication_decision_id'),('appointment_proposals','created_at'),('appointment_proposals','expires_at'),('appointment_proposals','id'),('appointment_proposals','institution_id'),('appointment_proposals','original_at'),('appointment_proposals','proposed_at'),('appointment_proposals','reason'),('appointment_proposals','responded_at'),('appointment_proposals','state'),('appointment_proposals','token_digest'),('appointment_proposals','verification_attempts'),('appointments','care_type'),('appointments','doctor_id'),('appointments','ends_at'),('appointments','hold_expires_at'),('appointments','id'),('appointments','institution_id'),('appointments','occupied_until'),('appointments','patient_id'),('appointments','schedule_version'),('appointments','service'),('appointments','starts_at'),('appointments','status'),('appointments','visit_kind'),('audit_events','action'),('audit_events','actor_id'),('audit_events','created_at'),('audit_events','id'),('audit_events','institution_id'),('audit_events','resource_id'),('audit_events','resource_type'),('availability_exceptions','approved_at'),('availability_exceptions','approved_by'),('availability_exceptions','assessment_minutes'),('availability_exceptions','break_minutes'),('availability_exceptions','care_type'),('availability_exceptions','closes_at'),('availability_exceptions','day'),('availability_exceptions','duration_minutes'),('availability_exceptions','first_minutes'),('availability_exceptions','id'),('availability_exceptions','kind'),('availability_exceptions','opens_at'),('availability_exceptions','override_closure'),('availability_exceptions','policy_id'),('availability_exceptions','reason'),('availability_policies','daily_limit'),('availability_policies','doctor_id'),('availability_policies','enabled'),('availability_policies','hold_minutes'),('availability_policies','holidays_confirmed'),('availability_policies','horizon_days'),('availability_policies','id'),('availability_policies','institution_id'),('availability_sessions','assessment_minutes'),('availability_sessions','break_minutes'),('availability_sessions','care_type'),('availability_sessions','closes_at'),('availability_sessions','duration_minutes'),('availability_sessions','first_minutes'),('availability_sessions','id'),('availability_sessions','opens_at'),('availability_sessions','policy_id'),('availability_sessions','weekday'),('booking_requests','consent_at'),('booking_requests','email'),('booking_requests','id'),('booking_requests','institution_id'),('booking_requests','name'),('booking_requests','phone'),('booking_requests','preferred_at'),('booking_requests','service'),('booking_requests','status'),('calendar_blocks','created_at'),('calendar_blocks','created_by'),('calendar_blocks','doctor_id'),('calendar_blocks','enabled'),('calendar_blocks','ends_at'),('calendar_blocks','id'),('calendar_blocks','institution_id'),('calendar_blocks','reason'),('calendar_blocks','released_at'),('calendar_blocks','released_by'),('calendar_blocks','starts_at'),('calendar_delegations','assistant_id'),('calendar_delegations','doctor_id'),('calendar_delegations','enabled'),('calendar_delegations','expires_at'),('calendar_delegations','id'),('calendar_delegations','institution_id'),('calendar_history','action'),('calendar_history','actor_id'),('calendar_history','appointment_id'),('calendar_history','block_id'),('calendar_history','created_at'),('calendar_history','id'),('calendar_history','institution_id'),('calendar_history','new_at'),('calendar_history','original_at'),('calendar_history','proposal_id'),('calendar_history','reason'),('care_assignments','id'),('care_assignments','nurse_id'),('care_assignments','patient_id'),('care_plan_reviews','cover_id'),('care_plan_reviews','due_at'),('care_plan_reviews','escalated'),('care_plan_reviews','id'),('care_plan_reviews','institution_id'),('care_plan_reviews','interval_days'),('care_plan_reviews','next_review_at'),('care_plan_reviews','owner_id'),('care_plan_reviews','owner_unavailable'),('care_plan_reviews','patient_id'),('care_plan_reviews','plan_id'),('care_plan_reviews','policy_id'),('care_plan_reviews','reviewed_at'),('care_plan_reviews','reviewer_id'),('care_plan_reviews','sequence'),('care_plan_reviews','status'),('care_plan_reviews','updated_at'),('care_plan_reviews','version'),('care_plans','agreed_at'),('care_plans','author_id'),('care_plans','channels'),('care_plans','clinical_definitions'),('care_plans','communication_consent'),('care_plans','created_at'),('care_plans','goals'),('care_plans','id'),('care_plans','institution_id'),('care_plans','monitoring_hours'),('care_plans','owner_id'),('care_plans','patient_id'),('care_plans','patient_visible'),('care_plans','planned_appointments'),('care_plans','response_steps'),('care_plans','review_at'),('care_plans','rules'),('care_plans','urgent_help'),('care_plans','warning_signs'),('care_referrals','appointment_at'),('care_referrals','appointment_id'),('care_referrals','closure_reason'),('care_referrals','completed_at'),('care_referrals','consent_id'),('care_referrals','cover_id'),('care_referrals','direction'),('care_referrals','due_at'),('care_referrals','escalated'),('care_referrals','id'),('care_referrals','institution_id'),('care_referrals','next_action'),('care_referrals','other_party'),('care_referrals','outstanding_information'),('care_referrals','owner_id'),('care_referrals','owner_unavailable'),('care_referrals','patient_id'),('care_referrals','patient_visible'),('care_referrals','practitioner_id'),('care_referrals','referred_at'),('care_referrals','requested_action'),('care_referrals','response_at'),('care_referrals','status'),('care_referrals','submission_key'),('care_referrals','updated_at'),('care_referrals','version'),('care_review_signoffs','id'),('care_review_signoffs','outcome'),('care_review_signoffs','review_id'),('care_review_signoffs','reviewed_at'),('care_review_signoffs','reviewer_id'),('clinical_records','author_id'),('clinical_records','content'),('clinical_records','created_at'),('clinical_records','id'),('clinical_records','institution_id'),('clinical_records','kind'),('clinical_records','patient_id'),('communication_decisions','channel'),('communication_decisions','contact_end'),('communication_decisions','contact_start'),('communication_decisions','destination'),('communication_decisions','id'),('communication_decisions','institution_id'),('communication_decisions','method'),('communication_decisions','notice_version'),('communication_decisions','patient_id'),('communication_decisions','purpose'),('communication_decisions','recorded_at'),('communication_decisions','recorded_by_id'),('communication_decisions','scope'),('communication_decisions','status'),('communication_decisions','timezone'),('communication_decisions','verified_at'),('communication_decisions','verified_by_id'),('continuity_events','appointment_id'),('continuity_events','author_id'),('continuity_events','category'),('continuity_events','created_at'),('continuity_events','definition'),('continuity_events','due_at'),('continuity_events','id'),('continuity_events','institution_id'),('continuity_events','kind'),('continuity_events','owner_id'),('continuity_events','patient_id'),('continuity_events','plan_id'),('continuity_events','reason'),('continuity_events','source_key'),('continuity_events','state'),('continuity_history','action'),('continuity_history','actor_id'),('continuity_history','created_at'),('continuity_history','detail'),('continuity_history','event_id'),('continuity_history','id'),('continuity_notifications','body'),('continuity_notifications','channel'),('continuity_notifications','created_at'),('continuity_notifications','decision_id'),('continuity_notifications','event_id'),('continuity_notifications','id'),('continuity_notifications','mode'),('continuity_notifications','purpose'),('continuity_notifications','result_code'),('continuity_notifications','scope'),('continuity_notifications','state'),('coordination_coverage','approved_by_id'),('coordination_coverage','created_at'),('coordination_coverage','id'),('coordination_coverage','institution_id'),('coordination_coverage','kind'),('coordination_coverage','patient_id'),('coordination_coverage','status'),('coordination_coverage','user_id'),('coordination_coverage','valid_until'),('coordination_history','action'),('coordination_history','actor_id'),('coordination_history','cover_id'),('coordination_history','created_at'),('coordination_history','id'),('coordination_history','institution_id'),('coordination_history','outcome_code'),('coordination_history','owner_id'),('coordination_history','previous_cover_id'),('coordination_history','previous_owner_id'),('coordination_history','source_id'),('coordination_history','source_type'),('coordination_policies','approved_at'),('coordination_policies','approved_by_id'),('coordination_policies','deadline_hours'),('coordination_policies','due_soon_days'),('coordination_policies','id'),('coordination_policies','institution_id'),('coordination_policies','instructions'),('coordination_policies','kind'),('coordination_policies','version'),('discharge_followups','admission_id'),('discharge_followups','agreed_action'),('discharge_followups','closure_reason'),('discharge_followups','cover_id'),('discharge_followups','due_at'),('discharge_followups','escalated'),('discharge_followups','id'),('discharge_followups','institution_id'),('discharge_followups','outcome'),('discharge_followups','owner_id'),('discharge_followups','owner_unavailable'),('discharge_followups','patient_id'),('discharge_followups','patient_visible'),('discharge_followups','planning_complete'),('discharge_followups','policy_id'),('discharge_followups','status'),('discharge_followups','team'),('discharge_followups','updated_at'),('discharge_followups','version'),('external_practitioners','author_id'),('external_practitioners','created_at'),('external_practitioners','email'),('external_practitioners','id'),('external_practitioners','institution_id'),('external_practitioners','name'),('external_practitioners','patient_id'),('external_practitioners','phone'),('external_practitioners','registration_reference'),('institutions','address'),('institutions','id'),('institutions','kind'),('institutions','name'),('memberships','enabled'),('memberships','id'),('memberships','institution_id'),('memberships','role'),('memberships','supervising_doctor_id'),('memberships','user_id'),('nursing_observations','author_id'),('nursing_observations','concern_escalated'),('nursing_observations','content'),('nursing_observations','created_at'),('nursing_observations','id'),('nursing_observations','institution_id'),('nursing_observations','patient_id'),('patient_permissions','approved_by_id'),('patient_permissions','created_at'),('patient_permissions','enabled'),('patient_permissions','id'),('patient_permissions','institution_id'),('patient_permissions','membership_id'),('patient_permissions','patient_id'),('patient_permissions','permission'),('patient_preferences','channels'),('patient_preferences','communication_consent'),('patient_preferences','id'),('patient_preferences','patient_id'),('patient_preferences','updated_at'),('patients','doctor_id'),('patients','email'),('patients','id'),('patients','institution_id'),('patients','name'),('patients','phone'),('patients','user_id'),('public_holidays','day'),('public_holidays','id'),('public_holidays','institution_id'),('public_holidays','label'),('referral_clinical_records','author_id'),('referral_clinical_records','content'),('referral_clinical_records','created_at'),('referral_clinical_records','id'),('referral_clinical_records','referral_id'),('users','email'),('users','enabled'),('users','failed_logins'),('users','id'),('users','locked_until'),('users','name'),('users','password_hash'),('users','session_version')) AS required(table_name,column_name) LEFT JOIN information_schema.columns c ON c.table_schema='ramosolo' AND c.table_name=required.table_name AND c.column_name=required.column_name WHERE c.column_name IS NULL) THEN RAISE EXCEPTION 'ORM column postcondition failed'; END IF;
 IF (SELECT count(*) FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='ramosolo' AND NOT t.tgisinternal) <> 34 THEN RAISE EXCEPTION 'Trigger inventory postcondition failed'; END IF;
 IF (SELECT indexdef FROM pg_indexes WHERE schemaname='ramosolo' AND indexname='admission_patient_identity') IS DISTINCT FROM 'CREATE UNIQUE INDEX admission_patient_identity ON ramosolo.admissions USING btree (id, patient_id)' THEN RAISE EXCEPTION 'admission_patient_identity postcondition failed'; END IF;
 IF NOT (SELECT relrowsecurity FROM pg_class WHERE oid='ramosolo.appointment_proposals'::regclass) OR NOT (SELECT relrowsecurity FROM pg_class WHERE oid='ramosolo.calendar_history'::regclass) OR NOT (SELECT relrowsecurity FROM pg_class WHERE oid='ramosolo.calendar_delegations'::regclass) THEN RAISE EXCEPTION 'Calendar RLS postcondition failed'; END IF;
 IF (SELECT array_agg(version ORDER BY version) FROM ramosolo.schema_versions) IS DISTINCT FROM ARRAY[1,2,3,4,5,6] THEN RAISE EXCEPTION 'Ledger changed before all postconditions'; END IF;
 IF (SELECT md5(p.prosrc) FROM pg_proc p WHERE p.pronamespace='ramosolo'::regnamespace AND p.proname='coordination_guard_outbox') IS DISTINCT FROM 'd109ea126eba57ae68b6a1fdd20f70bd' THEN RAISE EXCEPTION 'New routine postcondition failed: coordination_guard_outbox'; END IF;
 IF (SELECT md5(p.prosrc) FROM pg_proc p WHERE p.pronamespace='ramosolo'::regnamespace AND p.proname='coordination_suppress_withdrawn') IS DISTINCT FROM '97a6b1bf98549c9a9d9cea49b6a91af9' THEN RAISE EXCEPTION 'New routine postcondition failed: coordination_suppress_withdrawn'; END IF;
 IF (SELECT count(*) FROM pg_trigger t JOIN pg_proc p ON p.oid=t.tgfoid WHERE (t.tgrelid='ramosolo.notification_outbox'::regclass AND t.tgname='coordination_outbox_permission_guard' AND p.proname='coordination_guard_outbox' AND t.tgtype=23 AND t.tgenabled='O') OR (t.tgrelid='ramosolo.communication_decisions'::regclass AND t.tgname='coordination_consent_withdrawal' AND p.proname='coordination_suppress_withdrawn' AND t.tgtype=5 AND t.tgenabled='O')) <> 2 THEN RAISE EXCEPTION 'Coordination trigger postcondition failed'; END IF;
 original_search_path := current_setting('search_path');
 PERFORM set_config('search_path','public',true);
 IF (SELECT md5(p.prosrc) FROM pg_proc p WHERE p.pronamespace='ramosolo'::regnamespace AND p.proname='appointment_attendance_event') IS DISTINCT FROM '9e91e5561f2cdafaeafb8a91bcbcf484' THEN RAISE EXCEPTION 'Existing routine changed during reconciliation: appointment_attendance_event'; END IF;
 IF (SELECT md5(p.prosrc) FROM pg_proc p WHERE p.pronamespace='ramosolo'::regnamespace AND p.proname='booking_appointment_guard') IS DISTINCT FROM 'd9713aa1040af31189bb0e30e3115248' THEN RAISE EXCEPTION 'Existing routine changed during reconciliation: booking_appointment_guard'; END IF;
 IF (SELECT md5(p.prosrc) FROM pg_proc p WHERE p.pronamespace='ramosolo'::regnamespace AND p.proname='booking_config_guard') IS DISTINCT FROM 'cd1ddad5ffab5ee73012a534ca9eebed' THEN RAISE EXCEPTION 'Existing routine changed during reconciliation: booking_config_guard'; END IF;
 IF (SELECT md5(p.prosrc) FROM pg_proc p WHERE p.pronamespace='ramosolo'::regnamespace AND p.proname='booking_exception_audit') IS DISTINCT FROM '1a809621f31768c27022f14f1be4da69' THEN RAISE EXCEPTION 'Existing routine changed during reconciliation: booking_exception_audit'; END IF;
 IF (SELECT md5(p.prosrc) FROM pg_proc p WHERE p.pronamespace='ramosolo'::regnamespace AND p.proname='calendar_appointment_metadata') IS DISTINCT FROM '8c7fa0f0431fbbcf41223cae5ea61d6c' THEN RAISE EXCEPTION 'Existing routine changed during reconciliation: calendar_appointment_metadata'; END IF;
 IF (SELECT md5(p.prosrc) FROM pg_proc p WHERE p.pronamespace='ramosolo'::regnamespace AND p.proname='calendar_block_guard') IS DISTINCT FROM 'd349b9ab86c3429f53e439aa409d035e' THEN RAISE EXCEPTION 'Existing routine changed during reconciliation: calendar_block_guard'; END IF;
 IF (SELECT md5(p.prosrc) FROM pg_proc p WHERE p.pronamespace='ramosolo'::regnamespace AND p.proname='financial_audit') IS DISTINCT FROM '6e2394f201f09e24e250fe95d501b985' THEN RAISE EXCEPTION 'Existing routine changed during reconciliation: financial_audit'; END IF;
 IF (SELECT md5(p.prosrc) FROM pg_proc p WHERE p.pronamespace='ramosolo'::regnamespace AND p.proname='followup_actor_allowed') IS DISTINCT FROM '01c75ddc7bc63863c8db293884a0d2d5' THEN RAISE EXCEPTION 'Existing routine changed during reconciliation: followup_actor_allowed'; END IF;
 IF (SELECT md5(p.prosrc) FROM pg_proc p WHERE p.pronamespace='ramosolo'::regnamespace AND p.proname='followup_guard') IS DISTINCT FROM 'd70963d85293a7ac5b6d2b39aedb87f9' THEN RAISE EXCEPTION 'Existing routine changed during reconciliation: followup_guard'; END IF;
 IF (SELECT md5(p.prosrc) FROM pg_proc p WHERE p.pronamespace='ramosolo'::regnamespace AND p.proname='invalidate_reminder_jobs') IS DISTINCT FROM '27fe0e41e15fd3acd344daf9052fd35c' THEN RAISE EXCEPTION 'Existing routine changed during reconciliation: invalidate_reminder_jobs'; END IF;
 IF (SELECT md5(p.prosrc) FROM pg_proc p WHERE p.pronamespace='ramosolo'::regnamespace AND p.proname='medical_assignment_guard') IS DISTINCT FROM 'df43c9d5a3008225990b7419aab40b86' THEN RAISE EXCEPTION 'Existing routine changed during reconciliation: medical_assignment_guard'; END IF;
 IF (SELECT md5(p.prosrc) FROM pg_proc p WHERE p.pronamespace='ramosolo'::regnamespace AND p.proname='medical_invoice_guard') IS DISTINCT FROM 'd33780a803d1a24a7d737c8d9882daf0' THEN RAISE EXCEPTION 'Existing routine changed during reconciliation: medical_invoice_guard'; END IF;
 IF (SELECT md5(p.prosrc) FROM pg_proc p WHERE p.pronamespace='ramosolo'::regnamespace AND p.proname='medical_payment_guard') IS DISTINCT FROM '2db24f785ca8a3140991480d323a991e' THEN RAISE EXCEPTION 'Existing routine changed during reconciliation: medical_payment_guard'; END IF;
 IF (SELECT md5(p.prosrc) FROM pg_proc p WHERE p.pronamespace='ramosolo'::regnamespace AND p.proname='notification_outbox_guard') IS DISTINCT FROM '9e685225c72ec43064d55d53011329bd' THEN RAISE EXCEPTION 'Existing routine changed during reconciliation: notification_outbox_guard'; END IF;
 IF (SELECT md5(p.prosrc) FROM pg_proc p WHERE p.pronamespace='ramosolo'::regnamespace AND p.proname='reminder_configuration_guard') IS DISTINCT FROM 'df4237a5ada4b48a7b9ec5f9a8ddc1ab' THEN RAISE EXCEPTION 'Existing routine changed during reconciliation: reminder_configuration_guard'; END IF;
 IF (SELECT md5(p.prosrc) FROM pg_proc p WHERE p.pronamespace='ramosolo'::regnamespace AND p.proname='reminder_delivery_guard') IS DISTINCT FROM '4ca822b50eaf738e56516208c7518203' THEN RAISE EXCEPTION 'Existing routine changed during reconciliation: reminder_delivery_guard'; END IF;
 IF (SELECT md5(p.prosrc) FROM pg_proc p WHERE p.pronamespace='ramosolo'::regnamespace AND p.proname='reminder_job_current') IS DISTINCT FROM 'f457d575e0b28d04dda55a446487660f' THEN RAISE EXCEPTION 'Existing routine changed during reconciliation: reminder_job_current'; END IF;
 IF (SELECT md5(p.prosrc) FROM pg_proc p WHERE p.pronamespace='ramosolo'::regnamespace AND p.proname='reminder_source_invalidation') IS DISTINCT FROM 'c3aeea35cb0d1d9e61af94c70edbf111' THEN RAISE EXCEPTION 'Existing routine changed during reconciliation: reminder_source_invalidation'; END IF;
 IF (SELECT md5(pg_get_triggerdef(t.oid)) FROM pg_trigger t WHERE t.tgrelid='ramosolo.appointment_attendance_events'::regclass AND t.tgname='attendance_event_guard' AND NOT t.tgisinternal) IS DISTINCT FROM '51801af62b0ae96af2ea2da8b025586a' THEN RAISE EXCEPTION 'Existing trigger changed during reconciliation: appointment_attendance_events.attendance_event_guard'; END IF;
 IF (SELECT t.tgenabled::text FROM pg_trigger t WHERE t.tgrelid='ramosolo.appointment_attendance_events'::regclass AND t.tgname='attendance_event_guard' AND NOT t.tgisinternal) IS DISTINCT FROM 'O' THEN RAISE EXCEPTION 'Existing trigger enablement changed during reconciliation: appointment_attendance_events.attendance_event_guard'; END IF;
 IF (SELECT md5(pg_get_triggerdef(t.oid)) FROM pg_trigger t WHERE t.tgrelid='ramosolo.appointment_confirmation_requests'::regclass AND t.tgname='confirmation_request_guard' AND NOT t.tgisinternal) IS DISTINCT FROM '012888ac8a5390ec7881428392ca748f' THEN RAISE EXCEPTION 'Existing trigger changed during reconciliation: appointment_confirmation_requests.confirmation_request_guard'; END IF;
 IF (SELECT t.tgenabled::text FROM pg_trigger t WHERE t.tgrelid='ramosolo.appointment_confirmation_requests'::regclass AND t.tgname='confirmation_request_guard' AND NOT t.tgisinternal) IS DISTINCT FROM 'O' THEN RAISE EXCEPTION 'Existing trigger enablement changed during reconciliation: appointment_confirmation_requests.confirmation_request_guard'; END IF;
 IF (SELECT md5(pg_get_triggerdef(t.oid)) FROM pg_trigger t WHERE t.tgrelid='ramosolo.appointments'::regclass AND t.tgname='appointment_assignment_scope' AND NOT t.tgisinternal) IS DISTINCT FROM '5e95327eb529bcfa19f7243a511140a8' THEN RAISE EXCEPTION 'Existing trigger changed during reconciliation: appointments.appointment_assignment_scope'; END IF;
 IF (SELECT t.tgenabled::text FROM pg_trigger t WHERE t.tgrelid='ramosolo.appointments'::regclass AND t.tgname='appointment_assignment_scope' AND NOT t.tgisinternal) IS DISTINCT FROM 'O' THEN RAISE EXCEPTION 'Existing trigger enablement changed during reconciliation: appointments.appointment_assignment_scope'; END IF;
 IF (SELECT md5(pg_get_triggerdef(t.oid)) FROM pg_trigger t WHERE t.tgrelid='ramosolo.appointments'::regclass AND t.tgname='appointment_attendance_history' AND NOT t.tgisinternal) IS DISTINCT FROM '5360d15de5aaa20cc0038f48d08133e6' THEN RAISE EXCEPTION 'Existing trigger changed during reconciliation: appointments.appointment_attendance_history'; END IF;
 IF (SELECT t.tgenabled::text FROM pg_trigger t WHERE t.tgrelid='ramosolo.appointments'::regclass AND t.tgname='appointment_attendance_history' AND NOT t.tgisinternal) IS DISTINCT FROM 'O' THEN RAISE EXCEPTION 'Existing trigger enablement changed during reconciliation: appointments.appointment_attendance_history'; END IF;
 IF (SELECT md5(pg_get_triggerdef(t.oid)) FROM pg_trigger t WHERE t.tgrelid='ramosolo.appointments'::regclass AND t.tgname='appointment_capacity_guard' AND NOT t.tgisinternal) IS DISTINCT FROM '12a302c5dadece5caedcc35306863bce' THEN RAISE EXCEPTION 'Existing trigger changed during reconciliation: appointments.appointment_capacity_guard'; END IF;
 IF (SELECT t.tgenabled::text FROM pg_trigger t WHERE t.tgrelid='ramosolo.appointments'::regclass AND t.tgname='appointment_capacity_guard' AND NOT t.tgisinternal) IS DISTINCT FROM 'O' THEN RAISE EXCEPTION 'Existing trigger enablement changed during reconciliation: appointments.appointment_capacity_guard'; END IF;
 IF (SELECT md5(pg_get_triggerdef(t.oid)) FROM pg_trigger t WHERE t.tgrelid='ramosolo.appointments'::regclass AND t.tgname='appointment_metadata_guard' AND NOT t.tgisinternal) IS DISTINCT FROM 'e4cb10c5b69970b86615012712dd398f' THEN RAISE EXCEPTION 'Existing trigger changed during reconciliation: appointments.appointment_metadata_guard'; END IF;
 IF (SELECT t.tgenabled::text FROM pg_trigger t WHERE t.tgrelid='ramosolo.appointments'::regclass AND t.tgname='appointment_metadata_guard' AND NOT t.tgisinternal) IS DISTINCT FROM 'O' THEN RAISE EXCEPTION 'Existing trigger enablement changed during reconciliation: appointments.appointment_metadata_guard'; END IF;
 IF (SELECT md5(pg_get_triggerdef(t.oid)) FROM pg_trigger t WHERE t.tgrelid='ramosolo.appointments'::regclass AND t.tgname='appointment_reminder_invalidation' AND NOT t.tgisinternal) IS DISTINCT FROM 'd105e40f87fa4d91dcbfb0a224ddd10b' THEN RAISE EXCEPTION 'Existing trigger changed during reconciliation: appointments.appointment_reminder_invalidation'; END IF;
 IF (SELECT t.tgenabled::text FROM pg_trigger t WHERE t.tgrelid='ramosolo.appointments'::regclass AND t.tgname='appointment_reminder_invalidation' AND NOT t.tgisinternal) IS DISTINCT FROM 'O' THEN RAISE EXCEPTION 'Existing trigger enablement changed during reconciliation: appointments.appointment_reminder_invalidation'; END IF;
 IF (SELECT md5(pg_get_triggerdef(t.oid)) FROM pg_trigger t WHERE t.tgrelid='ramosolo.attendance_followup_reviews'::regclass AND t.tgname='followup_review_guard' AND NOT t.tgisinternal) IS DISTINCT FROM 'ff8f4e1ea2cefa72f9c21919c3dd2ca7' THEN RAISE EXCEPTION 'Existing trigger changed during reconciliation: attendance_followup_reviews.followup_review_guard'; END IF;
 IF (SELECT t.tgenabled::text FROM pg_trigger t WHERE t.tgrelid='ramosolo.attendance_followup_reviews'::regclass AND t.tgname='followup_review_guard' AND NOT t.tgisinternal) IS DISTINCT FROM 'O' THEN RAISE EXCEPTION 'Existing trigger enablement changed during reconciliation: attendance_followup_reviews.followup_review_guard'; END IF;
 IF (SELECT md5(pg_get_triggerdef(t.oid)) FROM pg_trigger t WHERE t.tgrelid='ramosolo.attendance_followups'::regclass AND t.tgname='attendance_followup_guard' AND NOT t.tgisinternal) IS DISTINCT FROM '351e618dc60ac24fea159e0ff2b6af38' THEN RAISE EXCEPTION 'Existing trigger changed during reconciliation: attendance_followups.attendance_followup_guard'; END IF;
 IF (SELECT t.tgenabled::text FROM pg_trigger t WHERE t.tgrelid='ramosolo.attendance_followups'::regclass AND t.tgname='attendance_followup_guard' AND NOT t.tgisinternal) IS DISTINCT FROM 'O' THEN RAISE EXCEPTION 'Existing trigger enablement changed during reconciliation: attendance_followups.attendance_followup_guard'; END IF;
 IF (SELECT md5(pg_get_triggerdef(t.oid)) FROM pg_trigger t WHERE t.tgrelid='ramosolo.availability_exceptions'::regclass AND t.tgname='exception_audit' AND NOT t.tgisinternal) IS DISTINCT FROM '99830920711cd0aab5a8076d30dc0f01' THEN RAISE EXCEPTION 'Existing trigger changed during reconciliation: availability_exceptions.exception_audit'; END IF;
 IF (SELECT t.tgenabled::text FROM pg_trigger t WHERE t.tgrelid='ramosolo.availability_exceptions'::regclass AND t.tgname='exception_audit' AND NOT t.tgisinternal) IS DISTINCT FROM 'O' THEN RAISE EXCEPTION 'Existing trigger enablement changed during reconciliation: availability_exceptions.exception_audit'; END IF;
 IF (SELECT md5(pg_get_triggerdef(t.oid)) FROM pg_trigger t WHERE t.tgrelid='ramosolo.availability_exceptions'::regclass AND t.tgname='exception_guard' AND NOT t.tgisinternal) IS DISTINCT FROM 'd4b52244db06ed4b581c66aad232f097' THEN RAISE EXCEPTION 'Existing trigger changed during reconciliation: availability_exceptions.exception_guard'; END IF;
 IF (SELECT t.tgenabled::text FROM pg_trigger t WHERE t.tgrelid='ramosolo.availability_exceptions'::regclass AND t.tgname='exception_guard' AND NOT t.tgisinternal) IS DISTINCT FROM 'O' THEN RAISE EXCEPTION 'Existing trigger enablement changed during reconciliation: availability_exceptions.exception_guard'; END IF;
 IF (SELECT md5(pg_get_triggerdef(t.oid)) FROM pg_trigger t WHERE t.tgrelid='ramosolo.availability_policies'::regclass AND t.tgname='policy_guard' AND NOT t.tgisinternal) IS DISTINCT FROM '9d25ea68cb3339f7fc5e21b458184a68' THEN RAISE EXCEPTION 'Existing trigger changed during reconciliation: availability_policies.policy_guard'; END IF;
 IF (SELECT t.tgenabled::text FROM pg_trigger t WHERE t.tgrelid='ramosolo.availability_policies'::regclass AND t.tgname='policy_guard' AND NOT t.tgisinternal) IS DISTINCT FROM 'O' THEN RAISE EXCEPTION 'Existing trigger enablement changed during reconciliation: availability_policies.policy_guard'; END IF;
 IF (SELECT md5(pg_get_triggerdef(t.oid)) FROM pg_trigger t WHERE t.tgrelid='ramosolo.availability_sessions'::regclass AND t.tgname='session_guard' AND NOT t.tgisinternal) IS DISTINCT FROM '38f94d9d044b45b3363433bb2ead5e71' THEN RAISE EXCEPTION 'Existing trigger changed during reconciliation: availability_sessions.session_guard'; END IF;
 IF (SELECT t.tgenabled::text FROM pg_trigger t WHERE t.tgrelid='ramosolo.availability_sessions'::regclass AND t.tgname='session_guard' AND NOT t.tgisinternal) IS DISTINCT FROM 'O' THEN RAISE EXCEPTION 'Existing trigger enablement changed during reconciliation: availability_sessions.session_guard'; END IF;
 IF (SELECT md5(pg_get_triggerdef(t.oid)) FROM pg_trigger t WHERE t.tgrelid='ramosolo.calendar_blocks'::regclass AND t.tgname='calendar_block_protection' AND NOT t.tgisinternal) IS DISTINCT FROM 'f05ee14711574c13e976db45d8e0a7c5' THEN RAISE EXCEPTION 'Existing trigger changed during reconciliation: calendar_blocks.calendar_block_protection'; END IF;
 IF (SELECT t.tgenabled::text FROM pg_trigger t WHERE t.tgrelid='ramosolo.calendar_blocks'::regclass AND t.tgname='calendar_block_protection' AND NOT t.tgisinternal) IS DISTINCT FROM 'O' THEN RAISE EXCEPTION 'Existing trigger enablement changed during reconciliation: calendar_blocks.calendar_block_protection'; END IF;
 IF (SELECT md5(pg_get_triggerdef(t.oid)) FROM pg_trigger t WHERE t.tgrelid='ramosolo.care_assignments'::regclass AND t.tgname='nursing_assignment_scope' AND NOT t.tgisinternal) IS DISTINCT FROM 'd0dc14375a7d849cf5732f8cff3c6140' THEN RAISE EXCEPTION 'Existing trigger changed during reconciliation: care_assignments.nursing_assignment_scope'; END IF;
 IF (SELECT t.tgenabled::text FROM pg_trigger t WHERE t.tgrelid='ramosolo.care_assignments'::regclass AND t.tgname='nursing_assignment_scope' AND NOT t.tgisinternal) IS DISTINCT FROM 'O' THEN RAISE EXCEPTION 'Existing trigger enablement changed during reconciliation: care_assignments.nursing_assignment_scope'; END IF;
 IF (SELECT md5(pg_get_triggerdef(t.oid)) FROM pg_trigger t WHERE t.tgrelid='ramosolo.communication_preferences'::regclass AND t.tgname='communication_preference_guard' AND NOT t.tgisinternal) IS DISTINCT FROM '547aeb5b2c4d57c3cabe250249c721f6' THEN RAISE EXCEPTION 'Existing trigger changed during reconciliation: communication_preferences.communication_preference_guard'; END IF;
 IF (SELECT t.tgenabled::text FROM pg_trigger t WHERE t.tgrelid='ramosolo.communication_preferences'::regclass AND t.tgname='communication_preference_guard' AND NOT t.tgisinternal) IS DISTINCT FROM 'O' THEN RAISE EXCEPTION 'Existing trigger enablement changed during reconciliation: communication_preferences.communication_preference_guard'; END IF;
 IF (SELECT md5(pg_get_triggerdef(t.oid)) FROM pg_trigger t WHERE t.tgrelid='ramosolo.communication_preferences'::regclass AND t.tgname='preference_reminder_invalidation' AND NOT t.tgisinternal) IS DISTINCT FROM '93980af46ec7979c397ee05a07607365' THEN RAISE EXCEPTION 'Existing trigger changed during reconciliation: communication_preferences.preference_reminder_invalidation'; END IF;
 IF (SELECT t.tgenabled::text FROM pg_trigger t WHERE t.tgrelid='ramosolo.communication_preferences'::regclass AND t.tgname='preference_reminder_invalidation' AND NOT t.tgisinternal) IS DISTINCT FROM 'O' THEN RAISE EXCEPTION 'Existing trigger enablement changed during reconciliation: communication_preferences.preference_reminder_invalidation'; END IF;
 IF (SELECT md5(pg_get_triggerdef(t.oid)) FROM pg_trigger t WHERE t.tgrelid='ramosolo.followup_policies'::regclass AND t.tgname='followup_policy_guard' AND NOT t.tgisinternal) IS DISTINCT FROM 'd60a0feb9a990f2a9d3fbe15ba68639e' THEN RAISE EXCEPTION 'Existing trigger changed during reconciliation: followup_policies.followup_policy_guard'; END IF;
 IF (SELECT t.tgenabled::text FROM pg_trigger t WHERE t.tgrelid='ramosolo.followup_policies'::regclass AND t.tgname='followup_policy_guard' AND NOT t.tgisinternal) IS DISTINCT FROM 'O' THEN RAISE EXCEPTION 'Existing trigger enablement changed during reconciliation: followup_policies.followup_policy_guard'; END IF;
 IF (SELECT md5(pg_get_triggerdef(t.oid)) FROM pg_trigger t WHERE t.tgrelid='ramosolo.in_app_notifications'::regclass AND t.tgname='in_app_notification_protection' AND NOT t.tgisinternal) IS DISTINCT FROM '3ff666c30acf97879b87da82925766a8' THEN RAISE EXCEPTION 'Existing trigger changed during reconciliation: in_app_notifications.in_app_notification_protection'; END IF;
 IF (SELECT t.tgenabled::text FROM pg_trigger t WHERE t.tgrelid='ramosolo.in_app_notifications'::regclass AND t.tgname='in_app_notification_protection' AND NOT t.tgisinternal) IS DISTINCT FROM 'O' THEN RAISE EXCEPTION 'Existing trigger enablement changed during reconciliation: in_app_notifications.in_app_notification_protection'; END IF;
 IF (SELECT md5(pg_get_triggerdef(t.oid)) FROM pg_trigger t WHERE t.tgrelid='ramosolo.medical_invoices'::regclass AND t.tgname='invoice_audit' AND NOT t.tgisinternal) IS DISTINCT FROM 'b0635cee3c81fe6eadcd82ca5621ad4b' THEN RAISE EXCEPTION 'Existing trigger changed during reconciliation: medical_invoices.invoice_audit'; END IF;
 IF (SELECT t.tgenabled::text FROM pg_trigger t WHERE t.tgrelid='ramosolo.medical_invoices'::regclass AND t.tgname='invoice_audit' AND NOT t.tgisinternal) IS DISTINCT FROM 'O' THEN RAISE EXCEPTION 'Existing trigger enablement changed during reconciliation: medical_invoices.invoice_audit'; END IF;
 IF (SELECT md5(pg_get_triggerdef(t.oid)) FROM pg_trigger t WHERE t.tgrelid='ramosolo.medical_invoices'::regclass AND t.tgname='invoice_protection' AND NOT t.tgisinternal) IS DISTINCT FROM 'c3b6a2d31bbdf28b443d5c1f77173163' THEN RAISE EXCEPTION 'Existing trigger changed during reconciliation: medical_invoices.invoice_protection'; END IF;
 IF (SELECT t.tgenabled::text FROM pg_trigger t WHERE t.tgrelid='ramosolo.medical_invoices'::regclass AND t.tgname='invoice_protection' AND NOT t.tgisinternal) IS DISTINCT FROM 'O' THEN RAISE EXCEPTION 'Existing trigger enablement changed during reconciliation: medical_invoices.invoice_protection'; END IF;
 IF (SELECT md5(pg_get_triggerdef(t.oid)) FROM pg_trigger t WHERE t.tgrelid='ramosolo.medical_payment_entries'::regclass AND t.tgname='payment_audit' AND NOT t.tgisinternal) IS DISTINCT FROM 'cfcf5ba20510b999df420a68105d931c' THEN RAISE EXCEPTION 'Existing trigger changed during reconciliation: medical_payment_entries.payment_audit'; END IF;
 IF (SELECT t.tgenabled::text FROM pg_trigger t WHERE t.tgrelid='ramosolo.medical_payment_entries'::regclass AND t.tgname='payment_audit' AND NOT t.tgisinternal) IS DISTINCT FROM 'O' THEN RAISE EXCEPTION 'Existing trigger enablement changed during reconciliation: medical_payment_entries.payment_audit'; END IF;
 IF (SELECT md5(pg_get_triggerdef(t.oid)) FROM pg_trigger t WHERE t.tgrelid='ramosolo.medical_payment_entries'::regclass AND t.tgname='payment_protection' AND NOT t.tgisinternal) IS DISTINCT FROM '6bd02273edc00a36aa5bb493611ace02' THEN RAISE EXCEPTION 'Existing trigger changed during reconciliation: medical_payment_entries.payment_protection'; END IF;
 IF (SELECT t.tgenabled::text FROM pg_trigger t WHERE t.tgrelid='ramosolo.medical_payment_entries'::regclass AND t.tgname='payment_protection' AND NOT t.tgisinternal) IS DISTINCT FROM 'O' THEN RAISE EXCEPTION 'Existing trigger enablement changed during reconciliation: medical_payment_entries.payment_protection'; END IF;
 IF (SELECT md5(pg_get_triggerdef(t.oid)) FROM pg_trigger t WHERE t.tgrelid='ramosolo.memberships'::regclass AND t.tgname='membership_assignment_scope' AND NOT t.tgisinternal) IS DISTINCT FROM '68721a4b64189da3c1cd851149edf6fd' THEN RAISE EXCEPTION 'Existing trigger changed during reconciliation: memberships.membership_assignment_scope'; END IF;
 IF (SELECT t.tgenabled::text FROM pg_trigger t WHERE t.tgrelid='ramosolo.memberships'::regclass AND t.tgname='membership_assignment_scope' AND NOT t.tgisinternal) IS DISTINCT FROM 'O' THEN RAISE EXCEPTION 'Existing trigger enablement changed during reconciliation: memberships.membership_assignment_scope'; END IF;
 IF (SELECT md5(pg_get_triggerdef(t.oid)) FROM pg_trigger t WHERE t.tgrelid='ramosolo.notification_attempts'::regclass AND t.tgname='notification_attempt_protection' AND NOT t.tgisinternal) IS DISTINCT FROM '18b50cca3c2ce7f9cf4d728ca19ece4a' THEN RAISE EXCEPTION 'Existing trigger changed during reconciliation: notification_attempts.notification_attempt_protection'; END IF;
 IF (SELECT t.tgenabled::text FROM pg_trigger t WHERE t.tgrelid='ramosolo.notification_attempts'::regclass AND t.tgname='notification_attempt_protection' AND NOT t.tgisinternal) IS DISTINCT FROM 'O' THEN RAISE EXCEPTION 'Existing trigger enablement changed during reconciliation: notification_attempts.notification_attempt_protection'; END IF;
 IF (SELECT md5(pg_get_triggerdef(t.oid)) FROM pg_trigger t WHERE t.tgrelid='ramosolo.notification_outbox'::regclass AND t.tgname='notification_outbox_protection' AND NOT t.tgisinternal) IS DISTINCT FROM '0d99b5649c5fb7a287cbd0ebe6dccf39' THEN RAISE EXCEPTION 'Existing trigger changed during reconciliation: notification_outbox.notification_outbox_protection'; END IF;
 IF (SELECT t.tgenabled::text FROM pg_trigger t WHERE t.tgrelid='ramosolo.notification_outbox'::regclass AND t.tgname='notification_outbox_protection' AND NOT t.tgisinternal) IS DISTINCT FROM 'O' THEN RAISE EXCEPTION 'Existing trigger enablement changed during reconciliation: notification_outbox.notification_outbox_protection'; END IF;
 IF (SELECT md5(pg_get_triggerdef(t.oid)) FROM pg_trigger t WHERE t.tgrelid='ramosolo.patients'::regclass AND t.tgname='patient_assignment_scope' AND NOT t.tgisinternal) IS DISTINCT FROM 'cc335f883f30431306c84dc8ae7aaa29' THEN RAISE EXCEPTION 'Existing trigger changed during reconciliation: patients.patient_assignment_scope'; END IF;
 IF (SELECT t.tgenabled::text FROM pg_trigger t WHERE t.tgrelid='ramosolo.patients'::regclass AND t.tgname='patient_assignment_scope' AND NOT t.tgisinternal) IS DISTINCT FROM 'O' THEN RAISE EXCEPTION 'Existing trigger enablement changed during reconciliation: patients.patient_assignment_scope'; END IF;
 IF (SELECT md5(pg_get_triggerdef(t.oid)) FROM pg_trigger t WHERE t.tgrelid='ramosolo.patients'::regclass AND t.tgname='patient_reminder_invalidation' AND NOT t.tgisinternal) IS DISTINCT FROM '810f412ecec1b6d5fd34b419037bfac1' THEN RAISE EXCEPTION 'Existing trigger changed during reconciliation: patients.patient_reminder_invalidation'; END IF;
 IF (SELECT t.tgenabled::text FROM pg_trigger t WHERE t.tgrelid='ramosolo.patients'::regclass AND t.tgname='patient_reminder_invalidation' AND NOT t.tgisinternal) IS DISTINCT FROM 'O' THEN RAISE EXCEPTION 'Existing trigger enablement changed during reconciliation: patients.patient_reminder_invalidation'; END IF;
 IF (SELECT md5(pg_get_triggerdef(t.oid)) FROM pg_trigger t WHERE t.tgrelid='ramosolo.public_holidays'::regclass AND t.tgname='holiday_guard' AND NOT t.tgisinternal) IS DISTINCT FROM '284b28650fa809cba27805de7ea977db' THEN RAISE EXCEPTION 'Existing trigger changed during reconciliation: public_holidays.holiday_guard'; END IF;
 IF (SELECT t.tgenabled::text FROM pg_trigger t WHERE t.tgrelid='ramosolo.public_holidays'::regclass AND t.tgname='holiday_guard' AND NOT t.tgisinternal) IS DISTINCT FROM 'O' THEN RAISE EXCEPTION 'Existing trigger enablement changed during reconciliation: public_holidays.holiday_guard'; END IF;
 IF (SELECT md5(pg_get_triggerdef(t.oid)) FROM pg_trigger t WHERE t.tgrelid='ramosolo.reminder_leads'::regclass AND t.tgname='reminder_lead_guard' AND NOT t.tgisinternal) IS DISTINCT FROM '6ef97de0d2f4b3e581cce4803f406229' THEN RAISE EXCEPTION 'Existing trigger changed during reconciliation: reminder_leads.reminder_lead_guard'; END IF;
 IF (SELECT t.tgenabled::text FROM pg_trigger t WHERE t.tgrelid='ramosolo.reminder_leads'::regclass AND t.tgname='reminder_lead_guard' AND NOT t.tgisinternal) IS DISTINCT FROM 'O' THEN RAISE EXCEPTION 'Existing trigger enablement changed during reconciliation: reminder_leads.reminder_lead_guard'; END IF;
 IF (SELECT md5(pg_get_triggerdef(t.oid)) FROM pg_trigger t WHERE t.tgrelid='ramosolo.reminder_policies'::regclass AND t.tgname='policy_reminder_invalidation' AND NOT t.tgisinternal) IS DISTINCT FROM 'f6825bdcc0977a1816058688d7400a5e' THEN RAISE EXCEPTION 'Existing trigger changed during reconciliation: reminder_policies.policy_reminder_invalidation'; END IF;
 IF (SELECT t.tgenabled::text FROM pg_trigger t WHERE t.tgrelid='ramosolo.reminder_policies'::regclass AND t.tgname='policy_reminder_invalidation' AND NOT t.tgisinternal) IS DISTINCT FROM 'O' THEN RAISE EXCEPTION 'Existing trigger enablement changed during reconciliation: reminder_policies.policy_reminder_invalidation'; END IF;
 IF (SELECT md5(pg_get_triggerdef(t.oid)) FROM pg_trigger t WHERE t.tgrelid='ramosolo.reminder_policies'::regclass AND t.tgname='reminder_policy_guard' AND NOT t.tgisinternal) IS DISTINCT FROM '732e000ace5d9308f2341a44af29a245' THEN RAISE EXCEPTION 'Existing trigger changed during reconciliation: reminder_policies.reminder_policy_guard'; END IF;
 IF (SELECT t.tgenabled::text FROM pg_trigger t WHERE t.tgrelid='ramosolo.reminder_policies'::regclass AND t.tgname='reminder_policy_guard' AND NOT t.tgisinternal) IS DISTINCT FROM 'O' THEN RAISE EXCEPTION 'Existing trigger enablement changed during reconciliation: reminder_policies.reminder_policy_guard'; END IF;
 PERFORM set_config('search_path',original_search_path,true);
 IF EXISTS (SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='ramosolo' AND c.relname IN ('appointment_proposals','calendar_delegations','calendar_history','care_plan_reviews','care_plans','care_referrals','care_review_signoffs','clinical_records','communication_decisions','continuity_events','continuity_history','continuity_notifications','coordination_coverage','coordination_history','coordination_policies','discharge_followups','external_practitioners','nursing_observations','patient_permissions','patient_preferences','referral_clinical_records','appointment_proposals_id_seq','calendar_delegations_id_seq','calendar_history_id_seq','care_plan_reviews_id_seq','care_plans_id_seq','care_referrals_id_seq','care_review_signoffs_id_seq','clinical_records_id_seq','communication_decisions_id_seq','continuity_events_id_seq','continuity_history_id_seq','continuity_notifications_id_seq','coordination_coverage_id_seq','coordination_history_id_seq','coordination_policies_id_seq','discharge_followups_id_seq','external_practitioners_id_seq','nursing_observations_id_seq','patient_permissions_id_seq','patient_preferences_id_seq','referral_clinical_records_id_seq') AND pg_get_userbyid(c.relowner) IS DISTINCT FROM 'postgres') THEN RAISE EXCEPTION 'Target table or sequence owner postcondition failed'; END IF;
 IF EXISTS (SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace CROSS JOIN LATERAL aclexplode(coalesce(c.relacl,acldefault(CASE WHEN c.relkind='S' THEN 'S'::"char" ELSE 'r'::"char" END,c.relowner))) x WHERE n.nspname='ramosolo' AND c.relname IN ('appointment_proposals','calendar_delegations','calendar_history','care_plan_reviews','care_plans','care_referrals','care_review_signoffs','clinical_records','communication_decisions','continuity_events','continuity_history','continuity_notifications','coordination_coverage','coordination_history','coordination_policies','discharge_followups','external_practitioners','nursing_observations','patient_permissions','patient_preferences','referral_clinical_records','appointment_proposals_id_seq','calendar_delegations_id_seq','calendar_history_id_seq','care_plan_reviews_id_seq','care_plans_id_seq','care_referrals_id_seq','care_review_signoffs_id_seq','clinical_records_id_seq','communication_decisions_id_seq','continuity_events_id_seq','continuity_history_id_seq','continuity_notifications_id_seq','coordination_coverage_id_seq','coordination_history_id_seq','coordination_policies_id_seq','discharge_followups_id_seq','external_practitioners_id_seq','nursing_observations_id_seq','patient_permissions_id_seq','patient_preferences_id_seq','referral_clinical_records_id_seq') AND x.grantee IN (0,'anon'::regrole,'authenticated'::regrole)) THEN RAISE EXCEPTION 'Target table or sequence grants postcondition failed'; END IF;
 IF EXISTS (SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace CROSS JOIN LATERAL aclexplode(coalesce(p.proacl,acldefault('f'::"char",p.proowner))) x WHERE n.nspname='ramosolo' AND p.proname IN ('coordination_guard_outbox','coordination_suppress_withdrawn') AND x.grantee IN (0,'anon'::regrole,'authenticated'::regrole)) THEN RAISE EXCEPTION 'Coordination routine grants postcondition failed'; END IF;
 IF (SELECT array_agg(version ORDER BY version) FROM ramosolo.schema_versions) IS DISTINCT FROM ARRAY[1,2,3,4,5,6] THEN RAISE EXCEPTION 'Ledger changed before all postconditions'; END IF;
 INSERT INTO ramosolo.schema_versions(version) VALUES (7),(8),(9);
 IF (SELECT array_agg(version ORDER BY version) FROM ramosolo.schema_versions) IS DISTINCT FROM ARRAY[1,2,3,4,5,6,7,8,9] THEN RAISE EXCEPTION 'Ledger postcondition failed'; END IF;
END $postcondition$;
COMMIT;
