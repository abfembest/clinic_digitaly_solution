from decimal import Decimal
from datetime import date, datetime
from email.policy import default
from xmlrpc.client import boolean
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone
from uuid import uuid4

# =============================================================================
# CORE SYSTEM MODELS (Alphabetical)
# =============================================================================

class Department(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name

class Staff(models.Model):
    ROLE_CHOICES = [
        ('account', 'Account'),
        ('admin', 'Administrator'),
        ('doctor', 'Doctor'),
        ('hr', 'HR'),
        ('lab', 'Lab Technician'),
        ('nurse', 'Nurse'),
        ('pharmacy', 'Pharmacy'),
        ('receptionist', 'Receptionist'),
    ]
    GENDER_CHOICES = [('M', 'Male'), ('F', 'Female')]

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    address = models.TextField(blank=True, null=True)
    date_joined = models.DateField(default=timezone.now)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, default='M')
    phone_number = models.CharField(max_length=15, blank=True)
    photo = models.ImageField(upload_to='profile_photos/', blank=True, null=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)

    class Meta:
        permissions = [
            ("can_edit_staff_profiles", "Can edit any staff user's profile details (username, email, names, role, phone)"),
            ("can_change_staff_status", "Can activate/deactivate staff user accounts"),
            ("can_view_staff_list", "Can view the list of all staff users in the admin area"),
            ("can_reset_staff_password", "Can reset staff user passwords"),
        ]

    def __str__(self):
        return f"{self.user.first_name} {self.user.last_name} ({self.role})"

# =============================================================================
# PATIENT CORE MODELS (Alphabetical)
# =============================================================================

class Patient(models.Model):
    BLOOD_GROUP_CHOICES = [
        ('A+', 'A+'), ('A-', 'A-'),
        ('B+', 'B+'), ('B-', 'B-'),
        ('AB+', 'AB+'), ('AB-', 'AB-'),
        ('O+', 'O+'), ('O-', 'O-'),
    ]
    STATUS_CHOICES = [
        ('critical', 'Critical'),
        ('recovered', 'Recovered'),
        ('stable', 'Stable'),
    ]
    
    RELATIONSHIP_CHOICES = [
        ('Spouse', 'Spouse'),
        ('Father', 'Father'),
        ('Mother', 'Mother'),
        ('Son', 'Son'),
        ('Daughter', 'Daughter'),
        ('Brother', 'Brother'),
        ('Sister', 'Sister'),
        ('Guardian', 'Guardian'),
        ('Friend', 'Friend'),
        ('Other', 'Other'),
    ]

    # Core Demographics
    address = models.TextField()
    blood_group = models.CharField(max_length=3, choices=BLOOD_GROUP_CHOICES, default='O+')
    date_of_birth = models.DateField()
    date_registered = models.DateTimeField(auto_now_add=True)
    email = models.EmailField(blank=True, null=True)
    first_time = models.CharField(max_length=20, blank=True)
    full_name = models.CharField(max_length=200)
    gender = models.CharField(max_length=10)
    id_number = models.CharField(max_length=100, blank=True)
    id_type = models.CharField(max_length=20, blank=True)
    marital_status = models.CharField(max_length=20)
    nationality = models.CharField(max_length=50)
    phone = models.CharField(max_length=15)
    photo = models.ImageField(upload_to='patient_photos/', blank=True, null=True)
    state_of_origin = models.CharField(max_length=50, blank=True)

    # Next of Kin - EXISTING FIELDS
    next_of_kin_name = models.CharField(max_length=100)
    next_of_kin_phone = models.CharField(max_length=15)
    
    # Next of Kin - ADD THESE NEW FIELDS
    next_of_kin_relationship = models.CharField(max_length=20, choices=RELATIONSHIP_CHOICES, blank=True, null=True, default='Ade')
    next_of_kin_email = models.EmailField(blank=True, null=True)
    next_of_kin_address = models.TextField(blank=True, null=True)

    # Medical Status
    diagnosis = models.TextField(blank=True, null=True)
    is_inpatient = models.BooleanField(default=False)
    medication = models.TextField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    referred_by = models.CharField(max_length=100, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='stable')
    
    def __str__(self):
        return f"{self.full_name}"

# =============================================================================
# APPOINTMENT & REFERRAL MODELS (Alphabetical)
# =============================================================================

class Appointment(models.Model):
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE)
    scheduled_time = models.DateTimeField()

    def __str__(self):
        return f"{self.patient.full_name} - {self.department}"

