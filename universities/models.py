from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

# Create your models here.

class University(models.Model):
    name = models.CharField(max_length=200)
    country = models.CharField(max_length=100)
    city = models.CharField(max_length=100, blank=True)
    course_offered = models.CharField(max_length=200, blank=True, default='')
    application_fee = models.DecimalField(max_digits=6, decimal_places=2)
    tuition_fee = models.DecimalField(max_digits=8, decimal_places=2)
    deadline_undergrad = models.DateField(null=True, blank=True)
    deadline_grad = models.DateField(null=True, blank=True)
    bachelor_programs = models.JSONField(default=list)
    masters_programs = models.JSONField(default=list)
    scholarships = models.JSONField(default=list)
    university_link = models.URLField()
    application_link = models.URLField()
    description = models.TextField(default="")

    def __str__(self):
        return self.name

class UserDashboard(models.Model):
    SUBSCRIPTION_CHOICES = [
        ('none', 'None'),
        ('active', 'Active'),
        ('expired', 'Expired'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='dashboard')
    favorites = models.ManyToManyField(University, related_name='favorited_by', blank=True)
    planning_to_apply = models.ManyToManyField(University, related_name='planned_by', blank=True)
    applied = models.ManyToManyField(University, related_name='applied_by', blank=True)
    accepted = models.ManyToManyField(University, related_name='accepted_by', blank=True)
    visa_approved = models.ManyToManyField(University, related_name='visa_approved_for', blank=True)
    subscription_status = models.CharField(
        max_length=10, choices=SUBSCRIPTION_CHOICES, default='none'
    )
    subscription_end_date = models.DateField(null=True, blank=True)
    phone_number = models.CharField(max_length=20, blank=True, default='')

    def __str__(self):
        return f"{self.user.username}'s Dashboard"

@receiver(post_save, sender=User)
def create_user_dashboard(sender, instance, created, **kwargs):
    """
    Automatically create a UserDashboard when a new User is created.
    """
    if created:
        UserDashboard.objects.create(user=instance)
