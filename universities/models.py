from django.db import models

# Create your models here.

class University(models.Model):
    name = models.CharField(max_length=200)
    country = models.CharField(max_length=100)
    city = models.CharField(max_length=100, blank=True)
    website = models.URLField()
    application_link = models.URLField()
    application_fee = models.DecimalField(max_digits=6, decimal_places=2)
    tuition_fee = models.DecimalField(max_digits=8, decimal_places=2)
    deadline_undergrad = models.DateField(null=True, blank=True)
    deadline_grad = models.DateField(null=True, blank=True)
    scholarship_info = models.TextField(blank=True)
    course_offered = models.CharField(max_length=200)  # e.g., Computer Science
    degree_level = models.CharField(
        max_length=20,
        choices=[
            ('bachelor', 'Bachelor'),
            ('master', 'Master'),
            ('both', 'Both'),
        ],
        default='both'
    )  

    def __str__(self):
        return self.name

