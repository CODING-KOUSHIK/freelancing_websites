"""
Migration 0003: Fix JSON/array column defaults to prevent IntegrityError
when admin form saves without touching optional list fields.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("marketplace", "0002_add_fixed_task_and_trending_fields"),
    ]

    operations = [
        # Set DEFAULT '[]' on all JSON list columns that were missing it in Postgres
        migrations.RunSQL(
            sql="""
                ALTER TABLE marketplace_jobposting
                    ALTER COLUMN language_restriction  SET DEFAULT '[]'::jsonb,
                    ALTER COLUMN country_restriction   SET DEFAULT '[]'::jsonb,
                    ALTER COLUMN skills_required       SET DEFAULT '[]'::jsonb,
                    ALTER COLUMN external_links        SET DEFAULT '[]'::jsonb,
                    ALTER COLUMN field_schema          SET DEFAULT '[]'::jsonb;

                -- Back-fill any existing NULLs
                UPDATE marketplace_jobposting SET language_restriction  = '[]'::jsonb WHERE language_restriction  IS NULL;
                UPDATE marketplace_jobposting SET country_restriction   = '[]'::jsonb WHERE country_restriction   IS NULL;
                UPDATE marketplace_jobposting SET skills_required       = '[]'::jsonb WHERE skills_required       IS NULL;
                UPDATE marketplace_jobposting SET external_links        = '[]'::jsonb WHERE external_links        IS NULL;
                UPDATE marketplace_jobposting SET field_schema          = '[]'::jsonb WHERE field_schema          IS NULL;
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