class Referral(models.Model):
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    notes = models.TextField()
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.patient.full_name} - {self.department.name}"

# =============================================================================
# ADMISSION MODELS (Alphabetical)
# =============================================================================

class Admission(models.Model):
    STATUS_CHOICES = [
        ('Admitted', 'Admitted'),
        ('Discharged', 'Discharged'),
    ]

    admission_date = models.DateField(default=timezone.now)
    admitted_by = models.CharField(max_length=100, blank=True, null=True)
    admitted_on = models.DateField(default=date.today)
    discharge_date = models.DateField(blank=True, null=True)
    discharge_notes = models.TextField(blank=True, null=True)
    discharged_by = models.CharField(max_length=100, blank=True, null=True)
    doctor_assigned = models.CharField(max_length=100)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Admitted')
    time = models.TimeField(auto_now_add=True)

    def __str__(self):
        return f"Admission for {self.patient.full_name} - {self.status}"

# Note: Removed redundant PatientAdmission model as it duplicates Admission functionality

# =============================================================================
# MEDICAL CARE MODELS (Alphabetical)
# =============================================================================

class CarePlan(models.Model):
    clinical_findings = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE)
    plan_of_care = models.TextField()

    def __str__(self):
        return f"Care Plan for {self.patient.full_name} on {self.created_at:%Y-%m-%d}"

class Consultation(models.Model):
    admission = models.ForeignKey(Admission, null=True, blank=True, on_delete=models.SET_NULL)
    advice = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    diagnosis_summary = models.TextField()
    doctor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='consultations')
    symptoms = models.TextField()

    def __str__(self):
        return f"Consultation for {self.patient.full_name} on {self.created_at:%Y-%m-%d}"

class NursingNote(models.Model):
    NOTE_TYPE_CHOICES = [
        ('care_plan', 'Care Plan Update'),
        ('medication', 'Medication Administered'),
        ('observation', 'Observation'),
        ('other', 'Other'),
        ('response', 'Patient Response'),
    ]

    created_at = models.DateTimeField(auto_now_add=True)
    follow_up = models.TextField(blank=True, null=True)
    note_datetime = models.DateTimeField(default=timezone.now)
    note_type = models.CharField(max_length=50, choices=NOTE_TYPE_CHOICES)
    notes = models.TextField()
    nurse = models.CharField(max_length=100)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='nursing_notes')
    patient_status = models.CharField(max_length=50, blank=True, null=True)

    def __str__(self):
        return f"Nursing Note for {self.patient.full_name} on {self.note_datetime.strftime('%Y-%m-%d %H:%M')}"

class Prescription(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    instructions = models.TextField()
    medication = models.CharField(max_length=200)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='prescriptions')
    prescribed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    start_date = models.DateField()

    def __str__(self):
        return f"{self.medication} for {self.patient.full_name}"

class Vitals(models.Model):
    bmi = models.FloatField(null=True, blank=True)
    blood_pressure = models.CharField(max_length=20, null=True, blank=True)
    height = models.FloatField(null=True, blank=True)
    notes = models.TextField(blank=True, null=True)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE)
    pulse = models.IntegerField(null=True, blank=True)
    recorded_at = models.DateTimeField()
    recorded_by = models.CharField(max_length=100)
    respiratory_rate = models.IntegerField(null=True, blank=True)
    temperature = models.FloatField(null=True, blank=True)
    weight = models.FloatField(null=True, blank=True)

    def __str__(self):
        return f"{self.patient.full_name} Vitals @ {self.recorded_at}"

# =============================================================================
# LABORATORY MODELS (Consolidated & Alphabetical)
# =============================================================================

