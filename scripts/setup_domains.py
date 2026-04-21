import yaml
import os
import sys

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def load_domains():
    config_path = os.path.join('config', 'domains.yaml')
    if not os.path.exists(config_path):
        return []
    with open(config_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
        return data.get('domains', [])

def save_domains(domains):
    os.makedirs('config', exist_ok=True)
    config_path = os.path.join('config', 'domains.yaml')
    with open(config_path, 'w', encoding='utf-8') as f:
        yaml.dump({'domains': domains}, f, sort_keys=False)

def print_header():
    print("╔" + "═" * 46 + "╗")
    print("║     Teaching Monster — Domain Setup          ║")
    print("╚" + "═" * 46 + "╝")

def show_domains(domains):
    if not domains:
        print("\n(No domains configured)")
        return
    
    print("\nCurrent configured domains:")
    for i, d in enumerate(domains, 1):
        print(f"  {i}. {d['name']:<20} ({len(d['topics'])} topics) [{d['level']}]")

def add_domain(domains):
    print("\n--- Add New Domain ---")
    name = input("Domain name (e.g., Elementary Music): ").strip()
    if not name:
        print("Name cannot be empty.")
        return
    
    level = input("Education level [primary/secondary/university]: ").strip().lower()
    if level not in ['primary', 'secondary', 'university']:
        print("Invalid level. Defaulting to 'secondary'.")
        level = 'secondary'
    
    print("Topics (one per line, blank line to finish):")
    topics = []
    while True:
        t = input("  > ").strip()
        if not t:
            break
        topics.append(t)
    
    if not topics:
        print("Error: A domain must have at least one topic.")
        return
    
    domains.append({
        'name': name,
        'level': level,
        'topics': topics
    })
    print(f"\n✓ Added \"{name}\" with {len(topics)} topics.")

def remove_domain(domains):
    if not domains:
        print("\nNothing to remove.")
        return
    
    show_domains(domains)
    try:
        idx = int(input("\nEnter number to remove (0 to cancel): "))
        if idx == 0:
            return
        if 1 <= idx <= len(domains):
            removed = domains.pop(idx - 1)
            print(f"\n✓ Removed \"{removed['name']}\".")
        else:
            print("\nInvalid number.")
    except ValueError:
        print("\nPlease enter a valid number.")

def clear_all():
    confirm = input("\nARE YOU SURE? This will clear all domains. (y/N): ").lower()
    if confirm == 'y':
        return []
    return None

def main():
    domains = load_domains()
    
    while True:
        clear_screen()
        print_header()
        show_domains(domains)
        
        print("\nOptions:")
        print("  [A] Add a domain")
        print("  [R] Remove a domain")
        print("  [C] Clear all and start fresh")
        print("  [S] Save & run ingestion now")
        print("  [Q] Save to domains.yaml and quit")
        print("  [X] Exit without saving")
        
        choice = input("\n> ").strip().upper()
        
        if choice == 'A':
            add_domain(domains)
            input("\nPress Enter to continue...")
        elif choice == 'R':
            remove_domain(domains)
            input("\nPress Enter to continue...")
        elif choice == 'C':
            cleared = clear_all()
            if cleared is not None:
                domains = cleared
        elif choice == 'S':
            if not domains:
                print("\nError: Cannot save empty domains list.")
                input("\nPress Enter to continue...")
                continue
            save_domains(domains)
            print("\n✓ Domains saved to config/domains.yaml")
            print("--- Starting Ingestion ---")
            # In a real environment, we'd subprocess.run(['python', 'scripts/ingest_rag.py'])
            # For now, we just suggest it since ingest_rag.py isn't built yet.
            print("Note: ingest_rag.py is the next step in the implementation plan.")
            print("Please run: python scripts/ingest_rag.py")
            sys.exit(0)
        elif choice == 'Q':
            if not domains:
                print("\nError: Cannot save empty domains list.")
                input("\nPress Enter to continue...")
                continue
            save_domains(domains)
            print("\n✓ Domains saved. Goodbye!")
            sys.exit(0)
        elif choice == 'X':
            confirm = input("\nDiscard changes and exit? (y/N): ").lower()
            if confirm == 'y':
                sys.exit(0)

if __name__ == "__main__":
    main()
