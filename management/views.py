from django.shortcuts import render, redirect
from .forms import LeaderRegistrationForm, MemberRegistrationForm, BarangayForm, AddMemberRegistrationForm, \
    ChangeBarangayNameForm, AddSitioForm, LeaderRegistrationEditForm, MemberRegistrationEditForm, RegistrantsForm, \
    ChangePasswordForm, ForgotPasswordForm, ChangeSitioDetailsForm, TotalVoterPopulationEditForm
from django.contrib import messages
from .models import Member, Barangay, Leader, Cluster, AddedLeaders, AddedMembers, Sitio, Individual, Registrants, \
    Notification, EmailMessage, PasswordResetToken, TotalVoterPopulation, QRCodeAttendance, ActivityLog, \
    LeaderConnectMemberRequest, LeadersRequestConnect
from django.db.models import Sum, Count, Q
from django.contrib.auth.models import Group, User
from django.contrib.auth.hashers import make_password
from django.http import HttpResponseRedirect
import qrcode
from cryptography.fernet import Fernet
from django.core.signing import Signer
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
import json
import folium
from django.db import models
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from .decorators import authenticated_user
from django.utils import timezone
from datetime import datetime, timedelta
from datetime import date
from django.core.serializers import serialize, deserialize
from django.core.files.storage import default_storage
import os
from django.contrib.humanize.templatetags.humanize import naturaltime
from django.template.loader import render_to_string
from django.core.mail import send_mail
from .decorators import authenticated_user, allowed_users
from django.contrib.auth.tokens import PasswordResetTokenGenerator
import six
import pdfkit


@login_required(login_url='login')
@allowed_users(allowed_roles=['Admin'])
def homepage(request):
    activities = ActivityLog.objects.order_by('-date_time')[:12]
    member_brgy = Member.objects.exclude(name=None).values('brgy__brgy_name').distinct()
    leader_brgy = Leader.objects.exclude(name=None).values('brgy__brgy_name').distinct()

    user = request.user
    logged_user = Individual.objects.get(user__username=user)

    # First let's retrieve the search field in the base.html
    search_engine_field_query = request.GET.get('search')

    # Now that we have retrieve the search engine field in the base.html, it's time to delve into the login of it

    if search_engine_field_query:
        search_engine_result_member = Member.objects.filter(
            Q(name__icontains=search_engine_field_query)
            | Q(brgy__brgy_name__icontains=search_engine_field_query) 
            | Q(sitio__name__icontains=search_engine_field_query))
        search_engine_result_leader = Leader.objects.filter(
            Q(name__icontains=search_engine_field_query) 
            | Q(brgy__brgy_name__icontains=search_engine_field_query) 
            | Q(sitio__name__icontains=search_engine_field_query))

        search_result_count_member = search_engine_result_member.annotate(count=Count('name'))
        search_result_sum_member = search_result_count_member.aggregate(sum=Sum('count'))['sum']

        search_result_count_leader = search_engine_result_leader.annotate(count=Count('name'))
        search_result_sum_leader = search_result_count_leader.aggregate(sum=Sum('count'))['sum']

        if search_result_sum_member is None and search_result_sum_leader is None:
            total_results = 0
        elif search_result_sum_member is None and search_result_sum_leader is not None:
            search_result_sum_member = 0
            total_results = search_result_sum_member + search_result_sum_leader
        elif search_result_sum_leader is None and search_result_sum_member is not None:
            search_result_sum_leader = 0
            total_results = search_result_sum_member + search_result_sum_leader
        else:
            total_results = search_result_sum_member + search_result_sum_leader
    else:
        search_engine_result_member = []
        search_engine_result_leader = []
        total_results = []
        search_result_count_member = []
        search_result_sum_member = []
        search_result_sum_leader = []

    return render(request, 'base.html', {
        'member_brgy': member_brgy,
        'leader_brgy': leader_brgy,
        'search_engine_result_member': search_engine_result_member,
        'search_engine_result_leader': search_engine_result_leader,
        'search_engine_field_query': search_engine_field_query,
        'search_result_count_member': search_result_count_member,
        'search_result_sum_member': search_result_sum_member,
        'search_result_sum_leader': search_result_sum_leader,
        'total_results': total_results,
        'logged_user': logged_user,
        'activities': activities,
        'user': user,
    })


@login_required(login_url='login')
@allowed_users(allowed_roles=['Admin'])
def barangay_members(request, brgy_name):
    request_user = request.user
    logged_user = Individual.objects.get(user__username=request_user)

    brgy = Barangay.objects.get(brgy_name=brgy_name)
    member_brgy = Member.objects.filter(brgy__brgy_name=brgy_name)
    brgy_leader = Leader.objects.filter(brgy__brgy_name=brgy_name)
    sitios = Sitio.objects.filter(brgy__brgy_name=brgy_name)
    brgy_edit_form = ChangeBarangayNameForm(instance=brgy)

    brgy_individual_count = Individual.objects.filter(brgy=brgy).annotate(count=Count('name'))
    brgy_individual_sum = brgy_individual_count.aggregate(sum=Sum('count'))['sum']

    brgy_sitio_count = Sitio.objects.filter(brgy=brgy).annotate(count=Count('name'))
    brgy_sitio_sum = brgy_sitio_count.aggregate(sum=Sum('count'))['sum']

    brgy_cluster = Cluster.objects.filter(leader__brgy=brgy)

    if request.method == 'POST':
        form = ChangeBarangayNameForm(request.POST, instance=brgy)
        if form.is_valid():
            brgy = form.save(commit=False)
            brgy.save()
            return redirect('member-brgy', brgy_name=brgy.brgy_name)

    return render(request, 'member_brgy.html', {
        'member_brgy': member_brgy,
        'brgy_leader': brgy_leader,
        'brgy': brgy,
        'brgy_edit_form': brgy_edit_form,
        'sitios': sitios,
        'brgy_individual_sum': brgy_individual_sum,
        'brgy_sitio_sum': brgy_sitio_sum,
        'brgy_cluster': brgy_cluster,
        'logged_user': logged_user,
    })


def sitio_profile(request, id):
    request_user = request.user
    logged_user = Individual.objects.get(user__username=request_user)

    sitio = Sitio.objects.get(id=id)
    sitio_members = Member.objects.filter(sitio=sitio)
    sitio_leaders = Leader.objects.filter(sitio=sitio)

    edit_sitio_details_form = ChangeSitioDetailsForm(instance=sitio)

    sitio_individual_count = Individual.objects.filter(sitio=sitio).annotate(count=Count('name'))
    sitio_individual_sum = sitio_individual_count.aggregate(sum=Sum('count'))['sum']

    if request.method == 'POST':
        form = ChangeSitioDetailsForm(request.POST, instance=sitio)
        if form.is_valid():
            sitio_edited = form.save(commit=False)
            sitio_edited.save()
            return redirect('sitio-profile', id=sitio.id)
    return render(request, 'sitio_profile.html', {
        'sitio_members': sitio_members,
        'sitio_leaders': sitio_leaders,
        'sitio': sitio,
        'edit_sitio_details_form': edit_sitio_details_form,
        'sitio_individual_sum': sitio_individual_sum,
        'logged_user': logged_user,
    })


def get_marker_color(percentage):
    if percentage is not None:
        return 'green' if percentage > 55 else 'red'
    return 'gray'


@login_required(login_url='login')
@allowed_users(allowed_roles=['Admin'])
def dashboard(request):
    request_user = request.user
    logged_user = Individual.objects.get(user__username=request_user)

    # Percentage Data
    percentage_data = Individual.objects.values('brgy__brgy_name', 'brgy__brgy_voter_population').annotate(
        member_popu_count=Count('name')
    )

    absolute_pop = [entry['brgy__brgy_voter_population'] for entry in percentage_data]
    population = [entry['member_popu_count'] for entry in percentage_data]

    member_percentage_population = [round(((pop / abs_pop) * 100)) for abs_pop, pop in zip(absolute_pop, population)]
    # For Graph Data
    member_brgy_graph_data = Individual.objects.values('brgy__brgy_name').annotate(member_count=Count('name'))
    brgys = [entry['brgy__brgy_name'] for entry in member_brgy_graph_data]
    brgy_member_count = [entry['member_count'] for entry in member_brgy_graph_data]

    member_per_brgy_dictionary = {}
    for brgy, sum in zip(brgys, brgy_member_count):
        member_per_brgy_dictionary[brgy] = str(sum)

    member_per_brgy_dictionary = {}
    for brgy, sum in zip(brgys, brgy_member_count):
        member_per_brgy_dictionary[brgy] = str(sum)

    # Number of Barangays Data
    count_brgy = Barangay.objects.all().annotate(brgy_count=Count('brgy_name'))
    count_brgy_sum = count_brgy.aggregate(total_brgy_sum=Sum('brgy_count'))['total_brgy_sum']

    # Total Number of Members
    members_count = Member.objects.all().annotate(member_count=Count('user'))
    member_sum = members_count.aggregate(total_members=Sum('member_count'))['total_members']

    # Total Number of Leaders
    leaders_count = Leader.objects.all().annotate(leader_count=Count('user'))
    leaders_sum = leaders_count.aggregate(total_leaders=Sum('leader_count'))['total_leaders']

    # Total Number of Individuals
    individuals_count = Individual.objects.all().annotate(count=Count('user'))
    individuals_sum = individuals_count.aggregate(sum=Sum('count'))['sum']

    total_voter_population_object = TotalVoterPopulation.objects.get(id=1)
    total_voter_population = total_voter_population_object.population

    total_voter_percentage = ((individuals_sum / total_voter_population) * 100).__round__()

    # Assuming you have a queryset of Barangay objects
    barangays = Barangay.objects.filter(lat__isnull=False, long__isnull=False)

    absolute_pop_map = {entry['brgy__brgy_name']: entry['brgy__brgy_voter_population'] for entry in percentage_data}
    population_map = {entry['brgy__brgy_name']: entry['member_popu_count'] for entry in percentage_data}

    member_percentage_population_map = {
        brgy: round((population_map[brgy] / absolute_pop_map[brgy]) * 100)
        for brgy in absolute_pop_map.keys() & population_map.keys()
    }

    # Create a Folium map centered at the mean coordinates of the Barangays
    if barangays.exists():
        center_lat = barangays.aggregate(models.Avg('lat'))['lat__avg']
        center_long = barangays.aggregate(models.Avg('long'))['long__avg']
        folium_map = folium.Map(location=[center_lat, center_long], zoom_start=11.5, tiles='CartoDB dark_matter')

        for barangay in barangays:
            percentage = member_percentage_population_map.get(barangay.brgy_name)
            marker_color = get_marker_color(percentage)

            folium.Marker(
                location=[barangay.lat, barangay.long],
                popup=f"<strong>{barangay.brgy_name}</strong><br>"
                      f"Voter Population: <strong>{absolute_pop_map.get(barangay.brgy_name, 'No Available Data')}</strong><br>"
                      f"Member Percentage: <strong>{percentage if percentage is not None else 'N/A'}%</strong>",
                icon=folium.Icon(color=marker_color),
            ).add_to(folium_map)

        map_html = folium_map._repr_html_()
    else:
        map_html = None

    # if request.method == 'POST':
    #     form = TotalVoterPopulationEditForm(request.POST, instance=)

    return render(request, 'dashboard.html', {
        'brgys': brgys,
        'brgy_member_count': brgy_member_count,
        'member_percentage_population': member_percentage_population,
        'count_brgy_sum': count_brgy_sum,
        'member_sum': member_sum,
        'leaders_sum': leaders_sum,
        'member_per_brgy_dictionary': member_per_brgy_dictionary,
        'map_html': map_html,
        'population': population,
        'absolute_pop': absolute_pop,
        'member_percentage_population_map': member_percentage_population_map,
        'population_map': population_map,
        'absolute_pop_map': absolute_pop_map,
        'percentage_data': percentage_data,
        'individuals_sum': individuals_sum,
        'total_voter_population': total_voter_population,
        'total_voter_percentage': total_voter_percentage,
        'logged_user': logged_user,
    })


