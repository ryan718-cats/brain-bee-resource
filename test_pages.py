import os
os.chdir(r'c:\Users\ryanc\brain-bee-ollama')
import app
c = app.app.test_client()
for path in ['/','/question-generator','/flashcards','/review','/api/health']:
    r = c.get(path)
    print(path, r.status_code)
