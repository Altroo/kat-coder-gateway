from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ModelViewSet
from .models import Invoice, Company
from .serializers import InvoiceSerializer

class InvoiceViewSet(ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = InvoiceSerializer
    queryset = Invoice.objects.all().order_by("id")

    @property
    def company_id(self):
        cid = getattr(self.request.user, "company_id", None)
        if cid is None:
            raise PermissionDenied("User has no company.")
        return cid

    def get_queryset(self):
        return self.queryset.filter(company_id=self.company_id)

    def perform_create(self, serializer):
        company = Company.objects.get(pk=self.company_id)
        serializer.save(company=company)
