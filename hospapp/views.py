from multiprocessing import context
from django.contrib import messages
from django.contrib.auth.models import User
from django.shortcuts import render, redirect, get_object_or_404, HttpResponse
from .models import Patient, Staff, Admission, Vitals, NursingNote, Consultation, Prescription, CarePlan, LabTest, LabResultFile, Department, TestCategory, ShiftAssignment, Attendance, StaffTransition, TestSubcategory, Payment, PatientBill, Budget, Expense, HandoverLog, ExpenseCategory, EmergencyAlert, Patient, Appointment, Referral, BillItem,IVFPackage, TreatmentLocation, IVFRecord, IVFProgressUpdate
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import logout
from django.db import models
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.http import JsonResponse
from django.utils.dateparse import parse_date
from django.db.models import Q
from django.views.decorators.http import require_GET
from django.shortcuts import get_object_or_404, render
import json
from django.db.models import Q, Max # Import Max for aggregation
from django.db.models.functions import Coalesce
from datetime import datetime, date
from django.db.models import Sum, F
from django.utils.timezone import localdate, now
from django.utils import timezone
from django.db.models.functions import TruncDate
from django.views.decorators.http import require_http_methods
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Count
from .models import Admission
from django.utils import timezone
from datetime import timedelta
from django.db import IntegrityError, DatabaseError
from decimal import Decimal
from collections import defaultdict
from dateutil.relativedelta import relativedelta
today = timezone.now().date()
from django.urls import reverse
import csv
from reportlab.pdfgen import canvas
from uuid import uuid4
from django.core.files.storage import default_storage
import csv
from io import BytesIO
from datetime import date, datetime, timedelta
from django.db.models import Case, When, Value, IntegerField, F, Q, Count, Avg
from calendar import monthrange


import string
import secrets
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from django.db.models import Q
from django.http import HttpResponse # Ensure HttpResponse is imported
from django.views.decorators.http import require_GET, require_POST


import logging

logger = logging.getLogger(__name__)

# Create your views here.
ROLE_DASHBOARD_PATHS = {
    'nurse': 'n/home',
    'doctor': 'd/home',
    'lab': 'l/home',
    'pharmacy': 'p/home',
    'admin': 'ad/home',
    'hr': 'hr/home',
    'receptionist': 'r/home',
    'account' : 'a/home'
}

def home(request):
    if request.method == "POST":
        username = request.POST["username"]
        password = request.POST["password"]
        user = authenticate(request, username=username, password=password)

        if user:
            login(request, user)
            try:
                role = user.staff.role
                dashboard_path = ROLE_DASHBOARD_PATHS.get(role)
                if dashboard_path:
                    return redirect(f'/{dashboard_path}',context )
                else:
                    messages.error(request, "Role not recognized.")
            except AttributeError:
                messages.error(request, "User profile is incomplete.")
        else:
            messages.error(request, "Invalid credentials!")
            
    return render(request, "home.html")

