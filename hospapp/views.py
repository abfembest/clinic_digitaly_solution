from multiprocessing import context
from django.contrib import messages
from django.contrib.auth.models import User
from django.shortcuts import render, redirect, get_object_or_404
from .models import Patient, Staff, Admission, Vitals, NursingNote, Consultation, Prescription, CarePlan, LabTest, LabResultFile, Department, TestCategory, ShiftAssignment, Attendance, Shift, StaffTransition, TestSubcategory, Payment, PatientBill, Budget, Expense, HandoverLog, ExpenseCategory
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
            'lab_tests': lab_tests,
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
    context = {'patients': Patient.objects.all(),}
    return render(request, 'doctors/consultation.html', context)

@login_required(login_url='home')
def save_consultation(request):
    if request.method == 'POST':
        patient_id = request.POST.get('patient_id')
        symptoms = request.POST.get('symptoms')
        diagnosis_summary = request.POST.get('diagnosis_summary')
        advice = request.POST.get('advice')
        
        patient = get_object_or_404(Patient, id=patient_id)
        
        Consultation.objects.create(
            patient=patient,
            doctor=request.user,
            symptoms=symptoms,
            diagnosis_summary=diagnosis_summary,
            advice=advice
        )
        
        messages.success(request, f"Consultation saved for {patient.full_name}.")
        return redirect('doctor_consultation')  # Or wherever you want to land after saving


@csrf_exempt
def patient_history_ajax(request, patient_id):
    patient = get_object_or_404(Patient, id=patient_id)

    consultations = patient.consultations.order_by('-created_at')[:5]
    admissions = patient.admission_set.order_by('-admission_date')[:5]
    vitals = patient.vitals_set.order_by('-recorded_at')[:5]
    notes = patient.nursing_notes.order_by('-note_datetime')[:5]
    records = patient.medical_records.order_by('-record_date')[:5]
    prescriptions = patient.prescriptions.order_by('-created_at')[:5]

    return render(request, 'doctors/history.html', {
        'patient': patient,
        'consultations': consultations,
        'admissions': admissions,
        'vitals': vitals,
        'nursing_notes': notes,
        'medical_records': records,
        'prescriptions': prescriptions,
    })

@csrf_exempt
def add_prescription(request):
    if request.method == 'POST':
        patient_id = request.POST.get('patient_id')
        medication = request.POST.get('medication')
        instructions = request.POST.get('instructions')
        start_date = request.POST.get('start_date')

        patient = get_object_or_404(Patient, id=patient_id)

        Prescription.objects.create(
            patient=patient,
            medication=medication,
            instructions=instructions,
            start_date=start_date,
            prescribed_by=request.user
        )

        messages.success(request, f"Prescription added for {patient.full_name}.")
        return redirect('doctor_consultation')  # Or wherever appropriate

    return redirect('home')

@csrf_exempt
def request_tests(request):
    if request.method == "POST":
        patient_id = request.POST.get('patient_id')
        tests = request.POST.getlist('test')
        instructions = request.POST.get('instructions', '').strip()

        if not patient_id or not tests:
            messages.error(request, "Please select a patient and at least one test.")
            return redirect(request.META.get('HTTP_REFERER', 'doctor_consultation'))

        patient = get_object_or_404(Patient, id=patient_id)
        
        test_request = LabTest.objects.create(
            patient=patient,
            requested_by=request.user,
            instructions=instructions
        )
        test_request.tests.set(tests)  # assuming 'tests' is a list of LabTestType IDs

        messages.success(request, "Test request submitted successfully.")
        return redirect('doctor_consultation')

    # If GET or other method, redirect or raise error
    return redirect('doctor_consultation')

