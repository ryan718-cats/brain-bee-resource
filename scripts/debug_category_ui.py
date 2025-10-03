"""Debug helper for the question-generator category UI.

What it does:
- Reads templates/question_generator.html and reports presence of key elements (select#category, #category_chips, custom dropdown markers).
- Lists .txt files under data/ and prints counts and names.
- Attempts an HTTP GET to http://127.0.0.1:5000/api/categories and prints the result (useful if the Flask server is running).

Run:
  python .\scripts\debug_category_ui.py
"""
import os
import re
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / 'templates' / 'question_generator.html'
DATA_DIR = ROOT / 'data'

print('Workspace root:', ROOT)
print('Template:', TEMPLATE)
print('Data dir:', DATA_DIR)
print('')

# Read template
if not TEMPLATE.exists():
    print('ERROR: template file not found:', TEMPLATE)
    sys.exit(2)

text = TEMPLATE.read_text(encoding='utf-8')

# Look for <select id="category">
select_match = re.search(r"<select[^>]*id=[\'\"]category[\'\"][^>]*>", text, re.I)
chips_match = re.search(r"id=[\'\"]category_chips[\'\"]", text, re.I)
custom_select_marker = 'custom-select' in text or 'custom-select-btn' in text or 'custom-select-menu' in text
hardcoded_list = 'FALLBACK_CATEGORIES' in text or 'CATEGORIES' in text
loadcategories_fn = 'function loadCategories' in text or 'async function loadCategories' in text

print('Template checks:')
print(' - select#category present:', bool(select_match))
print(' - #category_chips present:', bool(chips_match))
print(' - custom-select code present:', custom_select_marker)
print(' - hardcoded category list present:', hardcoded_list)
print(' - loadCategories function present:', loadcategories_fn)
print('')

# Print the select tag snippet for inspection
if select_match:
    start = select_match.start()
    snippet = text[start:start+200]
    print('Select snippet (first 200 chars):')
    print(snippet)
    print('')

# Inspect CSS rules for select width/z-index
select_style = None
m = re.search(r"select\s*\{([^}]*)\}", text, re.I|re.S)
if m:
    select_style = m.group(1).strip()
    print('Select style block found:')
    print(select_style)
    print('')

# List data files
if DATA_DIR.exists() and DATA_DIR.is_dir():
    txts = sorted([p.name for p in DATA_DIR.glob('*.txt')])
    print('Found data files (count={}):'.format(len(txts)))
    for n in txts:
        print(' -', n)
    print('')
else:
    print('Data directory not found or is not a directory:', DATA_DIR)
    print('')

# Try calling the local server endpoint
try:
    import requests
    url = 'http://127.0.0.1:5000/api/categories'
    print('Attempting GET', url)
    try:
        r = requests.get(url, timeout=3)
        print('HTTP', r.status_code)
        try:
            print('Response JSON:', json.dumps(r.json(), indent=2) )
        except Exception:
            print('Response text:', r.text[:1000])
    except Exception as e:
        print('Request to local server failed:', repr(e))
        print('Is the Flask server running? Try: python app.py')
except Exception as e:
    print('requests library not available. To test the endpoint, install requests or run the script while server is running.')

print('\nDone.')