class LabResultFile(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE)
    result_file = models.FileField(upload_to='lab_results/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return f"Result for {self.patient.full_name} uploaded on {self.uploaded_at.date()}"

class LabTest(models.Model):
    """Main lab test model - consolidated from multiple test models"""

    STATUS_CHOICES = [
        ('cancelled', 'Cancelled'),
        ('completed', 'Completed'),
        ('in_progress', 'In Progress'),
        ('pending', 'Pending'),
    ]

    # Optional grouping field for bulk requests
    test_request_id = models.UUIDField(default=uuid4, editable=False, db_index=True)

    # Test identification
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='lab_tests')
    category = models.ForeignKey('TestCategory', on_delete=models.CASCADE, related_name='test_category')
    test_name = models.CharField(max_length=100)
    normal_range = models.CharField(max_length=100, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)    
    result_value = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    testcompleted = models.BooleanField(default=0)
    doctor_comments = models.IntegerField(null=True, blank=True)
    labresulttestid = models.IntegerField(null=True, blank=True)

    # Timing
    date_performed = models.DateTimeField(null=True, blank=True)
    requested_at = models.DateTimeField(auto_now_add=True)
    submitted_on = models.DateField(default=timezone.now)
    time = models.TimeField(auto_now_add=True)

    # Personnel
    doctor_name = models.CharField(max_length=100, blank=True)
    performed_by = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True, related_name='performed_tests')
    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='recorded_tests')
    requested_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='requested_tests')

    # Additional fields for complex tests
    instructions = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['-requested_at']

    def __str__(self):
        return f"{self.patient.full_name} - {self.test_name} ({self.status})"

class TestCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        verbose_name_plural = "Test Categories"

    def __str__(self):
        return self.name

class TestSubcategory(models.Model):
    category = models.ForeignKey(TestCategory, related_name='subcategories', on_delete=models.CASCADE)
    name = models.CharField(max_length=100)

    class Meta:
        verbose_name_plural = "Test Subcategories"

    def __str__(self):
        return f"{self.category.name} - {self.name}"

# =============================================================================
# STAFF MANAGEMENT MODELS (Alphabetical)
# =============================================================================

class Attendance(models.Model):
    STATUS_CHOICES = [
        ('Absent', 'Absent'),
        ('On Leave', 'On Leave'),
        ('Present', 'Present'),
    ]

    date = models.DateTimeField(default=timezone.now)
    staff = models.ForeignKey(User, on_delete=models.CASCADE, related_name='attendances')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)

    class Meta:
        ordering = ['-date']
        unique_together = ('staff', 'date')

    def __str__(self):
        return f"{self.staff.get_full_name() or self.staff.username} - {self.date} - {self.status}"

class HandoverLog(models.Model):
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    notes = models.TextField()
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Handover: {self.patient.full_name} by {self.author}"

class Shift(models.Model):
    SHIFT_CHOICES = [
        ('Afternoon', 'Afternoon'),
        ('Morning', 'Morning'),
        ('Night', 'Night'),
    ]
    name = models.CharField(max_length=20, choices=SHIFT_CHOICES, unique=True)

    def __str__(self):
        return self.name

class ShiftAssignment(models.Model):
    date = models.DateField(default=timezone.now)
    shift = models.ForeignKey(Shift, on_delete=models.CASCADE)
    staff = models.ForeignKey(User, on_delete=models.CASCADE, related_name='shift_assignments')

    class Meta:
        unique_together = ('staff', 'date')

    def __str__(self):
        return f"{self.staff.get_full_name() or self.staff.username} - {self.shift.name} on {self.date}"

class StaffTransition(models.Model):
    TRANSITION_CHOICES = [
        ('offboarding', 'Offboarding'),
        ('onboarding', 'Onboarding'),
    ]

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    date = models.DateField()
    full_name = models.CharField(max_length=200)
    notes = models.TextField(blank=True, null=True)
    transition_type = models.CharField(max_length=20, choices=TRANSITION_CHOICES)

    def __str__(self):
        return f"{self.full_name} - {self.transition_type} on {self.date}"

# =============================================================================
# EMERGENCY & ALERTS (Alphabetical)
# =============================================================================

class EmergencyAlert(models.Model):
    acknowledged_by = models.ManyToManyField(User, blank=True, related_name='alerts_acknowledged')
    message = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    triggered_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='alerts_triggered')

    def __str__(self):
        return f"Alert: {self.message[:30]}..."

# =============================================================================
# FINANCIAL MODELS (Alphabetical)
# =============================================================================

class Budget(models.Model):
    allocated_amount = models.DecimalField(max_digits=12, decimal_places=2)
    category = models.ForeignKey('ExpenseCategory', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    month = models.PositiveIntegerField(choices=[(i, i) for i in range(1, 13)], null=True, blank=True)
    spent_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    year = models.PositiveIntegerField()

    class Meta:
        unique_together = ('category', 'year', 'month')

    def percentage_used(self):
        if self.allocated_amount > 0:
            return (self.spent_amount / self.allocated_amount) * 100
        return 0

    def remaining_amount(self):
        return self.allocated_amount - self.spent_amount

    def __str__(self):
        period = f"{self.year}" if not self.month else f"{self.month}/{self.year}"
        return f"{self.category.name} Budget - {period}"

class BillItem(models.Model):
    bill = models.ForeignKey('PatientBill', on_delete=models.CASCADE, related_name='items')
    description = models.CharField(max_length=200)
    quantity = models.PositiveIntegerField(default=1)
    service_type = models.ForeignKey('ServiceType', on_delete=models.CASCADE)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)

    def save(self, *args, **kwargs):
        self.total_price = self.quantity * self.unit_price
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.description} - ₦{self.total_price}"

