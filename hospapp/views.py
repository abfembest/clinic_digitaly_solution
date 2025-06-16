from multiprocessing import context
from django.contrib import messages
from django.contrib.auth.models import User
from django.shortcuts import render, redirect, get_object_or_404, HttpResponse
from .models import Patient, Staff, Admission, Vitals, NursingNote, Consultation, Prescription, CarePlan, LabTest, LabResultFile, Department, TestCategory, ShiftAssignment, Attendance, Shift, StaffTransition, TestSubcategory, Payment, PatientBill, Budget, Expense, HandoverLog, ExpenseCategory, EmergencyAlert
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
from .models import Patient, Appointment, Referral
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.http import JsonResponse
from django.utils.dateparse import parse_date
from django.db.models import Q
from django.views.decorators.http import require_GET
from django.shortcuts import get_object_or_404, render
import json
from datetime import datetime, date
from django.db.models import Sum
from django.utils.timezone import localdate, now
from django.utils import timezone
from django.db.models.functions import TruncDate
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

    # ✅ Get nurse profile
    nurse_profile = Staff.objects.filter(user=user, role='nurse').first()

    # ✅ Dashboard stats
    active_patients = Patient.objects.filter(is_inpatient=True).count()
    critical_patients = Patient.objects.filter(status='critical').count()
    stable_patients = Patient.objects.filter(status='stable').count()
    recovered_patients = Patient.objects.filter(status='recovered').count()
    todays_admissions = Admission.objects.filter(admission_date=now().date()).count()

    # ✅ Recent activities
    recent_notes = NursingNote.objects.select_related('patient').order_by('-note_datetime')[:5]

    # ✅ Action shortcuts
    quick_actions = [
        {
            'title': 'Admit New Patient',
            'url': reverse('nursing_actions'),
            'icon': 'fa-user-plus',
            'color': 'success',
            'description': 'Register and admit new patients'
        },
        {
            'title': 'Record Vitals',
            'url': reverse('vitals'),
            'icon': 'fa-heartbeat',
            'color': 'warning',
            'description': 'Monitor and record vital signs'
        },
        {
            'title': 'Prep for Consultation',
            'url': reverse('nursing_actions') + '#monitor',
            'icon': 'fa-stethoscope',
            'color': 'primary',
            'description': 'Prepare patients for doctor visits'
        },
        {
            'title': 'Discharge Patient',
            'url': reverse('nursing_actions') + '#discharge',
            'icon': 'fa-door-open',
            'color': 'danger',
            'description': 'Process patient discharge'
        },
        {
            'title': 'Monitor Patient Status',
            'url': reverse('nursing_actions') + '#monitor',
            'icon': 'fa-chart-line',
            'color': 'dark',
            'description': 'Update and monitor condition'
        },
        {
            'title': 'Write Nursing Note',
            'url': reverse('nursing_actions') + '#nursing_note',
            'icon': 'fa-notes-medical',
            'color': 'info',
            'description': 'Document observations and updates'
        },
    ]

    context = {
        'nurse_profile': nurse_profile,
        'active_patients': active_patients,
        'critical_patients': critical_patients,
        'stable_patients': stable_patients,
        'recovered_patients': recovered_patients,
        'recent_notes': recent_notes,
        'todays_admissions': todays_admissions,
        'quick_actions': quick_actions,
    }

    return render(request, 'nurses/index.html', context)

@login_required(login_url='home')
def nursing_actions(request):
    context = {
        'patients': Patient.objects.all(),
        'admitted_patients': Patient.objects.filter(is_inpatient=True),
        'doctors': Staff.objects.select_related('user').filter(Q(role='doctor')),
        'nurses': Staff.objects.select_related('user').filter(Q(role='nurse')),
        'departments': Department.objects.all(),
    }
    return render(request, 'nurses/nursing_actions.html', context)


@csrf_exempt
@login_required(login_url='home')
def admit_patient_nurse(request):
    if request.method == 'POST':
        patient_id = request.POST.get('patient_id')
        doctor = request.POST.get('doctor')
        admission_reason = request.POST.get('admission_reason')

        # Validate patient_id
        if not patient_id or patient_id.strip() == '':
            messages.error(request, "Please select a patient to admit.")
            return redirect('nursing_actions')

        try:
            patient = get_object_or_404(Patient, id=int(patient_id))
        except (ValueError, TypeError):
            messages.error(request, "Invalid patient selection.")
            return redirect('nursing_actions')

        if Admission.objects.filter(patient=patient, status='Admitted').exists():
            messages.warning(request, f"{patient.full_name} is already admitted.")
            return redirect('nursing_actions')

        # Store admission details in the notes field since the model lacks specific fields
        admission_details = f"Reason for Admission: {admission_reason}"

        Admission.objects.create(
            patient=patient,
            admission_date=timezone.now().date(),
            doctor_assigned=doctor,
            status='Admitted',
            admitted_by=request.user.get_full_name() or request.user.username,
            discharge_notes=admission_details
        )

        patient.is_inpatient = True
        patient.save()

        messages.success(request, f"{patient.full_name} admitted successfully.")
        return redirect('nursing_actions')

    return redirect('nursing_actions')


