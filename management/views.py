from django.shortcuts import render, redirect
from .forms import LeaderRegistrationForm, MemberRegistrationForm, BarangayForm, AddMemberRegistrationForm, \
    ChangeBarangayNameForm, AddSitioForm, LeaderRegistrationEditForm, MemberRegistrationEditForm, RegistrantsForm
from django.contrib import messages
from .models import Member, Barangay, Leader, Cluster, AddedLeaders, AddedMembers, Sitio, Individual, Registrants, \
    Notification
from django.db.models import Sum, Count, Q
from django.contrib.auth.models import Group, User
from django.contrib.auth.hashers import make_password
from django.http import HttpResponseRedirect
import qrcode
from cryptography.fernet import Fernet
from django.core.signing import Signer
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
import folium
from django.db import models
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from .decorators import authenticated_user
from django.utils import timezone
from django.core.serializers import serialize, deserialize
from django.core.files.storage import default_storage
import os
from django.contrib.humanize.templatetags.humanize import naturaltime


@login_required(login_url='login')
def homepage(request):
    member_brgy = Member.objects.exclude(name=None).values('brgy__brgy_name').distinct()
    leader_brgy = Leader.objects.exclude(name=None).values('brgy__brgy_name').distinct()

    # Let's create a search engine in the homepage to fill the void as it should

    # First let's retrieve the search field in the base.html
    search_engine_field_query = request.GET.get('search')

    # Now that we have retrieve the search engine field in the base.html, it's time to delve into the login of it

    if search_engine_field_query:
        search_engine_result_member = Member.objects.filter(
            Q(name__icontains=search_engine_field_query)
            | Q(brgy__brgy_name__icontains=search_engine_field_query))
        search_engine_result_leader = Leader.objects.filter(
            Q(name__icontains=search_engine_field_query) |
            Q(brgy__brgy_name__icontains=search_engine_field_query))

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
    })


def barangay_members(request, brgy_name):
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
    })


def barangay_leader(request, brgy_name):
    # brgy = Barangay.objects.get(brgy_name=brgy_name)
    leader_brgy = Leader.objects.filter(brgy__brgy_name=brgy_name)
    return render(request, 'leader_brgy.html', {
        'leader_brgy': leader_brgy
    })


def barangay_leaders(request, brgy_name):
    name_brgy = Barangay.objects.get(brgy_name=brgy_name)
    brgy_clusters = Cluster.objects.filter(leader__brgy=name_brgy)
    return render(request, 'brgy_leaders.html', {
        'brgy_clusters': brgy_clusters,
        'name_brgy': name_brgy,
    })


def get_marker_color(percentage):
    if percentage is not None:
        return 'green' if percentage > 55 else 'red'
    return 'gray'


def dashboard(request):
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
    members_count = Member.objects.all().annotate(member_count=Count('name'))
    member_sum = members_count.aggregate(total_members=Sum('member_count'))['total_members']

    # Total Number of Leaders
    leaders_count = Leader.objects.all().annotate(leader_count=Count('name'))
    leaders_sum = leaders_count.aggregate(total_leaders=Sum('leader_count'))['total_leaders']

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
    })


def leader_cluster(request, name):
    leader = Leader.objects.get(name=name)
    members = Cluster.objects.get(leader=leader)
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

    encrypted_username = signer.sign(leader.name) # 1st Encrypt the username
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
            messages.success(request, 'Editted!')
            return redirect('cluster', name=leader_profile.name)

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
        'members': members,
        'sitios': sitios,
        'edit_leader_profile_form': edit_leader_profile_form,
        'barangays': barangays,
        'brgy_members': brgy_members,
        'members_b': members_b,
        'unassociated_members': unassociated_members,
        'search_engine_result_member': search_engine_result_member,
        'search_engine_field_query': search_engine_field_query,
        'total_results': total_results,
    })


def add_barangay(request):
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
    })


def add_sitio(request):
    sitios = Sitio.objects.all()
    sitio_form = AddSitioForm()
    if request.method == 'POST':
        form = AddSitioForm(request.POST)
        if form.is_valid():
            sitio = form.save(commit=False)
            sitio.save()
    return render(request, 'add_sitio.html', {
        'sitio_form': sitio_form,
        'sitios': sitios,
    })


