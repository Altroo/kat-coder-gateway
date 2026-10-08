from rest_framework import serializers
from .models import Invoice


class InvoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Invoice
        fields = ["id", "company", "title", "amount"]
        read_only_fields = ["id"]

    def create(self, validated_data):
        validated_data.pop("company", None)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        validated_data.pop("company", None)
        return super().update(instance, validated_data)
