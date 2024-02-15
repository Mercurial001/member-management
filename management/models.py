from django.db import models
from django.contrib.auth.models import Group, User
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class PasswordResetToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    token = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField(default=timezone.now() + timezone.timedelta(minutes=10))

    class Meta:
        verbose_name = _('password reset token')
        verbose_name_plural = _('password reset tokens')

    def __str__(self):
        return f'{self.user.username} - {self.token}'


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


class Leader(models.Model):
    user = models.ForeignKey(User, related_name='leader_user', on_delete=models.CASCADE) # Added for version 2, 2/9/2024
    name = models.CharField(max_length=255)
    gender = models.ForeignKey(Gender, related_name='leader_gender', on_delete=models.CASCADE)
    age = models.IntegerField()
    brgy = models.ForeignKey(Barangay, related_name='leader_brgy', on_delete=models.CASCADE)
    sitio = models.ForeignKey(Sitio, related_name='leader_sitio', on_delete=models.CASCADE, null=True, blank=True)
    date_registered = models.DateTimeField(auto_now_add=True)
    image = models.ImageField(null=True, blank=True, upload_to="images/")

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
    user = models.ForeignKey(User, related_name='user_individual', on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    gender = models.ForeignKey(Gender, related_name='individual_gender', on_delete=models.PROTECT)
    age = models.IntegerField()
    brgy = models.ForeignKey(Barangay, related_name='individual_brgy', on_delete=models.PROTECT)
    sitio = models.ForeignKey(Sitio, related_name='individual_sitio', on_delete=models.PROTECT, null=True, blank=True)
    date_registered = models.DateTimeField(auto_now_add=True)
    group = models.CharField(max_length=255)
    image = models.ImageField(null=True, blank=True, upload_to="images/")

    def __str__(self):
        return self.name


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

