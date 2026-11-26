from django.db import migrations, models

# T-026 CP2: CP1 added ``membership_id``/``user_id`` to the immutable completion row for this
# backfill, so the guard must allow those two links to be filled from NULL exactly once. Every
# other edit is still refused, as is any rewrite of a filled link or of the rest of the row.
ALLOW_COMPLETION_LINKS = """
CREATE OR REPLACE FUNCTION academy_guard_completion_record() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'completion_record_immutable: DELETE is not allowed';
    END IF;
    IF NEW.membership_id IS NOT DISTINCT FROM OLD.membership_id
        AND NEW.user_id IS NOT DISTINCT FROM OLD.user_id THEN
        RAISE EXCEPTION 'completion_record_immutable: UPDATE is not allowed';
    END IF;
    IF (OLD.membership_id IS NOT NULL AND NEW.membership_id IS DISTINCT FROM OLD.membership_id)
        OR (OLD.user_id IS NOT NULL AND NEW.user_id IS DISTINCT FROM OLD.user_id) THEN
        RAISE EXCEPTION 'completion_record_immutable: UPDATE is not allowed';
    END IF;
    IF (to_jsonb(NEW) - 'membership_id' - 'user_id')
        IS DISTINCT FROM (to_jsonb(OLD) - 'membership_id' - 'user_id') THEN
        RAISE EXCEPTION 'completion_record_immutable: UPDATE is not allowed';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""

# Same rule for the audit ledger: CP1 added the two actor snapshots for this backfill, and the
# append-only guard refuses every edit except filling one of them from NULL exactly once.
ALLOW_AUDIT_ACTOR_LINKS = """
CREATE OR REPLACE FUNCTION academy_guard_audit_event() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'audit_event_append_only: DELETE is not allowed';
    END IF;
    IF NEW.actor_user_id IS NOT DISTINCT FROM OLD.actor_user_id
        AND NEW.actor_membership_id IS NOT DISTINCT FROM OLD.actor_membership_id THEN
        RAISE EXCEPTION 'audit_event_append_only: UPDATE is not allowed';
    END IF;
    IF (OLD.actor_user_id IS NOT NULL AND NEW.actor_user_id IS DISTINCT FROM OLD.actor_user_id)
        OR (OLD.actor_membership_id IS NOT NULL
            AND NEW.actor_membership_id IS DISTINCT FROM OLD.actor_membership_id) THEN
        RAISE EXCEPTION 'audit_event_append_only: UPDATE is not allowed';
    END IF;
    IF (to_jsonb(NEW) - 'actor_user_id' - 'actor_membership_id')
        IS DISTINCT FROM (to_jsonb(OLD) - 'actor_user_id' - 'actor_membership_id') THEN
        RAISE EXCEPTION 'audit_event_append_only: UPDATE is not allowed';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""

REFUSE_EVERY_AUDIT_UPDATE = """
CREATE OR REPLACE FUNCTION academy_guard_audit_event() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION
        'audit_event_append_only: % is not allowed', TG_OP;
END;
$$ LANGUAGE plpgsql;
"""

REFUSE_EVERY_COMPLETION_UPDATE = """
CREATE OR REPLACE FUNCTION academy_guard_completion_record() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION
        'completion_record_immutable: % is not allowed', TG_OP;
END;
$$ LANGUAGE plpgsql;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("academy", "0008_auditevent_actor_membership_id_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="department",
            name="legacy_ref",
            field=models.CharField(blank=True, max_length=64, null=True),
        ),
        migrations.AddField(
            model_name="user",
            name="legacy_ref",
            field=models.CharField(blank=True, max_length=64, null=True),
        ),
        migrations.AddField(
            model_name="user",
            name="must_set_email",
            field=models.BooleanField(default=False),
        ),
        migrations.AddConstraint(
            model_name="department",
            constraint=models.UniqueConstraint(
                condition=models.Q(("legacy_ref__isnull", False)),
                fields=("organization_id", "legacy_ref"),
                name="department_legacy_ref_unique",
            ),
        ),
        migrations.AddConstraint(
            model_name="user",
            constraint=models.UniqueConstraint(
                condition=models.Q(("legacy_ref__isnull", False)),
                fields=("legacy_ref",),
                name="user_legacy_ref_unique",
            ),
        ),
        migrations.RunSQL(
            sql=ALLOW_COMPLETION_LINKS,
            reverse_sql=REFUSE_EVERY_COMPLETION_UPDATE,
        ),
        migrations.RunSQL(
            sql=ALLOW_AUDIT_ACTOR_LINKS,
            reverse_sql=REFUSE_EVERY_AUDIT_UPDATE,
        ),
    ]
