import mysql.connector
from mysql.connector import pooling, Error
import json
import os
from datetime import datetime
from typing import Dict, Any, List
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', 3306)),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'database': os.getenv('DB_NAME', 'mbledos_bot'),
    'charset': 'utf8mb4',
    'collation': 'utf8mb4_unicode_ci',
    'autocommit': True,
    'pool_size': int(os.getenv('DB_POOL_SIZE', 5)),
    'pool_reset_session': True
}

# Connection pool
connection_pool = None

def init_database():
    """Initialize database connection pool"""
    global connection_pool
    try:
        connection_pool = pooling.MySQLConnectionPool(
            pool_name="mbledos_pool",
            pool_size=DB_CONFIG['pool_size'],
            pool_reset_session=DB_CONFIG['pool_reset_session'],
            host=DB_CONFIG['host'],
            port=DB_CONFIG['port'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password'],
            database=DB_CONFIG['database'],
            charset=DB_CONFIG['charset'],
            collation=DB_CONFIG['collation'],
            autocommit=DB_CONFIG['autocommit']
        )
        print("✅ Database connection pool initialized successfully")
        return True
    except Error as e:
        print(f"❌ Error initializing database: {e}")
        return False

def get_connection():
    """Get connection from pool"""
    global connection_pool
    if connection_pool is None:
        if not init_database():
            raise Exception("Failed to initialize database connection pool")
    
    try:
        return connection_pool.get_connection()
    except Error as e:
        print(f"Error getting database connection: {e}")
        raise

def ensure_data_directory():
    """Compatibility function - no longer needed for MySQL"""
    pass

def load_tasks() -> Dict[str, Dict[str, Any]]:
    """Load tasks from MySQL database"""
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT user_id, task_id, title, description, status, priority, 
                   deadline, progress, created_at, assigned_by
            FROM tasks
            ORDER BY user_id, CAST(task_id AS UNSIGNED)
        """)
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        # Convert to original format
        tasks = {}
        for row in rows:
            user_id = row['user_id']
            task_id = row['task_id']
            
            if user_id not in tasks:
                tasks[user_id] = {}
            
            tasks[user_id][task_id] = {
                'title': row['title'],
                'description': row['description'],
                'status': row['status'],
                'priority': row['priority'],
                'deadline': float(row['deadline']),
                'progress': row['progress'],
                'created_at': float(row['created_at']),
                'assigned_by': row['assigned_by']
            }
        
        return tasks
        
    except Error as e:
        print(f"Error loading tasks: {e}")
        return {}
    except Exception as e:
        print(f"Unexpected error loading tasks: {e}")
        return {}

def validate_task_structure(task: Dict[str, Any]) -> bool:
    """Validate task structure"""
    required_fields = ['title', 'description', 'status', 'priority', 'deadline', 'progress', 'created_at']
    
    if not isinstance(task, dict):
        return False
    
    for field in required_fields:
        if field not in task:
            return False
    
    try:
        if task['status'] not in ['pending', 'done', 'approved']:
            return False
        
        if task['priority'] not in ['low', 'medium', 'high']:
            return False
        
        progress = int(task['progress'])
        if progress < 0 or progress > 100:
            return False
        
        float(task['deadline'])
        float(task['created_at'])
        
        if not isinstance(task['title'], str) or not isinstance(task['description'], str):
            return False
        
        return True
        
    except (ValueError, TypeError):
        return False

def save_tasks(data: Dict[str, Dict[str, Any]]) -> bool:
    """Save tasks to MySQL database"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Clear existing tasks
        cursor.execute("DELETE FROM tasks")
        
        # Insert new tasks
        insert_query = """
            INSERT INTO tasks (user_id, task_id, title, description, status, priority, 
                             deadline, progress, created_at, assigned_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        for user_id, user_tasks in data.items():
            for task_id, task in user_tasks.items():
                if validate_task_structure(task):
                    cursor.execute(insert_query, (
                        user_id, task_id, task['title'], task['description'],
                        task['status'], task['priority'], task['deadline'],
                        task['progress'], task['created_at'], 
                        task.get('assigned_by')
                    ))
        
        conn.commit()
        cursor.close()
        conn.close()
        return True
        
    except Error as e:
        print(f"Error saving tasks: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error saving tasks: {e}")
        return False

def load_activities() -> List[Dict[str, str]]:
    """Load activities from MySQL database"""
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT timestamp, user, action
            FROM activities
            ORDER BY id ASC
        """)
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        activities = []
        for row in rows:
            if validate_activity_structure(row):
                activities.append({
                    'timestamp': row['timestamp'],
                    'user': row['user'],
                    'action': row['action']
                })
        
        return activities
        
    except Error as e:
        print(f"Error loading activities: {e}")
        return []
    except Exception as e:
        print(f"Unexpected error loading activities: {e}")
        return []