@csrf_exempt
def save_care_plan(request):
    if request.method == "POST":
        patient_id = request.POST.get('patient_id')
        clinical_findings = request.POST.get('clinical_findings', '').strip()
        plan_of_care = request.POST.get('plan_of_care', '').strip()

        if not patient_id or not clinical_findings or not plan_of_care:
            messages.error(request, "Please fill in all required fields.")
            return redirect(request.META.get('HTTP_REFERER', 'doctor_consultation'))

        patient = get_object_or_404(Patient, id=patient_id)

        CarePlan.objects.create(
            patient=patient,
            clinical_findings=clinical_findings,
            plan_of_care=plan_of_care,
            created_by=request.user
        )

        messages.success(request, "Care plan saved successfully.")
        return redirect('doctor_consultation')

    # For GET or other methods, redirect somewhere appropriate
    return redirect('doctor_consultation')

@login_required(login_url='home')
def access_medical_records(request):
    view_type = request.GET.get('view')
    if view_type == 'individual':
        patients = Patient.objects.all()
        return render(request, 'doctors/individual_records.html', {'patients': patients})

    elif view_type == 'all':
        patients = Patient.objects.all()
        return render(request, 'doctors/all_records.html', {'patients': patients})

    # Default page with the two links
    return render(request, 'doctors/access_medical_records.html')

