from django.db import models
from django.utils.timezone import now

# Create your models here.
# coredata/models.py

class Config(models.Model):
	attribute =  models.CharField(max_length=100, null=True, db_index=True)
	value = models.CharField(max_length=240, null=True)
	fetched_at = models.DateField(default=now)

	def __str__(self):
		return f"attribute Value on {self.value}: {self.fetched_at}"

class AppSettings(models.Model):
    key = models.CharField(max_length=100, unique=True)
    value = models.TextField()

    def __str__(self):
        return f"{self.key} = {self.value}"