def register(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        confirm_password = request.POST.get("confirm_password")
        email = request.POST.get("email")
        first_name = request.POST.get("first_name")
        last_name = request.POST.get("last_name")
        gender = request.POST.get("gender")
        phone_number = request.POST.get("phone_number")
        address = request.POST.get("address")
        photo = request.FILES.get("photo")

        if password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return redirect("register")

        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists.")
            return redirect("register")

        user = User.objects.create_user(
            username=username,
            password=password,
            email=email,
            first_name=first_name,
            last_name=last_name,
        )

        # Create Profile with default role
        Staff.objects.create(
            user=user,
            gender=gender,
            role="receptionist",
            phone_number=phone_number,
            address=address,
            photo=photo,
        )

        messages.success(request, "Account created successfully. Please log in.")
        return redirect("home")

    return render(request, "register.html")

def logout_view(request):
    logout(request)
    return redirect('home')


''' ############################################################################################################################ Nurses View ############################################################################################################################ '''

@login_required(login_url='home')
def nurses(request):
    user = request.user
    today = timezone.now().date()
    
    # ✅ Get nurse profile
    nurse_profile = Staff.objects.filter(user=user, role='nurse').first()
    
    # ✅ Patient Statistics
    active_patients = Patient.objects.filter(is_inpatient=True).count()
    critical_patients = Patient.objects.filter(status='critical').count()
    stable_patients = Patient.objects.filter(status='stable').count()
    recovered_patients = Patient.objects.filter(status='recovered').count()
    
    # ✅ Today's activities
    todays_admissions = Admission.objects.filter(
        admission_date=today,
        status='Admitted'
    ).count()
    
    # ✅ Recent nursing notes (all nurses for overview, but highlight current nurse's notes)
    recent_notes = NursingNote.objects.select_related('patient', 'nurse').order_by('-note_datetime')[:10]
    
    # ✅ My recent activities (nurse-specific)
    my_recent_notes = NursingNote.objects.filter(
        nurse=user
    ).select_related('patient').order_by('-note_datetime')[:5]
    
    # ✅ Patients requiring follow-up (based on nursing notes)
    patients_needing_followup = NursingNote.objects.filter(
        follow_up__isnull=False
    ).exclude(follow_up='').select_related('patient').order_by('-note_datetime')[:5]
    
    # ✅ Critical patients details for immediate attention
    critical_patients_list = Patient.objects.filter(
        status='critical',
        is_inpatient=True
    ).order_by('-date_registered')[:5]
    
    # ✅ Recent vitals recorded (last 24 hours)
    recent_vitals = Vitals.objects.filter(
        recorded_at__gte=timezone.now() - timedelta(hours=24)
    ).select_related('patient', 'recorded_by').order_by('-recorded_at')[:8]
    
    # ✅ Today's discharges
    todays_discharges = Admission.objects.filter(
        discharge_date=today,
        status='Discharged'
    ).count()
    
    # ✅ Patients admitted today (detailed)
    todays_new_admissions = Admission.objects.filter(
        admission_date=today,
        status='Admitted'
    ).select_related('patient', 'admitted_by').order_by('-time')[:5]
    
    # ✅ My shift information
    my_shift_today = ShiftAssignment.objects.filter(
        staff=user,
        date=today
    ).first()
    
    # ✅ Pending handovers (received by current nurse)
    pending_handovers = HandoverLog.objects.filter(
        recipient=user,
        timestamp__date=today
    ).select_related('patient', 'author').order_by('-timestamp')[:5]
    
    # ✅ Emergency alerts (recent)
    recent_alerts = EmergencyAlert.objects.filter(
        timestamp__gte=timezone.now() - timedelta(hours=24)
    ).exclude(acknowledged_by=user).order_by('-timestamp')[:3]
    
    # ✅ Patients I've worked with recently (last 7 days)
    my_recent_patients = Patient.objects.filter(
        Q(nursing_notes__nurse=user) | 
        Q(vitals__recorded_by=user)
    ).filter(
        Q(nursing_notes__created_at__gte=timezone.now() - timedelta(days=7)) |
        Q(vitals__recorded_at__gte=timezone.now() - timedelta(days=7))
    ).distinct().order_by('-date_registered')[:10]
    
    # ✅ Statistics for current nurse
    my_stats = {
        'notes_today': NursingNote.objects.filter(
            nurse=user,
            created_at__date=today
        ).count(),
        'vitals_recorded_today': Vitals.objects.filter(
            recorded_by=user,
            recorded_at__date=today
        ).count(),
        'patients_cared_this_week': Patient.objects.filter(
            Q(nursing_notes__nurse=user) | Q(vitals__recorded_by=user)
        ).filter(
            Q(nursing_notes__created_at__gte=timezone.now() - timedelta(days=7)) |
            Q(vitals__recorded_at__gte=timezone.now() - timedelta(days=7))
        ).distinct().count()
    }
    
    # ✅ Attendance status
    my_attendance_today = Attendance.objects.filter(
        staff=user,
        date__date=today
    ).first()

    # ⭐ NEW: Get all active patients with their latest vital signs for status monitoring
    # This query annotates each active patient with the timestamp of their most recent vital sign.
    active_patients_details = Patient.objects.filter(is_inpatient=True).annotate(
        last_vitals_recorded_at=Coalesce(Max('vitals__recorded_at'), None)
    ).order_by('full_name')
    
    context = {
        # Profile & Authentication
        'nurse_profile': nurse_profile,
        'user': user,
        
        # Dashboard Statistics
        'active_patients': active_patients,
        'critical_patients': critical_patients,
        'stable_patients': stable_patients,
        'recovered_patients': recovered_patients,
        'todays_admissions': todays_admissions,
        'todays_discharges': todays_discharges,
        
        # Recent Activities
        'recent_notes': recent_notes,
        'my_recent_notes': my_recent_notes,
        'recent_vitals': recent_vitals,
        'todays_new_admissions': todays_new_admissions,
        
        # Priority Items
        'critical_patients_list': critical_patients_list,
        'patients_needing_followup': patients_needing_followup,
        'pending_handovers': pending_handovers,
        'recent_alerts': recent_alerts,
        
        # Personal Work Data
        'my_recent_patients': my_recent_patients,
        'my_stats': my_stats,
        'my_shift_today': my_shift_today,
        'my_attendance_today': my_attendance_today,
        
        # Utility
        'today': today,
        'current_time': timezone.now(),
        'patients': Patient.objects.all(), # Keep for generic patient lists in modals
        'doctors': Staff.objects.select_related('user').filter(Q(role='doctor')),

        # ⭐ NEW: Data for patient status monitoring (excluding rooms)
        'active_patients_details': active_patients_details,
    }
    
    return render(request, 'nurses/index.html', context)

@login_required(login_url='home')                          
def vitals(request):
    context = {
        'patients': Patient.objects.all(),
    }
    return render(request, 'nurses/vital_signs.html', context)

@login_required(login_url='home')
def nursing_actions(request):
    context = {
        'patients': Patient.objects.all(),
        'admitted_patients': Patient.objects.filter(is_inpatient=True),
        'doctors': Staff.objects.select_related('user').filter(Q(role='doctor')),
        'nurses': Staff.objects.select_related('user').filter(Q(role='nurse')).exclude(user=request.user),
        'departments': Department.objects.all(),
    }
    return render(request, 'nurses/nursing_actions.html', context)

@login_required(login_url='home')
def nurse_reports_dashboard(request):
    # Fetch all staff who are nurses or doctors for the dropdown
    staff_users = Staff.objects.filter(Q(role='nurse') | Q(role='doctor')).select_related('user').order_by('user__first_name')
    
    users_data = [
        {'id': staff.user.id, 'full_name': staff.user.get_full_name() or staff.user.username}
        for staff in staff_users
    ]

    context = {
        'users': users_data,
    }
    return render(request, 'nurses/reports.html', context)


@login_required(login_url='home')
def generate_nurse_report(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        user_id = data.get('user_id')
        report_type = data.get('report_type')
        start_date_str = data.get('start_date')
        end_date_str = data.get('end_date')

        # Convert date strings to datetime objects
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date() if start_date_str else None
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date() if end_date_str else None

        user_filter = Q(pk=user_id) if user_id else Q() # Filter by user if selected

        report_data = []
        headers = []

        if report_type == 'patient_list':
            patients = Patient.objects.filter(user_filter).order_by('-date_registered')
            headers = ['Patient ID', 'Full Name', 'Gender', 'Date of Birth', 'Phone', 'Email', 'Registered By', 'Date Registered']
            for patient in patients:
                report_data.append({
                    'patient_id': patient.patient_id,
                    'full_name': patient.full_name,
                    'gender': patient.gender,
                    'date_of_birth': patient.date_of_birth.strftime('%Y-%m-%d'),
                    'phone': patient.phone,
                    'email': patient.email or 'N/A',
                    'registered_by': patient.registered_by.get_full_name() if patient.registered_by else 'N/A',
                    'date_registered': patient.date_registered.strftime('%Y-%m-%d %H:%M'),
                })
        
        elif report_type == 'admitted_patients':
            admissions = Admission.objects.filter(user_filter).order_by('-admission_date')
            if start_date and end_date:
                admissions = admissions.filter(admission_date__range=[start_date, end_date])
            
            headers = ['Patient', 'Admission Date', 'Admission Reason', 'Admitted By', 'Status']
            for admission in admissions:
                report_data.append({
                    'patient_name': admission.patient.full_name,
                    'admission_date': admission.admission_date.strftime('%Y-%m-%d'),
                    'admission_reason': admission.admission_reason or 'N/A',
                    'admitted_by': admission.admitted_by.get_full_name() if admission.admitted_by else 'N/A',
                    'status': admission.status,
                })

        elif report_type == 'vitals':
            vitals = Vitals.objects.filter(recorded_by__in=Staff.objects.filter(Q(role='nurse') | Q(role='doctor'), user_filter).values('user')).order_by('-recorded_at')
            if start_date and end_date:
                vitals = vitals.filter(recorded_at__date__range=[start_date, end_date])

            headers = ['Patient', 'Temperature (°C)', 'Blood Pressure', 'Pulse', 'BMI', 'Recorded By', 'Recorded At']
            for vital in vitals:
                report_data.append({
                    'patient_name': vital.patient.full_name,
                    'temperature': vital.temperature or 'N/A',
                    'blood_pressure': vital.blood_pressure or 'N/A',
                    'pulse': vital.pulse or 'N/A',
                    'bmi': f"{vital.bmi:.2f}" if vital.bmi else 'N/A',
                    'recorded_by': vital.recorded_by.get_full_name() if vital.recorded_by else 'N/A',
                    'recorded_at': vital.recorded_at.strftime('%Y-%m-%d %H:%M'),
                })

        elif report_type == 'nurse_notes':
            nursing_notes = NursingNote.objects.filter(nurse__in=Staff.objects.filter(Q(role='nurse'), user_filter).values('user')).order_by('-created_at')
            if start_date and end_date:
                nursing_notes = nursing_notes.filter(created_at__date__range=[start_date, end_date])
            
            headers = ['Patient', 'Note Type', 'Notes', 'Nurse', 'Created At']
            for note in nursing_notes:
                report_data.append({
                    'patient_name': note.patient.full_name,
                    'note_type': note.get_note_type_display(),
                    'notes': note.notes,
                    'nurse_name': note.nurse.get_full_name() if note.nurse else 'N/A',
                    'created_at': note.created_at.strftime('%Y-%m-%d %H:%M'),
                })

        elif report_type == 'referrals':
            referrals = Referral.objects.filter(referred_by__in=Staff.objects.filter(Q(role='nurse') | Q(role='doctor'), user_filter).values('user')).order_by('-created_at')
            if start_date and end_date:
                referrals = referrals.filter(created_at__date__range=[start_date, end_date])
            
            headers = ['Patient', 'Department', 'Notes', 'Referred By', 'Created At']
            for referral in referrals:
                report_data.append({
                    'patient_name': referral.patient.full_name,
                    'department': referral.department.name,
                    'notes': referral.notes,
                    'referred_by': referral.referred_by.get_full_name() if referral.referred_by else 'N/A',
                    'created_at': referral.created_at.strftime('%Y-%m-%d %H:%M'),
                })

        elif report_type == 'consultations':
            consultations = Consultation.objects.filter(doctor__in=Staff.objects.filter(Q(role='doctor'), user_filter).values('user')).order_by('-created_at')
            if start_date and end_date:
                consultations = consultations.filter(created_at__date__range=[start_date, end_date])
            
            headers = ['Patient', 'Doctor', 'Symptoms', 'Diagnosis Summary', 'Advice', 'Consultation Date']
            for consultation in consultations:
                report_data.append({
                    'patient_name': consultation.patient.full_name,
                    'doctor_name': consultation.doctor.get_full_name() if consultation.doctor else 'N/A',
                    'symptoms': consultation.symptoms,
                    'diagnosis_summary': consultation.diagnosis_summary,
                    'advice': consultation.advice,
                    'created_at': consultation.created_at.strftime('%Y-%m-%d %H:%M'),
                })
        
        elif report_type == 'prescriptions':
            prescriptions = Prescription.objects.filter(prescribed_by__in=Staff.objects.filter(Q(role='doctor'), user_filter).values('user')).order_by('-created_at')
            if start_date and end_date:
                prescriptions = prescriptions.filter(created_at__date__range=[start_date, end_date])
            
            headers = ['Patient', 'Medication', 'Instructions', 'Prescribed By', 'Start Date', 'Prescription Date']
            for prescription in prescriptions:
                report_data.append({
                    'patient_name': prescription.patient.full_name,
                    'medication': prescription.medication,
                    'instructions': prescription.instructions,
                    'prescribed_by': prescription.prescribed_by.get_full_name() if prescription.prescribed_by else 'N/A',
                    'start_date': prescription.start_date.strftime('%Y-%m-%d'),
                    'created_at': prescription.created_at.strftime('%Y-%m-%d %H:%M'),
                })

        elif report_type == 'lab_tests':
            lab_tests = LabTest.objects.filter(Q(requested_by__in=Staff.objects.filter(Q(role='doctor') | Q(role='nurse'), user_filter).values('user')) |
                                                Q(performed_by__in=Staff.objects.filter(Q(role='lab'), user_filter).values('user'))).order_by('-requested_at')
            if start_date and end_date:
                lab_tests = lab_tests.filter(requested_at__date__range=[start_date, end_date])
            
            headers = ['Patient', 'Test Name', 'Category', 'Status', 'Result Value', 'Requested By', 'Performed By', 'Requested At']
            for test in lab_tests:
                report_data.append({
                    'patient_name': test.patient.full_name,
                    'test_name': test.test_name,
                    'category': test.category.name if test.category else 'N/A',
                    'status': test.get_status_display(),
                    'result_value': test.result_value or 'N/A',
                    'requested_by': test.requested_by.get_full_name() if test.requested_by else 'N/A',
                    'performed_by': test.performed_by.get_full_name() if test.performed_by else 'N/A',
                    'requested_at': test.requested_at.strftime('%Y-%m-%d %H:%M'),
                })
        
        elif report_type == 'handovers':
            handovers = HandoverLog.objects.filter(Q(author__in=Staff.objects.filter(Q(role='nurse') | Q(role='doctor'), user_filter).values('user')) |
                                                    Q(recipient__in=Staff.objects.filter(Q(role='nurse') | Q(role='doctor'), user_filter).values('user'))).order_by('-timestamp')
            if start_date and end_date:
                handovers = handovers.filter(timestamp__date__range=[start_date, end_date])
            
            headers = ['Patient', 'Author', 'Recipient', 'Notes', 'Timestamp']
            for handover in handovers:
                report_data.append({
                    'patient_name': handover.patient.full_name,
                    'author': handover.author.get_full_name() if handover.author else 'N/A',
                    'recipient': handover.recipient.get_full_name() if handover.recipient else 'N/A',
                    'notes': handover.notes,
                    'timestamp': handover.timestamp.strftime('%Y-%m-%d %H:%M'),
                })

        return JsonResponse({'headers': headers, 'data': report_data})
    return JsonResponse({'error': 'Invalid request method'}, status=400)

@login_required
@require_http_methods(["GET"])
def nurse_view_ivf_progress(request):
    
    context = {
        'all_ivf_records': IVFRecord.objects.all().select_related('patient', 'ivf_package', 'treatment_location').order_by('-created_on'),
    }
    return render(request, 'nurses/ivf_progress.html', context)

###### Form Actions ######
@csrf_exempt
def record_vitals(request):
    if request.method == 'POST':
        try:
            Vitals.objects.create(
                patient_id=request.POST.get('patient_id'),
                recorded_at=timezone.now(),
                temperature=request.POST.get('temperature') or None,
                blood_pressure=request.POST.get('blood_pressure'),
                pulse=request.POST.get('pulse') or None,
                respiratory_rate=request.POST.get('respiratory_rate') or None,
                weight=request.POST.get('weight') or None,
                height=request.POST.get('height') or None,
                bmi=request.POST.get('bmi') or None,
                notes=request.POST.get('notes'),
                recorded_by=request.user
            )
            messages.success(request, "Vitals recorded successfully.")
        except Exception as e:
            messages.error(request, f"Error recording vitals: {str(e)}")

    referer = request.META.get('HTTP_REFERER', '/')
    return redirect(referer)

@csrf_exempt
@login_required(login_url='home')
def admit_patient_nurse(request):
    referer = request.META.get('HTTP_REFERER', '/')
    if request.method == 'POST':
        patient_id = request.POST.get('patient_id')
        doctor_id = request.POST.get('doctor')
        admission_reason = request.POST.get('admission_reason')

        # Validate input
        if not patient_id or not doctor_id or not admission_reason:
            messages.error(request, "All fields are required.")
            return redirect(referer)

        try:
            patient = get_object_or_404(Patient, id=int(patient_id))
        except (ValueError, TypeError):
            messages.error(request, "Invalid patient selection.")
            return redirect(referer)

        if Admission.objects.filter(patient=patient, status='Admitted').exists():
            messages.warning(request, f"{patient.full_name} is already admitted.")
            return redirect(referer)

        # Prepare admission details
        admission_details = f"Reason for Admission: {admission_reason}"

        try:
            doctor_user = User.objects.get(id=int(doctor_id))
        except (User.DoesNotExist, ValueError, TypeError):
            messages.error(request, "Selected doctor not found.")
            return redirect(referer)

        # Create admission
        Admission.objects.create(
            patient=patient,
            admission_date=timezone.now().date(),
            admitted_on=timezone.now().date(),
            doctor_assigned=doctor_user,
            admitted_by=request.user,
            admission_reason=admission_details,
            status='Admitted'
        )

        # Update patient status
        patient.is_inpatient = True
        patient.status = 'stable'
        patient.save()

        messages.success(request, f"{patient.full_name} admitted successfully.")        
        return redirect(referer)

    return redirect(referer)

@csrf_exempt  # Optional in development, but use CSRF tokens in production
@login_required(login_url='home')
def discharge_patient(request):
    referer = request.META.get('HTTP_REFERER', '/')
    if request.method == 'POST':
        patient_id = request.POST.get('patient_id')
        summary = request.POST.get('discharge_summary')
        followup_date = request.POST.get('followup_date')
        followup_doctor = request.POST.get('followup_doctor')

        # Validate patient_id
        if not patient_id or not patient_id.strip():
            messages.error(request, "Please select a patient to discharge.")
            return redirect(referer)

        try:
            patient = get_object_or_404(Patient, id=int(patient_id))
        except (ValueError, TypeError):
            messages.error(request, "Invalid patient selection.")
            return redirect(referer)

        admission = Admission.objects.filter(patient=patient, status='Admitted').first()
        if not admission:
            messages.error(request, "No active admission found for this patient.")
            return redirect(referer)

        # Compile discharge summary
        full_summary = f"Discharge Summary:\n{summary}"
        if followup_date:
            full_summary += f"\nFollow-up Date: {followup_date}"
        if followup_doctor:
            full_summary += f"\nFollow-up Doctor: {followup_doctor}"

        # Update patient status
        patient.is_inpatient = False
        patient.status = 'recovered'
        patient.save()

        # Update admission record
        admission.status = 'Discharged'
        admission.discharge_date = timezone.now().date()
        admission.discharge_notes = full_summary
        admission.discharged_by = request.user
        admission.save()

        messages.success(request, f"{patient.full_name} has been discharged successfully.")
        return redirect(referer)

    return redirect(referer)


@csrf_exempt
@login_required(login_url='home')
def update_patient_status(request):
    if request.method == 'POST':
        patient_id = request.POST.get('patient_id')
        new_status = request.POST.get('status') #
        note_text = request.POST.get('notes') #
        next_check = request.POST.get('next_check') #

        patient = get_object_or_404(Patient, id=patient_id)
        
        # Combine monitoring info for the nursing note
        monitoring_notes = f"Patient status set to: {new_status}.\n{note_text}"
        if next_check:
            monitoring_notes += f"\nNext Check scheduled for: {timezone.datetime.fromisoformat(next_check).strftime('%Y-%m-%d %H:%M')}"

        # Create a detailed nursing note for the status update
        NursingNote.objects.create(
            patient=patient,
            nurse=request.user.get_full_name() or request.user.username,
            note_type='observation', #
            notes=monitoring_notes,
            note_datetime=timezone.now(),
            patient_status=new_status
        )
        
        # Update the main patient status only if it's a valid choice
        valid_statuses = [choice[0] for choice in Patient.STATUS_CHOICES] #
        if new_status in valid_statuses:
            patient.status = new_status
            patient.save()

        messages.success(request, f"{patient.full_name}'s monitoring status has been updated.")
        return redirect('nursing_actions')

    return redirect('nursing_actions')


# @csrf_exempt
# @login_required(login_url='home')
# def refer_patient(request):
#     if request.method == 'POST':
#         patient_id = request.POST.get('patient_id')
#         department_id = request.POST.get('department') #
#         notes = request.POST.get('notes') #
#         priority = request.POST.get('priority') #
        
#         patient = get_object_or_404(Patient, id=patient_id)
#         department = get_object_or_404(Department, id=department_id)

#         # Prepend priority to notes since there's no dedicated field in the model
#         referral_notes = f"PRIORITY: {priority.upper()}\n\n{notes}"

#         Referral.objects.create(
#             patient=patient,
#             department=department,
#             priority=priority, #
#             notes=referral_notes #
#         )

#         messages.success(request, f"{patient.full_name} has been referred to {department.name}.")
#         return redirect('nursing_actions')

#     return redirect('nursing_actions')

@csrf_exempt
@login_required(login_url='home')
def save_nursing_note(request):
    referer = request.META.get('HTTP_REFERER', '/')
    if request.method == 'POST':
        patient_id = request.POST.get('patient_id')

        if not patient_id or patient_id.strip() == '':
            messages.error(request, "Please select a patient to add nursing notes.")
            return redirect(referer)

        try:
            patient = get_object_or_404(Patient, id=int(patient_id))
        except (ValueError, TypeError):
            messages.error(request, "Invalid patient selection.")
            return redirect(referer)

        NursingNote.objects.create(
            patient=patient,
            note_type=request.POST.get('note_type'),
            notes=request.POST.get('notes'),
            follow_up=request.POST.get('follow_up'),
            nurse=request.user,
            note_datetime=timezone.now()
        )

        messages.success(request, "Nursing note saved successfully.")
        return redirect(referer)

    return redirect(referer)

@csrf_exempt
@login_required(login_url='home')
def handover_log(request):
    if request.method == 'POST':
        patient_id = request.POST.get('patient_id')
        handover_to_id = request.POST.get('handover_to')
        shift = request.POST.get('shift')
        notes = request.POST.get('notes')

        if not all([patient_id, handover_to_id, shift, notes]):
            messages.error(request, "All fields are required.")
            return redirect('nursing_actions')

        patient = get_object_or_404(Patient, id=patient_id)
        try:
            handover_to_user = User.objects.get(id=handover_to_id)
        except User.DoesNotExist:
            messages.error(request, "The selected nurse to handover to does not exist.")
            return redirect('nursing_actions')

        # Combine handover details into the main notes field
        handover_details = (
            f"Handover To: {handover_to_user.get_full_name()}\n"
            f"Shift: {shift.title()}\n\n{notes}"
        )

        HandoverLog.objects.create(
            patient=patient,
            notes=handover_details,
            author=request.user,
            recipient=handover_to_user
        )

        messages.success(request, f"Handover for {patient.full_name} has been logged.")
        return redirect('nursing_actions')

    return redirect('nursing_actions')

@csrf_exempt
@login_required(login_url='home')
def get_patient_details(request, patient_id):
    try:
        patient = Patient.objects.get(id=patient_id)

        vitals = list(Vitals.objects.filter(patient=patient).order_by('-recorded_at').values(
            'temperature', 'blood_pressure', 'pulse', 'recorded_at', 'respiratory_rate',
            'weight', 'height', 'bmi', 'notes', 'recorded_by' # Add all desired fields
        ))

        prescriptions = list(Prescription.objects.filter(patient=patient).order_by('-created_at')[:5].values(
            'medication', 'instructions', 'start_date'
        ))

        lab_tests = list(LabTest.objects.filter(patient=patient).order_by('-requested_at')[:5].values(
            'test_name', 'result_value', 'status'
        ))

        care_plan = CarePlan.objects.filter(patient=patient).order_by('-created_at').first()
        care_plan_data = care_plan.plan_of_care if care_plan else None

        nursing_notes = list(NursingNote.objects.filter(patient=patient).order_by('-note_datetime')[:5].values(
            'note_type', 'notes', 'note_datetime'
        ))

        return JsonResponse({
            'id': patient.id,
            'full_name': patient.full_name,
            'status': patient.status,
            'photo_url': patient.photo.url if patient.photo else None,
            'vitals': vitals,
            'prescriptions': prescriptions,
            'lab_tests': lab_tests,
            'care_plan': care_plan_data,
            'nursing_notes': nursing_notes,
        })

    except Patient.DoesNotExist:
        return JsonResponse({'error': 'Patient not found'}, status=404)

''' ############################################################################################################################ End Nurses View ############################################################################################################################ '''

''' ############################################################################################################################ Doctors View ############################################################################################################################ '''

@login_required(login_url='home')
def doctors(request):
    return render(request, 'doctors/index.html')

@login_required(login_url='home')
def doctor_consultation(request):
    """Main consultation page with patient list"""
    context = {
        'patients': Patient.objects.all().order_by('full_name'),
    }
    return render(request, 'doctors/consultation.html', context)

@login_required(login_url='home')
def access_medical_records(request):
    view_type = request.GET.get('view')
    patients = Patient.objects.all()
    
    if view_type == 'individual':
        return render(request, 'doctors/individual_records.html', {'patients': patients})
    elif view_type == 'all':
        return render(request, 'doctors/all_records.html', {'patients': patients})
    
    # Default page with the two options
    return render(request, 'doctors/access_medical_records.html', {'patients': patients})

@login_required(login_url='home')
def requesttest(request):
    categories = TestCategory.objects.prefetch_related('subcategories').all()
    patients = Patient.objects.all()
    return render(request, 'doctors/requesttest.html', {
        'categories': categories,
        'patients': patients
    })

def recomended_tests(request):
    if request.method == 'POST':
        test_id = request.POST.get('test_id')
        result_value = request.POST.get('result_value')
        notes = request.POST.get('notes', '')

        try:
            test = LabTest.objects.select_related('patient', 'category').get(id=test_id, status='pending')
            test.result_value = result_value
            test.notes = notes
            test.status = 'completed'
            test.testcompleted = True
            test.date_performed = timezone.now()
            test.performed_by = request.user
            test.save()

            messages.success(request, f"Test {test.test_name} ({test.category.name}) for {test.patient.full_name} completed successfully.")
        except LabTest.DoesNotExist:
            messages.error(request, "Invalid test entry or test already completed.")

        return redirect('lab_test_entry')

    # Fetch all lab tests
    lab_tests = LabTest.objects.select_related('patient', 'category').order_by('-requested_at')
    total_patients = Patient.objects.count()

    # Group tests by status (corrected 'pending' typo)
    tests_by_status = {
        'pending': lab_tests.filter(status='pending'),
        'completed': lab_tests.filter(status='completed', doctor_comments=0),
        'in_progress': lab_tests.filter(status='in_progress')
    }

    # Build test data list
    tests_data = []
    for test in lab_tests:
        tests_data.append({
            'test': test,
            'patient': test.patient,
            'category': test.category,
            'status': test.status,
            'requested_at': test.requested_at,
            'date_performed': test.date_performed,
            'requested_by': test.requested_by.get_full_name() if test.requested_by else 'System',
            'performed_by': test.performed_by.get_full_name() if test.performed_by else 'N/A',
            'doctor_comments': test.doctor_comments
        })

    # Build patient map only where status is 'completed' and doctor_comments == 0
    patient_map = {}
    for data in tests_data:
        if data['status'] != 'completed' or (data['doctor_comments'] or 0) != 0:
            continue

        patient_id = data['patient'].id
        if patient_id not in patient_map:
            patient_map[patient_id] = {
                'patient': data['patient'],
                'tests': [],
                'categories': set(),
                'requested_by': data['requested_by']
            }

        patient_map[patient_id]['tests'].append(data['test'])
        if data['category']:
            patient_map[patient_id]['categories'].add(data['category'].name)

    # Statistics
    today = timezone.now().date()
    stats = {
        'total_patients':total_patients,
        'total_tests': lab_tests.count(),
        'total_pending_tests': tests_by_status['pending'].count(),
        'total_completed_today': LabTest.objects.filter(status='completed', date_performed__date=today).count(),
        'total_in_progress': tests_by_status['in_progress'].count(),
        'total_categories': TestCategory.objects.count(),
        'unique_patients': Patient.objects.filter(lab_tests__isnull=False).distinct().count(),
    }

    context = {
        "total_patients": total_patients,
        'tests_data': tests_data,
        'test_categories': TestCategory.objects.all(),
        'unique_patients_with_tests': patient_map.values(),  # Only with status='completed' and doctor_comments==0
        'stats': stats,
        'debug_info': {
            'total_tests_fetched': len(tests_data),
            'test_categories_count': TestCategory.objects.count(),
            'pending_tests_count': tests_by_status['pending'].count(),
            'methods_used': [
                'LabTest.objects.select_related(patient, category)',
                'Status == completed and doctor_comments == 0'
            ]
        } if request.user.is_superuser else None
    }

    return render(request, 'doctors/recomended_test.html', context)

@login_required
@require_http_methods(["GET", "POST"])
def start_ivf(request):
    if request.method == 'GET':
        context = {
            'patients': Patient.objects.only('id', 'full_name', 'patient_id'),
            'packages': IVFPackage.objects.only('id', 'name'),
            'locations': TreatmentLocation.objects.only('id', 'name'),
            'all_ivf_records': IVFRecord.objects.all().select_related('patient', 'ivf_package', 'treatment_location').order_by('-created_on'),
            'ivf_progress_statuses': IVFProgressUpdate.STATUS_CHOICES
        }
        return render(request, 'doctors/start_ivf.html', context)

    try:
        data = json.loads(request.body)
        patient_id = data.get('patient_name')
        ivf_package_id = data.get('ivf_package')
        treatment_location_id = data.get('treatment_location')
        doctor_name = data.get('doctor_name')
        doctor_comments = data.get('doctor_comments', '')

        # Create IVF record with 'in_progress' status immediately
        ivf_record = IVFRecord.objects.create(
            patient_id=patient_id,
            ivf_package_id=ivf_package_id,
            treatment_location_id=treatment_location_id,
            doctor_name=doctor_name,
            doctor_comments=doctor_comments,
            status='in_progress'  # Set status to in_progress directly
        )

        # Record the initial status update in the progress timeline
        IVFProgressUpdate.objects.create(
            ivf_record=ivf_record,
            status='in_progress',
            comments='IVF cycle initiated and started.',
            updated_by=request.user
        )

        return JsonResponse({'success': True, 'message': 'IVF treatment form submitted and cycle started successfully!'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)
    
def doctor_report(request):
    """
    Generate comprehensive report for logged-in doctor showing all their activities
    """
    user = request.user
    
    # Verify user is a doctor
    try:
        staff = Staff.objects.get(user=user)
        if staff.role != 'doctor':
            # Handle non-doctor users appropriately
            return render(request, 'error.html', {
                'message': 'Access denied. This report is only available for doctors.'
            })
    except Staff.DoesNotExist:
        return render(request, 'error.html', {
            'message': 'Staff profile not found.'
        })
    
    # Get date range for filtering (default: last 30 days)
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=30)
    
    # Allow custom date range from request parameters
    if request.GET.get('start_date'):
        start_date = datetime.strptime(request.GET.get('start_date'), '%Y-%m-%d').date()
    if request.GET.get('end_date'):
        end_date = datetime.strptime(request.GET.get('end_date'), '%Y-%m-%d').date()
    
    # 1. Consultations conducted by the doctor
    consultations = Consultation.objects.filter(
        doctor=user,
        created_at__date__range=[start_date, end_date]
    ).select_related('patient', 'admission').order_by('-created_at')
    
    # 2. Prescriptions written by the doctor
    prescriptions = Prescription.objects.filter(
        prescribed_by=user,
        created_at__date__range=[start_date, end_date]
    ).select_related('patient').order_by('-created_at')
    
    # 3. Admissions where doctor is assigned
    admissions_assigned = Admission.objects.filter(
        doctor_assigned=user,
        admission_date__range=[start_date, end_date]
    ).select_related('patient', 'admitted_by').order_by('-admission_date')
    
    # 4. Admissions conducted by the doctor
    admissions_conducted = Admission.objects.filter(
        admitted_by=user,
        admission_date__range=[start_date, end_date]
    ).select_related('patient', 'doctor_assigned').order_by('-admission_date')
    
    # 5. Discharges conducted by the doctor
    discharges = Admission.objects.filter(
        discharged_by=user,
        discharge_date__range=[start_date, end_date]
    ).select_related('patient', 'doctor_assigned').order_by('-discharge_date')
    
    # 6. Care plans created by the doctor
    care_plans = CarePlan.objects.filter(
        created_by=user,
        created_at__date__range=[start_date, end_date]
    ).select_related('patient').order_by('-created_at')
    
    # 7. Referrals made by the doctor
    referrals = Referral.objects.filter(
        referred_by=user,
        created_at__date__range=[start_date, end_date]
    ).select_related('patient', 'department').order_by('-created_at')
    
    # 8. Lab tests requested by the doctor
    lab_tests = LabTest.objects.filter(
        requested_by=user,
        requested_at__date__range=[start_date, end_date]
    ).select_related('patient', 'category').order_by('-requested_at')
    
    # 9. Vitals recorded by the doctor
    vitals_recorded = Vitals.objects.filter(
        recorded_by=user,
        recorded_at__date__range=[start_date, end_date]
    ).select_related('patient').order_by('-recorded_at')
    
    # 10. Patients registered by the doctor
    patients_registered = Patient.objects.filter(
        registered_by=user,
        date_registered__date__range=[start_date, end_date]
    ).order_by('-date_registered')
    
    # 11. Appointments scheduled by the doctor
    appointments_scheduled = Appointment.objects.filter(
        scheduled_by=user,
        scheduled_time__date__range=[start_date, end_date]
    ).select_related('patient', 'department').order_by('-scheduled_time')
    
    # 12. Doctor comments made
    doctor_comments = DoctorComments.objects.filter(
        doctor=user,
        date__date__range=[start_date, end_date]
    ).order_by('-date')
    
    # 13. Get patients currently under doctor's care (active admissions)
    current_patients = Patient.objects.filter(
        admission__doctor_assigned=user,
        admission__status='Admitted'
    ).distinct()
    
    # Calculate summary statistics
    summary_stats = {
        'total_consultations': consultations.count(),
        'total_prescriptions': prescriptions.count(),
        'total_admissions_assigned': admissions_assigned.count(),
        'total_admissions_conducted': admissions_conducted.count(),
        'total_discharges': discharges.count(),
        'total_care_plans': care_plans.count(),
        'total_referrals': referrals.count(),
        'total_lab_tests': lab_tests.count(),
        'total_vitals': vitals_recorded.count(),
        'total_patients_registered': patients_registered.count(),
        'total_appointments_scheduled': appointments_scheduled.count(),
        'total_comments': doctor_comments.count(),
        'current_active_patients': current_patients.count(),
    }
    
    # Get patient statistics by status for patients the doctor has seen
    patient_consultations = consultations.values_list('patient_id', flat=True)
    patient_status_stats = Patient.objects.filter(
        id__in=patient_consultations
    ).values('status').annotate(count=Count('status'))
    
    # Recent activities (last 7 days) for quick overview
    recent_date = end_date - timedelta(days=7)
    recent_activities = {
        'consultations': consultations.filter(created_at__date__gte=recent_date).count(),
        'prescriptions': prescriptions.filter(created_at__date__gte=recent_date).count(),
        'admissions': admissions_conducted.filter(admission_date__gte=recent_date).count(),
        'referrals': referrals.filter(created_at__date__gte=recent_date).count(),
    }
    
    context = {
        'doctor': staff,
        'start_date': start_date,
        'end_date': end_date,
        'consultations': consultations[:20],  # Limit for performance
        'prescriptions': prescriptions[:20],
        'admissions_assigned': admissions_assigned[:20],
        'admissions_conducted': admissions_conducted[:20],
        'discharges': discharges[:20],
        'care_plans': care_plans[:20],
        'referrals': referrals[:20],
        'lab_tests': lab_tests[:20],
        'vitals_recorded': vitals_recorded[:20],
        'patients_registered': patients_registered[:20],
        'appointments_scheduled': appointments_scheduled[:20],
        'doctor_comments': doctor_comments,
        'current_patients': current_patients,
        'summary_stats': summary_stats,
        'patient_status_stats': patient_status_stats,
        'recent_activities': recent_activities,
    }
    
    return render(request, 'doctors/reports.html', context)

def test_results(request, patient_id):
    patient = get_object_or_404(Patient, id=patient_id)
    
    pending_tests = LabTest.objects.filter(
        patient=patient,
        status='completed'
    ).filter(
        Q(doctor_comments=0) | Q(doctor_comments__isnull=True)
    ).select_related('category', 'patient')
    
    for i in pending_tests:
        print(i)
    
    grouped_tests = defaultdict(list)
    for test in pending_tests:
        grouped_tests[test.category.name].append(test)
    
    # Fetch uploaded lab result files for this patient
    # Get unique file IDs from tests that have associated files
    file_ids = pending_tests.filter(
        labresulttestid__isnull=False
    ).values_list('labresulttestid', flat=True).distinct()
    
    # Fetch the actual LabResultFile objects
    uploaded_files = LabResultFile.objects.filter(
        id__in=file_ids,
        patient=patient
    ).order_by('-uploaded_at')
    
    return render(request, 'doctors/testresults.html', {
        'pending_tests': dict(grouped_tests),
        'patient': patient,
        'uploaded_files': uploaded_files,
        'selected_patient': patient  # Adding this for template compatibility
    })

###### Form Actions ######
@login_required(login_url='home')
@csrf_exempt
def save_consultation(request):
    """Save consultation data"""
    if request.method == 'POST':
        patient_id = request.POST.get('patient_id')
        symptoms = request.POST.get('symptoms', '').strip()
        diagnosis_summary = request.POST.get('diagnosis_summary', '').strip()
        advice = request.POST.get('advice', '').strip()
        
        # Validation
        if not patient_id or not symptoms or not diagnosis_summary or not advice:
            messages.error(request, "Please fill in all required fields.")
            return redirect('doctor_consultation')
        
        try:
            patient = get_object_or_404(Patient, id=patient_id)
            
            Consultation.objects.create(
                patient=patient,
                doctor=request.user,
                symptoms=symptoms,
                diagnosis_summary=diagnosis_summary,
                advice=advice
            )
            
            messages.success(request, f"Consultation saved for {patient.full_name}.")
        except Exception as e:
            messages.error(request, f"Error saving consultation: {str(e)}")
        
        return redirect('doctor_consultation')
    
    return redirect('doctor_consultation')


@csrf_exempt
def patient_history_ajax(request, patient_id):
    """Return patient history as JSON for AJAX requests"""
    try:
        patient = get_object_or_404(Patient, id=patient_id)

        # Get recent consultations
        consultations = patient.consultations.order_by('-created_at')[:5]
        consultations_data = []
        for consultation in consultations:
            consultations_data.append({
                'created_at_formatted': consultation.created_at.strftime('%Y-%m-%d %H:%M'),
                'symptoms': consultation.symptoms,
                'diagnosis_summary': consultation.diagnosis_summary,
                'advice': consultation.advice,
                'doctor_name': consultation.doctor.get_full_name() if consultation.doctor else 'N/A'
            })

        # Get recent prescriptions
        prescriptions = patient.prescriptions.order_by('-created_at')[:5]
        prescriptions_data = []
        for prescription in prescriptions:
            prescriptions_data.append({
                'created_at_formatted': prescription.created_at.strftime('%Y-%m-%d'),
                'medication': prescription.medication,
                'instructions': prescription.instructions,
                'start_date_formatted': prescription.start_date.strftime('%Y-%m-%d'),
                'prescribed_by': prescription.prescribed_by.get_full_name() if prescription.prescribed_by else 'N/A'
            })

        # Get recent lab tests
        lab_tests = patient.lab_tests.select_related('category').order_by('-requested_at')[:10]
        lab_tests_data = []
        for test in lab_tests:
            lab_tests_data.append({
                'requested_at_formatted': test.requested_at.strftime('%Y-%m-%d'),
                'category_name': test.category.name if test.category else 'N/A',
                'test_name': test.test_name,
                'result_value': test.result_value or 'Pending',
                'normal_range': test.normal_range or 'N/A',
                'status': test.get_status_display()
            })

        # Get recent vitals
        vitals = patient.vitals_set.order_by('-recorded_at')[:5]
        vitals_data = []
        for vital in vitals:
            vitals_data.append({
                'recorded_at_formatted': vital.recorded_at.strftime('%Y-%m-%d %H:%M'),
                'blood_pressure': vital.blood_pressure or 'N/A', # Add 'N/A' for potentially null fields
                'temperature': vital.temperature or 'N/A',
                'pulse': vital.pulse or 'N/A',
                'respiratory_rate': vital.respiratory_rate or 'N/A',
                'weight': vital.weight or 'N/A',
                'height': vital.height or 'N/A',
                'bmi': vital.bmi or 'N/A',
                'notes': vital.notes or 'N/A',
                'recorded_by': vital.recorded_by.get_full_name() if vital.recorded_by else 'N/A'
            })

        # Get recent nursing notes
        nursing_notes = patient.nursing_notes.order_by('-note_datetime')[:5]
        nursing_notes_data = []
        for note in nursing_notes:
            nursing_notes_data.append({
                'note_datetime_formatted': note.note_datetime.strftime('%Y-%m-%d %H:%M'),
                'note_type_display': note.get_note_type_display(),
                'notes': note.notes or 'N/A',
                'patient_status': note.patient_status or 'N/A',
                'nurse': note.nurse.get_full_name() if note.nurse else 'N/A',
                'follow_up': note.follow_up or 'N/A'
            })

        # Get recent admissions
        admissions = patient.admission_set.order_by('-admission_date')[:3]
        admissions_data = []
        for admission in admissions:
            admissions_data.append({
                'admission_date_formatted': admission.admission_date.strftime('%Y-%m-%d'),
                'doctor_assigned': admission.doctor_assigned.get_full_name() if admission.doctor_assigned else 'N/A',
                'status': admission.get_status_display(),
                'discharge_date_formatted': admission.discharge_date.strftime('%Y-%m-%d') if admission.discharge_date else 'N/A',
                'discharge_notes': admission.discharge_notes or 'N/A'
            })

        # Prepare response data
        data = {
            'patient': {
                'full_name': patient.full_name,
                'date_of_birth': patient.date_of_birth.strftime('%Y-%m-%d'),
                'gender': patient.gender,
                'phone': patient.phone,
                'blood_group': patient.blood_group,
                'status': patient.get_status_display(),
                'marital_status': patient.marital_status,
                'nationality': patient.nationality,
                'next_of_kin_name': patient.next_of_kin_name,
                'next_of_kin_phone': patient.next_of_kin_phone
            },
            'consultations': consultations_data,
            'prescriptions': prescriptions_data,
            'lab_tests': lab_tests_data,
            'vitals': vitals_data,
            'nursing_notes': nursing_notes_data,
            'admissions': admissions_data
        }

        return JsonResponse(data, safe=False)

    except Patient.DoesNotExist:
        return JsonResponse({'error': 'Patient not found'}, status=404)
    except Exception as e:
        # Log the error for server-side debugging
        import logging
        logger = logging.getLogger(__name__)
        logger.exception("Error fetching patient history:")
        return JsonResponse({'error': str(e), 'detail': 'An internal server error occurred while fetching patient history.'}, status=500)


@login_required(login_url='home')
@csrf_exempt
def add_prescription(request):
    """Add prescription for a patient"""
    if request.method == 'POST':
        patient_id = request.POST.get('patient_id')
        medication = request.POST.get('medication', '').strip()
        instructions = request.POST.get('instructions', '').strip()
        start_date = request.POST.get('start_date')
        
        # Validation
        if not patient_id or not medication or not instructions or not start_date:
            messages.error(request, "Please fill in all required fields.")
            return redirect('doctor_consultation')
        
        try:
            patient = get_object_or_404(Patient, id=patient_id)
            
            Prescription.objects.create(
                patient=patient,
                medication=medication,
                instructions=instructions,
                start_date=start_date,
                prescribed_by=request.user
            )
            
            messages.success(request, f"Prescription added for {patient.full_name}.")
        except Exception as e:
            messages.error(request, f"Error adding prescription: {str(e)}")
        
        return redirect('doctor_consultation')
    
    return redirect('doctor_consultation')


@login_required(login_url='home')
@csrf_exempt
def save_care_plan(request):
    """Save care plan for a patient"""
    if request.method == "POST":
        patient_id = request.POST.get('patient_id')
        clinical_findings = request.POST.get('clinical_findings', '').strip()
        plan_of_care = request.POST.get('plan_of_care', '').strip()
        
        # Validation
        if not patient_id or not clinical_findings or not plan_of_care:
            messages.error(request, "Please fill in all required fields.")
            return redirect('doctor_consultation')
        
        try:
            patient = get_object_or_404(Patient, id=patient_id)
            
            CarePlan.objects.create(
                patient=patient,
                clinical_findings=clinical_findings,
                plan_of_care=plan_of_care,
                created_by=request.user
            )
            
            messages.success(request, f"Care plan saved successfully for {patient.full_name}.")
        except Exception as e:
            messages.error(request, f"Error saving care plan: {str(e)}")
        
        return redirect('doctor_consultation')
    
    return redirect('doctor_consultation')

@login_required(login_url='home')
@require_GET
def get_patient_overview(request, patient_id):
    try:
        patient = get_object_or_404(Patient, id=patient_id)
        latest_admission = Admission.objects.filter(patient=patient).order_by('-admission_date').first()
        latest_vitals = Vitals.objects.filter(patient=patient).order_by('-recorded_at').first()

        overview_data = {
            'name': patient.full_name,
            'gender': patient.gender,
            'blood_group': patient.blood_group,
            'date_of_birth': patient.date_of_birth.strftime('%Y-%m-%d'),
            'phone': patient.phone,
            'address': patient.address,
            'status': patient.status,
            'is_inpatient': patient.is_inpatient,
            'diagnosis': patient.diagnosis,
            'medication': patient.medication,
            'notes': patient.notes,
            'referred_by': patient.referred_by,
            'ward': 'N/A',  # Admission model does not have 'ward' or 'bed_number'
            'bed': 'N/A',   # These fields are not in the provided models.py
            'last_vitals': None
        }

        if latest_vitals:
            overview_data['last_vitals'] = {
                'date': latest_vitals.recorded_at.strftime('%Y-%m-%d %H:%M'),
                'temperature': str(latest_vitals.temperature),
                'blood_pressure': latest_vitals.blood_pressure,
                'pulse': str(latest_vitals.pulse),
                'respiratory_rate': str(latest_vitals.respiratory_rate),
                'weight': str(latest_vitals.weight),
                'height': str(latest_vitals.height),
                'bmi': str(latest_vitals.bmi),
            }

        return JsonResponse(overview_data)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    
@login_required(login_url='home')
def get_patient_monitor(request, patient_id):
    try:
        patient = Patient.objects.get(id=patient_id)
        
        consultations = Consultation.objects.filter(patient=patient).order_by('-created_at')
        prescriptions = Prescription.objects.filter(patient=patient).order_by('-created_at')
        lab_tests = LabTest.objects.filter(patient=patient).order_by('-requested_at')
        nursing_notes = NursingNote.objects.filter(patient=patient).order_by('-created_at')
        care_plans = CarePlan.objects.filter(patient=patient).order_by('-created_at')
        referrals = Referral.objects.filter(patient=patient).order_by('-id')
        appointments = Appointment.objects.filter(patient=patient).order_by('-scheduled_time')


        return JsonResponse({
            "consultations": [
                {
                    "diagnosis_summary": c.diagnosis_summary,
                    "advice": c.advice,
                    "symptoms": c.symptoms,
                    "date": c.created_at.strftime("%Y-%m-%d %H:%M")
                } 
                for c in consultations
            ],
            "prescriptions": [
                {
                    "medication": p.medication,
                    "instructions": p.instructions,
                    "start_date": p.start_date.strftime("%Y-%m-%d"),
                    "date": p.created_at.strftime("%Y-%m-%d %H:%M")
                } 
                for p in prescriptions
            ],
            "lab_tests": [
                {
                    "test_name": lt.test_name,
                    "category": lt.category.name,
                    "status": lt.status,
                    "result_value": lt.result_value,
                    "date_performed": lt.date_performed.strftime("%Y-%m-%d %H:%M") if lt.date_performed else 'N/A',
                    "requested_at": lt.requested_at.strftime("%Y-%m-%d %H:%M")
                }
                for lt in lab_tests
            ],
            "nursing_notes": [
                {
                    "note_type": nn.note_type,
                    "notes": nn.notes,
                    "patient_status": nn.patient_status,
                    "date": nn.note_datetime.strftime("%Y-%m-%d %H:%M")
                }
                for nn in nursing_notes
            ],
            "care_plans": [
                {
                    "clinical_findings": cp.clinical_findings,
                    "plan_of_care": cp.plan_of_care,
                    "created_at": cp.created_at.strftime("%Y-%m-%d %H:%M")
                }
                for cp in care_plans
            ],
            "referrals": [
                {
                    "department": r.department.name,
                    "notes": r.notes,
                    "patient_name": r.patient.full_name
                }
                for r in referrals
            ],
            "appointments": [
                {
                    "department": a.department.name,
                    "scheduled_time": a.scheduled_time.strftime("%Y-%m-%d %H:%M")
                }
                for a in appointments
            ]
        })
    except Patient.DoesNotExist:
        return JsonResponse({"error": "Patient not found"}, status=404)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
    
def submit_test_selection(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            patient_id = data.get('patient_id')
            selections = data.get('selections', [])
            
            if not patient_id or not selections:
                return JsonResponse({'status': 'error', 'message': 'Missing patient or selection data'})
            
            patient = Patient.objects.get(id=int(patient_id))
            
            # Generate a single UUID for this test request
            test_request_uuid = uuid4()
            
            created_tests = []
            for item in selections:
                category = item.get('category')
                tests = item.get('tests', [])
                
                try:
                    category_obj = TestCategory.objects.get(name=category)
                except TestCategory.DoesNotExist:
                    continue
                
                for test in tests:
                    lab_test = LabTest.objects.create(
                        patient=patient,
                        category=category_obj,
                        test_name=test,
                        test_request_id=test_request_uuid,  # Same UUID for all tests in this request
                        requested_by=request.user,
                        doctor_name=request.user.get_full_name() or request.user.username
                    )
                    created_tests.append(lab_test.id)
            
            return JsonResponse({
                'status': 'success', 
                'message': 'Selections saved.',
                'test_request_id': str(test_request_uuid),
                'created_tests': created_tests
            })
            
        except Patient.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Patient not found'})
        except DatabaseError as e:
            return JsonResponse({'status': 'error', 'message': f'Database error: {str(e)}'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': f'An error occurred: {str(e)}'})
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'})

def doc_test_comment(request, patient_id):
    if request.method == 'POST':
        comment_text = request.POST.get('doctor_comment', '')
        ids = request.POST.getlist('ids')

        if not ids or not comment_text:
            messages.error(request, "You must select tests and enter a comment.")
            return redirect('recomended_tests')

        # Create a new DoctorComments record
        comment_record = DoctorComments.objects.create(
            comments=comment_text,
            date=timezone.now(),
            doctor=request.user,  # or request.user.get_full_name() if applicable
            labtech_name="LabTech Placeholder"  # Replace with actual logic if needed
        )
        # Update each LabTest with the new doctor_comments ID
        LabTest.objects.filter(id__in=ids).update(doctor_comments=comment_record.id)

        messages.success(request, "Doctor's comment added and tests updated successfully.")
        return redirect('recomended_tests')

    # If GET request (optional, show test details or redirect)
    return redirect('recomended_tests')

def apply_date_filter(queryset, date_from_str, date_to_str, date_field_name, is_datetime_field=True):
    """
    Applies date range filtering to a queryset based on a specified date/datetime field.

    Args:
        queryset: The Django queryset to filter.
        date_from_str (str): The start date string in YYYY-MM-DD format (can be None).
        date_to_str (str): The end date string in YYYY-MM-DD format (can be None).
        date_field_name (str): The name of the date/datetime field on the model to filter by.
        is_datetime_field (bool): Whether the field is a DateTimeField (True) or DateField (False).
    """
    parsed_date_from = None
    parsed_date_to = None

    if date_from_str:
        try:
            parsed_date_from = datetime.strptime(date_from_str, '%Y-%m-%d').date()
        except ValueError:
            raise ValueError(f"Invalid start date format '{date_from_str}'. Use YYYY-MM-DD.")
    
    if date_to_str:
        try:
            parsed_date_to = datetime.strptime(date_to_str, '%Y-%m-%d').date()
        except ValueError:
            raise ValueError(f"Invalid end date format '{date_to_str}'. Use YYYY-MM-DD.")

    if parsed_date_from:
        if is_datetime_field:
            # Use __date for DateTimeField to filter by the date part only
            queryset = queryset.filter(**{f"{date_field_name}__date__gte": parsed_date_from})
        else:
            # Direct comparison for DateField
            queryset = queryset.filter(**{f"{date_field_name}__gte": parsed_date_from})
    
    if parsed_date_to:
        if is_datetime_field:
            # Use __date for DateTimeField to filter by the date part only
            queryset = queryset.filter(**{f"{date_field_name}__date__lte": parsed_date_to})
        else:
            # Direct comparison for DateField
            queryset = queryset.filter(**{f"{date_field_name}__lte": parsed_date_to})

    return queryset


def fetch_patient_activity(request):
    """
    Comprehensive AJAX view to fetch all patient medical records and activity
    """
    if request.method != 'GET':
        return JsonResponse({'error': 'Only GET method allowed'}, status=405)

    patient_id = request.GET.get('patient_id')
    date_from_param = request.GET.get('date_from')
    date_to_param = request.GET.get('date_to')

    if not patient_id:
        return JsonResponse({'error': 'Patient ID is required'}, status=400)

    try:
        # Get patient with error handling
        patient = get_object_or_404(Patient, id=patient_id)

        # If date_to is not provided, set it to today's date as a string
        if not date_to_param:
            date_to_param = date.today().strftime('%Y-%m-%d')

        # === FETCH ALL PATIENT DATA ===

        # 1. BASIC PATIENT INFO
        # Calculate age properly
        today = date.today()
        age = today.year - patient.date_of_birth.year - ((today.month, today.day) < (patient.date_of_birth.month, patient.date_of_birth.day))

        # Handle patient photo
        photo_url = ''
        if patient.photo and hasattr(patient.photo, 'url'):
            try:
                # Check if file exists
                if default_storage.exists(patient.photo.name):
                    photo_url = patient.photo.url
            except Exception as e:
                logger.warning(f"Error accessing patient photo for patient {patient.id}: {e}")
                pass

        patient_data = {
            'id': patient.id,
            'full_name': patient.full_name,
            'gender': patient.gender,
            'date_of_birth': patient.date_of_birth.strftime('%Y-%m-%d'),
            'age': age,
            'blood_group': patient.blood_group,
            'phone': patient.phone,
            'email': patient.email or '',
            'address': patient.address,
            'marital_status': patient.marital_status,
            'nationality': patient.nationality,
            'state_of_origin': patient.state_of_origin or '',
            'id_type': patient.id_type or '',
            'id_number': patient.id_number or '',
            'status': patient.status,
            'is_inpatient': patient.is_inpatient,
            'date_registered': patient.date_registered.strftime('%Y-%m-%d %H:%M'),
            'photo_url': photo_url,

            # Next of Kin Info
            'next_of_kin_name': patient.next_of_kin_name,
            'next_of_kin_phone': patient.next_of_kin_phone,
            'next_of_kin_relationship': patient.next_of_kin_relationship or '',
            'next_of_kin_email': patient.next_of_kin_email or '',
            'next_of_kin_address': patient.next_of_kin_address or '',

            # Current Medical Status
            'diagnosis': patient.diagnosis or '',
            'medication': patient.medication or '',
            'notes': patient.notes or '',
            'referred_by': patient.referred_by or '',
        }

        # 2. CONSULTATIONS
        consultations_qs = apply_date_filter(
            patient.consultations.select_related('doctor', 'admission').order_by('-created_at'),
            date_from_param,
            date_to_param,
            'created_at',
            is_datetime_field=True
        )
        consultations = []
        for consultation in consultations_qs:
            consultations.append({
                'id': consultation.id,
                'date': consultation.created_at.strftime('%Y-%m-%d %H:%M'),
                'doctor': consultation.doctor.get_full_name() if consultation.doctor else 'Unknown',
                'symptoms': consultation.symptoms,
                'diagnosis_summary': consultation.diagnosis_summary,
                'advice': consultation.advice,
                'admission_id': consultation.admission.id if consultation.admission else None,
            })

        # 3. PRESCRIPTIONS
        prescriptions_qs = apply_date_filter(
            patient.prescriptions.select_related('prescribed_by').order_by('-created_at'),
            date_from_param,
            date_to_param,
            'created_at',
            is_datetime_field=True
        )
        prescriptions = []
        for prescription in prescriptions_qs:
            prescriptions.append({
                'id': prescription.id,
                'medication': prescription.medication,
                'instructions': prescription.instructions,
                'start_date': prescription.start_date.strftime('%Y-%m-%d'),
                'prescribed_by': prescription.prescribed_by.get_full_name() if prescription.prescribed_by else 'Unknown',
                'created_at': prescription.created_at.strftime('%Y-%m-%d %H:%M'),
            })

        # 4. VITALS
        vitals_qs = apply_date_filter(
            Vitals.objects.filter(patient=patient).select_related('recorded_by').order_by('-recorded_at'),
            date_from_param,
            date_to_param,
            'recorded_at',
            is_datetime_field=True
        )
        vitals = []
        for vital in vitals_qs:
            vitals.append({
                'id': vital.id,
                'recorded_at': vital.recorded_at.strftime('%Y-%m-%d %H:%M'),
                'recorded_by': vital.recorded_by.get_full_name() if vital.recorded_by else 'Unknown',
                'temperature': vital.temperature,
                'blood_pressure': vital.blood_pressure,
                'pulse': vital.pulse,
                'respiratory_rate': vital.respiratory_rate,
                'weight': vital.weight,
                'height': vital.height,
                'bmi': vital.bmi,
                'notes': vital.notes or '',
            })

        # 5. LAB TESTS & RESULTS (Grouped by test_request_id UUID)
        lab_tests_qs = apply_date_filter(
            patient.lab_tests.select_related('category', 'performed_by', 'requested_by', 'recorded_by').order_by('-requested_at'),
            date_from_param,
            date_to_param,
            'requested_at',
            is_datetime_field=True
        )

        # Group tests by the UUID (test_request_id)
        grouped_lab_tests = defaultdict(list)
        for test in lab_tests_qs:
            grouped_lab_tests[test.test_request_id].append(test)

        lab_test_groups = []
        for request_id, tests_in_group in grouped_lab_tests.items():
            first_test = tests_in_group[0]

            # Fetch Doctor Comment - CORRECTED
            doctor_comment_data = None
            if first_test.doctor_comments:
                try:
                    comment = DoctorComments.objects.select_related('doctor').get(id=first_test.doctor_comments)
                    doctor_comment_data = {
                        "id": comment.id,
                        "comment": comment.comments,
                        "doctor_name": comment.doctor.get_full_name() if comment.doctor else 'Unknown',  # FIXED
                        "labtech_name": comment.labtech_name,
                        "date": comment.date.strftime('%Y-%m-%d %H:%M')
                    }
                except DoctorComments.DoesNotExist:
                    doctor_comment_data = None

            # Fetch Lab Result File - CORRECTED
            lab_file_data = None
            if first_test.labresulttestid:
                try:
                    lab_file = LabResultFile.objects.select_related('uploaded_by').get(id=first_test.labresulttestid)
                    file_url = ''
                    file_name = ''
                    if lab_file.result_file and hasattr(lab_file.result_file, 'url'):
                        try:
                            if default_storage.exists(lab_file.result_file.name):
                                file_url = lab_file.result_file.url
                                file_name = lab_file.result_file.name.split('/')[-1]
                        except Exception as e:
                            logger.warning(f"Error accessing lab result file {lab_file.id}: {e}")
                            pass
                    
                    lab_file_data = {
                        "id": lab_file.id,
                        "file_url": file_url,
                        "file_name": file_name,
                        "uploaded_at": lab_file.uploaded_at.strftime('%Y-%m-%d %H:%M'),
                        "uploaded_by": lab_file.uploaded_by.get_full_name() if lab_file.uploaded_by else 'Unknown'
                    }
                except LabResultFile.DoesNotExist:
                    lab_file_data = None

            # Prepare individual tests data
            tests_data = []
            for test in tests_in_group:
                tests_data.append({
                    'id': test.id,
                    'test_name': test.test_name,
                    'category': test.category.name if test.category else '',
                    'status': test.get_status_display(),
                    'status_code': test.status,
                    'result_value': test.result_value or '',
                    'normal_range': test.normal_range or '',
                    'notes': test.notes or '',
                    'instructions': test.instructions or '',
                    'doctor_name': test.doctor_name or '',
                    'performed_by': test.performed_by.get_full_name() if test.performed_by else '',
                    'requested_by': test.requested_by.get_full_name() if test.requested_by else '',
                    'recorded_by': test.recorded_by.get_full_name() if test.recorded_by else '',
                    'date_performed': test.date_performed.strftime('%Y-%m-%d %H:%M') if test.date_performed else '',
                    'submitted_on': test.submitted_on.strftime('%Y-%m-%d'),
                    'testcompleted': test.testcompleted,
                })

            tests_data.sort(key=lambda x: x['test_name'])

            group_statuses = [test.status for test in tests_in_group]
            if all(status == 'completed' for status in group_statuses):
                group_status = 'completed'
            elif any(status == 'in_progress' for status in group_statuses):
                group_status = 'in_progress'
            elif any(status == 'cancelled' for status in group_statuses):
                group_status = 'mixed'
            else:
                group_status = 'pending'

            lab_test_groups.append({
                "request_id": str(request_id),
                "requested_at": first_test.requested_at.strftime('%Y-%m-%d %H:%M'),
                "submitted_on": first_test.submitted_on.strftime('%Y-%m-%d'),
                "doctor_name": first_test.doctor_name or '',
                "requested_by": first_test.requested_by.get_full_name() if first_test.requested_by else '',
                "group_status": group_status,
                "tests_count": len(tests_in_group),
                "completed_tests": len([t for t in tests_in_group if t.status == 'completed']),
                "pending_tests": len([t for t in tests_in_group if t.status == 'pending']),
                "doctor_comment": doctor_comment_data,
                "result_file": lab_file_data,
                "tests": tests_data
            })

        lab_test_groups.sort(key=lambda x: x['requested_at'], reverse=True)

        # 6. NURSING NOTES - CORRECTED
        nursing_notes_qs = apply_date_filter(
            patient.nursing_notes.select_related('nurse').order_by('-note_datetime'),
            date_from_param,
            date_to_param,
            'note_datetime',
            is_datetime_field=True
        )
        nursing_notes = []
        for note in nursing_notes_qs:
            nursing_notes.append({
                'id': note.id,
                'note_datetime': note.note_datetime.strftime('%Y-%m-%d %H:%M'),
                'nurse': note.nurse.get_full_name() if note.nurse else 'Unknown',  # FIXED
                'note_type': note.get_note_type_display(),
                'note_type_code': note.note_type,
                'notes': note.notes,
                'patient_status': note.patient_status or '',
                'follow_up': note.follow_up or '',
                'created_at': note.created_at.strftime('%Y-%m-%d %H:%M'),
            })

        # 7. ADMISSIONS - CORRECTED
        admissions_qs = apply_date_filter(
            Admission.objects.filter(patient=patient).select_related('admitted_by', 'discharged_by', 'doctor_assigned').order_by('-admission_date'),
            date_from_param,
            date_to_param,
            'admission_date',
            is_datetime_field=False  # admission_date is DateField
        )
        admissions = []
        for admission in admissions_qs:
            admissions.append({
                'id': admission.id,
                'admission_date': admission.admission_date.strftime('%Y-%m-%d'),
                'admitted_on': admission.admitted_on.strftime('%Y-%m-%d'),
                'admitted_by': admission.admitted_by.get_full_name() if admission.admitted_by else 'Unknown',  # FIXED
                'doctor_assigned': admission.doctor_assigned.get_full_name() if admission.doctor_assigned else 'Unknown',  # FIXED
                'status': admission.status,
                'admission_reason': admission.admission_reason or '',  # ADDED
                'discharge_date': admission.discharge_date.strftime('%Y-%m-%d') if admission.discharge_date else '',
                'discharged_by': admission.discharged_by.get_full_name() if admission.discharged_by else '',  # FIXED
                'discharge_notes': admission.discharge_notes or '',
                'time': admission.time.strftime('%H:%M') if admission.time else '',
            })

        # 8. CARE PLANS
        care_plans_qs = apply_date_filter(
            CarePlan.objects.filter(patient=patient).select_related('created_by').order_by('-created_at'),
            date_from_param,
            date_to_param,
            'created_at',
            is_datetime_field=True
        )
        care_plans = []
        for plan in care_plans_qs:
            care_plans.append({
                'id': plan.id,
                'created_at': plan.created_at.strftime('%Y-%m-%d %H:%M'),
                'created_by': plan.created_by.get_full_name() if plan.created_by else 'Unknown',
                'clinical_findings': plan.clinical_findings,
                'plan_of_care': plan.plan_of_care,
            })

        # 9. REFERRALS - CORRECTED
        referrals = []
        referrals_qs = Referral.objects.filter(patient=patient).select_related('department', 'referred_by').order_by('-created_at')
        for referral in referrals_qs:
            referrals.append({
                'id': referral.id,
                'department': referral.department.name,
                'notes': referral.notes,
                'priority': referral.priority or '',  # ADDED
                'referred_by': referral.referred_by.get_full_name() if referral.referred_by else 'Unknown',  # ADDED
                'created_at': referral.created_at.strftime('%Y-%m-%d %H:%M'),  # ADDED
            })

        # 10. APPOINTMENTS - CORRECTED
        appointments_qs = apply_date_filter(
            Appointment.objects.filter(patient=patient).select_related('department', 'scheduled_by').order_by('-scheduled_time'),
            date_from_param,
            date_to_param,
            'scheduled_time',
            is_datetime_field=True
        )
        appointments = []
        for appointment in appointments_qs:
            appointments.append({
                'id': appointment.id,
                'scheduled_time': appointment.scheduled_time.strftime('%Y-%m-%d %H:%M'),
                'department': appointment.department.name,
                'scheduled_by': appointment.scheduled_by.get_full_name() if appointment.scheduled_by else 'Unknown',  # ADDED
            })

        # 11. BILLS
        bills_qs = apply_date_filter(
            patient.bills.select_related('created_by').prefetch_related('items__service_type').order_by('-created_at'),
            date_from_param,
            date_to_param,
            'created_at',
            is_datetime_field=True
        )
        bills = []
        for bill in bills_qs:
            bill_items = []
            for item in bill.items.all():
                bill_items.append({
                    'description': item.description,
                    'service_type': item.service_type.name,
                    'quantity': item.quantity,
                    'unit_price': float(item.unit_price),
                    'total_price': float(item.total_price),
                })

            bills.append({
                'id': bill.id,
                'bill_number': bill.bill_number,
                'created_at': bill.created_at.strftime('%Y-%m-%d %H:%M'),
                'created_by': bill.created_by.get_full_name() if bill.created_by else 'Unknown',  # ADDED
                'total_amount': float(bill.total_amount),
                'discount_amount': float(bill.discount_amount),
                'final_amount': float(bill.final_amount),
                'amount_paid': float(bill.amount_paid()),
                'outstanding_amount': float(bill.outstanding_amount()),
                'status': bill.get_status_display(),
                'status_code': bill.status,
                'items': bill_items,
                'notes': bill.notes or '',
            })

        # 12. PAYMENTS
        payments_qs = apply_date_filter(
            patient.payments.select_related('processed_by', 'bill').order_by('-payment_date'),
            date_from_param,
            date_to_param,
            'payment_date',
            is_datetime_field=True
        )
        payments = []
        for payment in payments_qs:
            payments.append({
                'id': payment.id,
                'amount': float(payment.amount),
                'payment_date': payment.payment_date.strftime('%Y-%m-%d %H:%M'),
                'payment_method': payment.get_payment_method_display(),
                'payment_method_code': payment.payment_method,
                'payment_reference': payment.payment_reference or '',
                'status': payment.get_status_display(),
                'status_code': payment.status,
                'processed_by': payment.processed_by.get_full_name() if payment.processed_by else 'Unknown',
                'bill_number': payment.bill.bill_number if payment.bill else '',
                'notes': payment.notes or '',
            })

        # 13. HANDOVER LOGS - CORRECTED
        handover_logs_qs = apply_date_filter(
            HandoverLog.objects.filter(patient=patient).select_related('author', 'recipient').order_by('-timestamp'),
            date_from_param,
            date_to_param,
            'timestamp',
            is_datetime_field=True
        )
        handover_logs = []
        for log in handover_logs_qs:
            handover_logs.append({
                'id': log.id,
                'timestamp': log.timestamp.strftime('%Y-%m-%d %H:%M'),
                'author': log.author.get_full_name() if log.author else 'Unknown',
                'recipient': log.recipient.get_full_name() if log.recipient else 'Unknown',  # ADDED
                'notes': log.notes,
            })

        # Calculate summary statistics
        total_lab_test_groups = len(lab_test_groups)
        total_individual_lab_tests = sum(len(group['tests']) for group in lab_test_groups)
        pending_lab_test_groups = len([g for g in lab_test_groups if g['group_status'] in ['pending', 'in_progress']])
        completed_lab_test_groups = len([g for g in lab_test_groups if g['group_status'] == 'completed'])

        # Compile comprehensive response
        response_data = {
            'success': True,
            'patient_info': patient_data,
            'consultations': consultations,
            'prescriptions': prescriptions,
            'vitals': vitals,
            'lab_test_groups': lab_test_groups,
            'nursing_notes': nursing_notes,
            'admissions': admissions,
            'care_plans': care_plans,
            'referrals': referrals,
            'appointments': appointments,
            'bills': bills,
            'payments': payments,
            'handover_logs': handover_logs,

            # Summary counts
            'summary': {
                'total_consultations': len(consultations),
                'total_prescriptions': len(prescriptions),
                'total_vitals': len(vitals),
                'total_lab_test_groups': total_lab_test_groups,
                'total_individual_lab_tests': total_individual_lab_tests,
                'pending_lab_test_groups': pending_lab_test_groups,
                'completed_lab_test_groups': completed_lab_test_groups,
                'total_nursing_notes': len(nursing_notes),
                'total_admissions': len(admissions),
                'current_admission': any(a['status'] == 'Admitted' for a in admissions),
                'total_bills': len(bills),
                'outstanding_bills': len([b for b in bills if b['outstanding_amount'] > 0]),
                'total_payments': len(payments),
                'total_referrals': len(referrals),
                'total_appointments': len(appointments),
                'total_care_plans': len(care_plans),
                'total_handover_logs': len(handover_logs),
            }
        }

        return JsonResponse(response_data)

    except Patient.DoesNotExist:
        return JsonResponse({'error': 'Patient not found'}, status=404)
    except ValueError as e:
        return JsonResponse({'error': f'Date format error: {str(e)}'}, status=400)
    except Exception as e:
        logger.error(f"Error in fetch_patient_activity: {str(e)}", exc_info=True)
        return JsonResponse({'error': f'An unexpected error occurred: {str(e)}'}, status=500)
    
@login_required
@require_http_methods(["POST"])
def update_ivf_status(request):
    try:
        data = json.loads(request.body)
        record_id = data.get('record_id')
        new_status = data.get('new_status')
        comments = data.get('comments', '')

        if not record_id or not new_status:
            return JsonResponse({'error': 'Missing record_id or new_status'}, status=400)

        ivf_record = get_object_or_404(IVFRecord, id=record_id)

        allowed_statuses = [choice[0] for choice in IVFProgressUpdate.STATUS_CHOICES]
        
        if new_status not in allowed_statuses:
            return JsonResponse({'error': f'Invalid status: {new_status}'}, status=400)

        ivf_record.status = new_status
        ivf_record.save()

        IVFProgressUpdate.objects.create(
            ivf_record=ivf_record,
            status=new_status,
            comments=comments,
            updated_by=request.user
        )

        return JsonResponse({'success': True, 'message': f'IVF Record {record_id} status updated to {new_status}'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@login_required
@require_http_methods(["GET"])
def get_ivf_progress(request, record_id):
    ivf_record = get_object_or_404(IVFRecord, id=record_id)
    patient = ivf_record.patient
    
    timeline_entries = []

    # 1. Add IVFProgressUpdate entries
    progress_updates = IVFProgressUpdate.objects.filter(ivf_record=ivf_record).order_by('timestamp')
    for update in progress_updates:
        timeline_entries.append({
            'type': 'status_update', 
            'status': update.get_status_display(),
            'comments': update.comments,
            'updated_by': update.updated_by.get_full_name() if update.updated_by else 'N/A',
            'timestamp': update.timestamp,
        })

    # 2. Add Vitals entries for the patient, around the IVF record creation time
    # This retrieves all vitals for the patient, not just the first one.
    vital = Vitals.objects.filter(patient=patient).order_by('-recorded_at').first()
    if vital:
        timeline_entries.append({
        'type': 'vitals',
        'blood_pressure': vital.blood_pressure,
        'temperature': vital.temperature,
        'pulse': vital.pulse,
        'respiratory_rate': vital.respiratory_rate,
        'weight': vital.weight,
        'height': vital.height,
        'bmi': vital.bmi,
        'notes': vital.notes,
        'recorded_by': vital.recorded_by.get_full_name() if vital.recorded_by else 'N/A',
        'timestamp': vital.recorded_at,
    })
    


    # 3. Add LabTest entries for the patient, around the IVF record creation time
    lab_tests = LabTest.objects.filter(patient=patient).order_by('requested_at')
    for test in lab_tests:
        timeline_entries.append({
            'type': 'lab_test', 
            'test_name': test.test_name,
            'status': test.get_status_display(),
            'result_value': test.result_value,
            'notes': test.notes,
            'requested_by': test.requested_by.get_full_name() if test.requested_by else 'N/A',
            'performed_by': test.performed_by.get_full_name() if test.performed_by else 'N/A',
            'timestamp': test.requested_at,
            'test_request_id': test.test_request_id,
        })

    # 4. Add Consultation entries for the patient
    consultations = Consultation.objects.filter(patient=patient).order_by('created_at')
    for consultation in consultations:
        timeline_entries.append({
            'type': 'consultation', 
            'symptoms': consultation.symptoms,
            'diagnosis_summary': consultation.diagnosis_summary,
            'advice': consultation.advice,
            'doctor': consultation.doctor.get_full_name() if consultation.doctor else 'N/A',
            'timestamp': consultation.created_at,
        })

    # 5. Add NursingNote entries for the patient
    nursing_notes = NursingNote.objects.filter(patient=patient).order_by('note_datetime')
    for note in nursing_notes:
        timeline_entries.append({
            'type': 'nursing_note', 
            'note_type': note.get_note_type_display(),
            'notes': note.notes,
            'nurse': note.nurse.get_full_name() if note.nurse else 'N/A',
            'timestamp': note.note_datetime,
        })

    # Sort all entries by timestamp
    timeline_entries.sort(key=lambda x: x['timestamp'])

    # Format timestamps for JSON response
    formatted_timeline_entries = []
    for entry in timeline_entries:
        entry['timestamp'] = entry['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
        formatted_timeline_entries.append(entry)

    current_record_details = {
        'patient_name': ivf_record.patient.full_name,
        'ivf_package': ivf_record.ivf_package.name if ivf_record.ivf_package else 'N/A',
        'current_status': ivf_record.get_status_display(),
        'doctor_name': ivf_record.doctor_name,
        'created_on': ivf_record.created_on.strftime('%Y-%m-%d %H:%M:%S'),
        'id': ivf_record.id,
    }

    return JsonResponse({'success': True, 'record_details': current_record_details, 'timeline': formatted_timeline_entries})

@login_required
@require_http_methods(["POST"])
def add_ivf_progress_comment(request):
    try:
        data = json.loads(request.body)
        record_id = data.get('record_id')
        comments = data.get('comments', '')

        if not record_id or not comments:
            return JsonResponse({'error': 'Missing record_id or comments'}, status=400)

        ivf_record = get_object_or_404(IVFRecord, id=record_id)

        IVFProgressUpdate.objects.create(
            ivf_record=ivf_record,
            status=ivf_record.status,  # Use the current status of the record for the comment
            comments=comments,
            updated_by=request.user
        )

        return JsonResponse({'success': True, 'message': 'Comment added to IVF progress successfully!'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)
    
''' ############################################################################################################################ End Doctors View ############################################################################################################################ '''

''' ############################################################################################################################ Laboratory View ############################################################################################################################ '''

@login_required(login_url='home')
def laboratory(request):
    today = date.today()
    start_of_day = timezone.make_aware(datetime.combine(today, datetime.min.time()))
    end_of_day = timezone.make_aware(datetime.combine(today, datetime.max.time()))

    user_filter = Q(requested_by=request.user) | Q(performed_by=request.user)

    test_today = LabTest.objects.filter(
        user_filter,
        date_performed__range=(start_of_day, end_of_day),
        status='completed'
    ).count()

    pending_count = LabTest.objects.filter(user_filter, status='pending').count()
    completed_count = LabTest.objects.filter(user_filter, status='completed').count()
    in_progress_count = LabTest.objects.filter(user_filter, status='in_progress').count()

    total_patients_count = Patient.objects.count()
    uploaded_results_count = LabResultFile.objects.count()

    # Data for Today's Test Status Table (Latest 5 tests requested today) - Filtered by user
    today_tests_details = LabTest.objects.filter(
        user_filter, # Apply user filter
        requested_at__range=(start_of_day, end_of_day)
    ).select_related('patient', 'category').order_by('-requested_at')[:5]

    # Data for Awaiting Tests (Pending Tests List) - Filtered by user
    awaiting_tests = LabTest.objects.filter(user_filter, status='pending').select_related('patient', 'category').order_by('-requested_at')[:8]

    # Data for Weekly Lab Activity Chart (Last 7 days) - Filtered by user
    weekly_labels = []
    weekly_tests_data_total = [0] * 7
    weekly_tests_data_completed = [0] * 7

    for i in range(7):
        day = today - timedelta(days=6 - i)
        weekly_labels.append(day.strftime('%a'))

        day_start = timezone.make_aware(datetime.combine(day, datetime.min.time()))
        day_end = timezone.make_aware(datetime.combine(day, datetime.max.time()))

        total_on_day = LabTest.objects.filter(
            user_filter, # Apply user filter
            date_performed__range=(day_start, day_end)
        ).count()
        completed_on_day = LabTest.objects.filter(
            user_filter, # Apply user filter
            status='completed',
            date_performed__range=(day_start, day_end)
        ).count()

        weekly_tests_data_total[i] = total_on_day
        weekly_tests_data_completed[i] = completed_on_day

    # Recent Activity (Timeline) - Filtered by user
    recent_activities = []
    recent_lab_tests = LabTest.objects.filter(user_filter).select_related('patient').order_by('-requested_at')[:5]

    for test in recent_lab_tests:
        icon_class = ''
        bg_color = ''
        header_text = ''
        body_text = ''
        link_url = '#'

        if test.status == 'completed':
            icon_class = 'fas fa-vial'
            bg_color = 'bg-primary'
            header_text = f"{test.test_name} completed"
            body_text = f"Patient {test.patient.full_name} - All parameters within normal range."
        elif test.status == 'pending':
            icon_class = 'fas fa-clock'
            bg_color = 'bg-warning'
            header_text = f"{test.test_name} Pending"
            body_text = f"Patient {test.patient.full_name} - Awaiting processing."
        else:
            icon_class = 'fas fa-hourglass-half'
            bg_color = 'bg-info'
            header_text = f"{test.test_name} in progress"
            body_text = f"Patient {test.patient.full_name} - Currently being processed."

        recent_activities.append({
            'timestamp': test.requested_at,
            'icon': icon_class,
            'bg_color': bg_color,
            'header': header_text,
            'body': body_text,
            'link': link_url
        })

    recent_activities.sort(key=lambda x: x['timestamp'], reverse=True)

    context = {
        'test_today': test_today,
        'pending_count': pending_count,
        'completed_count': completed_count,
        'in_progress_count': in_progress_count,
        'total_patients_count': total_patients_count, # Kept global
        'uploaded_results_count': uploaded_results_count, # Kept global

        'today_tests_details': today_tests_details,
        'awaiting_tests': awaiting_tests,

        'weekly_labels': weekly_labels,
        'weekly_tests_data_total': weekly_tests_data_total,
        'weekly_tests_data_completed': weekly_tests_data_completed,
        'recent_activities': recent_activities,

        'dashboard_url': 'laboratory',
        'pending_tests_url': 'lab_internal_logs',
        'test_logs_url': 'lab_internal_logs',
        'lab_test_entry_url': 'lab_test_entry',
        'logout_url': 'logout',
        'user_full_name': request.user.get_full_name() or request.user.username,
    }
    return render(request, 'laboratory/index.html', context)

@login_required(login_url='home')
def lab_test_entry(request):
    lab_tests = LabTest.objects.select_related('patient', 'category').filter(
        status='pending'
    ).order_by('-requested_at')

    # Group tests by status (filtered dataset only contains 'pending')
    tests_by_status = {
        'pending': lab_tests,
        'completed': LabTest.objects.none(),  # no need for completed here
        'in_progress': LabTest.objects.none()  # not used either
    }

    # Prepare structured test data
    tests_data = []
    for test in lab_tests:
        tests_data.append({
            'test': test,
            'patient': test.patient,
            'category': test.category,
            'status': test.status,
            'requested_at': test.requested_at,
            'date_performed': test.date_performed,
            'requested_by': test.requested_by.get_full_name() if test.requested_by else 'System',
            'performed_by': test.performed_by.get_full_name() if test.performed_by else 'N/A'
        })

    # Build patient_map for patients with relevant tests
    patient_map = {}
    for item in tests_data:
        patient_id = item['patient'].id
        if patient_id not in patient_map:
            patient_map[patient_id] = {
                'patient': item['patient'],
                'tests': [],
                'categories': set(),
                'requested_by': item['requested_by'],
                'pending_count': 0,
                'in_progress_count': 0,
                'completed_count': 0,
                'total_tests': 0,
                'referred_by': item['requested_by']
            }
        patient_map[patient_id]['tests'].append(item['test'])
        patient_map[patient_id]['categories'].add(item['category'])
        patient_map[patient_id]['pending_count'] += 1
        patient_map[patient_id]['total_tests'] += 1

    # Statistics
    today = timezone.now().date()
    stats = {
        'total_tests': lab_tests.count(),
        'total_pending_tests': lab_tests.count(),
        'total_completed_today': LabTest.objects.filter(status='completed', date_performed__date=today).count(),
        'total_in_progress': 0,
        'total_categories': TestCategory.objects.count(),
        'unique_patients': len(patient_map),
        'total_patients': len(patient_map),  # used by your template stats
    }

    context = {
        'tests_data': tests_data,
        'test_categories': TestCategory.objects.all(),
        'patients_data': patient_map.values(),
        'stats': stats,
        'debug_info': {
            'total_tests_fetched': len(tests_data),
            'test_categories_count': TestCategory.objects.count(),
            'pending_tests_count': lab_tests.count(),
            'methods_used': [
                'Filtered: status=pending & doctor_comments=0',
                'Grouped by patient',
                'Structured stats for dashboard'
            ]
        } if request.user.is_superuser else None
    }

    return render(request, 'laboratory/test_entry.html', context)

@login_required(login_url='home')
def lab_internal_logs(request):
    lab_tests = LabTest.objects.select_related('patient', 'recorded_by', 'category').order_by('-requested_at')

    logs = []
    for test in lab_tests:
        key_results = test.result_value if test.result_value else "N/A"
        
        display_status = test.status.capitalize() if test.status else "N/A"

        logs.append({
            'id': test.id,
            'date': test.date_performed.date() if test.date_performed else test.requested_at.date(),
            'patient_name': test.patient.full_name,
            'test_type': test.category.name if test.category else "Unknown Test Type",
            'lab_staff': test.recorded_by.get_full_name() if test.recorded_by else "Unknown",
            'key_results': key_results,
            'notes': test.notes if test.notes else '',
            'status': display_status,
        })

    context = {
        'lab_logs': logs,
    }
    return render(request, 'laboratory/logs.html', context)

@login_required
@require_http_methods(["GET"])
def lab_view_ivf_progress(request):
    context = {
        'all_ivf_records': IVFRecord.objects.all().select_related('patient', 'ivf_package', 'treatment_location').order_by('-created_on'),
    }
    return render(request, 'laboratory/ivf_progress.html', context)

def lab_activity_report(request):
    user = request.user
    today = date.today()

    total_tests_requested = LabTest.objects.count()

    pending_tests = LabTest.objects.filter(status='pending').count()
    completed_tests = LabTest.objects.filter(status='completed').count()
    in_progress_tests = LabTest.objects.filter(status='in_progress').count()

    recent_lab_activities = LabTest.objects.filter(
        Q(performed_by=user) | Q(recorded_by=user)
    ).order_by('-date_performed', '-requested_at')[:10]

    recent_lab_files = LabResultFile.objects.filter(uploaded_by=user).order_by('-uploaded_at')[:5]

    context = {
        'total_tests_requested': total_tests_requested,
        'pending_tests': pending_tests,
        'completed_tests': completed_tests,
        'in_progress_tests': in_progress_tests,
        'recent_lab_activities': recent_lab_activities,
        'recent_lab_files': recent_lab_files,
    }

    return render(request, 'laboratory/reports.html', context)

##### Form Action #####

@csrf_exempt
def get_patient_info(request, patient_id):
    try:
        patient = Patient.objects.get(id=patient_id)
        
        # Build photo URL safely
        photo_url = ''
        if patient.photo:
            try:
                photo_url = patient.photo.url
            except:
                photo_url = ''
        
        return JsonResponse({
            # Basic Demographics
            'full_name': patient.full_name or '',
            'date_of_birth': patient.date_of_birth.strftime('%Y-%m-%d') if patient.date_of_birth else '',
            'gender': patient.gender or '',
            'phone': patient.phone or '',
            'email': patient.email or '',
            'marital_status': patient.marital_status or '',
            'address': patient.address or '',
            'nationality': patient.nationality or '',
            'state_of_origin': patient.state_of_origin or '',
            
            # ID Information
            'id_type': patient.id_type or '',
            'id_number': patient.id_number or '',
            
            # Medical Information
            'blood_group': patient.blood_group or '',
            'first_time': patient.first_time or '',
            'referred_by': patient.referred_by or '',
            'notes': patient.notes or '',
            
            # Next of Kin Information - ALL FIELDS
            'next_of_kin_name': patient.next_of_kin_name or '',
            'next_of_kin_phone': patient.next_of_kin_phone or '',
            'next_of_kin_relationship': patient.next_of_kin_relationship or '',
            'next_of_kin_email': patient.next_of_kin_email or '',
            'next_of_kin_address': patient.next_of_kin_address or '',
            
            # Photo
            'photo': photo_url,
        })
        
    except Patient.DoesNotExist:
        return JsonResponse({'error': 'Patient not found'}, status=404)
    except Exception as e:
        logger.error(f"Error fetching patient info {patient_id}: {str(e)}")
        return JsonResponse({'error': 'An error occurred while fetching patient information'}, status=500)
    
def test_details(request, patient_id):
    patient = get_object_or_404(Patient, id=patient_id)

    pending_tests = LabTest.objects.filter(
        patient=patient,
        status='pending'
    ).select_related('category', 'patient')

    grouped_tests = defaultdict(list)
    for test in pending_tests:
        grouped_tests[test.category.name].append(test)

    return render(request, 'laboratory/test_details.html', {
        'pending_tests': dict(grouped_tests),
        'patient': patient
    })

def lab_log_detail_ajax(request):
    log_id = request.GET.get('log_id')
    if not log_id:
        return JsonResponse({"error": "Missing log ID"}, status=400)

    try:
        # Pre-fetch related objects for efficiency
        lab_test = get_object_or_404(LabTest.objects.select_related('patient', 'recorded_by', 'category'), id=log_id)

        data = {
            'patient': lab_test.patient.full_name,
            'test_type': lab_test.category.name if lab_test.category else "Unknown Test Type", # Corrected to category.name
            'date': (lab_test.date_performed or lab_test.requested_at).strftime('%B %d, %Y'), # Use date_performed if exists, else requested_at
            'recorded_by': lab_test.recorded_by.get_full_name() if lab_test.recorded_by else "Unknown",
            'notes': lab_test.notes if lab_test.notes else 'No additional notes provided.', # Access notes directly
            'result_value': lab_test.result_value if lab_test.result_value else "N/A", # General result value
            'normal_range': lab_test.normal_range if lab_test.normal_range else "N/A", # Normal range
        }
        
        return JsonResponse(data)

    except LabTest.DoesNotExist:
        return JsonResponse({"error": "Lab Test not found."}, status=404)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
    
@csrf_exempt
def submit_test_results(request, patient_id):
    if request.method == 'POST':
        patient = get_object_or_404(Patient, id=patient_id)
        test_ids = request.POST.getlist('ids')
        uploaded_file = request.FILES.get('result_file')
        lab_result_file = None

        if uploaded_file:
            try:
                lab_result_file = LabResultFile.objects.create(
                    patient=patient,
                    result_file=uploaded_file,
                    uploaded_by=request.user
                )
            except Exception as e:
                messages.error(request, f'File upload failed: {str(e)}')
                return redirect('lab_test_entry')

        for test_id in test_ids:
            try:
                lab_test = LabTest.objects.get(id=test_id)
                result_value = request.POST.get(lab_test.test_name)

                if result_value:
                    lab_test.result_value = result_value
                    lab_test.status = 'completed'
                    lab_test.testcompleted = True

                    # Fill additional fields
                    lab_test.recorded_by = request.user
                    lab_test.performed_by = request.user
                    lab_test.date_performed = timezone.now()

                    if lab_result_file:
                        lab_test.labresulttestid = lab_result_file.id

                    lab_test.save()
            except LabTest.DoesNotExist:
                continue

        if uploaded_file and lab_result_file:
            messages.success(request, f'Test results updated and file \"{uploaded_file.name}\" uploaded successfully!')
        elif test_ids:
            messages.success(request, 'Test results updated successfully!')
        else:
            messages.warning(request, 'No tests were selected for update.')

        return redirect('lab_test_entry')

    return redirect('lab_test_entry')

@login_required(login_url='home')
def patient_tests_ajax(request, patient_id):
    """
    AJAX endpoint to fetch patient tests data
    """
    try:
        patient = Patient.objects.select_related('ward').get(id=patient_id)
        
        # Get pending tests
        pending_tests = LabTest.objects.filter(
            patient=patient,
            status='pending'
        ).select_related('category', 'requested_by').order_by('-requested_at')
        
        # Get completed tests
        completed_tests = LabTest.objects.filter(
            patient=patient,
            status='completed'
        ).select_related('category', 'completed_by').order_by('-date_performed')
        
        # Get in-progress tests
        in_progress_tests = LabTest.objects.filter(
            patient=patient,
            status='in_progress'
        ).select_related('category', 'requested_by').order_by('-requested_at')
        
        # Format data for JSON response
        pending_tests_data = [{
            'id': test.id,
            'test_name': test.test_name,
            'category': test.category.name if test.category else None,
            'requested_by': test.requested_by.get_full_name() if test.requested_by else 'N/A',
            'requested_at': test.requested_at.strftime('%b %d, %Y %I:%M %p'),
            'normal_range': test.normal_range,
            'instructions': test.instructions,
        } for test in pending_tests]
        
        completed_tests_data = [{
            'id': test.id,
            'test_name': test.test_name,
            'category': test.category.name if test.category else None,
            'completed_by': test.completed_by.get_full_name() if test.completed_by else 'N/A',
            'completed_at': test.date_performed.strftime('%b %d, %Y %I:%M %p') if test.date_performed else 'N/A',
            'result_value': test.result_value[:100] if test.result_value else 'N/A',
            'status': test.status,
        } for test in completed_tests]
        
        in_progress_tests_data = [{
            'id': test.id,
            'test_name': test.test_name,
            'category': test.category.name if test.category else None,
            'requested_by': test.requested_by.get_full_name() if test.requested_by else 'N/A',
            'requested_at': test.requested_at.strftime('%b %d, %Y %I:%M %p'),
        } for test in in_progress_tests]
        
        patient_data = {
            'id': patient.id,
            'full_name': patient.full_name,
            'gender': patient.gender,
            'date_of_birth': patient.date_of_birth.strftime('%b %d, %Y'),
            'blood_group': patient.blood_group or 'N/A',
            'phone': patient.phone,
            'address': patient.address,
            'status': patient.status,
            'is_inpatient': patient.is_inpatient,
            'ward': patient.ward.name if patient.ward else None,
        }
        
        return JsonResponse({
            'success': True,
            'patient': patient_data,
            'pending_tests': pending_tests_data,
            'completed_tests': completed_tests_data,
            'in_progress_tests': in_progress_tests_data,
        })
        
    except Patient.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'Patient not found'
        })


@login_required(login_url='home')
def get_category_subtests(request, category_id):
    """
    AJAX endpoint to fetch sub-tests for a category
    """
    try:
        category = TestCategory.objects.get(id=category_id)
        subtests = TestSubcategory.objects.filter(category=category).order_by('name')
        
        subtests_data = [{
            'id': subtest.id,
            'name': subtest.name,
            'normal_range': subtest.normal_range,
            'unit': subtest.unit,
            'description': subtest.description,
        } for subtest in subtests]
        
        return JsonResponse({
            'success': True,
            'category': {
                'id': category.id,
                'name': category.name,
                'description': category.description,
            },
            'subtests': subtests_data,
        })
        
    except TestCategory.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'Category not found'
        })


@login_required(login_url='home')
def create_test_with_subtests(request):
    """
    Create a new lab test with selected sub-tests
    """
    if request.method == 'POST':
        try:
            patient_id = request.POST.get('patient_id')
            category_id = request.POST.get('category_id')
            selected_subtests = request.POST.getlist('selected_subtests')  # List of subtest IDs
            instructions = request.POST.get('instructions', '')
            
            patient = Patient.objects.get(id=patient_id)
            category = TestCategory.objects.get(id=category_id) if category_id else None
            
            # Create main lab test
            lab_test = LabTest.objects.create(
                patient=patient,
                test_name=f"{category.name} Panel" if category else "Custom Test",
                category=category,
                status='pending',
                requested_by=request.user,
                requested_at=timezone.now(),
                instructions=instructions,
            )
            
            # Create individual sub-test entries
            for subtest_id in selected_subtests:
                subtest = TestSubcategory.objects.get(id=subtest_id)
                LabResultFile.objects.create(
                    lab_test=lab_test,
                    subtest=subtest,
                    status='pending',
                    normal_range=subtest.normal_range,
                    unit=subtest.unit,
                )
            
            return JsonResponse({
                'success': True,
                'message': f'Test created successfully with {len(selected_subtests)} sub-tests',
                'test_id': lab_test.id,
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Error creating test: {str(e)}'
            })
    
    return JsonResponse({
        'success': False,
        'message': 'Invalid request method'
    })


@login_required(login_url='home')
def complete_test_with_results(request):
    """
    Complete a lab test with sub-test results
    """
    if request.method == 'POST':
        try:
            test_id = request.POST.get('test_id')
            lab_test = LabTest.objects.get(id=test_id)
            
            # Update main test
            lab_test.status = 'completed'
            lab_test.completed_by = request.user
            lab_test.date_performed = timezone.now()
            lab_test.result_value = request.POST.get('general_notes', '')
            lab_test.save()
            
            # Update sub-test results
            for key, value in request.POST.items():
                if key.startswith('subtest_result_'):
                    subtest_result_id = key.replace('subtest_result_', '')
                    try:
                        test_result = LabResultFile.objects.get(id=subtest_result_id)
                        test_result.result_value = value
                        test_result.status = 'completed'
                        test_result.completed_at = timezone.now()
                        test_result.save()
                    except LabResultFile.DoesNotExist:
                        continue
            
            return JsonResponse({
                'success': True,
                'message': 'Test completed successfully'
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Error completing test: {str(e)}'
            })
    
    return JsonResponse({
        'success': False,
        'message': 'Invalid request method'
    })

@csrf_exempt
def patient_search(request):
    query = request.GET.get('q', '').strip()
    lab_mode = request.GET.get('lab_mode') == '1'
    results = []

    if query:
        if lab_mode:
            try:
                lab_department = Department.objects.get(name__iexact='Lab')
            except Department.DoesNotExist:
                return JsonResponse({'results': []})
            referred_ids = Referral.objects.filter(department=lab_department).values_list('patient_id', flat=True)
            patients = Patient.objects.filter(id__in=referred_ids, full_name__icontains=query)
        else:
            patients = Patient.objects.filter(full_name__icontains=query)

        results = [{'id': p.id, 'full_name': p.full_name} for p in patients[:10]]

    return JsonResponse({'results': results})
    
''' ############################################################################################################################ End Lab View ############################################################################################################################ '''


''' ############################################################################################################################ HR View ############################################################################################################################ '''

@login_required(login_url='home')
def hr(request):
    """
    Comprehensive HR Dashboard with real data from models
    """
    # Get current date info
    today = timezone.now().date()
    current_month_start = today.replace(day=1)
    
    # === BASIC STAFF METRICS ===
    total_staff = Staff.objects.count()
    total_departments = Department.objects.count()
    
    # Fetch all staff for the Staff Profiles modal and Staff Transitions datalist
    staff_list = Staff.objects.select_related('user', 'department').all()
    # Fetch all departments for the Staff Profiles modal filters and selection
    departments = Department.objects.all()

    # Fetch all patients for relevant modals (e.g., Consultation Notes, Discharge)
    patients = Patient.objects.all()
    
    # Corrected: Fetch doctors as Staff members with the 'doctor' role
    doctors = Staff.objects.filter(role='doctor').select_related('user').all()

    # Get active patients details for monitoring (example structure, adjust based on your Patient model)
    active_patients_details = []
    for patient in patients:
        active_patients_details.append({
            'full_name': patient.full_name, # or patient.user.get_full_name() if Patient links to User
            'status': 'Active', # Replace with actual patient status if available in your model
            'last_vitals_recorded_at': None # Replace with actual field if available
        })

    # === TODAY'S ATTENDANCE DATA ===
    today_attendance = Attendance.objects.filter(date__date=today)
    present_today = today_attendance.filter(status='Present').count()
    absent_today = today_attendance.filter(status='Absent').count()
    on_leave_today = today_attendance.filter(status='On Leave').count()
    
    # Calculate percentages for progress bars
    attendance_percentage = (present_today / total_staff * 100) if total_staff > 0 else 0
    absent_percentage = (absent_today / total_staff * 100) if total_staff > 0 else 0
    leave_percentage = (on_leave_today / total_staff * 100) if total_staff > 0 else 0
    
    # === STAFF TRANSITIONS THIS MONTH ===
    new_hires_month = StaffTransition.objects.filter(
        transition_type='onboarding',
        date__gte=current_month_start,
        date__lte=today
    ).count()
    
    offboarded_month = StaffTransition.objects.filter(
        transition_type='offboarding',
        date__gte=current_month_start,
        date__lte=today
    ).count()
    
    # === RECENT TRANSITIONS (Last 10) ===
    recent_transitions = StaffTransition.objects.order_by('-created_at')[:10]
    
    # === SHIFT ASSIGNMENTS FOR TODAY ===
    shift_assignments_today = ShiftAssignment.objects.filter(date=today).count()
    
    # Get shift distribution for today
    # FIX: Corrected the aggregation for shift_distribution
    shift_distribution = ShiftAssignment.objects.filter(date=today).values('shift').annotate(
        count=Count('shift') # Count directly on 'shift' field within the filtered queryset
    ).order_by('shift')
    
    # === DEPARTMENT STATISTICS ===
    # For Department Chart
    dept_data = Department.objects.annotate(
        staff_count=Count('staff')
    ).values('name', 'staff_count')
    
    department_labels = [dept['name'] for dept in dept_data]
    department_data = [dept['staff_count'] for dept in dept_data]
    
    department_stats = [] # Kept for potential existing usage in template not covered by chart
    colors = ['#007bff', '#28a745', '#ffc107', '#dc3545', '#6f42c1', '#fd7e14', '#20c997', '#6c757d']
    for idx, dept in enumerate(dept_data):
        department_stats.append({
            'name': dept['name'],
            'count': dept['staff_count'],
            'color': colors[idx % len(colors)]
        })
    
    # === ROLE DISTRIBUTION (Gender Distribution) ===
    # For Gender Distribution Chart
    gender_distribution = Staff.objects.values('gender').annotate(count=Count('id'))
    gender_labels = ['Male' if item['gender'] == 'M' else 'Female' for item in gender_distribution]
    gender_data = [item['count'] for item in gender_distribution]

    # For overall role distribution (if needed elsewhere in dashboard)
    role_distribution = Staff.objects.values('role').annotate(
        count=Count('id')
    ).order_by('-count')
    role_display_map = dict(Staff.ROLE_CHOICES)
    for role_item in role_distribution: # Renamed loop variable to avoid conflict with 'role' in outer scope
        role_item['role_display'] = role_display_map.get(role_item['role'], role_item['role'])
    
    # === WEEKLY ATTENDANCE TRENDS ===
    attendance_labels = []
    attendance_present_data = []
    attendance_absent_data = []
    attendance_leave_data = []
    
    for i in range(6, -1, -1):  # Last 7 days
        check_date = today - timedelta(days=i)
        attendance_labels.append(check_date.strftime('%a %m/%d'))
        
        day_attendance = Attendance.objects.filter(date__date=check_date)
        present = day_attendance.filter(status='Present').count()
        absent = day_attendance.filter(status='Absent').count()
        leave = day_attendance.filter(status='On Leave').count()
        
        attendance_present_data.append(present)
        attendance_absent_data.append(absent)
        attendance_leave_data.append(leave)
    
    # === EMERGENCY ALERTS ===
    emergency_alerts = EmergencyAlert.objects.filter(
        timestamp__gte=today
    ).order_by('-timestamp')[:5]
    
    # === PENDING TASKS & NOTIFICATIONS ===
    pending_tasks_count = 0  # Placeholder, implement actual logic
    expiring_certs_count = 0 # Placeholder, implement actual logic
    # Example:
    # from datetime import timedelta
    # thirty_days_from_now = today + timedelta(days=30)
    # expiring_certs_count = StaffCertification.objects.filter(
    #    expiry_date__lte=thirty_days_from_now,
    #    expiry_date__gte=today
    # ).count()
    
    context = {
        # Basic metrics
        'total_staff': total_staff,
        'total_departments': total_departments,
        'present_today': present_today,
        'absent_today': absent_today,
        'on_leave_today': on_leave_today,
        'new_hires_month': new_hires_month,
        'offboarded_month': offboarded_month,
        'shift_assignments_today': shift_assignments_today,
        
        # Percentages for progress bars
        'attendance_percentage': round(attendance_percentage, 1),
        'absent_percentage': round(absent_percentage, 1),
        'leave_percentage': round(leave_percentage, 1),
        
        # Data for Modals
        'staff_list': staff_list,
        'departments': departments, # All departments for filters and selection
        'patients': patients,
        'doctors': doctors, # Now correctly fetches Staff with role='doctor'
        'active_patients_details': active_patients_details, # For monitor modal example

        # Complex data structures
        'department_stats': department_stats,
        'role_distribution': role_distribution,
        'shift_distribution': shift_distribution,
        'recent_transitions': recent_transitions,
        'emergency_alerts': emergency_alerts,
        
        # Chart data (JSON serialized for JavaScript)
        'attendance_labels': json.dumps(attendance_labels),
        'attendance_present_data': json.dumps(attendance_present_data),
        'attendance_absent_data': json.dumps(attendance_absent_data),
        'attendance_leave_data': json.dumps(attendance_leave_data),
        'gender_labels': json.dumps(gender_labels),
        'gender_data': json.dumps(gender_data),
        'department_labels': json.dumps(department_labels),
        'department_data': json.dumps(department_data),
        
        # Notification counters
        'pending_tasks_count': pending_tasks_count,
        'expiring_certs_count': expiring_certs_count,
    }
    
    return render(request, 'hr/index.html', context)

@login_required(login_url='home')
def staff_profiles(request):
    staff_list = Staff.objects.select_related('user', 'department').all()
    departments = Department.objects.all()
    context = {
        'staff_list': staff_list,
        'departments': departments,
    }
    return render(request, 'hr/staff_profiles.html', context)

@login_required(login_url='home')
def staff_attendance_list(request):
    """
    Displays the attendance and shift records.
    Handles the initial GET request for the page.
    """
    today = timezone.localdate()

    try:
        profile = request.user.staff
    except Staff.DoesNotExist:
        messages.error(request, "Your user profile is not set up properly.")
        return redirect('home')

    staff_users = Staff.objects.select_related('user').order_by('user__first_name', 'user__last_name') # Corrected to get Staff objects
    
    # FIX: Pass the SHIFT_CHOICES directly for the dropdown
    shifts = ShiftAssignment.SHIFT_CHOICES 

    attendance_records = Attendance.objects.select_related('staff__staff').order_by('-date')
    shift_records = ShiftAssignment.objects.select_related('staff__staff').order_by('-date')

    return render(request, 'hr/staff_attendance_shift.html', {
        'attendance_records': attendance_records,
        'shift_records': shift_records,
        'profile': profile,
        'staff_users': staff_users,
        'shifts': shifts,
        'today': today,
    })

@login_required(login_url='home')
def staff_transitions(request):
    staff_list = Staff.objects.all().order_by('user__first_name')
    transitions = StaffTransition.objects.all().order_by('-date', '-created_at')

    if request.method == 'POST':
        full_name = request.POST.get('full_name')
        transition_type = request.POST.get('type')
        date = request.POST.get('date')
        notes = request.POST.get('notes')

        if full_name and transition_type in ['onboarding', 'offboarding'] and date:
            StaffTransition.objects.create(
                full_name=full_name.strip(),
                transition_type=transition_type,
                date=date,
                notes=notes,
                created_by=request.user
            )
            messages.success(request, "Staff transition recorded successfully.")
            return redirect('staff_transitions')
        else:
            messages.error(request, "Please fill all required fields correctly.")

    return render(request, 'hr/staff_transitions.html', {
        'staff_list': staff_list,
        'transitions': transitions,
    })

@login_required(login_url='home')
def hr_act_report(request):
    """
    Comprehensive HR report view showing all HR-related activities
    for the logged-in HR user
    """
    
    # Verify user is HR staff
    try:
        hr_staff = Staff.objects.get(user=request.user, role='hr')
    except Staff.DoesNotExist:
        # Handle case where user is not HR staff
        context = {
            'error_message': 'Access denied. You must be HR staff to view this report.',
            'is_hr': False
        }
        return render(request, 'hr/reports.html', context)
    
    # Date range for filtering (default to current month)
    today = timezone.now().date()
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    if start_date:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    else:
        start_date = today.replace(day=1)  # First day of current month
    
    if end_date:
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    else:
        end_date = today
    
    # =====================================================
    # STAFF MANAGEMENT DATA
    # =====================================================
    
    # All staff members
    all_staff = Staff.objects.select_related('user', 'department').all()
    
    # Active staff (users who are active)
    active_staff = all_staff.filter(user__is_active=True)
    
    # Staff by role breakdown
    staff_by_role = all_staff.values('role').annotate(count=Count('id')).order_by('role')
    
    # Staff by department breakdown
    staff_by_department = all_staff.filter(department__isnull=False).values(
        'department__name'
    ).annotate(count=Count('id')).order_by('department__name')
    
    # Recently joined staff (last 30 days)
    recent_staff = all_staff.filter(
        date_joined__gte=today - timedelta(days=30)
    ).select_related('user', 'department')
    
    # =====================================================
    # ATTENDANCE DATA
    # =====================================================
    
    # Attendance records for date range
    attendance_records = Attendance.objects.filter(
        date__date__range=[start_date, end_date]
    ).select_related('staff').order_by('-date')
    
    # Attendance summary by status
    attendance_summary = attendance_records.values('status').annotate(
        count=Count('id')
    ).order_by('status')
    
    # Staff with perfect attendance in the period
    total_days = (end_date - start_date).days + 1
    perfect_attendance_staff = []
    
    for staff_member in active_staff:
        present_days = attendance_records.filter(
            staff=staff_member.user, # Assuming Attendance.staff links to User
            status='Present'
        ).count()
        
        if present_days == total_days:
            perfect_attendance_staff.append(staff_member)
    
    # Recent absences (last 7 days)
    recent_absences = attendance_records.filter(
        date__date__gte=today - timedelta(days=7),
        status__in=['Absent', 'On Leave']
    ).select_related('staff')
    
    # =====================================================
    # SHIFT MANAGEMENT DATA
    # =====================================================
    
    # All distinct shift types available (e.g., 'Morning', 'Afternoon', 'Night')
    # FIX: Get SHIFT_CHOICES directly, as 'shift' is a CharField, not a ForeignKey to a Shift model.
    all_shifts_types = ShiftAssignment.SHIFT_CHOICES
    
    # Shift assignments for the date range
    # FIX: Remove select_related('shift') as 'shift' is a CharField.
    shift_assignments = ShiftAssignment.objects.filter(
        date__range=[start_date, end_date]
    ).select_related('staff').order_by('-date')
    
    # Shift distribution
    # FIX: Use 'shift' directly, not 'shift__name'.
    shift_distribution = shift_assignments.values('shift').annotate(
        count=Count('id')
    ).order_by('shift')
    
    # Current week's shift assignments
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)
    # FIX: Remove select_related('shift') and use 'shift' directly in order_by.
    current_week_shifts = ShiftAssignment.objects.filter(
        date__range=[week_start, week_end]
    ).select_related('staff').order_by('date', 'shift')
    
    # =====================================================
    # STAFF TRANSITIONS DATA
    # =====================================================
    
    # All staff transitions
    all_transitions = StaffTransition.objects.filter(
        date__range=[start_date, end_date]
    ).order_by('-date')
    
    # Onboarding in the period
    onboarding_transitions = all_transitions.filter(transition_type='onboarding')
    
    # Offboarding in the period
    offboarding_transitions = all_transitions.filter(transition_type='offboarding')
    
    # Transitions created by this HR user
    hr_created_transitions = all_transitions.filter(created_by=request.user)
    
    # =====================================================
    # HANDOVER LOGS DATA
    # =====================================================
    
    # Recent handover logs
    recent_handovers = HandoverLog.objects.filter(
        timestamp__date__range=[start_date, end_date]
    ).select_related('author', 'recipient', 'patient').order_by('-timestamp')
    
    # Handovers by staff member
    handover_summary = recent_handovers.values(
        'author__first_name', 'author__last_name'
    ).annotate(count=Count('id')).order_by('-count')
    
    # =====================================================
    # DEPARTMENT DATA
    # =====================================================
    
    # All departments with staff count
    departments_with_staff = Department.objects.annotate(
        staff_count=Count('staff')
    ).order_by('name')
    
    # =====================================================
    # HR METRICS & ANALYTICS
    # =====================================================
    
    # Staff utilization rate (present vs total staff)
    total_active_staff = active_staff.count()
    if total_active_staff > 0:
        latest_attendance_date = attendance_records.first()
        if latest_attendance_date:
            present_today = attendance_records.filter(
                date__date=latest_attendance_date.date.date(),
                status='Present'
            ).count()
            utilization_rate = (present_today / total_active_staff) * 100
        else:
            utilization_rate = 0
    else:
        utilization_rate = 0
    
    # Absenteeism rate
    total_attendance_records = attendance_records.count()
    absent_records = attendance_records.filter(status='Absent').count()
    absenteeism_rate = (absent_records / total_attendance_records * 100) if total_attendance_records > 0 else 0
    
    # Turnover data (approximation based on transitions)
    monthly_offboarding = offboarding_transitions.count()
    turnover_rate = (monthly_offboarding / total_active_staff * 100) if total_active_staff > 0 else 0
    
    # =====================================================
    # EXPENSE DATA (HR related)
    # =====================================================
    
    # HR-related expenses (if any expense categories are HR-related)
    hr_expenses = Expense.objects.filter(
        expense_date__range=[start_date, end_date],
        # Add filters for HR-related categories if they exist
        # category__name__icontains='hr'  # Uncomment if you have HR expense categories
    ).order_by('-expense_date')
    
    # Total HR expenses
    total_hr_expenses = hr_expenses.aggregate(
        total=Sum('amount')
    )['total'] or 0

    # Staff by role breakdown (add these lines after your existing staff_by_role query)
    staff_roles = [item['role'] for item in staff_by_role]
    staff_counts = [item['count'] for item in staff_by_role]

    # Attendance summary by status (add these lines after your existing attendance_summary query)
    attendance_statuses = [item['status'] for item in attendance_summary]
    attendance_counts = [item['count'] for item in attendance_summary]
    
    # =====================================================
    # COMPILE CONTEXT DATA
    # =====================================================
    
    context = {
        'is_hr': True,
        'hr_staff': hr_staff,
        'start_date': start_date,
        'end_date': end_date,
        'today': today,
        
        # Staff Data
        'all_staff': all_staff,
        'active_staff': active_staff,
        'total_staff_count': all_staff.count(),
        'active_staff_count': active_staff.count(),
        'staff_by_role': staff_by_role,
        'staff_by_department': staff_by_department,
        'recent_staff': recent_staff,
        
        # Attendance Data
        'attendance_records': attendance_records[:50],  # Limit for display
        'attendance_summary': attendance_summary,
        'perfect_attendance_staff': perfect_attendance_staff,
        'recent_absences': recent_absences,
        'utilization_rate': round(utilization_rate, 2),
        'absenteeism_rate': round(absenteeism_rate, 2),
        
        # Shift Data
        'all_shifts_types': all_shifts_types, # Changed to all_shifts_types to reflect it's the choices
        'shift_assignments': shift_assignments[:30],  # Limit for display
        'shift_distribution': shift_distribution,
        'current_week_shifts': current_week_shifts,
        
        # Transition Data
        'all_transitions': all_transitions,
        'onboarding_transitions': onboarding_transitions,
        'offboarding_transitions': offboarding_transitions,
        'hr_created_transitions': hr_created_transitions,
        'turnover_rate': round(turnover_rate, 2),
        
        # Handover Data
        'recent_handovers': recent_handovers[:30],  # Limit for display
        'handover_summary': handover_summary[:10],  # Top 10
        
        # Department Data
        'departments_with_staff': departments_with_staff,
        
        # Financial Data
        'hr_expenses': hr_expenses[:20],  # Limit for display
        'total_hr_expenses': total_hr_expenses,

        'staff_roles_json': json.dumps(staff_roles), # New context variable
        'staff_counts_json': json.dumps(staff_counts), # New context variable
        'attendance_statuses_json': json.dumps(attendance_statuses), # New context variable
        'attendance_counts_json': json.dumps(attendance_counts),
        
        # Summary Statistics
        'summary_stats': {
            'total_staff': all_staff.count(),
            'active_staff': active_staff.count(),
            'total_departments': departments_with_staff.count(),
            'total_attendance_records': total_attendance_records,
            'total_handovers': recent_handovers.count(),
            'total_transitions': all_transitions.count(),
            'utilization_rate': round(utilization_rate, 2),
            'absenteeism_rate': round(absenteeism_rate, 2),
            'turnover_rate': round(turnover_rate, 2),
        }
    }
    
    return render(request, 'hr/reports.html', context)

##### Form Actions #####

@csrf_exempt
def edit_staff_profile(request, staff_id):
    try:
        profile = Staff.objects.select_related('user').get(id=staff_id)
        role = request.POST.get('role')
        department_id = request.POST.get('department')
        phone = request.POST.get('phone_number')
        address = request.POST.get('address')

        profile.role = role
        profile.phone_number = phone
        profile.address = address
        if department_id:
            profile.department_id = department_id
        else:
            profile.department = None
        profile.save()

        return JsonResponse({
            'success': True,
            'role': profile.get_role_display(),
            'department': profile.department.name if profile.department else '—',
            'phone': profile.phone_number or '—',
            'name': f"{profile.user.first_name} {profile.user.last_name}",
        })
    except Staff.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Staff not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@csrf_exempt
def change_staff_password(request, staff_id):
    try:
        profile = Staff.objects.select_related('user').get(id=staff_id)
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')

        if new_password != confirm_password:
            return JsonResponse({'success': False, 'error': 'Passwords do not match'})

        profile.user.set_password(new_password)
        profile.user.save()

        return JsonResponse({'success': True})
    except Staff.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Staff not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
    
@login_required(login_url='home')
def record_attendance_view(request):
    """
    Handles the POST request for recording staff attendance.
    This view should only be accessible via POST requests from the form.
    """
    if request.method == 'POST':
        today = timezone.localdate() # Use localdate for consistency
        staff_id = request.POST.get('staff_name')
        date_input = request.POST.get('date') or today
        status = request.POST.get('status')

        try:
            date_obj = parse_date_to_datetime(date_input)
            staff_user = User.objects.filter(staff__isnull=False).get(id=staff_id)
        except User.DoesNotExist:
            messages.error(request, "Selected staff not found.")
            return redirect('staff_attendance_shift')
        except ValueError as e:
            messages.error(request, f"Invalid date format: {e}")
            return redirect('staff_attendance_shift')

        Attendance.objects.update_or_create(
            staff=staff_user,
            date=date_obj,
            defaults={'status': status}
        )
        messages.success(request, "Attendance recorded successfully.")
        return redirect('staff_attendance_shift')
    else:
        # If someone tries to access this URL via GET, redirect them to the main page
        return redirect('staff_attendance_shift')


@login_required(login_url='home')
def assign_shift_view(request):
    """
    Handles the POST request for assigning shifts to staff.
    This view should only be accessible via POST requests from the form.
    """
    if request.method == 'POST':
        today = timezone.localdate()
        staff_id = request.POST.get('staff_name')
        shift_id = request.POST.get('shift')  # Change this to shift_id
        date_input = request.POST.get('date') or today

        try:
            date_obj = parse_date_to_datetime(date_input)
            staff_user = User.objects.filter(staff__isnull=False).get(id=staff_id)
            shift = ShiftAssignment.objects.get(id=shift_id)  # Change this to id=shift_id
        except User.DoesNotExist:
            messages.error(request, "Selected staff not found.")
            return redirect('staff_attendance_shift')
        except ShiftAssignment.DoesNotExist:
            messages.error(request, f"Shift with ID '{shift_id}' not found.") # Updated error message
            return redirect('staff_attendance_shift')
        except ValueError as e:
            messages.error(request, f"Invalid date format: {e}")
            return redirect('staff_attendance_shift')

        ShiftAssignment.objects.update_or_create(
            staff=staff_user,
            date=date_obj,
            defaults={'shift': shift}
        )
        messages.success(request, "Shift assigned successfully.")
        return redirect('staff_attendance_shift')
    else:
        return redirect('staff_attendance_shift')
    
@login_required
@require_GET
def get_hr_activity_detail(request, activity_type, id):
    try:
        if activity_type == 'staff':
            staff = get_object_or_404(Staff, id=id)
            data = {
                'title': f"Staff: {staff.user.get_full_name()}",
                'content': f"""
                    <div class="row">
                        <div class="col-md-6">
                            <p><strong>Role:</strong> {staff.get_role_display()}</p>
                            <p><strong>Department:</strong> {staff.department.name if staff.department else 'None'}</p>
                            <p><strong>Joined:</strong> {staff.date_joined}</p>
                        </div>
                        <div class="col-md-6">
                            <p><strong>Status:</strong> {'Active' if staff.user.is_active else 'Inactive'}</p>
                            <p><strong>Phone:</strong> {staff.phone_number or 'N/A'}</p>
                            <p><strong>Email:</strong> {staff.user.email}</p>
                        </div>
                    </div>
                """
            }
        
        elif activity_type == 'attendance':
            attendance = get_object_or_404(Attendance, id=id)
            data = {
                'title': f"Attendance: {attendance.staff.get_full_name()}",
                'content': f"""
                    <p><strong>Date:</strong> {attendance.date}</p>
                    <p><strong>Status:</strong> {attendance.status}</p>
                    <p><strong>Staff:</strong> {attendance.staff.get_full_name()}</p>
                """
            }
            
        elif activity_type == 'shift':
            shift = get_object_or_404(ShiftAssignment, id=id)
            data = {
                'title': f"Shift Assignment",
                'content': f"""
                    <p><strong>Staff:</strong> {shift.staff.get_full_name()}</p>
                    <p><strong>Shift:</strong> {shift.shift.name}</p>
                    <p><strong>Date:</strong> {shift.date}</p>
                """
            }
            
        elif activity_type == 'transition':
            transition = get_object_or_404(StaffTransition, id=id)
            data = {
                'title': f"Staff Transition",
                'content': f"""
                    <p><strong>Staff:</strong> {transition.full_name}</p>
                    <p><strong>Type:</strong> {transition.get_transition_type_display()}</p>
                    <p><strong>Date:</strong> {transition.date}</p>
                    <p><strong>Notes:</strong> {transition.notes or 'None'}</p>
                """
            }
            
        elif activity_type == 'handover':
            handover = get_object_or_404(HandoverLog, id=id)
            data = {
                'title': f"Handover Details",
                'content': f"""
                    <p><strong>From:</strong> {handover.author.get_full_name()}</p>
                    <p><strong>To:</strong> {handover.recipient.get_full_name()}</p>
                    <p><strong>Patient:</strong> {handover.patient.full_name}</p>
                    <p><strong>Time:</strong> {handover.timestamp}</p>
                    <p><strong>Notes:</strong> {handover.notes}</p>
                """
            }
            
        elif activity_type == 'expense':
            expense = get_object_or_404(Expense, id=id)
            data = {
                'title': f"Expense Details",
                'content': f"""
                    <p><strong>Amount:</strong> ${expense.amount}</p>
                    <p><strong>Category:</strong> {expense.category.name}</p>
                    <p><strong>Date:</strong> {expense.expense_date}</p>
                    <p><strong>Description:</strong> {expense.description}</p>
                    <p><strong>Status:</strong> {expense.get_status_display()}</p>
                """
            }
            
        else:
            return JsonResponse({'error': 'Invalid activity type'}, status=400)
            
        return JsonResponse(data)
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

''' ############################################################################################################################ End HR View ############################################################################################################################ '''

''' ############################################################################################################################ Receptionist View ############################################################################################################################ '''

@login_required(login_url='home')
def receptionist(request):
    today = localdate()
    start_of_week = today - timedelta(days=today.weekday())

    current_receptionist = request.user

    recent_activity = Patient.objects.filter(
        registered_by=current_receptionist
    ).order_by('-date_registered')[:5]

    new_patients_today = Patient.objects.filter(
        date_registered__date=today,
        registered_by=current_receptionist
    ).count()

    active_patients = Patient.objects.count()

    appointments_today = Appointment.objects.filter(
        scheduled_time__date=today,
        scheduled_by=current_receptionist
    ).count()

    admissions_this_week = Admission.objects.filter(
        admitted_on__range=[start_of_week, today],
        admitted_by=current_receptionist
    ).count()

    queue = Appointment.objects.filter(
        scheduled_time__date=today,
        scheduled_by=current_receptionist
    ).order_by('scheduled_time')[:5]

    context = {
        'new_patients_today': new_patients_today,
        'active_patients': active_patients,
        'appointments_today': appointments_today,
        'admissions_this_week': admissions_this_week,
        'recent_activity': recent_activity,
        'queue': queue,
    }
    return render(request, 'receptionist/index.html', context)

@login_required(login_url='home')
def register_patient(request):
    patients = Patient.objects.all().order_by('-date_registered')
    departments = Department.objects.all()

    doctors = Staff.objects.filter(role='doctor')
    nurses = Staff.objects.filter(role='nurse')

    return render(request, 'receptionist/register.html', {
        'patients': patients,
        'department': departments,
        'doctors': doctors,
        'nurses': nurses,
    })

@login_required(login_url='home')
def receptionist_activity_report(request):
    user = request.user
    
    patients_registered = Patient.objects.filter(registered_by=user).order_by('-date_registered')
    
    admissions_made = Admission.objects.filter(admitted_by=user).order_by('-admission_date')

    appointments_scheduled = Appointment.objects.filter(patient__registered_by=user).order_by('-scheduled_time')
    
    referrals_made = Referral.objects.filter(patient__registered_by=user).order_by('-created_at')

    # Aggregated data
    total_patients_registered = patients_registered.count()
    total_admissions_made = admissions_made.count()
    total_appointments_scheduled = appointments_scheduled.count()
    total_referrals_made = referrals_made.count()

    context = {
        'patients_registered': patients_registered,
        'admissions_made': admissions_made,
        'appointments_scheduled': appointments_scheduled,
        'referrals_made': referrals_made,
        'total_patients_registered': total_patients_registered,
        'total_admissions_made': total_admissions_made,
        'total_appointments_scheduled': total_appointments_scheduled,
        'total_referrals_made': total_referrals_made,
    }
    return render(request, 'receptionist/activity_report.html', context)

@csrf_exempt
def register_p(request):
    if request.method == 'POST':
        data = request.POST
        photo = request.FILES.get('photo')

        # Basic required fields
        full_name = data.get('full_name')
        date_of_birth = data.get('date_of_birth')
        gender = data.get('gender')
        phone = data.get('phone')
        marital_status = data.get('marital_status')
        address = data.get('address')
        nationality = data.get('nationality')
        next_of_kin_name = data.get('next_of_kin_name')
        next_of_kin_phone = data.get('next_of_kin_phone')
        next_of_kin_relationship = data.get('next_of_kin_relationship')

        if not all([full_name, date_of_birth, gender, phone, marital_status, address,
                    nationality, next_of_kin_name, next_of_kin_phone, next_of_kin_relationship]):
            messages.error(request, "Please fill all required fields marked with *.")
            return redirect('register_patient')

        # Check for duplicates
        if Patient.objects.filter(full_name=full_name, date_of_birth=date_of_birth).exists():
            messages.warning(request, "A patient with this name and date of birth already exists.")
            return redirect('register_patient')

        try:
            patient = Patient.objects.create(
                full_name=full_name,
                date_of_birth=date_of_birth,
                gender=gender,
                phone=phone,
                email=data.get('email'),
                marital_status=marital_status,
                address=address,
                nationality=nationality,
                state_of_origin=data.get('state_of_origin'),
                registered_by=request.user,
                id_type=data.get('id_type'),
                id_number=data.get('id_number'),
                photo=photo,
                blood_group=data.get('blood_group'),
                referred_by=data.get('referred_by'),
                notes=data.get('notes'),
                first_time=data.get('first_time'),

                # Next of kin
                next_of_kin_name=next_of_kin_name,
                next_of_kin_phone=next_of_kin_phone,
                next_of_kin_relationship=next_of_kin_relationship,
                next_of_kin_email=data.get('next_of_kin_email'),
                next_of_kin_address=data.get('next_of_kin_address'),
            )

            messages.success(request, f"Patient '{patient.full_name}' registered successfully.")
            return redirect('register_patient')

        except Exception as e:
            messages.error(request, f"An error occurred during registration: {e}")
            return redirect('register_patient')

    return redirect('register_patient')

@csrf_exempt
def admit_patient(request):
    if request.method == 'POST':
        patient_id = request.POST.get('patient_id')
        reason = request.POST.get('admission_reason')
        attending_id = request.POST.get('attending')

        if not all([patient_id, reason, attending_id]):
            messages.error(request, "All fields are required.")
            return redirect('register_patient')

        try:
            patient = Patient.objects.get(id=patient_id)
        except Patient.DoesNotExist:
            messages.error(request, "Selected patient not found.")
            return redirect('register_patient')

        # Check for existing admission
        if Admission.objects.filter(patient=patient, status='Admitted').exists():
            messages.warning(request, f"{patient.full_name} is already admitted and not yet discharged.")
            return redirect('register_patient')

        try:
            attending_profile = Staff.objects.get(user__id=attending_id).user  # Access the actual User object
        except Staff.DoesNotExist:
            messages.error(request, "Attending staff not found.")
            return redirect('register_patient')

        # Update patient status
        patient.is_inpatient = True
        patient.status = 'stable'
        patient.notes = reason
        patient.save()

        # Create admission
        Admission.objects.create(
            patient=patient,
            doctor_assigned=attending_profile,
            admitted_by=request.user,
            status='Admitted'
        )

        messages.success(request, f"{patient.full_name} has been admitted successfully.")
        return redirect('register_patient')

    return redirect('register_patient')

@csrf_exempt
def update_patient_info(request):
    if request.method == 'POST':
        patient_id = request.POST.get('patient_id')
        
        if not patient_id:
            messages.error(request, "Patient ID is required.")
            return redirect('register_patient')
            
        try:
            patient = Patient.objects.get(id=patient_id)
            
            # Update basic information
            patient.full_name = request.POST.get('full_name', patient.full_name)
            
            # Handle date parsing - CORRECTED: use 'date_of_birth' not 'dob'
            dob = request.POST.get('date_of_birth')
            if dob:
                try:
                    patient.date_of_birth = parse_date(dob)
                except:
                    logger.warning(f"Invalid date format: {dob}")
            
            patient.gender = request.POST.get('gender', patient.gender)
            patient.phone = request.POST.get('phone', patient.phone)
            patient.email = request.POST.get('email') or patient.email
            patient.marital_status = request.POST.get('marital_status') or patient.marital_status
            patient.address = request.POST.get('address', patient.address)
            patient.nationality = request.POST.get('nationality', patient.nationality)
            patient.state_of_origin = request.POST.get('state_of_origin') or patient.state_of_origin
            patient.id_type = request.POST.get('id_type') or patient.id_type
            patient.id_number = request.POST.get('id_number') or patient.id_number
            
            # Handle photo upload if present
            if 'photo' in request.FILES and request.FILES['photo']:
                patient.photo = request.FILES['photo']
            
            # Update additional medical info
            patient.blood_group = request.POST.get('blood_group') or patient.blood_group
            patient.first_time = request.POST.get('first_time') or patient.first_time
            patient.referred_by = request.POST.get('referred_by') or patient.referred_by
            patient.notes = request.POST.get('notes') or patient.notes
            
            # Update Next of Kin information
            patient.next_of_kin_name = request.POST.get('next_of_kin_name', patient.next_of_kin_name)
            patient.next_of_kin_phone = request.POST.get('next_of_kin_phone', patient.next_of_kin_phone)
            patient.next_of_kin_relationship = request.POST.get('next_of_kin_relationship') or patient.next_of_kin_relationship
            patient.next_of_kin_email = request.POST.get('next_of_kin_email') or patient.next_of_kin_email
            patient.next_of_kin_address = request.POST.get('next_of_kin_address') or patient.next_of_kin_address
            
            patient.save()
            
            messages.success(request, f"Patient {patient.full_name}'s information updated successfully.")
            
        except Patient.DoesNotExist:
            messages.error(request, "Patient not found.")
        except Exception as e:
            messages.error(request, f"An error occurred while updating patient information: {str(e)}")
            logger.error(f"Error updating patient {patient_id}: {str(e)}")
            
        return redirect('register_patient')
    
    return redirect('register_patient')

@csrf_exempt
def schedule_appointment(request):
    if request.method == 'POST':
        patient_id = request.POST.get('patient_id')
        department_id = request.POST.get('department')
        scheduled_time = request.POST.get('scheduled_time')

        try:
            patient = Patient.objects.get(id=patient_id)
            department = Department.objects.get(id=department_id)

            existing = Appointment.objects.filter(patient=patient, department=department).first()

            if existing:
                existing.scheduled_time = scheduled_time
                existing.save()
                messages.success(request, "Appointment rescheduled successfully.")
            else:
                Appointment.objects.create(
                    patient=patient,
                    department=department,
                    scheduled_time=scheduled_time,
                    scheduled_by=request.user
                )
                messages.success(request, "Appointment scheduled successfully.")
        
        except Patient.DoesNotExist:
            messages.error(request, "Patient not found.")
        except Department.DoesNotExist:
            messages.error(request, "Selected department not found.")

        return redirect('register_patient')

@csrf_exempt
def refer_patient(request):
    if request.method == 'POST':
        patient_id = request.POST.get('patient_id')
        department_id = request.POST.get('department')
        notes = request.POST.get('notes')

        try:
            patient = Patient.objects.get(id=patient_id)
            department = Department.objects.get(id=department_id)

            Referral.objects.create(
                patient=patient,
                department=department,
                notes=notes,
                referred_by=request.user
            )
            messages.success(request, "Patient referred successfully.")
        except Patient.DoesNotExist:
            messages.error(request, "Patient not found.")
        except Department.DoesNotExist:
            messages.error(request, "Department not found.")
        
        referer = request.META.get('HTTP_REFERER', '/')
        return redirect(referer)
    
''' ############################################################################################################################ End Receptionist View ############################################################################################################################ '''


#notification icon 


def notification_data(request):
    today = date.today()
    notifications = []

    test_outstanding = LabTest.objects.filter(testcompleted=False).count()
    if test_outstanding > 0:
        notifications.append({
            "title": "Test Outstanding",
            "count": test_outstanding,
            "url": "/tests/pending/"
        })

    appointments_today = Appointment.objects.filter(scheduled_time=today).count()
    if appointments_today > 0:
        notifications.append({
            "title": "Appointments Available",
            "count": appointments_today,
            "url": "/results/available/"
        })

    test_results = LabTest.objects.filter(testcompleted=True).count()
    if test_results > 0:
        notifications.append({
            "title": "Available Test Results",
            "count": test_results,
            "url": "/bookings/"
        })

    return JsonResponse({
        "notifications": notifications
    })


"""def notification_data(request):
    return JsonResponse({
        "notifications": [
            {
                "title": "Test Outstanding",
                "count": LabTest.objects.filter(testcompleted=False).count(),
                "url": "/tests/pending/"
            },
         
            {
                "title": "Appointments Available",
                "count": Appointment.objects.filter(scheduled_time=today).count(),
                "url": "/results/available/"
            },
            {
                "title": "Available Test results",
                "count": LabTest.objects.filter(testcompleted=True).count(),
                "url": "/bookings/"
            },
        ]
    })"""

# @login_required(login_url='home')
# def monitoring(request):
#     patient_id = request.GET.get("patient_id")
#     patient = Patient.objects.filter(id=patient_id).first() if patient_id else None

#     context = {
#         "all_patients": Patient.objects.all(),
#         "patient": patient,
#         "consultations": patient.consultations.all() if patient else [],
#         "prescriptions": patient.prescriptions.all() if patient else [],
#         "vitals": patient.vitals_set.all() if patient else [],
#         "notes": patient.nursing_notes.all() if patient else [],
#         "careplans": patient.careplan_set.all() if patient else [],
#         "admissions": patient.admission_set.all() if patient else [],
#     }
#     return render(request, "doctors/treatment_monitoring.html", context)

@login_required(login_url='home')                          
def ae(request):     
    return render(request, 'ae/base.html')


# Pharmacy Views
@login_required(login_url='home')
def pharmacy(request):
    return render(request, 'pharmacy/index.html')

@login_required(login_url='home')
def review_prescriptions(request):
    return render(request, 'pharmacy/prescriptions.html')

@login_required(login_url='home')
def dispense_medications(request):
    return render(request, 'pharmacy/medication.html')

@login_required(login_url='home')
def manage_inventory(request):
    return render(request, 'pharmacy/inventory.html')

@login_required(login_url='home')
def reorder_alerts(request):
    return render(request, 'pharmacy/alerts.html')

# @login_required(login_url='home')
# def institution_financials(request):
#     return render(request, 'accounts/financials.html')

# @login_required(login_url='home')
# def financial_reports(request):
#     return render(request, 'accounts/financial_reports.html')

# @login_required(login_url='home')
# def budget_planning(request):
#     return render(request, 'accounts/planning.html')






    
def parse_date_to_datetime(date_str_or_obj):
    if isinstance(date_str_or_obj, str):
        dt = datetime.strptime(date_str_or_obj, '%Y-%m-%d')
        return timezone.make_aware(dt, timezone.get_current_timezone())
    elif isinstance(date_str_or_obj, datetime):
        if timezone.is_naive(date_str_or_obj):
            return timezone.make_aware(date_str_or_obj, timezone.get_current_timezone())
        return date_str_or_obj
    elif isinstance(date_str_or_obj, date) and not isinstance(date_str_or_obj, datetime):
        dt = datetime.combine(date_str_or_obj, datetime.min.time())
        return timezone.make_aware(dt, timezone.get_current_timezone())
    else:
        return timezone.now()


@login_required(login_url='home')             
def inventory(request):
    return render(request, 'inventory/base.html')

# HMS Admin Views
@login_required(login_url='home')
def hms_admin(request):
    current_month = date.today().month
    current_year = date.today().year
    today = date.today()
    thirty_days_ago = timezone.now() - timedelta(days=30)
    start_of_month = date(current_year, current_month, 1)

    staff_active_count = Staff.objects.filter(user__is_active=True).count()
    total_doctors = Staff.objects.filter(role='doctor', user__is_active=True).count()
    total_nurses = Staff.objects.filter(role='nurse', user__is_active=True).count()

    staff_by_role = Staff.objects.values('role').annotate(count=Count('role')).order_by('role')

    staff_by_department = Staff.objects.filter(department__isnull=False)\
                                    .values('department__name')\
                                    .annotate(count=Count('department__name'))\
                                    .order_by('department__name')

    attendance_summary = Attendance.objects.filter(date__gte=thirty_days_ago)\
                                        .values('status')\
                                        .annotate(count=Count('status'))\
                                        .order_by('status')

    staff_transitions_summary = StaffTransition.objects.values('transition_type')\
                                                    .annotate(count=Count('transition_type'))\
                                                    .order_by('transition_type')

    total_patients = Patient.objects.count()
    patients_admitted = Admission.objects.filter(status='Admitted').count()

    new_patients_last_30_days = Patient.objects.filter(date_registered__gte=thirty_days_ago).count()

    recent_patients = Patient.objects.order_by('-date_registered')[:5]

    patients_by_gender = Patient.objects.values('gender').annotate(count=Count('gender')).order_by('gender')

    patients_by_age_group_raw = Patient.objects.annotate(age=models.functions.ExtractYear(date.today()) - models.functions.ExtractYear('date_of_birth'))\
                                            .values('age')\
                                            .annotate(count=Count('age'))\
                                            .order_by('age')

    age_groups = {
        '0-12': 0, '13-19': 0, '20-39': 0, '40-59': 0, '60+': 0
    }
    for p in patients_by_age_group_raw:
        age = p['age']
        if age <= 12:
            age_groups['0-12'] += p['count']
        elif 13 <= age <= 19:
            age_groups['13-19'] += p['count']
        elif 20 <= age <= 39:
            age_groups['20-39'] += p['count']
        elif 40 <= age <= 59:
            age_groups['40-59'] += p['count']
        else:
            age_groups['60+'] += p['count']
    patients_by_age_group = [{'age_group': k, 'count': v} for k, v in age_groups.items()]


    patients_by_blood_group = Patient.objects.values('blood_group').annotate(count=Count('blood_group')).order_by('blood_group')

    patients_by_status = Patient.objects.values('status').annotate(count=Count('status')).order_by('status')

    pending_lab_tests = LabTest.objects.filter(status='pending').count()
    upcoming_appointments_today = Appointment.objects.filter(
        scheduled_time__date=today
    ).count()

    recent_appointments = Appointment.objects.filter(
        scheduled_time__gte=timezone.now()
    ).order_by('scheduled_time')[:5]

    total_lab_tests = LabTest.objects.count()
    completed_lab_tests = LabTest.objects.filter(status='completed').count()
    lab_completion_rate = (completed_lab_tests / total_lab_tests * 100) if total_lab_tests > 0 else 0

    total_prescriptions = Prescription.objects.count()

    lab_tests_by_status = LabTest.objects.values('status').annotate(count=Count('status')).order_by('status')

    top_lab_tests = LabTest.objects.values('test_name').annotate(count=Count('test_name')).order_by('-count')[:5]

    pending_bills_amount = PatientBill.objects.filter(status='pending').aggregate(total_amount=Sum('final_amount'))['total_amount'] or 0.00


    monthly_revenue = Payment.objects.filter(
        status='completed',
        payment_date__year=current_year,
        payment_date__month=current_month
    ).aggregate(total_amount=Sum('amount'))['total_amount'] or 0.00

    monthly_expenses = Expense.objects.filter(
        status='approved',
        expense_date__year=current_year,
        expense_date__month=current_month
    ).aggregate(total_amount=Sum('amount'))['total_amount'] or 0.00

    total_income = Payment.objects.filter(status='completed').aggregate(total_amount=Sum('amount'))['total_amount'] or 0.00

    income_this_month = monthly_revenue

    total_approved_expenses = Expense.objects.filter(status='approved').aggregate(total_amount=Sum('amount'))['total_amount'] or 0.00

    expenses_this_month = monthly_expenses

    total_allocated_budget = Budget.objects.filter(year=current_year, month=current_month)\
                                        .aggregate(total_amount=Sum('allocated_amount'))['total_amount'] or 0.00
    total_spent_budget = Budget.objects.filter(year=current_year, month=current_month)\
                                    .aggregate(total_amount=Sum('spent_amount'))['total_amount'] or 0.00
    budget_utilization_percentage = (total_spent_budget / total_allocated_budget * 100) if total_allocated_budget > 0 else 0
    budget_summary = {
        'total_allocated': total_allocated_budget,
        'utilization_percentage': round(budget_utilization_percentage, 2)
    }

    payment_methods = Payment.objects.values('payment_method')\
                                .annotate(total_amount=Sum('amount'))\
                                .order_by('payment_method')

    expenses_by_category = Expense.objects.values('category__name')\
                                        .annotate(total_amount=Sum('amount'))\
                                        .order_by('category__name')

    monthly_registrations_labels = []
    monthly_registrations_data = []
    for i in range(5, -1, -1):
        month = (current_month - i - 1 + 12) % 12 + 1
        year = current_year if (current_month - i) > 0 else current_year - 1
        
        month_name = date(year, month, 1).strftime('%b')
        monthly_registrations_labels.append(f"{month_name} {year}")

        count = Patient.objects.filter(
            date_registered__year=year,
            date_registered__month=month
        ).count()
        monthly_registrations_data.append(count)

    context = {
        'staff_active_count': staff_active_count,
        'total_patients': total_patients,
        'patients_admitted': patients_admitted,
        'pending_lab_tests': pending_lab_tests,
        'pending_bills': pending_bills_amount,
        'monthly_revenue': monthly_revenue,
        'monthly_expenses': monthly_expenses,
        'total_doctors': total_doctors,
        'total_nurses': total_nurses,
        'new_patients_last_30_days': new_patients_last_30_days,
        'upcoming_appointments_today': upcoming_appointments_today,

        'recent_patients': recent_patients,
        'recent_appointments': recent_appointments,

        'monthly_registrations_labels_json': json.dumps(monthly_registrations_labels),
        'monthly_registrations_data_json': json.dumps(monthly_registrations_data),

        'total_income': total_income,
        'income_this_month': income_this_month,
        'total_approved_expenses': total_approved_expenses,
        'expenses_this_month': expenses_this_month,
        'budget_summary': budget_summary,
        'payment_methods': payment_methods,
        'expenses_by_category': expenses_by_category,

        'staff_by_role': staff_by_role,
        'staff_by_department': staff_by_department,
        'attendance_summary': attendance_summary,
        'staff_transitions_summary': staff_transitions_summary,

        'total_lab_tests': total_lab_tests,
        'lab_completion_rate': round(lab_completion_rate, 2),
        'total_prescriptions': total_prescriptions,
        'lab_tests_by_status': lab_tests_by_status,
        'top_lab_tests': top_lab_tests,

        'current_month': date(current_year, current_month, 1),
        'current_year': current_year,
    }

    return render(request, 'hms_admin/index.html', context)

@login_required(login_url='home')
def director_operations(request):
    # 1. Fetches data for 'Pending Discharges' table
    pending_discharges = Admission.objects.filter(status='Admitted')

    # 2. Fetches data for 'Expenses Approval' table
    pending_expenses = Expense.objects.filter(status='pending')

    # 3. Fetches data for 'Staff Transitions' table
    # Note: If StaffTransition needs approval, you'd add a status field to the model.
    # Currently, it fetches recent ones for display.
    pending_transitions = StaffTransition.objects.all().order_by('-created_at')[:10]

    # 4. Fetches data for 'Budget Overview' table
    current_year = timezone.now().year
    budgets = Budget.objects.filter(year=current_year).order_by('category__name', 'month')

    # 5. Fetches data for 'Emergency Alerts' table
    recent_alerts = EmergencyAlert.objects.all().order_by('-timestamp')[:10]

    context = {
        'pending_discharges': pending_discharges,
        'pending_expenses': pending_expenses,
        'pending_transitions': pending_transitions,
        'budgets': budgets,
        'recent_alerts': recent_alerts,
    }
    return render(request, 'hms_admin/operations.html', context)

# --- Existing Approval Views (as provided in previous response, kept for completeness) ---

@login_required(login_url='home')
def approve_discharge(request, d_id):
    try:
        admission_to_discharge = Admission.objects.get(id=d_id)
        admission_to_discharge.status = 'Discharged'
        admission_to_discharge.discharge_date = timezone.now().date()
        admission_to_discharge.discharged_by = request.user.get_full_name() or request.user.username
        admission_to_discharge.save()
        messages.success(request, f"Discharge for {admission_to_discharge.patient.full_name} approved successfully.")
    except Admission.DoesNotExist:
        messages.error(request, "Discharge request not found.")
    return redirect('director_operations')

@login_required(login_url='home')
def approve_expense(request, exp_id):
    try:
        expense_to_approve = Expense.objects.get(id=exp_id)
        expense_to_approve.status = 'approved'
        expense_to_approve.approved_by = request.user # Set the approving user
        expense_to_approve.save()
        messages.success(request, f"Expense '{expense_to_approve.description}' approved successfully.")
    except Expense.DoesNotExist:
        messages.error(request, "Expense request not found.")
    return redirect('director_operations')

# --- New Views for Proposed Functionalities ---

@login_required(login_url='home')
def acknowledge_alert(request, alert_id):
    try:
        alert = EmergencyAlert.objects.get(id=alert_id)
        alert.acknowledged_by.add(request.user) # Add current user to acknowledged_by
        alert.save()
        messages.success(request, "Emergency alert acknowledged.")
    except EmergencyAlert.DoesNotExist:
        messages.error(request, "Emergency alert not found.")
    return redirect('director_operations')

# Note: For Staff Transitions and Budget, direct 'approval' views
# would require adding 'status' fields to their respective models if not present,
# and defining specific approval logic. For now, the 'director_operations' view
# will just display them. If you want to add approval for staff transitions or budget,
# you would need to modify the models first to include a 'status' field like 'pending'.

@login_required(login_url='home')
def director_reports(request):

    # Get date ranges for filtering - using timezone.now() for consistency
    today_aware = timezone.now()
    today_date = today_aware.date() # For operations that need just a date

    current_month_start_aware = today_aware.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_month_start_aware = (current_month_start_aware - timedelta(days=1)).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    current_year = today_aware.year
    last_year = current_year - 1
    thirty_days_ago_aware = today_aware - timedelta(days=30)
    seven_days_ago_aware = today_aware - timedelta(days=7)

    # ==================== Overall Hospital Statistics ====================
    total_patients = Patient.objects.count()
    total_staff = Staff.objects.count()
    current_admitted_patients = Admission.objects.filter(status='Admitted').count()
    total_admissions = Admission.objects.count()
    total_discharges = Admission.objects.filter(status='Discharged').count()
    total_appointments = Appointment.objects.count()

    new_patients_target = 100
    admissions_target = 50
    lab_tests_target = 200
    prescriptions_target = 150

    # New patients this month
    new_patients_this_month = Patient.objects.filter(
        date_registered__gte=current_month_start_aware
    ).count()

    # Admissions this month
    admissions_this_month = Admission.objects.filter(
        admission_date__gte=current_month_start_aware
    ).count()

    # Average length of stay
    completed_admissions = Admission.objects.filter(
        status='Discharged',
        discharge_date__isnull=False
    )
    avg_length_of_stay = 0
    if completed_admissions.exists():
        # Ensure that admission.discharge_date and admission.admission_date are timezone-aware
        # and delta calculation is robust
        total_days = sum([
            (admission.discharge_date - admission.admission_date).days
            for admission in completed_admissions
        ])
        avg_length_of_stay = round(total_days / completed_admissions.count(), 1)

    # ==================== Patient Demographics & Analytics ====================
    patients_by_gender = Patient.objects.values('gender').annotate(count=Count('gender')).order_by('gender')
    patients_by_blood_group = Patient.objects.values('blood_group').annotate(count=Count('blood_group')).order_by('blood_group')
    patients_by_marital_status = Patient.objects.values('marital_status').annotate(count=Count('marital_status')).order_by('marital_status')

    # Age distribution
    patients_by_age_group = []
    age_groups = [
        ('0-18', 0, 18),
        ('19-30', 19, 30),
        ('31-50', 31, 50),
        ('51-70', 51, 70),
        ('70+', 71, 150)
    ]

    for group_name, min_age, max_age in age_groups:
        # Calculate birth dates relative to today_date (a date object)
        min_birth_date = today_date - timedelta(days=max_age*365)
        max_birth_date = today_date - timedelta(days=min_age*365)
        count = Patient.objects.filter(
            date_of_birth__gte=min_birth_date,
            date_of_birth__lte=max_birth_date
        ).count()
        patients_by_age_group.append({'age_group': group_name, 'count': count})

    # Patient status distribution
    patients_by_status = Patient.objects.values('status').annotate(count=Count('status')).order_by('status')

    # ==================== Financial Reports ====================
    # Income Analysis
    total_income = Payment.objects.filter(status='completed').aggregate(total=Sum('amount'))['total'] or 0
    income_this_month = Payment.objects.filter(
        status='completed',
        payment_date__gte=current_month_start_aware
    ).aggregate(total=Sum('amount'))['total'] or 0

    income_last_month = Payment.objects.filter(
        status='completed',
        payment_date__gte=last_month_start_aware,
        payment_date__lt=current_month_start_aware
    ).aggregate(total=Sum('amount'))['total'] or 0

    # Outstanding payments
    outstanding_bills = PatientBill.objects.filter(
        status__in=['pending', 'partial']
    ).aggregate(total=Sum('final_amount'))['total'] or 0

    # Expense Analysis
    total_expenses_incurred = Expense.objects.aggregate(total=Sum('amount'))['total'] or 0
    total_approved_expenses = Expense.objects.filter(status='approved').aggregate(total=Sum('amount'))['total'] or 0
    expenses_this_month = Expense.objects.filter(
        expense_date__gte=current_month_start_aware
    ).aggregate(total=Sum('amount'))['total'] or 0

    expenses_by_category = Expense.objects.filter(status='approved').values('category__name').annotate(
        total_amount=Sum('amount')
    ).order_by('-total_amount')

    # Payment methods analysis
    payment_methods = Payment.objects.filter(status='completed').values('payment_method').annotate(
        count=Count('payment_method'),
        total_amount=Sum('amount')
    ).order_by('-total_amount')

    # Budget Analysis
    budgets_data = Budget.objects.filter(year=current_year).order_by('category__name', 'month')

    # Calculate budget utilization
    budget_summary = {
        'total_allocated': budgets_data.aggregate(total=Sum('allocated_amount'))['total'] or 0,
        'total_spent': budgets_data.aggregate(total=Sum('spent_amount'))['total'] or 0,
    }
    if budget_summary['total_allocated'] > 0:
        budget_summary['utilization_percentage'] = round(
            (budget_summary['total_spent'] / budget_summary['total_allocated']) * 100, 2
        )
    else:
        budget_summary['utilization_percentage'] = 0

    # ==================== Staff Analytics ====================
    staff_by_role = Staff.objects.values('role').annotate(count=Count('role')).order_by('role')
    staff_by_department = Staff.objects.values('department__name').annotate(count=Count('department__name')).order_by('department__name')

    # Attendance Analysis
    attendance_summary = Attendance.objects.filter(date__gte=thirty_days_ago_aware).values('status').annotate(
        count=Count('status')
    ).order_by('status')

    # Weekly attendance trend
    weekly_attendance = []
    for i in range(4):
        week_start = today_aware - timedelta(days=(i+1)*7)
        week_end = today_aware - timedelta(days=i*7)
        week_data = Attendance.objects.filter(
            date__range=[week_start.date(), week_end.date()] # Use .date() if Attendance.date is a DateField
        ).values('status').annotate(count=Count('status'))
        weekly_attendance.append({
            'week': f"Week {4-i}",
            'data': list(week_data) # Convert queryset to list
        })

    staff_transitions_summary = StaffTransition.objects.values('transition_type').annotate(count=Count('transition_type')).order_by('transition_type')

    # Recent transitions (last 30 days)
    recent_transitions = StaffTransition.objects.filter(
        date__gte=thirty_days_ago_aware
    ).order_by('-date')[:10]

    # ==================== Clinical & Laboratory Analytics ====================
    total_lab_tests = LabTest.objects.count()
    lab_tests_by_status = LabTest.objects.values('status').annotate(count=Count('status')).order_by('status')
    lab_tests_by_category = LabTest.objects.values('category__name').annotate(count=Count('category__name')).order_by('category__name')

    # Lab test completion rate
    completed_tests = LabTest.objects.filter(status='completed').count()
    lab_completion_rate = round((completed_tests / total_lab_tests * 100), 2) if total_lab_tests > 0 else 0

    # Tests this month
    lab_tests_this_month = LabTest.objects.filter(
        requested_at__gte=current_month_start_aware
    ).count()

    # Average test completion time (for completed tests)
    avg_completion_time = "N/A"
    completed_tests_with_dates = LabTest.objects.filter(
        status='completed',
        date_performed__isnull=False
    )
    if completed_tests_with_dates.exists():
        total_hours = sum([
            (test.date_performed - test.requested_at).total_seconds() / 3600
            for test in completed_tests_with_dates
        ])
        avg_completion_time = f"{round(total_hours / completed_tests_with_dates.count(), 1)} hours"

    # Prescription Analysis
    total_prescriptions = Prescription.objects.count()
    prescriptions_this_month = Prescription.objects.filter(
        created_at__gte=current_month_start_aware
    ).count()

    # Most prescribed medications
    top_medications = Prescription.objects.values('medication').annotate(
        count=Count('medication')
    ).order_by('-count')[:10]

    # ==================== Emergency & Critical Care ====================
    critical_patients = Patient.objects.filter(status='critical').count()
    emergency_alerts = EmergencyAlert.objects.filter(
        timestamp__gte=seven_days_ago_aware
    ).count()

    # ==================== Occupancy & Capacity ====================
    bed_occupancy_rate = 0
    if current_admitted_patients > 0:
        estimated_capacity = 100  # This should come from your Hospital/Ward capacity model
        bed_occupancy_rate = round((current_admitted_patients / estimated_capacity) * 100, 2)

    # ==================== Monthly Trends ====================
    monthly_trends = []
    for i in range(6):  # Last 6 months
        # Calculate month start/end for filtering against DateTimeFields
        month_start_dt = (today_aware.replace(day=1) - timedelta(days=i*30)).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        # Calculate month_end for the last microsecond of the last day of the month
        month_end_dt = (month_start_dt.replace(day=1) + timedelta(days=32)).replace(day=1, hour=0, minute=0, second=0, microsecond=0) - timedelta(microseconds=1)

        monthly_data = {
            'month': month_start_dt.strftime('%B %Y'),
            'patients': Patient.objects.filter(date_registered__range=[month_start_dt, month_end_dt]).count(),
            'admissions': Admission.objects.filter(admission_date__range=[month_start_dt, month_end_dt]).count(),
            'income': Payment.objects.filter(
                status='completed',
                payment_date__range=[month_start_dt, month_end_dt]
            ).aggregate(total=Sum('amount'))['total'] or 0,
            'lab_tests': LabTest.objects.filter(requested_at__range=[month_start_dt, month_end_dt]).count(),
        }
        monthly_trends.append(monthly_data)

    monthly_trends.reverse()  # Show oldest to newest

    # ==================== Quality Metrics ====================
    # Readmission rates: Replaced problematic query with a robust two-step approach
    # Step 1: Get distinct patient IDs who had a discharge in the last 30 days
    recent_discharge_patient_ids = Admission.objects.filter(
        discharge_date__gte=thirty_days_ago_aware, # Use the aware datetime
        status='Discharged'
    ).values_list('patient_id', flat=True).distinct()

    # Step 2: Count *all* admissions for these recently discharged patients
    # (This reflects the apparent intent of your original problematic query's outer filter)
    readmissions = Admission.objects.filter(
        patient_id__in=recent_discharge_patient_ids
    ).count()

    readmission_rate = 0
    if total_discharges > 0:
        readmission_rate = round((readmissions / total_discharges) * 100, 2)


    context = {
        # Basic Statistics
        'total_patients': total_patients,
        'total_staff': total_staff,
        'current_admitted_patients': current_admitted_patients,
        'total_admissions': total_admissions,
        'total_discharges': total_discharges,
        'total_appointments': total_appointments,
        'new_patients_this_month': new_patients_this_month,
        'admissions_this_month': admissions_this_month,
        'avg_length_of_stay': avg_length_of_stay,

        # Patient Analytics
        'patients_by_gender': patients_by_gender,
        'patients_by_blood_group': patients_by_blood_group,
        'patients_by_marital_status': patients_by_marital_status,
        'patients_by_age_group': patients_by_age_group,
        'patients_by_status': patients_by_status,

        # Financial Data
        'total_income': total_income,
        'income_this_month': income_this_month,
        'income_last_month': income_last_month,
        'outstanding_bills': outstanding_bills,
        'total_expenses_incurred': total_expenses_incurred,
        'total_approved_expenses': total_approved_expenses,
        'expenses_this_month': expenses_this_month,
        'expenses_by_category': expenses_by_category,
        'payment_methods': payment_methods,
        'budgets_data': budgets_data,
        'budget_summary': budget_summary,

        # Staff Data
        'staff_by_role': staff_by_role,
        'staff_by_department': staff_by_department,
        'attendance_summary': attendance_summary,
        'weekly_attendance': weekly_attendance,
        'staff_transitions_summary': staff_transitions_summary,
        'recent_transitions': recent_transitions,

        # Clinical Data
        'total_lab_tests': total_lab_tests,
        'lab_tests_by_status': lab_tests_by_status,
        'lab_tests_by_category': lab_tests_by_category,
        'lab_completion_rate': lab_completion_rate,
        'lab_tests_this_month': lab_tests_this_month,
        'avg_completion_time': avg_completion_time,
        'total_prescriptions': total_prescriptions,
        'prescriptions_this_month': prescriptions_this_month,
        'top_medications': top_medications,

        # Emergency & Critical
        'critical_patients': critical_patients,
        'emergency_alerts': emergency_alerts,

        # Capacity & Trends
        'bed_occupancy_rate': bed_occupancy_rate,
        'monthly_trends': monthly_trends,
        'readmission_rate': readmission_rate,

        # Report Metadata
        'report_generated_date': timezone.now(),
        'report_period': f"{current_month_start_aware.strftime('%B %Y')} - Current",
        'current_year': current_year,

        'new_patients_target': new_patients_target,
        'admissions_target': admissions_target,
        'lab_tests_target': lab_tests_target,
        'prescriptions_target': prescriptions_target,
    }

    return render(request, 'hms_admin/reports.html', context)

@login_required(login_url='home')
def user_accounts(request):
    """
    Displays and manages user accounts, excluding superusers.
    Handles search filtering and provides statistics.
    """
    # Get search query if provided
    search_query = request.GET.get('search', '').strip()

    # Filter users (exclude superusers and get related staff info)
    users_qs = User.objects.filter(is_superuser=False).select_related('staff')

    # Apply search filter if query exists
    if search_query:
        users_qs = users_qs.filter(
            Q(username__icontains=search_query) |
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(staff__role__icontains=search_query)
        )

    # Get statistics for dashboard cards
    total_users = users_qs.count()
    active_users = users_qs.filter(is_active=True).count()
    inactive_users = total_users - active_users

    # Count users by role
    role_counts = {}
    for choice_key, choice_name in Staff.ROLE_CHOICES:
        count = users_qs.filter(staff__role=choice_key).count()
        role_counts[choice_name] = count

    context = {
        'users': users_qs,
        'search_query': search_query,
        'total_users': total_users,
        'active_users': active_users,
        'inactive_users': inactive_users,
        'role_counts': role_counts,
        'Staff': Staff,
    }

    return render(request, 'hms_admin/user_accounts.html', context)


@login_required(login_url='home')
@require_POST
@csrf_exempt
def toggle_user_status(request, user_id):
    """
    Toggles a user's active status. Accessible via AJAX.
    Takes user_id as URL parameter.
    """
    try:
        # Ensure only non-superusers can be toggled
        user_to_toggle = get_object_or_404(User, id=user_id, is_superuser=False)
        user_to_toggle.is_active = not user_to_toggle.is_active
        user_to_toggle.save()

        status_msg = "activated" if user_to_toggle.is_active else "deactivated"
        messages.success(request, f'User {user_to_toggle.username} has been {status_msg} successfully.')
        return JsonResponse({
            'success': True, 
            'message': f'User {user_to_toggle.username} status toggled successfully.',
            'new_status': user_to_toggle.is_active
        })

    except User.DoesNotExist:
        messages.error(request, "User not found or cannot be toggled.")
        return JsonResponse({'success': False, 'message': 'User not found.'}, status=404)
    except Exception as e:
        logger.error(f"Error toggling user status for {user_id}: {e}")
        messages.error(request, f"An error occurred: {e}")
        return JsonResponse({'success': False, 'message': f'An error occurred: {e}'}, status=500)


def is_hms_software_admin(user):
    """
    Test function for the user_passes_test decorator.
    The user must be staff (to access admin) AND have the custom permission
    Or be a superuser (who bypasses all custom permissions)
    """
    return user.is_superuser or (user.is_staff and user.has_perm('hms.can_edit_staff_profiles'))


@login_required(login_url='home')
@require_POST
@csrf_exempt
@user_passes_test(is_hms_software_admin, login_url='home')
def edit_user_endpoint(request, user_id):
    """
    Handles updating user details via AJAX from the edit user modal.
    Takes user_id as URL parameter.
    """
    username = request.POST.get('username')
    email = request.POST.get('email')
    first_name = request.POST.get('first_name')
    last_name = request.POST.get('last_name')
    role_key = request.POST.get('role')
    phone_number = request.POST.get('phone_number')
    is_active = request.POST.get('is_active') == 'true'

    try:
        user_to_edit = get_object_or_404(User, id=user_id)
        staff_profile_to_edit = get_object_or_404(Staff, user=user_to_edit)

        # --- Granular Permission Checks ---
        
        # 1. Prevent non-superusers from editing superusers
        if user_to_edit.is_superuser and not request.user.is_superuser:
            return JsonResponse({
                'success': False, 
                'message': 'Permission denied: Cannot edit superuser account without superuser privileges.'
            }, status=403)

        # 2. Prevent a superuser from deactivating their own account
        if user_to_edit == request.user and not is_active and request.user.is_superuser:
            return JsonResponse({
                'success': False, 
                'message': 'Superusers cannot deactivate their own account.'
            }, status=400)

        # Basic validation
        if not username or not email or not role_key:
            return JsonResponse({
                'success': False, 
                'message': 'Missing required fields: username, email, and role.'
            }, status=400)
        
        # Check for duplicate username or email if they are changed
        if user_to_edit.username != username and User.objects.filter(username=username).exists():
            return JsonResponse({'success': False, 'message': 'Username already exists.'}, status=400)
        
        if user_to_edit.email != email and User.objects.filter(email=email).exists():
            return JsonResponse({'success': False, 'message': 'Email already exists.'}, status=400)

        # Update User model fields
        user_to_edit.username = username
        user_to_edit.email = email
        user_to_edit.first_name = first_name
        user_to_edit.last_name = last_name
        user_to_edit.is_active = is_active
        user_to_edit.save()

        # Update Staff profile fields
        staff_profile_to_edit.role = role_key
        staff_profile_to_edit.phone_number = phone_number
        staff_profile_to_edit.save()

        return JsonResponse({'success': True, 'message': f'User {user_to_edit.username} updated successfully.'})

    except (User.DoesNotExist, Staff.DoesNotExist):
        return JsonResponse({'success': False, 'message': 'User or staff profile not found.'}, status=404)
    except Exception as e:
        logger.error(f"Error editing user {user_id}: {e}")
        return JsonResponse({'success': False, 'message': f'An error occurred: {str(e)}'}, status=500)


@login_required(login_url='home')
@require_POST
@csrf_exempt
@user_passes_test(is_hms_software_admin, login_url='home')
def add_user_endpoint(request):
    """
    Handles adding a new user and staff profile via AJAX.
    """
    username = request.POST.get('username')
    email = request.POST.get('email')
    password = request.POST.get('password')
    first_name = request.POST.get('first_name')
    last_name = request.POST.get('last_name')
    role_key = request.POST.get('role')
    phone_number = request.POST.get('phone_number')
    is_active = request.POST.get('is_active') == 'true'

    if not all([username, password, role_key]):
        return JsonResponse({
            'success': False, 
            'message': 'Username, password, and role are required.'
        }, status=400)

    try:
        if User.objects.filter(username=username).exists():
            return JsonResponse({'success': False, 'message': 'Username already exists.'}, status=409)

        if email and User.objects.filter(email=email).exists():
            return JsonResponse({'success': False, 'message': 'Email already exists.'}, status=409)

        user = User.objects.create_user(
            username=username,
            password=password,
            email=email,
            first_name=first_name,
            last_name=last_name,
            is_active=is_active
        )

        Staff.objects.create(
            user=user,
            role=role_key,
            phone_number=phone_number
        )

        messages.success(request, f"New user {user.username} added successfully.")
        return JsonResponse({'success': True, 'message': 'User added successfully.'})

    except Exception as e:
        logger.error(f"Error adding new user: {e}")
        messages.error(request, f"An error occurred: {e}")
        return JsonResponse({'success': False, 'message': f'An error occurred: {e}'}, status=500)


@login_required(login_url='home')
@require_POST
@csrf_exempt
@user_passes_test(is_hms_software_admin, login_url='home')
def set_user_password_endpoint(request, user_id):
    """
    Sets a new password for a user (for when they forget their password).
    Takes user_id as URL parameter.
    Returns the new password to the admin.
    """
    try:
        # Prevent non-superusers from resetting superuser passwords for security
        user_to_update = get_object_or_404(User, id=user_id)
        if user_to_update.is_superuser and not request.user.is_superuser:
            return JsonResponse({
                'success': False,
                'message': 'Permission denied: Cannot reset password for superuser account without superuser privileges.'
            }, status=403)

        # Set the password to "12345678" as requested
        new_password = "12345" # !!! WARNING: This is a highly insecure password !!!

        user_to_update.set_password(new_password)
        user_to_update.save()

        messages.success(request, f"New password set for {user_to_update.username}.")
        return JsonResponse({
            'success': True,
            'message': f'New password set for {user_to_update.username} successfully.',
            'new_password': new_password, # Be cautious about returning plaintext passwords in production
            'username': user_to_update.username
        })
    except User.DoesNotExist:
        messages.error(request, "User not found.")
        return JsonResponse({'success': False, 'message': 'User not found.'}, status=404)
    except Exception as e:
        logger.error(f"Error setting password for user {user_id}: {e}")
        messages.error(request, f"An error occurred: {e}")
        return JsonResponse({'success': False, 'message': f'An error occurred: {e}'}, status=500)


@login_required(login_url='home')
@require_POST
@csrf_exempt
@user_passes_test(is_hms_software_admin, login_url='home')
def delete_user_endpoint(request, user_id):
    """
    Deletes a user and their associated staff profile.
    Takes user_id as URL parameter.
    """
    try:
        # Ensure only non-superusers can be deleted
        user_to_delete = get_object_or_404(User, id=user_id, is_superuser=False)
        
        # Prevent admin from deleting their own account
        if user_to_delete == request.user:
            return JsonResponse({
                'success': False, 
                'message': 'You cannot delete your own account.'
            }, status=400)
        
        username = user_to_delete.username  # Store username before deleting
        user_to_delete.delete()

        messages.success(request, f"User {username} and associated staff profile deleted successfully.")
        return JsonResponse({'success': True, 'message': f'User {username} deleted successfully.'})

    except User.DoesNotExist:
        messages.error(request, "User not found or cannot delete superuser.")
        return JsonResponse({'success': False, 'message': 'User not found.'}, status=404)
    except Exception as e:
        logger.error(f"Error deleting user {user_id}: {e}")
        messages.error(request, f"An error occurred: {e}")
        return JsonResponse({'success': False, 'message': f'An error occurred: {e}'}, status=500)
    
@login_required(login_url='home')
@require_GET
def export_users_csv_view(request):
    """
    Exports filtered user account data to a CSV file.
    Filters based on search query, role, and status from GET parameters.
    """
    search_query = request.GET.get('search', '').strip()
    role_filter = request.GET.get('role', '').strip() # This will be the display name (e.g., 'Doctor')
    status_filter = request.GET.get('status', '').strip() # 'Active' or 'Inactive'

    # Start with all non-superuser users and prefetch staff for efficiency
    users_to_export = User.objects.filter(is_superuser=False).select_related('staff')

    # Apply search filter
    if search_query:
        users_to_export = users_to_export.filter(
            Q(username__icontains=search_query) |
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(staff__role__icontains=search_query) # Search by role key for Staff model
        )

    # Apply role filter (by display name, then map to role key)
    if role_filter:
        # Find the role key corresponding to the display name
        role_key = None
        for key, display_name in Staff.ROLE_CHOICES:
            if display_name == role_filter:
                role_key = key
                break
        if role_key:
            users_to_export = users_to_export.filter(staff__role=role_key)
        else:
            # If an invalid role display name is provided, return empty or handle error
            return HttpResponse("Invalid role filter.", status=400)


    # Apply status filter
    if status_filter:
        if status_filter.lower() == 'active':
            users_to_export = users_to_export.filter(is_active=True)
        elif status_filter.lower() == 'inactive':
            users_to_export = users_to_export.filter(is_active=False)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="user_accounts_export.csv"'

    writer = csv.writer(response)
    # Define CSV header
    writer.writerow([
        'Username', 'Full Name', 'Email', 'Role', 'Department',
        'Phone Number', 'Status', 'Date Joined'
    ])

    # Write data rows
    for user in users_to_export:
        staff_profile = getattr(user, 'staff', None) # Safely get staff profile

        full_name = user.get_full_name() or "Not provided"
        role_display = staff_profile.get_role_display() if staff_profile else "N/A"
        department_name = staff_profile.department.name if staff_profile and staff_profile.department else "N/A"
        phone_number = staff_profile.phone_number if staff_profile else "N/A"
        status = "Active" if user.is_active else "Inactive"
        date_joined = user.date_joined.strftime('%Y-%m-%d') if user.date_joined else "N/A"

        writer.writerow([
            user.username,
            full_name,
            user.email,
            role_display,
            department_name,
            phone_number,
            status,
            date_joined,
        ])
    return response


@login_required(login_url='home')
@require_GET
def export_users_pdf_view(request):
    """
    Exports filtered user account data to a PDF file.
    Filters based on search query, role, and status from GET parameters.
    """
    search_query = request.GET.get('search', '').strip()
    role_filter = request.GET.get('role', '').strip()
    status_filter = request.GET.get('status', '').strip()

    users_to_export = User.objects.filter(is_superuser=False).select_related('staff')

    # Apply search filter
    if search_query:
        users_to_export = users_to_export.filter(
            Q(username__icontains=search_query) |
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(staff__role__icontains=search_query)
        )

    # Apply role filter
    if role_filter:
        role_key = None
        for key, display_name in Staff.ROLE_CHOICES:
            if display_name == role_filter:
                role_key = key
                break
        if role_key:
            users_to_export = users_to_export.filter(staff__role=role_key)
        else:
            return HttpResponse("Invalid role filter.", status=400)

    # Apply status filter
    if status_filter:
        if status_filter.lower() == 'active':
            users_to_export = users_to_export.filter(is_active=True)
        elif status_filter.lower() == 'inactive':
            users_to_export = users_to_export.filter(is_active=False)

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()

    elements = []

    # Title
    elements.append(Paragraph("User Accounts Report", styles['h1']))
    elements.append(Paragraph(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles['Normal']))
    elements.append(Paragraph(f"Filters applied: Search='{search_query}', Role='{role_filter}', Status='{status_filter}'", styles['Normal']))
    elements.append(Paragraph("<br/>", styles['Normal'])) # Spacer

    # Table Data
    data = [
        ['Username', 'Full Name', 'Email', 'Role', 'Department', 'Phone', 'Status', 'Date Joined']
    ]
    for user in users_to_export:
        staff_profile = getattr(user, 'staff', None)

        full_name = user.get_full_name() or "Not provided"
        role_display = staff_profile.get_role_display() if staff_profile else "N/A"
        department_name = staff_profile.department.name if staff_profile and staff_profile.department else "N/A"
        phone_number = staff_profile.phone_number if staff_profile else "N/A"
        status = "Active" if user.is_active else "Inactive"
        date_joined = user.date_joined.strftime('%Y-%m-%d') if user.date_joined else "N/A"

        data.append([
            user.username,
            full_name,
            user.email,
            role_display,
            department_name,
            phone_number,
            status,
            date_joined,
        ])

    table_style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('BOX', (0, 0), (-1, -1), 1, colors.black),
    ])

    # Calculate column widths dynamically or set fixed ones
    # A4 width is 8.27 inches = 595.3 points. Margins often total ~72 points per side.
    # Usable width ~ 450-500 points.
    col_widths = [70, 90, 100, 60, 80, 70, 50, 70] # Adjusted widths
    
    user_table = Table(data, colWidths=col_widths)
    user_table.setStyle(table_style)
    elements.append(user_table)

    doc.build(elements)
    buffer.seek(0)
    return HttpResponse(buffer, content_type='application/pdf')

@login_required(login_url='home')
def doctor_reports(request):
    """
    Renders the Doctor's Reports Dashboard with comprehensive patient activity data,
    graphical representations, and export options.
    """
    # Ensure only 'doctor' or 'admin' role can access this dashboard
    if not hasattr(request.user, 'staff') or request.user.staff.role not in ['doctor', 'admin']:
        messages.error(request, "Access denied. You do not have permission to view this page.")
        return redirect('home')

    all_patients = Patient.objects.all().order_by('full_name')

    # Get filter parameters from GET request
    selected_patient_id = request.GET.get('patient_id')
    date_from_param = request.GET.get('date_from')
    date_to_param = request.GET.get('date_to')
    export_type = request.GET.get('export_type') # 'csv', 'pdf'

    current_patient = None
    if selected_patient_id:
        try:
            current_patient = get_object_or_404(Patient, id=selected_patient_id)
        except Exception as e:
            messages.error(request, f"Selected patient not found: {e}")
            current_patient = None
            selected_patient_id = None # Reset if patient not found

    # If no patient is selected, no detailed data is fetched beyond initial overview
    if not current_patient:
        context = {
            'all_patients': all_patients,
            'selected_patient': None,
            'date_from': date_from_param,
            'date_to': date_to_param,
            # Initialize empty lists for charts/tables if no patient selected
            'consultations': [], 'prescriptions': [], 'vitals': [], 'lab_test_groups': [],
            'nursing_notes': [], 'admissions': [], 'care_plans': [], 'referrals': [],
            'appointments': [], 'bills': [], 'payments': [], 'handover_logs': [],
            'summary': {}, # Empty summary
            # Chart data will also be empty if no patient
            'consultation_labels_json': json.dumps([]), 'consultation_data_json': json.dumps([]),
            'prescription_labels_json': json.dumps([]), 'prescription_data_json': json.dumps([]),
            'vital_bp_labels_json': json.dumps([]), 'vital_sys_data_json': json.dumps([]), 'vital_dia_data_json': json.dumps([]),
            'lab_status_labels_json': json.dumps([]), 'lab_status_data_json': json.dumps([]),
            'top_meds_labels_json': json.dumps([]), 'top_meds_data_json': json.dumps([]),
        }
        return render(request, 'hms_admin/doctor_reports.html', context)


    # --- Fetch Data for Selected Patient and Date Range ---
    
    # 1. BASIC PATIENT INFO
    # Calculate age properly
    today = date.today()
    age = today.year - current_patient.date_of_birth.year - ((today.month, today.day) < (current_patient.date_of_birth.month, current_patient.date_of_birth.day))

    # Handle patient photo
    photo_url = ''
    if current_patient.photo and hasattr(current_patient.photo, 'url'):
        try:
            if default_storage.exists(current_patient.photo.name):
                photo_url = current_patient.photo.url
        except Exception as e:
            logger.warning(f"Error accessing patient photo for patient {current_patient.id}: {e}")
            pass

    patient_data_for_display = {
        'id': current_patient.id,
        'full_name': current_patient.full_name,
        'gender': current_patient.gender,
        'date_of_birth': current_patient.date_of_birth.strftime('%Y-%m-%d'),
        'age': age,
        'blood_group': current_patient.blood_group,
        'phone': current_patient.phone,
        'email': current_patient.email or 'N/A',
        'address': current_patient.address,
        'marital_status': current_patient.marital_status,
        'nationality': current_patient.nationality,
        'state_of_origin': current_patient.state_of_origin or 'N/A',
        'id_type': current_patient.id_type or 'N/A',
        'id_number': current_patient.id_number or 'N/A',
        'status': current_patient.get_status_display(), # Use get_status_display
        'is_inpatient': current_patient.is_inpatient,
        'date_registered': current_patient.date_registered.strftime('%Y-%m-%d %H:%M'),
        'photo_url': photo_url,
        'next_of_kin_name': current_patient.next_of_kin_name,
        'next_of_kin_phone': current_patient.next_of_kin_phone,
        'next_of_kin_relationship': current_patient.next_of_kin_relationship or 'N/A',
        'next_of_kin_email': current_patient.next_of_kin_email or 'N/A',
        'next_of_kin_address': current_patient.next_of_kin_address or 'N/A',
        'diagnosis': current_patient.diagnosis or 'N/A',
        'medication': current_patient.medication or 'N/A',
        'notes': current_patient.notes or 'N/A',
        'referred_by': current_patient.referred_by or 'N/A',
    }

    # Apply date filters to all relevant querysets
    # Consultations
    consultations_qs = apply_date_filter(
        current_patient.consultations.select_related('doctor', 'admission').order_by('-created_at'),
        date_from_param, date_to_param, 'created_at'
    )
    consultations = []
    for c in consultations_qs:
        consultations.append({
            'date': c.created_at.strftime('%Y-%m-%d %H:%M'),
            'doctor': c.doctor.get_full_name() if c.doctor else 'Unknown',
            'symptoms': c.symptoms,
            'diagnosis_summary': c.diagnosis_summary,
            'advice': c.advice,
        })

    # Prescriptions
    prescriptions_qs = apply_date_filter(
        current_patient.prescriptions.select_related('prescribed_by').order_by('-created_at'),
        date_from_param, date_to_param, 'created_at'
    )
    prescriptions = []
    for p in prescriptions_qs:
        prescriptions.append({
            'date': p.created_at.strftime('%Y-%m-%d %H:%M'),
            'medication': p.medication,
            'instructions': p.instructions,
            'start_date': p.start_date.strftime('%Y-%m-%d'),
            'prescribed_by': p.prescribed_by.get_full_name() if p.prescribed_by else 'Unknown',
        })
    
    # Vitals
    vitals_qs = apply_date_filter(
        Vitals.objects.filter(patient=current_patient).order_by('recorded_at'), # Order by oldest to newest for trend charts
        date_from_param, date_to_param, 'recorded_at'
    )
    vitals = []
    for v in vitals_qs:
        vitals.append({
            'recorded_at': v.recorded_at.strftime('%Y-%m-%d %H:%M'),
            'temperature': v.temperature,
            'blood_pressure': v.blood_pressure,
            'pulse': v.pulse,
            'respiratory_rate': v.respiratory_rate,
            'weight': v.weight,
            'height': v.height,
            'bmi': v.bmi,
            'recorded_by': v.recorded_by,
            'notes': v.notes or ''
        })

    # Lab Tests & Results (Grouped by test_request_id UUID)
    lab_tests_qs = apply_date_filter(
        current_patient.lab_tests.select_related('category', 'performed_by', 'requested_by', 'recorded_by').order_by('-requested_at'),
        date_from_param, date_to_param, 'requested_at'
    )

    grouped_lab_tests = defaultdict(list)
    for test in lab_tests_qs:
        grouped_lab_tests[test.test_request_id].append(test)

    lab_test_groups = []
    for request_id, tests_in_group in grouped_lab_tests.items():
        first_test = tests_in_group[0]

        doctor_comment_data = None
        if first_test.doctor_comments:
            try:
                comment = DoctorComments.objects.get(id=first_test.doctor_comments)
                doctor_comment_data = {
                    "id": comment.id,
                    "comment": comment.comments,
                    "doctor_name": comment.doctor_name,
                    "date": comment.date.strftime('%Y-%m-%d %H:%M')
                }
            except DoctorComments.DoesNotExist:
                pass

        lab_file_data = None
        if first_test.labresulttestid:
            try:
                lab_file = LabResultFile.objects.select_related('uploaded_by').get(id=first_test.labresulttestid)
                file_url = ''
                file_name = ''
                if lab_file.result_file and hasattr(lab_file.result_file, 'url'):
                    try:
                        if default_storage.exists(lab_file.result_file.name):
                            file_url = lab_file.result_file.url
                            file_name = lab_file.result_file.name.split('/')[-1]
                    except Exception as e:
                        logger.warning(f"Error accessing lab result file {lab_file.id}: {e}")
                        pass
                
                lab_file_data = {
                    "id": lab_file.id,
                    "file_url": file_url,
                    "file_name": file_name,
                    "uploaded_at": lab_file.uploaded_at.strftime('%Y-%m-%d %H:%M'),
                    "uploaded_by": lab_file.uploaded_by.get_full_name() if lab_file.uploaded_by else 'Unknown'
                }
            except LabResultFile.DoesNotExist:
                pass

        tests_data = []
        for test in tests_in_group:
            tests_data.append({
                'id': test.id,
                'test_name': test.test_name,
                'category': test.category.name if test.category else 'N/A',
                'status': test.get_status_display(),
                'status_code': test.status,
                'result_value': test.result_value or 'N/A',
                'normal_range': test.normal_range or 'N/A',
                'notes': test.notes or 'N/A',
                'instructions': test.instructions or 'N/A',
                'doctor_name': test.doctor_name or 'N/A',
                'performed_by': test.performed_by.get_full_name() if test.performed_by else 'N/A',
                'requested_by': test.requested_by.get_full_name() if test.requested_by else 'N/A',
                'recorded_by': test.recorded_by.get_full_name() if test.recorded_by else 'N/A',
                'date_performed': test.date_performed.strftime('%Y-%m-%d %H:%M') if test.date_performed else 'N/A',
                'submitted_on': test.submitted_on.strftime('%Y-%m-%d'),
                'testcompleted': test.testcompleted,
            })
        tests_data.sort(key=lambda x: x['test_name']) # Sort individual tests within a group

        group_statuses = [test.status for test in tests_in_group]
        if all(s == 'completed' for s in group_statuses):
            group_status = 'completed'
        elif any(s == 'in_progress' for s in group_statuses):
            group_status = 'in_progress'
        elif any(s == 'cancelled' for s in group_statuses):
            group_status = 'cancelled'
        else:
            group_status = 'pending'

        lab_test_groups.append({
            "request_id": str(request_id),
            "requested_at": first_test.requested_at.strftime('%Y-%m-%d %H:%M'),
            "submitted_on": first_test.submitted_on.strftime('%Y-%m-%d'),
            "doctor_name": first_test.doctor_name or 'N/A',
            "requested_by": first_test.requested_by.get_full_name() if first_test.requested_by else 'N/A',
            "group_status": group_status,
            "tests_count": len(tests_in_group),
            "completed_tests_count": len([t for t in tests_in_group if t.status == 'completed']),
            "pending_tests_count": len([t for t in tests_in_group if t.status == 'pending']),
            "doctor_comment": doctor_comment_data,
            "result_file": lab_file_data,
            "tests": tests_data
        })
    lab_test_groups.sort(key=lambda x: x['requested_at'], reverse=True) # Sort groups by requested time

    # Nursing Notes
    nursing_notes_qs = apply_date_filter(
        current_patient.nursing_notes.order_by('-note_datetime'),
        date_from_param, date_to_param, 'note_datetime'
    )
    nursing_notes = []
    for n in nursing_notes_qs:
        nursing_notes.append({
            'date': n.note_datetime.strftime('%Y-%m-%d %H:%M'),
            'nurse': n.nurse,
            'note_type': n.get_note_type_display(),
            'notes': n.notes,
            'patient_status': n.patient_status or 'N/A',
            'follow_up': n.follow_up or 'N/A',
        })

    # Admissions
    admissions_qs = apply_date_filter(
        Admission.objects.filter(patient=current_patient).order_by('-admission_date'),
        date_from_param, date_to_param, 'admission_date', is_datetime_field=False
    )
    admissions = []
    for a in admissions_qs:
        admissions.append({
            'admission_date': a.admission_date.strftime('%Y-%m-%d'),
            'doctor_assigned': a.doctor_assigned,
            'status': a.get_status_display(),
            'discharge_date': a.discharge_date.strftime('%Y-%m-%d') if a.discharge_date else 'N/A',
            'discharge_notes': a.discharge_notes or 'N/A',
            'admitted_by': a.admitted_by or 'N/A',
        })

    # Care Plans
    care_plans_qs = apply_date_filter(
        CarePlan.objects.filter(patient=current_patient).select_related('created_by').order_by('-created_at'),
        date_from_param, date_to_param, 'created_at'
    )
    care_plans = []
    for cp in care_plans_qs:
        care_plans.append({
            'created_at': cp.created_at.strftime('%Y-%m-%d %H:%M'),
            'created_by': cp.created_by.get_full_name() if cp.created_by else 'Unknown',
            'clinical_findings': cp.clinical_findings,
            'plan_of_care': cp.plan_of_care,
        })

    # Referrals
    referrals_qs = Referral.objects.filter(patient=current_patient).select_related('department').order_by('-id') # Assuming 'id' can order them, or add a created_at field
    referrals = []
    for r in referrals_qs:
        referrals.append({
            'department': r.department.name,
            'notes': r.notes,
        })

    # Appointments
    appointments_qs = apply_date_filter(
        Appointment.objects.filter(patient=current_patient).select_related('department').order_by('-scheduled_time'),
        date_from_param, date_to_param, 'scheduled_time'
    )
    appointments = []
    for appt in appointments_qs:
        appointments.append({
            'scheduled_time': appt.scheduled_time.strftime('%Y-%m-%d %H:%M'),
            'department': appt.department.name,
        })

    # Bills
    bills_qs = apply_date_filter(
        current_patient.bills.prefetch_related('items__service_type').order_by('-created_at'),
        date_from_param, date_to_param, 'created_at'
    )
    bills = []
    for b in bills_qs:
        bill_items = []
        for item in b.items.all():
            bill_items.append({
                'description': item.description,
                'service_type': item.service_type.name,
                'quantity': item.quantity,
                'unit_price': float(item.unit_price),
                'total_price': float(item.total_price),
            })
        bills.append({
            'bill_number': b.bill_number,
            'created_at': b.created_at.strftime('%Y-%m-%d %H:%M'),
            'total_amount': float(b.total_amount),
            'discount_amount': float(b.discount_amount),
            'final_amount': float(b.final_amount),
            'amount_paid': float(b.amount_paid()),
            'outstanding_amount': float(b.outstanding_amount()),
            'status': b.get_status_display(),
            'notes': b.notes or 'N/A',
            'items': bill_items,
        })

    # Payments
    payments_qs = apply_date_filter(
        current_patient.payments.select_related('processed_by', 'bill').order_by('-payment_date'),
        date_from_param, date_to_param, 'payment_date'
    )
    payments = []
    for pay in payments_qs:
        payments.append({
            'amount': float(pay.amount),
            'payment_date': pay.payment_date.strftime('%Y-%m-%d %H:%M'),
            'payment_method': pay.get_payment_method_display(),
            'payment_reference': pay.payment_reference or 'N/A',
            'status': pay.get_status_display(),
            'processed_by': pay.processed_by.get_full_name() if pay.processed_by else 'Unknown',
            'bill_number': pay.bill.bill_number if pay.bill else 'N/A',
        })
    
    # Handover Logs
    handover_logs_qs = apply_date_filter(
        HandoverLog.objects.filter(patient=current_patient).select_related('author').order_by('-timestamp'),
        date_from_param, date_to_param, 'timestamp'
    )
    handover_logs = []
    for hl in handover_logs_qs:
        handover_logs.append({
            'timestamp': hl.timestamp.strftime('%Y-%m-%d %H:%M'),
            'author': hl.author.get_full_name() if hl.author else 'Unknown',
            'notes': hl.notes,
        })


    # --- Prepare Data for Charts ---
    
    # Consultation Frequency (Last 12 months)
    consultation_labels = []
    consultation_data = []
    for i in range(11, -1, -1): # From 11 months ago to current month
        month_start = (timezone.now() - timedelta(days=30*i)).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        month_end = (month_start + timedelta(days=32)).replace(day=1, hour=0, minute=0, second=0, microsecond=0) - timedelta(microseconds=1)
        
        count = Consultation.objects.filter(
            patient=current_patient,
            created_at__range=[month_start, month_end]
        ).count()
        consultation_labels.append(month_start.strftime('%b %Y'))
        consultation_data.append(count)

    # Top 5 Prescribed Medications (overall for this patient)
    top_medications = Prescription.objects.filter(patient=current_patient)\
                                        .values('medication')\
                                        .annotate(count=Count('medication'))\
                                        .order_by('-count')[:5]
    top_meds_labels = [m['medication'] for m in top_medications]
    top_meds_data = [m['count'] for m in top_medications]

    # Lab Test Status Distribution (for current patient within filtered range)
    lab_status_counts = LabTest.objects.filter(patient=current_patient)\
                                    .values('status')\
                                    .annotate(count=Count('status'))\
                                    .order_by('status')
    lab_status_labels = [s['status'] for s in lab_status_counts]
    lab_status_data = [s['count'] for s in lab_status_counts]

    # Vitals Trends (Blood Pressure, Temperature over time) - limited to last N records for clarity
    vitals_bp_labels = [v.recorded_at.strftime('%m-%d %H:%M') for v in vitals_qs[:20]] # Last 20 vitals
    vitals_sys_data = [int(v.blood_pressure.split('/')[0]) if v.blood_pressure and '/' in v.blood_pressure else None for v in vitals_qs[:20]]
    vitals_dia_data = [int(v.blood_pressure.split('/')[1]) if v.blood_pressure and '/' in v.blood_pressure else None for v in vitals_qs[:20]]
    vitals_temp_data = [v.temperature for v in vitals_qs[:20]]

    # Ensure no None values for charts, convert to 0 or filter
    vitals_sys_data = [x if x is not None else 0 for x in vitals_sys_data]
    vitals_dia_data = [x if x is not None else 0 for x in vitals_dia_data]
    vitals_temp_data = [x if x is not None else 0 for x in vitals_temp_data]


    # --- Prepare Summary Statistics ---
    summary = {
        'total_consultations': len(consultations),
        'total_prescriptions': len(prescriptions),
        'total_vitals': len(vitals),
        'total_lab_test_groups': len(lab_test_groups),
        'total_individual_lab_tests': sum(len(group['tests']) for group in lab_test_groups),
        'pending_lab_test_groups': len([g for g in lab_test_groups if g['group_status'] in ['pending', 'in_progress']]),
        'completed_lab_test_groups': len([g for g in lab_test_groups if g['group_status'] == 'completed']),
        'total_nursing_notes': len(nursing_notes),
        'total_admissions': len(admissions),
        'current_admission': any(a['status'] == 'Admitted' for a in admissions),
        'total_bills': len(bills),
        'outstanding_bills_count': len([b for b in bills if b['outstanding_amount'] > 0]),
        'total_payments': len(payments),
        'total_referrals': len(referrals),
        'total_appointments': len(appointments),
        'total_care_plans': len(care_plans),
        'total_handover_logs': len(handover_logs),
        'total_amount_billed': sum(b['final_amount'] for b in bills),
        'total_amount_paid': sum(p['amount'] for p in payments),
    }


    # --- Handle Exports ---
    if export_type == 'csv':
        return _export_doctor_report_csv(
            patient_data_for_display, consultations, prescriptions, vitals,
            lab_test_groups, nursing_notes, admissions, care_plans,
            referrals, appointments, bills, payments, handover_logs, summary
        )
    elif export_type == 'pdf':
        return _export_doctor_report_pdf(
            patient_data_for_display, consultations, prescriptions, vitals,
            lab_test_groups, nursing_notes, admissions, care_plans,
            referrals, appointments, bills, payments, handover_logs, summary
        )

    # --- Render Page ---
    context = {
        'all_patients': all_patients,
        'selected_patient': patient_data_for_display,
        'date_from': date_from_param,
        'date_to': date_to_param,

        # Detailed Data for Tables
        'consultations': consultations,
        'prescriptions': prescriptions,
        'vitals': vitals, # Ordered by oldest to newest for charts
        'lab_test_groups': lab_test_groups, # Grouped Lab Tests
        'nursing_notes': nursing_notes,
        'admissions': admissions,
        'care_plans': care_plans,
        'referrals': referrals,
        'appointments': appointments,
        'bills': bills,
        'payments': payments,
        'handover_logs': handover_logs,
        'summary': summary,

        # Chart Data (JSON serialized)
        'consultation_labels_json': json.dumps(consultation_labels),
        'consultation_data_json': json.dumps(consultation_data),
        'top_meds_labels_json': json.dumps(top_meds_labels),
        'top_meds_data_json': json.dumps(top_meds_data),
        'lab_status_labels_json': json.dumps(lab_status_labels),
        'lab_status_data_json': json.dumps(lab_status_data),
        'vital_bp_labels_json': json.dumps(vitals_bp_labels),
        'vital_sys_data_json': json.dumps(vitals_sys_data),
        'vital_dia_data_json': json.dumps(vitals_dia_data),
        'vital_temp_data_json': json.dumps(vitals_temp_data),
    }

    return render(request, 'hms_admin/doctor_reports.html', context)

# --- Export Helper Functions ---

def _export_doctor_report_csv(
    patient_info, consultations, prescriptions, vitals,
    lab_test_groups, nursing_notes, admissions, care_plans,
    referrals, appointments, bills, payments, handover_logs, summary
):
    response = HttpResponse(content_type='text/csv')
    file_name = f"Doctor_Report_{patient_info['full_name'].replace(' ', '_')}_{timezone.now().strftime('%Y%m%d%H%M')}.csv"
    response['Content-Disposition'] = f'attachment; filename="{file_name}"'

    writer = csv.writer(response)

    # Patient Information
    writer.writerow(["--- Patient Information ---"])
    writer.writerow(["Field", "Value"])
    for key, value in patient_info.items():
        if isinstance(value, str) and "photo_url" in key: # Exclude photo URL from CSV
             continue
        writer.writerow([key.replace('_', ' ').title(), value])
    writer.writerow([]) # Spacer

    # Summary
    writer.writerow(["--- Summary ---"])
    for key, value in summary.items():
        writer.writerow([key.replace('_', ' ').title(), value])
    writer.writerow([])

    # Consultations
    if consultations:
        writer.writerow(["--- Consultations ---"])
        writer.writerow(["Date", "Doctor", "Symptoms", "Diagnosis Summary", "Advice"])
        for c in consultations:
            writer.writerow([c['date'], c['doctor'], c['symptoms'], c['diagnosis_summary'], c['advice']])
        writer.writerow([])

    # Prescriptions
    if prescriptions:
        writer.writerow(["--- Prescriptions ---"])
        writer.writerow(["Date", "Medication", "Instructions", "Start Date", "Prescribed By"])
        for p in prescriptions:
            writer.writerow([p['date'], p['medication'], p['instructions'], p['start_date'], p['prescribed_by']])
        writer.writerow([])

    # Vitals
    if vitals:
        writer.writerow(["--- Vitals ---"])
        writer.writerow(["Recorded At", "Recorded By", "Temp", "BP", "Pulse", "Resp Rate", "Weight", "Height", "BMI", "Notes"])
        for v in vitals:
            writer.writerow([
                v['recorded_at'], v['recorded_by'], v['temperature'], v['blood_pressure'],
                v['pulse'], v['respiratory_rate'], v['weight'], v['height'], v['bmi'], v['notes']
            ])
        writer.writerow([])

    # Lab Tests
    if lab_test_groups:
        writer.writerow(["--- Lab Tests ---"])
        for group in lab_test_groups:
            writer.writerow([f"Test Request ID: {group['request_id']}"])
            writer.writerow([f"Requested At: {group['requested_at']}, Doctor: {group['doctor_name']}, Status: {group['group_status'].title()}"])
            if group['doctor_comment']:
                writer.writerow(["Doctor Comment:", group['doctor_comment']['comment']])
            if group['result_file'] and group['result_file']['file_url']:
                 writer.writerow(["Lab Result File:", group['result_file']['file_name'], group['result_file']['file_url']])
            writer.writerow(["Test Name", "Category", "Status", "Result Value", "Normal Range", "Date Performed", "Performed By"])
            for test in group['tests']:
                writer.writerow([
                    test['test_name'], test['category'], test['status'], test['result_value'],
                    test['normal_range'], test['date_performed'], test['performed_by']
                ])
            writer.writerow([]) # Spacer after each group

    # Nursing Notes
    if nursing_notes:
        writer.writerow(["--- Nursing Notes ---"])
        writer.writerow(["Date", "Nurse", "Note Type", "Notes", "Patient Status", "Follow Up"])
        for n in nursing_notes:
            writer.writerow([n['date'], n['nurse'], n['note_type'], n['notes'], n['patient_status'], n['follow_up']])
        writer.writerow([])

    # Admissions
    if admissions:
        writer.writerow(["--- Admissions ---"])
        writer.writerow(["Admission Date", "Doctor Assigned", "Status", "Discharge Date", "Discharge Notes", "Admitted By"])
        for a in admissions:
            writer.writerow([a['admission_date'], a['doctor_assigned'], a['status'], a['discharge_date'], a['discharge_notes'], a['admitted_by']])
        writer.writerow([])

    # Care Plans
    if care_plans:
        writer.writerow(["--- Care Plans ---"])
        writer.writerow(["Created At", "Created By", "Clinical Findings", "Plan of Care"])
        for cp in care_plans:
            writer.writerow([cp['created_at'], cp['created_by'], cp['clinical_findings'], cp['plan_of_care']])
        writer.writerow([])
    
    # Referrals
    if referrals:
        writer.writerow(["--- Referrals ---"])
        writer.writerow(["Department", "Notes"])
        for r in referrals:
            writer.writerow([r['department'], r['notes']])
        writer.writerow([])

    # Appointments
    if appointments:
        writer.writerow(["--- Appointments ---"])
        writer.writerow(["Scheduled Time", "Department"])
        for appt in appointments:
            writer.writerow([appt['scheduled_time'], appt['department']])
        writer.writerow([])

    # Bills
    if bills:
        writer.writerow(["--- Patient Bills ---"])
        for b in bills:
            writer.writerow([f"Bill Number: {b['bill_number']}"])
            writer.writerow([f"Created At: {b['created_at']}, Total: ₦{b['total_amount']:.2f}, Discount: ₦{b['discount_amount']:.2f}, Final: ₦{b['final_amount']:.2f}, Paid: ₦{b['amount_paid']:.2f}, Outstanding: ₦{b['outstanding_amount']:.2f}, Status: {b['status']}"])
            if b['notes'] != 'N/A':
                 writer.writerow(["Notes:", b['notes']])
            if b['items']:
                writer.writerow(["  Item Description", "Service Type", "Quantity", "Unit Price", "Total Price"])
                for item in b['items']:
                    writer.writerow([
                        f"  {item['description']}", item['service_type'], item['quantity'],
                        f"₦{item['unit_price']:.2f}", f"₦{item['total_price']:.2f}"
                    ])
            writer.writerow([])

    # Payments
    if payments:
        writer.writerow(["--- Payments ---"])
        writer.writerow(["Amount", "Payment Date", "Method", "Reference", "Status", "Processed By", "Bill No."])
        for pay in payments:
            writer.writerow([
                f"₦{pay['amount']:.2f}", pay['payment_date'], pay['payment_method'],
                pay['payment_reference'], pay['status'], pay['processed_by'], pay['bill_number']
            ])
        writer.writerow([])
    
    # Handover Logs
    if handover_logs:
        writer.writerow(["--- Handover Logs ---"])
        writer.writerow(["Timestamp", "Author", "Notes"])
        for hl in handover_logs:
            writer.writerow([hl['timestamp'], hl['author'], hl['notes']])
        writer.writerow([])


    return response

def _export_doctor_report_pdf(
    patient_info, consultations, prescriptions, vitals,
    lab_test_groups, nursing_notes, admissions, care_plans,
    referrals, appointments, bills, payments, handover_logs, summary
):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            rightMargin=50, leftMargin=50,
                            topMargin=50, bottomMargin=50)
    styles = getSampleStyleSheet()
    elements = []

    # Title
    elements.append(Paragraph("Doctor's Comprehensive Report", styles['h1']))
    elements.append(Paragraph(f"For Patient: <b>{patient_info['full_name']} (ID: {patient_info['id']})</b>", styles['h2']))
    elements.append(Paragraph(f"Report Generated: {timezone.now().strftime('%Y-%m-%d %H:%M')}", styles['Normal']))
    if patient_info.get('date_from') and patient_info.get('date_to'):
         elements.append(Paragraph(f"Filtered Period: {patient_info['date_from']} to {patient_info['date_to']}", styles['Normal']))
    elements.append(Spacer(1, 12))

    # Patient Information Table
    elements.append(Paragraph("Patient Demographics", styles['h3']))
    patient_data_table = [
        ['Field', 'Value'],
        ['Full Name', patient_info['full_name']],
        ['Date of Birth', patient_info['date_of_birth']],
        ['Age', patient_info['age']],
        ['Gender', patient_info['gender']],
        ['Blood Group', patient_info['blood_group']],
        ['Phone', patient_info['phone']],
        ['Email', patient_info['email']],
        ['Address', patient_info['address']],
        ['Marital Status', patient_info['marital_status']],
        ['Nationality', patient_info['nationality']],
        ['Current Status', patient_info['status']],
        ['Is Inpatient', 'Yes' if patient_info['is_inpatient'] else 'No'],
        ['Date Registered', patient_info['date_registered']],
        ['Diagnosis', patient_info['diagnosis']],
        ['Medication', patient_info['medication']],
        ['Next of Kin', patient_info['next_of_kin_name']],
        ['Next of Kin Phone', patient_info['next_of_kin_phone']],
    ]
    table_style_patient = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#007bff')), # Primary blue header
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BOX', (0, 0), (-1, -1), 1, colors.black),
    ])
    p_table = Table(patient_data_table, colWidths=[150, 350])
    p_table.setStyle(table_style_patient)
    elements.append(p_table)
    elements.append(Spacer(1, 12))

    # Summary Section
    elements.append(Paragraph("Summary", styles['h3']))
    summary_data = [
        ['Category', 'Count'],
        ['Total Consultations', summary['total_consultations']],
        ['Total Prescriptions', summary['total_prescriptions']],
        ['Total Vitals Recorded', summary['total_vitals']],
        ['Total Lab Test Requests', summary['total_individual_lab_tests']],
        ['Pending Lab Tests', summary['pending_lab_test_groups']],
        ['Completed Lab Tests', summary['completed_lab_test_groups']],
        ['Total Nursing Notes', summary['total_nursing_notes']],
        ['Total Admissions', summary['total_admissions']],
        ['Total Bills', summary['total_bills']],
        ['Outstanding Bills', summary['outstanding_bills_count']],
        ['Total Payments', summary['total_payments']],
        ['Total Referrals', summary['total_referrals']],
        ['Total Appointments', summary['total_appointments']],
        ['Total Care Plans', summary['total_care_plans']],
        ['Total Handover Logs', summary['total_handover_logs']],
        ['Total Amount Billed', f"₦{summary['total_amount_billed']:.2f}"],
        ['Total Amount Paid', f"₦{summary['total_amount_paid']:.2f}"],
    ]
    summary_table = Table(summary_data, colWidths=[250, 150])
    summary_table.setStyle(table_style_patient) # Reuse patient table style
    elements.append(summary_table)
    elements.append(Spacer(1, 12))


    # Consultations
    if consultations:
        elements.append(Paragraph("Consultations", styles['h3']))
        data = [['Date', 'Doctor', 'Symptoms', 'Diagnosis Summary', 'Advice']]
        for c in consultations:
            data.append([c['date'], c['doctor'], Paragraph(c['symptoms'], styles['Normal']), Paragraph(c['diagnosis_summary'], styles['Normal']), Paragraph(c['advice'], styles['Normal'])])
        table = Table(data, colWidths=[90, 80, 100, 100, 100]) # Adjusted for Paragraph
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#6c757d')), # Gray header
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('BOX', (0, 0), (-1, -1), 1, colors.black),
            ('WORDWRAP', (2, 1), (4, -1), True), # Enable word wrap for text fields
            ('LEFTPADDING', (2, 1), (4, -1), 6),
            ('RIGHTPADDING', (2, 1), (4, -1), 6),
            ('TOPPADDING', (2, 1), (4, -1), 6),
            ('BOTTOMPADDING', (2, 1), (4, -1), 6),
        ]))
        elements.append(table)
        elements.append(Spacer(1, 12))

    # Prescriptions
    if prescriptions:
        elements.append(Paragraph("Prescriptions", styles['h3']))
        data = [['Date', 'Medication', 'Instructions', 'Start Date', 'Prescribed By']]
        for p in prescriptions:
            data.append([p['date'], p['medication'], Paragraph(p['instructions'], styles['Normal']), p['start_date'], p['prescribed_by']])
        table = Table(data, colWidths=[90, 120, 150, 70, 70])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#28a745')), # Success green header
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('BOX', (0, 0), (-1, -1), 1, colors.black),
            ('WORDWRAP', (2, 1), (2, -1), True),
            ('LEFTPADDING', (2, 1), (2, -1), 6),
            ('RIGHTPADDING', (2, 1), (2, -1), 6),
            ('TOPPADDING', (2, 1), (2, -1), 6),
            ('BOTTOMPADDING', (2, 1), (2, -1), 6),
        ]))
        elements.append(table)
        elements.append(Spacer(1, 12))

    # Vitals
    if vitals:
        elements.append(Paragraph("Vitals", styles['h3']))
        data = [['Recorded At', 'Recorded By', 'Temp', 'BP', 'Pulse', 'Resp Rate', 'Weight (kg)', 'Height (cm)', 'BMI', 'Notes']]
        for v in vitals:
            data.append([
                v['recorded_at'], v['recorded_by'], str(v['temperature']) if v['temperature'] else 'N/A',
                v['blood_pressure'], str(v['pulse']) if v['pulse'] else 'N/A',
                str(v['respiratory_rate']) if v['respiratory_rate'] else 'N/A',
                str(v['weight']) if v['weight'] else 'N/A',
                str(v['height']) if v['height'] else 'N/A',
                str(v['bmi']) if v['bmi'] else 'N/A', Paragraph(v['notes'], styles['Normal'])
            ])
        table = Table(data, colWidths=[80, 70, 30, 45, 30, 40, 40, 40, 30, 100])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#ffc107')), # Warning yellow header
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('BOX', (0, 0), (-1, -1), 1, colors.black),
            ('WORDWRAP', (9, 1), (9, -1), True),
            ('LEFTPADDING', (9, 1), (9, -1), 6),
            ('RIGHTPADDING', (9, 1), (9, -1), 6),
            ('TOPPADDING', (9, 1), (9, -1), 6),
            ('BOTTOMPADDING', (9, 1), (9, -1), 6),
        ]))
        elements.append(table)
        elements.append(Spacer(1, 12))

    # Lab Tests (Grouped)
    if lab_test_groups:
        elements.append(Paragraph("Lab Tests", styles['h3']))
        for group in lab_test_groups:
            elements.append(Paragraph(f"<b>Test Request ID: {group['request_id']}</b>", styles['Normal']))
            elements.append(Paragraph(f"Requested At: {group['requested_at']}, Doctor: {group['doctor_name']}, Status: {group['group_status'].title()}", styles['Normal']))
            if group['doctor_comment']:
                elements.append(Paragraph(f"<i>Doctor Comment: {group['doctor_comment']['comment']}</i>", styles['Normal']))
            if group['result_file'] and group['result_file']['file_url']:
                elements.append(Paragraph(f"Lab Result File: <link href='{group['result_file']['file_url']}'>{group['result_file']['file_name']}</link>", styles['Normal']))
            
            data = [['Test Name', 'Category', 'Status', 'Result Value', 'Normal Range', 'Date Performed', 'Performed By']]
            for test in group['tests']:
                data.append([
                    test['test_name'], test['category'], test['status'],
                    Paragraph(test['result_value'], styles['Normal']), test['normal_range'],
                    test['date_performed'], test['performed_by']
                ])
            table = Table(data, colWidths=[90, 70, 50, 100, 70, 70, 70])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#17a2b8')), # Info blue header
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('BOX', (0, 0), (-1, -1), 1, colors.black),
                ('WORDWRAP', (3, 1), (3, -1), True),
                ('LEFTPADDING', (3, 1), (3, -1), 6),
                ('RIGHTPADDING', (3, 1), (3, -1), 6),
                ('TOPPADDING', (3, 1), (3, -1), 6),
                ('BOTTOMPADDING', (3, 1), (3, -1), 6),
            ]))
            elements.append(table)
            elements.append(Spacer(1, 12))

    # Nursing Notes
    if nursing_notes:
        elements.append(Paragraph("Nursing Notes", styles['h3']))
        data = [['Date', 'Nurse', 'Note Type', 'Notes', 'Patient Status', 'Follow Up']]
        for n in nursing_notes:
            data.append([n['date'], n['nurse'], n['note_type'], Paragraph(n['notes'], styles['Normal']), n['patient_status'], Paragraph(n['follow_up'], styles['Normal'])])
        table = Table(data, colWidths=[90, 70, 80, 100, 70, 90])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#6f42c1')), # Purple header
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('BOX', (0, 0), (-1, -1), 1, colors.black),
            ('WORDWRAP', (3, 1), (3, -1), True),
            ('WORDWRAP', (5, 1), (5, -1), True),
            ('LEFTPADDING', (3, 1), (3, -1), 6),
            ('RIGHTPADDING', (3, 1), (3, -1), 6),
            ('TOPPADDING', (3, 1), (3, -1), 6),
            ('BOTTOMPADDING', (3, 1), (3, -1), 6),
        ]))
        elements.append(table)
        elements.append(Spacer(1, 12))

    # Admissions
    if admissions:
        elements.append(Paragraph("Admissions", styles['h3']))
        data = [['Admission Date', 'Admitted By', 'Doctor Assigned', 'Status', 'Discharge Date', 'Discharge Notes']]
        for a in admissions:
            data.append([a['admission_date'], a['admitted_by'], a['doctor_assigned'], a['status'], a['discharge_date'], Paragraph(a['discharge_notes'], styles['Normal'])])
        table = Table(data, colWidths=[90, 90, 90, 50, 90, 100])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#007bff')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('BOX', (0, 0), (-1, -1), 1, colors.black),
            ('WORDWRAP', (5, 1), (5, -1), True),
            ('LEFTPADDING', (5, 1), (5, -1), 6),
            ('RIGHTPADDING', (5, 1), (5, -1), 6),
            ('TOPPADDING', (5, 1), (5, -1), 6),
            ('BOTTOMPADDING', (5, 1), (5, -1), 6),
        ]))
        elements.append(table)
        elements.append(Spacer(1, 12))

    # Care Plans
    if care_plans:
        elements.append(Paragraph("Care Plans", styles['h3']))
        data = [['Created At', 'Created By', 'Clinical Findings', 'Plan of Care']]
        for cp in care_plans:
            data.append([cp['created_at'], cp['created_by'], Paragraph(cp['clinical_findings'], styles['Normal']), Paragraph(cp['plan_of_care'], styles['Normal'])])
        table = Table(data, colWidths=[100, 100, 150, 150])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#fd7e14')), # Orange header
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('BOX', (0, 0), (-1, -1), 1, colors.black),
            ('WORDWRAP', (2, 1), (3, -1), True),
            ('LEFTPADDING', (2, 1), (3, -1), 6),
            ('RIGHTPADDING', (2, 1), (3, -1), 6),
            ('TOPPADDING', (2, 1), (3, -1), 6),
            ('BOTTOMPADDING', (2, 1), (3, -1), 6),
        ]))
        elements.append(table)
        elements.append(Spacer(1, 12))
    
    # Referrals
    if referrals:
        elements.append(Paragraph("Referrals", styles['h3']))
        data = [['Department', 'Notes']]
        for r in referrals:
            data.append([r['department'], Paragraph(r['notes'], styles['Normal'])])
        table = Table(data, colWidths=[150, 350])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#20c997')), # Teal header
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('BOX', (0, 0), (-1, -1), 1, colors.black),
            ('WORDWRAP', (1, 1), (1, -1), True),
            ('LEFTPADDING', (1, 1), (1, -1), 6),
            ('RIGHTPADDING', (1, 1), (1, -1), 6),
            ('TOPPADDING', (1, 1), (1, -1), 6),
            ('BOTTOMPADDING', (1, 1), (1, -1), 6),
        ]))
        elements.append(table)
        elements.append(Spacer(1, 12))

    # Appointments
    if appointments:
        elements.append(Paragraph("Appointments", styles['h3']))
        data = [['Scheduled Time', 'Department']]
        for appt in appointments:
            data.append([appt['scheduled_time'], appt['department']])
        table = Table(data, colWidths=[200, 300])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#6610f2')), # Indigo header
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('BOX', (0, 0), (-1, -1), 1, colors.black),
        ]))
        elements.append(table)
        elements.append(Spacer(1, 12))

    # Bills
    if bills:
        elements.append(Paragraph("Bills", styles['h3']))
        for b in bills:
            elements.append(Paragraph(f"<b>Bill Number: {b['bill_number']}</b>", styles['Normal']))
            elements.append(Paragraph(f"Created At: {b['created_at']}, Total: ₦{b['total_amount']:.2f}, Discount: ₦{b['discount_amount']:.2f}, Final: ₦{b['final_amount']:.2f}, Paid: ₦{b['amount_paid']:.2f}, Outstanding: ₦{b['outstanding_amount']:.2f}, Status: {b['status']}", styles['Normal']))
            if b['notes'] != 'N/A':
                 elements.append(Paragraph(f"Notes: {b['notes']}", styles['Normal']))
            if b['items']:
                elements.append(Paragraph("Items:", styles['Normal']))
                item_data = [['Description', 'Service Type', 'Qty', 'Unit Price', 'Total Price']]
                for item in b['items']:
                    item_data.append([
                        item['description'], item['service_type'], item['quantity'],
                        f"₦{item['unit_price']:.2f}", f"₦{item['total_price']:.2f}"
                    ])
                item_table = Table(item_data, colWidths=[150, 100, 40, 80, 80])
                item_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('GRID', (0, 0), (-1, -1), 0.25, colors.grey),
                    ('BOX', (0, 0), (-1, -1), 0.5, colors.black),
                ]))
                elements.append(item_table)
            elements.append(Spacer(1, 12))

    # Payments
    if payments:
        elements.append(Paragraph("Payments", styles['h3']))
        data = [['Amount', 'Payment Date', 'Method', 'Reference', 'Status', 'Processed By', 'Bill No.']]
        for pay in payments:
            data.append([
                f"₦{pay['amount']:.2f}", pay['payment_date'], pay['payment_method'],
                pay['payment_reference'], pay['status'], pay['processed_by'], pay['bill_number']
            ])
        table = Table(data, colWidths=[70, 90, 70, 90, 60, 70, 50])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e83e8c')), # Pink header
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('BOX', (0, 0), (-1, -1), 1, colors.black),
        ]))
        elements.append(table)
        elements.append(Spacer(1, 12))
    
    # Handover Logs
    if handover_logs:
        elements.append(Paragraph("Handover Logs", styles['h3']))
        data = [['Timestamp', 'Author', 'Notes']]
        for hl in handover_logs:
            data.append([hl['timestamp'], hl['author'], Paragraph(hl['notes'], styles['Normal'])])
        table = Table(data, colWidths=[100, 80, 320])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#dc3545')), # Danger red header
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('BOX', (0, 0), (-1, -1), 1, colors.black),
            ('WORDWRAP', (2, 1), (2, -1), True),
            ('LEFTPADDING', (2, 1), (2, -1), 6),
            ('RIGHTPADDING', (2, 1), (2, -1), 6),
            ('TOPPADDING', (2, 1), (2, -1), 6),
            ('BOTTOMPADDING', (2, 1), (2, -1), 6),
        ]))
        elements.append(table)
        elements.append(Spacer(1, 12))


    doc.build(elements)
    buffer.seek(0)
    return HttpResponse(buffer, content_type='application/pdf')

