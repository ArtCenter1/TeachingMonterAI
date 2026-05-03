import os

env_path = r'd:\My_Projects\TeachingMonsterAI\.env'
with open(env_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    # Filter out any line that looks like the massive auth json
    if 'NOTEBOOKLM_AUTH_JSON' in line and '{' in line:
        continue
    if 'ACCOUNT_CHOOSER' in line or 'OTZ' in line:
        continue
    new_lines.append(line)

with open(env_path, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
print("Cleanup complete.")
