from multiprocessing import context
from django.contrib import messages
from django.contrib.auth.models import User
from django.shortcuts import render, redirect, get_object_or_404
from .models import Patient, Profile, Ward, Bed, Admission, Vitals, NursingNote, Consultation, Prescription, CarePlan, LabTest, LabResultFile, Department, TestCategory, LabTest, ShiftAssignment, Attendance, Shift, StaffTransition, LabTest, TestSubcategory
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
import json
from datetime import datetime, date
from django.utils.timezone import localdate, now
from django.core.serializers.json import DjangoJSONEncoder

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
                role = user.profile.role
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
        Profile.objects.create(
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


""" Nurses Views """
@login_required(login_url='home')
def nurses(request):
    return render(request,'nurses/index.html')

@login_required(login_url='home')
def bed_ward_management_view(request):
    beds = Bed.objects.filter(is_occupied=False).values('id', 'number', 'ward_id', 'ward__name')
    beds_json = json.dumps(list(beds), cls=DjangoJSONEncoder)

    context = {
        'patients': Patient.objects.all(),
        'wards': Ward.objects.all(),
        'beds_json': beds_json,
        'admitted_patients': Patient.objects.filter(is_inpatient=True),
        'doctors': Profile.objects.select_related('user').filter(Q(role='doctor') | Q(role='nurse')),
        'departments' : Department.objects.all()
    }
    return render(request, 'nurses/bed_ward_management.html', context)

@csrf_exempt
@login_required(login_url='home')
def admit_patient_nurse(request):
    if request.method == 'POST':
        patient_id = request.POST.get('patient_id')
        admission_reason = request.POST.get('admission_reason')
        ward_id = request.POST.get('ward')
        bed_number = request.POST.get('bed_number')
        doctor = request.POST.get('doctor')
        admission_date = request.POST.get('admission_date') or timezone.now().date()

        # ✅ Get patient by ID
        try:
            patient = Patient.objects.get(id=patient_id)
        except Patient.DoesNotExist:
            messages.error(request, f"Patient with ID '{patient_id}' not found.")
            return redirect('nursing_ward_actions')

        # ✅ Check if already admitted
        if Admission.objects.filter(patient=patient, status='Admitted').exists():
            messages.warning(request, f"Patient '{patient.full_name}' is already admitted.")
            return redirect('nursing_ward_actions')

        try:
            ward = Ward.objects.get(id=ward_id)
        except Ward.DoesNotExist:
            messages.error(request, "Selected ward does not exist.")
            return redirect('nursing_ward_actions')

        try:
            bed = Bed.objects.get(number=bed_number, ward=ward)
        except Bed.DoesNotExist:
            messages.error(request, "Selected bed does not exist.")
            return redirect('nursing_ward_actions')

        # ✅ Create admission
        Admission.objects.create(
            patient=patient,
            admission_date=admission_date,
            ward=ward,
            bed=bed,
            doctor_assigned=doctor,
            status='Admitted',
            admitted_by=request.user.username
        )

        # ✅ Update bed and patient
        bed.is_occupied = True
        bed.save()

        patient.is_inpatient = True
        patient.ward = ward
        patient.bed = bed
        patient.notes = admission_reason
        patient.save()

        messages.success(request, f"Patient '{patient.full_name}' admitted to Ward {ward.name}, Bed {bed.number}.")
        return redirect('nursing_ward_actions')

    return redirect('nursing_ward_actions')

@csrf_exempt
@login_required(login_url='home')
def assign_ward_bed(request):
    if request.method == 'POST':
        patient_id = request.POST.get('patient_id')
        ward_id = request.POST.get('ward_id')
        bed_number = request.POST.get('bed_number')
        doctor = request.POST.get('doctor')

        try:
            patient = Patient.objects.get(id=patient_id)
            ward = Ward.objects.get(id=ward_id)
            new_bed = Bed.objects.get(ward=ward, number=bed_number, is_occupied=False)
        except Patient.DoesNotExist:
            messages.error(request, "Patient not found.")
            return redirect('nursing_ward_actions')
        except Ward.DoesNotExist:
            messages.error(request, "Ward not found.")
            return redirect('nursing_ward_actions')
        except Bed.DoesNotExist:
            messages.error(request, "Selected bed is not available.")
            return redirect('nursing_ward_actions')

        # Release the old bed if exists
        if patient.bed:
            patient.bed.is_occupied = False
            patient.bed.save()

        # Assign new bed
        new_bed.is_occupied = True
        new_bed.save()

        # Update or create admission
        admission = Admission.objects.filter(patient=patient, status='Admitted').first()
        if admission:
            admission.ward = ward
            admission.bed = new_bed
            admission.doctor_assigned = doctor or admission.doctor_assigned
            admission.admission_date = timezone.now().date()
            admission.save()
        else:
            Admission.objects.create(
                patient=patient,
                admission_date=timezone.now().date(),
                ward=ward,
                bed=new_bed,
                doctor_assigned=doctor,
                status='Admitted',
                admitted_by=request.user.username
            )

        # Update patient record
        patient.ward = ward
        patient.bed = new_bed
        patient.is_inpatient = True
        patient.status = 'stable'
        patient.save()

        messages.success(request, f"{patient.full_name} has been reassigned to {ward.name}, Bed {new_bed.number}")
        return redirect('nursing_ward_actions')

    return redirect('nursing_ward_actions')

@csrf_exempt
@login_required(login_url='home')
def discharge_patient(request):
    if request.method == 'POST':
        patient_id = request.POST.get('patient_id')
        discharge_summary = request.POST.get('discharge_summary')

        try:
            patient = Patient.objects.get(id=patient_id)

            if not patient.is_inpatient:
                messages.error(request, f"{patient.full_name} is not currently admitted.")
                return redirect('nursing_ward_actions')

            # Try to get the active admission record
            admission = Admission.objects.filter(patient=patient, status='Admitted').order_by('-admission_date').first()
            if not admission:
                messages.error(request, f"No active admission record found for {patient.full_name}.")
                return redirect('nursing_ward_actions')

            # Release the bed
            bed = patient.bed
            if bed:
                bed.is_occupied = False
                bed.save()

            # Update patient record
            patient.is_inpatient = False
            patient.ward = None
            patient.bed = None
            patient.status = 'discharged'
            patient.notes = f"{patient.notes or ''}\n\nDISCHARGE SUMMARY ({timezone.now().strftime('%Y-%m-%d %H:%M')}):\n{discharge_summary}"
            patient.save()

            # Update admission record
            admission.status = 'Discharged'
            admission.discharge_date = timezone.now().date()
            admission.discharge_notes = discharge_summary
            admission.discharged_by = request.user.username
            admission.save()

            messages.success(request, f"{patient.full_name} has been discharged successfully.")

        except Patient.DoesNotExist:
            messages.error(request, "Patient not found.")

        return redirect('nursing_ward_actions')

    return redirect('nursing_ward_actions')

@csrf_exempt
@login_required(login_url='home')
def update_patient_status(request):
    if request.method == 'POST':
        patient_id = request.POST.get('patient_id')
        status = request.POST.get('status')
        notes = request.POST.get('notes')

        try:
            patient = Patient.objects.get(id=patient_id)

            if not patient.is_inpatient:
                messages.error(request, f"{patient.full_name} is not currently admitted.")
                return redirect('nursing_ward_actions')

            # Get active admission
            admission = Admission.objects.filter(patient=patient, status='Admitted').order_by('-admission_date').first()
            if not admission:
                messages.error(request, f"No active admission record found for {patient.full_name}.")
                return redirect('nursing_ward_actions')

            # Update patient status
            patient.status = status

            # Timestamped note
            timestamp = timezone.now().strftime('%Y-%m-%d %H:%M')
            new_note = f"\n\nSTATUS UPDATE ({timestamp}) - STATUS: {status}\n{notes}"
            patient.notes = f"{patient.notes or ''}{new_note}"
            patient.save()

            # Optional: Append to admission notes if you like (e.g. monitor history)
            if admission.discharge_notes:
                admission.discharge_notes += f"\n\n{new_note}"
            else:
                admission.discharge_notes = new_note
            admission.save()

            messages.success(request, f"{patient.full_name}'s status updated to {status}.")

        except Patient.DoesNotExist:
            messages.error(request, "Patient not found.")

        return redirect('nursing_ward_actions')

    return redirect('nursing_ward_actions')

@csrf_exempt
@login_required(login_url='home')
def get_patient_details(request, patient_id):
    try:
        patient = Patient.objects.get(id=patient_id)
        return JsonResponse({
            'id': patient.id,
            'full_name': patient.full_name,
            'status': patient.status,
            'is_inpatient': patient.is_inpatient,
            'ward': patient.ward.id if patient.ward else None,
            'ward_name': patient.ward.name if patient.ward else None,
            'bed': patient.bed.number if patient.bed else None,
            'notes': patient.notes
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

@login_required(login_url='home')
def nursing_notes(request):
    context = {
        'patients': Patient.objects.all(),
    }
    return render(request, 'nurses/nursing_notes.html', context)

@csrf_exempt
@login_required(login_url='home')
def save_nursing_note(request):
    if request.method == "POST":
        patient_id = request.POST.get('patient_id')
        note_datetime = request.POST.get('note_datetime') or timezone.now()
        note_type = request.POST.get('note_type')
        nurse = request.user.get_full_name() or request.user.username
        patient_status = request.POST.get('patient_status')
        notes = request.POST.get('notes')
        follow_up = request.POST.get('follow_up')

        try:
            patient = Patient.objects.get(id=patient_id)
        except Patient.DoesNotExist:
            messages.error(request, "Patient not found.")
            return redirect('nursing_notes')  # adjust URL name accordingly

        NursingNote.objects.create(
            patient=patient,
            note_datetime=note_datetime,
            note_type=note_type,
            nurse=nurse,
            patient_status=patient_status,
            notes=notes,
            follow_up=follow_up
        )
        messages.success(request, "Nursing note saved successfully.")
        return redirect('nursing_notes')

    return redirect('nursing_notes')

""" Doctors Views"""
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
    patients = Patient.objects.all()
    return render(request, 'doctors/access_medical_records.html', {
        'patients': patients
    })

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

@login_required(login_url='home')                          
def ae(request):     
    return render(request, 'ae/base.html')

# Lab views
@login_required(login_url='home')                        
def laboratory(request):
<<<<<<< HEAD
    pending_test = TestSelection.objects.filter(status='pending').select_related('patient_id')
=======
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

    pending_test = TestSelection.objects.filter(status='pending').count()
>>>>>>> b6b32c30e3c1eca5f3feeadf385bf605245d02d5
    return render(request, 'laboratory/index.html', {'pending':pending_test})

@login_required(login_url='home')
def lab_test_entry(request):
    """
    Fetch all patients and display them in a table for lab test entry
    """
    # Get all patients
    patients = Patient.objects.all().select_related('ward', 'bed').order_by('-date_registered')
    
    # Prepare patient data with test counts and additional info
    patients_data = []
    for patient in patients:
        # Count pending tests for this patient
        pending_tests_count = LabTest.objects.filter(
            patient=patient,
            status='pending'
        ).count()
        
        # Count completed tests for this patient
        completed_tests_count = LabTest.objects.filter(
            patient=patient,
            status='completed'
        ).count()
        
        # Count in progress tests
        in_progress_tests_count = LabTest.objects.filter(
            patient=patient,
            status='in_progress'
        ).count()
        
        # Get latest consultation or referral info
        latest_referral = Referral.objects.filter(patient=patient).order_by('-id').first()
        referred_by = latest_referral.notes if latest_referral else patient.referred_by
        
        patients_data.append({
            'patient': patient,
            'pending_tests': pending_tests_count,
            'completed_tests': completed_tests_count,
            'in_progress_tests': in_progress_tests_count,
            'total_tests': pending_tests_count + completed_tests_count + in_progress_tests_count,
            'referred_by': referred_by or 'Walk-in',
            'last_test_date': LabTest.objects.filter(patient=patient).order_by('-requested_at').first(),
        })
    
    # Calculate summary statistics
    total_patients = patients.count()
    patients_with_pending_tests = len([p for p in patients_data if p['pending_tests'] > 0])
    total_pending_tests = LabTest.objects.filter(status='pending').count()
    total_completed_today = LabTest.objects.filter(
        status='completed',
        date_performed__date=timezone.now().date()
    ).count()
    total_in_progress = LabTest.objects.filter(status='in_progress').count()
    
    # Get available test categories for quick test creation
    test_categories = TestCategory.objects.all().order_by('name')
    
    context = {
        'patients_data': patients_data,
        'test_categories': test_categories,
        'stats': {
            'total_patients': total_patients,
            'patients_with_pending_tests': patients_with_pending_tests,
            'total_pending_tests': total_pending_tests,
            'total_completed_today': total_completed_today,
            'total_in_progress': total_in_progress,
        },
        'debug_info': {
            'total_patients_fetched': len(patients_data),
            'test_categories_count': test_categories.count(),
            'methods_used': ['Patient.objects.all()', 'LabTest filtering'],
        } if request.user.is_superuser else None
    }
    
    return render(request, 'laboratory/test_entry.html', context)

@login_required(login_url='home')
def lab_test_entry(request):
    """
    Fetch all patients and display them in a table for lab test entry
    """
    # Get all patients
    patients = Patient.objects.all().select_related('ward', 'bed').order_by('-date_registered')
    
    # Prepare patient data with test counts and additional info
    patients_data = []
    for patient in patients:
        # Count pending tests for this patient
        pending_tests_count = LabTest.objects.filter(
            patient=patient,
            status='pending'
        ).count()
        
        # Count completed tests for this patient
        completed_tests_count = LabTest.objects.filter(
            patient=patient,
            status='completed'
        ).count()
        
        # Count in progress tests
        in_progress_tests_count = LabTest.objects.filter(
            patient=patient,
            status='in_progress'
        ).count()
        
        # Get latest consultation or referral info
        latest_referral = Referral.objects.filter(patient=patient).order_by('-id').first()
        referred_by = latest_referral.notes if latest_referral else patient.referred_by
        
        patients_data.append({
            'patient': patient,
            'pending_tests': pending_tests_count,
            'completed_tests': completed_tests_count,
            'in_progress_tests': in_progress_tests_count,
            'total_tests': pending_tests_count + completed_tests_count + in_progress_tests_count,
            'referred_by': referred_by or 'Walk-in',
            'last_test_date': LabTest.objects.filter(patient=patient).order_by('-requested_at').first(),
        })
    
    # Calculate summary statistics
    total_patients = patients.count()
    patients_with_pending_tests = len([p for p in patients_data if p['pending_tests'] > 0])
    total_pending_tests = LabTest.objects.filter(status='pending').count()
    total_completed_today = LabTest.objects.filter(
        status='completed',
        date_performed__date=timezone.now().date()
    ).count()
    total_in_progress = LabTest.objects.filter(status='in_progress').count()
    
    # Get available test categories with sub-tests for quick test creation
    test_categories = TestCategory.objects.prefetch_related('subcategories').all().order_by('name')
    
    context = {
        'patients_data': patients_data,
        'test_categories': test_categories,
        'stats': {
            'total_patients': total_patients,
            'patients_with_pending_tests': patients_with_pending_tests,
            'total_pending_tests': total_pending_tests,
            'total_completed_today': total_completed_today,
            'total_in_progress': total_in_progress,
        },
        'debug_info': {
            'total_patients_fetched': len(patients_data),
            'test_categories_count': test_categories.count(),
            'methods_used': ['Patient.objects.all()', 'LabTest filtering'],
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
    return render(request, 'accounts/index.html')

@login_required(login_url='home')
def patient_payment_tracker(request):
    return render(request, 'accounts/payment_tracker.html')

# @login_required(login_url='home')
# def institution_financials(request):
#     return render(request, 'accounts/financials.html')

@login_required(login_url='home')
def financial_reports(request):
    return render(request, 'accounts/financial_reports.html')

@login_required(login_url='home')
def budget_planning(request):
    return render(request, 'accounts/planning.html')

# HR Views
@login_required(login_url='home')
def hr(request):
    return render(request, 'hr/index.html')

@login_required(login_url='home')
def staff_profiles(request):
    staff_list = Profile.objects.select_related('user', 'department').all()
    departments = Department.objects.all()
    context = {
        'staff_list': staff_list,
        'departments': departments,
    }
    return render(request, 'hr/staff_profiles.html', context)

@csrf_exempt
def edit_staff_profile(request, staff_id):
    try:
        profile = Profile.objects.select_related('user').get(id=staff_id)
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
    except Profile.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Staff not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@csrf_exempt
def change_staff_password(request, staff_id):
    try:
        profile = Profile.objects.select_related('user').get(id=staff_id)
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')

        if new_password != confirm_password:
            return JsonResponse({'success': False, 'error': 'Passwords do not match'})

        profile.user.set_password(new_password)
        profile.user.save()

        return JsonResponse({'success': True})
    except Profile.DoesNotExist:
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
        profile = request.user.profile
    except Profile.DoesNotExist:
        messages.error(request, "Your user profile is not set up properly.")
        return redirect('home')

    staff_users = User.objects.filter(profile__isnull=False).order_by('first_name', 'last_name')
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
    staff_list = Profile.objects.all().order_by('user__first_name')
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

# Receptionist View
@login_required(login_url='home')
def receptionist(request):
    return render(request, 'receptionist/index.html')

@login_required(login_url='home')
def register_patient(request):
    patients = Patient.objects.all().order_by('-date_registered')
    wards = Ward.objects.all()
    available_beds = Bed.objects.filter(is_occupied=False)
    department = Department.objects.all()
        
    return render(request, 'receptionist/register.html', {
        'wards': wards,
        'patients': patients,
        'available_beds' : available_beds,
        'department' : department
    }
)

@csrf_exempt
def admit_patient(request):
    if request.method == 'POST':
        patient_name = request.POST.get('patient_id')
        ward_name = request.POST.get('ward')
        bed_number = request.POST.get('bed_number')
        reason = request.POST.get('admission_reason')
        doctor = request.POST.get('doctor')
        admission_date = request.POST.get('admission_date') or timezone.now().date()

        # Get patient
        try:
            patient = Patient.objects.get(full_name=patient_name)
        except Patient.DoesNotExist:
            messages.error(request, "Patient not found.")
            return redirect('register_patient')

        # Get ward
        try:
            ward = Ward.objects.get(name=ward_name)
        except Ward.DoesNotExist:
            messages.error(request, "Selected ward does not exist.")
            return redirect('register_patient')

        # Get bed
        try:
            bed = Bed.objects.get(ward=ward, number=bed_number, is_occupied=False)
        except Bed.DoesNotExist:
            messages.error(request, "Selected bed is not available.")
            return redirect('register_patient')

        # Update bed status
        bed.is_occupied = True
        bed.save()

        # Update patient info
        patient.is_inpatient = True
        patient.ward = ward
        patient.bed = bed
        patient.status = 'stable'
        patient.notes = reason
        patient.save()

        # Create admission record
        Admission.objects.create(
            patient=patient,
            admission_date=admission_date,
            ward=ward,
            bed=bed,
            doctor_assigned=doctor,
            status='Admitted'
        )

        messages.success(request, f"{patient.full_name} has been admitted successfully.")
        return redirect('register_patient')
    
@csrf_exempt
def get_available_beds(request):
    ward_name = request.GET.get('ward_name')
    if not ward_name:
        return JsonResponse({'error': 'Ward not specified'}, status=400)
    
    try:
        ward = Ward.objects.get(name=ward_name)
    except Ward.DoesNotExist:
        return JsonResponse({'error': 'Ward not found'}, status=404)
    
    beds = Bed.objects.filter(ward=ward, is_occupied=False)
    bed_list = [{'number': bed.number} for bed in beds]
    return JsonResponse({'beds': bed_list})

@csrf_exempt
def register_p(request):
    if request.method == 'POST':
        data = request.POST
        photo = request.FILES.get('photo')

        full_name = data.get('full_name')
        phone = data.get('phone')
        dob = data.get('dob')
        gender = data.get('gender')

        if not full_name or not phone or not dob or not gender:
            messages.error(request, "Full name, phone, gender, and date of birth are required.")
            return redirect('register_patient')

        if Patient.objects.filter(full_name=full_name, date_of_birth=dob).exists():
            messages.warning(request, "A patient with the same name and date of birth already exists.")
            return redirect('register_patient')

        try:
            Patient.objects.create(
                full_name=full_name,
                date_of_birth=dob,
                gender=gender,
                phone=phone,
                email=data.get('email'),
                marital_status=data.get('marital_status'),
                address=data.get('address'),
                nationality=data.get('nationality'),
                state_of_origin=data.get('state_of_origin'),
                id_type=data.get('id_type'),
                id_number=data.get('id_number'),
                photo=photo,
                first_time=data.get('first_time'),
                referred_by=data.get('referred_by'),
                notes=data.get('notes')
            )

            messages.success(request, "Patient registered successfully.")
            return redirect('register_patient')

        except Exception as e:
            messages.error(request, f"An error occurred: {str(e)}")
            return redirect('register_patient')

@csrf_exempt
def update_patient_info(request):
    if request.method == 'POST':
        patient_id = request.POST.get('patient_id')
        try:
            patient = Patient.objects.get(id=patient_id)
            
            # Update basic information
            patient.full_name = request.POST.get('full_name')
            patient.date_of_birth = parse_date(request.POST.get('dob'))
            patient.gender = request.POST.get('gender')
            patient.phone = request.POST.get('phone')
            patient.email = request.POST.get('email')
            patient.marital_status = request.POST.get('marital_status')
            patient.address = request.POST.get('address')
            patient.nationality = request.POST.get('nationality')
            patient.state_of_origin = request.POST.get('state_of_origin')
            patient.id_type = request.POST.get('id_type')
            patient.id_number = request.POST.get('id_number')
            
            # Handle photo upload if present
            if 'photo' in request.FILES:
                patient.photo = request.FILES['photo']
            
            # Update additional info
            patient.first_time = request.POST.get('first_time')
            patient.referred_by = request.POST.get('referred_by')
            patient.blood_group = request.POST.get('blood_group')
            patient.next_of_kin_name = request.POST.get('next_of_kin_name')
            patient.next_of_kin_phone = request.POST.get('next_of_kin_phone')
            patient.notes = request.POST.get('notes')
            
            patient.save()
        
            messages.success(request, f"Patient {patient.full_name}'s information updated successfully.")
            
        except Patient.DoesNotExist:
            messages.error(request, "Patient not found.")
            pass
            
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

    
@csrf_exempt
def get_patient_info(request, patient_id):
    try:
        patient = Patient.objects.get(id=patient_id)
        return JsonResponse({
            'full_name': patient.full_name,
            'date_of_birth': patient.date_of_birth.strftime('%Y-%m-%d') if patient.date_of_birth else '',
            'gender': patient.gender,
            'phone': patient.phone,
            'email': patient.email,
            'marital_status': patient.marital_status,
            'address': patient.address,
            'nationality': patient.nationality,
            'state_of_origin': patient.state_of_origin,
            'id_type': patient.id_type,
            'id_number': patient.id_number,
            'first_time': patient.first_time,
            'referred_by': patient.referred_by,
            'blood_group': patient.blood_group,
            'next_of_kin_name': patient.next_of_kin_name,
            'next_of_kin_phone': patient.next_of_kin_phone,
            'notes': patient.notes
        })
    except Patient.DoesNotExist:
        return JsonResponse({'error': 'Patient not found'}, status=404)


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
            print("I am connected")
            data = json.loads(request.body)
            patient_id = data.get('patient_id')
            selections = data.get('selections', [])
            print(type(patient_id))
            print("patient id ", patient_id)
            print("data ", selections)
            if not patient_id or not selections:
                return JsonResponse({'status': 'error', 'message': 'Missing patient or selection data'})
            patient_id1 = int(patient_id)
            type(patient_id1)
            patient = Patient.objects.get(id=patient_id1)
            print("patient ", patient)
            for item in selections:
                category = item['category']
                for test in item['tests']:
                    LabTest.objects.create(patient_id=patient,category=category, test_name=test)

            return JsonResponse({'status': 'success', 'message': 'Selections saved.'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'})

#graph 2
from django.http import JsonResponse
from django.db.models import Count
from .models import Admission
from django.utils import timezone
from datetime import timedelta


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



