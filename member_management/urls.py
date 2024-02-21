"""member_management URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from management import views
from django.conf.urls.static import static
from member_management import settings


urlpatterns = [
    path('admin/', admin.site.urls),
    path('home/', views.homepage, name='homepage'),

    path('brgy/<str:brgy_name>/', views.barangay_members, name='member-brgy'),
    path('sitio/<int:id>/', views.sitio_profile, name='sitio-profile'),

    path('dashboard/', views.dashboard, name='dashboard'),
    path('leader/profile/<str:name>/<str:username>/', views.leader_cluster, name='cluster'),
    path('member-profile/<str:name>/<int:id>/', views.member_profile, name='member-profile'),
    path('add-brgy/', views.add_barangay, name='add-brgy'),
    path('add-members/', views.add_members, name='add-members'),
    path('clusters/', views.clusters, name='clusters'),
    path('add-leader/', views.add_leader, name='add-leader'),
    path('reports/', views.reports, name='reports'),

    path('report/member-count-brgy/', views.member_count_per_brgy, name='member-count-brgy'),
    path('report/leaders/member/None/', views.no_members_leader, name='no-member-leader'),
    path('report/members/leader/None/', views.leaderless_members, name='leaderless-members'),
    path('report/no-member-brgys/', views.no_member_barangays, name='no-member-brgys'),
    path('report/members/all/', views.all_members_individuals_report, name='all-members-report'),
    path('report/brgy/members/', views.members_per_brgy_report, name='per-brgy-members'),
    path('report/cluster/', views.leader_members_report, name='cluster-report'),
    path('report/members/', views.all_members_report, name='members-report'),
    path('report/leaders/', views.all_leaders_report, name='leaders-report'),
    path('attendance/list/', views.attendance_list, name='attendance-list'),
    path('report/sitios/', views.sitios_report, name='sitio-report'),

    path('report/no-member-brgys/download-pdf', views.no_member_barangays_pdf, name='no-member-brgys-pdf'),
    path('report/member-count-brgy/download-pdf', views.member_count_per_brgy_pdf, name='member-count-brgy-pdf'),
    path('report/leaders/member/None/download-pdf', views.no_members_leader_pdf, name='no-member-leader-pdf'),
    path('report/brgy/members/download-pdf/', views.members_per_brgy_report_pdf, name="per-brgy-members-pdf"),
    path('report/members/leader/None/download-pdf', views.leaderless_members_pdf, name='leaderless-members-pdf'),
    path('report/cluster/download-pdf', views.leader_members_report_pdf, name='cluster-report-pdf'),
    path('report/members/all/download-pdf/', views.all_members_individuals_report_pdf, name='all-members-report-pdf'),
    path('report/leaders/download-pdf', views.all_leaders_report_pdf, name='leaders-report-pdf'),
    path('report/members/download-pdf', views.all_members_report_pdf, name='members-report-pdf'),
    path('attendance/list/download-pdf/', views.attendance_list_pdf, name='attendance-list-pdf'),
    path('report/sitios/download-pdf', views.sitios_report_pdf, name='sitio-report-pdf'),

    path('report/cluster-filtered/download-pdf', views.leader_members_report_filtered_pdf,
         name='cluster-filtered-report-pdf'),
    path('report/brgy-filtered/members/download-pdf/', views.members_filtered_per_brgy_report_pdf,
       name="per-filtered-brgy-members-pdf"),
    path('attendance/list-daily/download-pdf/', views.attendance_list_filtered_daily_pdf,
       name='attendance-list-daily-pdf'),
    path('report/sitios/download-filtered-pdf', views.sitios_report_filtered_pdf, name='sitio-report-filtered-pdf'),


    path('function/<str:member_name>/<str:leader_name>/', views.tag_leader_member, name='tag-leader'),
    path('change-brgy-name/', views.change_brgy_name, name='change-brgy-name'),
    path('attendance/qr-code-scan/', views.qr_code_scanner, name='qr-code-attendance'),
    path('promote/<str:username>/', views.promote_to_leader, name='promote-member-to-leader'),
    path('add-sitio/', views.add_sitio, name='add-sitio'),
    path('get_filtered_sitios/', views.get_filtered_sitios, name='get_filtered_sitios'),
    path('get_filtered_sitios_using_brgy_id/', views.get_filtered_sitios_using_brgy_id,
         name='get-filtered-sitios-using-brgy-id'),
    path('get_filtered_leaders/', views.get_filtered_leaders, name='get_filtered_leaders'),
    path('', views.authentication, name='login'),
    path('logout/', views.logout_user, name='logout'),
    path('create-individuals/', views.create_individuals, name='create-individuals'),
    path('registration/', views.registration_validation, name='registration'),
    path('registrants/', views.registrants, name='registrants'),
    path('create-json/', views.create_json, name='create-json'),
    path('load-json/', views.load_json, name='load-json'),
    path('registration/confirm/member/<str:username>/', views.confirm_registration_member, name='confirm-member'),
    path('registration/confirm/leader/<str:username>/', views.confirm_registration_leader, name='confirm-leader'),
    path('registration/confirm/admin/<str:username>/', views.confirm_registrant_as_admin_and_leader,
         name='confirm-admin'),
    path('deny-registration/<str:username>/', views.deny_registration, name='deny-registration'),
    path('deny-registration/illegible-image/<str:username>/', views.deny_registration_invalid_image,
         name='deny-registration-illegible-image'),
    path('deny-registration/invalid-email/<str:username>/', views.deny_registration_invalid_email,
         name='deny-registration-invalid-email'),
    path('associate/<str:leader_username>/<str:member_username>/', views.associate_member_to_leader,
         name='associate-member'),
    path('remove/<str:leader_username>/<str:member_username>/', views.remove_member_from_leader,
         name='unassociated-member'),
    path('notifications/', views.notifications_async, name='notifications'),
    path('seen-notifications/', views.seen_notifications, name='seen-notifications'),
    path('delete-notification/<str:title>/<int:id>/', views.remove_notification, name='delete-notification'),
    path('profile/leader/<str:username>/', views.non_admin_leader_profile, name='profile-leader'),
    path('profile/member/<str:username>/', views.non_admin_member_profile, name='profile-member'),
    path('forgot-password/', views.forgot_password, name='forgot-password'),
    path('enter-token/<str:email>/', views.enter_token, name='enter-token'),
    path('change-password/<str:email>/<str:token_str>/', views.change_password, name='change-password'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# if settings.DEBUG:
#     urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