def clusters(request):
    barangays = Barangay.objects.all()
    leaders = {}
    for brgys in barangays:
        brgy_name = brgys.brgy_name
        if Leader.objects.filter(brgy__brgy_name=brgy_name).exists():
            leaders[Leader.objects.filter(brgy__brgy_name=brgy_name)] = brgy_name

    return render(request, 'clusters.html', {
        'leaders': leaders,
        'barangays': barangays,
    })


def add_leader(request):
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
    })


def add_members(request):
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
    })


def member_profile(request, name, id):
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

    encrypted_username = signer.sign(member.name) # 1st Encrypt the username
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
            member_sitio = Sitio.objects.get(id=selected_sitio)
            edited_member.sitio = member_sitio
            edited_member.save()
            return redirect('member-profile', name=edited_member.name, id=member.id)

    return render(request, 'member_profile.html', {
        'member': member,
        'no_leader_member_list': no_leader_member_list,
        'leaders': leaders,
        'encrypted_data': encrypted_data,
        'get_member_leader': get_member_leader,
        'edit_member_detail_form': edit_member_detail_form,
        "sitios": sitios,
    })


def reports(request):
    return render(request, 'reports.html', {

    })


def no_member_barangays(request):
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
    })


def member_count_per_brgy(request):
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
    })


def no_members_leader(request):
    no_members = Cluster.objects.filter(members=None)
    return render(request, 'no_member_leaders.html', {
        'no_members': no_members,
    })


def leaderless_members(request):
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
    })


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


def tag_leader_member(request, member_name, leader_name):
    member = Member.objects.get(name=member_name)
    leader = Leader.objects.get(name=leader_name)

    leader_cluster, created = Cluster.objects.get_or_create(leader=leader)
    leader_cluster.members.add(member)
    leader_cluster.save()

    referring_url = request.META.get('HTTP_REFERER')

    if referring_url:
        return HttpResponseRedirect(referring_url)
    else:
        return redirect('function', member_name=member.name, leader_name=leader.name)


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
        if Member.objects.filter(name=decrypted_username).exists() or Leader.objects.filter(name=decrypted_username).exists():
            # if User.objects.filter(username=decrypted_username).exists():
            #     user_instance = User.objects.get(username=decrypted_username)
            #
            #     # Create Attendance Instance
            #     attendance_object = Attendance.objects.create(
            #         name=user_instance.username,
            #         department=user_instance.department,
            #         course=user_instance.course,
            #         position=user_instance.position
            #     )
            #     attendance_object.save()
            #
            #     attendance_data = AttendanceGraph.objects.create(name=decrypted_username)
            #     attendance_data.save()
            #
            #     # For example, return a JSON response
            #     # messages.success(request, f'Welcome, {decrypted_username}')
            #     # return redirect('qr-code-attendance') and JsonResponse({decrypted_username: True})
            return JsonResponse({'status': 'success', 'message': f'Welcome, {decrypted_username}'})
        elif not Member.objects.filter(name=decrypted_username).exists() or Leader.objects.filter(name=decrypted_username).exists():
            # messages.error(request, 'Scanned Data Does not Exists')
            # return redirect('qr-code-attendance') and JsonResponse({decrypted_username: True})
            return JsonResponse({'status': 'error', 'message': 'Scanned Data Does not Exist'})
        # return JsonResponse({decrypted_username: True})

    return render(request, 'qr_code_attendance.html')


def promote_to_leader(request, name):
    member = Member.objects.get(name=name)

    leader, created = Leader.objects.get_or_create(name=member.name,
                                                           gender=member.gender,
                                                           age=member.age,
                                                           brgy=member.brgy)

    cluster, created = Cluster.objects.get_or_create(leader=leader)
    cluster.save()

    leader.save()
    member.delete()

    return redirect('cluster', name=leader.name)


