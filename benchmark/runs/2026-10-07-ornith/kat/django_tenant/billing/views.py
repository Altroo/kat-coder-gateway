from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ModelViewSet
from .models import Invoice
from .serializers import InvoiceSerializer


class InvoiceViewSet(ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = InvoiceSerializer
    queryset = Invoice.objects.all().order_by("id")

    def get_queryset(self):
        user = self.request.user
        if not user.company_id:
            raise PermissionDenied("User has no company.")
        return Invoice.objects.filter(company_id=user.company_id).order_by("id")

    def perform_create(self, serializer):
        serializer.save(company_id=self.request.user.company_id)
