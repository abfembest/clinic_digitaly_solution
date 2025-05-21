from django.contrib import admin
from .models import (
    Ward, Bed, Patient, Appointment, Referral, Admission,
    HandoverLog, Shift, TaskAssignment, EmergencyAlert,
    MedicalRecord, Profile, Vitals, NursingNote, Consultation, Prescription, LabTest, LabTestType, TestRequest, CarePlan, LabResultFile
)

admin.site.register(Ward)
admin.site.register(Bed)
admin.site.register(Patient)
admin.site.register(Appointment)
admin.site.register(Referral)
admin.site.register(Admission)
admin.site.register(HandoverLog)
admin.site.register(Shift)
admin.site.register(TaskAssignment)
admin.site.register(EmergencyAlert)
admin.site.register(MedicalRecord)
admin.site.register(Profile)
admin.site.register(Vitals)
admin.site.register(NursingNote)
admin.site.register(Consultation)
admin.site.register(Prescription)
admin.site.register(LabTest)
admin.site.register(LabTestType)
admin.site.register(TestRequest)
admin.site.register(CarePlan)
admin.site.register(LabResultFile)