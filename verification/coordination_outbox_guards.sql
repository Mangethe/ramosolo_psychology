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
