import os,sys,unittest
from types import SimpleNamespace
sys.path.insert(0,"/work")
os.environ["DJANGO_SETTINGS_MODULE"]="settings"
import django
django.setup()
from django.db import connection
from rest_framework.test import APIRequestFactory,force_authenticate
from billing.models import Company,Invoice
from billing.views import InvoiceViewSet
with connection.schema_editor() as e:
    e.create_model(Company);e.create_model(Invoice)
class TenantTests(unittest.TestCase):
    def setUp(self):
        Invoice.objects.all().delete();Company.objects.all().delete()
        self.a=Company.objects.create(name="A");self.b=Company.objects.create(name="B")
        self.own=Invoice.objects.create(company=self.a,title="own",amount="10.00")
        self.other=Invoice.objects.create(company=self.b,title="other",amount="20.00")
        self.user=SimpleNamespace(is_authenticated=True,company_id=self.a.id)
    def call(self,method,action,pk=None,data=None,user="default"):
        req=getattr(APIRequestFactory(),method)("/invoices/",data or {},format="json")
        selected=self.user if user=="default" else user
        if selected is not None:force_authenticate(req,user=selected)
        return InvoiceViewSet.as_view({method:action})(req,**({"pk":pk} if pk else {}))
    def test_list_is_scoped(self):
        r=self.call("get","list",data={"company":self.b.id});self.assertEqual(r.status_code,200);self.assertEqual([x["id"] for x in r.data],[self.own.id])
    def test_own_detail(self):
        r=self.call("get","retrieve",self.own.id);self.assertEqual(r.status_code,200);self.assertEqual(r.data["title"],"own")
    def test_other_detail_is_404(self):self.assertEqual(self.call("get","retrieve",self.other.id).status_code,404)
    def test_other_patch_is_404(self):
        r=self.call("patch","partial_update",self.other.id,{"title":"stolen"});self.assertEqual(r.status_code,404);self.other.refresh_from_db();self.assertEqual(self.other.title,"other")
    def test_other_delete_is_404(self):
        self.assertEqual(self.call("delete","destroy",self.other.id).status_code,404);self.assertTrue(Invoice.objects.filter(pk=self.other.id).exists())
    def test_create_without_company(self):
        r=self.call("post","create",data={"title":"new","amount":"12.50"});self.assertEqual(r.status_code,201);self.assertEqual(Invoice.objects.get(pk=r.data["id"]).company_id,self.a.id)
    def test_create_cannot_spoof_company(self):
        r=self.call("post","create",data={"title":"new","amount":"12.50","company":self.b.id});self.assertEqual(r.status_code,201);self.assertEqual(Invoice.objects.get(pk=r.data["id"]).company_id,self.a.id)
    def test_update_cannot_transfer_company(self):
        r=self.call("patch","partial_update",self.own.id,{"title":"changed","company":self.b.id});self.assertEqual(r.status_code,200);self.own.refresh_from_db();self.assertEqual(self.own.company_id,self.a.id);self.assertEqual(self.own.title,"changed")
    def test_missing_tenant_fails_closed(self):
        u=SimpleNamespace(is_authenticated=True,company_id=None)
        self.assertEqual(self.call("get","list",user=u).status_code,403)
        self.assertEqual(self.call("post","create",data={"title":"bad","amount":"1.00","company":self.a.id},user=u).status_code,403)
    def test_anonymous_is_denied(self):self.assertEqual(self.call("get","list",user=None).status_code,403)
if __name__=="__main__":unittest.main()
