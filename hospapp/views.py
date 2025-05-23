from django.contrib import messages
from django.contrib.auth.models import User
from .forms import PatientForm
from django.shortcuts import render, redirect, get_object_or_404
from .models import Patient, HandoverLog, TaskAssignment, Shift, EmergencyAlert, Profile, Ward, Bed, Admission, Vitals, NursingNote
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
from .models import Patient, Appointment, Referral
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.http import JsonResponse
from django.utils.dateparse import parse_date


# Create your views here.
ROLE_DASHBOARD_PATHS = {
    'nurse': 'n/home',
    'doctor': 'd/home',
    'lab': 'l/home',
    'pharmacy': 'p/home',
    'admin': 'ad/home',
    'hr': 'hr/home',
    'receptionist': 'r/home',
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
                    return redirect(f'/{dashboard_path}')
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
    context = {
        'patients': Patient.objects.all(),
        'wards': Ward.objects.all(),
        'available_beds': Bed.objects.filter(is_occupied=False),
        'admitted_patients': Patient.objects.filter(is_inpatient=True)
    }
    return render(request, 'nurses/bed_ward_management.html', context)

@csrf_exempt
@login_required(login_url='home')
def admit_patient_nurse(request):
    if request.method == 'POST':
        patient_id = request.POST.get('patient_id')  # <-- This must now be the patient ID
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
        doctor = request.POST.get('doctor', '')

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
@login_required(login_url='home')
def record_vitals(request):
    if request.method == 'POST':
        Vitals.objects.create(
            patient_id=request.POST.get('patient_id'),
            recorded_at=request.POST.get('recorded_at'),
            temperature=request.POST.get('temperature'),
            blood_pressure=request.POST.get('blood_pressure'),
            pulse=request.POST.get('pulse'),
            respiratory_rate=request.POST.get('respiratory_rate'),
            weight=request.POST.get('weight'),
            height=request.POST.get('height'),
            bmi=request.POST.get('bmi'),  # ✅ use submitted BMI
            notes=request.POST.get('notes'),
            recorded_by=request.user.username
        )
        messages.success(request, "Vitals recorded successfully.")
        return redirect('vitals')
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

@login_required(login_url='home')
def mar(request):
    return render(request, 'nurses/mar.html')

@login_required(login_url='home')
def handover_logs_view(request):
    if request.method == 'POST' and 'handover_submit' in request.POST:
        patient_id = request.POST.get('patient_id')
        notes = request.POST.get('notes')

        if patient_id and notes:
            try:
                patient = Patient.objects.get(id=patient_id)
                HandoverLog.objects.create(
                    patient=patient,
                    author=request.user,
                    notes=notes
                )
            except Patient.DoesNotExist:
                # optionally handle error if patient is not found
                pass

        return redirect('handover_logs')  # update with your actual URL name

    context = {
        'patients': Patient.objects.all(),
        'handovers': HandoverLog.objects.select_related('patient', 'author').order_by('-timestamp')[:50],
    }
    return render(request, 'nurses/handover_logs.html', context)

@login_required(login_url='home')
def task_assignments_view(request):
    if request.method == 'POST':
        nurse_id = request.POST.get('nurse_id')
        shift_id = request.POST.get('shift_id')
        task_description = request.POST.get('task_description')

        if nurse_id and shift_id and task_description:
            nurse = User.objects.get(id=nurse_id)
            shift = Shift.objects.get(id=shift_id)

            TaskAssignment.objects.create(
                nurse=nurse,
                shift=shift,
                task_description=task_description
            )
            return redirect('task_assignments')

    context = {
        'assignments': TaskAssignment.objects.select_related('nurse', 'shift').order_by('-created_at')[:50],
        'nurses': User.objects.all(),
        'shifts': Shift.objects.all()
    }
    return render(request, 'nurses/task_assignments.html', context)

@login_required(login_url='home')
def emergency_alerts_view(request):
    if request.method == 'POST':
        if 'acknowledge' in request.POST:
            alert_id = request.POST.get('alert_id')
            alert = EmergencyAlert.objects.get(id=alert_id)
            alert.acknowledged_by.add(request.user)

        elif 'trigger' in request.POST:
            message = request.POST.get('message')
            if message:
                EmergencyAlert.objects.create(
                    message=message,
                    triggered_by=request.user
                )
        return redirect('emergency_alerts')

    context = {
        'alerts': EmergencyAlert.objects.prefetch_related('acknowledged_by').order_by('-timestamp')[:50]
    }
    return render(request, 'nurses/emergency_alerts.html', context)

""" Doctors Views"""
@login_required(login_url='home')
def doctors(request):
    return render(request, 'doctors/index.html')

@login_required(login_url='home')
def doctor_consultation(request):
    return render(request, 'doctors/consultation.html')

# def patient_list(request):
#     return render(request, 'doctors/patient_list.html')

# View for the Patient List Page
# def patient_list(request):
#     patients = Patient.objects.all()
#     inpatients = patients.filter(is_inpatient=True)
#     outpatients = patients.filter(is_inpatient=False)
#     critical_count = patients.filter(status="critical").count()

#     context = {
#         'patients': patients,
#         'inpatients': inpatients,
#         'outpatients': outpatients,
#         'critical_count': critical_count
#     }
#     return render(request, 'doctors/patient_list.html', context)

# # View for Viewing Patient Profile
# def view_patient(request, patient_id):
#     patient = get_object_or_404(Patient, id=patient_id)
#     return render(request, 'doctors/view_patient.html', {'patient': patient})

# # View for Adding Diagnosis
# def add_diagnosis(request, patient_id):
#     patient = get_object_or_404(Patient, id=patient_id)
#     if request.method == 'POST':
#         # Logic for adding diagnosis here
#         # You can add diagnosis to the patient
#         diagnosis = request.POST.get('diagnosis')
#         patient.diagnosis = diagnosis
#         patient.save()
#         return HttpResponseRedirect(reverse('view_patient', args=[patient.id]))
#     return render(request, 'doctors/add_diagnosis.html', {'patient': patient})

# # View for Prescribing Medication
# def prescribe_med(request, patient_id):
#     patient = get_object_or_404(Patient, id=patient_id)
#     if request.method == 'POST':
#         # Logic for prescribing medication here
#         medication = request.POST.get('medication')
#         # Assume you have a Medication model to save prescriptions
#         patient.medication = medication
#         patient.save()
#         return HttpResponseRedirect(reverse('view_patient', args=[patient.id]))
#     return render(request, 'doctors/prescribe_medication.html', {'patient': patient})

# # View for Writing Notes
# def write_notes(request, patient_id):
#     patient = get_object_or_404(Patient, id=patient_id)
#     if request.method == 'POST':
#         # Logic for adding notes here
#         notes = request.POST.get('notes')
#         patient.notes = notes
#         patient.save()
#         return HttpResponseRedirect(reverse('view_patient', args=[patient.id]))
#     return render(request, 'doctors/write_notes.html', {'patient': patient})

@login_required(login_url='home')
def access_medical_records(request):
    patients = Patient.objects.all()
    return render(request, 'doctors/access_medical_records.html', {
        'patients': patients
    })

@login_required(login_url='home')
def monitoring(request):
    return render(request, 'doctors/treatment_monitoring.html')

@login_required(login_url='home')                          
def ae(request):     
    return render(request, 'ae/base.html')

# Lab views
@login_required(login_url='home')                        
def laboratory(request):
    return render(request, 'laboratory/index.html')

@login_required(login_url='home')
def lab_test_entry(request):
    return render(request, 'laboratory/test_entry.html')

@login_required(login_url='home')
def lab_result_upload(request):
    return render(request, 'laboratory/result_upload.html')

@login_required(login_url='home')
def lab_internal_logs(request):
    return render(request, 'laboratory/logs.html')

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

@login_required(login_url='home')
def institution_financials(request):
    return render(request, 'accounts/financials.html')

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
    return render(request, 'hr/staff_profiles.html')

@login_required(login_url='home')
def staff_attendance(request):
    return render(request, 'hr/staff_attendance_shift.html')

@login_required(login_url='home')
def staff_transitions(request):
    return render(request, 'hr/staff_transitions.html')

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
        
    return render(request, 'receptionist/register.html', {
        'wards': wards,
        'patients': patients,
        'available_beds' : available_beds
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
        return redirect('register_patient')  # Redirect to the main registration page/tab

@csrf_exempt
def register_p(request):
    if request.method == 'POST':
        data = request.POST
        photo = request.FILES.get('photo')
        Patient.objects.create(
            full_name=data.get('full_name'),
            date_of_birth=data.get('dob'),
            gender=data.get('gender'),
            phone=data.get('phone'),
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
            
            # Add success message if you have message framework set up
            # messages.success(request, f"Patient {patient.full_name}'s information updated successfully.")
            
        except Patient.DoesNotExist:
            # Add error message if you have message framework set up
            # messages.error(request, "Patient not found.")
            pass
            
        return redirect('register_patient')

@csrf_exempt
def schedule_appointment(request):
    if request.method == 'POST':
        patient_id = request.POST.get('patient_id')
        try:
            patient = Patient.objects.get(id=patient_id)
            Appointment.objects.create(
                patient=patient,
                department=request.POST.get('department'),
                scheduled_time=request.POST.get('scheduled_time')
            )
            messages.success(request, "Appointment scheduled successfully.")
        except Patient.DoesNotExist:
            messages.error(request, "Patient not found.")
        return redirect('register_patient')

@csrf_exempt
def refer_patient(request):
    if request.method == 'POST':
        patient_id = request.POST.get('patient_id')
        try:
            patient = Patient.objects.get(id=patient_id)
            Referral.objects.create(
                patient=patient,
                department=request.POST.get('department'),
                notes=request.POST.get('notes')
            )
            messages.success(request, "Patient referred successfully.")
        except Patient.DoesNotExist:
            messages.error(request, "Patient not found.")
        return redirect('register_patient')
    
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