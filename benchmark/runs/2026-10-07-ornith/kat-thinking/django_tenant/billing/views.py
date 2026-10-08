from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ModelViewSet
from rest_framework.exceptions import PermissionDenied
from .models import Invoice
from .serializers import InvoiceSerializer

class InvoiceViewSet(ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = InvoiceSerializer
    queryset = Invoice.objects.all().order_by("id")

    def get_queryset(self):
        if not self.request.user.company_id:
            raise PermissionDenied()
        return Invoice.objects.filter(company_id=self.request.user.company_id).order_by("id")

    def perform_create(self, serializer):
        if not self.request.user.company_id:
            raise PermissionDenied()
        serializer.save(company_id=self.request.user.company_id)
