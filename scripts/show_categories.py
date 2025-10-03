"""Small debugging helper: list available categories and print a sample chunk from each file.
Run: python scripts\show_categories.py
"""
import os
import random

ROOT = os.path.dirname(os.path.dirname(__file__)) if os.path.basename(__file__)=='show_categories.py' else os.path.dirname(__file__)
DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
if not os.path.isdir(DATA_DIR):
    DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')

DATA_DIR = os.path.normpath(DATA_DIR)
print('Data dir:', DATA_DIR)
if not os.path.isdir(DATA_DIR):
    print('No data directory found at', DATA_DIR)
    raise SystemExit(1)

files = [f for f in os.listdir(DATA_DIR) if f.lower().endswith('.txt')]
if not files:
    print('No .txt files in', DATA_DIR)
    raise SystemExit(1)

for fn in files:
    path = os.path.join(DATA_DIR, fn)
    print('\n---', fn)
    with open(path, 'r', encoding='utf-8', errors='replace') as fh:
        text = fh.read()
    print('Size:', len(text))
    chunk = text[:500]
    print('Sample start (500 chars):')
    print(chunk)
    # sample a somewhere-random chunk
    if len(text) > 1000:
        start = random.randint(0, len(text)-800)
        print('Random snippet:')
        print(text[start:start+400])

print('\nFound', len(files), 'category files.')
