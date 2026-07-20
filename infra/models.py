from django.db import models
from django.utils.timezone import now

# Create your models here.
# coredata/models.py

class Tickers(models.Model):
	ticker = models.CharField(max_length=20)
	name = models.CharField(max_length=100, null=True)
	price = models.FloatField(null=True)
	face_value = models.FloatField(null=True)
	book_value = models.FloatField(null=True)
	pe = models.FloatField(null=True)
	roe = models.FloatField(null=True)
	eps = models.FloatField(null=True)
	ind_pe = models.FloatField(null=True)
	roce = models.FloatField(null=True)
	notes = models.CharField(max_length=1000, null=True)
	status = models.CharField(max_length=20, default="Active")
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateField(default=now, null=True)

	def __str__(self):
		return f"Ticker Value on {self.ticker}: {self.face_value}"