@login_required(login_url='home')
def receptionist_reports(request):
    """
    Renders the Receptionist's Reports Dashboard with patient registration,
    admission, appointment, and referral data, along with graphical representations
    and export options.
    """
    # Ensure only 'receptionist' or 'admin' role can access this dashboard
    if not hasattr(request.user, 'staff') or request.user.staff.role not in ['receptionist', 'admin']:
        messages.error(request, "Access denied. You do not have permission to view this page.")
        return redirect('home')

    all_patients = Patient.objects.all().order_by('full_name')
    all_departments = Department.objects.all().order_by('name')

    # Get filter parameters from GET request
    selected_patient_id = request.GET.get('patient_id')
    date_from_param = request.GET.get('date_from')
    date_to_param = request.GET.get('date_to')
    export_type = request.GET.get('export_type') # 'csv', 'pdf'

    current_patient = None
    if selected_patient_id:
        try:
            current_patient = get_object_or_404(Patient, id=selected_patient_id)
        except Exception as e:
            messages.error(request, f"Selected patient not found: {e}")
            current_patient = None
            selected_patient_id = None # Reset if patient not found
    
    # Base querysets (before patient-specific filtering, but after date range if global)
    # For trend charts, we want overall data, not patient-specific, so filter dates globally.
    # For tables, we want patient-specific data, filtered by patient and date.

    # Apply global date filters for overall trends if date range is set
    filtered_patients_qs = Patient.objects.all()
    filtered_admissions_qs = Admission.objects.all()
    filtered_appointments_qs = Appointment.objects.all()
    filtered_referrals_qs = Referral.objects.all()

    if date_from_param or date_to_param:
        filtered_patients_qs = apply_date_filter(filtered_patients_qs, date_from_param, date_to_param, 'date_registered')
        filtered_admissions_qs = apply_date_filter(filtered_admissions_qs, date_from_param, date_to_param, 'admission_date', is_datetime_field=False)
        filtered_appointments_qs = apply_date_filter(filtered_appointments_qs, date_from_param, date_to_param, 'scheduled_time')
        # Referrals usually don't have a specific date field, might need 'id' or 'timestamp' if added.
        # Assuming Referral has a 'created_at' or 'id' field for time-based filtering.
        # For now, let's assume 'id' for ordering if no date field exists or skip time filter for referrals.
        # If Referral model gets a 'created_at' field, use it.
        # filtered_referrals_qs = apply_date_filter(filtered_referrals_qs, date_from_param, date_to_param, 'created_at')

    
    # --- Fetch Data for Summary & Charts (Overall & Filtered) ---

    # Patient Registrations Trend (Last 6 months)
    registration_labels = []
    registration_data = []
    for i in range(5, -1, -1): # Last 6 months including current
        month_start_date = (timezone.now() - timedelta(days=30*i)).replace(day=1).date()
        next_month_start_date = (month_start_date + timedelta(days=32)).replace(day=1) # First day of next month
        
        count = Patient.objects.filter(
            date_registered__date__gte=month_start_date,
            date_registered__date__lt=next_month_start_date # Use less than for next month's start
        ).count()
        registration_labels.append(month_start_date.strftime('%b %Y'))
        registration_data.append(count)

    # Admissions Trend (Last 6 months)
    admissions_trend_labels = []
    admissions_trend_data = []
    for i in range(5, -1, -1):
        month_start_date = (timezone.now() - timedelta(days=30*i)).replace(day=1).date()
        next_month_start_date = (month_start_date + timedelta(days=32)).replace(day=1)
        
        count = Admission.objects.filter(
            admission_date__gte=month_start_date,
            admission_date__lt=next_month_start_date
        ).count()
        admissions_trend_labels.append(month_start_date.strftime('%b %Y'))
        admissions_trend_data.append(count)

    # Appointments Trend (Last 6 months)
    appointments_trend_labels = []
    appointments_trend_data = []
    for i in range(5, -1, -1):
        month_start_dt = (timezone.now() - timedelta(days=30*i)).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        next_month_start_dt = (month_start_dt + timedelta(days=32)).replace(day=1, hour=0, minute=0, second=0, microsecond=0) - timedelta(microseconds=1)
        
        count = Appointment.objects.filter(
            scheduled_time__gte=month_start_dt,
            scheduled_time__lte=next_month_start_dt
        ).count()
        appointments_trend_labels.append(month_start_dt.strftime('%b %Y'))
        appointments_trend_data.append(count)


    # Patient Demographics: Gender Distribution
    patients_by_gender = filtered_patients_qs.values('gender').annotate(count=Count('gender')).order_by('gender')
    gender_labels = [item['gender'] for item in patients_by_gender]
    gender_data = [item['count'] for item in patients_by_gender]

    # Patient Demographics: Age Group (re-using logic from admin/doctor reports)
    patients_by_age_group_raw = filtered_patients_qs.annotate(
        # Calculate the difference in years as a base
        years_diff=F('date_registered__year') - F('date_of_birth__year'),
        
        # Determine the age adjustment based on month and day
        # Subtract 1 if the registration date's (month, day) is before the birth date's (month, day)
        age_adjustment=Case(
            When(
                Q(date_registered__month__lt=F('date_of_birth__month')) |
                (
                    Q(date_registered__month=F('date_of_birth__month')) &
                    Q(date_registered__day__lt=F('date_of_birth__day'))
                ),
                then=Value(1)
            ),
            default=Value(0),
            output_field=IntegerField()
        ),
        
        # Calculate the final age by subtracting the adjustment
        age=F('years_diff') - F('age_adjustment')
    ).values('age').annotate(count=Count('age')).order_by('age')

    age_groups = {
        '0-12': 0, '13-19': 0, '20-39': 0, '40-59': 0, '60+': 0
    }
    for p in patients_by_age_group_raw:
        age = p['age']
        if age <= 12:
            age_groups['0-12'] += p['count']
        elif 13 <= age <= 19:
            age_groups['13-19'] += p['count']
        elif 20 <= age <= 39:
            age_groups['20-39'] += p['count']
        elif 40 <= age <= 59:
            age_groups['40-59'] += p['count']
        else:
            age_groups['60+'] += p['count']
    age_labels = list(age_groups.keys())
    age_data = list(age_groups.values())


    # Patient Demographics: Marital Status
    patients_by_marital_status = filtered_patients_qs.values('marital_status').annotate(count=Count('marital_status')).order_by('marital_status')
    marital_status_labels = [item['marital_status'] for item in patients_by_marital_status]
    marital_status_data = [item['count'] for item in patients_by_marital_status]

    # Patient Demographics: Nationality (Top 5)
    patients_by_nationality = filtered_patients_qs.values('nationality').annotate(count=Count('nationality')).order_by('-count')[:5]
    nationality_labels = [item['nationality'] for item in patients_by_nationality]
    nationality_data = [item['count'] for item in patients_by_nationality]

    # Admissions by Status
    admissions_by_status = filtered_admissions_qs.values('status').annotate(count=Count('status')).order_by('status')
    admission_status_labels = [item['status'] for item in admissions_by_status]
    admission_status_data = [item['count'] for item in admissions_by_status]

    # Appointments by Department
    appointments_by_dept = filtered_appointments_qs.values('department__name').annotate(count=Count('department__name')).order_by('department__name')
    appointment_dept_labels = [item['department__name'] for item in appointments_by_dept]
    appointment_dept_data = [item['count'] for item in appointments_by_dept]

    # Referrals by Department
    referrals_by_dept = filtered_referrals_qs.values('department__name').annotate(count=Count('department__name')).order_by('department__name')
    referral_dept_labels = [item['department__name'] for item in referrals_by_dept]
    referral_dept_data = [item['count'] for item in referrals_by_dept]


    # --- Fetch Data for Tables (Patient-specific if selected, otherwise global recent) ---
    
    recent_patients = []
    recent_admissions = []
    recent_appointments = []
    recent_referrals = []

    if current_patient:
        # Patient-specific data
        recent_patients = apply_date_filter(Patient.objects.filter(id=current_patient.id), date_from_param, date_to_param, 'date_registered').order_by('-date_registered')
        recent_admissions = apply_date_filter(Admission.objects.filter(patient=current_patient).select_related('patient'), date_from_param, date_to_param, 'admission_date', is_datetime_field=False).order_by('-admission_date')
        recent_appointments = apply_date_filter(Appointment.objects.filter(patient=current_patient).select_related('patient', 'department'), date_from_param, date_to_param, 'scheduled_time').order_by('-scheduled_time')
        recent_referrals = apply_date_filter( Referral.objects.filter(patient=current_patient).select_related('patient', 'department'), date_from_param, date_to_param, 'created_at').order_by('-created_at') # Also order by the date field
        
        # Format patient data for display in tables (similar to doctor_reports for consistency)
        patient_data_for_display = {
            'id': current_patient.id,
            'full_name': current_patient.full_name,
            'gender': current_patient.gender,
            'date_of_birth': current_patient.date_of_birth.strftime('%Y-%m-%d'),
            'age': timezone.now().year - current_patient.date_of_birth.year - ((timezone.now().month, timezone.now().day) < (current_patient.date_of_birth.month, current_patient.date_of_birth.day)),
            'blood_group': current_patient.blood_group,
            'phone': current_patient.phone,
            'email': current_patient.email or 'N/A',
            'address': current_patient.address,
            'marital_status': current_patient.marital_status,
            'nationality': current_patient.nationality,
            'id_type': current_patient.id_type or 'N/A',
            'id_number': current_patient.id_number or 'N/A',
            'status': current_patient.get_status_display(),
            'is_inpatient': current_patient.is_inpatient,
            'date_registered': current_patient.date_registered.strftime('%Y-%m-%d %H:%M'),
            'referred_by': current_patient.referred_by or 'N/A',
            'next_of_kin_name': current_patient.next_of_kin_name or 'N/A',
            'next_of_kin_phone': current_patient.next_of_kin_phone or 'N/A',
            'next_of_kin_relationship': current_patient.next_of_kin_relationship or 'N/A',
            'notes': current_patient.notes or 'N/A',
        }
        # Handle patient photo
        photo_url = ''
        if current_patient.photo and hasattr(current_patient.photo, 'url'):
            try:
                if default_storage.exists(current_patient.photo.name):
                    photo_url = current_patient.photo.url
            except Exception as e:
                logger.warning(f"Error accessing patient photo for patient {current_patient.id}: {e}")
                pass
        patient_data_for_display['photo_url'] = photo_url

    else:
        # Global recent data if no patient selected
        recent_patients = filtered_patients_qs.order_by('-date_registered')[:10]
        recent_admissions = filtered_admissions_qs.select_related('patient').order_by('-admission_date')[:10]
        recent_appointments = filtered_appointments_qs.select_related('patient', 'department').order_by('-scheduled_time')[:10]
        recent_referrals = filtered_referrals_qs.select_related('patient', 'department').order_by('-id')[:10]
        patient_data_for_display = None # No single patient overview if no patient is selected.


    # --- Summary Statistics ---
    summary = {
        'total_registered_patients': filtered_patients_qs.count(),
        'patients_registered_today': filtered_patients_qs.filter(date_registered__date=timezone.now().date()).count(),
        'total_admissions': filtered_admissions_qs.count(),
        'admissions_today': filtered_admissions_qs.filter(admission_date=timezone.now().date()).count(),
        'total_appointments': filtered_appointments_qs.count(),
        'appointments_today': filtered_appointments_qs.filter(scheduled_time__date=timezone.now().date()).count(),
        'total_referrals': filtered_referrals_qs.count(),
    }


    # --- Handle Exports ---
    if export_type == 'csv':
        return _export_receptionist_report_csv(
            patient_data_for_display, recent_patients, recent_admissions,
            recent_appointments, recent_referrals, summary,
            registration_labels, registration_data,
            admissions_trend_labels, admissions_trend_data,
            appointments_trend_labels, appointments_trend_data,
            gender_labels, gender_data, age_labels, age_data,
            marital_status_labels, marital_status_data,
            nationality_labels, nationality_data,
            admission_status_labels, admission_status_data,
            appointment_dept_labels, appointment_dept_data,
            referral_dept_labels, referral_dept_data,
        )
    elif export_type == 'pdf':
        return _export_receptionist_report_pdf(
            patient_data_for_display, recent_patients, recent_admissions,
            recent_appointments, recent_referrals, summary,
            registration_labels, registration_data,
            admissions_trend_labels, admissions_trend_data,
            appointments_trend_labels, appointments_trend_data,
            gender_labels, gender_data, age_labels, age_data,
            marital_status_labels, marital_status_data,
            nationality_labels, nationality_data,
            admission_status_labels, admission_status_data,
            appointment_dept_labels, appointment_dept_data,
            referral_dept_labels, referral_dept_data,
        )

    # --- Render Page ---
    context = {
        'all_patients': all_patients,
        'all_departments': all_departments,
        'selected_patient': patient_data_for_display, # This will be None if no patient selected
        'date_from': date_from_param,
        'date_to': date_to_param,
        
        'summary': summary,

        # Chart Data (JSON serialized)
        'registration_labels_json': json.dumps(registration_labels),
        'registration_data_json': json.dumps(registration_data),
        'admissions_trend_labels_json': json.dumps(admissions_trend_labels),
        'admissions_trend_data_json': json.dumps(admissions_trend_data),
        'appointments_trend_labels_json': json.dumps(appointments_trend_labels),
        'appointments_trend_data_json': json.dumps(appointments_trend_data),
        'gender_labels_json': json.dumps(gender_labels),
        'gender_data_json': json.dumps(gender_data),
        'age_labels_json': json.dumps(age_labels),
        'age_data_json': json.dumps(age_data),
        'marital_status_labels_json': json.dumps(marital_status_labels),
        'marital_status_data_json': json.dumps(marital_status_data),
        'nationality_labels_json': json.dumps(nationality_labels),
        'nationality_data_json': json.dumps(nationality_data),
        'admission_status_labels_json': json.dumps(admission_status_labels),
        'admission_status_data_json': json.dumps(admission_status_data),
        'appointment_dept_labels_json': json.dumps(appointment_dept_labels),
        'appointment_dept_data_json': json.dumps(appointment_dept_data),
        'referral_dept_labels_json': json.dumps(referral_dept_labels),
        'referral_dept_data_json': json.dumps(referral_dept_data),

        # Table Data (recent or patient-specific)
        'recent_patients': recent_patients,
        'recent_admissions': recent_admissions,
        'recent_appointments': recent_appointments,
        'recent_referrals': recent_referrals,
    }

    return render(request, 'hms_admin/reception_reports.html', context)