def validate_activity_structure(activity: Dict[str, str]) -> bool:
    """Validate activity structure"""
    required_fields = ['timestamp', 'user', 'action']
    
    if not isinstance(activity, dict):
        return False
    
    for field in required_fields:
        if field not in activity or not isinstance(activity[field], str):
            return False
    
    return True

def save_activities(activities: List[Dict[str, str]]) -> bool:
    """Save activities to MySQL database"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Clear existing activities
        cursor.execute("DELETE FROM activities")
        
        # Insert new activities
        insert_query = """
            INSERT INTO activities (timestamp, user, action)
            VALUES (%s, %s, %s)
        """
        
        for activity in activities:
            if validate_activity_structure(activity):
                cursor.execute(insert_query, (
                    activity['timestamp'],
                    activity['user'],
                    activity['action']
                ))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print(f"Successfully saved {len(activities)} activities to database")
        return True
        
    except Error as e:
        print(f"Error saving activities: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error saving activities: {e}")
        return False

def load_identities() -> Dict[str, Dict[str, str]]:
    """Load identities from MySQL database"""
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT user_id, full_name, nickname, discord_name, updated_at, updated_by
            FROM identities
        """)
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        identities = {}
        for row in rows:
            identities[row['user_id']] = {
                'full_name': row['full_name'],
                'nickname': row['nickname'],
                'discord_name': row['discord_name'],
                'updated_at': row['updated_at'],
                'updated_by': row['updated_by']
            }
        
        return identities
        
    except Error as e:
        print(f"Error loading identities: {e}")
        return {}
    except Exception as e:
        print(f"Unexpected error loading identities: {e}")
        return {}

def validate_identity_structure(identity: Dict[str, str]) -> bool:
    """Validate identity structure"""
    required_fields = ['full_name', 'nickname', 'discord_name']
    
    if not isinstance(identity, dict):
        return False
    
    for field in required_fields:
        if field not in identity or not isinstance(identity[field], str):
            return False
    
    return True

def save_identities(identities: Dict[str, Dict[str, str]]) -> bool:
    """Save identities to MySQL database"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Use INSERT ... ON DUPLICATE KEY UPDATE for upsert behavior
        upsert_query = """
            INSERT INTO identities (user_id, full_name, nickname, discord_name, updated_at, updated_by)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                full_name = VALUES(full_name),
                nickname = VALUES(nickname),
                discord_name = VALUES(discord_name),
                updated_at = VALUES(updated_at),
                updated_by = VALUES(updated_by)
        """
        
        for user_id, identity in identities.items():
            if validate_identity_structure(identity):
                cursor.execute(upsert_query, (
                    user_id,
                    identity['full_name'],
                    identity['nickname'],
                    identity['discord_name'],
                    identity.get('updated_at'),
                    identity.get('updated_by')
                ))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print(f"Successfully saved {len(identities)} identities to database")
        return True
        
    except Error as e:
        print(f"Error saving identities: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error saving identities: {e}")
        return False

def get_user_display_name(user_id: str, fallback_name: str = None) -> str:
    """Get user display name (nickname if available, fallback if not)"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT nickname FROM identities WHERE user_id = %s", (str(user_id),))
        result = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if result and result[0]:
            return result[0]
        
        return fallback_name or f"User {user_id}"
        
    except Error as e:
        print(f"Error getting user display name: {e}")
        return fallback_name or f"User {user_id}"
    except Exception as e:
        print(f"Unexpected error getting user display name: {e}")
        return fallback_name or f"User {user_id}"

def get_user_full_name(user_id: str, fallback_name: str = None) -> str:
    """Get user full name"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT full_name FROM identities WHERE user_id = %s", (str(user_id),))
        result = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if result and result[0]:
            return result[0]
        
        return fallback_name or f"User {user_id}"
        
    except Error as e:
        print(f"Error getting user full name: {e}")
        return fallback_name or f"User {user_id}"
    except Exception as e:
        print(f"Unexpected error getting user full name: {e}")
        return fallback_name or f"User {user_id}"

def get_user_identity(user_id: str) -> Dict[str, str]:
    """Get complete user identity"""
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT full_name, nickname, discord_name, updated_at, updated_by
            FROM identities WHERE user_id = %s
        """, (str(user_id),))
        
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        return result if result else {}
        
    except Error as e:
        print(f"Error getting user identity: {e}")
        return {}
    except Exception as e:
        print(f"Unexpected error getting user identity: {e}")
        return {}

