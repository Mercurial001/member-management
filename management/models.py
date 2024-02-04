from django.db import models


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
    name = models.CharField(max_length=255)
    gender = models.ForeignKey(Gender, related_name='leader_gender', on_delete=models.CASCADE)
    age = models.IntegerField()
    brgy = models.ForeignKey(Barangay, related_name='leader_brgy', on_delete=models.CASCADE)
    sitio = models.ForeignKey(Sitio, related_name='leader_sitio', on_delete=models.CASCADE, null=True, blank=True)
    date_registered = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Member(models.Model):
    name = models.CharField(max_length=255)
    gender = models.ForeignKey(Gender, related_name='member_gender', on_delete=models.CASCADE)
    age = models.IntegerField()
    brgy = models.ForeignKey(Barangay, related_name='member_brgy', on_delete=models.CASCADE)
    sitio = models.ForeignKey(Sitio, related_name='member_sitio', on_delete=models.CASCADE, null=True, blank=True)
    date_registered = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Cluster(models.Model):
    leader = models.ForeignKey(Leader, related_name='cluster_leader', on_delete=models.CASCADE)
    members = models.ManyToManyField(Member, related_name='cluster_member')


class AddedLeaders(models.Model):
    leader = models.CharField(max_length=255)
    date_time_registered = models.DateTimeField(auto_now_add=True)
    date_registered = models.DateField(auto_now_add=True)


class AddedMembers(models.Model):
    member = models.CharField(max_length=255)
    date_time_registered = models.DateTimeField(auto_now_add=True)
    date_registered = models.DateField(auto_now_add=True)


class Individual(models.Model):
    name = models.CharField(max_length=255)
    gender = models.ForeignKey(Gender, related_name='individual_gender', on_delete=models.CASCADE)
    age = models.IntegerField()
    brgy = models.ForeignKey(Barangay, related_name='individual_brgy', on_delete=models.CASCADE)
    sitio = models.ForeignKey(Sitio, related_name='individual_sitio', on_delete=models.CASCADE, null=True, blank=True)
    date_registered = models.DateTimeField(auto_now_add=True)
    # date_registered_no_time = models.DateField()

    def __str__(self):
        return self.name
