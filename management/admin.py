from django.contrib import admin
from .models import Gender
from .models import Barangay
from .models import Leader
from .models import Member
from .models import Cluster
from .models import AddedMembers
from .models import AddedLeaders
from .models import Sitio
from .models import Individual
from .models import Registrants
from .models import Notification
from .models import EmailMessage
from .models import PasswordResetToken
from .models import TotalVoterPopulation
from .models import QRCodeAttendance
from .models import ActivityLog
from .models import LeaderConnectMemberRequest
from .models import LeadersRequestConnect
from .models import AmbiguousVoters
from .models import IndividualParents
from .models import IndividualSiblings
from .models import IndividualSpouse
from .models import IndividualOffspring
from .models import IndividualLeaderCluster
from .models import BarangayFigures
from .models import ElectionType
from .models import BarangayElectionResults
from .models import BarangayElectionContender
from .models import ElectionContender
from .models import Religion
from .models import Occupation
from .models import Church
from .models import BarangayRemark
from .models import SitioRemark


class BarangayRemarkAdmin(admin.ModelAdmin):
    list_display = ('brgy',)


class SitioRemarkAdmin(admin.ModelAdmin):
    list_display = ('sitio',)


class ReligionAdmin(admin.ModelAdmin):
    list_display = ('name',)


class OccupationAdmin(admin.ModelAdmin):
    list_display = ('name',)


class ChurchAdmin(admin.ModelAdmin):
    list_display = ('brgy',)


class BarangayFiguresAdmin(admin.ModelAdmin):
    list_display = ('brgy',)


class ElectionTypeAdmin(admin.ModelAdmin):
    list_display = ('name',)


class BarangayElectionResultsAdmin(admin.ModelAdmin):
    list_display = ('brgy',)


class BarangayElectionContendersAdmin(admin.ModelAdmin):
    list_display = ('name',)


class ElectionContendersAdmin(admin.ModelAdmin):
    list_display = ('name',)


class IndividualParentsAdmin(admin.ModelAdmin):
    list_display = ('individual',)


class IndividualSiblingsAdmin(admin.ModelAdmin):
    list_display = ('individual',)


class IndividualSpouseAdmin(admin.ModelAdmin):
    list_display = ('individual',)


class IndividualOffspringAdmin(admin.ModelAdmin):
    list_display = ('individual',)


class IndividualLeaderClusterAdmin(admin.ModelAdmin):
    list_display = ('individual',)


class AmbiguousVotersAdmin(admin.ModelAdmin):
    list_display = ('name', )


class LeadersRequestConnectAdmin(admin.ModelAdmin):
    list_display = ('leader', )


class LeaderConnectMemberRequestAdmin(admin.ModelAdmin):
    list_display = ('member', )


class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ('title', 'date_time')


class QRCodeAttendanceAdmin(admin.ModelAdmin):
    list_display = ('user', 'name')


class TotalVoterPopulationAdmin(admin.ModelAdmin):
    list_display = ('date', 'population')


class PasswordResetTokenAdmin(admin.ModelAdmin):
    list_display = ('user', 'token')


class EmailMessageAdmin(admin.ModelAdmin):
    list_display = ('type', 'subject')


class NotificationAdmin(admin.ModelAdmin):
    list_display = ('title',)


class RegistrantsAdmin(admin.ModelAdmin):
    list_display = ('username', 'name', 'brgy', 'sitio')


class IndividualAdmin(admin.ModelAdmin):
    list_display = ('name', 'brgy', 'sitio')


class SitioAdmin(admin.ModelAdmin):
    list_display = ('name', 'brgy')


class AddedLeadersAdmin(admin.ModelAdmin):
    list_display = ('leader', 'date_time_registered', 'date_registered')


class AddedMembersAdmin(admin.ModelAdmin):
    list_display = ('member', 'date_time_registered', 'date_registered')


class GenderAdmin(admin.ModelAdmin):
    list_display = ('gender',)


class BarangayAdmin(admin.ModelAdmin):
    list_display = ('brgy_name',)


class LeaderAdmin(admin.ModelAdmin):
    list_display = ('name',)


class MemberAdmin(admin.ModelAdmin):
    list_display = ('name',)


class CLusterAdmin(admin.ModelAdmin):
    list_display = ('leader',)


admin.site.register(BarangayRemark, BarangayRemarkAdmin)
admin.site.register(SitioRemark, SitioRemarkAdmin)
admin.site.register(Religion, ReligionAdmin)
admin.site.register(Occupation, OccupationAdmin)
admin.site.register(Church, ChurchAdmin)
admin.site.register(BarangayFigures, BarangayFiguresAdmin)
admin.site.register(ElectionType, ElectionTypeAdmin)
admin.site.register(BarangayElectionResults, BarangayElectionResultsAdmin)
admin.site.register(BarangayElectionContender, BarangayElectionContendersAdmin)
admin.site.register(ElectionContender, ElectionContendersAdmin)
admin.site.register(IndividualParents, IndividualParentsAdmin)
admin.site.register(IndividualSiblings, IndividualSiblingsAdmin)
admin.site.register(IndividualSpouse, IndividualSpouseAdmin)
admin.site.register(IndividualOffspring, IndividualOffspringAdmin)
admin.site.register(IndividualLeaderCluster, IndividualLeaderClusterAdmin)
admin.site.register(AmbiguousVoters, AmbiguousVotersAdmin)
admin.site.register(LeadersRequestConnect, LeadersRequestConnectAdmin)
admin.site.register(LeaderConnectMemberRequest, LeaderConnectMemberRequestAdmin)
admin.site.register(ActivityLog, ActivityLogAdmin)
admin.site.register(QRCodeAttendance, QRCodeAttendanceAdmin)
admin.site.register(TotalVoterPopulation, TotalVoterPopulationAdmin)
admin.site.register(PasswordResetToken, PasswordResetTokenAdmin)
admin.site.register(EmailMessage, EmailMessageAdmin)
admin.site.register(Notification, NotificationAdmin)
admin.site.register(Registrants, RegistrantsAdmin)
admin.site.register(Individual, IndividualAdmin)
admin.site.register(Sitio, SitioAdmin)
admin.site.register(AddedLeaders, AddedLeadersAdmin)
admin.site.register(AddedMembers, AddedMembersAdmin)
admin.site.register(Gender, GenderAdmin)
admin.site.register(Barangay, BarangayAdmin)
admin.site.register(Leader, LeaderAdmin)
admin.site.register(Member, MemberAdmin)
admin.site.register(Cluster, CLusterAdmin)
