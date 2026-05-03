import os
import hashlib
from collections import defaultdict

def hash_file(filepath):
    hasher = hashlib.md5()
    try:
        with open(filepath, 'rb') as f:
            buf = f.read(65536)
            while len(buf) > 0:
                hasher.update(buf)
                buf = f.read(65536)
        return hasher.hexdigest()
    except Exception as e:
        return None

hashes = defaultdict(list)
# skip directories to speed up
skip_dirs = {'.git', 'node_modules', 'venv', '.venv', '__pycache__', '.cache', 'dist', 'build', '.next', '.tox', '.eggs', '.hermes'}

for root, dirs, files in os.walk('.'):
    # modify dirs in place to skip
    dirs[:] = [d for d in dirs if d not in skip_dirs and not d.endswith('.egg-info')]
    
    for f in files:
        filepath = os.path.join(root, f)
        h = hash_file(filepath)
        if h:
            hashes[h].append(filepath)

dupes = {k: v for k, v in hashes.items() if len(v) > 1}
for k, v in dupes.items():
    print(f'Hash {k}:')
    for path in v:
        print(f'  {path}')