@login_required(login_url='home')
def get_patient_overview(request, patient_id):
    try:
        patient = Patient.objects.get(id=patient_id)
        # Get the latest admission for this patient, if any
        admission = Admission.objects.filter(patient=patient).order_by('-admission_date').first()
        
        # Get the latest vitals for this patient, limited to 5
        vitals = Vitals.objects.filter(patient=patient).order_by('-recorded_at')[:5]
        
        # Calculate age from date_of_birth (implement as needed)
        # For simplicity, we're not calculating age here, but you would typically do:
        # from datetime import date
        # age = (date.today() - patient.date_of_birth).days // 365
        
        return JsonResponse({
            "name": patient.full_name,
            "gender": patient.gender,
            "status": patient.status,
            "ward": admission.ward.name if admission and admission.ward else None,
            "bed": str(admission.bed) if admission and admission.bed else None,
            "last_vitals": [
                {
                    "bp": vital.blood_pressure, 
                    "hr": vital.pulse, 
                    "temp": vital.temperature,
                    "date": vital.recorded_at.strftime("%Y-%m-%d %H:%M")
                } 
                for vital in vitals
            ],
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
def get_patient_monitor(request, patient_id):
    try:
        patient = Patient.objects.get(id=patient_id)
        # Get consultations for this patient, ordered by most recent first
        consultations = Consultation.objects.filter(patient=patient).order_by('-created_at')
        
        # Get prescriptions for this patient, ordered by most recent first
        prescriptions = Prescription.objects.filter(patient=patient).order_by('-created_at')
        
        return JsonResponse({
            "consultations": [
                {
                    "notes": c.diagnosis_summary,  # Using diagnosis_summary instead of notes
                    "date": c.created_at.strftime("%Y-%m-%d")
                } 
                for c in consultations
            ],
            "prescriptions": [
                {
                    "drug": p.medication,  # Using medication instead of drug
                    "dosage": p.instructions,  # Using instructions instead of dosage
                    "date": p.created_at.strftime("%Y-%m-%d")
                } 
                for p in prescriptions
            ],
        })
    except Patient.DoesNotExist:
        return JsonResponse({"error": "Patient not found"}, status=404)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

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
    #pending_test = TestSelection.objects.filter(status='pending').select_related('patient_id')
    labtest = LabTest.objects.all()
    pending_count = LabTest.objects.filter(status='pending').count()
    completed_count = LabTest.objects.filter(status='completed').count()
    uploaded_results = LabResultFile.objects.all().count()

    start_of_day = now().replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = start_of_day + timedelta(days=1)

    test_today = LabTest.objects.filter(date_performed__range=(start_of_day, end_of_day)).count()
    context = {
        'labtest' : labtest,
        'test_today' : test_today,
        'pending_count' : pending_count,
        'completed_count' : completed_count,
        'uploaded_results' : uploaded_results
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
def lab_result_upload(request):
    # Get only patients who have a referral
    referred_patient_ids = Referral.objects.values_list('patient_id', flat=True).distinct()
    patients = Patient.objects.filter(id__in=referred_patient_ids).order_by('full_name')
    
    selected_patient = None
    lab_tests = []
    uploaded_files = []

    if request.method == "POST":
        patient_id = request.POST.get('patient_id')
        patient = get_object_or_404(Patient, id=patient_id)
        result_file = request.FILES.get('result_file')

        if result_file:
            LabResultFile.objects.create(
                patient=patient,
                uploaded_by=request.user,
                result_file=result_file
            )
            messages.success(request, "Lab result file uploaded successfully.")
            return redirect(f"{request.path}?patient_id={patient_id}")
        else:
            messages.error(request, "Please upload a valid file.")

    selected_patient_id = request.GET.get('patient_id')
    if selected_patient_id:
        selected_patient = get_object_or_404(Patient, id=selected_patient_id)
        lab_tests = LabTest.objects.filter(patient=selected_patient).order_by('-date_performed')
        uploaded_files = LabResultFile.objects.filter(patient=selected_patient).order_by('-uploaded_at')

    context = {
        'patients': patients,
        'selected_patient': selected_patient,
        'lab_tests': lab_tests,
        'uploaded_files': uploaded_files,
    }
    return render(request, 'laboratory/result_upload.html', context)

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
    return render(request, 'hms_admin/index.html')

@login_required(login_url='home')
def director_operations(request):
    return render(request, 'hms_admin/operations.html')

@login_required(login_url='home')
def director_reports(request):
    return render(request, 'hms_admin/reports.html')

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

def submit_test_selection(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            patient_id = data.get('patient_id')
            selections = data.get('selections', [])
            patient_id1 = int(patient_id)
            if not patient_id or not selections:
                return JsonResponse({'status': 'error', 'message': 'Missing patient or selection data'})
            patient = Patient.objects.get(id=patient_id1)            
            for item in selections:
                category = item.get('category')
                tests = item.get('tests', [])
                for test in tests:
                    category_name = TestCategory.objects.get(name=category)
                    print(category,  test)
                    LabTest.objects.create(patient=patient, category=category_name, test_name=test)
                    
            return JsonResponse({'status': 'success', 'message': 'Selections saved.'})
        except DatabaseError as e:
            print("Database error:", str(e))  # Generic DB errors
    return JsonResponse({'status': 'error', 'message': 'Database error: ' + str(e)})
       
    
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
                return render(request, 'laboratory/test_entry.html')
        
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
        
        return render(request, 'laboratory/test_entry.html')
    
    return render(request, 'laboratory/test_entry.html')
 


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

def fetch_patient_activity(request):
    patient_id = request.POST.get('patient_id')
    date_filter = request.POST.get('dateFilter')
    start_date = request.POST.get('startDate')
    end_date = request.POST.get('endDate')
    export_format = request.POST.get('export')

    if not patient_id:
        return JsonResponse({'error': 'No patient selected'}, status=400)

    filters = {'id': patient_id}
    if date_filter == 'between' and start_date and end_date:
        filters['created_at__range'] = [start_date, end_date]

    lab_tests = LabTest.objects.filter(**filters)
    doctor_comments = DoctorComments.objects.filter(**filters)
    vitals = Vitals.objects.filter(**filters)
    payments = Payment.objects.filter(**filters)

    if export_format == 'csv':
        return export_to_csv(lab_tests, doctor_comments, vitals, payments)
    elif export_format == 'pdf':
        return export_to_pdf(lab_tests, doctor_comments, vitals, payments)

    # Paginate
    paginator = Paginator(lab_tests, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'partials/activity_results.html', {
        'lab_tests': page_obj,
        'doctor_comments': doctor_comments,
        'vitals': vitals,
        'payments': payments,
        'paginator': paginator,
        'page_obj': page_obj
    })

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