@login_required
def nurses_report(request):
    """Main nurses report dashboard"""
    today = timezone.now().date()
    last_30_days = today - timedelta(days=30)
    
    # Get all nurses
    nurses = Staff.objects.filter(role='nurse').select_related('user')
    nurse_users = User.objects.filter(staff__role='nurse')
    
    # Basic stats
    total_nurses = nurses.count()
    active_nurses = nurses.filter(user__is_active=True).count()
    nurses_on_duty = ShiftAssignment.objects.filter(
        date=today, 
        staff__staff__role='nurse'
    ).count()
    
    # Today's attendance
    today_attendance = Attendance.objects.filter(
        date__date=today,
        staff__staff__role='nurse'
    ).aggregate(
        present=Count('id', filter=Q(status='Present')),
        absent=Count('id', filter=Q(status='Absent')),
        on_leave=Count('id', filter=Q(status='On Leave'))
    )
    
    # Nursing notes stats (last 30 days)
    nursing_notes_stats = NursingNote.objects.filter(
        created_at__date__gte=last_30_days
    ).aggregate(
        total_notes=Count('id'),
        care_plan_notes=Count('id', filter=Q(note_type='care_plan')),
        medication_notes=Count('id', filter=Q(note_type='medication')),
        observation_notes=Count('id', filter=Q(note_type='observation'))
    )
    
    # Vitals recorded by nurses (last 30 days)
    vitals_recorded = Vitals.objects.filter(
        recorded_at__date__gte=last_30_days
    ).count()
    
    # Handover logs (last 30 days)
    handover_logs = HandoverLog.objects.filter(
        timestamp__date__gte=last_30_days
    ).count()
    
    # Patient care stats
    patients_under_care = Patient.objects.filter(
        is_inpatient=True
    ).count()
    
    context = {
        'total_nurses': total_nurses,
        'active_nurses': active_nurses,
        'nurses_on_duty': nurses_on_duty,
        'today_attendance': today_attendance,
        'nursing_notes_stats': nursing_notes_stats,
        'vitals_recorded': vitals_recorded,
        'handover_logs': handover_logs,
        'patients_under_care': patients_under_care,
        'nurses': nurses[:10],  # Top 10 for quick view
    }
    
    return render(request, 'hms_admin/nurses_reports.html', context)

