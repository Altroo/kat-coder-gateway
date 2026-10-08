import sys,unittest,copy
sys.path.insert(0,'/work')
from solution import order_tasks
class Tests(unittest.TestCase):
 def test_empty(self): self.assertEqual(order_tasks([]),[])
 def test_basic(self): self.assertEqual(order_tasks([{'id':'b','depends_on':['a']},{'id':'a'}]),['a','b'])
 def test_reprioritize(self): self.assertEqual(order_tasks([{'id':'a','depends_on':['b']},{'id':'b'},{'id':'c'}]),['b','a','c'])
 def test_duplicate_edge(self): self.assertEqual(order_tasks([{'id':'b','depends_on':['a','a']},{'id':'a'}]),['a','b'])
 def test_duplicate_id(self):
  with self.assertRaises(ValueError): order_tasks([{'id':'a'},{'id':'a'}])
 def test_unknown(self):
  with self.assertRaises(ValueError): order_tasks([{'id':'a','depends_on':['missing']}])
 def test_self(self):
  with self.assertRaises(ValueError): order_tasks([{'id':'a','depends_on':['a']}])
 def test_cycle(self):
  with self.assertRaises(ValueError): order_tasks([{'id':'a','depends_on':['b']},{'id':'b','depends_on':['a']},{'id':'c'}])
 def test_chain(self):
  tasks=[{'id':str(i),'depends_on':[str(i-1)] if i else []} for i in range(2000)]; self.assertEqual(order_tasks(tasks),[str(i) for i in range(2000)])
 def test_no_mutation(self):
  x=[{'id':'b','depends_on':['a','a']},{'id':'a'}]; before=copy.deepcopy(x); order_tasks(x); self.assertEqual(x,before)
if __name__=='__main__': unittest.main()