@authenticated_user
def authentication(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('homepage')
        else:
            messages.error(request, 'Invalid Form Data')

    return render(request, 'login.html', {

    })


def logout_user(request):
    logout(request)
    return redirect('login')


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

                messages.success(request, 'Works')
                return redirect('homepage')

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


def registrants(request):
    registrant_objects = Registrants.objects.all()
    return render(request, 'registrants.html', {
        'registrant_objects': registrant_objects,
    })


def confirm_registration_member(request, username):
    registrant = Registrants.objects.get(username=username)

    new_filename = f"member-{registrant.username}"

    # Save the image with the new filename
    old_image_path = registrant.image.path
    new_image_path = os.path.join(default_storage.location, new_filename)
    default_storage.save(new_filename, default_storage.open(old_image_path))

    # Create A User object

    user, created = User.objects.get_or_create(
        username=registrant.username,
        email=registrant.email,
        password=registrant.password,
    )
    user.save()

    new_user = User.objects.get(username=user.username)

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
    )
    individual.save()

    current_time = timezone.now()

    # Format the current date and time as a string
    formatted_time = current_time.strftime("%B %d, %Y")

    member_verified_notification, created = Notification.objects.get_or_create(
        title=f'Registrant {registrant.name} verified as Member ',
        message=f'This is to notify you that the registrant, {registrant.name} '
                f'has been verified as a member {formatted_time}',
        identifier=f' Registrant Verified as Member Identifier: {registrant.name}-{registrant.id}',
        date=timezone.now(),
        date_time=timezone.now(),
    )
    member_verified_notification.save()

    registrant.delete()

    referring_url = request.META.get('HTTP_REFERER')

    if referring_url:
        # Redirect back to the referring page
        return HttpResponseRedirect(referring_url)
    else:
        # If there's no referring URL, redirect to a default page
        return redirect('homepage')


def confirm_registration_leader(request, username):
    registrant = Registrants.objects.get(username=username)

    new_filename = f"leader-{registrant.username}"

    # Save the image with the new filename
    old_image_path = registrant.image.path
    new_image_path = os.path.join(default_storage.location, new_filename)
    default_storage.save(new_filename, default_storage.open(old_image_path))

    # Create A User object

    user, created = User.objects.get_or_create(
        username=registrant.username,
        email=registrant.email,
        password=registrant.password,
    )
    user.save()

    new_user = User.objects.get(username=user.username)

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
    )
    individual.save()

    current_time = timezone.now()

    # Format the current date and time as a string
    formatted_time = current_time.strftime("%B %d, %Y")

    leader_verified_notification, created = Notification.objects.get_or_create(
        title=f'Registrant {registrant.name} verified as Leader ',
        message=f'This is to notify you that the registrant, {registrant.name} '
                f'has been verified as a leader on {formatted_time}',
        identifier=f' Registrant Verified as Leader Identifier: {registrant.name}-{registrant.id}',
        date=timezone.now(),
        date_time=timezone.now(),
    )
    leader_verified_notification.save()

    registrant.delete()

    referring_url = request.META.get('HTTP_REFERER')

    if referring_url:
        # Redirect back to the referring page
        return HttpResponseRedirect(referring_url)
    else:
        # If there's no referring URL, redirect to a default page
        return redirect('homepage')


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


def load_json(request):
    with open('Individual_model.json', 'r') as f:
        for obj in deserialize('json', f):
            obj.save()

    return redirect('homepage')


def associate_member_to_leader(request, leader_username, member_username):
    leader_user = User.objects.get(username=leader_username)
    member_user = User.objects.get(username=member_username)

    leader = Leader.objects.get(user=leader_user)
    member = Member.objects.get(user=member_user)

    leader_cluster = Cluster.objects.get(leader=leader)
    leader_cluster.members.add(member)
    leader_cluster.save()

    referring_url = request.META.get('HTTP_REFERER')

    if referring_url:
        # Redirect back to the referring page
        return HttpResponseRedirect(referring_url)
    else:
        # If there's no referring URL, redirect to a default page
        return redirect('homepage')


def remove_member_from_leader(request, leader_username, member_username):
    leader_user = User.objects.get(username=leader_username)
    member_user = User.objects.get(username=member_username)

    leader = Leader.objects.get(user=leader_user)
    member = Member.objects.get(user=member_user)

    leader_cluster = Cluster.objects.get(leader=leader)
    leader_cluster.members.remove(member)
    leader_cluster.save()

    referring_url = request.META.get('HTTP_REFERER')

    if referring_url:
        # Redirect back to the referring page
        return HttpResponseRedirect(referring_url)
    else:
        # If there's no referring URL, redirect to a default page
        return redirect('homepage')


def notifications_async(request):
    notifications = Notification.objects.filter(removed=False)
    notification_list = []

    unseen_notifications = Notification.objects.filter(is_seen=False).annotate(unseen_notifications=Count('is_seen'))
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
def remove_notification(request, title, id):
    notification = Notification.objects.get(title=title, id=id)
    notification.removed = True
    notification.save()

    # Assuming you want to send a JSON response to confirm the removal
    return JsonResponse({'message': 'Notification removed successfully'})


@login_required(login_url='login')
def seen_notifications(request):
    try:
        notifications = Notification.objects.all()
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
