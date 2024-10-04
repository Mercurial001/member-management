from django.db import models
from django.contrib.auth.models import Group, User
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class PasswordResetToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    token = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField(null=True, blank=True) # changed on 3/12/2024

    class Meta:
        verbose_name = _('password reset token')
        verbose_name_plural = _('password reset tokens')

    def __str__(self):
        return f'{self.user.username} - {self.token}'


class Religion(models.Model):
    name = models.CharField(max_length=200)


class Occupation(models.Model):
    name = models.CharField(max_length=255)


class Gender(models.Model):
    gender = models.CharField(max_length=255)

    def __str__(self):
        return self.gender


class Barangay(models.Model):
    brgy_name = models.CharField(max_length=255)
    brgy_voter_population = models.IntegerField(blank=True, null=True)
    lat = models.FloatField(blank=True, null=True)
    long = models.FloatField(blank=True, null=True)

    def __str__(self):
        return self.brgy_name

    class Meta:
        ordering = ['brgy_name']


class Sitio(models.Model):
    name = models.CharField(max_length=255)
    population = models.IntegerField(default=0, blank=True, null=True)
    brgy = models.ForeignKey(Barangay, related_name='brgy_sitio', on_delete=models.CASCADE)
    lat = models.FloatField(blank=True, null=True)
    long = models.FloatField(blank=True, null=True)

    def __str__(self):
        return self.name


class BarangayRemark(models.Model):
    brgy = models.ForeignKey(Barangay, on_delete=models.SET_NULL, null=True, blank=True)
    remark = models.CharField(max_length=500)


class SitioRemark(models.Model):
    sitio = models.ForeignKey(Sitio, on_delete=models.SET_NULL, null=True, blank=True)
    remark = models.CharField(max_length=500)


class Church(models.Model):
    brgy = models.ForeignKey(Barangay, on_delete=models.PROTECT)
    sitio = models.ForeignKey(Sitio, on_delete=models.SET_NULL, null=True, blank=True)
    lat = models.FloatField(blank=True, null=True)
    long = models.FloatField(blank=True, null=True)


class Leader(models.Model):
    user = models.ForeignKey(User, related_name='leader_user', on_delete=models.CASCADE) # Added for version 2, 2/9/2024
    name = models.CharField(max_length=255)
    gender = models.ForeignKey(Gender, related_name='leader_gender', on_delete=models.CASCADE)
    age = models.IntegerField()
    brgy = models.ForeignKey(Barangay, related_name='leader_brgy', on_delete=models.CASCADE)
    sitio = models.ForeignKey(Sitio, related_name='leader_sitio', on_delete=models.CASCADE, null=True, blank=True)
    date_registered = models.DateTimeField(auto_now_add=True)
    image = models.ImageField(null=True, blank=True, upload_to="images/")
    encryption = models.CharField(max_length=2000) # Added 3/12/2024

    def __str__(self):
        return self.name


class Member(models.Model):
    user = models.ForeignKey(User, related_name='member_user', on_delete=models.CASCADE) # Added for version 2, 2/9/2024
    name = models.CharField(max_length=255)
    gender = models.ForeignKey(Gender, related_name='member_gender', on_delete=models.CASCADE)
    age = models.IntegerField()
    brgy = models.ForeignKey(Barangay, related_name='member_brgy', on_delete=models.CASCADE)
    sitio = models.ForeignKey(Sitio, related_name='member_sitio', on_delete=models.CASCADE, null=True, blank=True)
    date_registered = models.DateTimeField(auto_now_add=True)
    image = models.ImageField(null=True, blank=True, upload_to="images/")
    encryption = models.CharField(max_length=2000) # Added 3/12/2024

    def __str__(self):
        return self.name


class Cluster(models.Model):
    leader = models.ForeignKey(Leader, related_name='cluster_leader', on_delete=models.CASCADE)
    members = models.ManyToManyField(Member, related_name='cluster_member')

    def __str__(self):
        return self.leader.name


class AddedLeaders(models.Model):
    leader = models.CharField(max_length=255)
    date_time_registered = models.DateTimeField(auto_now_add=True)
    date_registered = models.DateField(auto_now_add=True)


