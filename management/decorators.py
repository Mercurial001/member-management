from django.shortcuts import redirect
from django.http import HttpResponseRedirect, HttpResponseForbidden
from django.contrib.auth.models import User
from functools import wraps
from .models import Member, Leader


def authenticated_user(view_func):
    def wrapper_func(request, *args, **kwargs):
        if request.user.groups.filter(name='Admin').exists() and request.user.groups.filter(name='Leaders').exists():
            return redirect('homepage')
        elif request.user.groups.filter(name='Leaders').exists():
            user_object = User.objects.get(username=request.user)
            leader_user = Leader.objects.get(user=user_object)
            return redirect('profile-leader', name=leader_user.name, username=request.user)
        elif request.user.groups.filter(name='Members').exists():
            user_object = User.objects.get(username=request.user)
            member_user = Member.objects.get(user=user_object)
            return redirect('profile-member', name=member_user.name, username=request.user)
        else:
            return view_func(request, *args, **kwargs)
    return wrapper_func


# def authenticated_user(view_func):
#     def wrapper_func(request, *args, **kwargs):
#         if request.user.is_authenticated:
#             return redirect('homepage')
#         elif request.user.groups.filter(name='Admin').exists()
#         and request.user.groups.filter(name='Leaders').exists():
#             return redirect('homepage')
#         elif request.user.groups.filter(name='Leaders').exists():
#             user_object = User.objects.get(username=request.user)
#             leader_user = Leader.objects.get(user=user_object)
#             return redirect('profile-leader', name=leader_user.name, username=request.user)
#         elif request.user.groups.filter(name='Members').exists():
#             user_object = User.objects.get(username=request.user)
#             member_user = Member.objects.get(user=user_object)
#             return redirect('profile-member', name=member_user.name, username=request.user)
#         else:
#             return view_func(request, *args, **kwargs)
#     return wrapper_func



def allowed_users(allowed_roles=[]):
    def decorator(view_func):
        def wrapper_func(request, *args, **kwargs):
            group = None
            if request.user.groups.exists():
                group = request.user.groups.all()[0].name
            if group in allowed_roles:
                return view_func(request, *args, **kwargs)
            elif group == 'Admin':
                return view_func(request, *args, **kwargs)
            else:
                return HttpResponseForbidden("You don't have permission to access this page.")
        return wrapper_func
    return decorator
