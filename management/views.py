from django.shortcuts import render, redirect
from .forms import LeaderRegistrationForm, MemberRegistrationForm, BarangayForm, AddMemberRegistrationForm, \
    ChangeBarangayNameForm, AddSitioForm, LeaderRegistrationEditForm, MemberRegistrationEditForm, RegistrantsForm, \
    ChangePasswordForm, ForgotPasswordForm, ChangeSitioDetailsForm, TotalVoterPopulationEditForm
from django.contrib import messages
from .models import Member, Barangay, Leader, Cluster, AddedLeaders, AddedMembers, Sitio, Individual, Registrants, \
    Notification, EmailMessage, PasswordResetToken, TotalVoterPopulation, QRCodeAttendance, ActivityLog, \
    LeaderConnectMemberRequest, LeadersRequestConnect, AmbiguousVoters, Gender, Religion, Occupation, IndividualParents, \
    IndividualSpouse, IndividualOffspring, IndividualSiblings, IndividualLeaderCluster, BarangayFigures, ElectionType, \
    BarangayElectionResults, BarangayElectionContender, ElectionResults, ElectionContender, BrgyOfficial, BrgySchoolHead, \
    Church, BarangayRemark, SitioRemark
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
from .serializers import QRCodeAttendanceSerializer
from rest_framework.decorators import api_view
from rest_framework.response import Response
import statistics
from itertools import zip_longest


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

    # Now that we have retrieve the search engine field in the base.html,
    # it's time to delve into the login of it # Start with all individuals

    if search_engine_field_query:
        filters = Q(name__icontains=search_engine_field_query) | \
                  Q(brgy__brgy_name__icontains=search_engine_field_query) | \
                  Q(sitio__name__icontains=search_engine_field_query) | \
                  Q(last_name__icontains=search_engine_field_query) | \
                  Q(religion__name__icontains=search_engine_field_query.title())

        # Check for year
        try:
            year = datetime.strptime(search_engine_field_query, "%Y").year
            filters |= Q(birthday__year=year)
        except ValueError:
            pass  # If it fails, just skip this filter

        # Check for month
        try:
            month = datetime.strptime(search_engine_field_query.title(), "%B").month
            filters |= Q(birthday__month=month)
        except ValueError:
            pass  # If it fails, just skip this filter

        try:
            month_year = datetime.strptime(search_engine_field_query, "%B").month
            filters |= Q(birthday__month=month)
        except ValueError:
            pass  # If it fails, just skip this filter

        # Apply all the filters
        search_engine_result_individual = Individual.objects.filter(filters)

        search_result_count_member = search_engine_result_individual.annotate(count=Count('name'))
        search_result_sum_member = search_result_count_member.aggregate(sum=Sum('count'))['sum']

        if search_result_sum_member is None:
            total_results = 0
        else:
            total_results = search_result_sum_member
    else:
        total_results = []
        search_result_count_member = []
        search_result_sum_member = []
        search_engine_result_individual = []

    return render(request, 'base.html', {
        'member_brgy': member_brgy,
        'leader_brgy': leader_brgy,
        'search_engine_result_individual': search_engine_result_individual,
        'search_engine_field_query': search_engine_field_query,
        'search_result_count_member': search_result_count_member,
        'search_result_sum_member': search_result_sum_member,
        'total_results': total_results,
        'logged_user': logged_user,
        'activities': activities,
        'user': user,
    })