def log_activity(user, action: str) -> bool:
    """Log user activity"""
    try:
        # Get display name (nickname if available)
        if hasattr(user, 'id'):
            display_name = get_user_display_name(str(user.id), user.display_name if hasattr(user, 'display_name') else str(user))
        else:
            display_name = str(user)
        
        conn = get_connection()
        cursor = conn.cursor()
        
        # Insert new activity
        cursor.execute("""
            INSERT INTO activities (timestamp, user, action)
            VALUES (%s, %s, %s)
        """, (
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            display_name,
            action
        ))
        
        conn.commit()
        
        # Keep only last 1000 activities
        cursor.execute("""
            DELETE FROM activities 
            WHERE id NOT IN (
                SELECT id FROM (
                    SELECT id FROM activities 
                    ORDER BY id DESC 
                    LIMIT 1000
                ) AS keep_activities
            )
        """)
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print(f"Activity logged: {display_name} - {action}")
        return True
        
    except Error as e:
        print(f"Error logging activity: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error logging activity: {e}")
        return False

def get_user_tasks(user_id: str) -> Dict[str, Any]:
    """Get all tasks for specific user"""
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT task_id, title, description, status, priority, 
                   deadline, progress, created_at, assigned_by
            FROM tasks
            WHERE user_id = %s
            ORDER BY CAST(task_id AS UNSIGNED)
        """, (str(user_id),))
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        tasks = {}
        for row in rows:
            tasks[row['task_id']] = {
                'title': row['title'],
                'description': row['description'],
                'status': row['status'],
                'priority': row['priority'],
                'deadline': float(row['deadline']),
                'progress': row['progress'],
                'created_at': float(row['created_at']),
                'assigned_by': row['assigned_by']
            }
        
        return tasks
        
    except Error as e:
        print(f"Error getting user tasks: {e}")
        return {}
    except Exception as e:
        print(f"Unexpected error getting user tasks: {e}")
        return {}

def get_task(user_id: str, task_id: str) -> Dict[str, Any]:
    """Get specific task"""
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT title, description, status, priority, 
                   deadline, progress, created_at, assigned_by
            FROM tasks
            WHERE user_id = %s AND task_id = %s
        """, (str(user_id), task_id))
        
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if result:
            return {
                'title': result['title'],
                'description': result['description'],
                'status': result['status'],
                'priority': result['priority'],
                'deadline': float(result['deadline']),
                'progress': result['progress'],
                'created_at': float(result['created_at']),
                'assigned_by': result['assigned_by']
            }
        
        return {}
        
    except Error as e:
        print(f"Error getting task: {e}")
        return {}
    except Exception as e:
        print(f"Unexpected error getting task: {e}")
        return {}

def update_task(user_id: str, task_id: str, updates: Dict[str, Any]) -> bool:
    """Update specific task"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Build dynamic update query
        update_fields = []
        values = []
        
        allowed_fields = ['title', 'description', 'status', 'priority', 'progress', 'deadline']
        for key, value in updates.items():
            if key in allowed_fields:
                update_fields.append(f"{key} = %s")
                values.append(value)
        
        if not update_fields:
            return False
        
        values.extend([str(user_id), task_id])
        
        query = f"""
            UPDATE tasks 
            SET {', '.join(update_fields)}
            WHERE user_id = %s AND task_id = %s
        """
        
        cursor.execute(query, values)
        success = cursor.rowcount > 0
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return success
        
    except Error as e:
        print(f"Error updating task: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error updating task: {e}")
        return False

def delete_task(user_id: str, task_id: str) -> bool:
    """Delete specific task"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            DELETE FROM tasks 
            WHERE user_id = %s AND task_id = %s
        """, (str(user_id), task_id))
        
        success = cursor.rowcount > 0
        conn.commit()
        cursor.close()
        conn.close()
        
        return success
        
    except Error as e:
        print(f"Error deleting task: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error deleting task: {e}")
        return False

def get_tasks_by_status(status: str) -> Dict[str, Dict[str, Any]]:
    """Get all tasks with specific status"""
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT user_id, task_id, title, description, status, priority, 
                   deadline, progress, created_at, assigned_by
            FROM tasks
            WHERE status = %s
            ORDER BY user_id, CAST(task_id AS UNSIGNED)
        """, (status,))
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        tasks = {}
        for row in rows:
            user_id = row['user_id']
            task_id = row['task_id']
            
            if user_id not in tasks:
                tasks[user_id] = {}
            
            tasks[user_id][task_id] = {
                'title': row['title'],
                'description': row['description'],
                'status': row['status'],
                'priority': row['priority'],
                'deadline': float(row['deadline']),
                'progress': row['progress'],
                'created_at': float(row['created_at']),
                'assigned_by': row['assigned_by']
            }
        
        return tasks
        
    except Error as e:
        print(f"Error getting tasks by status: {e}")
        return {}
    except Exception as e:
        print(f"Unexpected error getting tasks by status: {e}")
        return {}

