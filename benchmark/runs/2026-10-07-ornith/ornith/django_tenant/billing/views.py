from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ModelViewSet
from .models import Invoice
from .serializers import InvoiceSerializer


class InvoiceViewSet(ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = InvoiceSerializer

    def get_permissions(self):
        if self.action == "create":
            return [IsAuthenticated()]
        return [IsAuthenticated()]

    def check_tenant(self):
        company_id = self.request.user.company_id
        if company_id is None:
            raise PermissionDenied("No company assigned.")
        return company_id

    def get_queryset(self):
        company_id = self.check_tenant()
        return Invoice.objects.filter(company_id=company_id)

    def perform_create(self, serializer):
        company_id = self.check_tenant()
        serializer.save(company_id=company_id)
