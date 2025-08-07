from django.contrib.auth import logout
from django.shortcuts import redirect
from .models import Staff
from functools import wraps


#===================================
#       ROLE NURSE
#===================================

def check_nurse_role(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        try:
            staff = Staff.objects.get(user=request.user)
            if staff.role.lower() != 'nurse':
                logout(request)
                return redirect('home')
        except Staff.DoesNotExist:
            logout(request)
            return redirect('home')

        return view_func(request, *args, **kwargs)
    return _wrapped_view

#===================================
#       ROLE DOCTOR
#===================================

def check_doctor_role(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        try:
            staff = Staff.objects.get(user=request.user)
            if staff.role.lower() != 'doctor':
                logout(request)
                return redirect('home')
        except Staff.DoesNotExist:
            logout(request)
            return redirect('home')

        return view_func(request, *args, **kwargs)
    return _wrapped_view


#===================================
#       ROLE DOCTOR
#===================================

def check_lab_role(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        try:
            staff = Staff.objects.get(user=request.user)
            if staff.role.lower() != 'lab':
                logout(request)
                return redirect('home')
        except Staff.DoesNotExist:
            logout(request)
            return redirect('home')

        return view_func(request, *args, **kwargs)
    return _wrapped_view

#===================================
#       ROLE Receptionist
#===================================

def check_receiption_role(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        try:
            staff = Staff.objects.get(user=request.user)
            if staff.role.lower() != 'receptionist':
                logout(request)
                return redirect('home')
        except Staff.DoesNotExist:
            logout(request)
            return redirect('home')

        return view_func(request, *args, **kwargs)
    return _wrapped_view



#===================================
#       ROLE Account
#===================================

def check_account_role(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        try:
            staff = Staff.objects.get(user=request.user)
            if staff.role.lower() != 'account':
                logout(request)
                return redirect('home')
        except Staff.DoesNotExist:
            logout(request)
            return redirect('home')

        return view_func(request, *args, **kwargs)
    return _wrapped_view


#===================================
#       ROLE Admin
#===================================

def check_admin_role(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        try:
            staff = Staff.objects.get(user=request.user)
            if staff.role.lower() != 'admin':
                logout(request)
                return redirect('home')
        except Staff.DoesNotExist:
            logout(request)
            return redirect('home')

        return view_func(request, *args, **kwargs)
    return _wrapped_view