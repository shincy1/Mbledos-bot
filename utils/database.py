import json
import os
from datetime import datetime
from typing import Dict, Any, List

DATA_FILE = 'data/tasks.json'
ACTIVITIES_FILE = 'data/activities.json'
IDENTITIES_FILE = 'data/identities.json'

def ensure_data_directory():
    """Pastikan direktori data ada"""
    os.makedirs('data', exist_ok=True)

def load_tasks() -> Dict[str, Dict[str, Any]]:
    """Load tasks dari file JSON"""
    ensure_data_directory()
    
    if not os.path.exists(DATA_FILE):
        # Buat file kosong dengan struktur JSON yang benar
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump({}, f, indent=4, ensure_ascii=False)
        return {}
    
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            if not content:  # File kosong
                return {}
            
            data = json.loads(content)
            
            # Validasi struktur data
            if not isinstance(data, dict):
                print("Warning: Invalid data structure in tasks.json, resetting...")
                return {}
            
            # Validasi setiap user data
            validated_data = {}
            for user_id, user_tasks in data.items():
                if isinstance(user_tasks, dict):
                    validated_tasks = {}
                    for task_id, task in user_tasks.items():
                        if isinstance(task, dict) and validate_task_structure(task):
                            validated_tasks[task_id] = task
                        else:
                            print(f"Warning: Invalid task structure for user {user_id}, task {task_id}")
                    
                    if validated_tasks:  # Only add if user has valid tasks
                        validated_data[user_id] = validated_tasks
            
            return validated_data
            
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"Error loading tasks: {e}")
        # Backup corrupted file
        if os.path.exists(DATA_FILE):
            backup_name = f"{DATA_FILE}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            try:
                os.rename(DATA_FILE, backup_name)
                print(f"Corrupted file backed up as: {backup_name}")
            except:
                pass
        return {}
    except Exception as e:
        print(f"Unexpected error loading tasks: {e}")
        return {}

def validate_task_structure(task: Dict[str, Any]) -> bool:
    """Validasi struktur task"""
    required_fields = ['title', 'description', 'status', 'priority', 'deadline', 'progress', 'created_at']
    
    if not isinstance(task, dict):
        return False
    
    # Cek field yang wajib ada
    for field in required_fields:
        if field not in task:
            return False
    
    # Validasi tipe data
    try:
        # Status harus string dan valid
        if task['status'] not in ['pending', 'done', 'approved']:
            return False
        
        # Priority harus string dan valid
        if task['priority'] not in ['low', 'medium', 'high']:
            return False
        
        # Progress harus integer 0-100
        progress = int(task['progress'])
        if progress < 0 or progress > 100:
            return False
        
        # Deadline dan created_at harus timestamp yang valid
        float(task['deadline'])
        float(task['created_at'])
        
        # Title dan description harus string
        if not isinstance(task['title'], str) or not isinstance(task['description'], str):
            return False
        
        return True
        
    except (ValueError, TypeError):
        return False

def save_tasks(data: Dict[str, Dict[str, Any]]) -> bool:
    """Simpan tasks ke file JSON"""
    ensure_data_directory()
    
    try:
        # Validasi data sebelum menyimpan
        if not isinstance(data, dict):
            print("Error: Invalid data type for saving tasks")
            return False
        
        # Buat backup file lama jika ada
        if os.path.exists(DATA_FILE):
            backup_name = f"{DATA_FILE}.backup"
            try:
                with open(DATA_FILE, 'r', encoding='utf-8') as original:
                    with open(backup_name, 'w', encoding='utf-8') as backup:
                        backup.write(original.read())
            except:
                pass  # Ignore backup errors
        
        # Simpan data baru
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        
        return True
        
    except Exception as e:
        print(f"Error saving tasks: {e}")
        return False

