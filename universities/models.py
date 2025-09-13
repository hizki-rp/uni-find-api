from django.db import models

# Create your models here.

class University(models.Model):
    name = models.CharField(max_length=200)
    country = models.CharField(max_length=100)
    city = models.CharField(max_length=100, blank=True)
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
