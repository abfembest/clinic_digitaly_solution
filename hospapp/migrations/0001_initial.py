# Generated by Django 5.2 on 2025-05-13 10:46

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Bed',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('bed_number', models.CharField(max_length=20)),
                ('is_occupied', models.BooleanField(default=False)),
            ],
        ),
        migrations.CreateModel(
            name='Shift',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(choices=[('Morning', 'Morning'), ('Afternoon', 'Afternoon'), ('Night', 'Night')], max_length=20, unique=True)),
            ],
        ),
        migrations.CreateModel(
            name='Ward',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True)),
            ],
        ),
        migrations.CreateModel(
            name='EmergencyAlert',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('message', models.TextField()),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('acknowledged_by', models.ManyToManyField(blank=True, related_name='alerts_acknowledged', to=settings.AUTH_USER_MODEL)),
                ('triggered_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='alerts_triggered', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='Patient',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('full_name', models.CharField(max_length=200)),
                ('first_name', models.CharField(max_length=50)),
                ('last_name', models.CharField(max_length=50)),
                ('gender', models.CharField(choices=[('M', 'Male'), ('F', 'Female'), ('O', 'Other')], max_length=1)),
                ('date_of_birth', models.DateField()),
                ('phone', models.CharField(max_length=15)),
                ('email', models.EmailField(blank=True, max_length=254, null=True)),
                ('address', models.TextField()),
                ('blood_group', models.CharField(choices=[('A+', 'A+'), ('A-', 'A-'), ('B+', 'B+'), ('B-', 'B-'), ('AB+', 'AB+'), ('AB-', 'AB-'), ('O+', 'O+'), ('O-', 'O-')], default='O+', max_length=3)),
                ('next_of_kin_name', models.CharField(max_length=100)),
                ('next_of_kin_phone', models.CharField(max_length=15)),
                ('is_inpatient', models.BooleanField(default=False)),
                ('photo', models.ImageField(blank=True, null=True, upload_to='patient_photos/')),
                ('date_registered', models.DateTimeField(auto_now_add=True)),
                ('status', models.CharField(choices=[('stable', 'Stable'), ('critical', 'Critical'), ('recovered', 'Recovered')], default='stable', max_length=20)),
                ('diagnosis', models.TextField(blank=True, null=True)),
                ('medication', models.TextField(blank=True, null=True)),
                ('notes', models.TextField(blank=True, null=True)),
                ('bed', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='hospapp.bed')),
                ('ward', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='hospapp.ward')),
            ],
        ),
        migrations.CreateModel(
            name='MedicalRecord',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('record_date', models.DateField(auto_now_add=True)),
                ('description', models.TextField()),
                ('created_by', models.CharField(max_length=100)),
                ('patient', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='medical_records', to='hospapp.patient')),
            ],
        ),
        migrations.CreateModel(
            name='HandoverLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('notes', models.TextField()),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('author', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ('patient', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='hospapp.patient')),
            ],
        ),
        migrations.CreateModel(
            name='Profile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('gender', models.CharField(choices=[('M', 'Male'), ('F', 'Female')], default='M', max_length=1)),
                ('role', models.CharField(choices=[('receptionist', 'Receptionist'), ('nurse', 'Nurse'), ('doctor', 'Doctor'), ('lab', 'Lab Technician'), ('admin', 'Administrator'), ('pharmacy', 'Pharmacy'), ('hr', 'HR')], max_length=20)),
                ('phone_number', models.CharField(blank=True, max_length=15)),
                ('address', models.TextField(blank=True, null=True)),
                ('photo', models.ImageField(blank=True, null=True, upload_to='profile_photos/')),
                ('date_joined', models.DateField(default=django.utils.timezone.now)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='TaskAssignment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('task_description', models.TextField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('nurse', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
                ('shift', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='hospapp.shift')),
            ],
        ),
        migrations.AddField(
            model_name='bed',
            name='ward',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='beds', to='hospapp.ward'),
        ),
        migrations.CreateModel(
            name='Admission',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('admission_date', models.DateField(default=django.utils.timezone.now)),
                ('doctor_assigned', models.CharField(max_length=100)),
                ('status', models.CharField(choices=[('Admitted', 'Admitted'), ('Discharged', 'Discharged')], default='Admitted', max_length=20)),
                ('discharge_date', models.DateField(blank=True, null=True)),
                ('discharge_notes', models.TextField(blank=True, null=True)),
                ('bed', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='hospapp.bed')),
                ('patient', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='hospapp.patient')),
                ('ward', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='hospapp.ward')),
            ],
        ),
    ]
