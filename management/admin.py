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


admin.site.register(Individual, IndividualAdmin)
admin.site.register(Sitio, SitioAdmin)
admin.site.register(AddedLeaders, AddedLeadersAdmin)
admin.site.register(AddedMembers, AddedMembersAdmin)
admin.site.register(Gender, GenderAdmin)
admin.site.register(Barangay, BarangayAdmin)
admin.site.register(Leader, LeaderAdmin)
admin.site.register(Member, MemberAdmin)
admin.site.register(Cluster, CLusterAdmin)
