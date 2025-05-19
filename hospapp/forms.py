from django import forms
from .models import Patient, Admission, Ward, Bed, LabTest

class PatientForm(forms.ModelForm):
    class Meta:
        model = Patient
        fields = '__all__'
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
            'gender': forms.Select(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={
                'class': 'form-control form-control-sm',
                'rows': 2
            }),
        }

    def __init__(self, *args, **kwargs):
        super(PatientForm, self).__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if field_name != 'address' and not isinstance(field.widget, forms.FileInput):
                field.widget.attrs.update({'class': 'form-control form-control-sm'})

class AdmissionForm(forms.ModelForm):
    class Meta:
        model = Admission
        fields = [
            'patient',
            'admission_date',
            'ward',
            'bed',
            'doctor_assigned',
            'status',
            'discharge_date',
            'discharge_notes'
        ]
        widgets = {
            'admission_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control form-control-sm'}),
            'discharge_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control form-control-sm'}),
            'discharge_notes': forms.Textarea(attrs={'rows': 2, 'class': 'form-control form-control-sm'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            if not isinstance(self.fields[field].widget, (forms.CheckboxInput, forms.Textarea)):
                self.fields[field].widget.attrs.update({'class': 'form-control form-control-sm'})


class WardForm(forms.ModelForm):
    class Meta:
        model = Ward
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control form-control-sm'})
        }

class LabTestForm(forms.ModelForm):
    class Meta:
        model = LabTest
        fields = ['test_type', 'sperm_count', 'motility', 'blood_type', 'notes', 'hormone', 'hormone_level',
                  'pregnancy_result', 'infection_type', 'infection_result']
        widgets = {
            'test_type': forms.HiddenInput(),
            'notes': forms.Textarea(attrs={'rows':2}),
        }

# class BedForm(forms.ModelForm):
#     class Meta:
#         model = Bed
#         fields = ['ward', 'bed_number', 'is_occupied']
#         widgets = {
#             'ward': forms.Select(attrs={'class': 'form-control form-control-sm'}),
#             'bed_number': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
#             'is_occupied': forms.CheckboxInput(attrs={'class': 'form-check-input'})
#         }
