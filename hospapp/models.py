from email.policy import default
from unittest.mock import DEFAULT
from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from datetime import date, datetime

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

class Department(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name
    
class Appointment(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE)
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    scheduled_time = models.DateTimeField()

    def __str__(self):
        return f"{self.patient.full_name} - {self.department}"
    
class Referral(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE)
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    notes = models.TextField()

    def __str__(self):
        return f"{self.patient.full_name} - {self.department.name}"

# Admission by Nurse
class Admission(models.Model):
    STATUS_CHOICES = [
        ('Admitted', 'Admitted'),
        ('Discharged', 'Discharged'),
    ]
    def get_current_time():
        return datetime.now().time()
    admitted_on = models.DateField(default=date.today)
    time = models.TimeField(default=get_current_time)
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

class Shift(models.Model):
    SHIFT_CHOICES = [
        ('Morning', 'Morning'),
        ('Afternoon', 'Afternoon'),
        ('Night', 'Night'),
    ]
    name = models.CharField(max_length=20, choices=SHIFT_CHOICES, unique=True)

    def __str__(self):
        return self.name

class Attendance(models.Model):
    STATUS_CHOICES = [
        ('Present', 'Present'),
        ('Absent', 'Absent'),
        ('On Leave', 'On Leave'),
    ]
    staff = models.ForeignKey(User, on_delete=models.CASCADE, related_name='attendances')
    date = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)

    class Meta:
        unique_together = ('staff', 'date')
        ordering = ['-date']

    def __str__(self):
        return f"{self.staff.get_full_name() or self.staff.username} - {self.date} - {self.status}"

class ShiftAssignment(models.Model):
    staff = models.ForeignKey(User, on_delete=models.CASCADE, related_name='shift_assignments')
    shift = models.ForeignKey(Shift, on_delete=models.CASCADE)
    date = models.DateField(default=timezone.now)

    class Meta:
        unique_together = ('staff', 'date')

    def __str__(self):
        return f"{self.staff.get_full_name() or self.staff.username} - {self.shift.name} on {self.date}"

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
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True)
    date_joined = models.DateField(default=timezone.now)

    def __str__(self):
        return f"{self.user.first_name} {self.user.last_name} ({self.role})"
    
class StaffTransition(models.Model):
    TRANSITION_CHOICES = [
        ('onboarding', 'Onboarding'),
        ('offboarding', 'Offboarding'),
    ]
    full_name = models.CharField(max_length=200)
    transition_type = models.CharField(max_length=20, choices=TRANSITION_CHOICES)
    date = models.DateField()
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"{self.full_name} - {self.transition_type} on {self.date}"


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
    
class Consultation(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='consultations')
    admission = models.ForeignKey(Admission, null=True, blank=True, on_delete=models.SET_NULL)
    # test = models.ForeignKey(LabTest, null=True, blank=True, on_delete=models.SET_NULL)
    
    doctor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    symptoms = models.TextField()  # New field for symptoms
    diagnosis_summary = models.TextField()
    advice = models.TextField()
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Consultation for {self.patient.full_name} on {self.created_at:%Y-%m-%d}"

class Prescription(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='prescriptions')
    medication = models.CharField(max_length=200)
    instructions = models.TextField()
    start_date = models.DateField()
    prescribed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.medication} for {self.patient.full_name}"
    
class CarePlan(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE)
    clinical_findings = models.TextField()
    plan_of_care = models.TextField()
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Care Plan for {self.patient.full_name} on {self.created_at:%Y-%m-%d}"
    
class LabTestType(models.Model):
    name = models.CharField(max_length=100, unique=True)
    category = models.CharField(max_length=100, blank=True, null=True)  # e.g., "Hormonal", "Imaging", etc.
    units = models.CharField(max_length=50, blank=True, null=True)      # e.g., "ng/mL", "%", etc.
    reference_range = models.CharField(max_length=100, blank=True, null=True)  # optional

    def __str__(self):
        return self.name

    
class TestRequest(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE)
    requested_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    tests = models.ManyToManyField(LabTestType)
    instructions = models.TextField(blank=True, null=True)
    requested_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Test Request for {self.patient.full_name} at {self.requested_at.strftime('%Y-%m-%d %H:%M')}"
    
    
class LabTest(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE)
    test_request = models.ForeignKey(TestRequest, on_delete=models.SET_NULL, null=True, blank=True, related_name='lab_tests')
    test_type = models.ForeignKey(LabTestType, on_delete=models.CASCADE)
    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    date_recorded = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.patient.full_name} - {self.test_type.name} ({self.date_recorded.date()})"
    
class LabTestField(models.Model):
    lab_test = models.ForeignKey(LabTest, on_delete=models.CASCADE, related_name='fields')
    name = models.CharField(max_length=100)
    value = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.name}: {self.value}"

    
class LabResultFile(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    result_file = models.FileField(upload_to='lab_results/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Result for {self.patient.full_name} uploaded on {self.uploaded_at.date()}"

#The available tests and test subcategories models
from django.db import models

class TestCategory(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name

class TestSubcategory(models.Model):
    category = models.ForeignKey(TestCategory, related_name='subcategories', on_delete=models.CASCADE)
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name
#It end here    
#Doctor tests requested for the lab to do
class TestSelection(models.Model):
    def get_current_time():
        return datetime.now().time()
    submitted_on = models.DateField(default=date.today)
    time = models.TimeField(default=get_current_time)
    patient_id = models.ForeignKey(Patient, default=1, on_delete=models.CASCADE)
    category = models.CharField(max_length=100)
    test_name = models.CharField(max_length=100)
    timestamp = models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return f"{self.category} - {self.test_name}"    