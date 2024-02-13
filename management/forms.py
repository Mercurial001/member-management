from .models import Gender, Barangay, Leader, Member, Cluster, Barangay, Sitio, Registrants
from django.forms import Select, DateInput, Textarea, TextInput, ModelForm, SelectMultiple, NumberInput, EmailInput, FileInput
from django.contrib.auth.forms import UserCreationForm
from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.contrib.auth import password_validation
from django.utils.translation import gettext_lazy as _


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
        fields = ['name', 'gender', 'age', 'image']
        widgets = {
            'name': TextInput(attrs={
                'class': "add-leader-field",
            }),
            'gender': Select(attrs={
                'class': "add-leader-field-min",
            }),
            'age': NumberInput(attrs={
                'class': "add-leader-field-min",
            }),
        }


class LeaderRegistrationEditForm(ModelForm):
    class Meta:
        model = Leader
        fields = ['name', 'brgy', 'gender', 'age', 'image']
        widgets = {
            'name': TextInput(attrs={
                'class': "edit-leader-field",
            }),
            'gender': Select(attrs={
                'class': "edit-leader-field",
            }),
            'brgy': Select(attrs={
                'class': "edit-leader-field",
                'id': 'leader-edit-brgys',
            }),
            'age': NumberInput(attrs={
                'class': "edit-leader-field",
            }),
        }


class MemberRegistrationForm(ModelForm):
    class Meta:
        model = Member
        fields = ['name', 'gender', 'age', 'image']
        widgets = {
            'name': TextInput(attrs={
                'class': "add-new-member-in-leader-field",
            }),
            'gender': Select(attrs={
                'class': "add-new-member-in-leader-field-min",
            }),
            'age': NumberInput(attrs={
                'class': "add-new-member-in-leader-field-min",
            }),
        }


class MemberRegistrationEditForm(ModelForm):
    class Meta:
        model = Member
        fields = ['name', 'gender', 'age', 'brgy', 'image']
        widgets = {
            'name': TextInput(attrs={
                'class': "edit-leader-field",
            }),
            'gender': Select(attrs={
                'class': "edit-leader-field",
            }),
            'age': NumberInput(attrs={
                'class': "edit-leader-field",
            }),
            'brgy': Select(attrs={
                'class': "edit-leader-field",
                'id': 'member-edit-brgys',
            }),
        }


class AddMemberRegistrationForm(ModelForm):
    class Meta:
        model = Member
        fields = ['name', 'gender', 'age', 'image']
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


# Added 2/9/2024 for Version 2


class RegistrantsForm(ModelForm):
    password1 = forms.CharField(
        label=_("Password"),
        strip=False,
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password',
                                          'class': 'registration-field',
                                          'placeholder': 'Password'}),
        help_text=password_validation.password_validators_help_text_html(),
    )
    password2 = forms.CharField(
        label=_("Password confirmation"),
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password',
                                          'class': 'registration-field',
                                          'placeholder': 'Confirm Password'}),
        strip=False,
    )

    class Meta:
        model = Registrants
        fields = ['username', 'name', 'email', 'brgy', 'age', 'gender', 'image']

        def clean_email(self):
            email = self.cleaned_data.get('email')
            if not email or '@' not in email:
                raise ValidationError('Invalid Email Format')
            return email

        widgets = {
            'brgy': Select(attrs={
                'class': "registration-field",
                'id': 'registration-brgy-field',
            }),
            'username': TextInput(attrs={
                'class': "registration-field",
                'id': 'registration-username-field',
            }),
            'name': TextInput(attrs={
                'class': "registration-field",
                'id': 'registration-full-name-field',
            }),
            'email': EmailInput(attrs={
                'class': "registration-field",
                'id': 'registration-email-field',
            }),
            'age': NumberInput(attrs={
                'class': "registration-field",
                'id': 'registration-age-field',
            }),
            'gender': Select(attrs={
                'class': "registration-field",
                'id': 'registration-gender-field',
            }),
            'image': FileInput(attrs={
                'class': "registration-field",
            }),
        }
