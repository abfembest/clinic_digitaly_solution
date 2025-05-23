from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User

# Wards and Beds
class Ward(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name

class Bed(models.Model):
    ward = models.ForeignKey(Ward, on_delete=models.CASCADE, related_name='beds')
    number = models.CharField(max_length=20)
    is_occupied = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.ward.name} - Bed {self.number}"

# Patient Model
class Patient(models.Model):
    BLOOD_GROUP_CHOICES = [
        ('A+', 'A+'), ('A-', 'A-'),
        ('B+', 'B+'), ('B-', 'B-'),
        ('AB+', 'AB+'), ('AB-', 'AB-'),
        ('O+', 'O+'), ('O-', 'O-'),
    ]
    STATUS_CHOICES = [
        ('stable', 'Stable'),
        ('critical', 'Critical'),
        ('recovered', 'Recovered'),
    ]

    # Core info
    full_name = models.CharField(max_length=200)
    gender = models.CharField()
    date_of_birth = models.DateField()
    phone = models.CharField(max_length=15)
    email = models.EmailField(blank=True, null=True)
    address = models.TextField()
    marital_status = models.CharField(max_length=20)
    nationality = models.CharField(max_length=50)
    state_of_origin = models.CharField(max_length=50, blank=True)
    id_type = models.CharField(max_length=20, blank=True)
    id_number = models.CharField(max_length=100, blank=True)

    # Next of Kin
    next_of_kin_name = models.CharField(max_length=100)
    next_of_kin_phone = models.CharField(max_length=15)

    # Medical and system data
    blood_group = models.CharField(max_length=3, choices=BLOOD_GROUP_CHOICES, default='O+')
    is_inpatient = models.BooleanField(default=False)
    ward = models.ForeignKey(Ward, null=True, blank=True, on_delete=models.SET_NULL)
    bed = models.ForeignKey(Bed, null=True, blank=True, on_delete=models.SET_NULL)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='stable')
    diagnosis = models.TextField(blank=True, null=True)
    medication = models.TextField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)

    # Admin fields
    referred_by = models.CharField(max_length=100, blank=True, null=True)
    first_time = models.CharField(max_length=20, blank=True)
    photo = models.ImageField(upload_to='patient_photos/', blank=True, null=True)
    date_registered = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.full_name}"

class Appointment(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE)
    department = models.CharField(max_length=100)
    scheduled_time = models.DateTimeField()

    def __str__(self):
        return f"{self.patient.full_name} - {self.department}"

class Referral(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE)
    department = models.CharField(max_length=100)
    notes = models.TextField()

    def __str__(self):
        return f"{self.patient.full_name} - {self.department}"

# Admission
class Admission(models.Model):
    STATUS_CHOICES = [
        ('Admitted', 'Admitted'),
        ('Discharged', 'Discharged'),
    ]

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE)
    admission_date = models.DateField(default=timezone.now)
    ward = models.ForeignKey(Ward, on_delete=models.SET_NULL, null=True)
    bed = models.ForeignKey(Bed, on_delete=models.SET_NULL, null=True)
    doctor_assigned = models.CharField(max_length=100)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Admitted')
    discharge_date = models.DateField(blank=True, null=True)
    discharge_notes = models.TextField(blank=True, null=True)
    admitted_by = models.CharField(max_length=100, blank=True, null=True)
    discharged_by = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return f"Admission for {self.patient.full_name} - {self.status}"


# Handover logs between staff
class HandoverLog(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE)
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    notes = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Handover: {self.patient.full_name} by {self.author}"

# Shift Types
class Shift(models.Model):
    SHIFT_CHOICES = [('Morning', 'Morning'), ('Afternoon', 'Afternoon'), ('Night', 'Night')]
    name = models.CharField(max_length=20, choices=SHIFT_CHOICES, unique=True)

    def __str__(self):
        return self.name

# Tasks assigned per shift
class TaskAssignment(models.Model):
    shift = models.ForeignKey(Shift, on_delete=models.CASCADE)
    nurse = models.ForeignKey(User, on_delete=models.CASCADE)
    task_description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.nurse.username} - {self.shift.name}"

# Emergency Alerts
class EmergencyAlert(models.Model):
    message = models.TextField()
    triggered_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='alerts_triggered')
    acknowledged_by = models.ManyToManyField(User, blank=True, related_name='alerts_acknowledged')
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Alert: {self.message[:30]}..."

# Medical Records
class MedicalRecord(models.Model):
    patient = models.ForeignKey(Patient, related_name='medical_records', on_delete=models.CASCADE)
    record_date = models.DateField(auto_now_add=True)
    description = models.TextField()
    created_by = models.CharField(max_length=100)  # Consider FK to User in future

    def __str__(self):
        return f"Medical Record - {self.patient.full_name} ({self.record_date})"

# Role-based User Profiles
ROLE_CHOICES = [
    ('receptionist', 'Receptionist'),
    ('nurse', 'Nurse'),
    ('doctor', 'Doctor'),
    ('lab', 'Lab Technician'),
    ('admin', 'Administrator'),
    ('pharmacy', 'Pharmacy'),
    ('hr', 'HR'),
]

class Profile(models.Model):
    GENDER_CHOICES = [('M', 'Male'), ('F', 'Female')]

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, default='M')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    phone_number = models.CharField(max_length=15, blank=True)
    address = models.TextField(blank=True, null=True)
    photo = models.ImageField(upload_to='profile_photos/', blank=True, null=True)
    date_joined = models.DateField(default=timezone.now)

    def __str__(self):
        return f"{self.user.first_name} {self.user.last_name} ({self.role})"


class Vitals(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE)
    recorded_at = models.DateTimeField()
    temperature = models.FloatField(null=True, blank=True)
    blood_pressure = models.CharField(max_length=20, null=True, blank=True)
    pulse = models.IntegerField(null=True, blank=True)
    respiratory_rate = models.IntegerField(null=True, blank=True)
    weight = models.FloatField(null=True, blank=True)
    height = models.FloatField(null=True, blank=True)
    bmi = models.FloatField(null=True, blank=True)  # ✅ Add this field
    notes = models.TextField(blank=True, null=True)
    recorded_by = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.patient.full_name} Vitals @ {self.recorded_at}"
    
class NursingNote(models.Model):
    NOTE_TYPE_CHOICES = [
        ('observation', 'Observation'),
        ('medication', 'Medication Administered'),
        ('response', 'Patient Response'),
        ('care_plan', 'Care Plan Update'),
        ('other', 'Other'),
    ]

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='nursing_notes')
    note_datetime = models.DateTimeField(default=timezone.now)
    note_type = models.CharField(max_length=50, choices=NOTE_TYPE_CHOICES)
    nurse = models.CharField(max_length=100)  # or ForeignKey to User if desired
    patient_status = models.CharField(max_length=50, blank=True, null=True)
    notes = models.TextField()
    follow_up = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Nursing Note for {self.patient.full_name} on {self.note_datetime.strftime('%Y-%m-%d %H:%M')}"