class Expense(models.Model):
    EXPENSE_STATUS_CHOICES = [
        ('approved', 'Approved'),
        ('paid', 'Paid'),
        ('pending', 'Pending Approval'),
        ('rejected', 'Rejected'),
    ]

    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_expenses')
    category = models.ForeignKey('ExpenseCategory', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    description = models.CharField(max_length=200)
    expense_date = models.DateField()
    notes = models.TextField(blank=True, null=True)
    receipt_number = models.CharField(max_length=50, blank=True, null=True)
    requested_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='requested_expenses')
    status = models.CharField(max_length=20, choices=EXPENSE_STATUS_CHOICES, default='pending')
    vendor = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return f"{self.description} - ₦{self.amount}"

class ExpenseCategory(models.Model):
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        verbose_name_plural = "Expense Categories"

    def __str__(self):
        return self.name

class PatientBill(models.Model):
    BILL_STATUS_CHOICES = [
        ('cancelled', 'Cancelled'),
        ('paid', 'Fully Paid'),
        ('partial', 'Partially Paid'),
        ('pending', 'Pending'),
        ('refunded', 'Refunded'),
    ]

    bill_number = models.CharField(max_length=20, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    final_amount = models.DecimalField(max_digits=10, decimal_places=2)
    notes = models.TextField(blank=True, null=True)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='bills')
    status = models.CharField(max_length=20, choices=BILL_STATUS_CHOICES, default='pending')
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.00'))])

    def amount_paid(self):
        return self.payments.filter(status='completed').aggregate(
            total=models.Sum('amount')
        )['total'] or Decimal('0.00')

    def outstanding_amount(self):
        return self.final_amount - self.amount_paid()

    def save(self, *args, **kwargs):
        if not self.bill_number:
            from datetime import date
            today = date.today()
            count = PatientBill.objects.filter(created_at__date=today).count() + 1
            self.bill_number = f"BILL-{today.strftime('%Y%m%d')}-{count:04d}"
        
        self.final_amount = self.total_amount - self.discount_amount
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.bill_number} - {self.patient.full_name}"

class Payment(models.Model):
    PAYMENT_METHOD_CHOICES = [
        ('cash', 'Cash'),
        ('cheque', 'Cheque'),
        ('online', 'Online Payment'),
        ('pos', 'POS'),
        ('transfer', 'Bank Transfer'),
    ]
    PAYMENT_STATUS_CHOICES = [
        ('cancelled', 'Cancelled'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('pending', 'Pending'),
    ]

    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    bill = models.ForeignKey(PatientBill, on_delete=models.CASCADE, related_name='payments', null=True, blank=True)
    notes = models.TextField(blank=True, null=True)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='payments')
    payment_date = models.DateTimeField(auto_now_add=True)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    payment_reference = models.CharField(max_length=100, blank=True, null=True)
    processed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='completed')

    def __str__(self):
        return f"Payment ₦{self.amount} - {self.patient.full_name}"

class PaymentUpload(models.Model):
    STATUS_CHOICES = [
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('processing', 'Processing'),
    ]

    error_log = models.TextField(blank=True, null=True)
    failed_records = models.PositiveIntegerField(default=0)
    file_name = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='processing')
    successful_records = models.PositiveIntegerField(default=0)
    total_records = models.PositiveIntegerField(default=0)
    upload_date = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return f"Upload: {self.file_name} - {self.status}"

class ServiceType(models.Model):
    default_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name

# =============================================================================
# DOCTORS COMMENT MODELS
# =============================================================================

class DoctorComments(models.Model):
    comments = models.TextField()
    date = models.DateTimeField(default=timezone.now)
    doctor_name = models.CharField(max_length=100)
    labtech_name = models.CharField(max_length=100)

    def __str__(self):
        return f"Comment by Dr. {self.doctor_name} on {self.date.strftime('%Y-%m-%d')}"