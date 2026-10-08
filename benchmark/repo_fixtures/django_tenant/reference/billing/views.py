from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ModelViewSet
from .models import Invoice
from .serializers import InvoiceSerializer

class InvoiceViewSet(ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = InvoiceSerializer
    queryset = Invoice.objects.all().order_by("id")

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if getattr(request.user, "company_id", None) is None:
            raise PermissionDenied("Company required")

    def get_queryset(self):
        return super().get_queryset().filter(company_id=self.request.user.company_id)

    def perform_create(self, serializer):
        serializer.save(company_id=self.request.user.company_id)
