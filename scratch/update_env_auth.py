import os
import json

def update_env_auth():
    # Paths
    user_profile = os.environ.get('USERPROFILE')
    if not user_profile:
        print("Error: USERPROFILE environment variable not found.")
        return
        
    auth_file = os.path.join(user_profile, '.notebooklm', 'storage_state.json')
    env_file = 'd:/My_Projects/TeachingMonsterAI/.env'
    
    if not os.path.exists(auth_file):
        print(f"Error: {auth_file} not found.")
        return
        
    # Read auth JSON
    try:
        with open(auth_file, 'r', encoding='utf-8') as f:
            auth_data = f.read().strip()
            # Validate it's proper JSON
            json.loads(auth_data)
    except Exception as e:
        print(f"Error reading/parsing auth JSON: {e}")
        return
        
    # Read .env file
    if not os.path.exists(env_file):
        print(f"Error: {env_file} not found.")
        return
        
    with open(env_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    # Update line 27 (index 26) or look for NOTEBOOKLM_AUTH_JSON
    updated = False
    new_lines = []
    auth_key = "NOTEBOOKLM_AUTH_JSON="
    
    for line in lines:
        if line.strip().startswith("NOTEBOOKLM_AUTH_JSON=") or line.strip().startswith("# NOTEBOOKLM_AUTH_JSON="):
            # Escape single quotes if necessary, but typically we wrap in single quotes to avoid shell issues
            # Or just use double quotes and escape internal ones. 
            # The previous one used single quotes.
            new_lines.append(f"NOTEBOOKLM_AUTH_JSON='{auth_data}'\n")
            updated = True
        else:
            new_lines.append(line)
            
    if not updated:
        print("Warning: NOTEBOOKLM_AUTH_JSON not found in .env. Appending to end.")
        new_lines.append(f"\nNOTEBOOKLM_AUTH_JSON='{auth_data}'\n")
        
    # Write back to .env
    with open(env_file, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
        
    print("Successfully updated NOTEBOOKLM_AUTH_JSON in .env")

if __name__ == "__main__":
    update_env_auth()
