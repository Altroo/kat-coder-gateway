from django.db import models

class Company(models.Model):
    name = models.CharField(max_length=80)

class Invoice(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    title = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
