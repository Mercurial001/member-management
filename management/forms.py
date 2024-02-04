from .models import Gender, Barangay, Leader, Member, Cluster, Barangay, Sitio
from django.forms import Select, DateInput, Textarea, TextInput, ModelForm, SelectMultiple, NumberInput
from django.contrib.auth.forms import UserCreationForm
from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError


class AddSitioForm(ModelForm):
    class Meta:
        model = Sitio
        fields = ['name', 'brgy']
        widgets = {
            'name': TextInput(attrs={
                'class': "add-sitio-field",
                'placeholder': 'Sitio Name'
            }),
            'brgy': Select(attrs={
                'class': "add-sitio-field",
                'placeholder': 'Barangay Name'
            }),
        }


class ChangeBarangayNameForm(ModelForm):
    class Meta:
        model = Barangay
        fields = ['brgy_name', 'brgy_voter_population']
        widgets = {
            'brgy_name': TextInput(attrs={
                'class': "brgy-profile-edit-field",
            }),
            'brgy_voter_population': NumberInput(attrs={
                'class': "brgy-profile-edit-field",
            }),
        }


class LeaderRegistrationForm(ModelForm):
    class Meta:
        model = Leader
        fields = ['name', 'gender', 'age']
        widgets = {
            'name': TextInput(attrs={
                'class': "add-leader-field",
            }),
            'gender': Select(attrs={
                'class': "add-leader-field",
            }),
            'age': NumberInput(attrs={
                'class': "add-leader-field",
            }),
        }


class MemberRegistrationForm(ModelForm):
    class Meta:
        model = Member
        fields = ['name', 'gender', 'age']


class AddMemberRegistrationForm(ModelForm):
    class Meta:
        model = Member
        fields = ['name', 'gender', 'age']
        widgets = {
            'name': TextInput(attrs={
                'class': "add-member-field",
            }),
            'gender': Select(attrs={
                'class': "add-member-field-min",
            }),
            'age': NumberInput(attrs={
                'class': "add-member-field-min",
            }),
        }


class BarangayForm(ModelForm):
    class Meta:
        model = Barangay
        fields = ['brgy_name', 'brgy_voter_population', 'lat', 'long']
        widgets = {
            'brgy_name': TextInput(attrs={
                'class': "add-brgy-field",
                'placeholder': 'Barangay Name'
            }),
            'brgy_voter_population': NumberInput(attrs={
                'class': "add-brgy-field",
                'placeholder': 'Barangay Voter Population'
            }),
            'lat': NumberInput(attrs={
                'class': "add-brgy-field",
                'placeholder': 'Barangay Latitude'
            }),
            'long': NumberInput(attrs={
                'class': "add-brgy-field",
                'placeholder': 'Barangay Latitude'
            }),
        }