@csrf_exempt
@login_required(login_url='home')
def discharge_patient(request):
    if request.method == 'POST':
        patient_id = request.POST.get('patient_id')
        summary = request.POST.get('discharge_summary')
        followup_date = request.POST.get('followup_date')
        followup_doctor = request.POST.get('followup_doctor')

        # Validate patient_id
        if not patient_id or patient_id.strip() == '':
            messages.error(request, "Please select a patient to discharge.")
            return redirect('nursing_actions')

        try:
            patient = get_object_or_404(Patient, id=int(patient_id))
        except (ValueError, TypeError):
            messages.error(request, "Invalid patient selection.")
            return redirect('nursing_actions')
        
        admission = Admission.objects.filter(patient=patient, status='Admitted').first()
        if not admission:
            messages.error(request, "No active admission found for this patient.")
            return redirect('nursing_actions')
        
        # Combine all discharge info into the notes field
        full_summary = f"Discharge Summary:\n{summary}"
        if followup_date:
            full_summary += f"\n\nFollow-up Date: {followup_date}"
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
        admission.discharged_by = request.user.get_full_name() or request.user.username
        admission.save()

        messages.success(request, f"{patient.full_name} has been discharged successfully.")
        return redirect('nursing_actions')

    return redirect('nursing_actions')


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


@csrf_exempt
@login_required(login_url='home')
def refer_patient(request):
    if request.method == 'POST':
        patient_id = request.POST.get('patient_id')
        department_id = request.POST.get('department') #
        notes = request.POST.get('notes') #
        priority = request.POST.get('priority') #
        
        patient = get_object_or_404(Patient, id=patient_id)
        department = get_object_or_404(Department, id=department_id)

        # Prepend priority to notes since there's no dedicated field in the model
        referral_notes = f"PRIORITY: {priority.upper()}\n\n{notes}"

        Referral.objects.create(
            patient=patient,
            department=department, #
            notes=referral_notes #
        )

        messages.success(request, f"{patient.full_name} has been referred to {department.name}.")
        return redirect('nursing_actions')

    return redirect('nursing_actions')

@csrf_exempt
@login_required(login_url='home')
def save_nursing_note(request):  # Make sure this matches your URL name
    if request.method == 'POST':
        patient_id = request.POST.get('patient_id')
        
        # Validate patient_id
        if not patient_id or patient_id.strip() == '':
            messages.error(request, "Please select a patient to add nursing notes.")
            return redirect('nursing_actions')

        try:
            patient = get_object_or_404(Patient, id=int(patient_id))
        except (ValueError, TypeError):
            messages.error(request, "Invalid patient selection.")
            return redirect('nursing_actions')

        NursingNote.objects.create(
            patient=patient,
            note_type=request.POST.get('note_type'),
            notes=request.POST.get('notes'),
            follow_up=request.POST.get('follow_up'),
            nurse=request.user.get_full_name() or request.user.username,
            note_datetime=timezone.now()
        )
        messages.success(request, "Nursing note saved successfully.")
        return redirect('nursing_actions')

    return redirect('nursing_actions')

@csrf_exempt
@login_required(login_url='home')
def handover_log(request):
    if request.method == 'POST':
        patient_id = request.POST.get('patient_id')
        handover_to = request.POST.get('handover_to') #
        shift = request.POST.get('shift') #
        notes = request.POST.get('notes') #
        
        patient = get_object_or_404(Patient, id=patient_id)

        # Combine handover details into the main notes field
        handover_details = f"Handover To: {handover_to}\nShift: {shift.title()}\n\n{notes}"

        HandoverLog.objects.create(
            patient=patient,
            notes=handover_details, #
            author=request.user #
        )

        messages.success(request, f"Handover for {patient.full_name} has been logged.")
        return redirect('nursing_actions')

    return redirect('nursing_actions')

@csrf_exempt
@login_required(login_url='home')
def get_patient_details(request, patient_id):
    try:
        patient = Patient.objects.get(id=patient_id)

        vitals = list(Vitals.objects.filter(patient=patient).order_by('-recorded_at')[:5].values(
            'temperature', 'blood_pressure', 'pulse', 'recorded_at'
        ))

        prescriptions = list(Prescription.objects.filter(patient=patient).order_by('-created_at')[:5].values(
            'medication', 'instructions', 'start_date'
        ))

        _ts = list(LabTest.objects.filter(patient=patient).order_by('-requested_at')[:5].values(
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
            'notes': patient.notes,
            'photo_url': patient.photo.url if patient.photo else None,
            'vitals': vitals,
            'prescriptions': prescriptions,
            # 'lab_tests': lab_tests,
            'care_plan': care_plan_data,
            'nursing_notes': nursing_notes,
        })

    except Patient.DoesNotExist:
        return JsonResponse({'error': 'Patient not found'}, status=404)