def get_overdue_tasks() -> Dict[str, Dict[str, Any]]:
    """Get all overdue tasks"""
    try:
        current_time = datetime.now().timestamp()
        
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT user_id, task_id, title, description, status, priority, 
                   deadline, progress, created_at, assigned_by
            FROM tasks
            WHERE status NOT IN ('done', 'approved') AND deadline < %s
            ORDER BY user_id, CAST(task_id AS UNSIGNED)
        """, (current_time,))
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        tasks = {}
        for row in rows:
            user_id = row['user_id']
            task_id = row['task_id']
            
            if user_id not in tasks:
                tasks[user_id] = {}
            
            tasks[user_id][task_id] = {
                'title': row['title'],
                'description': row['description'],
                'status': row['status'],
                'priority': row['priority'],
                'deadline': float(row['deadline']),
                'progress': row['progress'],
                'created_at': float(row['created_at']),
                'assigned_by': row['assigned_by']
            }
        
        return tasks
        
    except Error as e:
        print(f"Error getting overdue tasks: {e}")
        return {}
    except Exception as e:
        print(f"Unexpected error getting overdue tasks: {e}")
        return {}

def cleanup_invalid_data():
    """Clean up invalid data - MySQL constraints handle most validation"""
    try:
        print("Starting data cleanup...")
        
        conn = get_connection()
        cursor = conn.cursor()
        
        # Clean up tasks with invalid progress values
        cursor.execute("""
            UPDATE tasks 
            SET progress = CASE 
                WHEN progress < 0 THEN 0
                WHEN progress > 100 THEN 100
                ELSE progress
            END
            WHERE progress < 0 OR progress > 100
        """)
        
        # Clean up tasks with invalid status
        cursor.execute("""
            UPDATE tasks 
            SET status = 'pending'
            WHERE status NOT IN ('pending', 'done', 'approved')
        """)
        
        # Clean up tasks with invalid priority
        cursor.execute("""
            UPDATE tasks 
            SET priority = 'medium'
            WHERE priority NOT IN ('low', 'medium', 'high')
        """)
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print("Data cleanup completed.")
        return True
        
    except Error as e:
        print(f"Error during cleanup: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error during cleanup: {e}")
        return False

def reset_activities_file():
    """Reset activities table"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM activities")
        conn.commit()
        cursor.close()
        conn.close()
        
        print("Activities table has been reset")
        return True
        
    except Error as e:
        print(f"Error resetting activities: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error resetting activities: {e}")
        return False

def reset_identities_file():
    """Reset identities table"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM identities")
        conn.commit()
        cursor.close()
        conn.close()
        
        print("Identities table has been reset")
        return True
        
    except Error as e:
        print(f"Error resetting identities: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error resetting identities: {e}")
        return False

# Config functions for registered roles
def load_registered_roles() -> List[int]:
    """Load registered roles from config table"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT config_value 
            FROM config 
            WHERE config_key = 'registered_roles'
        """)
        
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if result and result[0]:
            return json.loads(result[0])
        
        return []
        
    except Error as e:
        print(f"Error loading registered roles: {e}")
        return []
    except Exception as e:
        print(f"Unexpected error loading registered roles: {e}")
        return []

def save_registered_roles(roles: List[int]) -> bool:
    """Save registered roles to config table"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO config (config_key, config_value)
            VALUES ('registered_roles', %s)
            ON DUPLICATE KEY UPDATE config_value = VALUES(config_value)
        """, (json.dumps(roles),))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True
        
    except Error as e:
        print(f"Error saving registered roles: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error saving registered roles: {e}")
        return False

# Initialize database on import
if not init_database():
    print("⚠️ Warning: Database initialization failed. Some features may not work.")
