from django.contrib.auth import logout
from django.shortcuts import redirect
from .models import Staff
from functools import wraps

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
