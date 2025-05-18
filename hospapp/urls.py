from . import views
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('', views.home, name='home'),
    path('register', views.register, name='register'),
    path('logout', views.logout_view, name='logout'),

    path('n/home', views.nurses, name='nurse'),
    path('n/bed_ward_management', views.bed_ward_management_view, name='nursing_ward_actions'),
    path('n/admit_patient_nurse', views.admit_patient_nurse, name='admit_patient_nurse'),
    path('n/assign_ward_bed', views.assign_ward_bed, name='assign_ward_bed'),
    path('n/discharge_patient', views.discharge_patient, name='discharge_patient'),
    path('n/update_patient_status', views.update_patient_status, name='update_patient_status'),
    path('n/get_patient_details/<int:patient_id>', views.get_patient_details, name='get_patient_details'),
    path('n/vitals', views.vitals, name='vitals'),
    path('n/record_vitals', views.record_vitals, name='record_vitals'),
    path('n/nursing_notes', views.nursing_notes, name='nursing_notes'),
    path('n/save_nursing_notes', views.save_nursing_note, name='save_nursing_note'),

    path('d/home', views.doctors, name='doctors'),
    path('d/consultations', views.doctor_consultation, name='doctor_consultation'),
    path('save-consultations', views.save_consultation, name='save_consultation'),
    path('patient-history/<int:patient_id>/', views.patient_history_ajax, name='patient_history_ajax'),
    path('add-prescription/', views.add_prescription, name='add_prescription'),
    path('request-tests/', views.request_tests, name='request_tests'),
    path('save-care-plan/', views.save_care_plan, name='save_care_plan'),
    path('d/medical-records/', views.access_medical_records, name='access_medical_records'),
    path('patient/<int:patient_id>/overview/', views.get_patient_overview, name='patient_overview'),
    path('patient/<int:patient_id>/monitor/', views.get_patient_monitor, name='patient_monitor'),
    path('d/monitoring/', views.monitoring, name='monitoring'),

    path('ae/', views.ae, name='ae'),

    path('l/home', views.laboratory, name='laboratory'),
    path('l/test_entry', views.lab_test_entry, name='lab_test_entry'),
    path('l/upload_result', views.lab_result_upload, name='lab_result_upload'),
    path('l/internal_logs', views.lab_internal_logs, name='lab_internal_logs'),

    path('p/home', views.pharmacy, name='pharmacy'),
    path('p/review', views.review_prescriptions, name='review_prescriptions'),
    path('p/medication', views.dispense_medications, name='dispense_medications'),
    path('p/inventory', views.manage_inventory, name='manage_inventory'),
    path('p/reorder_alerts', views.reorder_alerts, name='reorder_alerts'),

    path('a/home', views.accounts, name='accounts'),
    path('a/payment_tracker', views.patient_payment_tracker, name='patient_payment_tracker'),
    path('a/financials', views.institution_financials, name='institution_financials'),
    path('a/financial_reports', views.financial_reports, name='financial_reports'),
    path('a/budget_planning', views.budget_planning, name='budget_planning'),

    path('hr/home', views.hr, name='hr'),
    path('hr/staff_profile', views.staff_profiles, name='staff_profiles'),
    path('hr/staff_attendance', views.staff_attendance, name='staff_attendance_shift'),
    path('hr/staff_transitions', views.staff_transitions, name='staff_transitions'),
    path('hr/staff_certifications', views.staff_certifications, name='staff_certifications'),

    path('inventory/', views.inventory, name='inventory'),

    path('ad/home', views.hms_admin, name='hms_admin'),
    path('ad/operations', views.director_operations, name='director_operations'),
    path('ad/reports', views.director_reports, name='director_reports'),
    path('ad/accounts', views.user_accounts, name='user_accounts'),

    path('r/home', views.receptionist, name='receptionist'),
    path('r/new_patient', views.register_patient, name='register_patient'),
    path('register_p', views.register_p, name='register_p'),
    path('admit/', views.admit_patient, name='admit_patient'),
    path('update', views.update_patient_info, name='update_patient_info'),
    path('schedule', views.schedule_appointment, name='schedule_appointment'),
    path('refer', views.refer_patient, name='refer_patient'),
    path('ajax/patient-info/<int:patient_id>/', views.get_patient_info, name='get_patient_info'),

]+ static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