@login_required
def nurses_report_api(request):
    """API endpoint for chart data"""
    chart_type = request.GET.get('type', 'attendance')
    
    if chart_type == 'attendance':
        # Last 7 days attendance
        data = []
        for i in range(7):
            date = timezone.now().date() - timedelta(days=i)
            attendance = Attendance.objects.filter(
                date__date=date,
                staff__staff__role='nurse'
            ).aggregate(
                present=Count('id', filter=Q(status='Present')),
                absent=Count('id', filter=Q(status='Absent')),
                on_leave=Count('id', filter=Q(status='On Leave'))
            )
            data.append({
                'date': date.strftime('%Y-%m-%d'),
                'present': attendance['present'] or 0,
                'absent': attendance['absent'] or 0,
                'on_leave': attendance['on_leave'] or 0
            })
        return JsonResponse({'data': list(reversed(data))})
    
    elif chart_type == 'nursing_notes':
        # Last 30 days nursing notes by type
        last_30_days = timezone.now().date() - timedelta(days=30)
        notes_by_type = NursingNote.objects.filter(
            created_at__date__gte=last_30_days
        ).values('note_type').annotate(count=Count('id'))
        
        data = list(notes_by_type)
        return JsonResponse({'data': data})
    
    elif chart_type == 'shift_distribution':
        # Current shift distribution
        today = timezone.now().date()
        shift_data = ShiftAssignment.objects.filter(
            date=today,
            staff__staff__role='nurse'
        ).values('shift__name').annotate(count=Count('id'))
        
        data = list(shift_data)
        return JsonResponse({'data': data})
    
    elif chart_type == 'monthly_performance':
        # Monthly nursing activities
        data = []
        for i in range(6):  # Last 6 months
            month_start = (timezone.now().replace(day=1) - timedelta(days=32*i)).replace(day=1)
            month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            
            notes_count = NursingNote.objects.filter(
                created_at__date__gte=month_start,
                created_at__date__lte=month_end
            ).count()
            
            vitals_count = Vitals.objects.filter(
                recorded_at__date__gte=month_start,
                recorded_at__date__lte=month_end
            ).count()
            
            handovers_count = HandoverLog.objects.filter(
                timestamp__date__gte=month_start,
                timestamp__date__lte=month_end
            ).count()
            
            data.append({
                'month': month_start.strftime('%B %Y'),
                'nursing_notes': notes_count,
                'vitals_recorded': vitals_count,
                'handovers': handovers_count
            })
        
        return JsonResponse({'data': list(reversed(data))})
    
    return JsonResponse({'error': 'Invalid chart type'})


