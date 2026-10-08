import sys, unittest, copy
sys.path.insert(0, '/work')
from solution import invoice_total
class Tests(unittest.TestCase):
 def line(self,q,p,v): return dict(quantity=q,unit_price=p,vat_percent=v)
 def test_basic(self): self.assertEqual(invoice_total([self.line('2','10','20')]), {'net':'20.00','tax':'4.00','total':'24.00'})
 def test_line_rounding(self): self.assertEqual(invoice_total([self.line('1','.025','20')]*2), {'net':'0.06','tax':'0.02','total':'0.08'})
 def test_discount(self): self.assertEqual(invoice_total([self.line('3','19.99','20')], '12.5'), {'net':'52.47','tax':'10.49','total':'62.96'})
 def test_empty(self): self.assertEqual(invoice_total([]), {'net':'0.00','tax':'0.00','total':'0.00'})
 def test_no_mutation(self):
  lines=[self.line('1','1','0')]; before=copy.deepcopy(lines); invoice_total(lines); self.assertEqual(lines,before)
 def test_full_discount(self): self.assertEqual(invoice_total([self.line('1','9.99','20')],'100')['total'], '0.00')
 def test_negative(self):
  for key in ('quantity','unit_price','vat_percent'):
   x=self.line('1','1','1'); x[key]='-1'
   with self.assertRaises(ValueError): invoice_total([x])
 def test_nonfinite(self):
  for bad in ('NaN','Infinity','-Infinity'):
   with self.assertRaises(ValueError): invoice_total([self.line('1',bad,'20')])
 def test_discount_bounds(self):
  for bad in ('-0.1','100.01','NaN','Infinity','oops'):
   with self.assertRaises(ValueError): invoice_total([],bad)
 def test_missing(self):
  with self.assertRaises(ValueError): invoice_total([{'quantity':'1'}])
if __name__=='__main__': unittest.main()
