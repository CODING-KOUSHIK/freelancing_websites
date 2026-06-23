from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("support", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="supportticket",
            name="first_response_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="supportticket",
            name="last_response_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="supportticket",
            name="sla_due_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="supportticket",
            name="escalation_level",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="supportticket",
            name="escalated_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="supportticket",
            name="metadata",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
