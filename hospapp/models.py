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
    patient = models.ForeignKey('Patient', on_delete=models.CASCADE)
    department = models.ForeignKey('Department', on_delete=models.CASCADE)
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
    ('account', 'Account')
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
    
class LabResultFile(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    result_file = models.FileField(upload_to='lab_results/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Result for {self.patient.full_name} uploaded on {self.uploaded_at.date()}"

class TestCategory(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name

class TestSubcategory(models.Model):
    category = models.ForeignKey(TestCategory, related_name='subcategories', on_delete=models.CASCADE)
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name

#Doctor tests requested for the lab to do
class TestSelection(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
    ]

    def get_current_time():
        from datetime import datetime
        return datetime.now().time()

    submitted_on = models.DateField(default=timezone.now)
    time = models.TimeField(default=get_current_time)
    patient_id = models.ForeignKey('Patient', on_delete=models.CASCADE, related_name='test_selections')
    category = models.CharField(max_length=100)
    test_name = models.CharField(max_length=100)
    timestamp = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    testcompleted = models.BooleanField(default=False)
    doctor_name = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return f"{self.category} - {self.test_name} ({self.status})"

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
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE)
    requested_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    tests = models.ManyToManyField(LabTestType)
    instructions = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    requested_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Test Request for {self.patient.full_name} - {self.status}"
    
    def update_status(self):
        """Auto-update status based on test completion"""
        total_tests = self.tests.count()
        completed_tests = self.lab_tests.filter(result_value__isnull=False).count()
        
        if completed_tests == 0:
            self.status = 'pending'
        elif completed_tests < total_tests:
            self.status = 'in_progress'
            if not self.started_at:
                self.started_at = timezone.now()
        else:
            self.status = 'completed'
            if not self.completed_at:
                self.completed_at = timezone.now()
        
        self.save()
    
class LabTest(models.Model):
    def get_current_time():
        return datetime.now().time()
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE)
    test_request = models.ForeignKey(TestRequest, on_delete=models.SET_NULL, null=True, blank=True, related_name='lab_tests')
    test_selection = models.ForeignKey(TestSelection, on_delete=models.SET_NULL, null=True, blank=True, related_name='lab_results')
    test_type = models.CharField(max_length=100)  # This can be the name from TestSelection
    test_category = models.CharField(max_length=100, default ="empty")  # This can be the category from TestSelection
    result_value = models.TextField(default ="positive")  # The actual test result
    normal_range = models.CharField(max_length=100, blank=True, null=True)  # Reference range
    notes = models.TextField(blank=True, null=True)  # Additional notes
    performed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='performed_tests')
    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='recorded_tests')
    date_performed = models.DateTimeField(default=get_current_time())

    def __str__(self):
        return f"{self.patient.full_name} - {self.test_type} ({self.date_performed.date()})"
    
class LabTestField(models.Model):
    lab_test = models.ForeignKey(LabTest, on_delete=models.CASCADE, related_name='fields')
    name = models.CharField(max_length=100)
    value = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.name}: {self.value}"
    

# Add these models to your existing models.py file

from decimal import Decimal
from django.core.validators import MinValueValidator

# Financial Models for Accounts Module

class ServiceType(models.Model):
    """Types of services offered by the hospital"""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    default_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return self.name

class PatientBill(models.Model):
    """Main billing record for patients"""
    BILL_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('partial', 'Partially Paid'),
        ('paid', 'Fully Paid'),
        ('cancelled', 'Cancelled'),
        ('refunded', 'Refunded'),
    ]
    
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='bills')
    bill_number = models.CharField(max_length=20, unique=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.00'))])
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    final_amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=BILL_STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    notes = models.TextField(blank=True, null=True)
    
    def save(self, *args, **kwargs):
        if not self.bill_number:
            # Generate unique bill number
            from datetime import date
            today = date.today()
            count = PatientBill.objects.filter(created_at__date=today).count() + 1
            self.bill_number = f"BILL-{today.strftime('%Y%m%d')}-{count:04d}"
        
        self.final_amount = self.total_amount - self.discount_amount
        super().save(*args, **kwargs)
    
    def amount_paid(self):
        return self.payments.filter(status='completed').aggregate(
            total=models.Sum('amount')
        )['total'] or Decimal('0.00')
    
    def outstanding_amount(self):
        return self.final_amount - self.amount_paid()
    
    def __str__(self):
        return f"{self.bill_number} - {self.patient.full_name}"

class BillItem(models.Model):
    """Individual items/services in a bill"""
    bill = models.ForeignKey(PatientBill, on_delete=models.CASCADE, related_name='items')
    service_type = models.ForeignKey(ServiceType, on_delete=models.CASCADE)
    description = models.CharField(max_length=200)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    
    def save(self, *args, **kwargs):
        self.total_price = self.quantity * self.unit_price
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.description} - ₦{self.total_price}"

class Payment(models.Model):
    """Payment records"""
    PAYMENT_METHOD_CHOICES = [
        ('cash', 'Cash'),
        ('pos', 'POS'),
        ('transfer', 'Bank Transfer'),
        ('cheque', 'Cheque'),
        ('online', 'Online Payment'),
    ]
    
    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    bill = models.ForeignKey(PatientBill, on_delete=models.CASCADE, related_name='payments', null=True, blank=True)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    payment_reference = models.CharField(max_length=100, blank=True, null=True)
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='completed')
    payment_date = models.DateTimeField(auto_now_add=True)
    processed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    notes = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return f"Payment ₦{self.amount} - {self.patient.full_name}"

class ExpenseCategory(models.Model):
    """Categories for hospital expenses"""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return self.name

class Expense(models.Model):
    """Hospital expenses/expenditure"""
    EXPENSE_STATUS_CHOICES = [
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('paid', 'Paid'),
        ('rejected', 'Rejected'),
    ]
    
    category = models.ForeignKey(ExpenseCategory, on_delete=models.CASCADE)
    description = models.CharField(max_length=200)
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    expense_date = models.DateField()
    status = models.CharField(max_length=20, choices=EXPENSE_STATUS_CHOICES, default='pending')
    receipt_number = models.CharField(max_length=50, blank=True, null=True)
    vendor = models.CharField(max_length=100, blank=True, null=True)
    requested_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='requested_expenses')
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_expenses')
    created_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return f"{self.description} - ₦{self.amount}"

class Budget(models.Model):
    """Budget planning"""
    category = models.ForeignKey(ExpenseCategory, on_delete=models.CASCADE)
    year = models.PositiveIntegerField()
    month = models.PositiveIntegerField(choices=[(i, i) for i in range(1, 13)], null=True, blank=True)
    allocated_amount = models.DecimalField(max_digits=12, decimal_places=2)
    spent_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('category', 'year', 'month')
    
    def remaining_amount(self):
        return self.allocated_amount - self.spent_amount
    
    def percentage_used(self):
        if self.allocated_amount > 0:
            return (self.spent_amount / self.allocated_amount) * 100
        return 0
    
    def __str__(self):
        period = f"{self.year}" if not self.month else f"{self.month}/{self.year}"
        return f"{self.category.name} Budget - {period}"

class PaymentUpload(models.Model):
    """Track bulk payment uploads"""
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    file_name = models.CharField(max_length=255)
    upload_date = models.DateTimeField(auto_now_add=True)
    total_records = models.PositiveIntegerField(default=0)
    successful_records = models.PositiveIntegerField(default=0)
    failed_records = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=[
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ], default='processing')
    error_log = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return f"Upload: {self.file_name} - {self.status}"

    