@login_required(login_url='home')                          
def vitals(request):
    context = {
        'patients': Patient.objects.all(),
    }
    return render(request, 'nurses/vital_signs.html', context)

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
                recorded_by=request.user.username
            )
            messages.success(request, "Vitals recorded successfully.")
        except Exception as e:
            messages.error(request, f"Error recording vitals: {str(e)}")
    return redirect('vitals')

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
                'blood_pressure': vital.blood_pressure,
                'temperature': vital.temperature,
                'pulse': vital.pulse,
                'respiratory_rate': vital.respiratory_rate,
                'weight': vital.weight,
                'height': vital.height,
                'bmi': vital.bmi,
                'notes': vital.notes,
                'recorded_by': vital.recorded_by
            })
        
        # Get recent nursing notes
        nursing_notes = patient.nursing_notes.order_by('-note_datetime')[:5]
        nursing_notes_data = []
        for note in nursing_notes:
            nursing_notes_data.append({
                'note_datetime_formatted': note.note_datetime.strftime('%Y-%m-%d %H:%M'),
                'note_type_display': note.get_note_type_display(),
                'notes': note.notes,
                'patient_status': note.patient_status,
                'nurse': note.nurse,
                'follow_up': note.follow_up
            })
        
        # Get recent admissions
        admissions = patient.admission_set.order_by('-admission_date')[:3]
        admissions_data = []
        for admission in admissions:
            admissions_data.append({
                'admission_date_formatted': admission.admission_date.strftime('%Y-%m-%d'),
                'doctor_assigned': admission.doctor_assigned,
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
        return JsonResponse({'error': str(e)}, status=500)


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

@login_required(login_url='home')
def monitoring(request):
    patient_id = request.GET.get("patient_id")
    patient = Patient.objects.filter(id=patient_id).first() if patient_id else None

    context = {
        "all_patients": Patient.objects.all(),
        "patient": patient,
        "consultations": patient.consultations.all() if patient else [],
        "prescriptions": patient.prescriptions.all() if patient else [],
        "vitals": patient.vitals_set.all() if patient else [],
        "notes": patient.nursing_notes.all() if patient else [],
        "careplans": patient.careplan_set.all() if patient else [],
        "admissions": patient.admission_set.all() if patient else [],
    }
    return render(request, "doctors/treatment_monitoring.html", context)

''' ############################################################################################################################ End Doctors View ############################################################################################################################ '''

@login_required(login_url='home')                          
def ae(request):     
    return render(request, 'ae/base.html')

# Lab views
@login_required(login_url='home')
def laboratory(request):
    # Get current date for filtering
    today = date.today()
    start_of_day = timezone.make_aware(datetime.combine(today, datetime.min.time()))
    end_of_day = timezone.make_aware(datetime.combine(today, datetime.max.time()))

    # --- Dashboard Counts ---
    # Tests completed/performed today
    test_today = LabTest.objects.filter(
        date_performed__range=(start_of_day, end_of_day),
        status='completed' # Assuming 'date_performed' is set upon completion
    ).count()

    # Pending Tests Count (overall)
    pending_count = LabTest.objects.filter(status='pending').count()

    # Completed Tests Count (overall)
    completed_count = LabTest.objects.filter(status='completed').count()

    # In Progress Tests Count (overall) - Used for the donut chart
    in_progress_count = LabTest.objects.filter(status='in_progress').count()

    # Total Patients Count
    total_patients_count = Patient.objects.count()

    # Total Uploaded Results Files Count
    uploaded_results_count = LabResultFile.objects.count()

    # --- Data for Today's Test Status Table (Latest 5 tests requested today) ---
    today_tests_details = LabTest.objects.filter(
        requested_at__range=(start_of_day, end_of_day)
    ).select_related('patient', 'category').order_by('-requested_at')[:5] # Limit to 5 for dashboard snippet

    # --- Data for Awaiting Tests (Pending Tests List) ---
    awaiting_tests = LabTest.objects.filter(status='pending').select_related('patient', 'category').order_by('-requested_at')[:8] # Limit for quick view

    # --- Data for Weekly Lab Activity Chart (Last 7 days) ---
    weekly_labels = [] # e.g., ['Mon', 'Tue', 'Wed', ...]
    weekly_tests_data_total = [0] * 7 # Total tests performed each day
    weekly_tests_data_completed = [0] * 7 # Completed tests each day

    for i in range(7):
        day = today - timedelta(days=6 - i) # Calculate date for each of the last 7 days
        weekly_labels.append(day.strftime('%a')) # Format day name (e.g., 'Mon')

        day_start = timezone.make_aware(datetime.combine(day, datetime.min.time()))
        day_end = timezone.make_aware(datetime.combine(day, datetime.max.time()))

        total_on_day = LabTest.objects.filter(
            date_performed__range=(day_start, day_end)
        ).count()
        completed_on_day = LabTest.objects.filter(
            status='completed',
            date_performed__range=(day_start, day_end)
        ).count()

        weekly_tests_data_total[i] = total_on_day
        weekly_tests_data_completed[i] = completed_on_day

    # --- Recent Activity (Timeline) ---
    # Fetch recent LabTests to populate the timeline. You can extend this to include other activities.
    recent_activities = []
    recent_lab_tests = LabTest.objects.all().select_related('patient').order_by('-requested_at')[:5] # Get top 5 recent tests

    for test in recent_lab_tests:
        if test.status == 'completed':
            icon_class = 'fas fa-vial'
            bg_color = 'bg-primary'
            header_text = f"{test.test_name} completed"
            body_text = f"Patient {test.patient.full_name} - All parameters within normal range."
            # Assuming a detail URL for a completed test
            link_url = "" # Replace with actual URL for test details if available
        elif test.status == 'pending':
            icon_class = 'fas fa-clock'
            bg_color = 'bg-warning'
            header_text = f"{test.test_name} Pending"
            body_text = f"Patient {test.patient.full_name} - Awaiting processing."
            # Assuming a process URL for pending test
            link_url = "" # Replace with actual URL to process test if available
        else: # For 'in_progress' or 'cancelled'
            icon_class = 'fas fa-hourglass-half'
            bg_color = 'bg-info'
            header_text = f"{test.test_name} in progress"
            body_text = f"Patient {test.patient.full_name} - Currently being processed."
            link_url = ""

        recent_activities.append({
            'timestamp': test.requested_at,
            'icon': icon_class,
            'bg_color': bg_color,
            'header': header_text,
            'body': body_text,
            'link': link_url
        })
    
    # Sort by timestamp in descending order (most recent first)
    recent_activities.sort(key=lambda x: x['timestamp'], reverse=True)


    context = {
        'test_today': test_today,
        'pending_count': pending_count,
        'completed_count': completed_count,
        'in_progress_count': in_progress_count,
        'total_patients_count': total_patients_count,
        'uploaded_results_count': uploaded_results_count,

        'today_tests_details': today_tests_details,
        'awaiting_tests': awaiting_tests,

        'weekly_labels': weekly_labels,
        'weekly_tests_data_total': weekly_tests_data_total,
        'weekly_tests_data_completed': weekly_tests_data_completed,
        'recent_activities': recent_activities,

        # URLs for navigation - these should match your urls.py names
        'dashboard_url': 'laboratory', # The name of this current view
        'pending_tests_url': 'lab_internal_logs', # Used for 'View Pending Tests' link
        'test_logs_url': 'lab_internal_logs', # Used for 'View Details' and 'View Logs' links
        'lab_test_entry_url': 'lab_test_entry', # Used for 'Enter New Test' link
        'logout_url': 'logout', # Standard Django logout URL name
    }
    return render(request, 'laboratory/index.html', context)

@login_required(login_url='home')
def lab_test_entry(request):
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

    # Filter lab tests strictly by status='pending' and doctor_comments=0
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

@login_required(login_url='home')
def lab_internal_logs(request):
    user = request.user

    # Fetch all lab tests, with related patient and user to optimize queries
    lab_tests = LabTest.objects.select_related('patient', 'recorded_by', 'performed_by').order_by('-date_performed')

    logs = []
    for test in lab_tests:
        # Gather key results dynamically from LabTestField related objects
        fields = test.fields.all()

        # Compose a summary string of all fields for display
        key_results = ', '.join([f"{field.name}: {field.value}" for field in fields]) or "N/A"

        logs.append({
            'id': test.id,
            'date': test.date_performed.date(),
            'patient_name': test.patient.full_name,
            'test_type': test.test_type.name,
            'lab_staff': test.recorded_by.get_full_name() if test.recorded_by else "Unknown",
            'key_results': key_results,
            'notes': getattr(test, 'notes', ''),
            'status': 'Completed',
        })

    context = {
        'lab_logs': logs,
    }
    return render(request, 'laboratory/logs.html', context)

def lab_log_detail_ajax(request):
    log_id = request.GET.get('log_id')
    if not log_id:
        return JsonResponse({"error": "Missing log ID"}, status=400)

    try:
        lab_test = get_object_or_404(LabTest, id=log_id)

        data = {
            'patient': lab_test.patient.full_name,
            'test_type': lab_test.test_type.name,
            'date': lab_test.date_recorded.strftime('%B %d, %Y'),
            'recorded_by': lab_test.recorded_by.get_full_name() if lab_test.recorded_by else "Unknown",
            'notes': getattr(lab_test, 'notes', ''),
            'fields': []
        }

        # Add all test fields dynamically
        for field in lab_test.fields.all():
            data['fields'].append({
                'name': field.name,
                'value': field.value,
            })

        return JsonResponse(data)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


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

# Acoounts Views
@login_required(login_url='home')
def accounts(request):
    # Core stats
    total_revenue = Payment.objects.filter(status='completed').aggregate(total=Sum('amount'))['total'] or 0
    start_month = datetime.today().replace(day=1)
    monthly_income = Payment.objects.filter(status='completed', payment_date__gte=start_month)\
                                    .aggregate(total=Sum('amount'))['total'] or 0
    
    # Pending payments total amount (not just count)
    pending_payments = Payment.objects.filter(status='pending').aggregate(total=Sum('amount'))['total'] or 0
    pending_payments_count = Payment.objects.filter(status='pending').count()
    
    # Outstanding balance from unpaid bills
    outstanding_balance = sum(bill.outstanding_amount() for bill in 
                              PatientBill.objects.exclude(status='paid'))

    # Charts (past 6 months revenue/expense)
    last6 = [datetime.today().replace(day=1) - relativedelta(months=i) for i in reversed(range(6))]
    labels, income, expenses = [], [], []
    
    for dt in last6:
        month_end = (dt + timedelta(days=32)).replace(day=1)
        month_name = dt.strftime('%B')
        labels.append(month_name)
        
        # Monthly income
        month_income = Payment.objects.filter(
            status='completed',
            payment_date__date__gte=dt.date(),
            payment_date__date__lt=month_end.date()
        ).aggregate(sum=Sum('amount'))['sum'] or 0
        income.append(float(month_income))
        
        # Monthly expenses (if you have an Expense model, otherwise use placeholder)
        # Replace this with actual expense calculation if you have expense tracking
        month_expenses = Expense.objects.filter(
            status='paid',
            expense_date__gte=dt.date(),
            expense_date__lt=month_end.date()
        ).aggregate(total=Sum('amount'))['total'] or 0
  # Placeholder: 40% of income as expenses
        expenses.append(float(month_expenses))

    # Payment status chart values
    paid_count = Payment.objects.filter(status='completed').count()
    pending_count = Payment.objects.filter(status='pending').count()
    
    # Overdue payments (assuming you have a way to identify overdue payments)
    # This is a placeholder - adjust based on your actual overdue logic
    overdue_count = PatientBill.objects.filter(
        status__in=['unpaid', 'partial'],
        due_date__lt=datetime.today().date()
    ).count() if hasattr(PatientBill, 'due_date') else 0
    
    # Calculate percentages for pie chart
    total_payments = paid_count + pending_count + overdue_count
    if total_payments > 0:
        paid_percentage = round((paid_count / total_payments) * 100, 1)
        pending_percentage = round((pending_count / total_payments) * 100, 1)
        overdue_percentage = round((overdue_count / total_payments) * 100, 1)
    else:
        paid_percentage = pending_percentage = overdue_percentage = 0

    # Recent transactions with better formatting
    recent_transactions = Payment.objects.select_related('patient')\
                            .filter(status__in=['completed', 'pending'])\
                            .order_by('-payment_date')[:5]

    # Budget data (if you have Budget model)
    try:
        budgets = Budget.objects.order_by('-created_at')[:3]
    except:
        budgets = []

    context = {
        'total_revenue': total_revenue,
        'monthly_income': monthly_income,
        'pending_payments': pending_payments,  # Amount, not count
        'pending_payments_count': pending_payments_count,
        'outstanding_balance': outstanding_balance,
        'recent_transactions': recent_transactions,
        'budgets': budgets,
        
        # Chart data for JavaScript (properly formatted)
        'revenue_labels': json.dumps(labels),
        'revenue_income': json.dumps(income),
        'revenue_expenses': json.dumps(expenses),
        
        'payment_status_labels': json.dumps(['Paid', 'Pending', 'Overdue']),
        'payment_status_values': json.dumps([paid_percentage, pending_percentage, overdue_percentage]),
        
        # Raw counts for display
        'paid_count': paid_count,
        'pending_count': pending_count,
        'overdue_count': overdue_count,
    }
    
    return render(request, 'accounts/index.html', context)

@login_required(login_url='home')
def patient_payment_tracker(request):
    return render(request, 'accounts/payment_tracker.html')

# @login_required(login_url='home')
# def institution_financials(request):
#     return render(request, 'accounts/financials.html')

# @login_required(login_url='home')
# def financial_reports(request):
#     return render(request, 'accounts/financial_reports.html')

# @login_required(login_url='home')
# def budget_planning(request):
#     return render(request, 'accounts/planning.html')

''' ############################################################################################################################ HR View ############################################################################################################################ '''

@login_required(login_url='home')
def hr(request):
    """
    Comprehensive HR Dashboard with real data from models
    """
    # Get current date info
    today = timezone.now().date()
    current_month_start = today.replace(day=1)
    week_ago = today - timedelta(days=7)
    
    # === BASIC STAFF METRICS ===
    total_staff = Staff.objects.count()
    total_departments = Department.objects.count()
    
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
    shift_distribution = Shift.objects.annotate(
        count=Count('shiftassignment__id', filter=Q(shiftassignment__date=today))
    ).values('name', 'count')
    
    # === DEPARTMENT STATISTICS ===
    department_stats = []
    colors = ['#007bff', '#28a745', '#ffc107', '#dc3545', '#6f42c1', '#fd7e14', '#20c997', '#6c757d']
    
    dept_data = Department.objects.annotate(
        staff_count=Count('staff')
    ).values('name', 'staff_count')
    
    for idx, dept in enumerate(dept_data):
        department_stats.append({
            'name': dept['name'],
            'count': dept['staff_count'],
            'color': colors[idx % len(colors)]
        })
    
    # === ROLE DISTRIBUTION ===
    role_distribution = Staff.objects.values('role').annotate(
        count=Count('id')
    ).order_by('-count')

    # Add display name manually
    role_display_map = dict(Staff.ROLE_CHOICES)
    for role in role_distribution:
        role['role_display'] = role_display_map.get(role['role'], role['role'])
    
    # === WEEKLY ATTENDANCE TRENDS ===
    # Get last 7 days of attendance data
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
    # Calculate some HR-specific metrics for alerts
    pending_tasks_count = 0  # You can implement this based on your workflow
    expiring_certs_count = 0  # You can implement certification expiry logic
    
    # If you have a certification model, uncomment and modify:
    # from datetime import timedelta
    # thirty_days_from_now = today + timedelta(days=30)
    # expiring_certs_count = StaffCertification.objects.filter(
    #     expiry_date__lte=thirty_days_from_now,
    #     expiry_date__gte=today
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
def staff_attendance(request):
    today = timezone.localdate()

    try:
        profile = request.user.staff
    except Staff.DoesNotExist:
        messages.error(request, "Your user profile is not set up properly.")
        return redirect('home')

    staff_users = User.objects.filter(staff__isnull=False).order_by('first_name', 'last_name')
    shifts = Shift.objects.all().order_by('name')

    if request.method == 'POST':
        if 'record_attendance' in request.POST:
            staff_id = request.POST.get('staff_name')
            date_input = request.POST.get('date') or today
            date_obj = parse_date_to_datetime(date_input)
            status = request.POST.get('status')

            try:
                staff_user = staff_users.get(id=staff_id)
            except User.DoesNotExist:
                messages.error(request, "Selected staff not found.")
                return redirect('staff_attendance_shift')

            Attendance.objects.update_or_create(
                staff=staff_user,
                date=date_obj,
                defaults={'status': status}
            )
            messages.success(request, "Attendance recorded successfully.")
            return redirect('staff_attendance_shift')

        elif 'assign_shift' in request.POST:
            staff_id = request.POST.get('staff_name')
            shift_name = request.POST.get('shift')
            date_input = request.POST.get('date') or today
            date_obj = parse_date_to_datetime(date_input)

            try:
                staff_user = staff_users.get(id=staff_id)
            except User.DoesNotExist:
                messages.error(request, "Selected staff not found.")
                return redirect('staff_attendance_shift')

            try:
                shift = shifts.get(name=shift_name)
                print(shift)
            except Shift.DoesNotExist:
                messages.error(request, f"Shift '{shift_name}' not found.")
                return redirect('staff_attendance_shift')

            ShiftAssignment.objects.update_or_create(
                staff=staff_user,
                date=date_obj.date(),
                defaults={'shift': shift}
            )
            messages.success(request, "Shift assigned successfully.")
            return redirect('staff_attendance_shift')

    attendance_records = Attendance.objects.select_related('staff').order_by('-date')
    shift_records = ShiftAssignment.objects.select_related('staff', 'shift').order_by('-date')

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
def staff_certifications(request):
    return render(request, 'hr/certifications.html')

''' ############################################################################################################################ End HR View ############################################################################################################################ '''

@login_required(login_url='home')             
def inventory(request):
    return render(request, 'inventory/base.html')

# HMS Admin Views
@login_required(login_url='home')
def hms_admin(request):
    """
    Renders the Admin Dashboard with dynamic data.

    Fetches key metrics from the database related to:
    - Staff (active, by role)
    - Patients (total, admitted, new registrations)
    - Lab Tests (pending)
    - Financials (pending bills, monthly revenue, monthly expenses)
    - Appointments (recent)

    The data is then passed to the 'hms_admin/index.html' template
    to display a dynamic and informative dashboard.
    """
    
    # Ensure only 'admin' role can access this dashboard
    if not hasattr(request.user, 'staff') or request.user.staff.role != 'admin':
        # Redirect to a generic home or unauthorized page, or show an error
        # For now, let's redirect to a general home page
        return redirect('home') # Assuming 'home' is a general entry point

    current_month = date.today().month
    current_year = date.today().year
    
    # 1. Staff Statistics
    staff_active_count = Staff.objects.filter(user__is_active=True).count()
    total_doctors = Staff.objects.filter(role='doctor', user__is_active=True).count()
    total_nurses = Staff.objects.filter(role='nurse', user__is_active=True).count()
    total_lab_techs = Staff.objects.filter(role='lab', user__is_active=True).count()
    
    # 2. Patient Statistics
    total_patients = Patient.objects.count()
    patients_admitted = Admission.objects.filter(status='Admitted').count()
    
    # Calculate new patient registrations for the last 30 days
    thirty_days_ago = timezone.now() - timedelta(days=30)
    new_patients_last_30_days = Patient.objects.filter(date_registered__gte=thirty_days_ago).count()

    # 3. Lab & Appointments
    pending_lab_tests = LabTest.objects.filter(status='pending').count()
    upcoming_appointments_today = Appointment.objects.filter(
        scheduled_time__date=date.today()
    ).count()

    # 4. Financials
    pending_bills = PatientBill.objects.filter(status='pending').count()
    
    # Monthly Revenue
    monthly_revenue = Payment.objects.filter(
        status='completed',
        payment_date__year=current_year,
        payment_date__month=current_month
    ).aggregate(total_amount=Sum('amount'))['total_amount'] or 0.00

    # Monthly Expenses
    monthly_expenses = Expense.objects.filter(
        status='approved',
        expense_date__year=current_year,
        expense_date__month=current_month
    ).aggregate(total_amount=Sum('amount'))['total_amount'] or 0.00

    # Recent Data for Lists/Tables
    # Fetch top 5 recently registered patients
    recent_patients = Patient.objects.order_by('-date_registered')[:5]
    
    # Fetch top 5 upcoming appointments
    recent_appointments = Appointment.objects.filter(
        scheduled_time__gte=timezone.now()
    ).order_by('scheduled_time')[:5]

    # Data for Charts (e.g., monthly patient registrations)
    # This is an example; you might need to adjust based on specific chart requirements
    # For a sales chart, you might aggregate payments by month.
    
    # Example: Monthly patient registrations for the last 6 months
    monthly_registrations = {}
    for i in range(6):
        month = (current_month - i - 1 + 12) % 12 + 1 # Handles year rollover
        year = current_year if (current_month - i) > 0 else current_year - 1
        
        count = Patient.objects.filter(
            date_registered__year=year,
            date_registered__month=month
        ).count()
        monthly_registrations[f"{month}/{year}"] = count

    # Reverse the order for chart display
    monthly_registrations_labels = list(monthly_registrations.keys())[::-1]
    monthly_registrations_data = list(monthly_registrations.values())[::-1]


    context = {
        # Overview Stats
        'staff_active_count': staff_active_count,
        'total_patients': total_patients,
        'patients_admitted': patients_admitted,
        'pending_lab_tests': pending_lab_tests,
        'pending_bills': pending_bills,
        'monthly_revenue': monthly_revenue,
        'monthly_expenses': monthly_expenses,
        'total_doctors': total_doctors,
        'total_nurses': total_nurses,
        'total_lab_techs': total_lab_techs,
        'new_patients_last_30_days': new_patients_last_30_days,
        'upcoming_appointments_today': upcoming_appointments_today,

        # Recent Lists
        'recent_patients': recent_patients,
        'recent_appointments': recent_appointments,

        # Chart Data (convert to JSON string for JS)
        'monthly_registrations_labels_json': json.dumps(monthly_registrations_labels),
        'monthly_registrations_data_json': json.dumps(monthly_registrations_data),
    }

    return render(request, 'hms_admin/index.html', context)

@login_required(login_url='home')
def director_operations(request):
    return render(request, 'hms_admin/operations.html')

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
    }

    return render(request, 'hms_admin/reports.html', context)

@login_required(login_url='home')
def user_accounts(request):
    users = User.objects.filter(is_superuser=False)

    context = {'users' : users }
    return render(request, 'hms_admin/user_accounts.html', context)

''' ############################################################################################################################ Receptionist View ############################################################################################################################ '''

@login_required(login_url='home')
def receptionist(request):
    today = localdate()
    start_of_week = today - timedelta(days=today.weekday())

    recent_activity = Patient.objects.order_by('-date_registered')[:5]
    queue = Appointment.objects.filter(scheduled_time__date=today).order_by('scheduled_time')[:5]

    context = {
        'new_patients_today': Patient.objects.filter(date_registered__date=today).count(),
        'active_patients': Patient.objects.count(),
        'appointments_today': Appointment.objects.filter(scheduled_time__date=today).count(),
        'admissions_this_week': Admission.objects.filter(admitted_on__range=[start_of_week, today]).count(),
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

        # ✅ Check for existing open admission
        if Admission.objects.filter(patient=patient, status='Admitted').exists():
            messages.warning(request, f"{patient.full_name} is already admitted and not yet discharged.")
            return redirect('register_patient')

        # Get attending staff name
        try:
            attending_profile = Staff.objects.get(user__id=attending_id)
            attending_name = f"{attending_profile.user.first_name} {attending_profile.user.last_name}"
        except Staff.DoesNotExist:
            attending_name = "Unknown Staff"

        # Update patient status
        patient.is_inpatient = True
        patient.status = 'stable'
        patient.notes = reason
        patient.save()

        # Create admission
        Admission.objects.create(
            patient=patient,
            doctor_assigned=attending_name,
            admitted_by=request.user.get_full_name() or request.user.username,
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
                    scheduled_time=scheduled_time
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
                notes=notes
            )
            messages.success(request, "Patient referred successfully.")
        except Patient.DoesNotExist:
            messages.error(request, "Patient not found.")
        except Department.DoesNotExist:
            messages.error(request, "Department not found.")
        
        referer = request.META.get('HTTP_REFERER', '/')
        return redirect(referer)
    
''' ############################################################################################################################ End Receptionist View ############################################################################################################################ '''

#Charts views
def chart_view(request):
    context= { 'labels':['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'],
               'data': [12, 19, 20, 5, 7]}    
    return render(request, 'doctors/chart.html', context)   

def requesttest(request):
    categories = TestCategory.objects.prefetch_related('subcategories').all()
    patients = Patient.objects.all()
    return render(request, 'doctors/requesttest.html', {
        'categories': categories,
        'patients': patients
    })

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

#Test details and completion by lab

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

def submit_test_results(request, patient_id):
    if request.method == 'POST':
        # Get the patient object for file upload
        patient = get_object_or_404(Patient, id=patient_id)
        
        # Process test results (your existing logic)
        test_ids = request.POST.getlist('ids')
        
        # Handle file upload first (if provided)
        uploaded_file = request.FILES.get('result_file')
        lab_result_file = None
        
        if uploaded_file:
            try:
                # Create a new LabResultFile entry
                lab_result_file = LabResultFile.objects.create(
                    patient=patient,
                    result_file=uploaded_file,
                    uploaded_by=request.user if request.user.is_authenticated else None
                )
            except Exception as e:
                messages.error(request, f'File upload failed: {str(e)}')
                return redirect('lab_test_entry')
        
        # Process individual test results
        for test_id in test_ids:
            try:
                lab_test = LabTest.objects.get(id=test_id)
                # Fetch the value using test name as the input name
                result_value = request.POST.get(lab_test.test_name)
                
                if result_value:
                    lab_test.result_value = result_value
                    lab_test.status = 'completed'
                    
                    # Link the uploaded file to this test (similar to doctor_comments pattern)
                    if lab_result_file:
                        lab_test.labresulttestid = lab_result_file.id
                    
                    lab_test.save()
            except LabTest.DoesNotExist:
                continue  # Ignore invalid IDs
        
        # Success messages
        if uploaded_file and lab_result_file:
            messages.success(request, f'Test results updated and file "{uploaded_file.name}" uploaded successfully!')
        elif test_ids:
            messages.success(request, 'Test results updated successfully!')
        else:
            messages.warning(request, 'No tests were selected for update.')
        
        return redirect('lab_test_entry')

    return redirect('lab_test_entry')
 

 #Doctor's fetching test results that were recommended


from collections import defaultdict
from django.utils import timezone
from django.shortcuts import render, redirect
from django.contrib import messages



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
            doctor_name=str(request.user),  # or request.user.get_full_name() if applicable
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
            Vitals.objects.filter(patient=patient).order_by('-recorded_at'),
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
                'recorded_by': vital.recorded_by,
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

            # Fetch Doctor Comment
            doctor_comment_data = None
            if first_test.doctor_comments:
                try:
                    comment = DoctorComments.objects.get(id=first_test.doctor_comments)
                    doctor_comment_data = {
                        "id": comment.id,
                        "comment": comment.comments,
                        "doctor_name": comment.doctor_name,
                        "labtech_name": comment.labtech_name,
                        "date": comment.date.strftime('%Y-%m-%d %H:%M')
                    }
                except DoctorComments.DoesNotExist:
                    doctor_comment_data = None

            # Fetch Lab Result File
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

        # 6. NURSING NOTES
        nursing_notes_qs = apply_date_filter(
            patient.nursing_notes.order_by('-note_datetime'),
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
                'nurse': note.nurse,
                'note_type': note.get_note_type_display(),
                'note_type_code': note.note_type,
                'notes': note.notes,
                'patient_status': note.patient_status or '',
                'follow_up': note.follow_up or '',
                'created_at': note.created_at.strftime('%Y-%m-%d %H:%M'),
            })

        # 7. ADMISSIONS
        admissions_qs = apply_date_filter(
            Admission.objects.filter(patient=patient).order_by('-admission_date'),
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
                'admitted_by': admission.admitted_by or '',
                'doctor_assigned': admission.doctor_assigned,
                'status': admission.status,
                'discharge_date': admission.discharge_date.strftime('%Y-%m-%d') if admission.discharge_date else '',
                'discharged_by': admission.discharged_by or '',
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

        # 9. REFERRALS (No date filtering since Referral model doesn't have created_at)
        referrals = []
        referrals_qs = Referral.objects.filter(patient=patient).select_related('department')
        for referral in referrals_qs:
            referrals.append({
                'id': referral.id,
                'department': referral.department.name,
                'notes': referral.notes,
            })

        # 10. APPOINTMENTS
        appointments_qs = apply_date_filter(
            Appointment.objects.filter(patient=patient).select_related('department').order_by('-scheduled_time'),
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
            })

        # 11. BILLS
        bills_qs = apply_date_filter(
            patient.bills.prefetch_related('items__service_type').order_by('-created_at'),
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

        # 13. HANDOVER LOGS
        handover_logs_qs = apply_date_filter(
            HandoverLog.objects.filter(patient=patient).select_related('author').order_by('-timestamp'),
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
