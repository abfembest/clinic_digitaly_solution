from . import views
from . import accts
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('', views.home, name='home'),
    path('register', views.register, name='register'),
    path('logout', views.logout_view, name='logout'),

    ########################### Nurses URLS #################################

    path('n/home', views.nurses, name='nurse'),
    path('n/vitals', views.vitals, name='vitals'),
    path('n/nursing_actions', views.nursing_actions, name='nursing_actions'),
    path('n/reports', views.nurse_reports_dashboard, name='nurse_activity_report'),
    path('n/ivf-progress', views.nurse_view_ivf_progress, name='nurse_ivf_progress'),

    path('n/record_vitals', views.record_vitals, name='record_vitals'),
    path('n/admit_patient_nurse', views.admit_patient_nurse, name='admit_patient_nurse'),
    path('n/discharge_patient', views.discharge_patient, name='discharge_patient'),
    path('n/update_patient_status', views.update_patient_status, name='update_patient_status'),
    path('n/refer_patient', views.refer_patient, name='refer_patient'),
    path('n/save_nursing_note', views.save_nursing_note, name='nursing_note'),
    path('n/handover_log', views.handover_log, name='handover_log'),
    path('n/get_patient_details/<int:patient_id>', views.get_patient_details, name='get_patient_details'),
    path('api/generate-nurse-report/', views.generate_nurse_report, name='generate_nurse_report'),
    path('n/new_patient', views.n_register_patient, name='n_register_patient'),
    path('ajax/n_patient-info/<int:patient_id>/', views.n_get_patient_info, name='n_get_patient_info'),
    path('patients/print_card/<int:patient_id>/', views.print_patient_card, name='print_patient_card'),
    path('patients/', views.n_register_p, name='n_register_p'),


    ########################### End Nurses URLS #################################

    ########################### Doctors URLS ####################################

    # path('d/home', views.doctors, name='doctors'),
    path('d/home', views.doctors, name='doctors'),
    path('d/admit-patient', views.admit_patient_doctor, name='admit_patient_doctor'),
    path('d/consultations', views.doctor_consultation, name='doctor_consultation'),
    path('d/medical-records/', views.access_medical_records, name='access_medical_records'),
    path('d/requesttest/', views.requesttest, name='requesttest'),
    path('d/recomended_tests', views.recomended_tests, name='recomended_tests'),
    path('d/ivf/start/', views.start_ivf, name='start_ivf'),
    path('d/reports', views.doctor_report, name='doctor_report'),
    path('api/doctor/generate_report/', views.generate_doctor_report_ajax, name='generate_doctor_report_ajax'),
    path('d/test_results/<int:patient_id>/', views.test_results, name='test_results'),

    path('d/chart', views.admissions_data, name='admissions_data'),
    path('notifications/data/', views.notification_data, name='notification_data'),

    path('save-consultations', views.save_consultation, name='save_consultation'),
    path('patient-history/<int:patient_id>/', views.patient_history_ajax, name='patient_history_ajax'),
    path('add-prescription/', views.add_prescription, name='add_prescription'),
    path('save-care-plan/', views.save_care_plan, name='save_care_plan'),
    path('patient/<int:patient_id>/overview/', views.get_patient_overview, name='patient_overview'),
    path('patient/<int:patient_id>/monitor/', views.get_patient_monitor, name='patient_monitor'),
    path('submit-selection/', views.submit_test_selection, name='submit_selection'),
    path('d/doc_test_comment/<int:patient_id>/', views.doc_test_comment, name='doc_test_comment'),
    path('fetch-activity/', views.fetch_patient_activity, name='fetch_patient_activity'),

    path('ivf/update_status/', views.update_ivf_status, name='update_ivf_status'),
    path('ivf/progress/<int:record_id>/', views.get_ivf_progress, name='get_ivf_progress'),
    path('ivf/add_progress_comment/', views.add_ivf_progress_comment, name='add_ivf_progress_comment'),

    ########################### End Doctors URLS #################################

    ########################### Labs URLS ####################################

    path('l/home', views.laboratory, name='laboratory'),
    path('l/test_entry', views.lab_test_entry, name='lab_test_entry'),
    path('l/internal_logs', views.lab_internal_logs, name='lab_internal_logs'),
    path('l/ivf-progress', views.lab_view_ivf_progress, name='lab_ivf_progress'),
    path('l/reports', views.lab_activity_report, name='lab_activity_report'),
    
    path('lab/patient-info/<int:patient_id>/', views.get_patient_info, name='get_patient_info'),
    path('l/test_details/<int:patient_id>/', views.test_details, name='test_details'),
    path('ajax/lab-log-detail/', views.lab_log_detail_ajax, name='lab_log_detail_ajax'),
    path('labtests/submit/<int:patient_id>/', views.submit_test_results, name='submit_test_results'),
    path('lab/generate-report/', views.generate_lab_report, name='generate_lab_report'),

    ########################### End Lab URLS ####################################

    ########################### ACCTS URLS ####################################

    path('a/home', accts.accounts, name='accounts'),
    path('a/payment_tracker', accts.payment_tracker_view, name="patient_payment_tracker"),
    path('api/patients/', accts.patient_list_api, name='patient_list_api'),
    path('api/patients/<int:patient_id>/financial-details/', accts.get_patient_financial_details, name='patient_financial_details'),
    path('accounts/income-expenditure/', accts.income_expenditure_view, name='institution_financials'),

    # path('a/payment_tracker', views.patient_payment_tracker, name='patient_payment_tracker'),
    # path('a/financials', views.institution_financials, name='institution_financials'),
    path('a/financial_reports', accts.financial_reports, name='financial_reports'),
    path('a/budget-planning', accts.budget_planning, name='budget_planning'),
    path('budget-analytics', accts.budget_analytics, name='budget_analytics'),
    path('budget/delete/<int:budget_id>', accts.delete_budget, name='delete_budget'),
    path('export_budget_data', accts.export_budget_data, name='export_budget_data'),
    path('a/reports', accts.accounting_activity_report, name='acct_report'),
    path('generate-activity-report/', accts.generate_accounting_report, name='generate_accounting_report'),

    ########################### END ACCTS URLS ####################################

    ########################### HR URLS ####################################

    path('hr/home', views.hr, name='hr'),
    path('hr/staff-profiles', views.staff_profiles, name='staff_profiles'),
    path('hr/attendance-shifts', views.staff_attendance_list, name='staff_attendance_shift'),
    path('hr/staff_transitions', views.staff_transitions, name='staff_transitions'),
    path('hr/reports', views.hr_act_report, name='hr_report'),

    path('staff/<int:staff_id>/edit/', views.edit_staff_profile, name='edit_staff_profile'),
    path('staff/<int:staff_id>/change-password/', views.change_staff_password, name='change_staff_password'),
    path('attendance/record/', views.record_attendance_view, name='record_attendance'),
    path('shift/assign/', views.assign_shift_view, name='assign_shift'),
    path('activity-details/<str:activity_type>/<int:id>/', views.get_hr_activity_detail, name='get_hr_activity_detail'),

    ########################### End HR URLS ####################################

    ########################### Receptionist URLS #################################
    path('r/home', views.receptionist, name='receptionist'),
    path('r/new_patient', views.register_patient, name='register_patient'),
    path('r/reports/', views.receptionist_activity_report, name='receptionist_activity_report'),
    path('generate-activity-report/', views.generate_activity_report, name='generate_activity_report'),
    path('patient_file/', views.patient_file_page, name='patient_file_page'),
    path('ajax_patient_search/', views.ajax_patient_search, name='ajax_patient_search'),


    path('receptionist/register/submit', views.register_p, name='register_p'),
    path('receptionist/admit', views.admit_patient, name='admit_patient'),
    path('receptionist/update', views.update_patient_info, name='update_patient_info'),
    path('receptionist/schedule', views.schedule_appointment, name='schedule_appointment'),
    path('receptionist/refer', views.refer_patient, name='refer_patient'),

    path('ajax/patient-info/<int:patient_id>/', views.get_patient_info, name='get_patient_info'),
    ########################### Receptionist URLS #################################

    # path('d/monitoring/', views.monitoring, name='monitoring'),
    # path('d/home', views.chart_view, name='chart_view'),
    # path('request-tests/', views.request_tests, name='request_tests'),
    # path('d/testresults/', views.waitinglist, name='testresults'),

    # path('doctors/filtered-records/', views.filter_activities, name='filtered_records'),
    
    


    #path('doctors/individual', views.individual_record, name='individual_record'),
    #path('doctors/all', views.all_record, name='all_record'),


   
    

    path('ae/', views.ae, name='ae'),

    path('p/home', views.pharmacy, name='pharmacy'),
    path('p/review', views.review_prescriptions, name='review_prescriptions'),
    path('p/medication', views.dispense_medications, name='dispense_medications'),
    path('p/inventory', views.manage_inventory, name='manage_inventory'),
    path('p/reorder_alerts', views.reorder_alerts, name='reorder_alerts'),

    path('inventory/', views.inventory, name='inventory'),

    path('ad/home', views.hms_admin, name='hms_admin'),
    path('ad/operations', views.director_operations, name='director_operations'),
    path('ad/acknowledge_alert/<int:alert_id>/', views.acknowledge_alert, name='acknowledge_alert'),
    path('ad/approve_discharge/<int:d_id>/', views.approve_discharge, name='approve_discharge'),
    path('ad/approve_expense/<int:exp_id>/', views.approve_expense, name='approve_expense'),
    path('ad/reports', views.director_reports, name='director_reports'),

    path('nurses/report/', views.nurses_report, name='nurses_report'),
    path('nurses/report/api/', views.nurses_report_api, name='nurses_report_api'),

    path('lab/report/', views.lab_report_view, name='lab_reports'),
    path('api/analytics/', views.lab_analytics_api, name='lab_analytics_api'),

    path('report/', views.account_report, name='account_report'),
    path('report/api/', views.account_report_api, name='account_report_api'),

    path('hr/report/', views.hr_report, name='hr_reports'),

    path('ad/accounts', views.user_accounts, name='user_accounts'),
    path('ad/user_accounts', views.user_accounts, name='user_accounts'),

    # User management endpoints with user_id as URL parameter
    path('user/<int:user_id>/toggle-status/', views.toggle_user_status, name='toggle_user_status'),
    path('user/<int:user_id>/edit/', views.edit_user_endpoint, name='edit_user'),
    path('user/<int:user_id>/set-password/', views.set_user_password_endpoint, name='set_user_password'),
    path('user/<int:user_id>/delete/', views.delete_user_endpoint, name='delete_user'),
    
    # Add user endpoint (no user_id needed)
    path('user/add/', views.add_user_endpoint, name='add_user'),

    path('reports/departments/', views.department_reports_view, name='doctor_reports'),

    # AJAX endpoint to fetch report types for a selected department
    path('ajax/get_department_report_types/', views.get_department_report_types, name='get_department_report_types'),

    # AJAX endpoint to generate the actual department report
    path('ajax/generate_department_report/', views.generate_department_report, name='generate_department_report'),
    path('ad/receptionist_report', views.receptionist_reports, name='receptionist_reports'),
    
    path('admin/users/export/csv/', views.export_users_csv_view, name='export_users_csv'),
    path('admin/users/export/pdf/', views.export_users_pdf_view, name='export_users_pdf'),
    
    path('n/get_patient_details/<int:patient_id>', views.get_patient_details, name='get_patient_details'),


    # path('ajax/get-available-beds/', views.get_available_beds, name='get_available_beds'),
    
    path('chart', views.chart_view, name='chart_view'),


    #graph
    path('mainchart', views.chart2, name='chart2'),
    

]+ static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