@api_view(['GET'])
def endpoints(request):
    routes = [
        {
            'Endpoint': '/attendance/qr-scan/mobile/',
            'method': 'POST',
            'body': None,
            'description': 'Endpoint for making attendances through QR Code scan via mobile app'
        },
        {
            'Endpoint': '/attendance/list/',
            'method': 'GET',
            'body': None,
            'description': 'Endpoint for retrieving attendances'
        }
    ]

    return Response(routes)


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

    barangay_remarks = BarangayRemark.objects.filter(brgy=brgy)

    brgy_individual_count = Individual.objects.filter(brgy=brgy).annotate(count=Count('name'))
    brgy_individual_sum = brgy_individual_count.aggregate(sum=Sum('count'))['sum']

    brgy_sitio_count = Sitio.objects.filter(brgy=brgy).annotate(count=Count('name'))
    brgy_sitio_sum = brgy_sitio_count.aggregate(sum=Sum('count'))['sum']

    brgy_cluster = Cluster.objects.filter(leader__brgy=brgy)

    brgy_figures, created_brgy_figures = BarangayFigures.objects.get_or_create(
        brgy=brgy
    )

    barangay_official_ranks = []
    for official in BrgyOfficial.objects.all():
        if official.rank not in barangay_official_ranks:
            barangay_official_ranks.append(official.rank)

    barangay_official_rank_len = len(barangay_official_ranks)

    barangay_official_party = []
    for contender in BarangayElectionContender.objects.all():
        if contender.party not in barangay_official_party:
            barangay_official_party.append(contender.party)

    barangay_official_party_len = len(barangay_official_party)

    barangay_school_head_ranks = []
    for school_head in BrgySchoolHead.objects.all():
        if school_head.rank not in barangay_school_head_ranks:
            barangay_school_head_ranks.append(school_head.rank)

    barangay_school_head_len = len(barangay_school_head_ranks)

    barangay_election_type = ElectionType.objects.all()
    barangay_election_type_len = len(barangay_election_type)

    barangay_contender_ranks = []
    for contender in BarangayElectionContender.objects.all():
        if contender.rank not in barangay_contender_ranks:
            barangay_contender_ranks.append(contender.rank)

    barangay_contender_ranks_len = len(barangay_contender_ranks)

    brgy_election_results = BarangayElectionResults.objects.filter(brgy=brgy)

    # Fetch election results
    election_results = BarangayElectionResults.objects.filter(brgy=brgy)
    election_dict = {}

    # Organize results by election type and party
    for result in election_results:
        election_year = result.election_year
        str_year = datetime.strftime(election_year, '%Y')

        if str_year not in election_dict:
            election_dict[str_year] = {}

        for contender in result.contenders.all():
            party = contender.party

            if party not in election_dict[str_year]:
                election_dict[str_year][party] = []

            election_dict[str_year][party].append(contender)

    zipped_vote_count_party_name = ''
    party_votes = {}
    if BarangayElectionResults.objects.filter(brgy=brgy).exists():

        for election_type, parties in election_dict.items():
            for party, contenders in parties.items():
                # Calculate the average vote count for this party
                avg_vote_count = sum(contender.vote_count for contender in contenders) / len(contenders)
                if election_type not in party_votes:
                    party_votes[election_type] = [(party, avg_vote_count)]
                else:
                    party_votes[election_type].append((party, avg_vote_count))

    # Prepare the zipped data for rendering
        zipped_vote_count_party_name = zip_longest(party_votes.keys(), party_votes.values())

    # Prepare years for x-axis
    years = list(election_dict.keys())

    # print(party_votes)
    # matrix = [[], []]
    #
    # index = -1
    # for election_type, parties in election_dict.items():
    #
    #     for party, contenders in parties.items():
    #         index += 1
    #         matrix[index].append(contenders)
    #
    # for alpha, omega in zip(matrix[0][0], matrix[1][0]):
    #     print(f'{alpha.vote_count} {omega.vote_count}')
    #
    # contender_gen = (
    #     (election_type, party_name, contender)
    #     for election_type, parties in election_dict.items()
    #     for party_name, contenders in parties.items()
    #     for contender in contenders
    # )

    if request.method == 'POST':
        if 'edit-brgy-detail-btn' in request.POST:
            form = ChangeBarangayNameForm(request.POST, instance=brgy)
            if form.is_valid():
                brgy = form.save(commit=False)
                brgy.save()
                return redirect('member-brgy', brgy_name=brgy.brgy_name)

        elif 'brgy-election-contender-btn' in request.POST:
            election_year = request.POST.get('election-year')
            contender_name = request.POST.get('contender-name')
            contender_rank = request.POST.get('contender-rank')
            contender_vote_count = request.POST.get('contender-votes')
            contender_party = request.POST.get('contender-party')

            brgy_result_instance = BarangayElectionResults.objects.get(election_year__year=election_year)

            brgy_election_contender, created_contender = BarangayElectionContender.objects.get_or_create(
                name=contender_name,
                rank=contender_rank,
                vote_count=contender_vote_count,
                party=contender_party,
            )

            brgy_result_instance.contenders.add(brgy_election_contender)
            brgy_result_instance.save()

            brgy_election_contender.save()

        elif 'add-brgy-official-btn' in request.POST:
            official_first_name = request.POST.get('brgy-official-first-name').title()
            official_rank = request.POST.get('brgy-official-rank').title()

            official, created = BrgyOfficial.objects.get_or_create(
                brgy=brgy,
                name=official_first_name,
                rank=official_rank,
            )
            brgy_figures.officials.add(official)
            brgy_figures.save()

        elif 'add-school-head-btn' in request.POST:
            school_head_first_name = request.POST.get('school-head-first-name').title()
            school_head_rank = request.POST.get('school-head-rank')

            school_head, created = BrgySchoolHead.objects.get_or_create(
                brgy=brgy,
                name=school_head_first_name,
                rank=school_head_rank,
            )
            brgy_figures.school_heads.add(school_head)
            brgy_figures.save()

        elif 'add-election-type-btn' in request.POST:
            election_type_request = request.POST.get('election-type')
            election_year_str = request.POST.get('election-year')

            election_year = datetime.strptime(election_year_str, '%Y-%m-%d')

            election_type, created_election_type = ElectionType.objects.get_or_create(
                name=election_type_request.title()
            )

            brgy_election, created_election = BarangayElectionResults.objects.get_or_create(
                brgy=brgy,
                election_year=election_year,
                election_type=election_type
            )
            brgy_election.save()
        elif 'add-brgy-remark-btn' in request.POST:
            remark = request.POST.get('brgy-remarks')
            print(remark)
            brgy_remark, created = BarangayRemark.objects.get_or_create(
                brgy=brgy,
                remark=remark
            )
            brgy_remark.save()

            http_referrer = request.META.get('HTTP_REFERER')

            if http_referrer:
                return HttpResponseRedirect(http_referrer)
            else:
                return redirect('homepage')

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
        'brgy_figures': brgy_figures,
        'brgy_election_results': brgy_election_results,
        'election_dict': election_dict,
        'zipped_vote_count_party_name': list(zipped_vote_count_party_name),
        'years': years,
        'party_votes': party_votes,
        'barangay_official_ranks': barangay_official_ranks,
        'barangay_official_rank_len': barangay_official_rank_len,
        'barangay_school_head_ranks': barangay_school_head_ranks,
        'barangay_school_head_len': barangay_school_head_len,
        'barangay_election_type_len': barangay_election_type_len,
        'barangay_election_type': barangay_election_type,
        'barangay_contender_ranks': barangay_contender_ranks,
        'barangay_contender_ranks_len': barangay_contender_ranks_len,
        'barangay_official_party': barangay_official_party,
        'barangay_official_party_len': barangay_official_party_len,
        'barangay_remarks': barangay_remarks,
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

    sitio_remarks = SitioRemark.objects.filter(sitio=sitio)

    if request.method == 'POST':
        if 'edit-sitio-details-btn' in request.POST:
            form = ChangeSitioDetailsForm(request.POST, instance=sitio)
            if form.is_valid():
                sitio_edited = form.save(commit=False)
                sitio_edited.save()
                return redirect('sitio-profile', id=sitio.id)
        elif 'add-sitio-remark-btn' in request.POST:
            remark = request.POST.get('sitio-remark')

            sitio_remark, created = SitioRemark.objects.get_or_create(
                sitio=sitio,
                remark=remark,
            )
            sitio_remark.save()

            http_referrer = request.META.get('HTTP_REFERER')

            if http_referrer:
                return HttpResponseRedirect(http_referrer)
            else:
                return redirect('homepage')

    return render(request, 'sitio_profile.html', {
        'sitio_members': sitio_members,
        'sitio_leaders': sitio_leaders,
        'sitio': sitio,
        'edit_sitio_details_form': edit_sitio_details_form,
        'sitio_individual_sum': sitio_individual_sum,
        'logged_user': logged_user,
        'sitio_remarks': sitio_remarks,
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
    ambiguous_voters = AmbiguousVoters.objects.get(id=1)

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

    ambiguous_voters_list = []
    for voter in ambiguous_voters.voters.all():
        voter_name = voter.name
        if voter_name not in ambiguous_voters_list:
            ambiguous_voters_list.append(voter.user.username)

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
        'ambiguous_voters_list': ambiguous_voters_list,
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

    ambiguous_voters = AmbiguousVoters.objects.get(id=1)
    ambiguous_voters_list = []
    for voter in ambiguous_voters.voters.all():
        voter_name = voter.name
        if voter_name not in ambiguous_voters_list:
            ambiguous_voters_list.append(voter.user.username)

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
        'ambiguous_voters_list': ambiguous_voters_list,
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
                    round((len([m for m in members if m.brgy == member_brgy]) / member.brgy.brgy_voter_population) * 100),
                    member.brgy.brgy_voter_population,
                )]
            else:
                member_filtered_per_brgy_list[member_brgy].append((
                    member,
                    round((len([m for m in members if m.brgy == member_brgy]) / member.brgy.brgy_voter_population) * 100),
                    member.brgy.brgy_voter_population,
                ))
    else:
        the_brgy = None

    for member in members:
        member_brgy = member.brgy
        if member_brgy not in member_per_brgy_list:
            member_per_brgy_list[member_brgy] = [(
                member,
                round((len([m for m in members if m.brgy == member_brgy]) / member.brgy.brgy_voter_population) * 100),
                member.brgy.brgy_voter_population,
            )]
        else:
            member_per_brgy_list[member_brgy].append((
                member,
                round((len([m for m in members if m.brgy == member_brgy]) / member.brgy.brgy_voter_population) * 100),
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
def tag_leader_member(request, member_id, leader_id):
    if request.method == 'POST':
        member = Individual.objects.get(id=member_id)
        leader = Individual.objects.get(id=leader_id)

        individual_leader, created = IndividualLeaderCluster.objects.get_or_create(individual=leader)
        individual_leader.members.add(member)
        individual_leader.save()

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


@login_required(login_url='login')
@allowed_users(allowed_roles=['Admin'])
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


@login_required(login_url='login')
@allowed_users(allowed_roles=['Admin'])
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


@login_required(login_url='login')
@allowed_users(allowed_roles=['Admin'])
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
def ambiguous_members_report(request):
    request_user = request.user
    logged_user = Individual.objects.get(user__username=request_user)
    barangays = Barangay.objects.all()
    ambiguous_members = AmbiguousVoters.objects.get(id=1)
    ambiguous_voters_brgy = request.GET.get('ambiguous-voter-brgy')

    ambiguous_voters_filtered_brgy_list = []
    if ambiguous_voters_brgy:
        ambiguous_voters_filtered = AmbiguousVoters.objects.get(id=1)
        for voter in ambiguous_voters_filtered.voters.all():
            voter_brgy = voter.brgy.brgy_name
            if voter_brgy == ambiguous_voters_brgy:
                ambiguous_voters_filtered_brgy_list.append(voter)

    return render(request, 'ambiguous_voters_report.html', {
        'logged_user': logged_user,
        'ambiguous_members': ambiguous_members,
        'barangays': barangays,
        'ambiguous_voters_brgy': ambiguous_voters_brgy,
        'ambiguous_voters_filtered_brgy_list': ambiguous_voters_filtered_brgy_list,
    })


@login_required(login_url='login')
@allowed_users(allowed_roles=['Admin'])
def ambiguous_members_report_pdf(request):
    request_user = request.user
    logged_user = Individual.objects.get(user__username=request_user)
    barangays = Barangay.objects.all()
    ambiguous_members = AmbiguousVoters.objects.get(id=1)
    ambiguous_voters_brgy = request.GET.get('ambiguous-voter-brgy')

    ambiguous_voters_filtered_brgy_list = []
    if ambiguous_voters_brgy:
        ambiguous_voters_filtered = AmbiguousVoters.objects.get(id=1)
        for voter in ambiguous_voters_filtered.voters.all():
            voter_brgy = voter.brgy.brgy_name
            if voter_brgy == ambiguous_voters_brgy:
                ambiguous_voters_filtered_brgy_list.append(voter)

    html = render_to_string('ambiguous_voters_report_pdf.html', {
        'logged_user': logged_user,
        'ambiguous_members': ambiguous_members,
        'barangays': barangays,
        'ambiguous_voters_brgy': ambiguous_voters_brgy,
        'ambiguous_voters_filtered_brgy_list': ambiguous_voters_filtered_brgy_list,
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
    response['Content-Disposition'] = f'attachment; filename="ambiguous_voter.pdf"'
    return response


@login_required(login_url='login')
@allowed_users(allowed_roles=['Admin'])
def ambiguous_members_filter_report_pdf(request):
    barangays = Barangay.objects.all()
    ambiguous_voters_brgy = request.GET.get('ambiguous-voter-brgy')

    ambiguous_voters_filtered_brgy_list = []
    if ambiguous_voters_brgy:
        ambiguous_voters_filtered = AmbiguousVoters.objects.get(id=1)
        for voter in ambiguous_voters_filtered.voters.all():
            voter_brgy = voter.brgy.brgy_name
            if voter_brgy == ambiguous_voters_brgy:
                ambiguous_voters_filtered_brgy_list.append(voter)

    html = render_to_string('ambiguous_voters_filtered_report.html', {
        'barangays': barangays,
        'ambiguous_voters_brgy': ambiguous_voters_brgy,
        'ambiguous_voters_filtered_brgy_list': ambiguous_voters_filtered_brgy_list,
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
    response['Content-Disposition'] = f'attachment; filename="ambiguous_voter-{ambiguous_voters_brgy}.pdf"'
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
    admin_users = User.objects.filter(groups__name='Admin')
    for user in admin_users:
        promote_notification, created = Notification.objects.get_or_create(
            user=user,
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
            if user.is_superuser is True:
                return redirect('homepage')
            else:
                return redirect('individual-input')
            # if user.groups.filter(name='Admin').exists() and user.groups.filter(name='Leaders').exists():
            #     return redirect('homepage')
            # elif user.groups.filter(name='Leaders').exists():
            #     user_object = User.objects.get(username=username)
            #     leader_user = Leader.objects.get(user=user_object)
            #     return redirect('profile-leader', encryption=leader_user.encryption)
            # elif user.groups.filter(name='Members').exists():
            #     user_object = User.objects.get(username=username)
            #     member_user = Member.objects.get(user=user_object)
            #     return redirect('profile-member', encryption=member_user.encryption)
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


def suspect_voter(request, username):
    individual_user = User.objects.get(username=username)
    individual = Individual.objects.get(user=individual_user)
    ambiguous_members = AmbiguousVoters.objects.get(id=1)
    ambiguous_members.voters.add(individual)

    referring_url = request.META.get('HTTP_REFERER')

    if referring_url:
        # Redirect back to the referring page
        return HttpResponseRedirect(referring_url)
    else:
        # If there's no referring URL, redirect to a default page
        return redirect('homepage')


def unsuspect_voter(request, username):
    individual_user = User.objects.get(username=username)
    individual = Individual.objects.get(user=individual_user)
    ambiguous_members = AmbiguousVoters.objects.get(id=1)
    ambiguous_members.voters.remove(individual)

    referring_url = request.META.get('HTTP_REFERER')

    if referring_url:
        # Redirect back to the referring page
        return HttpResponseRedirect(referring_url)
    else:
        # If there's no referring URL, redirect to a default page
        return redirect('homepage')


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

            # Commented 3/13/2024 for sir IJ's and staff's request for convenience.
            # if User.objects.filter(email=registrant.email).exists() or\
            #         Registrants.objects.filter(email=registrant.email).exists():
            #     messages.error(request, 'Email Already Exists')

            # if password1 == password2 and not User.objects.filter(email=registrant.email).exists() and not \
            #         Registrants.objects.filter(email=registrant.email).exists():
            if password1 == password2:

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

                admin_users = User.objects.filter(groups__name='Admin')
                for user in admin_users:
                    registrant_notification, created = Notification.objects.get_or_create(
                        user=user,
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
    brgys  = Barangay.objects.all()
    request_user = request.user
    logged_user = Individual.objects.get(user__username=request_user)

    selected_brgy_filter = request.GET.get('registrant-brgy')
    if selected_brgy_filter:
        filtered_registrants_brgy = Registrants.objects.filter(brgy__brgy_name=selected_brgy_filter)
    else:
        filtered_registrants_brgy = []

    registrant_objects = Registrants.objects.all()
    return render(request, 'registrants.html', {
        'registrant_objects': registrant_objects,
        'logged_user': logged_user,
        'brgys': brgys,
        'selected_brgy_filter': selected_brgy_filter,
        'filtered_registrants_brgy': filtered_registrants_brgy,
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
    admin_users = User.objects.filter(groups__name='Admin')
    for user in admin_users:
        member_verified_notification, created = Notification.objects.get_or_create(
            user=user,
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

    admin_users = User.objects.filter(groups__name='Admin')
    for user in admin_users:
        leader_verified_notification, created = Notification.objects.get_or_create(
            user=user,
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
    admin_users = User.objects.filter(groups__name='Admin')
    for user in admin_users:
        denied_registration_notification, created = Notification.objects.get_or_create(
            user=user,
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
    admin_users = User.objects.filter(groups__name='Admin')
    for user in admin_users:
        denied_registration_notification, created = Notification.objects.get_or_create(
            user=user,
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
def non_admin_leader_profile(request, encryption):
    leader_user = User.objects.get(username=request.user.username)
    leader = Leader.objects.get(encryption=encryption)
    leaders_cluster = Cluster.objects.get(leader=leader)
    barangays = Barangay.objects.all()
    sitios = Sitio.objects.filter(brgy=leader.brgy)
    selected_sitio = request.POST.get('added-member-sitio')

    authenticated_user_request = request.user
    authenticated_leader = ''
    authenticated_member_stalk = ''
    if Leader.objects.filter(user=authenticated_user_request).exists():
        authenticated_leader = Leader.objects.get(user=authenticated_user_request)
    elif Member.objects.filter(user=authenticated_user_request).exists():
        authenticated_member_stalk = Member.objects.get(user=authenticated_user_request)

    leader_brgy_unassociated_members = Member.objects.filter(brgy=leader.brgy)

    members_brgy = [member for member in leader_brgy_unassociated_members]

    # First let's retrieve the search field in the base.html
    search_engine_field_query = request.GET.get('search')

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

    # Now that we have retrieve the search engine field in the base.html, it's time to delve into the login of it

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
    if search_engine_field_query:
        search_engine_result_member = [member for member in unassociated_members
                                       if search_engine_field_query.lower() in member.name.lower() or
                                       search_engine_field_query.lower() in member.sitio.name.lower()]

        total_results = len(search_engine_result_member)
    else:
        search_engine_result_member = []
        total_results = 0

    # # Added 3/5/2024 1:40 AM
    # leader_requests = LeaderConnectMemberRequest.objects.all()
    # leaders_request_list = []
    # for leaders in leader_requests:
    #     for leadera in leaders.requests.all():
    #         if leadera not in leaders_request_list:
    #             leaders_request_list.append(leaders.member.user.username)

    # Added 3/5/2024 1:40 AM
    if LeadersRequestConnect.objects.filter(leader=leader).exists():
        leader_member_request = LeadersRequestConnect.objects.get(leader=leader)
        leader_member_connect_request_list = []
        for members in leader_member_request.requests.all():
            member_username = members.user
            if member_username not in leader_member_connect_request_list:
                leader_member_connect_request_list.append(members.user.username)
    else:
        leader_member_connect_request_list = []

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
        if 'add-new-member-btn' in request.POST:
            form = MemberRegistrationForm(request.POST, request.FILES)
            if form.is_valid():
                member = form.save(commit=False)

                member.brgy = leader.brgy
                if selected_sitio != 'None':
                    print(f'Sitio: {selected_sitio}')
                    member_sitio = Sitio.objects.get(id=selected_sitio)
                    member.sitio = member_sitio
                else:
                    member.sitio = None

                member_enc_key = b'bSKEk2cT2V8vllCpMtQWsO2FxUVQdl3S_IHwBbEE4eQ='
                member_enc_cipher_suite = Fernet(member_enc_key)
                member_enc_signing_key = b'ColdSoulGenesis'
                member_enc_signer = Signer(key=member_enc_signing_key)

                # Commented 2/20/2024 encrypted_username = signer.sign(leader.name) # 1st Encrypt the username
                member_encrypted_id = member_enc_signer.sign(f'{member.id}')  # 1st Encrypt the username
                member_enc_data = member_encrypted_id.encode('utf-8')  # 2 Convert encrypted_username to bytes
                member_enc_encrypted_data = member_enc_cipher_suite.encrypt(member_enc_data)  # Final

                member.encryption = member_enc_encrypted_data
                # member.save()

                hashed_password = make_password(f'{member.name}{member.id}{leader.brgy}')

                user_created, created = User.objects.get_or_create(
                    email=leader_user.email,
                    password=hashed_password,
                )

                group = Group.objects.get(name='Members')
                user_created.groups.add(group)

                user_created.save()

                member.user = user_created
                member.save()
                user_created.username = f'{member.name}{member.id}'
                user_created.save()
                # Commented 2/20/2024 encrypted_username = signer.sign(leader.name) # 1st Encrypt the username
                member_encrypted_id = member_enc_signer.sign(f'{member.user}')  # 1st Encrypt the username
                member_enc_data = member_encrypted_id.encode('utf-8')  # 2 Convert encrypted_username to bytes
                member_enc_encrypted_data = member_enc_cipher_suite.encrypt(member_enc_data)  # Final

                member.encryption = member_enc_encrypted_data
                member.save()

                # Let's create a cluster object
                cluster, created = Cluster.objects.get_or_create(leader=leader)
                cluster.members.add(member)
                cluster.save()

                member_individual, created_individual = Individual.objects.get_or_create(
                    user=user_created,
                    name=member.name,
                    gender=member.gender,
                    age=member.age,
                    brgy=member.brgy,
                    sitio=member.sitio,
                    group="Member",
                    image=member.image,
                )
                member_individual.save()

                messages.success(request, 'Member Added')
                return redirect('profile-leader', encryption=leader.encryption)

        elif 'edit-leader-profile-btn' in request.POST:
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
                return redirect('profile-leader', encryption=leader.encryption)

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
        # 'leaders_request_list': leaders_request_list,
        'leader_member_connect_request_list': leader_member_connect_request_list,
        'authenticated_member_stalk': authenticated_member_stalk,
    })


@login_required(login_url='login')
@allowed_users(allowed_roles=['Admin', 'Leaders', 'Members'])
def non_admin_member_profile(request, encryption):
    # member_user = User.objects.get(username=username)
    member = Member.objects.get(encryption=encryption)
    members = Cluster.objects.values('members__name')
    leaders = Leader.objects.filter(brgy=member.brgy)

    request_leader_user = request.user
    if Leader.objects.filter(user=request_leader_user).exists():
        leader_request = Leader.objects.get(user=request.user)
    else:
        leader_request = ''
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
    if LeaderConnectMemberRequest.objects.filter(member=member).exists():
        leaders_request = LeaderConnectMemberRequest.objects.get(member=member)
    else:
        leaders_request = ''

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

            return redirect('profile-member', encryption=member.encryption)

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
        'leader_request': leader_request,
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

    if LeadersRequestConnect.objects.filter(leader=leader).exists():
        leader_member_request = LeadersRequestConnect.objects.get(leader=leader)
        leader_member_connect_request_list = []
        for members in leader_member_request.requests.all():
            member_username = members.user
            if member_username not in leader_member_connect_request_list:
                leader_member_connect_request_list.append(members.user.username)
    else:
        leader_member_connect_request_list = []

    # referring_url = request.META.get('HTTP_REFERER')
    #
    # if referring_url:
    #     # Redirect back to the referring page
    #     return HttpResponseRedirect(referring_url)
    # else:
    #     # If there's no referring URL, redirect to a default page
    #     return redirect('homepage')
    return render(request, 'leader_request_connect.html', {
        'member': member,
        'leader': leader,
        'member_connect_request': member_connect_request,
        'leader_connect_to_member': leader_connect_to_member,
        'leader_member_connect_request_list': leader_member_connect_request_list,
    })


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

    if LeadersRequestConnect.objects.filter(leader=leader).exists():
        leader_member_request = LeadersRequestConnect.objects.get(leader=leader)
        leader_member_connect_request_list = []
        for members in leader_member_request.requests.all():
            member_username = members.user
            if member_username not in leader_member_connect_request_list:
                leader_member_connect_request_list.append(members.user.username)
    else:
        leader_member_connect_request_list = []

    return render(request, 'leader_request_cancel.html', {
        'member': member,
        'leader': leader,
        'member_connect_request': member_connect_request,
        'leader_connect_to_member': leader_connect_to_member,
        'leader_member_connect_request_list': leader_member_connect_request_list,
    })
    # referring_url = request.META.get('HTTP_REFERER')
    #
    # if referring_url:
    #     # Redirect back to the referring page
    #     return HttpResponseRedirect(referring_url)
    # else:
    #     # If there's no referring URL, redirect to a default page
    #     return redirect('homepage')


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


def encrypt_members(request):
    members = Member.objects.all()
    leaders = Leader.objects.all()

    member_enc_key = b'bSKEk2cT2V8vllCpMtQWsO2FxUVQdl3S_IHwBbEE4eQ='
    member_enc_cipher_suite = Fernet(member_enc_key)
    member_enc_signing_key = b'ColdSoulGenesis'
    member_enc_signer = Signer(key=member_enc_signing_key)

    for member in members:

        # Commented 2/20/2024 encrypted_username = signer.sign(leader.name) # 1st Encrypt the username
        member_encrypted_id = member_enc_signer.sign(f'{member.id}')  # 1st Encrypt the username
        member_enc_data = member_encrypted_id.encode('utf-8')  # 2 Convert encrypted_username to bytes
        member_enc_encrypted_data = member_enc_cipher_suite.encrypt(member_enc_data)  # Final

        member.encryption = member_enc_encrypted_data
        member.save()

    for leader in leaders:
        # Commented 2/20/2024 encrypted_username = signer.sign(leader.name) # 1st Encrypt the username
        leader_encrypted_id = member_enc_signer.sign(f'{leader.user}')  # 1st Encrypt the username
        leader_enc_data = leader_encrypted_id.encode('utf-8')  # 2 Convert encrypted_username to bytes
        leader_enc_encrypted_data = member_enc_cipher_suite.encrypt(leader_enc_data)  # Final

        leader.encryption = leader_enc_encrypted_data
        leader.save()

    referring_url = request.META.get('HTTP_REFERER')

    if referring_url:
        # Redirect back to the referring page
        return HttpResponseRedirect(referring_url)
    else:
        # If there's no referring URL, redirect to a default page
        return redirect('homepage')


#APIS Functions
@api_view(['POST'])
def scanned_qr_data_mobile(request):
    data = request.data

    scanned_data = data['scanned_data']

    key = b'bSKEk2cT2V8vllCpMtQWsO2FxUVQdl3S_IHwBbEE4eQ='
    cipher_suite = Fernet(key)
    signing_key = b'Cold'
    signer = Signer(key=signing_key)

    plain_text = cipher_suite.decrypt(scanned_data)  # 1
    my_string = plain_text.decode('utf-8')  # 2
    decrypted_username = signer.unsign(my_string)  # 3

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
        serializer = QRCodeAttendanceSerializer(attendance, mamy=False)
        return Response(serializer.data)
    elif not Individual.objects.filter(user__username=decrypted_username).exists():
        return Response('Scanned data does not exist!')


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
        # return JsonResponse({decrypted_username: True})

    return render(request, 'qr_code_attendance.html')


def individual_view(request, individual_id):
    individual = Individual.objects.get(id=individual_id)

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
    encrypted_username = signer.sign(individual.id) # 1st Encrypt the username
    data = encrypted_username.encode('utf-8') # 2 Convert encrypted_username to bytes
    encrypted_data = cipher_suite.encrypt(data) # Final

    qr.add_data(encrypted_data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    img.save(f'management/static/images/qr-codes/QR-Code-{individual.name}-{individual.brgy}-{individual.id}.png')

    individual_parents, created_parents = IndividualParents.objects.get_or_create(individual=individual)
    individual_siblings, created_siblings = IndividualSiblings.objects.get_or_create(individual=individual)
    individual_spouse, created_spouse = IndividualSpouse.objects.get_or_create(individual=individual)
    individual_children, created_children = IndividualOffspring.objects.get_or_create(individual=individual)

    individual_leader = Individual.objects.filter(is_leader=True, brgy=individual.brgy)

    individual_members = None

    affiliated_individual_members = []
    affiliated_members = IndividualLeaderCluster.objects.all()
    for members in affiliated_members:
        for member in members.members.all():
            affiliated_individual_members.append(member.id)

    individual_associated_leader = IndividualLeaderCluster.objects.filter(members__id=individual.id)

    if individual.is_leader:
        individual_members, created_members = IndividualLeaderCluster.objects.get_or_create(
            individual=individual
        )

    start_coords = (11.05780, 124.3835)  # Manila coordinates
    if individual.lat is not None and individual.long is not None:
        end_coords = (individual.lat, individual.long)
    else:
        end_coords = (11.0582, 124.3890)    # Quezon City coordinates

    # Create a Folium map centered around the starting point
    # m = folium.Map(location=start_coords, zoom_start=12)
    m = folium.Map(location=[14.5995, 120.9842], zoom_start=11.5, tiles='CartoDB dark_matter')

    # Add markers for the start and end points
    folium.Marker(location=start_coords, popup="Start").add_to(m)
    folium.Marker(location=end_coords, popup="End").add_to(m)

    return render(request, 'individual_page.html', {
        'individual': individual,
        'individual_spouse': individual_spouse,
        'individual_parents': individual_parents,
        'individual_siblings': individual_siblings,
        'individual_children': individual_children,
        'individual_members': individual_members,
        'individual_leader': individual_leader,
        'affiliated_individual_members': affiliated_individual_members,
        'individual_associated_leader': individual_associated_leader,
        'start_coords': start_coords,
        'end_coords': end_coords,
    })


@login_required(login_url='login')
def individual_input(request):
    genders = Gender.objects.all()
    barangays = Barangay.objects.all()
    religions = Religion.objects.all()
    religion_len = len(religions)
    occupations = Occupation.objects.all()
    occupation_len = len(occupations)
    individual_general = Individual.objects.all()
    individual_mothers = Individual.objects.filter(is_parent=True, is_father=False)
    individual_fathers = Individual.objects.filter(is_parent=True, is_father=True)


    # print(religion_len)
    # if religion_len <= 1:
    #     print('Yasha!')
    # requested value

    if request.method == 'POST':
        individual_first_name = request.POST.get('individual-first-name')
        individual_middle_name = request.POST.get('individual-middle-name')
        individual_last_name = request.POST.get('individual-last-name')
        individual_suffix = request.POST.get('individual-suffix')
        individual_gender = request.POST.get('individual-gender')
        # individual_age = request.POST.get('individual-age')
        individual_brgy = request.POST.get('individual-brgy')
        individual_sitio = request.POST.get('individual-sitio-result-htmx')
        individual_house_image = request.FILES.get('individual-house-photo')
        individual_image = request.FILES.get('individual-photo')
        individual_religion = request.POST.get('individual-religion')
        individual_contact_number = request.POST.get('individual-number')
        individual_latitude = request.POST.get('individual-latitude')
        individual_longitude = request.POST.get('individual-longitude')
        individual_occupation = request.POST.get('individual-occupation')
        individual_oot_status = request.POST.get('individual-oot')
        individual_swing_voter_status = request.POST.get('individual-swing-voter')
        individual_leader_bool = request.POST.get('individual-leader-status')
        # individual_deceased_status = request.POST.get('individual-deceased-status')
        individual_ok_ok = request.POST.get('individual-cockroach')
        individual_birthday_str = request.POST.get('individual-birthday')

        # individual_birthday = datetime.strptime(individual_birthday_str, '%Y-%m-%d').date()
        individual_birthday = datetime.strptime(individual_birthday_str, '%Y-%m-%d').date()
        selected_gender = Gender.objects.get(id=individual_gender)
        selected_brgy = Barangay.objects.get(id=individual_brgy)

        if individual_sitio is not None:
            selected_sitio = Sitio.objects.get(id=individual_sitio)
        else:
            selected_sitio = None

        religion, created = Religion.objects.get_or_create(
            name=individual_religion
        )
        religion.save()

        occupation, created = Occupation.objects.get_or_create(
            name=individual_occupation
        )
        occupation.save()

        if selected_gender.gender == 'Male':
            father = True
        else:
            father = False

        if individual_latitude == "":
            latitude = None
        else:
            latitude = float(individual_latitude)

        if individual_longitude == "":
            longitude = None
        else:
            longitude = float(individual_longitude)

        age = int((timezone.now().date() - individual_birthday).days / 365.25)

        individual, created = Individual.objects.get_or_create(
            name=individual_first_name,
            middle_name=individual_middle_name,
            last_name=individual_last_name,
            suffix=individual_suffix,
            gender=selected_gender,
            age=age,
            brgy=selected_brgy,
            sitio=selected_sitio,
            group='Members',
            image=individual_image,
            house_image=individual_house_image,
            religion=religion,
            occupation=occupation,
            mobile=individual_contact_number,
            lat=latitude,
            long=longitude,
            is_father=father,
            birthday=individual_birthday,
            is_oot=individual_oot_status,
            is_swing_voter=individual_swing_voter_status,
            is_leader=individual_leader_bool,
            is_cockroach=individual_ok_ok,
        )

        IndividualSpouse.objects.get_or_create(
            individual=individual
        )
        IndividualParents.objects.get_or_create(
            individual=individual
        )
        IndividualSiblings.objects.get_or_create(
            individual=individual
        )
        IndividualOffspring.objects.get_or_create(
            individual=individual
        )

        return redirect('individual-family-conf', individual_id=individual.id)

    print(occupation_len)

    return render(request, 'individual_input.html', {
        'genders': genders,
        'barangays': barangays,
        'individual_general': individual_general,
        'individual_mothers': individual_mothers,
        'individual_fathers': individual_fathers,
        'religions': religions,
        'religion_len': religion_len,
        'occupations': occupations,
        'occupation_len': occupation_len,
    })


def individual_family_input(request, individual_id):
    individual = Individual.objects.get(id=individual_id)
    barangays = Barangay.objects.all()
    genders = Gender.objects.all()

    form_header = [
        'father',
        'mother',
        'sibling',
        'spouse',
        'child',
        'member'
    ]

    individual_parents, parent_created = IndividualParents.objects.get_or_create(individual=individual)
    individual_siblings, sibling_created = IndividualSiblings.objects.get_or_create(individual=individual)
    individual_children, child_created = IndividualOffspring.objects.get_or_create(individual=individual)
    individual_spouse, spouse_created = IndividualSpouse.objects.get_or_create(individual=individual)

    father_exists = IndividualParents.objects.filter(
        individual=individual,
        parents__is_father=True,
        parents__is_parent=True).exists()
    mother_exists = IndividualParents.objects.filter(
        individual=individual,
        parents__is_parent=True,
        parents__is_father=False).exists()

    return render(request, 'individual_family_conf.html', {
        'individual': individual,
        'barangays': barangays,
        'genders': genders,
        'individual_parents': individual_parents,
        'individual_siblings': individual_siblings,
        'individual_children': individual_children,
        'individual_spouse': individual_spouse,
        'father_exists': father_exists,
        'mother_exists': mother_exists,
        'form_header': form_header,
    })


# For individual & mother
def htmx_sitio_options(request):
    selected_brgy = request.POST.get('individual-brgy')
    sitios = Sitio.objects.filter(brgy__id=selected_brgy)

    return render(request, 'sitio_results_htmx.html', {
        'sitios': sitios,
    })


def htmx_sitio_options_one_ring(request):

    form_header = [
        'father',
        'mother',
        'sibling',
        'spouse',
        'child',
        'member'
    ]

    selected_brgy = request.POST.get('individual-brgy')
    sitios = Sitio.objects.filter(brgy__id=selected_brgy)

    return render(request, 'sitio_results_htmx_one_ring.html', {
        'sitios': sitios,
        'form_header': form_header,
    })


def one_ring(request, individual_id):
    individual = Individual.objects.get(id=individual_id)

    if request.method == 'POST':
        individual_form_header = request.POST.get('individual-form-header')
        individual_first_name = request.POST.get('individual-first-name')
        individual_middle_name = request.POST.get('individual-middle-name')
        individual_last_name = request.POST.get('individual-last-name')
        individual_suffix = request.POST.get('individual-suffix')
        individual_gender = request.POST.get('individual-gender')
        individual_brgy = request.POST.get('individual-brgy')
        individual_sitio = request.POST.get('individual-sitio-result-htmx')
        individual_house_image = request.FILES.get('individual-house-photo')
        individual_image = request.FILES.get('individual-photo')
        individual_religion = request.POST.get('individual-religion')
        individual_contact_number = request.POST.get('individual-number')
        individual_latitude = request.POST.get('individual-latitude')
        individual_longitude = request.POST.get('individual-longitude')
        individual_occupation = request.POST.get('individual-occupation')
        individual_leader_bool = request.POST.get('individual-leader-status')
        individual_oot_status = request.POST.get('individual-oot')
        individual_swing_voter_status = request.POST.get('individual-swing-voter')
        individual_ok_ok = request.POST.get('individual-cockroach')
        individual_birthday_str = request.POST.get('individual-birthday')

        individual_birthday = datetime.strptime(individual_birthday_str, '%Y-%m-%d').date()

        if individual_latitude == '':
            individual_latitude = None

        if individual_longitude == '':
            individual_longitude = None

        if individual_form_header == 'father':
            gender = Gender.objects.get(gender='Male')
        elif individual_form_header == 'mother':
            gender = Gender.objects.get(gender='Female')
        else:
            gender = Gender.objects.get(id=individual_gender)

        age = int((timezone.now().date() - individual_birthday).days / 365.25)
        # print(age)
        if individual_brgy != '' or individual_brgy is not None:
            brgy = Barangay.objects.get(id=individual_brgy)
        else:
            brgy = None

        if individual_sitio != '' or individual_sitio is not None:
            sitio = Sitio.objects.get(id=individual_sitio)
        else:
            sitio = None

        religion, created = Religion.objects.get_or_create(
            name=individual_religion
        )

        occupation, created = Occupation.objects.get_or_create(
            name=individual_occupation
        )

        individual_created, created = Individual.objects.get_or_create(
            name=individual_first_name,
            middle_name=individual_middle_name,
            last_name=individual_last_name,
            suffix=individual_suffix,
            gender=gender,
            age=age,
            brgy=brgy,
            sitio=sitio,
            image=individual_image,
            house_image=individual_house_image,
            religion=religion,
            occupation=occupation,
            mobile=individual_contact_number,
            lat=individual_latitude,
            long=individual_longitude,
            birthday=individual_birthday,
            is_leader=individual_leader_bool,
            is_oot=individual_oot_status,
            is_swing_voter=individual_swing_voter_status,
            is_cockroach=individual_ok_ok,
        )

        if individual_form_header == 'father':

            individual_created.is_parent = True
            individual_created.is_father = True
            individual_created.save()

            individual_parent_segment, created = IndividualParents.objects.get_or_create(
                individual=individual
            )
            individual_parent_segment.parents.add(individual_created)
            individual_parent_segment.save()

            individual_father_created, father_created = IndividualOffspring.objects.get_or_create(
                individual=individual_created
            )

            individual_father_created.children.add(individual)
            individual_father_created.save()

            # Checks if mother exists
            if IndividualParents.objects.filter(individual=individual, parents__is_father=False,
                                                parents__is_parent=True).exists():

                individual_created_father_spouse, father_created_spouse = IndividualSpouse.objects.get_or_create(
                    individual=individual_created,
                )

                derived_mother = IndividualParents.objects.get(
                    individual=individual,
                    parents__is_father=False,
                    parents__is_parent=True
                )

                for mother in derived_mother.parents.all():
                    if mother.is_parent and not mother.is_father:
                        individual_created_father_spouse.spouse = mother
                        individual_created_father_spouse.save()

                        mother_spouse, mother_created_spouse = IndividualSpouse.objects.get_or_create(
                            individual=mother
                        )
                        mother_spouse.spouse = individual_created
                        mother_spouse.save()

        elif individual_form_header == 'mother':
            individual_created.is_parent = True
            individual_created.is_father = False
            individual_created.save()

            individual_parent_segment, created = IndividualParents.objects.get_or_create(
                individual=individual
            )
            individual_parent_segment.parents.add(individual_created)
            individual_parent_segment.save()

            # Check if father Exists
            if IndividualParents.objects.filter(individual=individual, parents__is_father=True,
                                                parents__is_parent=True).exists():
                individual_created_mother_spouse, mother_created_spouse = IndividualSpouse.objects.get_or_create(
                    individual=individual_created,
                )

                derived_father = IndividualParents.objects.get(
                    individual=individual,
                    parents__is_father=True,
                    parents__is_parent=True
                )

                for father in derived_father.parents.all():
                    if father.is_parent and father.is_father:
                        individual_created_mother_spouse.spouse = father
                        individual_created_mother_spouse.save()

                        father_spouse, father_created_spouse = IndividualSpouse.objects.get_or_create(
                            individual=father
                        )
                        father_spouse.spouse = individual_created
                        father_spouse.save()

            individual_mother_created, mother_created = IndividualOffspring.objects.get_or_create(
                individual=individual_created
            )
            individual_mother_created.children.add(individual)
            individual_mother_created.save()

        elif individual_form_header == 'sibling':

            individual_sibling_segment, individual_sibling_created = IndividualSiblings.objects.get_or_create(
                individual=individual
            )
            individual_sibling_segment.siblings.add(individual_created)
            individual_sibling_segment.save()

            individual_sibling_created_segment, individual_created_sibling_created = IndividualSiblings.objects.get_or_create(
                individual=individual_created
            )
            individual_sibling_created_segment.siblings.add(individual)

            for sibling in individual_sibling_segment.siblings.all():
                sibling_s_sibling = IndividualSiblings.objects.get(individual=sibling)
                if individual_created.id != sibling.id:
                    individual_sibling_created_segment.siblings.add(sibling)
                    individual_sibling_created_segment.save()

                    sibling_s_sibling.siblings.add(individual_created)
                    sibling_s_sibling.save()

            if IndividualParents.objects.filter(individual=individual, parents__isnull=False).exists():
                individual_parents = IndividualParents.objects.get(
                    individual=individual
                )

                individual_created_parents, created_parents = IndividualParents.objects.get_or_create(
                    individual=individual_created
                )

                for parent in individual_parents.parents.all():
                    individual_created_parents.parents.add(parent)
                    individual_created_parents.save()

                    parent_offsprings, created_offspring = IndividualOffspring.objects.get_or_create(
                        individual=parent,
                    )
                    parent_offsprings.children.add(individual_created)
                    parent_offsprings.save()

        elif individual_form_header == 'spouse':
            individual_spouse_segment, spouse_created = IndividualSpouse.objects.get_or_create(
                individual=individual
            )
            individual_spouse_segment.spouse = individual_created
            individual_spouse_segment.save()

            individual_spouse_created_segment, individual_created_spouse = IndividualSpouse.objects.get_or_create(
                individual=individual_created
            )
            individual_spouse_created_segment.spouse = individual
            individual_spouse_created_segment.save()

        elif individual_form_header == 'child':
            # Associates the child to the Individual object relative to the page as a child from the
            # page it has been created
            individual_children_segment, created_child = IndividualOffspring.objects.get_or_create(
                individual=individual
            )
            individual_children_segment.children.add(individual_created)
            individual_children_segment.save()

            # Creates a Parent object to individual created in this case associates the created child to the
            # relative Individual Object
            individual_created_child_parent_segment, created_parent = IndividualParents.objects.get_or_create(
                individual=individual_created
            )
            individual_created_child_parent_segment.parents.add(individual)

            if individual.gender.gender == 'Male':
                individual.is_parent = True
                individual.is_father = True
                individual.save()
            else:
                individual.is_parent = True
                individual.is_father = False
                individual.save()

            # Associates the relative Individual object's spouse as a parent to the Child Individual object created
            if IndividualSpouse.objects.filter(individual=individual, spouse__isnull=False).exists():

                individual_spouse, created_spouse = IndividualSpouse.objects.get_or_create(
                    individual=individual,
                )

                if individual_spouse.spouse.gender == 'Female':
                    individual_spouse.spouse.is_parent = True
                    individual_spouse.spouse.is_father = False
                    individual_spouse.save()
                else:
                    individual_spouse.spouse.is_parent = True
                    individual_spouse.spouse.is_father = True
                    individual_spouse.save()

                individual_created_child_parent_segment.parents.add(individual_spouse.spouse)
                individual_created_child_parent_segment.save()

                individual_spouse_child, individual_spouse_created = IndividualOffspring.objects.get_or_create(
                    individual=individual_spouse.spouse,
                )
                individual_spouse_child.children.add(individual_created)
                individual_spouse_child.save()

            for child in individual_children_segment.children.all():
                derived_child_sibling_segment, created_child_seg = IndividualSiblings.objects.get_or_create(
                    individual=child
                )
                for child_sibling in individual_children_segment.children.all():
                    if child.id != child_sibling.id:
                        derived_child_sibling_segment.siblings.add(child_sibling)
                        derived_child_sibling_segment.save()

        elif individual_form_header == 'member':
            individual_leader_members_segment, \
                individual_leader_created, created = IndividualLeaderCluster.objects.get_or_create(
            )
            individual_leader_members_segment.members.add(individual_created)
            individual_leader_members_segment.save()

    http_referrer = request.META.get('HTTP_REFERER')
    if http_referrer:
        return HttpResponseRedirect(http_referrer)
    else:
        return redirect('homepage')


def individual_add_family(request):
    headers = [
        'father',
        'mother',
        'sibling',
        'spouse',
        'child',
        'member'
    ]

    if request.method == 'POST':
        form_header = request.POST.get('family-form-header')
    return render(request, 'individual_family_conf_singular.html', {
        'headers': headers,
    })


def election_results_func(request):
    congressional_election_type, created_congressional = ElectionType.objects.get_or_create(
        name='Congressional Election'
    )

    board_member_election_type, created_board_member_type = ElectionType.objects.get_or_create(
        name='Board Member Election'
    )

    mayoral_election_type, created_mayoral_type = ElectionType.objects.get_or_create(
        name='Mayoral Election'
    )

    congress_election_results = ElectionResults.objects.filter(election_type=congressional_election_type)
    board_member_election_results = ElectionResults.objects.filter(election_type=board_member_election_type)
    mayoral_election_results = ElectionResults.objects.filter(election_type=mayoral_election_type)

    congressional_ranks = []
    congressional_parties = []
    congressional_election_dict = {}
    for election in congress_election_results:
        election_date = election.election_year
        year = datetime.strftime(election_date, '%Y')
        if year not in congressional_election_dict:
            congressional_election_dict[year] = {}
        for contender in election.contenders.all():
            party = contender.party
            if contender.rank not in congressional_ranks:
                congressional_ranks.append(contender.rank)
            if party not in congressional_election_dict[year]:
                congressional_election_dict[year][party] = []
                congressional_parties.append(party)
            congressional_election_dict[year][party].append(contender)

    congressional_ranks_len = len(congressional_ranks)
    congressional_parties_len = len(congressional_parties)

    congressional_contender_election_data = {}
    for election_type, parties in congressional_election_dict.items():
        for party, contenders in parties.items():
            # Calculate the average vote count for this party
            avg_vote_count = sum(contender.vote_count for contender in contenders) / len(contenders)
            if election_type not in congressional_contender_election_data:
                congressional_contender_election_data[election_type] = [(party, avg_vote_count)]
            else:
                congressional_contender_election_data[election_type].append((party, avg_vote_count))

    board_member_ranks = []
    board_member_parties = []
    board_member_election_result_dict = {}
    for election in board_member_election_results:
        election_date = election.election_year
        year = datetime.strftime(election_date, '%Y')

        if year not in board_member_election_result_dict:
            board_member_election_result_dict[year] = {}

        for contender in election.contenders.all():
            party = contender.party
            if contender.rank not in board_member_ranks:
                board_member_ranks.append(contender.rank)
            if party not in board_member_election_result_dict[year]:
                board_member_election_result_dict[year][party] = []
                board_member_parties.append(party)
            board_member_election_result_dict[year][party].append(contender)

    board_member_ranks_len = len(board_member_ranks)
    board_member_parties_len = len(board_member_parties)

    board_member_contender_election_data = {}
    for election_type, parties in board_member_election_result_dict.items():
        for party, contenders in parties.items():
            # Calculate the average vote count for this party
            avg_vote_count = sum(contender.vote_count for contender in contenders) / len(contenders)
            if election_type not in board_member_contender_election_data:
                board_member_contender_election_data[election_type] = [(party, avg_vote_count)]
            else:
                board_member_contender_election_data[election_type].append((party, avg_vote_count))

    mayoral_ranks = []
    mayoral_parties = []
    mayoral_election_dict = {}
    for election in mayoral_election_results:
        election_date = election.election_year
        year = datetime.strftime(election_date, '%Y')

        if year not in mayoral_election_dict:
            mayoral_election_dict[year] = {}

        for contender in election.contenders.all():
            party = contender.party
            if contender.rank not in mayoral_ranks:
                mayoral_ranks.append(contender.rank)
            if party not in mayoral_election_dict[year]:
                mayoral_election_dict[year][party] = []
                mayoral_parties.append(party)
            mayoral_election_dict[year][party].append(contender)

    mayoral_ranks_len = len(mayoral_ranks)
    mayoral_parties_len = len(mayoral_parties)

    mayoral_contender_election_data = {}
    for election_type, parties in mayoral_election_dict.items():
        for party, contenders in parties.items():
            # Calculate the average vote count for this party
            avg_vote_count = sum(contender.vote_count for contender in contenders) / len(contenders)
            if election_type not in mayoral_contender_election_data:
                mayoral_contender_election_data[election_type] = [(party, avg_vote_count)]
            else:
                mayoral_contender_election_data[election_type].append((party, avg_vote_count))

    if request.method == 'POST':
        if 'create-congress-election-btn' in request.POST:
            congress_election_date_str = request.POST.get('congress-election-date')
            congress_election_date = datetime.strptime(congress_election_date_str, '%Y-%m-%d')

            congress_election_result, created_congress_election = ElectionResults.objects.get_or_create(
                election_type=congressional_election_type,
                election_year=congress_election_date,
            )

        elif 'congressional-election-type-btn' in request.POST:
            congress_contender_name = request.POST.get('congress-contender-name')
            congress_contender_rank = request.POST.get('congress-contender-rank')
            congress_contender_votes = request.POST.get('congress-contender-votes')
            congress_contender_party = request.POST.get('congress-contender-party')
            congress_contender_election_instance = request.POST.get('congress-election-year')

            congress_election_contender, created_contender = ElectionContender.objects.get_or_create(
                name=congress_contender_name,
                rank=congress_contender_rank,
                vote_count=congress_contender_votes,
                party=congress_contender_party
            )

            congress_election = ElectionResults.objects.get(election_year__year=congress_contender_election_instance)
            congress_election.contenders.add(congress_election_contender)
            congress_election.save()

        elif 'create-board-election-type-btn' in request.POST:
            board_member_election_date_str = request.POST.get('create-board-member-election-result')
            board_member_election_year = datetime.strptime(board_member_election_date_str, '%Y-%m-%d')

            board_election_year, board_election_created = ElectionResults.objects.get_or_create(
                election_type=board_member_election_type,
                election_year=board_member_election_year
            )

        elif 'add-board-member-contender-btn' in request.POST:
            board_member_name = request.POST.get('board-member-contender-name')
            board_member_rank = request.POST.get('board-member-contender-rank')
            board_member_votes = request.POST.get('board-member-contender-votes')
            board_member_party = request.POST.get('board-member-type-party')
            board_member_election_instance = request.POST.get('board-member-election-instance')

            board_member_contender, contender_created = ElectionContender.objects.get_or_create(
                name=board_member_name,
                rank=board_member_rank,
                vote_count=board_member_votes,
                party=board_member_party,
            )

            board_member_election = ElectionResults.objects.get(
                election_year__year=board_member_election_instance
            )

            board_member_election.contenders.add(board_member_contender)
            board_member_election.save()

        elif 'create-mayoral-election-btn' in request.POST:
            mayoral_election_date_str = request.POST.get('create-mayoral-election-instance')
            mayoral_election_date = datetime.strptime(mayoral_election_date_str, '%Y-%m-%d')

            mayoral_election_instance, created_instance = ElectionResults.objects.get_or_create(
                election_type=mayoral_election_type,
                election_year=mayoral_election_date
            )

        elif 'create-mayoral-contender-btn' in request.POST:
            mayoral_contender_name = request.POST.get('mayoral-contender-name')
            mayoral_contender_rank = request.POST.get('mayoral-contender-rank')
            mayoral_contender_votes = request.POST.get('mayoral-contender-votes')
            mayoral_contender_party = request.POST.get('mayoral-contender-party')
            mayoral_contender_instance = request.POST.get('mayoral-contender-election-instance')

            mayoral_contender, created_contender = ElectionContender.objects.get_or_create(
                name=mayoral_contender_name,
                rank=mayoral_contender_rank,
                vote_count=mayoral_contender_votes,
                party=mayoral_contender_party
            )

            mayoral_election_instance = ElectionResults.objects.get(
                election_year__year=mayoral_contender_instance
            )
            mayoral_election_instance.contenders.add(mayoral_contender)
            mayoral_election_instance.save()

    return render(request, 'election_results.html', {
        'congress_election_results': congress_election_results,
        'board_member_election_results': board_member_election_results,
        'mayoral_election_results': mayoral_election_results,
        'mayoral_election_type': mayoral_election_type,
        'mayoral_election_dict': mayoral_election_dict,
        'congressional_election_dict': congressional_election_dict,
        'board_member_election_result_dict': board_member_election_result_dict,
        'congressional_contender_election_data': congressional_contender_election_data,
        'board_member_contender_election_data': board_member_contender_election_data,
        'mayoral_contender_election_data': mayoral_contender_election_data,

        'congressional_ranks': congressional_ranks,
        'congressional_parties': congressional_parties,
        'congressional_ranks_len': congressional_ranks_len,
        'congressional_parties_len': congressional_parties_len,

        'board_member_ranks': board_member_ranks,
        'board_member_parties': board_member_parties,
        'board_member_ranks_len': board_member_ranks_len,
        'board_member_parties_len': board_member_parties_len,

        'mayoral_ranks': mayoral_ranks,
        'mayoral_parties': mayoral_parties,
        'mayoral_ranks_len': mayoral_ranks_len,
        'mayoral_parties_len': mayoral_parties_len,
    })


def encode_church(request):
    brgys = Barangay.objects.all()
    if request.method == 'POST':
        church_brgy = request.POST.get('individual-brgy')
        church_lat = request.POST.get('church-lat')
        church_long = request.POST.get('church-long')
        church_sitio = request.POST.get('individual-sitio-result-htmx')

        if church_lat == '':
            church_lat = 0

        if church_long == '':
            church_long = 0

        brgy = Barangay.objects.get(id=church_brgy)
        if church_sitio == '' or church_sitio is None:
            sitio = None
        else:
            sitio = Sitio.objects.get(id=church_sitio)

        church, created = Church.objects.get_or_create(
            brgy=brgy,
            sitio=sitio,
            lat=church_lat,
            long=church_long,
        )
        church.save()

        http_referrer = request.META.get('HTTP_REFERER')

        if http_referrer:
            return HttpResponseRedirect(http_referrer)
        else:
            return redirect('homepage')

    churches = Church.objects.filter(lat__isnull=False, long__isnull=False)

    if churches.exists():
        center_lat = churches.aggregate(models.Avg('lat'))['lat__avg']
        center_long = churches.aggregate(models.Avg('long'))['long__avg']
        folium_map = folium.Map(location=[center_lat, center_long], zoom_start=11.5, tiles='CartoDB dark_matter')

        for church in churches:

            folium.Marker(
                location=[church.lat, church.long],
            ).add_to(folium_map)

        map_html = folium_map._repr_html_()
    else:
        map_html = None

    return render(request, 'church_input.html', {
        'churches': churches,
        'map_html': map_html,
        'brgys': brgys,
    })


def brgy_profile_htmx_trigger_party_input(request):
    return render(request, 'htmx-templates/party_input.html', {
    })


def trigger_select_contender_party(request):
    barangay_official_party = []
    for contender in BarangayElectionContender.objects.all():
        if contender.party not in barangay_official_party:
            barangay_official_party.append(contender.party)

    barangay_official_party_len = len(barangay_official_party)

    return render(request, 'htmx-templates/trigger_select_input_party_contender.html', {
        'barangay_official_party': barangay_official_party,
        'barangay_official_party_len': barangay_official_party_len,
    })


def captain_rank_manual_input(request):
    return render(request, "htmx-templates/captain_input.html")


def brgy_captain_existing_ranks(request):
    barangay_contender_ranks = []
    for contender in BarangayElectionContender.objects.all():
        if contender.rank not in barangay_contender_ranks:
            barangay_contender_ranks.append(contender.rank)

    barangay_contender_ranks_len = len(barangay_contender_ranks)
    return render(request, 'htmx-templates/captain_existing_ranks.html', {
        'barangay_contender_ranks': barangay_contender_ranks,
        'barangay_contender_ranks_len': barangay_contender_ranks_len,
    })


def election_type_input_trigger(request):
    return render(request, 'htmx-templates/election_type_input.html')


def election_existing_type_trigger(request):
    barangay_election_type = ElectionType.objects.all()
    barangay_election_type_len = len(barangay_election_type)

    return render(request, 'htmx-templates/election_existing_types.html', {
        'barangay_election_type': barangay_election_type,
        'barangay_election_type_len': barangay_election_type_len,
    })


def brgy_official_rank_input_trigger(request):
    return render(request, 'htmx-templates/brgy_official_input.html')


def brgy_official_existing_rank(request):
    barangay_official_ranks = []
    for official in BrgyOfficial.objects.all():
        if official.rank not in barangay_official_ranks:
            barangay_official_ranks.append(official.rank)

    barangay_official_rank_len = len(barangay_official_ranks)

    return render(request, 'htmx-templates/brgy_official_existing_ranks.html', {
        'barangay_official_ranks': barangay_official_ranks,
        'barangay_official_rank_len': barangay_official_rank_len,
    })


def school_heads_input_trigger(request):
    return render(request, 'htmx-templates/brgy_school_head_rank_input.html')


def school_head_existing_rank(request):
    barangay_school_head_ranks = []
    for school_head in BrgySchoolHead.objects.all():
        if school_head.rank not in barangay_school_head_ranks:
            barangay_school_head_ranks.append(school_head.rank)

    barangay_school_head_len = len(barangay_school_head_ranks)
    return render(request, 'htmx-templates/brgy_existing_school_head_rank.html', {
        'barangay_school_head_ranks': barangay_school_head_ranks,
        'barangay_school_head_len': barangay_school_head_len,
    })

    # barangay_official_party = []
    # for contender in BarangayElectionContender.objects.all():
    #     if contender.party not in barangay_official_party:
    #         barangay_official_party.append(contender.party)
    #
    # barangay_official_party_len = len(barangay_official_party)

    # barangay_election_type = ElectionType.objects.all()
    # barangay_election_type_len = len(barangay_election_type)
    #
    # barangay_contender_ranks = []
    # for contender in BarangayElectionContender.objects.all():
    #     if contender.rank not in barangay_contender_ranks:
    #         barangay_contender_ranks.append(contender.rank)
    #
    # barangay_contender_ranks_len = len(barangay_contender_ranks)


    # board_member_election_type, created_board_member_type = ElectionType.objects.get_or_create(
    #     name='Board Member Election'
    # )
    #
    # mayoral_election_type, created_mayoral_type = ElectionType.objects.get_or_create(
    #     name='Mayoral Election'
    # )

    # board_member_election_results = ElectionResults.objects.filter(election_type=board_member_election_type)
    # mayoral_election_results = ElectionResults.objects.filter(election_type=mayoral_election_type)

#     board_member_ranks = []
#     board_member_parties = []
#     board_member_election_result_dict = {}
#     for election in board_member_election_results:
#         election_date = election.election_year
#         year = datetime.strftime(election_date, '%Y')
#
#         if year not in board_member_election_result_dict:
#             board_member_election_result_dict[year] = {}
#
#         for contender in election.contenders.all():
#             party = contender.party
#             if contender.rank not in board_member_ranks:
#                 board_member_ranks.append(contender.rank)
#             if party not in board_member_election_result_dict[year]:
#                 board_member_election_result_dict[year][party] = []
#                 board_member_parties.append(party)
#             board_member_election_result_dict[year][party].append(contender)
#
#     board_member_ranks_len = len(board_member_ranks)
#     board_member_parties_len = len(board_member_parties)
#     mayoral_ranks = []
#     mayoral_parties = []
#     mayoral_election_dict = {}
#     for election in mayoral_election_results:
#         election_date = election.election_year
#         year = datetime.strftime(election_date, '%Y')
#
#         if year not in mayoral_election_dict:
#             mayoral_election_dict[year] = {}
#
#         for contender in election.contenders.all():
#             party = contender.party
#             if contender.rank not in mayoral_ranks:
#                 mayoral_ranks.append(contender.rank)
#             if party not in mayoral_election_dict[year]:
#                 mayoral_election_dict[year][party] = []
#                 mayoral_parties.append(party)
#             mayoral_election_dict[year][party].append(contender)
#
#     mayoral_ranks_len = len(mayoral_ranks)
#     mayoral_parties_len = len(mayoral_parties)


def congressional_add_new_rank_trigger(request):
    congressional_election_type, created_congressional = ElectionType.objects.get_or_create(
        name='Congressional Election'
    )

    congress_election_results = ElectionResults.objects.filter(election_type=congressional_election_type)

    congressional_ranks = []
    congressional_parties = []
    congressional_election_dict = {}
    for election in congress_election_results:
        election_date = election.election_year
        year = datetime.strftime(election_date, '%Y')
        if year not in congressional_election_dict:
            congressional_election_dict[year] = {}
        for contender in election.contenders.all():
            party = contender.party
            if contender.rank not in congressional_ranks:
                congressional_ranks.append(contender.rank)
            if party not in congressional_election_dict[year]:
                congressional_election_dict[year][party] = []
                congressional_parties.append(party)
            congressional_election_dict[year][party].append(contender)

    congressional_ranks_len = len(congressional_ranks)
    congressional_parties_len = len(congressional_parties)

    return render(request, 'htmx-templates/congressional_rank_input.html', {
        'congressional_election_dict': congressional_election_dict,
    })


def congress_select_existing_rank(request):
    congressional_election_type, created_congressional = ElectionType.objects.get_or_create(
        name='Congressional Election'
    )

    congress_election_results = ElectionResults.objects.filter(election_type=congressional_election_type)

    congressional_ranks = []
    congressional_parties = []
    congressional_election_dict = {}
    for election in congress_election_results:
        election_date = election.election_year
        year = datetime.strftime(election_date, '%Y')
        if year not in congressional_election_dict:
            congressional_election_dict[year] = {}
        for contender in election.contenders.all():
            party = contender.party
            if contender.rank not in congressional_ranks:
                congressional_ranks.append(contender.rank)
            if party not in congressional_election_dict[year]:
                congressional_election_dict[year][party] = []
                congressional_parties.append(party)
            congressional_election_dict[year][party].append(contender)

    return render(request, 'htmx-templates/congress-select-existing-rank.html', {
        'congressional_ranks': congressional_ranks,
        'congressional_parties': congressional_parties,
        'congressional_election_dict': congressional_election_dict,
    })


def congress_party_input(request):
    congressional_election_type, created_congressional = ElectionType.objects.get_or_create(
        name='Congressional Election'
    )

    congress_election_results = ElectionResults.objects.filter(election_type=congressional_election_type)

    congressional_ranks = []
    congressional_parties = []
    congressional_election_dict = {}
    for election in congress_election_results:
        election_date = election.election_year
        year = datetime.strftime(election_date, '%Y')
        if year not in congressional_election_dict:
            congressional_election_dict[year] = {}
        for contender in election.contenders.all():
            party = contender.party
            if contender.rank not in congressional_ranks:
                congressional_ranks.append(contender.rank)
            if party not in congressional_election_dict[year]:
                congressional_election_dict[year][party] = []
                congressional_parties.append(party)
            congressional_election_dict[year][party].append(contender)

    congressional_ranks_len = len(congressional_ranks)
    congressional_parties_len = len(congressional_parties)
    return render(request, 'htmx-templates/congress-party-input.html', {
        'congressional_election_dict': congressional_election_dict,
    })


def congress_existing_party(request):
    congressional_election_type, created_congressional = ElectionType.objects.get_or_create(
        name='Congressional Election'
    )

    congress_election_results = ElectionResults.objects.filter(election_type=congressional_election_type)

    congressional_ranks = []
    congressional_parties = []
    congressional_election_dict = {}
    for election in congress_election_results:
        election_date = election.election_year
        year = datetime.strftime(election_date, '%Y')
        if year not in congressional_election_dict:
            congressional_election_dict[year] = {}
        for contender in election.contenders.all():
            party = contender.party
            if contender.rank not in congressional_ranks:
                congressional_ranks.append(contender.rank)
            if party not in congressional_election_dict[year]:
                congressional_election_dict[year][party] = []
                congressional_parties.append(party)
            congressional_election_dict[year][party].append(contender)

    return render(request, 'htmx-templates/congress-existing-party.html', {
        'congressional_election_dict': congressional_election_dict,
        'congressional_parties': congressional_parties,
    })


def board_member_rank_input(request):
    board_member_election_type, created_board_member_type = ElectionType.objects.get_or_create(
        name='Board Member Election'
    )
    board_member_election_results = ElectionResults.objects.filter(election_type=board_member_election_type)
    board_member_ranks = []
    board_member_parties = []
    board_member_election_result_dict = {}
    for election in board_member_election_results:
        election_date = election.election_year
        year = datetime.strftime(election_date, '%Y')

        if year not in board_member_election_result_dict:
            board_member_election_result_dict[year] = {}

        for contender in election.contenders.all():
            party = contender.party
            if contender.rank not in board_member_ranks:
                board_member_ranks.append(contender.rank)
            if party not in board_member_election_result_dict[year]:
                board_member_election_result_dict[year][party] = []
                board_member_parties.append(party)
            board_member_election_result_dict[year][party].append(contender)
    return render(request, 'htmx-templates/board-member-rank-input.html', {
        'board_member_election_result_dict': board_member_election_result_dict,
    })


def board_member_existing_rank(request):
    board_member_election_type, created_board_member_type = ElectionType.objects.get_or_create(
        name='Board Member Election'
    )

    board_member_election_results = ElectionResults.objects.filter(election_type=board_member_election_type)
    board_member_ranks = []
    board_member_parties = []
    board_member_election_result_dict = {}
    for election in board_member_election_results:
        election_date = election.election_year
        year = datetime.strftime(election_date, '%Y')

        if year not in board_member_election_result_dict:
            board_member_election_result_dict[year] = {}

        for contender in election.contenders.all():
            party = contender.party
            if contender.rank not in board_member_ranks:
                board_member_ranks.append(contender.rank)
            if party not in board_member_election_result_dict[year]:
                board_member_election_result_dict[year][party] = []
                board_member_parties.append(party)
            board_member_election_result_dict[year][party].append(contender)

    return render(request, 'htmx-templates/board-member-existing-ranks.html', {
        'board_member_ranks': board_member_ranks,
        'board_member_election_result_dict': board_member_election_result_dict,
    })


def board_member_party_input(request):
    board_member_election_type, created_board_member_type = ElectionType.objects.get_or_create(
        name='Board Member Election'
    )

    board_member_election_results = ElectionResults.objects.filter(election_type=board_member_election_type)
    board_member_ranks = []
    board_member_parties = []
    board_member_election_result_dict = {}
    for election in board_member_election_results:
        election_date = election.election_year
        year = datetime.strftime(election_date, '%Y')

        if year not in board_member_election_result_dict:
            board_member_election_result_dict[year] = {}

        for contender in election.contenders.all():
            party = contender.party
            if contender.rank not in board_member_ranks:
                board_member_ranks.append(contender.rank)
            if party not in board_member_election_result_dict[year]:
                board_member_election_result_dict[year][party] = []
                board_member_parties.append(party)
            board_member_election_result_dict[year][party].append(contender)

    return render(request, 'htmx-templates/board-member-party-input.html', {
        'board_member_election_result_dict': board_member_election_result_dict,
    })


def board_member_existing_party(request):
    board_member_election_type, created_board_member_type = ElectionType.objects.get_or_create(
        name='Board Member Election'
    )

    board_member_election_results = ElectionResults.objects.filter(election_type=board_member_election_type)
    board_member_ranks = []
    board_member_parties = []
    board_member_election_result_dict = {}
    for election in board_member_election_results:
        election_date = election.election_year
        year = datetime.strftime(election_date, '%Y')

        if year not in board_member_election_result_dict:
            board_member_election_result_dict[year] = {}

        for contender in election.contenders.all():
            party = contender.party
            if contender.rank not in board_member_ranks:
                board_member_ranks.append(contender.rank)
            if party not in board_member_election_result_dict[year]:
                board_member_election_result_dict[year][party] = []
                board_member_parties.append(party)
            board_member_election_result_dict[year][party].append(contender)

    return render(request, 'htmx-templates/board-member-existing-party.html', {
        'board_member_election_result_dict': board_member_election_result_dict,
        'board_member_parties': board_member_parties,
    })


def mayoral_rank_input(request):
    mayoral_election_type, created_mayoral_type = ElectionType.objects.get_or_create(
        name='Mayoral Election'
    )

    mayoral_election_results = ElectionResults.objects.filter(election_type=mayoral_election_type)

    mayoral_ranks = []
    mayoral_parties = []
    mayoral_election_dict = {}
    for election in mayoral_election_results:
        election_date = election.election_year
        year = datetime.strftime(election_date, '%Y')

        if year not in mayoral_election_dict:
            mayoral_election_dict[year] = {}

        for contender in election.contenders.all():
            party = contender.party
            if contender.rank not in mayoral_ranks:
                mayoral_ranks.append(contender.rank)
            if party not in mayoral_election_dict[year]:
                mayoral_election_dict[year][party] = []
                mayoral_parties.append(party)
            mayoral_election_dict[year][party].append(contender)
    return render(request, 'htmx-templates/mayoral-rank-input.html', {
        'mayoral_election_dict': mayoral_election_dict,
    })


def mayoral_existing_rank(request):
    mayoral_election_type, created_mayoral_type = ElectionType.objects.get_or_create(
        name='Mayoral Election'
    )

    mayoral_election_results = ElectionResults.objects.filter(election_type=mayoral_election_type)

    mayoral_ranks = []
    mayoral_parties = []
    mayoral_election_dict = {}
    for election in mayoral_election_results:
        election_date = election.election_year
        year = datetime.strftime(election_date, '%Y')

        if year not in mayoral_election_dict:
            mayoral_election_dict[year] = {}

        for contender in election.contenders.all():
            party = contender.party
            if contender.rank not in mayoral_ranks:
                mayoral_ranks.append(contender.rank)
            if party not in mayoral_election_dict[year]:
                mayoral_election_dict[year][party] = []
                mayoral_parties.append(party)
            mayoral_election_dict[year][party].append(contender)
    return render(request, 'htmx-templates/mayoral-existing-rank.html', {
        'mayoral_election_dict': mayoral_election_dict,
        'mayoral_ranks': mayoral_ranks,
    })


def mayoral_party_input(request):
    mayoral_election_type, created_mayoral_type = ElectionType.objects.get_or_create(
        name='Mayoral Election'
    )

    mayoral_election_results = ElectionResults.objects.filter(election_type=mayoral_election_type)

    mayoral_ranks = []
    mayoral_parties = []
    mayoral_election_dict = {}
    for election in mayoral_election_results:
        election_date = election.election_year
        year = datetime.strftime(election_date, '%Y')

        if year not in mayoral_election_dict:
            mayoral_election_dict[year] = {}

        for contender in election.contenders.all():
            party = contender.party
            if contender.rank not in mayoral_ranks:
                mayoral_ranks.append(contender.rank)
            if party not in mayoral_election_dict[year]:
                mayoral_election_dict[year][party] = []
                mayoral_parties.append(party)
            mayoral_election_dict[year][party].append(contender)

    return render(request, 'htmx-templates/mayoral-party-input.html', {
        'mayoral_election_dict': mayoral_election_dict,
    })


def mayoral_existing_party(request):
    mayoral_election_type, created_mayoral_type = ElectionType.objects.get_or_create(
        name='Mayoral Election'
    )

    mayoral_election_results = ElectionResults.objects.filter(election_type=mayoral_election_type)

    mayoral_ranks = []
    mayoral_parties = []
    mayoral_election_dict = {}
    for election in mayoral_election_results:
        election_date = election.election_year
        year = datetime.strftime(election_date, '%Y')

        if year not in mayoral_election_dict:
            mayoral_election_dict[year] = {}

        for contender in election.contenders.all():
            party = contender.party
            if contender.rank not in mayoral_ranks:
                mayoral_ranks.append(contender.rank)
            if party not in mayoral_election_dict[year]:
                mayoral_election_dict[year][party] = []
                mayoral_parties.append(party)
            mayoral_election_dict[year][party].append(contender)

    return render(request, 'htmx-templates/mayoral-existing-party.html', {
        'mayoral_parties': mayoral_parties,
        'mayoral_election_dict': mayoral_election_dict,
    })


def htmx_existing_religion(request):
    religions = Religion.objects.all()

    return render(request, 'htmx-templates/religion_existing.html', {
        'religions': religions,
    })


def htmx_new_religion(request):
    return render(request, 'htmx-templates/religion_new_input.html', {

    })


def htmx_existing_occupation(request):
    occupations = Occupation.objects.all()
    return render(request, 'htmx-templates/occupation-existing.html', {
        'occupations': occupations,
    })


def htmx_new_occupation(request):

    return render(request, 'htmx-templates/occupation-new.html')
