#!/usr/bin/env python3
"""
AstroVed Agent Management CLI.
Allows administrators to manage agents interactively:
- add: Create new agent with securely prompted password (Argon2id)
- list: Display safe metadata of registered agents
- deactivate: Deactivate an agent
- activate: Re-activate an agent
- change-password: Change an agent's password securely
"""

import sys
import os
import getpass
from datetime import datetime, timezone

# Add backend directory to sys.path so app imports work
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.core.database import get_agents_collection, init_db_indexes
from app.core.security import hash_password

def add_agent():
    print("\n--- Register New AstroVed Agent ---")
    username = input("Username: ").strip()
    if not username:
        print("Error: Username cannot be empty.")
        return 1

    agents_col = get_agents_collection()
    if agents_col.find_one({"username": username}):
        print(f"Error: Agent with username '{username}' already exists.")
        return 1

    display_name = input("Display Name (e.g. Agent 1 (Vedic Support)): ").strip()
    if not display_name:
        display_name = username

    role = input("Role [advisor/admin] (default: advisor): ").strip().lower()
    if role not in ["advisor", "admin"]:
        role = "advisor"

    pwd = getpass.getpass("Password: ")
    if len(pwd) < 6:
        print("Error: Password must be at least 6 characters long.")
        return 1

    pwd_confirm = getpass.getpass("Confirm Password: ")
    if pwd != pwd_confirm:
        print("Error: Passwords do not match.")
        return 1

    pwd_hash = hash_password(pwd)
    now = datetime.now(timezone.utc)

    agent_doc = {
        "username": username,
        "display_name": display_name,
        "role": role,
        "password_hash": pwd_hash,
        "is_active": True,
        "created_at": now,
        "updated_at": now
    }

    agents_col.insert_one(agent_doc)
    print(f"\n✓ Agent '{username}' ({display_name}) created successfully with Argon2id hash.")
    return 0

def list_agents():
    print("\n--- Registered AstroVed Agents ---")
    agents_col = get_agents_collection()
    agents = list(agents_col.find({}, {"password_hash": 0}).sort("created_at", 1))

    if not agents:
        print("No agents registered in the database.")
        return 0

    print(f"{'Username':<18} {'Display Name':<30} {'Role':<10} {'Active':<8} {'Created At'}")
    print("-" * 85)
    for a in agents:
        created = a.get("created_at")
        created_str = created.strftime("%Y-%m-%d %H:%M:%S") if isinstance(created, datetime) else str(created)
        print(f"{a['username']:<18} {a.get('display_name', ''):<30} {a.get('role', 'advisor'):<10} {str(a.get('is_active', True)):<8} {created_str}")
    print("-" * 85)
    return 0

def deactivate_agent():
    username = sys.argv[2].strip() if len(sys.argv) > 2 else input("Username of agent to deactivate: ").strip()
    if not username:
        print("Error: Username cannot be empty.")
        return 1

    agents_col = get_agents_collection()
    import re
    res = agents_col.update_one(
        {"username": {"$regex": f"^{re.escape(username)}$", "$options": "i"}},
        {"$set": {"is_active": False, "updated_at": datetime.now(timezone.utc)}}
    )
    if res.matched_count == 0:
        print(f"Error: Agent '{username}' not found.")
        return 1

    print(f"✓ Agent '{username}' has been deactivated.")
    return 0

def activate_agent():
    username = sys.argv[2].strip() if len(sys.argv) > 2 else input("Username of agent to activate: ").strip()
    if not username:
        print("Error: Username cannot be empty.")
        return 1

    agents_col = get_agents_collection()
    import re
    res = agents_col.update_one(
        {"username": {"$regex": f"^{re.escape(username)}$", "$options": "i"}},
        {"$set": {"is_active": True, "updated_at": datetime.now(timezone.utc)}}
    )
    if res.matched_count == 0:
        print(f"Error: Agent '{username}' not found.")
        return 1

    print(f"✓ Agent '{username}' has been activated.")
    return 0

def change_password():
    if len(sys.argv) > 2 and sys.argv[2].strip():
        username = sys.argv[2].strip()
    else:
        username = input("Username of agent: ").strip()
    if not username:
        print("Error: Username cannot be empty.")
        return 1

    agents_col = get_agents_collection()
    import re
    agent = agents_col.find_one({"username": username}) or agents_col.find_one(
        {"username": {"$regex": f"^{re.escape(username)}$", "$options": "i"}}
    )
    if not agent:
        print(f"Error: Agent '{username}' not found.")
        return 1

    actual_username = agent["username"]

    if len(sys.argv) > 3 and sys.argv[3]:
        new_pwd = sys.argv[3]
    else:
        new_pwd = getpass.getpass("New Password: ")
        if len(new_pwd) < 6:
            print("Error: Password must be at least 6 characters long.")
            return 1

        confirm = getpass.getpass("Confirm New Password: ")
        if new_pwd != confirm:
            print("Error: Passwords do not match.")
            return 1

    if len(new_pwd) < 6:
        print("Error: Password must be at least 6 characters long.")
        return 1

    pwd_hash = hash_password(new_pwd)
    agents_col.update_one(
        {"username": actual_username},
        {"$set": {"password_hash": pwd_hash, "updated_at": datetime.now(timezone.utc)}}
    )
    print(f"✓ Password for agent '{actual_username}' successfully updated with Argon2id.")
    return 0

def main():
    init_db_indexes()
    
    if len(sys.argv) > 1:
        cmd = sys.argv[1].lower()
    else:
        print("\nAstroVed Agent Management")
        print("Commands: add | list | deactivate | activate | change-password")
        cmd = input("Select command: ").strip().lower()

    if cmd == "add":
        sys.exit(add_agent())
    elif cmd == "list":
        sys.exit(list_agents())
    elif cmd == "deactivate":
        sys.exit(deactivate_agent())
    elif cmd == "activate":
        sys.exit(activate_agent())
    elif cmd == "change-password":
        sys.exit(change_password())
    else:
        print(f"Unknown command: '{cmd}'. Use add, list, deactivate, activate, or change-password.")
        sys.exit(1)

if __name__ == "__main__":
    main()
