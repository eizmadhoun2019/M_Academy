"""Make ``AuditEvent`` append-only at the database (``docs/domain-model.md`` §2.13)."""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("academy", "0003_auditevent_notificationlog_quiz_quizattempt_and_more"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            CREATE OR REPLACE FUNCTION academy_guard_audit_event() RETURNS trigger AS $$
            BEGIN
                RAISE EXCEPTION
                    'audit_event_append_only: % is not allowed', TG_OP;
            END;
            $$ LANGUAGE plpgsql;

            CREATE TRIGGER audit_event_append_only
            BEFORE UPDATE OR DELETE ON academy_auditevent
            FOR EACH ROW EXECUTE FUNCTION academy_guard_audit_event();
            """,
            reverse_sql="""
            DROP TRIGGER IF EXISTS audit_event_append_only ON academy_auditevent;
            DROP FUNCTION IF EXISTS academy_guard_audit_event();
            """,
        ),
    ]
