import os

forbidden_patterns = [
    'AIza' + 'Sy',
    'sk-',
    'redis://:',
    'neo4j+s://',
    'supabase.co',
]

skip_dirs = [
    '__pycache__', '.git', 'node_modules',
    'venv', '.venv', 'frontend'
]
skip_files = [
    'keys.txt.example',
    'verify_all_phases.py',
    'security_check.py',
    'CHANGELOG.md',
    'README.md',
    'SETUP.md',
]

issues = []
for root, dirs, files in os.walk('.'):
    dirs[:] = [d for d in dirs
               if d not in skip_dirs]
    for file in files:
        if not file.endswith('.py'): continue
        if file in skip_files: continue
        filepath = os.path.join(root, file)
        with open(filepath, 'r',
                  encoding='utf-8',
                  errors='ignore') as f:
            content = f.read()
        for pattern in forbidden_patterns:
            if pattern in content:
                issues.append(
                    f'{filepath}: {pattern}'
                )

if issues:
    print('SECRETS FOUND:')
    for i in issues: print(f'  {i}')
else:
    print('No hardcoded secrets found - clean')