@login_required(login_url='login')
@allowed_users(allowed_roles=['Admin'])
def leader_cluster(request, name, username):
    request_user = request.user
    logged_user = Individual.objects.get(user__username=request_user)

    leader_user = User.objects.get(username=username)
    leader = Leader.objects.get(name=name, user=leader_user)
    leaders_cluster = Cluster.objects.get(leader=leader)
    barangays = Barangay.objects.all()
    sitios = Sitio.objects.filter(brgy=leader.brgy)
    selected_sitio = request.POST.get('added-member-sitio')

    leader_brgy_unassociated_members = Member.objects.filter(brgy=leader.brgy)

    members_brgy = [member for member in leader_brgy_unassociated_members]

    # First let's retrieve the search field in the base.html
    search_engine_field_query = request.GET.get('search')

    # Now that we have retrieve the search engine field in the base.html, it's time to delve into the login of it

    if search_engine_field_query:
        search_engine_result_member = Member.objects.filter(
            Q(name__icontains=search_engine_field_query, brgy=leader.brgy) |
            Q(sitio__name__icontains=search_engine_field_query, brgy=leader.brgy))

        search_result_count_member = search_engine_result_member.annotate(count=Count('name'))
        search_result_sum_member = search_result_count_member.aggregate(sum=Sum('count'))['sum']

        if search_result_sum_member is None:
            total_results = 0
        else:
            total_results = search_result_sum_member

    else:
        search_engine_result_member = []
        total_results = []

    brgy_members = Cluster.objects.all()
    members_b = []
    for members in brgy_members:
        for member in members.members.all():
            member_name = member.name
            if member_name not in members_b:
                members_b.append(member_name)

    unassociated_members = []
    for member in members_brgy:
        member_name = member.name
        if member_name not in members_b:
            unassociated_members.append(member)

    # Create QR Code for each user
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=2,
    )

    key = b'bSKEk2cT2V8vllCpMtQWsO2FxUVQdl3S_IHwBbEE4eQ='
    cipher_suite = Fernet(key)
    signing_key = b'Cold'
    signer = Signer(key=signing_key)

    # encrypted_username = signer.sign(leader.name) # 1st Encrypt the username # Commented 2/20/2024
    encrypted_username = signer.sign(leader.user) # 1st Encrypt the username
    data = encrypted_username.encode('utf-8') # 2 Convert encrypted_username to bytes
    encrypted_data = cipher_suite.encrypt(data) # Final

    qr.add_data(encrypted_data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    img.save(f'management/static/images/qr-codes/QR-Code-{leader.name}-{leader.brgy}-{leader.id}.png')

    member_registration_form = MemberRegistrationForm()
    edit_leader_profile_form = LeaderRegistrationEditForm(instance=leader)

    if request.method == 'POST':
        # Added for V.2, 2/10/ 2024
        edit_profile_leader_profile_form = LeaderRegistrationEditForm(request.POST, request.FILES, instance=leader)
        if edit_profile_leader_profile_form.is_valid():

            # external_data
            edit_selected_sitio = request.POST.get('leader-profile-edit-sitio')

            leader_profile = edit_profile_leader_profile_form.save(commit=False)
            if edit_selected_sitio != 'None':
                selected_sitio_edit = Sitio.objects.get(id=edit_selected_sitio)
                leader_profile.sitio = selected_sitio_edit
            else:
                leader_profile.sitio = None
            leader_profile.save()

            individual_link = Individual.objects.get(user=leader_profile.user)
            individual_link.name = leader_profile.name
            individual_link.gender = leader_profile.gender
            individual_link.age = leader_profile.age
            individual_link.brgy = leader_profile.brgy
            individual_link.sitio = leader_profile.sitio
            individual_link.image = leader_profile.image
            individual_link.save()

            # natural_time = naturaltime(notification.date_time)
            current_time = timezone.now()

            # Format the current date and time as a string
            formatted_time = current_time.strftime("%B %d, %Y")

            activity_log = ActivityLog.objects.create(
                title=f'Leader Profile Edited {leader.name}',
                content=f'Leader {leader.name} has their profile edited on {formatted_time}',
                date=timezone.now(),
                date_time=timezone.now(),
            )
            activity_log.save()

            messages.success(request, 'Editted!')
            return redirect('cluster', name=leader_profile.name, username=username)

        # Commented for V.2, 2/10/2024
        # if 'add-new-member-btn' in request.POST:
        #     form = MemberRegistrationForm(request.POST, request.FILES)
        #     if form.is_valid():
        #         member = form.save(commit=False)
        #         member.brgy = leader.brgy
        #         if selected_sitio != 'None':
        #             print(f'Sitio: {selected_sitio}')
        #             member_sitio = Sitio.objects.get(id=selected_sitio)
        #             member.sitio = member_sitio
        #         else:
        #             member.sitio = None
        #         member.save()
        #
        #         # Let's create a cluster object
        #         cluster, created = Cluster.objects.get_or_create(leader=leader)
        #         cluster.members.add(member)
        #         cluster.save()
        #
        #         member_added_obj, created = AddedMembers.objects.get_or_create(member=member.name)
        #         member_added_obj.save()
        #
        #         messages.success(request, 'Member Added')
        # elif 'edit-leader-profile-btn' in request.POST:
        #     edit_profile_leader_profile_form = LeaderRegistrationEditForm(request.POST, request.FILES, instance=leader)
        #     if edit_profile_leader_profile_form.is_valid():
        #
        #         # external_data
        #         edit_selected_sitio = request.POST.get('leader-profile-edit-sitio')
        #
        #         leader_profile = edit_profile_leader_profile_form.save(commit=False)
        #         if edit_selected_sitio != 'None':
        #             selected_sitio_edit = Sitio.objects.get(id=edit_selected_sitio)
        #             leader_profile.sitio = selected_sitio_edit
        #         else:
        #             leader_profile.sitio = None
        #         leader_profile.save()
        #         messages.success(request, 'Editted!')
        #         return redirect('cluster', name=leader_profile.name)

    return render(request, 'leader_cluster.html', {
        'leader': leader,
        'member_registration_form': member_registration_form,
        'leaders_cluster': leaders_cluster,
        'sitios': sitios,
        'edit_leader_profile_form': edit_leader_profile_form,
        'barangays': barangays,
        'brgy_members': brgy_members,
        'members_b': members_b,
        'unassociated_members': unassociated_members,
        'search_engine_result_member': search_engine_result_member,
        'search_engine_field_query': search_engine_field_query,
        'total_results': total_results,
        'logged_user': logged_user,
    })


@login_required(login_url='login')
@allowed_users(allowed_roles=['Admin'])
def add_barangay(request):
    request_user = request.user
    logged_user = Individual.objects.get(user__username=request_user)

    # member_brgy = Member.objects.exclude(name=None).values('brgy__brgy_name').distinct()
    member_brgy = Barangay.objects.all()
    brgy_add_form = BarangayForm()
    add_sitio_form = AddSitioForm()
    if request.method == 'POST':
        if 'add-brgy-form-btn' in request.POST:
            brgy_form = BarangayForm(request.POST)
            if brgy_form.is_valid():
                barangay = brgy_form.save(commit=False)
                if Barangay.objects.filter(brgy_name=barangay.brgy_name).exists():
                    # messages.error(request, 'Barangay Already Exists')
                    brgy = Barangay.objects.get(brgy_name=barangay.brgy_name)
                    brgy.brgy_voter_population = barangay.brgy_voter_population
                    brgy.lat = barangay.lat
                    brgy.long = barangay.long
                    brgy.save()
                    messages.success(request, 'Existing Barangay Updated!')
                    return redirect('add-brgy')
                else:
                    barangay.save()
                    messages.success(request, "Barangay Added"), redirect('add-brgy')
                    return redirect('add-brgy')
        elif 'add-sitio-form-btn' in request.POST:
            sitio_form = AddSitioForm(request.POST)
            if sitio_form.is_valid():
                sitio = sitio_form.save(commit=False)
                if Sitio.objects.filter(name=sitio.name).exists():
                    existing_sitio = Sitio.objects.get(name=sitio.name)
                    existing_sitio.name = sitio.name
                    existing_sitio.brgy = sitio.brgy
                    existing_sitio.save()
                    messages.success(request, 'Existing Sitio Updated'), redirect('add-brgy')
                    return redirect('add-brgy')
                else:
                    sitio.save()
                    messages.success(request, 'Sitio Successfully Added'), redirect('add-brgy')
                    return redirect('add-brgy')

    return render(request, 'add_brgy.html', {
        'brgy_add_form': brgy_add_form,
        'member_brgy': member_brgy,
        'add_sitio_form': add_sitio_form,
        'logged_user': logged_user,
    })


@login_required(login_url='login')
@allowed_users(allowed_roles=['Admin'])
def add_sitio(request):
    request_user = request.user
    logged_user = Individual.objects.get(user__username=request_user)

    sitios = Sitio.objects.all()
    sitio_form = AddSitioForm()
    if request.method == 'POST':
        form = AddSitioForm(request.POST)
        if form.is_valid():
            sitio = form.save(commit=False)
            sitio.save()

            activity_log = ActivityLog.objects.create(
                title=f'Sitio Added by {request_user}',
                content=f'{request_user} has added sitio {sitio.name} in {sitio.brgy}',
                date=timezone.now(),
                date_time=timezone.now(),
            )
            activity_log.save()
    return render(request, 'add_sitio.html', {
        'sitio_form': sitio_form,
        'sitios': sitios,
        'logged_user': logged_user,
    })


@login_required(login_url='login')
@allowed_users(allowed_roles=['Admin'])
def clusters(request):
    request_user = request.user
    logged_user = Individual.objects.get(user__username=request_user)

    barangays = Barangay.objects.all()
    leaders = {}
    for brgys in barangays:
        brgy_name = brgys.brgy_name
        if Leader.objects.filter(brgy__brgy_name=brgy_name).exists():
            leaders[Leader.objects.filter(brgy__brgy_name=brgy_name)] = brgy_name

    return render(request, 'clusters.html', {
        'leaders': leaders,
        'barangays': barangays,
        'logged_user': logged_user,
    })


@login_required(login_url='login')
@allowed_users(allowed_roles=['Admin'])
def add_leader(request):
    request_user = request.user
    logged_user = Individual.objects.get(user__username=request_user)

    leader_form = LeaderRegistrationForm()
    brgys = Barangay.objects.all()
    selected_brgy = request.GET.get('leader-brgy')
    filtered_sitios = []
    if selected_brgy:
        sitios_exist = Sitio.objects.filter(brgy__brgy_name=selected_brgy).exists()

        if sitios_exist:
            filtered_sitios = Sitio.objects.filter(brgy__brgy_name=selected_brgy)
        else:
            return JsonResponse({'message': 'No Sitio in this Barangay'})

    elif selected_brgy == '---------':
        return JsonResponse({'message': 'Please Choose a Barangay'})
    else:
        sitios_exist = False

    if request.method == 'POST':
        form = LeaderRegistrationForm(request.POST, request.FILES)
        brgy_field_value = request.POST.get('leader-brgy')
        sitio_field_value = request.POST.get('leader-sitio')
        leader_brgy = Barangay.objects.get(brgy_name=brgy_field_value)
        if form.is_valid():
            leader = form.save(commit=False)
            leader.brgy = leader_brgy

            if sitio_field_value != 'None':
                leader_sitio = Sitio.objects.get(id=sitio_field_value)
                leader.sitio = leader_sitio
            else:
                leader.sitio = None

            leader.save()

            cluster, created = Cluster.objects.get_or_create(leader=leader)
            cluster.save()

            individual, created = Individual.objects.get_or_create(
                name=leader.name,
                gender=leader.gender,
                age=leader.age,
                brgy=leader.brgy,
            )
            if leader.sitio is not None:
                individual.sitio = leader.sitio
            else:
                individual.sitio = None

            individual.save()
            # Let's create an AddedLeader object
            added_leader_obj, created = AddedLeaders.objects.get_or_create(leader=leader.name)
            added_leader_obj.save()

            messages.success(request, 'Leader Added')
    return render(request, 'add_leader.html', {
        'leader_form': leader_form,
        'filtered_sitios': filtered_sitios,
        'sitios_exist': sitios_exist,
        'brgys': brgys,
        'logged_user': logged_user,
    })


@login_required(login_url='login')
@allowed_users(allowed_roles=['Admin'])
def add_members(request):
    request_user = request.user
    logged_user = Individual.objects.get(user__username=request_user)

    member_form = AddMemberRegistrationForm()
    brgys = Barangay.objects.all()
    selected_brgy = request.GET.get('member-brgy')
    filtered_sitios = []
    filtered_leaders = []
    if selected_brgy:
        sitios_exist = Sitio.objects.filter(brgy__brgy_name=selected_brgy).exists()
        leaders_exist = Leader.objects.filter(brgy__brgy_name=selected_brgy).exists()
        if leaders_exist:
            filtered_leaders = Leader.objects.filter(brgy__brgy_name=selected_brgy)
        else:
            return JsonResponse({'message': 'No Leadrs in this Barangay'})

        if sitios_exist:
            filtered_sitios = Sitio.objects.filter(brgy__brgy_name=selected_brgy)
        else:
            return JsonResponse({'message': 'No Sitio in this Barangay'})
    elif selected_brgy == '---------':
        return JsonResponse({'message': 'Please Choose a Barangay'})
    else:
        sitios_exist = False
        leaders_exists = False

    if request.method == 'POST':
        form = AddMemberRegistrationForm(request.POST, request.FILES)
        brgy_field_value = request.POST.get('member-brgy')
        sitio_field_value = request.POST.get('member-sitio')
        leader_field_value = request.POST.get('member-leader')
        member_brgy = Barangay.objects.get(brgy_name=brgy_field_value)

        if sitio_field_value != 'None':
            member_sitio = Sitio.objects.get(id=sitio_field_value)
        else:
            member_sitio = None

        if leader_field_value != 'None':
            member_leader = Leader.objects.get(id=leader_field_value)
        else:
            member_leader = None

        if form.is_valid():
            member = form.save(commit=False)
            member.brgy = member_brgy
            member.sitio = member_sitio
            member.save()

            # Let's Assign This member to the Added Member model for some data analysis matters.
            added_member = AddedMembers.objects.create(member=member.name)
            added_member.save()

            if member_leader is not None:
                new_member = Member.objects.get(name=member.name, id=member.id)
                existing_leader, created = Cluster.objects.get_or_create(leader=member_leader)
                existing_leader.members.add(new_member)
                existing_leader.save()

    return render(request, 'add_member.html', {
        'member_form': member_form,
        'brgys': brgys,
        'filtered_sitios': filtered_sitios,
        'filtered_leaders': filtered_leaders,
        'selected_brgy': selected_brgy,
        'sitios_exist': sitios_exist,
        'logged_user': logged_user,
    })


@login_required(login_url='login')
@allowed_users(allowed_roles=['Admin'])
def member_profile(request, name, id):
    request_user = request.user
    logged_user = Individual.objects.get(user__username=request_user)

    member = Member.objects.get(id=id, name=name)
    members = Cluster.objects.values('members__name')
    leaders = Leader.objects.filter(brgy=member.brgy)
    get_member_leader = Cluster.objects.filter(members__name=member.name)
    no_leader_member_list = [name['members__name'] for name in members]

    sitios = Sitio.objects.filter(brgy=member.brgy)

    # Create QR Code for each user
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=2,
    )

    key = b'bSKEk2cT2V8vllCpMtQWsO2FxUVQdl3S_IHwBbEE4eQ='
    cipher_suite = Fernet(key)
    signing_key = b'Cold'
    signer = Signer(key=signing_key)

    # Commented 2/20/2024 encrypted_username = signer.sign(member.name) # 1st Encrypt the username
    encrypted_username = signer.sign(member.user) # 1st Encrypt the username
    data = encrypted_username.encode('utf-8') # 2 Convert encrypted_username to bytes
    encrypted_data = cipher_suite.encrypt(data) # Final

    qr.add_data(encrypted_data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    img.save(f'management/static/images/qr-codes/QR-Code-{member.name}-{member.brgy}-{member.id}.png')
    edit_member_detail_form = MemberRegistrationEditForm(instance=member)
    if request.method == 'POST':
        form = MemberRegistrationEditForm(request.POST, request.FILES, instance=member)
        if form.is_valid():
            edited_member = form.save(commit=False)

            # External Data
            selected_sitio = request.POST.get('member-edit-sitio')
            if selected_sitio != 'None':
                member_sitio = Sitio.objects.get(id=selected_sitio)
                edited_member.sitio = member_sitio
            else:
                edited_member.sitio = None
            edited_member.save()

            individual_link = Individual.objects.get(user=edited_member.user)
            individual_link.name = edited_member.name
            individual_link.gender = edited_member.gender
            individual_link.age = edited_member.age
            individual_link.brgy = edited_member.brgy
            individual_link.sitio = edited_member.sitio
            individual_link.image = edited_member.image
            individual_link.save()

            current_time = timezone.now()
            # Format the current date and time as a string
            formatted_time = current_time.strftime("%B %d, %Y")

            activity_log = ActivityLog.objects.create(
                title=f"{request_user} has Edited Member {member.name}'s details",
                content=f"{request_user} has edited {member.name}'s details on {formatted_time}",
                date=timezone.now(),
                date_time=timezone.now(),
            )
            activity_log.save()

            return redirect('member-profile', name=edited_member.name, id=member.id)

    return render(request, 'member_profile.html', {
        'member': member,
        'no_leader_member_list': no_leader_member_list,
        'leaders': leaders,
        'encrypted_data': encrypted_data,
        'get_member_leader': get_member_leader,
        'edit_member_detail_form': edit_member_detail_form,
        "sitios": sitios,
        'logged_user': logged_user,
    })


@login_required(login_url='login')
@allowed_users(allowed_roles=['Admin'])
def reports(request):
    request_user = request.user
    logged_user = Individual.objects.get(user__username=request_user)

    return render(request, 'reports.html', {
        'logged_user': logged_user,
    })


def members_per_brgy_report(request):
    request_user = request.user
    logged_user = Individual.objects.get(user__username=request_user)

    member_per_brgy_list = {}
    member_filtered_per_brgy_list = {}

    brgys = Barangay.objects.all()
    member_list = []
    members = Individual.objects.all()

    selected_brgy = request.GET.get('selected-brgy')
    if selected_brgy:  # Check if a date is selected
        members_filter = Individual.objects.filter(brgy=selected_brgy)
        the_brgy = Barangay.objects.get(id=selected_brgy)

        for member in members_filter:
            member_brgy = member.brgy

            if member_brgy not in member_filtered_per_brgy_list:
                member_filtered_per_brgy_list[member_brgy] = [(
                    member,
                    round((1 / member.brgy.brgy_voter_population) * 100),
                    member.brgy.brgy_voter_population,
                )]
            else:
                member_filtered_per_brgy_list[member_brgy].append((
                    member,
                    round((1 / member.brgy.brgy_voter_population) * 100),
                    member.brgy.brgy_voter_population,
                ))
    else:
        the_brgy = None

    for member in members:
        member_brgy = member.brgy
        if member_brgy not in member_per_brgy_list:
            member_per_brgy_list[member_brgy] = [(
                member,
                round((1 / member.brgy.brgy_voter_population) * 100),
                member.brgy.brgy_voter_population,
            )]
        else:
            member_per_brgy_list[member_brgy].append((
                member,
                round((1 / member.brgy.brgy_voter_population) * 100),
                member.brgy.brgy_voter_population,
            ))

    return render(request, 'member_per_brgy_report.html', {
        'member_per_brgy_list': member_per_brgy_list,
        'brgys': brgys,
        'selected_brgy': selected_brgy,
        'the_brgy': the_brgy,
        'member_filtered_per_brgy_list': member_filtered_per_brgy_list,
        'member_list': member_list,
        'logged_user': logged_user,
    })


def members_per_brgy_report_pdf(request):
    member_per_brgy_list = {}
    members = Individual.objects.all()
    current_time = timezone.now()
    # Format the current date and time as a string
    formatted_time = current_time.strftime("%B %d, %Y")
    activity_log = ActivityLog.objects.create(
        title=f"{request.user} has downloaded a pdf copy of Members Per Barangay Report",
        content=f"{request.user} has download a pdf copy of Members Per Barangay Report on {formatted_time}",
        date=timezone.now(),
        date_time=timezone.now(),
    )
    activity_log.save()

    for member in members:
        member_brgy = member.brgy
        if member_brgy not in member_per_brgy_list:
            member_per_brgy_list[member_brgy] = [(
                member,
                round((1 / member.brgy.brgy_voter_population) * 100),
                member.brgy.brgy_voter_population,
            )]
        else:
            member_per_brgy_list[member_brgy].append((
                member,
                round((1 / member.brgy.brgy_voter_population) * 100),
                member.brgy.brgy_voter_population,
            ))

    html = render_to_string('member_per_brgy_report_pdf.html', {
        'member_per_brgy_list': member_per_brgy_list,
    })

    options = {
        'margin-top': '0',
        'margin-right': '0',
        'margin-bottom': '0',
        'margin-left': '0',
        'page-size': 'Letter',
        'encoding': 'UTF-8',
        'quiet': '',
        'print-media-type': '',
        'disable-smart-shrinking': '',
        'no-outline': '',
    }

    config = pdfkit.configuration(wkhtmltopdf='C:/Program Files/wkhtmltopdf/bin/wkhtmltopdf.exe')

    pdf = pdfkit.from_string(html, False, options=options, configuration=config)

    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="members_per_brgy.pdf"'
    return response


def members_filtered_per_brgy_report_pdf(request):
    member_filtered_per_brgy_list = {}
    brgys = Barangay.objects.all()

    current_time = timezone.now()
    # Format the current date and time as a string
    formatted_time = current_time.strftime("%B %d, %Y")
    activity_log = ActivityLog.objects.create(
        title=f"{request.user} has downloaded a pdf copy of Members(Filtered) Per Barangay Report",
        content=f"{request.user} has downloaded a pdf copy of Members(Filtered) Per Barangay Report on {formatted_time}",
        date=timezone.now(),
        date_time=timezone.now(),
    )
    activity_log.save()

    selected_brgy = request.GET.get('selected-brgy')
    if selected_brgy:  # Check if a date is selected
        members_filter = Individual.objects.filter(brgy=selected_brgy)
        the_brgy = Barangay.objects.get(id=selected_brgy)

        for member in members_filter:
            member_brgy = member.brgy

            if member_brgy not in member_filtered_per_brgy_list:
                member_filtered_per_brgy_list[member_brgy] = [(
                    member,
                    round((1 / member.brgy.brgy_voter_population) * 100),
                    member.brgy.brgy_voter_population,
                )]
            else:
                member_filtered_per_brgy_list[member_brgy].append((
                    member,
                    round((1 / member.brgy.brgy_voter_population) * 100),
                    member.brgy.brgy_voter_population,
                ))
    else:
        the_brgy = None

    html = render_to_string('member_filtered_per_brgy_report_pdf.html', {
        'brgys': brgys,
        'selected_brgy': selected_brgy,
        'the_brgy': the_brgy,
        'member_filtered_per_brgy_list': member_filtered_per_brgy_list,
    })

    options = {
        'margin-top': '0',
        'margin-right': '0',
        'margin-bottom': '0',
        'margin-left': '0',
        'page-size': 'Letter',
        'encoding': 'UTF-8',
        'quiet': '',
        'print-media-type': '',
        'disable-smart-shrinking': '',
        'no-outline': '',
    }

    config = pdfkit.configuration(wkhtmltopdf='C:/Program Files/wkhtmltopdf/bin/wkhtmltopdf.exe')

    pdf = pdfkit.from_string(html, False, options=options, configuration=config)

    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="members_{the_brgy}_brgy.pdf"'
    return response


def leader_members_report(request):
    request_user = request.user
    logged_user = Individual.objects.get(user__username=request_user)

    cluster = Cluster.objects.all()

    brgys = Barangay.objects.all()

    selected_brgy = request.GET.get('selected-brgy')
    if selected_brgy:  # Check if a date is selected
        cluster_filter = Cluster.objects.filter(leader__brgy=selected_brgy)
        the_brgy = Barangay.objects.get(id=selected_brgy)
    else:
        cluster_filter = []
        the_brgy = None

    return render(request, 'leader_members_report.html', {
        'cluster': cluster,
        'brgys': brgys,
        'cluster_filter': cluster_filter,
        'selected_brgy': selected_brgy,
        'the_brgy': the_brgy,
        'logged_user': logged_user,
    })


def leader_members_report_pdf(request):
    cluster = Cluster.objects.all()

    current_time = timezone.now()
    # Format the current date and time as a string
    formatted_time = current_time.strftime("%B %d, %Y")
    activity_log = ActivityLog.objects.create(
        title=f"{request.user} has downloaded a pdf copy of Leaders' Cluster",
        content=f"{request.user} has downloaded a pdf copy of Leaders' Cluster on {formatted_time}",
        date=timezone.now(),
        date_time=timezone.now(),
    )
    activity_log.save()

    html = render_to_string('leader_members_report_pdf.html', {
        'cluster': cluster,
    })

    options = {
        'margin-top': '0',
        'margin-right': '0',
        'margin-bottom': '0',
        'margin-left': '0',
        'page-size': 'Letter',
        'encoding': 'UTF-8',
        'quiet': '',
        'print-media-type': '',
        'disable-smart-shrinking': '',
        'no-outline': '',
    }

    config = pdfkit.configuration(wkhtmltopdf='C:/Program Files/wkhtmltopdf/bin/wkhtmltopdf.exe')

    pdf = pdfkit.from_string(html, False, options=options, configuration=config)

    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="leader_members_report.pdf"'
    return response


def leader_members_report_filtered_pdf(request):
    brgys = Barangay.objects.all()

    current_time = timezone.now()
    # Format the current date and time as a string
    formatted_time = current_time.strftime("%B %d, %Y")
    activity_log = ActivityLog.objects.create(
        title=f"{request.user} has downloaded a pdf copy of a Filtered Leaders' Cluster",
        content=f"{request.user} has downloaded a pdf copy of a Filtered Leaders' Cluster on {formatted_time}",
        date=timezone.now(),
        date_time=timezone.now(),
    )
    activity_log.save()

    selected_brgy = request.GET.get('selected-brgy')
    if selected_brgy:  # Check if a date is selected
        cluster_filter = Cluster.objects.filter(leader__brgy=selected_brgy)
        the_brgy = Barangay.objects.get(id=selected_brgy)
    else:
        cluster_filter = []
        the_brgy = None

    html = render_to_string('leader_members_filtered_report_pdf.html', {
        'brgys': brgys,
        'cluster_filter': cluster_filter,
        'selected_brgy': selected_brgy,
        'the_brgy': the_brgy,
    })

    options = {
        'margin-top': '0',
        'margin-right': '0',
        'margin-bottom': '0',
        'margin-left': '0',
        'page-size': 'Letter',
        'encoding': 'UTF-8',
        'quiet': '',
        'print-media-type': '',
        'disable-smart-shrinking': '',
        'no-outline': '',
    }

    config = pdfkit.configuration(wkhtmltopdf='C:/Program Files/wkhtmltopdf/bin/wkhtmltopdf.exe')

    pdf = pdfkit.from_string(html, False, options=options, configuration=config)

    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="leader_members_{the_brgy}_cluster_report.pdf"'
    return response


def all_members_individuals_report(request):
    request_user = request.user
    logged_user = Individual.objects.get(user__username=request_user)

    individuals = Individual.objects.all().order_by('brgy')
    return render(request, 'all_member_report.html', {
        'individuals': individuals,
        'logged_user': logged_user,
    })


def all_members_individuals_report_pdf(request):
    individuals = Individual.objects.all().order_by('brgy')

    current_time = timezone.now()
    # Format the current date and time as a string
    formatted_time = current_time.strftime("%B %d, %Y")
    activity_log = ActivityLog.objects.create(
        title=f"{request.user} has downloaded a pdf copy of a Total Members PDF",
        content=f"{request.user} has downloaded a pdf copy of a Filtered Leaders' Cluster on {formatted_time}",
        date=timezone.now(),
        date_time=timezone.now(),
    )
    activity_log.save()

    html = render_to_string('all_member_report_pdf.html', {
        'individuals': individuals,
    })

    options = {
        'margin-top': '0',
        'margin-right': '0',
        'margin-bottom': '0',
        'margin-left': '0',
        'page-size': 'Letter',
        'encoding': 'UTF-8',
        'quiet': '',
        'print-media-type': '',
        'disable-smart-shrinking': '',
        'no-outline': '',
    }

    config = pdfkit.configuration(wkhtmltopdf='C:/Program Files/wkhtmltopdf/bin/wkhtmltopdf.exe')

    pdf = pdfkit.from_string(html, False, options=options, configuration=config)

    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="all_members_individuals_report.pdf"'
    return response


def all_leaders_report(request):
    request_user = request.user
    logged_user = Individual.objects.get(user__username=request_user)

    leaders = Cluster.objects.all()

    leader_list = {}
    for leader in leaders:
        if leader not in leader_list:
            leader_list[leader] = len(leader.members.all())
        else:
            leader_list[leader].append(len(leader.members.all()))

    return render(request, 'leaders_report.html', {
        'leaders': leaders,
        'leader_list': leader_list,
        'logged_user': logged_user,
    })


def all_leaders_report_pdf(request):
    leaders = Cluster.objects.all()

    current_time = timezone.now()
    # Format the current date and time as a string
    formatted_time = current_time.strftime("%B %d, %Y")
    activity_log = ActivityLog.objects.create(
        title=f"{request.user} has downloaded a pdf copy of All Leaders Report",
        content=f"{request.user} has downloaded a pdf copy of All Leaders Report on {formatted_time}",
        date=timezone.now(),
        date_time=timezone.now(),
    )
    activity_log.save()

    leader_list = {}
    for leader in leaders:
        if leader not in leader_list:
            leader_list[leader] = len(leader.members.all())
        else:
            leader_list[leader].append(len(leader.members.all()))

    html = render_to_string('leaders_report_pdf.html', {
        'leaders': leaders,
        'leader_list': leader_list,
    })

    options = {
        'margin-top': '0',
        'margin-right': '0',
        'margin-bottom': '0',
        'margin-left': '0',
        'page-size': 'Letter',
        'encoding': 'UTF-8',
        'quiet': '',
        'print-media-type': '',
        'disable-smart-shrinking': '',
        'no-outline': '',
    }

    config = pdfkit.configuration(wkhtmltopdf='C:/Program Files/wkhtmltopdf/bin/wkhtmltopdf.exe')

    pdf = pdfkit.from_string(html, False, options=options, configuration=config)

    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="all_leaders_report.pdf"'
    return response


def all_members_report(request):
    request_user = request.user
    logged_user = Individual.objects.get(user__username=request_user)

    members = Member.objects.all()
    return render(request, 'members_report.html', {
        'members': members,
        'logged_user': logged_user,
    })


def all_members_report_pdf(request):
    members = Member.objects.all()

    current_time = timezone.now()
    # Format the current date and time as a string
    formatted_time = current_time.strftime("%B %d, %Y")
    activity_log = ActivityLog.objects.create(
        title=f"{request.user} has downloaded a pdf copy of All Members Report",
        content=f"{request.user} has downloaded a pdf copy of All Members Report on {formatted_time}",
        date=timezone.now(),
        date_time=timezone.now(),
    )
    activity_log.save()

    html = render_to_string('members_report_pdf.html', {
        'members': members,
    })

    options = {
        'margin-top': '0',
        'margin-right': '0',
        'margin-bottom': '0',
        'margin-left': '0',
        'page-size': 'Letter',
        'encoding': 'UTF-8',
        'quiet': '',
        'print-media-type': '',
        'disable-smart-shrinking': '',
        'no-outline': '',
    }

    config = pdfkit.configuration(wkhtmltopdf='C:/Program Files/wkhtmltopdf/bin/wkhtmltopdf.exe')

    pdf = pdfkit.from_string(html, False, options=options, configuration=config)

    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="members_report.pdf"'
    return response


@login_required(login_url='login')
@allowed_users(allowed_roles=['Admin'])
def no_member_barangays(request):
    request_user = request.user
    logged_user = Individual.objects.get(user__username=request_user)

    member_brgys = Individual.objects.values('brgy__brgy_name').distinct()

    brgys = [brgy['brgy__brgy_name'] for brgy in member_brgys]
    # Barangay w/o members

    no_member_brgy_list = {}
    brgys_for_members = Barangay.objects.all()
    for no_mem_brgy in brgys_for_members:
        brgy = no_mem_brgy.brgy_name
        if brgy not in brgys:
            no_member_brgy_list[brgy] = brgy

    return render(request, 'no_member_brgy.html', {
        'member_brgys': member_brgys,
        'brgys': brgys,
        'no_member_brgy_list': no_member_brgy_list,
        'logged_user': logged_user,
    })


@login_required(login_url='login')
@allowed_users(allowed_roles=['Admin'])
def no_member_barangays_pdf(request):
    member_brgys = Individual.objects.values('brgy__brgy_name').distinct()

    brgys = [brgy['brgy__brgy_name'] for brgy in member_brgys]
    # Barangay w/o members

    current_time = timezone.now()
    # Format the current date and time as a string
    formatted_time = current_time.strftime("%B %d, %Y")
    activity_log = ActivityLog.objects.create(
        title=f"{request.user} has downloaded a pdf copy of Barangay w/o Members",
        content=f"{request.user} has downloaded a pdf copy of Barangay w/o Members on {formatted_time}",
        date=timezone.now(),
        date_time=timezone.now(),
    )
    activity_log.save()

    no_member_brgy_list = {}
    brgys_for_members = Barangay.objects.all()
    for no_mem_brgy in brgys_for_members:
        brgy = no_mem_brgy.brgy_name
        if brgy not in brgys:
            no_member_brgy_list[brgy] = brgy

    html = render_to_string('no_member_brgy_pdf.html', {
        'member_brgys': member_brgys,
        'brgys': brgys,
        'no_member_brgy_list': no_member_brgy_list,
    })

    options = {
        'margin-top': '0',
        'margin-right': '0',
        'margin-bottom': '0',
        'margin-left': '0',
        'page-size': 'Letter',
        'encoding': 'UTF-8',
        'quiet': '',
        'print-media-type': '',
        'disable-smart-shrinking': '',
        'no-outline': '',
    }

    config = pdfkit.configuration(wkhtmltopdf='C:/Program Files/wkhtmltopdf/bin/wkhtmltopdf.exe')

    pdf = pdfkit.from_string(html, False, options=options, configuration=config)

    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="no_member_barangays.pdf"'
    return response


@login_required(login_url='login')
@allowed_users(allowed_roles=['Admin'])
def member_count_per_brgy(request):
    request_user = request.user
    logged_user = Individual.objects.get(user__username=request_user)

    brgys_member_count = Individual.objects.values(
        'brgy__brgy_name',
        'brgy__brgy_voter_population'
    ).annotate(member_count=Count('name'))

    member_sum = [count['member_count'] for count in brgys_member_count]
    member_brgy = [brgy['brgy__brgy_name'] for brgy in brgys_member_count]
    member_percentage = [round(((count['member_count'] / count['brgy__brgy_voter_population']) * 100)) for count in brgys_member_count]

    member_per_brgy_list = {}
    for sum, brgy, percentage in zip(member_sum, member_brgy, member_percentage):
        if brgy not in member_per_brgy_list:
            member_per_brgy_list[brgy] = [(sum, percentage)]
        else:
            member_per_brgy_list[brgy].append((sum, percentage))

    return render(request, 'member_count_per_brgy.html', {
        'brgys_member_count': brgys_member_count,
        'member_sum': member_sum,
        'member_per_brgy_list': member_per_brgy_list,
        'logged_user': logged_user,
    })


@login_required(login_url='login')
@allowed_users(allowed_roles=['Admin'])
def member_count_per_brgy_pdf(request):
    brgys_member_count = Individual.objects.values(
        'brgy__brgy_name',
        'brgy__brgy_voter_population'
    ).annotate(member_count=Count('name'))

    current_time = timezone.now()
    # Format the current date and time as a string
    formatted_time = current_time.strftime("%B %d, %Y")
    activity_log = ActivityLog.objects.create(
        title=f"{request.user} has downloaded a pdf copy of Members Count per Barangay",
        content=f"{request.user} has downloaded a pdf copy of Members Count per Barangay on {formatted_time}",
        date=timezone.now(),
        date_time=timezone.now(),
    )
    activity_log.save()

    member_sum = [count['member_count'] for count in brgys_member_count]
    member_brgy = [brgy['brgy__brgy_name'] for brgy in brgys_member_count]
    member_percentage = [round(((count['member_count'] / count['brgy__brgy_voter_population']) * 100)) for count in brgys_member_count]

    member_per_brgy_list = {}
    for sum, brgy, percentage in zip(member_sum, member_brgy, member_percentage):
        if brgy not in member_per_brgy_list:
            member_per_brgy_list[brgy] = [(sum, percentage)]
        else:
            member_per_brgy_list[brgy].append((sum, percentage))

    html = render_to_string('member_count_per_brgy_pdf.html', {
        'brgys_member_count': brgys_member_count,
        'member_sum': member_sum,
        'member_per_brgy_list': member_per_brgy_list,
    })

    options = {
        'margin-top': '0',
        'margin-right': '0',
        'margin-bottom': '0',
        'margin-left': '0',
        'page-size': 'Letter',
        'encoding': 'UTF-8',
        'quiet': '',
        'print-media-type': '',
        'disable-smart-shrinking': '',
        'no-outline': '',
    }

    config = pdfkit.configuration(wkhtmltopdf='C:/Program Files/wkhtmltopdf/bin/wkhtmltopdf.exe')

    pdf = pdfkit.from_string(html, False, options=options, configuration=config)

    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="member_count_per_brgy.pdf"'
    return response


@login_required(login_url='login')
@allowed_users(allowed_roles=['Admin'])
def no_members_leader(request):
    request_user = request.user
    logged_user = Individual.objects.get(user__username=request_user)

    no_members = Cluster.objects.filter(members=None)
    return render(request, 'no_member_leaders.html', {
        'no_members': no_members,
        'logged_user': logged_user,
    })


@login_required(login_url='login')
@allowed_users(allowed_roles=['Admin'])
def no_members_leader_pdf(request):
    no_members = Cluster.objects.filter(members=None)

    current_time = timezone.now()
    # Format the current date and time as a string
    formatted_time = current_time.strftime("%B %d, %Y")
    activity_log = ActivityLog.objects.create(
        title=f"{request.user} has downloaded a pdf copy of Leaders w/o Members",
        content=f"{request.user} has downloaded a pdf copy of Leaders w/o Members on {formatted_time}",
        date=timezone.now(),
        date_time=timezone.now(),
    )
    activity_log.save()

    html = render_to_string('no_member_leaders_pdf.html', {
        'no_members': no_members,
    })

    options = {
        'margin-top': '0',
        'margin-right': '0',
        'margin-bottom': '0',
        'margin-left': '0',
        'page-size': 'Letter',
        'encoding': 'UTF-8',
        'quiet': '',
        'print-media-type': '',
        'disable-smart-shrinking': '',
        'no-outline': '',
    }

    config = pdfkit.configuration(wkhtmltopdf='C:/Program Files/wkhtmltopdf/bin/wkhtmltopdf.exe')

    pdf = pdfkit.from_string(html, False, options=options, configuration=config)

    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="no_members_leader.pdf"'
    return response


@login_required(login_url='login')
@allowed_users(allowed_roles=['Admin'])
def leaderless_members(request):
    request_user = request.user
    logged_user = Individual.objects.get(user__username=request_user)

    members = Member.objects.all().order_by('brgy__brgy_name')
    leaderless_member = Cluster.objects.values('members__name')

    cluster_members_filter = [members['members__name'] for members in leaderless_member]

    leaderless = {}
    for member in members:
        member_name = member.name
        if member_name not in cluster_members_filter:
            leaderless[member] = member.brgy

    return render(request, 'leaderless_members.html', {
        'members': members,
        'leaderless_member': leaderless_member,
        'leaderless': leaderless,
        'cluster_members_filter': cluster_members_filter,
        'logged_user': logged_user,
    })


@login_required(login_url='login')
@allowed_users(allowed_roles=['Admin'])
def leaderless_members_pdf(request):
    members = Member.objects.all().order_by('brgy__brgy_name')
    leaderless_member = Cluster.objects.values('members__name')

    current_time = timezone.now()
    # Format the current date and time as a string
    formatted_time = current_time.strftime("%B %d, %Y")
    activity_log = ActivityLog.objects.create(
        title=f"{request.user} has downloaded a pdf copy of Members w/o Leaders",
        content=f"{request.user} has downloaded a pdf copy of Members w/o Leaders on {formatted_time}",
        date=timezone.now(),
        date_time=timezone.now(),
    )
    activity_log.save()

    cluster_members_filter = [members['members__name'] for members in leaderless_member]

    leaderless = {}
    for member in members:
        member_name = member.name
        if member_name not in cluster_members_filter:
            leaderless[member] = member.brgy

    html = render_to_string('leaderless_members_pdf.html', {
        'members': members,
        'leaderless_member': leaderless_member,
        'leaderless': leaderless,
        'cluster_members_filter': cluster_members_filter,
    })

    options = {
        'margin-top': '0',
        'margin-right': '0',
        'margin-bottom': '0',
        'margin-left': '0',
        'page-size': 'Letter',
        'encoding': 'UTF-8',
        'quiet': '',
        'print-media-type': '',
        'disable-smart-shrinking': '',
        'no-outline': '',
    }

    config = pdfkit.configuration(wkhtmltopdf='C:/Program Files/wkhtmltopdf/bin/wkhtmltopdf.exe')

    pdf = pdfkit.from_string(html, False, options=options, configuration=config)

    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="leaderless_members.pdf"'
    return response


@login_required(login_url='login')
@allowed_users(allowed_roles=['Admin'])
def get_filtered_sitios(request):
    selected_brgy = request.GET.get('barangay')
    if selected_brgy:
        sitios = Sitio.objects.filter(brgy__brgy_name=selected_brgy)
        serialized_sitios = [{'id': sitio.id, 'name': sitio.name} for sitio in sitios]
        return JsonResponse(serialized_sitios, safe=False)
    else:
        return JsonResponse([], safe=False)


def get_filtered_sitios_using_brgy_id(request):
    selected_brgy = request.GET.get('barangay')
    if selected_brgy:
        sitios = Sitio.objects.filter(brgy__id=selected_brgy)
        serialized_sitios = [{'id': sitio.id, 'name': sitio.name} for sitio in sitios]
        return JsonResponse(serialized_sitios, safe=False)
    else:
        return JsonResponse([], safe=False)


def get_filtered_leaders(request):
    selected_brgy = request.GET.get('barangay')
    if selected_brgy:
        leaders = Leader.objects.filter(brgy__brgy_name=selected_brgy)
        serialized_leaders = [{'id': leader.id, 'name': leader.name} for leader in leaders]
        return JsonResponse(serialized_leaders, safe=False)
    else:
        return JsonResponse([], safe=False)


@login_required(login_url='login')
@allowed_users(allowed_roles=['Admin'])
def tag_leader_member(request, member_name, leader_name):
    member = Member.objects.get(name=member_name)
    leader = Leader.objects.get(name=leader_name)

    leader_cluster, created = Cluster.objects.get_or_create(leader=leader)
    leader_cluster.members.add(member)
    leader_cluster.save()

    current_time = timezone.now()
    # Format the current date and time as a string
    formatted_time = current_time.strftime("%B %d, %Y")
    activity_log = ActivityLog.objects.create(
        title=f"{request.user} has associated {member.name} to Leader {leader.name}",
        content=f"{request.user} has associated {member.name} to Leader {leader.name} on {formatted_time}",
        date=timezone.now(),
        date_time=timezone.now(),
    )
    activity_log.save()

    referring_url = request.META.get('HTTP_REFERER')

    if referring_url:
        return HttpResponseRedirect(referring_url)
    else:
        return redirect('function', member_name=member.name, leader_name=leader.name)


@login_required(login_url='login')
@allowed_users(allowed_roles=['Admin'])
def change_brgy_name(request):
    barangays = Barangay.objects.all()
    change_brgy_name_form = ChangeBarangayNameForm()
    if request.method == 'POST':
        form = ChangeBarangayNameForm(request.POST)
        if form.is_valid():
            brgy = form.save(commit=False)
            brgy.save()
    return render(request, 'change_brgy_name.html', {
        'barangays': barangays,
        'change_brgy_name_form': change_brgy_name_form,
    })


@login_required(login_url='login')
@allowed_users(allowed_roles=['Admin'])
@csrf_exempt
def qr_code_scanner(request):
    if request.method == 'POST':
        data = json.loads(request.body.decode('utf-8'))
        scanned_data = data.get('scanned_data')
        # Process or store the scanned data as needed

        # encrypted_username = signer.sign(user.username)  # 1st Encrypt the username
        # data = encrypted_username.encode('utf-8')  # 2 Convert encrypted_username to bytes
        # encrypted_data = cipher_suite.encrypt(data)  # Final

        key = b'bSKEk2cT2V8vllCpMtQWsO2FxUVQdl3S_IHwBbEE4eQ='
        cipher_suite = Fernet(key)
        signing_key = b'Cold'
        signer = Signer(key=signing_key)

        # encrypted_username = signer.sign(user.username)  # 1st Encrypt the username
        # data = encrypted_username.encode('utf-8')  # 2 Convert encrypted_username to bytes
        # encrypted_data = cipher_suite.encrypt(data)  # Final

        plain_text = cipher_suite.decrypt(scanned_data)  # 1
        my_string = plain_text.decode('utf-8')  # 2
        decrypted_username = signer.unsign(my_string)  # 3
        print(decrypted_username)
        if Individual.objects.filter(user__username=decrypted_username).exists():
            individual_object = Individual.objects.get(user__username=decrypted_username)

            attendance = QRCodeAttendance.objects.create(
                user=decrypted_username,
                name=individual_object.name,
                brgy=individual_object.brgy.brgy_name,
                sitio=individual_object.sitio.name,
                group=individual_object.group,
                date=timezone.now(),
                date_time=timezone.now(),
            )

            attendance.save()
            return JsonResponse({'status': 'success', 'message': f'Welcome, {decrypted_username}'})
        elif not Individual.objects.filter(user__username=decrypted_username).exists():

            return JsonResponse({'status': 'error', 'message': 'Scanned Data Does not Exist'})
        # return JsonResponse({decrypted_username: True})

    return render(request, 'qr_code_attendance.html')


@login_required(login_url='login')
@allowed_users(allowed_roles=['Admin'])
def attendance_list(request):
    request_user = request.user
    logged_user = Individual.objects.get(user__username=request_user)

    default_date = date.today()
    attendances_default = QRCodeAttendance.objects.all()

    selected_date_str = request.GET.get('date')
    if selected_date_str:
        selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
    else:
        selected_date = None

    if selected_date:  # Check if a date is selected
        attendances = QRCodeAttendance.objects.filter(date=selected_date)
    else:
        attendances = []

    return render(request, 'attendance_list.html', {
        'attendances': attendances,
        'selected_date': selected_date,
        'attendances_default': attendances_default,
        'default_date': default_date,
        'logged_user': logged_user,
    })


@login_required(login_url='login')
@allowed_users(allowed_roles=['Admin'])
def attendance_list_pdf(request):
    attendances_default = QRCodeAttendance.objects.all()

    current_time = timezone.now()
    # Format the current date and time as a string
    formatted_time = current_time.strftime("%B %d, %Y")
    activity_log = ActivityLog.objects.create(
        title=f"{request.user} has downloaded a pdf copy of attendances",
        content=f"{request.user} has downloaded a pdf copy of attendances on {formatted_time}",
        date=timezone.now(),
        date_time=timezone.now(),
    )
    activity_log.save()

    html = render_to_string('attendance_list_pdf.html', {
        'attendances_default': attendances_default,
    })

    options = {
        'margin-top': '0',
        'margin-right': '0',
        'margin-bottom': '0',
        'margin-left': '0',
        'page-size': 'Letter',
        'encoding': 'UTF-8',
        'quiet': '',
        'print-media-type': '',
        'disable-smart-shrinking': '',
        'no-outline': '',
    }

    config = pdfkit.configuration(wkhtmltopdf='C:/Program Files/wkhtmltopdf/bin/wkhtmltopdf.exe')

    pdf = pdfkit.from_string(html, False, options=options, configuration=config)

    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="attendance_list.pdf"'
    return response


@login_required(login_url='login')
@allowed_users(allowed_roles=['Admin'])
def attendance_list_filtered_daily_pdf(request):
    default_date = date.today()
    attendances_default = QRCodeAttendance.objects.all()

    selected_date_str = request.GET.get('date')
    if selected_date_str:
        selected_date = datetime.strptime(selected_date_str, '%b. %d, %Y').date()
    else:
        selected_date = None

    if selected_date:  # Check if a date is selected
        attendances = QRCodeAttendance.objects.filter(date=selected_date)
    else:
        attendances = []

    current_time = timezone.now()
    # Format the current date and time as a string
    formatted_time = current_time.strftime("%B %d, %Y")
    activity_log = ActivityLog.objects.create(
        title=f"{request.user} has downloaded a pdf filtered copy of attendances-{selected_date}",
        content=f"{request.user} has downloaded a pdf copy of attendances on {formatted_time}",
        date=timezone.now(),
        date_time=timezone.now(),
    )
    activity_log.save()

    html = render_to_string('attendance_list_filtered_daily_pdf.html', {
        # 'selected_date_str': selected_date_str,
        'attendances': attendances,
        'attendances_default': attendances_default,
        'default_date': default_date,
        'selected_date': selected_date,
    })

    options = {
        'margin-top': '0',
        'margin-right': '0',
        'margin-bottom': '0',
        'margin-left': '0',
        'page-size': 'Letter',
        'encoding': 'UTF-8',
        'quiet': '',
        'print-media-type': '',
        'disable-smart-shrinking': '',
        'no-outline': '',
    }

    config = pdfkit.configuration(wkhtmltopdf='C:/Program Files/wkhtmltopdf/bin/wkhtmltopdf.exe')

    pdf = pdfkit.from_string(html, False, options=options, configuration=config)

    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="attendance_list_daily-{selected_date}.pdf"'
    return response


def sitios_report(request):
    request_user = request.user
    logged_user = Individual.objects.get(user__username=request_user)

    brgys = Barangay.objects.all()
    selected_brgy = request.GET.get('sitio-brgy')

    individuals = Individual.objects.all()
    individual_per_sitio_list = {}
    for individual in individuals:
        sitio = individual.sitio
        if not sitio in individual_per_sitio_list:
            individual_per_sitio_list[sitio] = [individual]
        else:
            individual_per_sitio_list[sitio].append(individual)

    individual_filtered_per_sitio_list = {}
    if selected_brgy == 'None':
        individuals = Individual.objects.filter(sitio=None)
        for individual in individuals:
            sitio = individual.sitio
            if not sitio in individual_filtered_per_sitio_list:
                individual_filtered_per_sitio_list[sitio] = [individual]
            else:
                individual_filtered_per_sitio_list[sitio].append(individual)
    elif selected_brgy:
        individuals = Individual.objects.filter(sitio__brgy__id=selected_brgy)
        for individual in individuals:
            sitio = individual.sitio
            if not sitio in individual_filtered_per_sitio_list:
                individual_filtered_per_sitio_list[sitio] = [individual]
            else:
                individual_filtered_per_sitio_list[sitio].append(individual)

    return render(request, 'sitios_report.html', {
        'individual_per_sitio_list': individual_per_sitio_list,
        'individual_filtered_per_sitio_list': individual_filtered_per_sitio_list,
        'brgys': brgys,
        'logged_user': logged_user,
        'selected_brgy': selected_brgy,
    })


def sitios_report_pdf(request):
    individuals = Individual.objects.all()

    current_time = timezone.now()
    # Format the current date and time as a string
    formatted_time = current_time.strftime("%B %d, %Y")
    activity_log = ActivityLog.objects.create(
        title=f"{request.user} has downloaded a pdf copy of Sitio Report",
        content=f"{request.user} has downloaded a pdf copy of Sitio Report on {formatted_time}",
        date=timezone.now(),
        date_time=timezone.now(),
    )
    activity_log.save()

    individual_per_sitio_list = {}
    for individual in individuals:
        sitio = individual.sitio
        if not sitio in individual_per_sitio_list:
            individual_per_sitio_list[sitio] = [individual]
        else:
            individual_per_sitio_list[sitio].append(individual)

    html = render_to_string('sitios_report_pdf.html', {
        'individual_per_sitio_list': individual_per_sitio_list,
    })

    options = {
        'margin-top': '0',
        'margin-right': '0',
        'margin-bottom': '0',
        'margin-left': '0',
        'page-size': 'Letter',
        'encoding': 'UTF-8',
        'quiet': '',
        'print-media-type': '',
        'disable-smart-shrinking': '',
        'no-outline': '',
    }

    config = pdfkit.configuration(wkhtmltopdf='C:/Program Files/wkhtmltopdf/bin/wkhtmltopdf.exe')

    pdf = pdfkit.from_string(html, False, options=options, configuration=config)

    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="sitios.pdf"'
    return response


def sitios_report_filtered_pdf(request):
    selected_brgy = request.GET.get('sitio-brgy')

    brgy = Barangay.objects.get(id=selected_brgy)

    current_time = timezone.now()
    # Format the current date and time as a string
    formatted_time = current_time.strftime("%B %d, %Y")
    activity_log = ActivityLog.objects.create(
        title=f"{request.user} has downloaded a filtered pdf copy of Sitio of Barangay {brgy} Report",
        content=f"{request.user} has downloaded a filtered pdf copy of Sitio of Barangay {brgy} Report on {formatted_time}",
        date=timezone.now(),
        date_time=timezone.now(),
    )
    activity_log.save()

    individual_filtered_per_sitio_list = {}
    if selected_brgy == 'None':
        individuals = Individual.objects.filter(sitio=None)
        for individual in individuals:
            sitio = individual.sitio
            if not sitio in individual_filtered_per_sitio_list:
                individual_filtered_per_sitio_list[sitio] = [individual]
            else:
                individual_filtered_per_sitio_list[sitio].append(individual)
    elif selected_brgy:
        individuals = Individual.objects.filter(sitio__brgy__id=selected_brgy)
        for individual in individuals:
            sitio = individual.sitio
            if not sitio in individual_filtered_per_sitio_list:
                individual_filtered_per_sitio_list[sitio] = [individual]
            else:
                individual_filtered_per_sitio_list[sitio].append(individual)

    html = render_to_string('sitios_report_filtered_pdf.html', {
        'individual_filtered_per_sitio_list': individual_filtered_per_sitio_list,
        'selected_brgy': selected_brgy,
    })

    options = {
        'margin-top': '0',
        'margin-right': '0',
        'margin-bottom': '0',
        'margin-left': '0',
        'page-size': 'Letter',
        'encoding': 'UTF-8',
        'quiet': '',
        'print-media-type': '',
        'disable-smart-shrinking': '',
        'no-outline': '',
    }

    config = pdfkit.configuration(wkhtmltopdf='C:/Program Files/wkhtmltopdf/bin/wkhtmltopdf.exe')

    pdf = pdfkit.from_string(html, False, options=options, configuration=config)

    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="sitios.pdf"'
    return response


@login_required(login_url='login')
@allowed_users(allowed_roles=['Admin'])
def promote_to_leader(request, username):
    user = User.objects.get(username=username)
    member = Member.objects.get(user=user)

    current_time = timezone.now()
    # Format the current date and time as a string
    formatted_time = current_time.strftime("%B %d, %Y")
    activity_log = ActivityLog.objects.create(
        title=f"{request.user} has promoted {member.name} to Leader",
        content=f"{request.user} has promoted {member.name} to Leader on {formatted_time}",
        date=timezone.now(),
        date_time=timezone.now(),
    )
    activity_log.save()

    promote_notification, created = Notification.objects.get_or_create(
        title=f'Member {member.name} Promoted to Leader by {request.user}',
        message=f'This is to notify you that the member, {member.name} '
                f'has been promoted to leader by {request.user} on {formatted_time}',
        identifier=f'Member Promoted to Leader Identifier: {member.name}-{request.user}',
        date=timezone.now(),
        date_time=timezone.now(),
    )
    promote_notification.save()

    new_filename = f"leader-{member.user.username}.jpg"

    # Save the image with the new filename
    old_image_path = member.image.path
    new_image_path = os.path.join(default_storage.location, new_filename)
    default_storage.save(new_filename, default_storage.open(old_image_path))

    leader, created = Leader.objects.get_or_create(user=user,
                                                   name=member.name,
                                                   gender=member.gender,
                                                   age=member.age,
                                                   brgy=member.brgy,
                                                   image=new_filename)

    leader_group = Group.objects.get(name='Leaders')
    member_group = Group.objects.get(name='Members')
    user.groups.remove(member_group)
    user.groups.add(leader_group)

    individual_user = Individual.objects.get(user=user)
    individual_user.group = "Leader"
    individual_user.save()

    cluster, created = Cluster.objects.get_or_create(leader=leader)
    cluster.save()

    leader.save()
    user.save()
    member.delete()

    return redirect('cluster', name=leader.name, username=user.username)


@authenticated_user
def authentication(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(username=username, password=password)
        if user is not None:

            current_time = timezone.now()
            # Format the current date and time as a string
            formatted_time = current_time.strftime("%B %d, %Y")
            activity_log = ActivityLog.objects.create(
                title=f"{username} has logged in to the platform",
                content=f"{username} has logged in to the platform on {formatted_time}",
                date=timezone.now(),
                date_time=timezone.now(),
            )
            activity_log.save()

            login(request, user)
            if user.groups.filter(name='Admin').exists() and user.groups.filter(name='Leaders').exists():
                return redirect('homepage')
            elif user.groups.filter(name='Leaders').exists():
                user_object = User.objects.get(username=username)
                leader_user = Leader.objects.get(user=user_object)
                return redirect('profile-leader', username=username)
            elif user.groups.filter(name='Members').exists():
                user_object = User.objects.get(username=username)
                member_user = Member.objects.get(user=user_object)
                return redirect('profile-member', username=username)
        else:
            messages.error(request, 'Invalid Form Data')

    return render(request, 'login.html', {

    })


def logout_user(request):
    current_time = timezone.now()
    # Format the current date and time as a string
    formatted_time = current_time.strftime("%B %d, %Y")
    activity_log = ActivityLog.objects.create(
        title=f"{request.user} has logged out from the platform",
        content=f"{request.user} has logged out from the platform on {formatted_time}",
        date=timezone.now(),
        date_time=timezone.now(),
    )
    activity_log.save()

    logout(request)
    return redirect('login')


@login_required(login_url='login')
@allowed_users(allowed_roles=['Admin'])
def create_individuals(request):
    leaders = Leader.objects.all()
    members = Member.objects.all()
    for leader in leaders:
        individual_leader, created = Individual.objects.get_or_create(
            name=leader.name,
            gender=leader.gender,
            age=leader.age,
            brgy=leader.brgy,
            sitio=leader.sitio,
        )
        individual_leader.save()

    for member in members:
        individual_member, created = Individual.objects.get_or_create(
            name=member.name,
            gender=member.gender,
            age=member.age,
            brgy=member.brgy,
            sitio=member.sitio,
        )

        individual_member.save()

    return redirect('homepage')


# Added 2/9/2024 for Version 2, registration_validation, registrants, confirm_registration_member


def registration_validation(request):
    current_date = timezone.now()
    registrant_form = RegistrantsForm()
    email_message = EmailMessage.objects.get(type='Registration Validation')
    if request.method == 'POST':
        form = RegistrantsForm(request.POST, request.FILES)

        if form.is_valid():
            registrant = form.save(commit=False)

            sitio_id = request.POST.get('registrant-sitio')

            password1 = form.cleaned_data['password1']
            password2 = form.cleaned_data['password2']
            if User.objects.filter(email=registrant.email).exists() or\
                    Registrants.objects.filter(email=registrant.email).exists():
                messages.error(request, 'Email Already Exists')

            if password1 == password2 and not User.objects.filter(email=registrant.email).exists() and not \
                    Registrants.objects.filter(email=registrant.email).exists():

                hashed_password = make_password(password1)

                registrant.password = hashed_password
                registrant.date = current_date
                registrant.date_time = current_date
                if sitio_id != 'None':
                    selected_sitio = Sitio.objects.get(id=sitio_id)
                    registrant.sitio = selected_sitio
                else:
                    registrant.sitio = None
                registrant.save()

                current_time = timezone.now()

                # Format the current date and time as a string
                formatted_time = current_time.strftime("%B %d, %Y")

                registrant_notification, created = Notification.objects.get_or_create(
                    title=f'Registrant {registrant.name} Unverified ',
                    message=f'This is to notify you that a registrant, {registrant.name} '
                            f'registered on {formatted_time} is awaiting verification',
                    identifier=f'Registrant Verified as Member Identifier: {registrant.name}-{registrant.id}',
                    date=timezone.now(),
                    date_time=timezone.now(),
                )
                registrant_notification.save()

                name = registrant.name
                from_email = 'Autodidacticism'
                subject = f'{email_message.subject}, {registrant.name}'
                message = email_message.content
                to_email = [registrant.email]
                html_message = render_to_string('confirmed_registration_message.html', {
                    'name': name,
                    'subject': subject,
                    'message': message,
                })
                send_mail(
                    subject=subject,
                    from_email=from_email,
                    recipient_list=to_email,
                    message=message,
                    html_message=html_message,
                    fail_silently=False
                )

                rendered_template = render(request, 'registration_response.html', {'variable': 'value'})

                # Create an HttpResponse with the rendered template as content
                response = HttpResponse(rendered_template)
                return response

            elif password1 != password2:
                messages.error(request, 'Password not the same')

            if User.objects.filter(username=registrant.username).exists() or \
                    Registrants.objects.filter(username=registrant.username).exists():
                messages.error(request, 'Username Already Exists')

        else:
            # Handle form errors, including the email format error
            messages.error(request, 'Invalid Form Submission. Check Your Email format')

    return render(request, 'registrations.html', {
        'registrant_form': registrant_form,
    })


@login_required(login_url='login')
@allowed_users(allowed_roles=['Admin'])
def registrants(request):
    request_user = request.user
    logged_user = Individual.objects.get(user__username=request_user)

    registrant_objects = Registrants.objects.all()
    return render(request, 'registrants.html', {
        'registrant_objects': registrant_objects,
        'logged_user': logged_user,
    })


@login_required(login_url='login')
@allowed_users(allowed_roles=['Admin'])
def confirm_registration_member(request, username):
    registrant = Registrants.objects.get(username=username)
    email_message = EmailMessage.objects.get(type='Member Verification')
    new_filename = f"member-{registrant.username}.jpg"

    # Save the image with the new filename
    old_image_path = registrant.image.path
    new_image_path = os.path.join(default_storage.location, new_filename)
    default_storage.save(new_filename, default_storage.open(old_image_path))

    # Create A User object

    user_created, created = User.objects.get_or_create(
        username=registrant.username,
        email=registrant.email,
        password=registrant.password,
    )
    user_created.save()

    group = Group.objects.get(name='Members')
    user_created.groups.add(group)
    user_created.save()

    new_user = User.objects.get(username=user_created.username)

    # Member objects creation
    member, created_member = Member.objects.get_or_create(
        user=new_user,
        name=registrant.name,
        gender=registrant.gender,
        age=registrant.age,
        brgy=registrant.brgy,
        sitio=registrant.sitio,
        image=new_filename,
    )
    member.save()

    # create Individual object

    individual, individual_created = Individual.objects.get_or_create(
        user=new_user,
        name=registrant.name,
        gender=registrant.gender,
        age=registrant.age,
        brgy=registrant.brgy,
        sitio=registrant.sitio,
        group='Member',
        image=new_filename,
    )
    individual.save()

    acting_user = request.user

    current_time = timezone.now()

    # Format the current date and time as a string
    formatted_time = current_time.strftime("%B %d, %Y")

    member_verified_notification, created = Notification.objects.get_or_create(
        title=f'Registrant {registrant.name} verified as Member by {acting_user}',
        message=f'This is to notify you that the registrant, {registrant.name} '
                f'has been verified as a member {formatted_time}',
        identifier=f' Registrant Verified as Member Identifier: {registrant.name}-{registrant.id}',
        date=timezone.now(),
        date_time=timezone.now(),
    )
    member_verified_notification.save()

    name = f'{registrant.name}'
    from_email = 'Autodidacticism'
    subject = f'{email_message.subject}, {registrant.name}'
    message = f'{email_message.content}'
    to_email = [registrant.email]
    html_message = render_to_string('confirmed_registration_message.html', {
        'name': name,
        'subject': subject,
        'message': message,
    })
    send_mail(
        subject=subject,
        from_email=from_email,
        recipient_list=to_email,
        message=message,
        html_message=html_message,
        fail_silently=False
    )

    registrant.delete()

    referring_url = request.META.get('HTTP_REFERER')

    if referring_url:
        # Redirect back to the referring page
        return HttpResponseRedirect(referring_url)
    else:
        # If there's no referring URL, redirect to a default page
        return redirect('homepage')


@login_required(login_url='login')
@allowed_users(allowed_roles=['Admin'])
def confirm_registration_leader(request, username):
    registrant = Registrants.objects.get(username=username)
    email_message = EmailMessage.objects.get(type='Leader Verification')
    new_filename = f"leader-{registrant.username}.jpg"

    # Save the image with the new filename
    old_image_path = registrant.image.path
    new_image_path = os.path.join(default_storage.location, new_filename)
    default_storage.save(new_filename, default_storage.open(old_image_path))

    # Create A User object

    user_created, created = User.objects.get_or_create(
        username=registrant.username,
        email=registrant.email,
        password=registrant.password,
    )
    user_created.save()

    group = Group.objects.get(name='Leaders')
    user_created.groups.add(group)
    user_created.save()

    new_user = User.objects.get(username=user_created.username)

    # Member objects creation
    leader, created_leader = Leader.objects.get_or_create(
        user=new_user,
        name=registrant.name,
        gender=registrant.gender,
        age=registrant.age,
        brgy=registrant.brgy,
        sitio=registrant.sitio,
        image=new_filename,
    )
    leader.save()

    cluster, created = Cluster.objects.get_or_create(leader=leader)
    cluster.save()

    # create Individual object

    individual, individual_created = Individual.objects.get_or_create(
        user=new_user,
        name=registrant.name,
        gender=registrant.gender,
        age=registrant.age,
        brgy=registrant.brgy,
        sitio=registrant.sitio,
        group='Leader',
        image=new_filename,
    )
    individual.save()

    acting_user = request.user

    current_time = timezone.now()

    # Format the current date and time as a string
    formatted_time = current_time.strftime("%B %d, %Y")

    leader_verified_notification, created = Notification.objects.get_or_create(
        title=f'Registrant {registrant.name} verified as Leader by {acting_user}',
        message=f'This is to notify you that the registrant, {registrant.name} '
                f'has been verified as a leader on {formatted_time}',
        identifier=f' Registrant Verified as Leader Identifier: {registrant.name}-{registrant.id}',
        date=timezone.now(),
        date_time=timezone.now(),
    )
    leader_verified_notification.save()

    name = registrant.name
    from_email = 'Autodidacticism'
    subject = f'{email_message.subject}, {registrant.name}'
    message = email_message.content
    to_email = [registrant.email]
    html_message = render_to_string('confirmed_registration_message.html', {
        'name': name,
        'subject': subject,
        'message': message,
    })
    send_mail(
        subject=subject,
        from_email=from_email,
        recipient_list=to_email,
        message=message,
        html_message=html_message,
        fail_silently=False
    )
    registrant.delete()

    referring_url = request.META.get('HTTP_REFERER')

    if referring_url:
        # Redirect back to the referring page
        return HttpResponseRedirect(referring_url)
    else:
        # If there's no referring URL, redirect to a default page
        return redirect('homepage')


# Palompon Total Voters 43,065


@login_required(login_url='login')
@allowed_users(allowed_roles=['Admin'])
def confirm_registrant_as_admin_and_leader(request, username):
    registrant = Registrants.objects.get(username=username)
    email_message = EmailMessage.objects.get(type='Admin Verification')

    new_filename = f"leader-{registrant.username}.jpg"

    # Save the image with the new filename
    old_image_path = registrant.image.path
    new_image_path = os.path.join(default_storage.location, new_filename)
    default_storage.save(new_filename, default_storage.open(old_image_path))

    # Create A User object

    user_created, created = User.objects.get_or_create(
        username=registrant.username,
        email=registrant.email,
        password=registrant.password,
    )
    user_created.save()

    group = Group.objects.get(name='Admin')
    leader_group = Group.objects.get(name='Leaders')
    user_created.groups.add(group)
    user_created.groups.add(leader_group)
    user_created.save()

    new_user = User.objects.get(username=user_created.username)

    # Member objects creation
    leader, created_leader = Leader.objects.get_or_create(
        user=new_user,
        name=registrant.name,
        gender=registrant.gender,
        age=registrant.age,
        brgy=registrant.brgy,
        sitio=registrant.sitio,
        image=new_filename,
    )
    leader.save()

    cluster, created = Cluster.objects.get_or_create(leader=leader)
    cluster.save()

    # create Individual object

    individual, individual_created = Individual.objects.get_or_create(
        user=new_user,
        name=registrant.name,
        gender=registrant.gender,
        age=registrant.age,
        brgy=registrant.brgy,
        sitio=registrant.sitio,
        group='Admin',
        image=new_filename,
    )
    individual.save()

    acting_user = request.user

    current_time = timezone.now()

    # Format the current date and time as a string
    formatted_time = current_time.strftime("%B %d, %Y")

    admin_users = User.objects.filter(groups__name='Admin')
    for user in admin_users:
        leader_verified_notification, created = Notification.objects.get_or_create(
            user=user,
            title=f'Registrant {registrant.name} verified as Leader and Admin by {acting_user}',
            message=f'This is to notify you that the registrant, {registrant.name} '
                    f'has been verified as an admin and leader on {formatted_time}',
            identifier=f' Registrant Verified as Leader Identifier: {registrant.name}-{registrant.id}',
            date=timezone.now(),
            date_time=timezone.now(),
        )
        leader_verified_notification.save()

    name = registrant.name
    from_email = 'Autodidacticism'
    subject = f'{email_message.subject}, {registrant.name}'
    message = email_message.content
    to_email = [registrant.email]
    html_message = render_to_string('confirmed_registration_message.html', {
        'name': name,
        'subject': subject,
        'message': message,
    })
    send_mail(
        subject=subject,
        from_email=from_email,
        recipient_list=to_email,
        message=message,
        html_message=html_message,
        fail_silently=False
    )
    registrant.delete()

    referring_url = request.META.get('HTTP_REFERER')

    if referring_url:
        # Redirect back to the referring page
        return HttpResponseRedirect(referring_url)
    else:
        # If there's no referring URL, redirect to a default page
        return redirect('homepage')


@login_required(login_url='login')
@allowed_users(allowed_roles=['Admin'])
def deny_registration(request, username):
    registrant = Registrants.objects.get(username=username)
    email_message = EmailMessage.objects.get(type='Denied Registration')
    acting_user = request.user
    current_time = timezone.now()

    # Format the current date and time as a string
    formatted_time = current_time.strftime("%B %d, %Y")

    admin_users = User.objects.filter(groups__name='Admin')
    for user in admin_users:
        denied_registration_notification, created = Notification.objects.get_or_create(
            user=user,
            title=f'Registrant {registrant.name} registration denied by {acting_user} ',
            message=f"This is to notify you that the registrant, {registrant.name}"
                    f'has been denied registration on {formatted_time}',
            identifier=f' Registrant Verified as Leader Identifier: {registrant.name}-{registrant.id}',
            date=timezone.now(),
            date_time=timezone.now(),
        )
        denied_registration_notification.save()

    name = registrant.name
    from_email = 'Autodidacticism'
    subject = f'{email_message.subject}, {registrant.name}'
    message = email_message.content
    to_email = [registrant.email]
    html_message = render_to_string('confirmed_registration_message.html', {
        'name': name,
        'subject': subject,
        'message': message,
    })
    send_mail(
        subject=subject,
        from_email=from_email,
        recipient_list=to_email,
        message=message,
        html_message=html_message,
        fail_silently=False
    )
    registrant.delete()

    referring_url = request.META.get('HTTP_REFERER')

    if referring_url:
        # Redirect back to the referring page
        return HttpResponseRedirect(referring_url)
    else:
        # If there's no referring URL, redirect to a default page
        return redirect('homepage')


@login_required(login_url='login')
@allowed_users(allowed_roles=['Admin'])
def deny_registration_invalid_image(request, username):
    registrant = Registrants.objects.get(username=username)
    email_message = EmailMessage.objects.get(type='Denied Registration (Image)')
    acting_user = request.user
    current_time = timezone.now()

    # Format the current date and time as a string
    formatted_time = current_time.strftime("%B %d, %Y")

    denied_registration_notification, created = Notification.objects.get_or_create(
        title=f'Registrant {registrant.name} registration denied by {acting_user} ',
        message=f"This is to notify you that the registrant, {registrant.name}"
                f'has been denied registration on {formatted_time} for passing illegible photographic '
                f'identification data',
        identifier=f' Registrant Verified as Leader Identifier: {registrant.name}-{registrant.id}',
        date=timezone.now(),
        date_time=timezone.now(),
    )
    denied_registration_notification.save()

    name = registrant.name
    from_email = 'Autodidacticism'
    subject = f'{email_message.subject}, {registrant.name}'
    message = email_message.content
    to_email = [registrant.email]
    html_message = render_to_string('confirmed_registration_message.html', {
        'name': name,
        'subject': subject,
        'message': message,
    })
    send_mail(
        subject=subject,
        from_email=from_email,
        recipient_list=to_email,
        message=message,
        html_message=html_message,
        fail_silently=False
    )
    registrant.delete()

    referring_url = request.META.get('HTTP_REFERER')

    if referring_url:
        # Redirect back to the referring page
        return HttpResponseRedirect(referring_url)
    else:
        # If there's no referring URL, redirect to a default page
        return redirect('homepage')


@login_required(login_url='login')
@allowed_users(allowed_roles=['Admin'])
def deny_registration_invalid_email(request, username):
    registrant = Registrants.objects.get(username=username)
    email_message = EmailMessage.objects.get(type='Denied Registration (Email)')
    acting_user = request.user
    current_time = timezone.now()

    # Format the current date and time as a string
    formatted_time = current_time.strftime("%B %d, %Y")

    denied_registration_notification, created = Notification.objects.get_or_create(
        title=f'Registrant {registrant.name} registration denied by {acting_user} ',
        message=f"This is to notify you that the registrant, {registrant.name}"
                f'has been denied registration on {formatted_time} for passing an invalid email address',
        identifier=f' Registrant Verified as Leader Identifier: {registrant.name}-{registrant.id}',
        date=timezone.now(),
        date_time=timezone.now(),
    )
    denied_registration_notification.save()

    name = registrant.name
    from_email = 'Autodidacticism'
    subject = f'{email_message.subject}, {registrant.name}'
    message = email_message.content
    to_email = [registrant.email]
    html_message = render_to_string('confirmed_registration_message.html', {
        'name': name,
        'subject': subject,
        'message': message,
    })
    send_mail(
        subject=subject,
        from_email=from_email,
        recipient_list=to_email,
        message=message,
        html_message=html_message,
        fail_silently=False
    )
    registrant.delete()

    referring_url = request.META.get('HTTP_REFERER')

    if referring_url:
        # Redirect back to the referring page
        return HttpResponseRedirect(referring_url)
    else:
        # If there's no referring URL, redirect to a default page
        return redirect('homepage')


@login_required(login_url='login')
@allowed_users(allowed_roles=['Admin', 'Leaders'])
def associate_member_to_leader(request, leader_username, member_username):
    leader_user = User.objects.get(username=leader_username)
    member_user = User.objects.get(username=member_username)

    leader = Leader.objects.get(user=leader_user)
    member = Member.objects.get(user=member_user)

    leader_cluster = Cluster.objects.get(leader=leader)
    leader_cluster.members.add(member)
    leader_cluster.save()

    current_time = timezone.now()
    # Format the current date and time as a string
    formatted_time = current_time.strftime("%B %d, %Y")
    activity_log = ActivityLog.objects.create(
        title=f"Leader {leader.name} has associated {member.name} in their cluster",
        content=f"Leader {leader.name} has associated {member.name} in their cluster on {formatted_time}",
        date=timezone.now(),
        date_time=timezone.now(),
    )
    activity_log.save()

    referring_url = request.META.get('HTTP_REFERER')

    if referring_url:
        # Redirect back to the referring page
        return HttpResponseRedirect(referring_url)
    else:
        # If there's no referring URL, redirect to a default page
        return redirect('homepage')


@login_required(login_url='login')
@allowed_users(allowed_roles=['Admin', 'Leaders'])
def remove_member_from_leader(request, leader_username, member_username):
    leader_user = User.objects.get(username=leader_username)
    member_user = User.objects.get(username=member_username)

    leader = Leader.objects.get(user=leader_user)
    member = Member.objects.get(user=member_user)

    leader_cluster = Cluster.objects.get(leader=leader)
    leader_cluster.members.remove(member)
    leader_cluster.save()

    current_time = timezone.now()
    # Format the current date and time as a string
    formatted_time = current_time.strftime("%B %d, %Y")
    activity_log = ActivityLog.objects.create(
        title=f"Leader {leader.name} has removed {member.name} from their cluster",
        content=f"Leader {leader.name} has removed{member.name} from their cluster on {formatted_time}",
        date=timezone.now(),
        date_time=timezone.now(),
    )
    activity_log.save()

    referring_url = request.META.get('HTTP_REFERER')

    if referring_url:
        # Redirect back to the referring page
        return HttpResponseRedirect(referring_url)
    else:
        # If there's no referring URL, redirect to a default page
        return redirect('homepage')


def notifications_async(request):
    notifications = Notification.objects.filter(user__username=request.user, removed=False)
    notification_list = []

    unseen_notifications = Notification.objects.filter(
        user__username=request.user,
        is_seen=False).annotate(unseen_notifications=Count('is_seen'))
    unseen_sum = unseen_notifications.aggregate(unseen=Sum('unseen_notifications'))['unseen']

    for notification in notifications:
        natural_time = naturaltime(notification.date_time)
        notification_data = {
            'title': notification.title,
            'message': notification.message,
            'time': natural_time,
            'id': notification.id,
            'unseen': unseen_sum
        }
        # print(naturaltime(notification.date_time))
        notification_list.append(notification_data)

    return JsonResponse({
        'notification': notification_list,
    })


@login_required(login_url='login')
@allowed_users(allowed_roles=['Admin'])
def remove_notification(request, title, id):
    notification = Notification.objects.get(title=title, id=id)
    notification.removed = True
    notification.save()

    # Assuming you want to send a JSON response to confirm the removal
    return JsonResponse({'message': 'Notification removed successfully'})


@login_required(login_url='login')
@allowed_users(allowed_roles=['Admin', 'Leaders', 'Members'])
def non_admin_leader_profile(request, username):
    leader_user = User.objects.get(username=username)
    leader = Leader.objects.get(user=leader_user)
    leaders_cluster = Cluster.objects.get(leader=leader)
    barangays = Barangay.objects.all()
    sitios = Sitio.objects.filter(brgy=leader.brgy)
    selected_sitio = request.POST.get('added-member-sitio')

    authenticated_user_request = request.user
    authenticated_leader = Leader.objects.filter(user=authenticated_user_request).exists()

    leader_brgy_unassociated_members = Member.objects.filter(brgy=leader.brgy)

    members_brgy = [member for member in leader_brgy_unassociated_members]

    # First let's retrieve the search field in the base.html
    search_engine_field_query = request.GET.get('search')

    # Now that we have retrieve the search engine field in the base.html, it's time to delve into the login of it

    if search_engine_field_query:
        search_engine_result_member = Member.objects.filter(
            Q(name__icontains=search_engine_field_query, brgy=leader.brgy) |
            Q(sitio__name__icontains=search_engine_field_query, brgy=leader.brgy))

        search_result_count_member = search_engine_result_member.annotate(count=Count('name'))
        search_result_sum_member = search_result_count_member.aggregate(sum=Sum('count'))['sum']

        if search_result_sum_member is None:
            total_results = 0
        else:
            total_results = search_result_sum_member

    else:
        search_engine_result_member = []
        total_results = []

    brgy_members = Cluster.objects.all()
    members_b = []
    for members in brgy_members:
        for member in members.members.all():
            member_name = member.name
            if member_name not in members_b:
                members_b.append(member_name)

    members_c = []
    for members in leaders_cluster.members.all():
        members_user = members.user
        if members_user not in members_c:
            members_c.append(members_user)

    unassociated_members = []
    for member in members_brgy:
        member_name = member.name
        if member_name not in members_b:
            unassociated_members.append(member)

    # Added 3/5/2024 1:40 AM
    leader_requests = LeaderConnectMemberRequest.objects.all()
    leaders_request_list = []
    for leaders in leader_requests:
        for leader in leaders.requests.all():
            if leader not in leaders_request_list:
                leaders_request_list.append(leaders.member.user)

    # Added 3/5/2024 1:40 AM
    leader_member_request = LeadersRequestConnect.objects.all()
    leader_member_connect_request_list = []
    for leaders in leader_member_request:
        for members in leaders.requests.all():
            member_username = members.user
            if member_username not in leader_member_connect_request_list:
                leader_member_connect_request_list.append(members.user)

    # Create QR Code for each user
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=2,
    )

    key = b'bSKEk2cT2V8vllCpMtQWsO2FxUVQdl3S_IHwBbEE4eQ='
    cipher_suite = Fernet(key)
    signing_key = b'Cold'
    signer = Signer(key=signing_key)

    # Commented 2/20/2024 encrypted_username = signer.sign(leader.name) # 1st Encrypt the username
    encrypted_username = signer.sign(leader.user) # 1st Encrypt the username
    data = encrypted_username.encode('utf-8') # 2 Convert encrypted_username to bytes
    encrypted_data = cipher_suite.encrypt(data) # Final

    qr.add_data(encrypted_data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    img.save(f'management/static/images/qr-codes/QR-Code-{leader.name}-{leader.brgy}-{leader.id}.png')

    member_registration_form = MemberRegistrationForm()
    edit_leader_profile_form = LeaderRegistrationEditForm(instance=leader)

    if request.method == 'POST':
        # Added for V.2, 2/10/ 2024
        edit_profile_leader_profile_form = LeaderRegistrationEditForm(request.POST, request.FILES, instance=leader)
        if edit_profile_leader_profile_form.is_valid():

            # external_data
            edit_selected_sitio = request.POST.get('leader-profile-edit-sitio')

            leader_profile = edit_profile_leader_profile_form.save(commit=False)
            if edit_selected_sitio != 'None':
                selected_sitio_edit = Sitio.objects.get(id=edit_selected_sitio)
                leader_profile.sitio = selected_sitio_edit
            else:
                leader_profile.sitio = None
            leader_profile.save()

            individual_link = Individual.objects.get(user=leader_profile.user)
            individual_link.name = leader_profile.name
            individual_link.gender = leader_profile.gender
            individual_link.age = leader_profile.age
            individual_link.brgy = leader_profile.brgy
            individual_link.sitio = leader_profile.sitio
            individual_link.image = leader_profile.image
            individual_link.save()

            current_time = timezone.now()
            # Format the current date and time as a string
            formatted_time = current_time.strftime("%B %d, %Y")
            activity_log = ActivityLog.objects.create(
                title=f"Leader {leader.name} has edited their details",
                content=f"Leader {leader.name} has edited their details on {formatted_time}",
                date=timezone.now(),
                date_time=timezone.now(),
            )
            activity_log.save()

            return redirect('profile-leader', username=leader_profile.user)
    # leader_user = User.objects.get(username=username)
    # leader = Leader.objects.get(user=leader_user)
    # leaders_cluster = Cluster.objects.get(leader=leader)
    # barangays = Barangay.objects.all()
    # sitios = Sitio.objects.filter(brgy=leader.brgy)
    # selected_sitio = request.POST.get('added-member-sitio')
    #
    # leader_brgy_unassociated_members = Member.objects.filter(brgy=leader.brgy)
    #
    # members_brgy = [member for member in leader_brgy_unassociated_members]
    #
    # # First let's retrieve the search field in the base.html
    # search_engine_field_query = request.GET.get('search')
    #
    # # Now that we have retrieve the search engine field in the base.html, it's time to delve into the login of it
    #
    # if search_engine_field_query:
    #     search_engine_result_member = Member.objects.filter(
    #         Q(name__icontains=search_engine_field_query, brgy=leader.brgy) |
    #         Q(sitio__name__icontains=search_engine_field_query, brgy=leader.brgy))
    #
    #     search_result_count_member = search_engine_result_member.annotate(count=Count('name'))
    #     search_result_sum_member = search_result_count_member.aggregate(sum=Sum('count'))['sum']
    #
    #     if search_result_sum_member is None:
    #         total_results = 0
    #     else:
    #         total_results = search_result_sum_member
    #
    # else:
    #     search_engine_result_member = []
    #     total_results = []
    #
    # brgy_members = Cluster.objects.all()
    # members_b = []
    # for members in leaders_cluster.members.all():
    #         member_name = members.user
    #         if member_name not in members_b:
    #             members_b.append(member_name)
    #
    # unassociated_members = []
    # for member in members_brgy:
    #     member_name = member.name
    #     if member_name not in members_b:
    #         unassociated_members.append(member)
    #
    # # Create QR Code for each user
    # qr = qrcode.QRCode(
    #     version=1,
    #     error_correction=qrcode.constants.ERROR_CORRECT_L,
    #     box_size=10,
    #     border=2,
    # )
    #
    # key = b'bSKEk2cT2V8vllCpMtQWsO2FxUVQdl3S_IHwBbEE4eQ='
    # cipher_suite = Fernet(key)
    # signing_key = b'Cold'
    # signer = Signer(key=signing_key)
    #
    # encrypted_username = signer.sign(leader.name)  # 1st Encrypt the username
    # data = encrypted_username.encode('utf-8')  # 2 Convert encrypted_username to bytes
    # encrypted_data = cipher_suite.encrypt(data)  # Final
    #
    # qr.add_data(encrypted_data)
    # qr.make(fit=True)
    #
    # img = qr.make_image(fill_color="black", back_color="white")
    #
    # img.save(f'management/static/images/qr-codes/QR-Code-{leader.name}-{leader.brgy}-{leader.id}.png')
    #
    # member_registration_form = MemberRegistrationForm()
    # edit_leader_profile_form = LeaderRegistrationEditForm(instance=leader)
    #
    # if request.method == 'POST':
    #     # Added for V.2, 2/10/ 2024
    #     edit_profile_leader_profile_form = LeaderRegistrationEditForm(request.POST, request.FILES, instance=leader)
    #     if edit_profile_leader_profile_form.is_valid():
    #
    #         # external_data
    #         edit_selected_sitio = request.POST.get('leader-profile-edit-sitio')
    #
    #         leader_profile = edit_profile_leader_profile_form.save(commit=False)
    #         if edit_selected_sitio != 'None':
    #             selected_sitio_edit = Sitio.objects.get(id=edit_selected_sitio)
    #             leader_profile.sitio = selected_sitio_edit
    #         else:
    #             leader_profile.sitio = None
    #         leader_profile.save()
    #         messages.success(request, 'Editted!')
    #         return redirect('profile-leader', name=leader_profile.name, username=leader_profile.user)

        # Commented for V.2, 2/10/2024
        # if 'add-new-member-btn' in request.POST:
        #     form = MemberRegistrationForm(request.POST, request.FILES)
        #     if form.is_valid():
        #         member = form.save(commit=False)
        #         member.brgy = leader.brgy
        #         if selected_sitio != 'None':
        #             print(f'Sitio: {selected_sitio}')
        #             member_sitio = Sitio.objects.get(id=selected_sitio)
        #             member.sitio = member_sitio
        #         else:
        #             member.sitio = None
        #         member.save()
        #
        #         # Let's create a cluster object
        #         cluster, created = Cluster.objects.get_or_create(leader=leader)
        #         cluster.members.add(member)
        #         cluster.save()
        #
        #         member_added_obj, created = AddedMembers.objects.get_or_create(member=member.name)
        #         member_added_obj.save()
        #
        #         messages.success(request, 'Member Added')
        # elif 'edit-leader-profile-btn' in request.POST:
        #     edit_profile_leader_profile_form = LeaderRegistrationEditForm(request.POST,
        #                                                                   request.FILES,
        #                                                                   instance=leader)
        #     if edit_profile_leader_profile_form.is_valid():
        #
        #         # external_data
        #         edit_selected_sitio = request.POST.get('leader-profile-edit-sitio')
        #
        #         leader_profile = edit_profile_leader_profile_form.save(commit=False)
        #         if edit_selected_sitio != 'None':
        #             selected_sitio_edit = Sitio.objects.get(id=edit_selected_sitio)
        #             leader_profile.sitio = selected_sitio_edit
        #         else:
        #             leader_profile.sitio = None
        #         leader_profile.save()
        #         messages.success(request, 'Editted!')
        #         return redirect('cluster', name=leader_profile.name)

    return render(request, 'leader_profile_non_admin.html', {
        'leader': leader,
        'member_registration_form': member_registration_form,
        'leaders_cluster': leaders_cluster,
        'sitios': sitios,
        'edit_leader_profile_form': edit_leader_profile_form,
        'barangays': barangays,
        'brgy_members': brgy_members,
        'members_b': members_b,
        'members_c': members_c,
        'unassociated_members': unassociated_members,
        'search_engine_result_member': search_engine_result_member,
        'search_engine_field_query': search_engine_field_query,
        'total_results': total_results,
        'authenticated_leader': authenticated_leader,
        'leaders_request_list': leaders_request_list,
        'leader_member_connect_request_list': leader_member_connect_request_list,
    })


@login_required(login_url='login')
@allowed_users(allowed_roles=['Admin', 'Leaders', 'Members'])
def non_admin_member_profile(request, username):
    member_user = User.objects.get(username=username)
    member = Member.objects.get(user=member_user)
    members = Cluster.objects.values('members__name')
    leaders = Leader.objects.filter(brgy=member.brgy)
    get_member_leader = Cluster.objects.filter(members__name=member.name)

    get_member_leader_filter = Cluster.objects.filter(members__name=member.name).values('leader__user__username')

    member_leader = [leader['leader__user__username'] for leader in get_member_leader_filter]

    no_leader_member_list = [name['members__name'] for name in members]

    sitios = Sitio.objects.filter(brgy=member.brgy)

    authenticated_user_request = request.user
    authenticated_member = Member.objects.filter(user=authenticated_user_request).exists()

    # Create QR Code for each user
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=2,
    )

    key = b'bSKEk2cT2V8vllCpMtQWsO2FxUVQdl3S_IHwBbEE4eQ='
    cipher_suite = Fernet(key)
    signing_key = b'Cold'
    signer = Signer(key=signing_key)

    # Commented 2/20/2024 encrypted_username = signer.sign(member.name) # 1st Encrypt the username
    encrypted_username = signer.sign(member.user) # 1st Encrypt the username
    data = encrypted_username.encode('utf-8') # 2 Convert encrypted_username to bytes
    encrypted_data = cipher_suite.encrypt(data) # Final

    qr.add_data(encrypted_data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    img.save(f'management/static/images/qr-codes/QR-Code-{member.name}-{member.brgy}-{member.id}.png')

    # Added 3/5/2024 1:40 AM
    leaders_request = LeaderConnectMemberRequest.objects.get(member=member)

    edit_member_detail_form = MemberRegistrationEditForm(instance=member)
    if request.method == 'POST':
        form = MemberRegistrationEditForm(request.POST, request.FILES, instance=member)
        if form.is_valid():
            edited_member = form.save(commit=False)

            # External Data
            selected_sitio = request.POST.get('member-edit-sitio')
            if selected_sitio != 'None':
                member_sitio = Sitio.objects.get(id=selected_sitio)
                edited_member.sitio = member_sitio
            else:
                edited_member.sitio = None

            current_time = timezone.now()

            # Format the current date and time as a string
            formatted_time = current_time.strftime("%B %d, %Y")
            activity_log = ActivityLog.objects.create(
                title=f"Member {member.name} has edited their details",
                content=f"Member {member.name} has edited their details on {formatted_time}",
                date=timezone.now(),
                date_time=timezone.now(),
            )
            activity_log.save()

            edited_member.save()

            individual_link = Individual.objects.get(user=edited_member.user)
            individual_link.name = edited_member.name
            individual_link.gender = edited_member.gender
            individual_link.age = edited_member.age
            individual_link.brgy = edited_member.brgy
            individual_link.sitio = edited_member.sitio
            individual_link.image = edited_member.image
            individual_link.save()

            return redirect('profile-member', username=edited_member.user)

    return render(request, 'non_admin_member_profile.html', {
        'member': member,
        'no_leader_member_list': no_leader_member_list,
        'leaders': leaders,
        'encrypted_data': encrypted_data,
        'get_member_leader': get_member_leader,
        'edit_member_detail_form': edit_member_detail_form,
        "sitios": sitios,
        'member_leader': member_leader,
        'authenticated_member': authenticated_member,
        'leaders_request': leaders_request,
    })


# Added 3/5/2024 1:40 AM
@login_required(login_url='login')
@allowed_users(allowed_roles=['Admin', 'Leaders'])
def add_member_leader_request(request, member, leader):
    member_user = User.objects.get(username=member)
    leader_user = User.objects.get(username=leader)

    member = Member.objects.get(user=member_user)
    leader = Leader.objects.get(user=leader_user)

    member_connect_request, created = LeaderConnectMemberRequest.objects.get_or_create(
        member=member,
    )
    member_connect_request.requests.add(leader)
    member_connect_request.save()

    leader_connect_to_member, created = LeadersRequestConnect.objects.get_or_create(leader=leader)
    leader_connect_to_member.requests.add(member)
    leader_connect_to_member.save()

    referring_url = request.META.get('HTTP_REFERER')

    if referring_url:
        # Redirect back to the referring page
        return HttpResponseRedirect(referring_url)
    else:
        # If there's no referring URL, redirect to a default page
        return redirect('homepage')


# Added 3/5/2024 1:52 AM
@login_required(login_url='login')
@allowed_users(allowed_roles=['Admin', 'Leaders'])
def revert_member_leader_request(request, member, leader):
    member_user = User.objects.get(username=member)
    leader_user = User.objects.get(username=leader)

    member = Member.objects.get(user=member_user)
    leader = Leader.objects.get(user=leader_user)

    member_connect_request, created = LeaderConnectMemberRequest.objects.get_or_create(
        member=member,
    )
    member_connect_request.requests.remove(leader)
    member_connect_request.save()

    leader_connect_to_member, created = LeadersRequestConnect.objects.get_or_create(leader=leader)
    leader_connect_to_member.requests.remove(member)
    leader_connect_to_member.save()

    referring_url = request.META.get('HTTP_REFERER')

    if referring_url:
        # Redirect back to the referring page
        return HttpResponseRedirect(referring_url)
    else:
        # If there's no referring URL, redirect to a default page
        return redirect('homepage')


# Added 3/5/2024 1:40 AM
@login_required(login_url='login')
@allowed_users(allowed_roles=['Admin', 'Members'])
def accept_leader_connect_request(request, leader, member):
    member_user = User.objects.get(username=member)
    leader_user = User.objects.get(username=leader)

    member = Member.objects.get(user=member_user)
    leader = Leader.objects.get(user=leader_user)

    member_connect_request, created = LeaderConnectMemberRequest.objects.get_or_create(
        member=member,
    )
    member_connect_request.requests.remove(leader)
    member_connect_request.save()

    leader_connect_to_member, created = LeadersRequestConnect.objects.get_or_create(leader=leader)
    leader_connect_to_member.requests.remove(member)
    leader_connect_to_member.save()

    cluster_leader, created = Cluster.objects.get_or_create(leader=leader)
    cluster_leader.members.add(member)
    cluster_leader.save()

    referring_url = request.META.get('HTTP_REFERER')

    if referring_url:
        # Redirect back to the referring page
        return HttpResponseRedirect(referring_url)
    else:
        # If there's no referring URL, redirect to a default page
        return redirect('homepage')


# Added 3/5/2024 1:53 AM
@login_required(login_url='login')
@allowed_users(allowed_roles=['Admin', 'Members'])
def deny_leader_connect_request(request, leader, member):
    member_user = User.objects.get(username=member)
    leader_user = User.objects.get(username=leader)

    member = Member.objects.get(user=member_user)
    leader = Leader.objects.get(user=leader_user)

    member_connect_request, created = LeaderConnectMemberRequest.objects.get_or_create(
        member=member,
    )
    member_connect_request.requests.remove(leader)
    member_connect_request.save()

    leader_connect_to_member, created = LeadersRequestConnect.objects.get_or_create(leader=leader)
    leader_connect_to_member.requests.remove(member)
    leader_connect_to_member.save()

    referring_url = request.META.get('HTTP_REFERER')

    if referring_url:
        # Redirect back to the referring page
        return HttpResponseRedirect(referring_url)
    else:
        # If there's no referring URL, redirect to a default page
        return redirect('homepage')


class MyTokenGenerator(PasswordResetTokenGenerator):
    def _make_hash_value(self, user, timestamp):
        try:
            email_confirmed = user.profile.email_confirmed
        except AttributeError:
            email_confirmed = ''

        return (
            six.text_type(user.pk) + six.text_type(timestamp) +
            six.text_type(email_confirmed)
        )


token_generator = MyTokenGenerator()


def create_password_reset_token(user):
    # Generate a unique token for the user
    token = token_generator.make_token(user)

    # Create a PasswordResetToken object and save it to the database
    password_reset_token = PasswordResetToken.objects.create(
        user=user,
        token=token,
        expires_at=timezone.now() + timezone.timedelta(minutes=10)
    )

    return password_reset_token


@authenticated_user
def forgot_password(request):
    forgot_password_form = ForgotPasswordForm()
    if request.method == 'POST':
        form = ForgotPasswordForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            if User.objects.filter(email=email).exists():
                user = User.objects.get(email=email)
                individual = Individual.objects.get(user=user)
                # Generate a unique token for the user
                password_reset_token = create_password_reset_token(user)

                # Send email
                from_email = 'LMS'
                name = individual.name
                to_email = [user.email]
                message = 'Your Token Is'
                subject = 'Change Password'
                html_message = render_to_string('forgot_password_message_to_email.html', {
                    'name': name,
                    'message': message,
                    'token': password_reset_token.token,
                    'username': user.username,
                    'email': user.email,
                })

                send_mail(
                    subject,
                    message,
                    'LMS <dandan321321321@gmail.com>',
                    to_email,

                    html_message=html_message,
                    fail_silently=False,
                )
                # End send email
                messages.success(request, 'Email sent!')
            else:
                messages.error(request, 'Email not found')

    return render(request, 'forgot_password.html', {
        'form': forgot_password_form,
    })


@authenticated_user
def enter_token(request, email):
    if request.method == 'POST':
        token = request.POST.get('token')
        user = User.objects.get(email=email)

        # Check if the token is valid
        if PasswordResetToken.objects.filter(user=user, token=token).exists():
            return redirect('change-password', email=email, token_str=token)
        else:
            # Check if there are any expired tokens for the user
            expired_tokens = PasswordResetToken.objects.filter(user=user, expires_at__lt=timezone.now())
            if expired_tokens.exists():
                # Delete the expired tokens
                expired_tokens.delete()
                messages.error(request, 'Token is expired. Please request a new one.')
                return redirect('forgot-password')
            else:
                messages.error(request, 'Invalid token. Please try again.')

    return render(request, 'enter_token.html')


@authenticated_user
def change_password(request, email, token_str):
    user = User.objects.get(email=email)
    if request.method == 'POST':
        form = ChangePasswordForm(request.POST)
        if form.is_valid():
            if form.cleaned_data['password1'] == form.cleaned_data['password2']:
                hashed_password = make_password(form.cleaned_data['password1'])
                user.password = hashed_password
                user.save()
                messages.success(request, "You've successfully reset your password")
                token = PasswordResetToken.objects.get(user=user, token=token_str)
                token.delete()

                current_time = timezone.now()

                # Format the current date and time as a string
                formatted_time = current_time.strftime("%B %d, %Y")
                activity_log = ActivityLog.objects.create(
                    title=f"User {user.username} changed their password",
                    content=f"User {user.username} changed their password on {formatted_time}",
                    date=timezone.now(),
                    date_time=timezone.now(),
                )
                activity_log.save()

                return redirect('login')

            else:
                messages.error(request, "Password does not match")

    form = ChangePasswordForm()

    return render(request, 'change_password.html', {
        'form': form,
    })


@login_required(login_url='login')
@allowed_users(allowed_roles=['Admin'])
def seen_notifications(request):
    try:
        user = request.user
        notifications = Notification.objects.filter(user__username=user)
        for notification in notifications:
            notification.is_seen = True
            notification.save()

        # Return a success response
        return JsonResponse({'status': 'success'})

    except ValueError as e:
        # Print the error for debugging purposes
        print('Error marking notifications as seen:', str(e))

        # Return an error response
        return JsonResponse({'status': 'error', 'message': str(e)})


@login_required(login_url='login')
@allowed_users(allowed_roles=['Admin'])
def create_json(request):
    member_objects = Member.objects.all()
    leader_objects = Leader.objects.all()
    individual_objects = Individual.objects.all()

    serialized_members = serialize('json', member_objects)
    serialized_leaders = serialize('json', leader_objects)
    serialized_individual = serialize('json', individual_objects)

    # Write the serialized data into a JSON file
    with open('Member_model.json', 'w') as f:
        f.write(serialized_members)

    with open('Leader_model.json', 'w') as f:
        f.write(serialized_leaders)

    with open('Individual_model.json', 'w') as f:
        f.write(serialized_individual)

    return redirect('homepage')


@login_required(login_url='login')
@allowed_users(allowed_roles=['Admin'])
def load_json(request):
    with open('Individual_model.json', 'r') as f:
        for obj in deserialize('json', f):
            obj.save()

    return redirect('homepage')
