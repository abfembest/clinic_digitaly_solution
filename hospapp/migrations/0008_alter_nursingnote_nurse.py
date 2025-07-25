# Generated by Django 5.2 on 2025-06-24 13:55

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hospapp', '0007_alter_nursingnote_nurse'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name='nursingnote',
            name='nurse',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='nursing_notes', to=settings.AUTH_USER_MODEL),
        ),
    ]