class AddedMembers(models.Model):
    member = models.CharField(max_length=255)
    date_time_registered = models.DateTimeField(auto_now_add=True)
    date_registered = models.DateField(auto_now_add=True)


class Individual(models.Model):
    # Added null=True attribute to user field on 9/16/2024 MM/DD/YYYY
    # All fields nullified due sibling, and children fields
    user = models.ForeignKey(
        User,
        related_name='user_individual',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    # member field added on 3/13/2024 to link member since members are now tied to user objects through forms.
    # member = models.ForeignKey(Member, related_name='member_instance',
    #                            on_delete=models.CASCADE,
    #                            blank=True,
    #                            null=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    middle_name = models.CharField(max_length=50, null=True, blank=True)
    last_name = models.CharField(max_length=50, null=True, blank=True)
    suffix = models.CharField(max_length=10, null=True, blank=True)
    gender = models.ForeignKey(
        Gender,
        related_name='individual_gender',
        on_delete=models.PROTECT,
        null=True,
        blank=True
    )
    age = models.IntegerField(null=True, blank=True)
    brgy = models.ForeignKey(
        Barangay,
        related_name='individual_brgy',
        on_delete=models.PROTECT,
        null=True,
        blank=True
    )
    sitio = models.ForeignKey(
        Sitio,
        related_name='individual_sitio',
        on_delete=models.PROTECT,
        null=True,
        blank=True
    )
    date_registered = models.DateTimeField(auto_now_add=True)
    group = models.CharField(max_length=255, null=True, blank=True)
    image = models.ImageField(null=True, blank=True, upload_to="images/")
    house_image = models.ImageField(null=True, blank=True, upload_to="houses/")
    # New Fields Added 09/15/2024
    religion = models.ForeignKey(Religion, on_delete=models.PROTECT, null=True, blank=True)
    occupation = models.ForeignKey(Occupation, on_delete=models.SET_NULL, null=True, blank=True)
    mobile = models.CharField(max_length=20, null=True, blank=True)
    lat = models.FloatField(null=True, blank=True)
    long = models.FloatField(null=True, blank=True)
    birthday = models.DateField(null=True, blank=True)
    is_leader = models.BooleanField(default=False)
    is_oot = models.BooleanField(default=False)
    is_swing_voter = models.BooleanField(default=False)
    is_cockroach = models.BooleanField(default=False)
    is_deceased = models.BooleanField(default=False)
    is_parent = models.BooleanField(default=False)
    is_father = models.BooleanField(default=False)
    # Add precent number for election purposes

    def __str__(self):
        if self.name != None:
            return self.name
        else:
            return str(self.id)

    def middle_initial(self):
        return self.middle_name[0]


class IndividualSpouse(models.Model):
    individual = models.ForeignKey(
        Individual,
        on_delete=models.PROTECT,
        related_name="individuals_spouse"
    )
    spouse = models.ForeignKey(Individual, on_delete=models.SET_NULL, blank=True, null=True)


class IndividualSiblings(models.Model):
    individual = models.ForeignKey(
        Individual,
        on_delete=models.PROTECT,
        related_name="individuals_sibling"
    )
    siblings = models.ManyToManyField(Individual, blank=True)


class IndividualOffspring(models.Model):
    individual = models.ForeignKey(
        Individual,
        on_delete=models.PROTECT,
        related_name="individuals_offspring"
    )
    children = models.ManyToManyField(Individual, blank=True)


class IndividualParents(models.Model):
    individual = models.ForeignKey(
        Individual,
        on_delete=models.PROTECT,
        related_name="individuals_parent"
    )
    parents = models.ManyToManyField(Individual, blank=True)


class IndividualLeaderCluster(models.Model):
    individual = models.ForeignKey(
        Individual,
        on_delete=models.PROTECT,
        related_name='individual_leader'
    )
    members = models.ManyToManyField(
        Individual,
        related_name='individual_leader_members'
    )


class BrgyOfficial(models.Model):
    brgy = models.ForeignKey(Barangay, related_name='brgy_official', on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    rank = models.CharField(max_length=255)

    def middle_initial(self):
        return self.middle_name[0]


class BrgySchoolHead(models.Model):
    brgy = models.ForeignKey(Barangay, related_name='brgy_school_head', on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    rank = models.CharField(max_length=255)

    # def middle_initial(self):
    #     return self.middle_name[0]


class BarangayFigures(models.Model):
    brgy = models.ForeignKey(Barangay, on_delete=models.PROTECT)
    # captain = models.CharField()
    officials = models.ManyToManyField(
        BrgyOfficial,
        related_name='officials_barangay',
        blank=True
    )
    school_heads = models.ManyToManyField(BrgySchoolHead, blank=True)


class ElectionType(models.Model):
    name = models.CharField(max_length=100, null=True, blank=True)

    def __str__(self):
        return self.name


class BarangayElectionContender(models.Model):
    name = models.CharField(max_length=255)
    rank = models.CharField(max_length=255)
    vote_count = models.IntegerField(default=0)
    party = models.CharField(max_length=255)


# For Barangay Level
class BarangayElectionResults(models.Model):
    brgy = models.ForeignKey(
        Barangay,
        on_delete=models.PROTECT
    )
    election_year = models.DateField(null=True, blank=True)
    election_type = models.ForeignKey(ElectionType, on_delete=models.PROTECT, null=True, blank=True)
    contenders = models.ManyToManyField(BarangayElectionContender, blank=True)


class ElectionContender(models.Model):
    name = models.CharField(max_length=255)
    rank = models.CharField(max_length=255)
    vote_count = models.IntegerField(default=0)
    party = models.CharField(max_length=255)


# For Palompon Town
class ElectionResults(models.Model):
    election_type = models.ForeignKey(
        ElectionType,
        on_delete=models.PROTECT,
        related_name='election_type_result',
    )
    election_year = models.DateField()
    contenders = models.ManyToManyField(
        ElectionContender,
        blank=True
    )


# Added 2/9/2024 for Version 2
class Registrants(models.Model):
    username = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    password = models.CharField(max_length=255)
    email = models.EmailField()
    date = models.DateField()
    date_time = models.DateTimeField()
    brgy = models.ForeignKey(Barangay, on_delete=models.CASCADE)
    sitio = models.ForeignKey(Sitio, on_delete=models.CASCADE, null=True, blank=True)
    age = models.IntegerField()
    gender = models.ForeignKey(Gender, on_delete=models.CASCADE)
    image = models.ImageField(upload_to="images/")


class Notification(models.Model):
    # user field added on 3/4/2024 to fix bug
    user = models.ForeignKey(User, related_name='user_notification', on_delete=models.CASCADE, null=True, blank=True)
    title = models.CharField(max_length=255)
    message = models.CharField(max_length=400)
    is_seen = models.BooleanField(default=False, null=True, blank=True)
    removed = models.BooleanField(default=False, null=True, blank=True)
    date = models.DateField()
    date_time = models.DateTimeField()
    identifier = models.CharField(max_length=500)

    class Meta:
        ordering = ['-date_time']


class EmailMessage(models.Model):
    type = models.CharField(max_length=255)
    subject = models.CharField(max_length=255)
    content = models.TextField()


class TotalVoterPopulation(models.Model):
    date = models.DateField()
    population = models.IntegerField()


class QRCodeAttendance(models.Model):
    user = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    brgy = models.CharField(max_length=255)
    sitio = models.CharField(max_length=255)
    group = models.CharField(max_length=255)
    date = models.DateField()
    date_time = models.DateTimeField()


class ActivityLog(models.Model):
    date = models.DateField()
    date_time = models.DateTimeField()
    title = models.CharField(max_length=255)
    content = models.TextField()


class LeaderConnectMemberRequest(models.Model):
    member = models.ForeignKey(Member, related_name='member_connect_request', on_delete=models.CASCADE)
    requests = models.ManyToManyField(Leader, related_name='leader_connecting_request')

    def __str__(self):
        return self.member.name


# Added 3/5/2024 1:46 AM
class LeadersRequestConnect(models.Model):
    leader = models.ForeignKey(Leader, related_name='leader_connect_request', on_delete=models.CASCADE)
    requests = models.ManyToManyField(Member, related_name='leader_connecting_member')

    def __str__(self):
        return self.leader.name


# Added 3/13/2024
class AmbiguousVoters(models.Model):
    name = models.CharField(max_length=255)
    voters = models.ManyToManyField(Individual, related_name='ambiguous_voters')
