# Generated by Django 5.2 on 2025-05-13 12:59

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('hospapp', '0006_alter_patient_first_time'),
    ]

    operations = [
        migrations.RenameField(
            model_name='bed',
            old_name='bed_number',
            new_name='number',
        ),
    ]