@login_required
def lab_report_view(request):
    """Main lab report dashboard view"""
    
    # Date filtering
    today = timezone.now().date()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)
    
    # Basic statistics
    total_tests = LabTest.objects.count()
    pending_tests = LabTest.objects.filter(status='pending').count()
    completed_tests = LabTest.objects.filter(status='completed').count()
    in_progress_tests = LabTest.objects.filter(status='in_progress').count()
    
    # Today's statistics
    today_tests = LabTest.objects.filter(requested_at__date=today).count()
    today_completed = LabTest.objects.filter(
        status='completed',
        date_performed__date=today
    ).count()
    
    # Weekly trend data
    weekly_data = []
    for i in range(7):
        date = today - timedelta(days=i)
        count = LabTest.objects.filter(requested_at__date=date).count()
        weekly_data.append({
            'date': date.strftime('%Y-%m-%d'),
            'count': count
        })
    weekly_data.reverse()
    
    # Test category distribution
    category_stats = TestCategory.objects.annotate(
        test_count=Count('test_category')
    ).values('name', 'test_count').order_by('-test_count')
    
    # Status distribution for pie chart
    status_stats = LabTest.objects.values('status').annotate(
        count=Count('id')
    ).order_by('-count')
    
    # Monthly completion rate
    monthly_completion = []
    for i in range(6):
        start_date = today.replace(day=1) - timedelta(days=i*30)
        end_date = (start_date + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        
        total = LabTest.objects.filter(
            requested_at__date__range=[start_date, end_date]
        ).count()
        
        completed = LabTest.objects.filter(
            requested_at__date__range=[start_date, end_date],
            status='completed'
        ).count()
        
        rate = (completed / total * 100) if total > 0 else 0
        monthly_completion.append({
            'month': start_date.strftime('%b %Y'),
            'rate': round(rate, 1)
        })
    monthly_completion.reverse()
    
    # Recent tests
    recent_tests = LabTest.objects.select_related(
        'patient', 'category', 'requested_by'
    ).order_by('-requested_at')[:10]
    
    # Top performing technicians
    top_technicians = User.objects.filter(
        performed_tests__isnull=False
    ).annotate(
        test_count=Count('performed_tests')
    ).order_by('-test_count')[:5]
    
    # Pending tests by category
    pending_by_category = TestCategory.objects.annotate(
        pending_count=Count('test_category', filter=Q(test_category__status='pending'))
    ).filter(pending_count__gt=0).order_by('-pending_count')
    
    context = {
        'total_tests': total_tests,
        'pending_tests': pending_tests,
        'completed_tests': completed_tests,
        'in_progress_tests': in_progress_tests,
        'today_tests': today_tests,
        'today_completed': today_completed,
        'weekly_data': json.dumps(weekly_data),
        'category_stats': list(category_stats),
        'status_stats': list(status_stats),
        'monthly_completion': json.dumps(monthly_completion),
        'recent_tests': recent_tests,
        'top_technicians': top_technicians,
        'pending_by_category': pending_by_category,
        'completion_rate': round((completed_tests / total_tests * 100) if total_tests > 0 else 0, 1),
    }
    
    return render(request, 'hms_admin/lab_reports.html', context)

@login_required
def lab_analytics_api(request):
    """API endpoint for dynamic chart data"""
    
    chart_type = request.GET.get('type', 'daily')
    days = int(request.GET.get('days', 30))
    
    today = timezone.now().date()
    start_date = today - timedelta(days=days)
    
    if chart_type == 'daily':
        data = []
        for i in range(days):
            date = start_date + timedelta(days=i)
            tests = LabTest.objects.filter(requested_at__date=date)
            data.append({
                'date': date.strftime('%Y-%m-%d'),
                'total': tests.count(),
                'completed': tests.filter(status='completed').count(),
                'pending': tests.filter(status='pending').count(),
                'in_progress': tests.filter(status='in_progress').count(),
            })
    
    elif chart_type == 'category_performance':
        data = []
        categories = TestCategory.objects.all()
        for category in categories:
            tests = LabTest.objects.filter(
                category=category,
                requested_at__date__gte=start_date
            )
            total = tests.count()
            completed = tests.filter(status='completed').count()
            avg_completion_time = tests.filter(
                status='completed',
                date_performed__isnull=False
            ).extra(
                select={'completion_time': 'TIMESTAMPDIFF(HOUR, requested_at, date_performed)'}
            ).aggregate(Avg('completion_time'))['completion_time__avg'] or 0
            
            data.append({
                'category': category.name,
                'total': total,
                'completed': completed,
                'completion_rate': round((completed / total * 100) if total > 0 else 0, 1),
                'avg_completion_hours': round(avg_completion_time, 1)
            })
    
    return JsonResponse({'data': data})

def account_report(request):
    """Main account report dashboard"""
    today = timezone.now().date()
    current_month = today.month
    current_year = today.year
    
    # Financial Summary
    total_revenue = PatientBill.objects.filter(
        status='paid'
    ).aggregate(Sum('final_amount'))['final_amount__sum'] or Decimal('0.00')
    
    total_expenses = Expense.objects.filter(
        status='paid'
    ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
    
    monthly_revenue = PatientBill.objects.filter(
        created_at__month=current_month,
        created_at__year=current_year,
        status='paid'
    ).aggregate(Sum('final_amount'))['final_amount__sum'] or Decimal('0.00')
    
    monthly_expenses = Expense.objects.filter(
        expense_date__month=current_month,
        expense_date__year=current_year,
        status='paid'
    ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
    
    # Outstanding amounts
    outstanding_bills = PatientBill.objects.filter(
        status__in=['pending', 'partial']
    ).aggregate(Sum('final_amount'))['final_amount__sum'] or Decimal('0.00')
    
    # Revenue by service type (last 30 days)
    last_30_days = today - timedelta(days=30)
    service_revenue = BillItem.objects.filter(
        bill__created_at__gte=last_30_days,
        bill__status='paid'
    ).values('service_type__name').annotate(
        total=Sum('total_price')
    ).order_by('-total')[:10]
    
    # Monthly trends (last 12 months)
    monthly_data = []
    for i in range(12):
        month_date = today.replace(day=1) - timedelta(days=30*i)
        month_revenue = PatientBill.objects.filter(
            created_at__month=month_date.month,
            created_at__year=month_date.year,
            status='paid'
        ).aggregate(Sum('final_amount'))['final_amount__sum'] or Decimal('0.00')
        
        month_expenses = Expense.objects.filter(
            expense_date__month=month_date.month,
            expense_date__year=month_date.year,
            status='paid'
        ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
        
        monthly_data.append({
            'month': month_date.strftime('%B %Y'),
            'revenue': float(month_revenue),
            'expenses': float(month_expenses),
            'profit': float(month_revenue - month_expenses)
        })
    
    monthly_data.reverse()
    
    # Payment method distribution
    payment_methods = Payment.objects.filter(
        status='completed',
        payment_date__gte=last_30_days
    ).values('payment_method').annotate(
        total=Sum('amount'),
        count=Count('id')
    ).order_by('-total')
    
    # Budget utilization
    current_budgets = Budget.objects.filter(
        year=current_year,
        month=current_month
    ).select_related('category')
    
    # Top patients by revenue
    top_patients = PatientBill.objects.filter(
        status='paid'
    ).values('patient__full_name').annotate(
        total_spent=Sum('final_amount')
    ).order_by('-total_spent')[:10]
    
    # Expense categories breakdown
    expense_categories = Expense.objects.filter(
        status='paid',
        expense_date__gte=last_30_days
    ).values('category__name').annotate(
        total=Sum('amount')
    ).order_by('-total')
    
    # Daily revenue trend (last 30 days)
    daily_revenue = PatientBill.objects.filter(
        created_at__gte=last_30_days,
        status='paid'
    ).extra(
        select={'day': 'date(created_at)'}
    ).values('day').annotate(
        revenue=Sum('final_amount')
    ).order_by('day')
    
    context = {
        'total_revenue': total_revenue,
        'total_expenses': total_expenses,
        'monthly_revenue': monthly_revenue,
        'monthly_expenses': monthly_expenses,
        'outstanding_bills': outstanding_bills,
        'net_profit': total_revenue - total_expenses,
        'monthly_profit': monthly_revenue - monthly_expenses,
        'service_revenue': service_revenue,
        'monthly_data': json.dumps(monthly_data),
        'payment_methods': payment_methods,
        'current_budgets': current_budgets,
        'top_patients': top_patients,
        'expense_categories': expense_categories,
        'daily_revenue': json.dumps(list(daily_revenue)),
        'current_month_name': today.strftime('%B %Y'),
        'total_patients': Patient.objects.count(),
        'total_bills': PatientBill.objects.count(),
        'paid_bills': PatientBill.objects.filter(status='paid').count(),
        'pending_bills': PatientBill.objects.filter(status='pending').count(),
    }
    
    return render(request, 'hms_admin/account_reports.html', context)

def account_report_api(request):
    """API endpoint for dynamic chart data"""
    chart_type = request.GET.get('type', 'revenue')
    period = request.GET.get('period', '30')  # days
    
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=int(period))
    
    if chart_type == 'revenue_trend':
        data = PatientBill.objects.filter(
            created_at__gte=start_date,
            status='paid'
        ).extra(
            select={'day': 'date(created_at)'}
        ).values('day').annotate(
            revenue=Sum('final_amount')
        ).order_by('day')
        
        return JsonResponse({
            'labels': [item['day'].strftime('%Y-%m-%d') for item in data],
            'data': [float(item['revenue']) for item in data]
        })
    
    elif chart_type == 'expense_trend':
        data = Expense.objects.filter(
            expense_date__gte=start_date,
            status='paid'
        ).extra(
            select={'day': 'date(expense_date)'}
        ).values('day').annotate(
            expenses=Sum('amount')
        ).order_by('day')
        
        return JsonResponse({
            'labels': [item['day'].strftime('%Y-%m-%d') for item in data],
            'data': [float(item['expenses']) for item in data]
        })
    
    return JsonResponse({'error': 'Invalid chart type'}, status=400)

@login_required
def hr_report(request):
    """Comprehensive HR Report Dashboard"""
    
    # Get current date and calculate date ranges
    today = timezone.now().date()
    current_month = today.month
    current_year = today.year
    
    # Calculate previous month
    if current_month == 1:
        prev_month = 12
        prev_year = current_year - 1
    else:
        prev_month = current_month - 1
        prev_year = current_year
    
    # Date ranges
    month_start = datetime(current_year, current_month, 1).date()
    month_end = datetime(current_year, current_month, monthrange(current_year, current_month)[1]).date()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)
    
    # STAFF OVERVIEW METRICS
    total_staff = Staff.objects.count()
    active_staff = Staff.objects.filter(user__is_active=True).count()
    inactive_staff = total_staff - active_staff
    
    # Staff by role
    staff_by_role = Staff.objects.values('role').annotate(count=Count('id')).order_by('-count')
    
    # Staff by department
    staff_by_dept = Staff.objects.filter(department__isnull=False).values('department__name').annotate(count=Count('id')).order_by('-count')
    
    # Staff by gender
    staff_by_gender = Staff.objects.values('gender').annotate(count=Count('id'))
    
    # New hires this month
    new_hires_month = Staff.objects.filter(date_joined__gte=month_start, date_joined__lte=month_end).count()
    
    # ATTENDANCE METRICS
    # Today's attendance
    today_attendance = Attendance.objects.filter(date__date=today)
    present_today = today_attendance.filter(status='Present').count()
    absent_today = today_attendance.filter(status='Absent').count()
    on_leave_today = today_attendance.filter(status='On Leave').count()
    
    # Weekly attendance trends
    weekly_attendance = []
    for i in range(7):
        day = week_start + timedelta(days=i)
        day_attendance = Attendance.objects.filter(date__date=day)
        weekly_attendance.append({
            'date': day.strftime('%Y-%m-%d'),
            'day': day.strftime('%a'),
            'present': day_attendance.filter(status='Present').count(),
            'absent': day_attendance.filter(status='Absent').count(),
            'on_leave': day_attendance.filter(status='On Leave').count()
        })
    
    # Monthly attendance summary
    monthly_attendance = Attendance.objects.filter(date__month=current_month, date__year=current_year)
    monthly_present = monthly_attendance.filter(status='Present').count()
    monthly_absent = monthly_attendance.filter(status='Absent').count()
    monthly_on_leave = monthly_attendance.filter(status='On Leave').count()
    
    # Attendance rate calculation
    total_working_days = len([d for d in weekly_attendance if d['present'] + d['absent'] + d['on_leave'] > 0])
    attendance_rate = (present_today / active_staff * 100) if active_staff > 0 else 0
    
    # SHIFT MANAGEMENT
    # Current shift assignments
    current_shifts = ShiftAssignment.objects.filter(date=today).select_related('shift', 'staff')
    shift_distribution = current_shifts.values('shift__name').annotate(count=Count('id'))
    
    # Weekly shift patterns
    weekly_shifts = []
    for i in range(7):
        day = week_start + timedelta(days=i)
        day_shifts = ShiftAssignment.objects.filter(date=day).select_related('shift')
        shift_counts = day_shifts.values('shift__name').annotate(count=Count('id'))
        weekly_shifts.append({
            'date': day.strftime('%Y-%m-%d'),
            'day': day.strftime('%a'),
            'shifts': {shift['shift__name']: shift['count'] for shift in shift_counts}
        })
    
    # STAFF TRANSITIONS
    # Recent onboarding
    recent_onboarding = StaffTransition.objects.filter(
        transition_type='onboarding',
        date__gte=month_start
    ).order_by('-date')[:5]
    
    # Recent offboarding
    recent_offboarding = StaffTransition.objects.filter(
        transition_type='offboarding',
        date__gte=month_start
    ).order_by('-date')[:5]
    
    # Monthly transition trends (last 6 months)
    transition_trends = []
    for i in range(6):
        if current_month - i <= 0:
            month = current_month - i + 12
            year = current_year - 1
        else:
            month = current_month - i
            year = current_year
        
        month_transitions = StaffTransition.objects.filter(date__month=month, date__year=year)
        onboarding_count = month_transitions.filter(transition_type='onboarding').count()
        offboarding_count = month_transitions.filter(transition_type='offboarding').count()
        
        transition_trends.append({
            'month': datetime(year, month, 1).strftime('%b %Y'),
            'onboarding': onboarding_count,
            'offboarding': offboarding_count,
            'net': onboarding_count - offboarding_count
        })
    
    transition_trends.reverse()
    
    # DEPARTMENT ANALYSIS
    dept_analysis = []
    for dept in Department.objects.all():
        dept_staff = Staff.objects.filter(department=dept)
        dept_active = dept_staff.filter(user__is_active=True).count()
        dept_total = dept_staff.count()
        
        # Recent attendance for this department
        dept_attendance = Attendance.objects.filter(
            staff__staff__department=dept,
            date__gte=week_start
        )
        dept_present = dept_attendance.filter(status='Present').count()
        dept_absent = dept_attendance.filter(status='Absent').count()
        
        dept_analysis.append({
            'name': dept.name,
            'total_staff': dept_total,
            'active_staff': dept_active,
            'present_week': dept_present,
            'absent_week': dept_absent,
            'attendance_rate': (dept_present / (dept_present + dept_absent) * 100) if (dept_present + dept_absent) > 0 else 0
        })
    
    # TOP PERFORMERS (by attendance)
    top_performers = []
    for staff in Staff.objects.filter(user__is_active=True)[:10]:
        staff_attendance = Attendance.objects.filter(
            staff=staff.user,
            date__gte=month_start
        )
        present_days = staff_attendance.filter(status='Present').count()
        total_days = staff_attendance.count()
        attendance_rate = (present_days / total_days * 100) if total_days > 0 else 0
        
        top_performers.append({
            'name': f"{staff.user.first_name} {staff.user.last_name}",
            'role': staff.get_role_display(),
            'department': staff.department.name if staff.department else 'N/A',
            'attendance_rate': attendance_rate,
            'present_days': present_days,
            'total_days': total_days
        })
    
    top_performers.sort(key=lambda x: x['attendance_rate'], reverse=True)
    top_performers = top_performers[:10]
    
    # ALERTS AND NOTIFICATIONS
    alerts = []
    
    # Low attendance alert
    if attendance_rate < 80:
        alerts.append({
            'type': 'warning',
            'message': f'Low attendance rate today: {attendance_rate:.1f}%',
            'action': 'Review attendance patterns'
        })
    
    # High absence rate
    if absent_today > active_staff * 0.15:
        alerts.append({
            'type': 'danger',
            'message': f'High absence rate: {absent_today} staff members absent',
            'action': 'Contact absent staff'
        })
    
    # Understaffed departments
    for dept in dept_analysis:
        if dept['attendance_rate'] < 70:
            alerts.append({
                'type': 'warning',
                'message': f'{dept["name"]} department understaffed: {dept["attendance_rate"]:.1f}% attendance',
                'action': 'Review staffing levels'
            })
    
    context = {
        # Overview metrics
        'total_staff': total_staff,
        'active_staff': active_staff,
        'inactive_staff': inactive_staff,
        'new_hires_month': new_hires_month,
        'attendance_rate': round(attendance_rate, 1),
        
        # Today's stats
        'present_today': present_today,
        'absent_today': absent_today,
        'on_leave_today': on_leave_today,
        
        # Charts data
        'staff_by_role': json.dumps(list(staff_by_role)),
        'staff_by_dept': json.dumps(list(staff_by_dept)),
        'staff_by_gender': json.dumps(list(staff_by_gender)),
        'weekly_attendance': json.dumps(weekly_attendance),
        'shift_distribution': json.dumps(list(shift_distribution)),
        'weekly_shifts': json.dumps(weekly_shifts),
        'transition_trends': json.dumps(transition_trends),
        
        # Tables data
        'dept_analysis': dept_analysis,
        'top_performers': top_performers,
        'recent_onboarding': recent_onboarding,
        'recent_offboarding': recent_offboarding,
        'current_shifts': current_shifts,
        
        # Alerts
        'alerts': alerts,
        
        # Date info
        'today': today,
        'current_month': datetime(current_year, current_month, 1).strftime('%B %Y'),
        'week_range': f"{week_start.strftime('%B %d')} - {week_end.strftime('%B %d, %Y')}"
    }
    
    return render(request, 'hms_admin/hr_report.html', context)


# --- Export Helper Functions for Receptionist ---

def _export_receptionist_report_csv(
    patient_info, recent_patients, recent_admissions,
    recent_appointments, recent_referrals, summary,
    registration_labels, registration_data,
    admissions_trend_labels, admissions_trend_data,
    appointments_trend_labels, appointments_trend_data,
    gender_labels, gender_data, age_labels, age_data,
    marital_status_labels, marital_status_data,
    nationality_labels, nationality_data,
    admission_status_labels, admission_status_data,
    appointment_dept_labels, appointment_dept_data,
    referral_dept_labels, referral_dept_data,
):
    response = HttpResponse(content_type='text/csv')
    file_name_suffix = patient_info['full_name'].replace(' ', '_') if patient_info else 'Overall'
    file_name = f"Receptionist_Report_{file_name_suffix}_{timezone.now().strftime('%Y%m%d%H%M')}.csv"
    response['Content-Disposition'] = f'attachment; filename="{file_name}"'

    writer = csv.writer(response)

    writer.writerow([f"Receptionist's Report - Generated: {timezone.now().strftime('%Y-%m-%d %H:%M')}"])
    writer.writerow([])

    if patient_info:
        writer.writerow(["--- Selected Patient Information ---"])
        writer.writerow(["Field", "Value"])
        for key, value in patient_info.items():
            if "photo_url" in key: continue # Exclude photo URL
            writer.writerow([key.replace('_', ' ').title(), value])
        writer.writerow([])

    # Summary
    writer.writerow(["--- Summary Statistics ---"])
    for key, value in summary.items():
        writer.writerow([key.replace('_', ' ').title(), value])
    writer.writerow([])

    # Recent Patients
    if recent_patients:
        writer.writerow(["--- Recent Patient Registrations ---"])
        writer.writerow(["ID", "Full Name", "Gender", "DOB", "Phone", "Email", "Date Registered"])
        for p in recent_patients:
            writer.writerow([
                p.id, p.full_name, p.gender, p.date_of_birth.strftime('%Y-%m-%d'),
                p.phone, p.email, p.date_registered.strftime('%Y-%m-%d %H:%M')
            ])
        writer.writerow([])

    # Recent Admissions
    if recent_admissions:
        writer.writerow(["--- Recent Admissions ---"])
        writer.writerow(["Patient Name", "Admission Date", "Status", "Doctor Assigned", "Discharge Date", "Reason", "Admitted By"])
        for a in recent_admissions:
            writer.writerow([
                a.patient.full_name, a.admission_date.strftime('%Y-%m-%d'), a.get_status_display(),
                a.doctor_assigned_staff.user.get_full_name() if a.doctor_assigned_staff else a.doctor_assigned,
                a.discharge_date.strftime('%Y-%m-%d') if a.discharge_date else 'N/A',
                a.discharge_notes, a.admitted_by
            ])
        writer.writerow([])

    # Recent Appointments
    if recent_appointments:
        writer.writerow(["--- Recent Appointments ---"])
        writer.writerow(["Patient Name", "Department", "Scheduled Time"])
        for appt in recent_appointments:
            writer.writerow([
                appt.patient.full_name, appt.department.name, appt.scheduled_time.strftime('%Y-%m-%d %H:%M')
            ])
        writer.writerow([])

    # Recent Referrals
    if recent_referrals:
        writer.writerow(["--- Recent Referrals ---"])
        writer.writerow(["Patient Name", "Department", "Notes"])
        for r in recent_referrals:
            writer.writerow([
                r.patient.full_name, r.department.name, r.notes
            ])
        writer.writerow([])

    # Chart Data Sections (Raw data for analysis)
    writer.writerow(["--- Patient Registration Trend (Last 6 Months) ---"])
    writer.writerow(["Month", "Registrations"])
    for label, data in zip(registration_labels, registration_data):
        writer.writerow([label, data])
    writer.writerow([])

    writer.writerow(["--- Admissions Trend (Last 6 Months) ---"])
    writer.writerow(["Month", "Admissions"])
    for label, data in zip(admissions_trend_labels, admissions_trend_data):
        writer.writerow([label, data])
    writer.writerow([])
    
    writer.writerow(["--- Appointments Trend (Last 6 Months) ---"])
    writer.writerow(["Month", "Appointments"])
    for label, data in zip(appointments_trend_labels, appointments_trend_data):
        writer.writerow([label, data])
    writer.writerow([])

    writer.writerow(["--- Patient Gender Distribution ---"])
    writer.writerow(["Gender", "Count"])
    for label, data in zip(gender_labels, gender_data):
        writer.writerow([label, data])
    writer.writerow([])

    writer.writerow(["--- Patient Age Group Distribution ---"])
    writer.writerow(["Age Group", "Count"])
    for label, data in zip(age_labels, age_data):
        writer.writerow([label, data])
    writer.writerow([])

    writer.writerow(["--- Patient Marital Status Distribution ---"])
    writer.writerow(["Marital Status", "Count"])
    for label, data in zip(marital_status_labels, marital_status_data):
        writer.writerow([label, data])
    writer.writerow([])

    writer.writerow(["--- Patient Nationality Distribution ---"])
    writer.writerow(["Nationality", "Count"])
    for label, data in zip(nationality_labels, nationality_data):
        writer.writerow([label, data])
    writer.writerow([])

    writer.writerow(["--- Admission Status Distribution ---"])
    writer.writerow(["Status", "Count"])
    for label, data in zip(admission_status_labels, admission_status_data):
        writer.writerow([label, data])
    writer.writerow([])

    writer.writerow(["--- Appointments by Department Distribution ---"])
    writer.writerow(["Department", "Count"])
    for label, data in zip(appointment_dept_labels, appointment_dept_data):
        writer.writerow([label, data])
    writer.writerow([])

    writer.writerow(["--- Referrals by Department Distribution ---"])
    writer.writerow(["Department", "Count"])
    for label, data in zip(referral_dept_labels, referral_dept_data):
        writer.writerow([label, data])
    writer.writerow([])

    return response

def _export_receptionist_report_pdf(
    patient_info, recent_patients, recent_admissions,
    recent_appointments, recent_referrals, summary,
    registration_labels, registration_data,
    admissions_trend_labels, admissions_trend_data,
    appointments_trend_labels, appointments_trend_data,
    gender_labels, gender_data, age_labels, age_data,
    marital_status_labels, marital_status_data,
    nationality_labels, nationality_data,
    admission_status_labels, admission_status_data,
    appointment_dept_labels, appointment_dept_data,
    referral_dept_labels, referral_dept_data,
):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            rightMargin=50, leftMargin=50,
                            topMargin=50, bottomMargin=50)
    styles = getSampleStyleSheet()
    elements = []

    # Title
    elements.append(Paragraph("Receptionist's Activity Report", styles['h1']))
    report_scope = "Overall Activity"
    if patient_info:
        report_scope = f"For Patient: {patient_info['full_name']} (ID: {patient_info['id']})"
    elements.append(Paragraph(report_scope, styles['h2']))
    elements.append(Paragraph(f"Report Generated: {timezone.now().strftime('%Y-%m-%d %H:%M')}", styles['Normal']))
    elements.append(Spacer(1, 12))

    if patient_info:
        # Patient Information Table
        elements.append(Paragraph("Selected Patient Demographics", styles['h3']))
        patient_data_table = [
            ['Field', 'Value'],
            ['Full Name', patient_info['full_name']],
            ['Date of Birth', patient_info['date_of_birth']],
            ['Age', patient_info['age']],
            ['Gender', patient_info['gender']],
            ['Blood Group', patient_info['blood_group']],
            ['Phone', patient_info['phone']],
            ['Email', patient_info['email']],
            ['Address', patient_info['address']],
            ['Marital Status', patient_info['marital_status']],
            ['Nationality', patient_info['nationality']],
            ['ID Type', patient_info['id_type']],
            ['ID Number', patient_info['id_number']],
            ['Current Status', patient_info['status']],
            ['Is Inpatient', 'Yes' if patient_info['is_inpatient'] else 'No'],
            ['Date Registered', patient_info['date_registered']],
            ['Referred By', patient_info['referred_by']],
            ['Next of Kin', patient_info['next_of_kin_name']],
            ['Next of Kin Phone', patient_info['next_of_kin_phone']],
            ['Next of Kin Relationship', patient_info['next_of_kin_relationship']],
        ]
        table_style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#007bff')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('BOX', (0, 0), (-1, -1), 1, colors.black),
        ])
        p_table = Table(patient_data_table, colWidths=[150, 350])
        p_table.setStyle(table_style)
        elements.append(p_table)
        elements.append(Spacer(1, 12))

    # Summary Statistics
    elements.append(Paragraph("Summary Statistics", styles['h3']))
    summary_data = [['Metric', 'Value']]
    for key, value in summary.items():
        summary_data.append([key.replace('_', ' ').title(), value])
    summary_table = Table(summary_data, colWidths=[250, 150])
    summary_table.setStyle(table_style)
    elements.append(summary_table)
    elements.append(Spacer(1, 12))

    # Recent Patient Registrations
    if recent_patients:
        elements.append(Paragraph("Recent Patient Registrations", styles['h3']))
        data = [['ID', 'Full Name', 'Gender', 'DOB', 'Phone', 'Email', 'Date Registered']]
        for p in recent_patients:
            data.append([
                p.id, p.full_name, p.gender, p.date_of_birth.strftime('%Y-%m-%d'),
                p.phone, p.email, p.date_registered.strftime('%Y-%m-%d %H:%M')
            ])
        table = Table(data, colWidths=[40, 90, 50, 60, 60, 80, 80])
        table.setStyle(table_style)
        elements.append(table)
        elements.append(Spacer(1, 12))

    # Recent Admissions
    if recent_admissions:
        elements.append(Paragraph("Recent Admissions", styles['h3']))
        data = [['Patient', 'Adm. Date', 'Status', 'Doctor', 'Disc. Date', 'Reason', 'Admitted By']]
        for a in recent_admissions:
            data.append([
                a.patient.full_name, a.admission_date.strftime('%Y-%m-%d'), a.get_status_display(),
                a.doctor_assigned_staff.user.get_full_name() if a.doctor_assigned_staff else a.doctor_assigned,
                a.discharge_date.strftime('%Y-%m-%d') if a.discharge_date else 'N/A',
                Paragraph(a.discharge_notes or '', styles['Normal']), a.admitted_by
            ])
        table = Table(data, colWidths=[80, 60, 50, 70, 60, 80, 70])
        table.setStyle(table_style)
        elements.append(table)
        elements.append(Spacer(1, 12))

    # Recent Appointments
    if recent_appointments:
        elements.append(Paragraph("Recent Appointments", styles['h3']))
        data = [['Patient', 'Department', 'Scheduled Time']]
        for appt in recent_appointments:
            data.append([
                appt.patient.full_name, appt.department.name, appt.scheduled_time.strftime('%Y-%m-%d %H:%M')
            ])
        table = Table(data, colWidths=[150, 100, 200])
        table.setStyle(table_style)
        elements.append(table)
        elements.append(Spacer(1, 12))

    # Recent Referrals
    if recent_referrals:
        elements.append(Paragraph("Recent Referrals", styles['h3']))
        data = [['Patient', 'Department', 'Notes']]
        for r in recent_referrals:
            data.append([
                r.patient.full_name, r.department.name, Paragraph(r.notes or '', styles['Normal'])
            ])
        table = Table(data, colWidths=[150, 100, 250])
        table.setStyle(table_style)
        elements.append(table)
        elements.append(Spacer(1, 12))

    # Add sections for Chart Data if needed in PDF (as tables)
    # Example: Patient Registration Trend
    if registration_labels and registration_data:
        elements.append(Paragraph("Patient Registration Trend (Last 6 Months)", styles['h3']))
        data = [['Month', 'Registrations']]
        for label, count in zip(registration_labels, registration_data):
            data.append([label, count])
        table = Table(data, colWidths=[250, 250])
        table.setStyle(table_style)
        elements.append(table)
        elements.append(Spacer(1, 12))

    # ... similarly for other chart data if you want them in PDF as tables

    doc.build(elements)
    buffer.seek(0)
    return HttpResponse(buffer, content_type='application/pdf')

