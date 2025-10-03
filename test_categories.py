import os
os.chdir(r'c:\Users\ryanc\brain-bee-ollama')
import app
c = app.app.test_client()
resp = c.get('/api/categories')
print('status', resp.status_code)
print(resp.get_json())