def load_activities() -> List[Dict[str, str]]:
    """Load activities dari file JSON"""
    ensure_data_directory()
    
    if not os.path.exists(ACTIVITIES_FILE):
        with open(ACTIVITIES_FILE, 'w', encoding='utf-8') as f:
            json.dump([], f, indent=4, ensure_ascii=False)
        return []
    
    try:
        with open(ACTIVITIES_FILE, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            if not content:
                # File kosong, tulis array kosong
                with open(ACTIVITIES_FILE, 'w', encoding='utf-8') as f:
                    json.dump([], f, indent=4, ensure_ascii=False)
                return []
            
            data = json.loads(content)
            
            # Validasi struktur data
            if not isinstance(data, list):
                print("Warning: Invalid activities data structure, resetting...")
                # Reset file dengan array kosong
                with open(ACTIVITIES_FILE, 'w', encoding='utf-8') as f:
                    json.dump([], f, indent=4, ensure_ascii=False)
                return []
            
            # Validasi setiap activity
            validated_activities = []
            for activity in data:
                if isinstance(activity, dict) and validate_activity_structure(activity):
                    validated_activities.append(activity)
                else:
                    print(f"Warning: Invalid activity structure: {activity}")
            
            return validated_activities
            
    except json.JSONDecodeError as e:
        print(f"Error loading activities - JSON decode error: {e}")
        # Backup file yang rusak
        backup_name = f"{ACTIVITIES_FILE}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        try:
            os.rename(ACTIVITIES_FILE, backup_name)
            print(f"Corrupted activities file backed up as: {backup_name}")
        except:
            pass
        
        # Buat file baru
        with open(ACTIVITIES_FILE, 'w', encoding='utf-8') as f:
            json.dump([], f, indent=4, ensure_ascii=False)
        return []
        
    except FileNotFoundError:
        print(f"Activities file not found, creating new one")
        with open(ACTIVITIES_FILE, 'w', encoding='utf-8') as f:
            json.dump([], f, indent=4, ensure_ascii=False)
        return []
        
    except Exception as e:
        print(f"Unexpected error loading activities: {e}")
        return []

def validate_activity_structure(activity: Dict[str, str]) -> bool:
    """Validasi struktur activity"""
    required_fields = ['timestamp', 'user', 'action']
    
    if not isinstance(activity, dict):
        return False
    
    # Cek field yang wajib ada
    for field in required_fields:
        if field not in activity or not isinstance(activity[field], str):
            return False
    
    return True

def save_activities(activities: List[Dict[str, str]]) -> bool:
    """Simpan activities ke file JSON"""
    ensure_data_directory()
    
    try:
        # Validasi data
        if not isinstance(activities, list):
            print("Error: Invalid data type for saving activities")
            return False
        
        # Buat backup file lama jika ada
        if os.path.exists(ACTIVITIES_FILE):
            backup_name = f"{ACTIVITIES_FILE}.backup"
            try:
                with open(ACTIVITIES_FILE, 'r', encoding='utf-8') as original:
                    with open(backup_name, 'w', encoding='utf-8') as backup:
                        backup.write(original.read())
            except:
                pass
        
        # Simpan data baru
        with open(ACTIVITIES_FILE, 'w', encoding='utf-8') as f:
            json.dump(activities, f, indent=4, ensure_ascii=False)
        
        print(f"Successfully saved {len(activities)} activities to file")
        return True
        
    except Exception as e:
        print(f"Error saving activities: {e}")
        return False

def load_identities() -> Dict[str, Dict[str, str]]:
    """Load identities dari file JSON"""
    ensure_data_directory()
    
    if not os.path.exists(IDENTITIES_FILE):
        with open(IDENTITIES_FILE, 'w', encoding='utf-8') as f:
            json.dump({}, f, indent=4, ensure_ascii=False)
        return {}
    
    try:
        with open(IDENTITIES_FILE, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            if not content:
                # File kosong, tulis object kosong
                with open(IDENTITIES_FILE, 'w', encoding='utf-8') as f:
                    json.dump({}, f, indent=4, ensure_ascii=False)
                return {}
            
            data = json.loads(content)
            
            # Validasi struktur data
            if not isinstance(data, dict):
                print("Warning: Invalid identities data structure, resetting...")
                # Reset file dengan object kosong
                with open(IDENTITIES_FILE, 'w', encoding='utf-8') as f:
                    json.dump({}, f, indent=4, ensure_ascii=False)
                return {}
            
            # Validasi setiap identity
            validated_identities = {}
            for user_id, identity in data.items():
                if isinstance(identity, dict) and validate_identity_structure(identity):
                    validated_identities[user_id] = identity
                else:
                    print(f"Warning: Invalid identity structure for user {user_id}")
            
            return validated_identities
            
    except json.JSONDecodeError as e:
        print(f"Error loading identities - JSON decode error: {e}")
        # Backup file yang rusak
        backup_name = f"{IDENTITIES_FILE}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        try:
            os.rename(IDENTITIES_FILE, backup_name)
            print(f"Corrupted identities file backed up as: {backup_name}")
        except:
            pass
        
        # Buat file baru
        with open(IDENTITIES_FILE, 'w', encoding='utf-8') as f:
            json.dump({}, f, indent=4, ensure_ascii=False)
        return {}
        
    except FileNotFoundError:
        print(f"Identities file not found, creating new one")
        with open(IDENTITIES_FILE, 'w', encoding='utf-8') as f:
            json.dump({}, f, indent=4, ensure_ascii=False)
        return {}
        
    except Exception as e:
        print(f"Unexpected error loading identities: {e}")
        return {}

def validate_identity_structure(identity: Dict[str, str]) -> bool:
    """Validasi struktur identity"""
    required_fields = ['full_name', 'nickname', 'discord_name']
    
    if not isinstance(identity, dict):
        return False
    
    # Cek field yang wajib ada
    for field in required_fields:
        if field not in identity or not isinstance(identity[field], str):
            return False
    
    return True

def save_identities(identities: Dict[str, Dict[str, str]]) -> bool:
    """Simpan identities ke file JSON"""
    ensure_data_directory()
    
    try:
        # Validasi data
        if not isinstance(identities, dict):
            print("Error: Invalid data type for saving identities")
            return False
        
        # Buat backup file lama jika ada
        if os.path.exists(IDENTITIES_FILE):
            backup_name = f"{IDENTITIES_FILE}.backup"
            try:
                with open(IDENTITIES_FILE, 'r', encoding='utf-8') as original:
                    with open(backup_name, 'w', encoding='utf-8') as backup:
                        backup.write(original.read())
            except:
                pass
        
        # Simpan data baru
        with open(IDENTITIES_FILE, 'w', encoding='utf-8') as f:
            json.dump(identities, f, indent=4, ensure_ascii=False)
        
        print(f"Successfully saved {len(identities)} identities to file")
        return True
        
    except Exception as e:
        print(f"Error saving identities: {e}")
        return False

def get_user_display_name(user_id: str, fallback_name: str = None) -> str:
    """Dapatkan nama tampilan user (nickname jika ada, fallback jika tidak)"""
    try:
        identities = load_identities()
        identity = identities.get(str(user_id))
        
        if identity and identity.get('nickname'):
            return identity['nickname']
        
        return fallback_name or f"User {user_id}"
        
    except Exception as e:
        print(f"Error getting user display name: {e}")
        return fallback_name or f"User {user_id}"

def get_user_full_name(user_id: str, fallback_name: str = None) -> str:
    """Dapatkan nama lengkap user"""
    try:
        identities = load_identities()
        identity = identities.get(str(user_id))
        
        if identity and identity.get('full_name'):
            return identity['full_name']
        
        return fallback_name or f"User {user_id}"
        
    except Exception as e:
        print(f"Error getting user full name: {e}")
        return fallback_name or f"User {user_id}"

def get_user_identity(user_id: str) -> Dict[str, str]:
    """Dapatkan identitas lengkap user"""
    try:
        identities = load_identities()
        return identities.get(str(user_id), {})
    except Exception as e:
        print(f"Error getting user identity: {e}")
        return {}

def log_activity(user, action: str) -> bool:
    """Log aktivitas user"""
    try:
        activities = load_activities()
        
        # Get display name (nickname if available)
        if hasattr(user, 'id'):
            display_name = get_user_display_name(str(user.id), user.display_name if hasattr(user, 'display_name') else str(user))
        else:
            display_name = str(user)
        
        new_activity = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "user": display_name,
            "action": action
        }
        
        activities.append(new_activity)
        
        # Batasi jumlah log (keep last 1000 entries)
        if len(activities) > 1000:
            activities = activities[-1000:]
        
        result = save_activities(activities)
        if result:
            print(f"Activity logged: {new_activity['user']} - {new_activity['action']}")
        else:
            print(f"Failed to log activity: {new_activity['user']} - {new_activity['action']}")
        
        return result
        
    except Exception as e:
        print(f"Error logging activity: {e}")
        return False

def get_user_tasks(user_id: str) -> Dict[str, Any]:
    """Dapatkan semua tasks untuk user tertentu"""
    tasks = load_tasks()
    return tasks.get(str(user_id), {})

def get_task(user_id: str, task_id: str) -> Dict[str, Any]:
    """Dapatkan task tertentu"""
    user_tasks = get_user_tasks(user_id)
    return user_tasks.get(task_id, {})

def update_task(user_id: str, task_id: str, updates: Dict[str, Any]) -> bool:
    """Update task tertentu"""
    try:
        tasks = load_tasks()
        user_id = str(user_id)
        
        if user_id not in tasks or task_id not in tasks[user_id]:
            return False
        
        # Update fields
        for key, value in updates.items():
            if key in ['title', 'description', 'status', 'priority', 'progress', 'deadline']:
                tasks[user_id][task_id][key] = value
        
        return save_tasks(tasks)
        
    except Exception as e:
        print(f"Error updating task: {e}")
        return False

def delete_task(user_id: str, task_id: str) -> bool:
    """Hapus task tertentu"""
    try:
        tasks = load_tasks()
        user_id = str(user_id)
        
        if user_id not in tasks or task_id not in tasks[user_id]:
            return False
        
        del tasks[user_id][task_id]
        
        # Hapus user entry jika tidak ada task lagi
        if not tasks[user_id]:
            del tasks[user_id]
        
        return save_tasks(tasks)
        
    except Exception as e:
        print(f"Error deleting task: {e}")
        return False

def get_tasks_by_status(status: str) -> Dict[str, Dict[str, Any]]:
    """Dapatkan semua tasks dengan status tertentu"""
    all_tasks = load_tasks()
    filtered_tasks = {}
    
    for user_id, user_tasks in all_tasks.items():
        user_filtered = {}
        for task_id, task in user_tasks.items():
            if task.get('status') == status:
                user_filtered[task_id] = task
        
        if user_filtered:
            filtered_tasks[user_id] = user_filtered
    
    return filtered_tasks

def get_overdue_tasks() -> Dict[str, Dict[str, Any]]:
    """Dapatkan semua tasks yang sudah melewati deadline"""
    all_tasks = load_tasks()
    overdue_tasks = {}
    current_time = datetime.now().timestamp()
    
    for user_id, user_tasks in all_tasks.items():
        user_overdue = {}
        for task_id, task in user_tasks.items():
            if (task.get('status') not in ['done', 'approved'] and 
                task.get('deadline', 0) < current_time):
                user_overdue[task_id] = task
        
        if user_overdue:
            overdue_tasks[user_id] = user_overdue
    
    return overdue_tasks

def cleanup_invalid_data():
    """Bersihkan data yang tidak valid"""
    try:
        print("Starting data cleanup...")
        
        # Cleanup tasks
        tasks = load_tasks()
        cleaned_tasks = {}
        
        for user_id, user_tasks in tasks.items():
            cleaned_user_tasks = {}
            for task_id, task in user_tasks.items():
                if validate_task_structure(task):
                    cleaned_user_tasks[task_id] = task
                else:
                    print(f"Removed invalid task: {user_id}/{task_id}")
            
            if cleaned_user_tasks:
                cleaned_tasks[user_id] = cleaned_user_tasks
        
        save_tasks(cleaned_tasks)
        
        # Cleanup activities
        activities = load_activities()
        cleaned_activities = []
        
        for activity in activities:
            if validate_activity_structure(activity):
                cleaned_activities.append(activity)
            else:
                print(f"Removed invalid activity: {activity}")
        
        save_activities(cleaned_activities)
        
        # Cleanup identities
        identities = load_identities()
        cleaned_identities = {}
        
        for user_id, identity in identities.items():
            if validate_identity_structure(identity):
                cleaned_identities[user_id] = identity
            else:
                print(f"Removed invalid identity: {user_id}")
        
        save_identities(cleaned_identities)
        
        print("Data cleanup completed.")
        return True
        
    except Exception as e:
        print(f"Error during cleanup: {e}")
        return False

# Fungsi untuk reset file activities jika rusak
def reset_activities_file():
    """Reset file activities.json jika rusak"""
    try:
        ensure_data_directory()
        with open(ACTIVITIES_FILE, 'w', encoding='utf-8') as f:
            json.dump([], f, indent=4, ensure_ascii=False)
        print("Activities file has been reset")
        return True
    except Exception as e:
        print(f"Error resetting activities file: {e}")
        return False

def reset_identities_file():
    """Reset file identities.json jika rusak"""
    try:
        ensure_data_directory()
        with open(IDENTITIES_FILE, 'w', encoding='utf-8') as f:
            json.dump({}, f, indent=4, ensure_ascii=False)
        print("Identities file has been reset")
        return True
    except Exception as e:
        print(f"Error resetting identities file: {e}")
        return False