#Charts views
def chart_view(request):
    context= { 'labels':['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'],
               'data': [12, 19, 20, 5, 7]}    
    return render(request, 'doctors/chart.html', context)   



def medical_test_selection(request):
    categories = TestCategory.objects.prefetch_related('subcategories').all()
    return render(request, 'requesttest.html', {'categories': categories})

# def submit_test_selection(request):
#     if request.method == 'POST':
#         try:
#             data = json.loads(request.body)
#             patient_id = data.get('patient_id')
#             selections = data.get('selections', [])
#             patient_id1 = int(patient_id)
#             if not patient_id or not selections:
#                 return JsonResponse({'status': 'error', 'message': 'Missing patient or selection data'})
#             patient = Patient.objects.get(id=patient_id1)            
#             for item in selections:
#                 category = item.get('category')
#                 tests = item.get('tests', [])
#                 for test in tests:
#                     category_name = TestCategory.objects.get(name=category)
#                     print(category,  test)
#                     LabTest.objects.create(patient=patient, category=category_name, test_name=test)
                    
#             return JsonResponse({'status': 'success', 'message': 'Selections saved.'})
#         except DatabaseError as e:
#             print("Database error:", str(e))  # Generic DB errors
#     return JsonResponse({'status': 'error', 'message': 'Database error: ' + str(e)})

#graph 2

def chart2(request):
    return render(request, "doctors/graph.html")


"""def admissions_data(request):
    today = timezone.now().date()
    last_week = today - timedelta(days=6)
    
    data = (
        LabTest.objects.filter(submitted_on__range=[last_week, today])
        .values('submitted_on')
        .annotate(count=Count('id'))
        .order_by('submitted_on')
    )
    
    labels = [entry['submitted_on'].strftime('%b %d') for entry in data]
    counts = [entry['count'] for entry in data]
    
    return JsonResponse({'labels': labels, 'counts': counts})    
"""

def admissions_dataold(request):
    today = timezone.now().date()
    last_week = today - timedelta(days=6)

    # All test requests
    all_tests = (
        LabTest.objects.filter(submitted_on__range=[last_week, today])
        .values('submitted_on')
        .annotate(count=Count('id'))
        .order_by('submitted_on')
    )

    # Completed tests (adjust filter condition as needed)
    completed_tests = (
        LabTest.objects.filter(
            submitted_on__range=[last_week, today],
            testcompleted = True  # Change this to your actual model's field/value
        )
        .values('submitted_on')
        .annotate(count=Count('id'))
        .order_by('submitted_on')
    )
    
    print(completed_tests)

    def format_data(queryset):
        return {
            'labels': [entry['submitted_on'].strftime('%b %d') for entry in queryset],
            'counts': [entry['count'] for entry in queryset]
        }

    return JsonResponse({
        'requested': format_data(all_tests),
        'completed': format_data(completed_tests),
    })  

def admissions_data(request):
    today = timezone.now().date()
    last_week = today - timedelta(days=6)

    # All test requests
    all_tests = (
        LabTest.objects.filter(submitted_on__range=[last_week, today])
        .values('submitted_on')
        .annotate(count=Count('id'))
        .order_by('submitted_on')
    )

    # Completed tests (ensure correct field name: testcompleted=True)
    completed_tests = (
        LabTest.objects.filter(
            submitted_on__range=[last_week, today],
            testcompleted=True  # Make sure this field exists and is Boolean
            )
        .values('submitted_on')
        .annotate(count=Count('id'))
        .order_by('submitted_on')
    )

    def format_data(queryset):
        labels = []
        counts = []
        for entry in queryset:
            date_obj = entry['submitted_on']
            if isinstance(date_obj, str):  # just in case it's stringified
                date_obj = timezone.datetime.strptime(date_obj, "%Y-%m-%d").date()
            labels.append(date_obj.strftime('%b %d'))
            counts.append(entry['count'])
        return {'labels': labels, 'counts': counts}

    return JsonResponse({
        'requested': format_data(all_tests),
        'completed': format_data(completed_tests),
    })


#Waiting List

def waitinglist(request):
    today = date.today()
    appointments_today = Appointment.objects.filter(scheduled_time=today)
    test_outstanding = LabTest.objects.filter(testcompleted=True)    
    context = {
        'appointments_today': appointments_today,
        'test_outstanding': test_outstanding,
    }
    return render(request, 'doctors/waitinglist.html', context)






##### Doctor test result view

#Test details and completion by lab






 

 #Doctor's fetching test results that were recommended


from collections import defaultdict
from django.utils import timezone
from django.shortcuts import render, redirect
from django.contrib import messages






def bk2recomended_tests(request):
    if request.method == 'POST':
        test_id = request.POST.get('test_id')
        result_value = request.POST.get('result_value')
        notes = request.POST.get('notes', '')

        try:
            test = LabTest.objects.select_related('patient', 'category').get(id=test_id, status='pending')
            test.result_value = result_value
            test.notes = notes
            test.status = 'completed'
            test.testcompleted = True
            test.date_performed = timezone.now()
            test.performed_by = request.user
            test.save()

            messages.success(request, f"Test {test.test_name} ({test.category.name}) for {test.patient.full_name} completed successfully.")
        except LabTest.DoesNotExist:
            messages.error(request, "Invalid test entry or test already completed.")

        return redirect('lab_test_entry')

    # Fetch all lab tests with related patient and category information
    lab_tests = LabTest.objects.select_related('patient', 'category').order_by('-requested_at')

    # Group tests by status
    tests_by_status = {
        'pending': lab_tests.filter(status='pending'),
        'completed': lab_tests.filter(status='completed', doctor_comments__gt=0),
        'in_progress': lab_tests.filter(status='in_progress')
    }

    # Create a list of all tests (this will include all statuses)
    tests_data = []
    for test in lab_tests:
        tests_data.append({
            'test': test,
            'patient': test.patient,
            'category': test.category,
            'status': test.status,
            'requested_at': test.requested_at,
            'date_performed': test.date_performed,
            'requested_by': test.requested_by.get_full_name() if test.requested_by else 'System',
            'performed_by': test.performed_by.get_full_name() if test.performed_by else 'N/A',
            'doctor_comments': test.doctor_comments  # Add this so we can filter on it
        })

    # Create patient map ONLY for tests that are completed AND have doctor_comments > 0
    patient_map = {}
    for data in tests_data:
        if data['status'] != 'completed' or (data['doctor_comments'] or 0) <= 0:
            continue
        patient_id = data['patient'].id
        if patient_id not in patient_map:
            patient_map[patient_id] = {
                'patient': data['patient'],
                'tests': [],
                'categories': set(),
                'requested_by': data['requested_by']
            }
        patient_map[patient_id]['tests'].append(data['test'])
        if data['category']:
            patient_map[patient_id]['categories'].add(data['category'].name)

    # Statistics
    today = timezone.now().date()
    stats = {
        'total_tests': lab_tests.count(),
        'total_pending_tests': tests_by_status['pending'].count(),
        'total_completed_today': LabTest.objects.filter(status='completed', date_performed__date=today).count(),
        'total_in_progress': tests_by_status['in_progress'].count(),
        'total_categories': TestCategory.objects.count(),
        'unique_patients': Patient.objects.filter(lab_tests__isnull=False).distinct().count(),
    }

    context = {
        'tests_data': tests_data,
        'test_categories': TestCategory.objects.all(),
        'unique_patients_with_tests': patient_map.values(),  # Now only patients with completed tests + comments
        'stats': stats,
        'debug_info': {
            'total_tests_fetched': len(tests_data),
            'test_categories_count': TestCategory.objects.count(),
            'pending_tests_count': tests_by_status['pending'].count(),
            'methods_used': [
                'LabTest.objects.select_related(patient, category)',
                'Patient grouping in view',
                'Status-based filtering with doctor_comments'
            ]
        } if request.user.is_superuser else None
    }

    return render(request, 'doctors/recomended_test.html', context)



def bkrecomended_tests(request):
    if request.method == 'POST':
        test_id = request.POST.get('test_id')
        result_value = request.POST.get('result_value')
        notes = request.POST.get('notes', '')

        try:
            test = LabTest.objects.select_related('patient', 'category').get(id=test_id, status='pending')
            test.result_value = result_value
            test.notes = notes
            test.status = 'completed'
            test.testcompleted = True
            test.date_performed = timezone.now()
            test.performed_by = request.user
            test.save()

            messages.success(request, f"Test {test.test_name} ({test.category.name}) for {test.patient.full_name} completed successfully.")
        except LabTest.DoesNotExist:
            messages.error(request, "Invalid test entry or test already completed.")

        return redirect('lab_test_entry')

    # Fetch all lab tests with related patient and category information
    lab_tests = LabTest.objects.select_related('patient', 'category').order_by('-requested_at')

    # Group tests by status
    tests_by_status = {
        'pending': lab_tests.filter(status='pendin'),
        'completed': lab_tests.filter(status='completed', doctor_comments=0),
        'in_progress': lab_tests.filter(status='in_progress')
    }

    # Create a list of all tests for use if needed
    tests_data = []
    for test in lab_tests:
        tests_data.append({
            'test': test,
            'patient': test.patient,
            'category': test.category,
            'status': test.status,
            'requested_at': test.requested_at,
            'date_performed': test.date_performed,
            'requested_by': test.requested_by.get_full_name() if test.requested_by else 'System',
            'performed_by': test.performed_by.get_full_name() if test.performed_by else 'N/A'
        })

    # Create a unique patient map with pending tests and categories
    patient_map = {}
    for item in tests_data:
        if item['status'] != 'pending':
            continue
        patient_id = item['patient'].id
        if patient_id not in patient_map:
            patient_map[patient_id] = {
                'patient': item['patient'],
                'tests': [],
                'categories': set(),
                'requested_by': item['requested_by']
            }
        patient_map[patient_id]['tests'].append(item['test'])
        if item['category']:
            patient_map[patient_id]['categories'].add(item['category'].name)

    # Statistics
    today = timezone.now().date()
    stats = {
        'total_tests': lab_tests.count(),
        'total_pending_tests': tests_by_status['pending'].count(),
        'total_completed_today': LabTest.objects.filter(status='completed', date_performed__date=today).count(),
        'total_in_progress': tests_by_status['in_progress'].count(),
        'total_categories': TestCategory.objects.count(),
        'unique_patients': Patient.objects.filter(lab_tests__isnull=False).distinct().count(),
    }

    # Group lab tests by patient for template rendering
    patient_map = {}
    for data in tests_data:
        patient_id = data['patient'].id
        if patient_id not in patient_map:
            patient_map[patient_id] = {
            'patient': data['patient'],
            'tests': [],
            'categories': set(),
            'requested_by': data['requested_by']
        }
        if data['status'] == 'completed':
            patient_map[patient_id]['tests'].append(data['test'])
            if data['category']:
                patient_map[patient_id]['categories'].add(data['category'].name)




    context = {
        'tests_data': tests_data,
        'test_categories': TestCategory.objects.all(),
        'unique_patients_with_tests': patient_map.values(),  # send only unique patients with pending tests
        'stats': stats,
        'debug_info': {
            'total_tests_fetched': len(tests_data),
            'test_categories_count': TestCategory.objects.count(),
            'pending_tests_count': tests_by_status['pending'].count(),
            'methods_used': [
                'LabTest.objects.select_related(patient, category)',
                'Patient grouping in view',
                'Status-based filtering'
            ]
        } if request.user.is_superuser else None
    }

    return render(request, 'doctors/recomended_test.html', context)



#=============================
#Doctor submitting comments on final test results
#=============================
from .models import LabTest, DoctorComments, Patient

def doc_test_comment(request, patient_id):
    if request.method == 'POST':
        comment_text = request.POST.get('doctor_comment', '')
        ids = request.POST.getlist('ids')

        if not ids or not comment_text:
            messages.error(request, "You must select tests and enter a comment.")
            return redirect('recomended_tests')

        # Create a new DoctorComments record
        comment_record = DoctorComments.objects.create(
            comments=comment_text,
            date=timezone.now(),
            doctor=request.user,  # or request.user.get_full_name() if applicable
            labtech_name="LabTech Placeholder"  # Replace with actual logic if needed
        )
        # Update each LabTest with the new doctor_comments ID
        LabTest.objects.filter(id__in=ids).update(doctor_comments=comment_record.id)

        messages.success(request, "Doctor's comment added and tests updated successfully.")
        return redirect('recomended_tests')

    # If GET request (optional, show test details or redirect)
    return redirect('recomended_tests')


###############################################################
    #DOCTOR ALL REPORTS AND PATIENT ACTIVITIES GENERATED
###############################################################
from reportlab.pdfgen import canvas
from datetime import datetime
from django.core.paginator import Paginator

import csv
from reportlab.pdfgen import canvas
import io



def export_to_csv(lab_tests, doctor_comments, vitals, payments):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="patient_activity.csv"'
    writer = csv.writer(response)
    writer.writerow(['Lab Test', 'Doctor Comment', 'Vital Sign', 'Payment'])

    max_len = max(len(lab_tests), len(doctor_comments), len(vitals), len(payments))
    for i in range(max_len):
        row = [
            getattr(lab_tests[i], 'test_name', '') if i < len(lab_tests) else '',
            getattr(doctor_comments[i], 'comment', '') if i < len(doctor_comments) else '',
            getattr(vitals[i], 'temperature', '') if i < len(vitals) else '',
            getattr(payments[i], 'amount', '') if i < len(payments) else '',
        ]
        writer.writerow(row)

    return response

def export_to_pdf(lab_tests, doctor_comments, vitals, payments):
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer)
    p.drawString(100, 800, "Patient Activity Report")

    y = 780
    for test in lab_tests:
        p.drawString(100, y, f"Lab Test: {test.test_name}")
        y -= 20
    p.showPage()
    p.save()

    buffer.seek(0)
    return HttpResponse(buffer, content_type='application/pdf')

def filter_activities(request):
    patients = Patient.objects.all()
    context = {'patients': patients}

    patient_id = request.GET.get('patient_id')
    date_filter = request.GET.get('dateFilter')
    start_date = request.GET.get('startDate')
    end_date = request.GET.get('endDate')
    export_type = request.GET.get('export')  # 'csv' or 'pdf'

    if patient_id:
        patient = Patient.objects.get(id=patient_id)
        context['selected_patient'] = patient

        if date_filter == 'between' and start_date and end_date:
            start = datetime.strptime(start_date, "%Y-%m-%d")
            end = datetime.strptime(end_date, "%Y-%m-%d")
            labtests = LabTest.objects.filter(patient=patient, created__range=(start, end))
            comments = DoctorComments.objects.filter(patient=patient, created__range=(start, end))
            vitals = Vitals.objects.filter(patient=patient, created__range=(start, end))
            payments = Payment.objects.filter(patient=patient, created__range=(start, end))
        else:
            labtests = LabTest.objects.filter(patient=patient)
            comments = DoctorComments.objects.filter(patient=patient)
            vitals = Vitals.objects.filter(patient=patient)
            payments = Payment.objects.filter(patient=patient)

        context.update({
            'labtests': labtests,
            'comments': comments,
            'vitals': vitals,
            'payments': payments
        })

        # Export CSV
        if export_type == 'csv':
            return export_to_csv(patient, labtests, comments, vitals, payments)

        # Export PDF
        if export_type == 'pdf':
            return export_to_pdf(patient, labtests, comments, vitals, payments)

    return render(request, 'doctors/filtered_records.html', context)