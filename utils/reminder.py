import asyncio
from datetime import datetime, timedelta
from utils.database import load_tasks, get_overdue_tasks, log_activity, get_user_display_name
import discord

class ReminderSystem:
    def __init__(self, bot):
        self.bot = bot
        self.last_check = datetime.now()
        self.reminder_cache = {}  # Cache untuk mencegah spam reminder
    
    def should_send_reminder(self, user_id: str, task_id: str, reminder_type: str) -> bool:
        """Cek apakah reminder sudah dikirim dalam periode tertentu"""
        cache_key = f"{user_id}_{task_id}_{reminder_type}"
        now = datetime.now()
        
        if cache_key in self.reminder_cache:
            last_sent = self.reminder_cache[cache_key]
            # Jangan kirim reminder yang sama dalam 6 jam
            if now - last_sent < timedelta(hours=6):
                return False
        
        self.reminder_cache[cache_key] = now
        return True
    
    def clean_reminder_cache(self):
        """Bersihkan cache reminder yang sudah lama"""
        now = datetime.now()
        expired_keys = []
        
        for key, timestamp in self.reminder_cache.items():
            if now - timestamp > timedelta(days=1):
                expired_keys.append(key)
        
        for key in expired_keys:
            del self.reminder_cache[key]

async def check_deadlines(bot):
    """Fungsi utama untuk mengecek deadline dan mengirim reminder"""
    try:
        reminder_system = ReminderSystem(bot)
        tasks = load_tasks()
        
        if not tasks:
            return
        
        now = datetime.now()
        current_timestamp = now.timestamp()
        
        # Statistik
        total_checked = 0
        reminders_sent = 0
        overdue_found = 0
        
        for user_id, user_tasks in tasks.items():
            if not user_tasks:
                continue
            
            try:
                user = bot.get_user(int(user_id))
                if not user:
                    continue
                
                for task_id, task in user_tasks.items():
                    total_checked += 1
                    
                    # Skip task yang sudah selesai atau disetujui
                    if task.get("status") in ["done", "approved"]:
                        continue
                    
                    deadline_timestamp = task.get("deadline", 0)
                    created_timestamp = task.get("created_at", 0)
                    
                    if not deadline_timestamp or not created_timestamp:
                        continue
                    
                    deadline_dt = datetime.fromtimestamp(deadline_timestamp)
                    created_dt = datetime.fromtimestamp(created_timestamp)
                    
                    # Hitung durasi total dan waktu yang sudah berlalu
                    total_duration = deadline_timestamp - created_timestamp
                    elapsed_time = current_timestamp - created_timestamp
                    time_remaining = deadline_timestamp - current_timestamp
                    
                    # Tentukan jenis reminder
                    reminder_sent = False
                    
                    # 1. Reminder overdue (sudah lewat deadline)
                    if current_timestamp > deadline_timestamp:
                        if reminder_system.should_send_reminder(user_id, task_id, "overdue"):
                            await send_overdue_reminder(user, task, task_id, deadline_dt, user_id)
                            reminder_sent = True
                            overdue_found += 1
                    
                    # 2. Reminder deadline dekat (24 jam sebelum deadline)
                    elif time_remaining <= 86400 and time_remaining > 0:  # 24 jam
                        if reminder_system.should_send_reminder(user_id, task_id, "24h"):
                            await send_deadline_reminder(user, task, task_id, deadline_dt, "24 jam", user_id)
                            reminder_sent = True
                    
                    # 3. Reminder 80% waktu berlalu
                    elif elapsed_time >= 0.8 * total_duration:
                        if reminder_system.should_send_reminder(user_id, task_id, "80percent"):
                            progress_percentage = int((elapsed_time / total_duration) * 100)
                            await send_progress_reminder(user, task, task_id, deadline_dt, progress_percentage, user_id)
                            reminder_sent = True
                    
                    # 4. Reminder 50% waktu berlalu (untuk task prioritas tinggi)
                    elif task.get("priority") == "high" and elapsed_time >= 0.5 * total_duration:
                        if reminder_system.should_send_reminder(user_id, task_id, "50percent_high"):
                            await send_priority_reminder(user, task, task_id, deadline_dt, user_id)
                            reminder_sent = True
                    
                    if reminder_sent:
                        reminders_sent += 1
                        
            except Exception as e:
                print(f"Error processing reminders for user {user_id}: {e}")
                continue
        
        # Bersihkan cache reminder
        reminder_system.clean_reminder_cache()
        
        # Log statistik jika ada aktivitas
        if reminders_sent > 0 or overdue_found > 0:
            print(f"Reminder check completed: {total_checked} tasks checked, {reminders_sent} reminders sent, {overdue_found} overdue tasks")
        
    except Exception as e:
        print(f"Error in check_deadlines: {e}")

async def send_overdue_reminder(user, task, task_id, deadline_dt, user_id):
    """Kirim reminder untuk task yang sudah overdue"""
    try:
        overdue_duration = datetime.now() - deadline_dt
        overdue_str = format_duration(overdue_duration)
        
        # Get user display name
        display_name = get_user_display_name(user_id, user.display_name)
        
        embed = discord.Embed(
            title="🚨 TUGAS TERLAMBAT!",
            description=f"Halo **{display_name}**, tugas Anda sudah melewati deadline!",
            color=0xe74c3c
        )
        
        embed.add_field(name="📝 Tugas", value=task.get('title', 'Untitled'), inline=False)
        embed.add_field(name="📄 Deskripsi", value=task.get('description', 'Tidak ada deskripsi')[:200] + "..." if len(task.get('description', '')) > 200 else task.get('description', 'Tidak ada deskripsi'), inline=False)
        embed.add_field(name="⏰ Deadline", value=deadline_dt.strftime("%d/%m/%Y %H:%M"), inline=True)
        embed.add_field(name="⏱️ Terlambat", value=overdue_str, inline=True)
        embed.add_field(name="📈 Progress", value=f"{task.get('progress', 0)}%", inline=True)
        embed.add_field(name="🆔 Task ID", value=f"#{task_id}", inline=True)
        
        embed.add_field(
            name="💡 Tindakan",
            value="Segera selesaikan tugas ini dan update progress ke 100%!",
            inline=False
        )
        
        embed.set_footer(text="Gunakan /myjob untuk mengupdate progress tugas")
        
        await user.send(embed=embed)
        
    except discord.Forbidden:
        print(f"Cannot send overdue reminder to user {user.id} (DMs disabled)")
    except Exception as e:
        print(f"Error sending overdue reminder to user {user.id}: {e}")

async def send_deadline_reminder(user, task, task_id, deadline_dt, time_left, user_id):
    """Kirim reminder untuk deadline yang dekat"""
    try:
        # Get user display name
        display_name = get_user_display_name(user_id, user.display_name)
        
        embed = discord.Embed(
            title="⏰ DEADLINE MENDEKAT!",
            description=f"Halo **{display_name}**, deadline tugas Anda tinggal {time_left} lagi!",
            color=0xf39c12
        )
        
        embed.add_field(name="📝 Tugas", value=task.get('title', 'Untitled'), inline=False)
        embed.add_field(name="📄 Deskripsi", value=task.get('description', 'Tidak ada deskripsi')[:200] + "..." if len(task.get('description', '')) > 200 else task.get('description', 'Tidak ada deskripsi'), inline=False)
        embed.add_field(name="⏰ Deadline", value=deadline_dt.strftime("%d/%m/%Y %H:%M"), inline=True)
        embed.add_field(name="📈 Progress", value=f"{task.get('progress', 0)}%", inline=True)
        embed.add_field(name="⚡ Prioritas", value=task.get('priority', 'medium').title(), inline=True)
        embed.add_field(name="🆔 Task ID", value=f"#{task_id}", inline=True)
        
        progress = task.get('progress', 0)
        if progress < 50:
            urgency_msg = "🔴 Progress masih rendah! Segera kerjakan tugas ini!"
        elif progress < 80:
            urgency_msg = "🟡 Hampir selesai! Sedikit lagi untuk menyelesaikan tugas."
        else:
            urgency_msg = "🟢 Tinggal sedikit lagi! Selesaikan dan update progress ke 100%."
        
        embed.add_field(name="💡 Status", value=urgency_msg, inline=False)
        embed.set_footer(text="Gunakan /myjob untuk mengupdate progress tugas")
        
        await user.send(embed=embed)
        
    except discord.Forbidden:
        print(f"Cannot send deadline reminder to user {user.id} (DMs disabled)")
    except Exception as e:
        print(f"Error sending deadline reminder to user {user.id}: {e}")

async def send_progress_reminder(user, task, task_id, deadline_dt, time_percentage, user_id):
    """Kirim reminder berdasarkan persentase waktu yang berlalu"""
    try:
        # Get user display name
        display_name = get_user_display_name(user_id, user.display_name)
        
        embed = discord.Embed(
            title="📊 PENGINGAT PROGRESS",
            description=f"Halo **{display_name}**, sudah {time_percentage}% waktu berlalu untuk tugas ini!",
            color=0x3498db
        )
        
        embed.add_field(name="📝 Tugas", value=task.get('title', 'Untitled'), inline=False)
        embed.add_field(name="⏰ Deadline", value=deadline_dt.strftime("%d/%m/%Y %H:%M"), inline=True)
        embed.add_field(name="📈 Progress Saat Ini", value=f"{task.get('progress', 0)}%", inline=True)
        embed.add_field(name="⚡ Prioritas", value=task.get('priority', 'medium').title(), inline=True)
        embed.add_field(name="🆔 Task ID", value=f"#{task_id}", inline=True)
        
        # Saran berdasarkan progress vs waktu
        current_progress = task.get('progress', 0)
        if current_progress < time_percentage - 20:
            suggestion = "🔴 Progress tertinggal dari jadwal! Percepat pengerjaan."
        elif current_progress < time_percentage:
            suggestion = "🟡 Progress sedikit tertinggal. Tingkatkan fokus pada tugas ini."
        else:
            suggestion = "🟢 Progress bagus! Pertahankan momentum ini."
        
        embed.add_field(name="💡 Saran", value=suggestion, inline=False)
        embed.set_footer(text="Gunakan /myjob untuk mengupdate progress tugas")
        
        await user.send(embed=embed)
        
    except discord.Forbidden:
        print(f"Cannot send progress reminder to user {user.id} (DMs disabled)")
    except Exception as e:
        print(f"Error sending progress reminder to user {user.id}: {e}")

async def send_priority_reminder(user, task, task_id, deadline_dt, user_id):
    """Kirim reminder khusus untuk task prioritas tinggi"""
    try:
        # Get user display name
        display_name = get_user_display_name(user_id, user.display_name)
        
        embed = discord.Embed(
            title="🔥 TUGAS PRIORITAS TINGGI",
            description=f"Halo **{display_name}**, reminder untuk tugas dengan prioritas tinggi!",
            color=0xe74c3c
        )
        
        embed.add_field(name="📝 Tugas", value=task.get('title', 'Untitled'), inline=False)
        embed.add_field(name="📄 Deskripsi", value=task.get('description', 'Tidak ada deskripsi')[:200] + "..." if len(task.get('description', '')) > 200 else task.get('description', 'Tidak ada deskripsi'), inline=False)
        embed.add_field(name="⏰ Deadline", value=deadline_dt.strftime("%d/%m/%Y %H:%M"), inline=True)
        embed.add_field(name="📈 Progress", value=f"{task.get('progress', 0)}%", inline=True)
        embed.add_field(name="🆔 Task ID", value=f"#{task_id}", inline=True)
        
        embed.add_field(
            name="⚠️ Penting",
            value="Tugas ini memiliki prioritas tinggi. Pastikan untuk memberikan perhatian ekstra!",
            inline=False
        )
        
        embed.set_footer(text="Gunakan /myjob untuk mengupdate progress tugas")
        
        await user.send(embed=embed)
        
    except discord.Forbidden:
        print(f"Cannot send priority reminder to user {user.id} (DMs disabled)")
    except Exception as e:
        print(f"Error sending priority reminder to user {user.id}: {e}")

def format_duration(duration: timedelta) -> str:
    """Format durasi menjadi string yang mudah dibaca"""
    total_seconds = int(duration.total_seconds())
    
    if total_seconds < 0:
        return "0 detik"
    
    days = total_seconds // 86400
    hours = (total_seconds % 86400) // 3600
    minutes = (total_seconds % 3600) // 60
    
    parts = []
    if days > 0:
        parts.append(f"{days} hari")
    if hours > 0:
        parts.append(f"{hours} jam")
    if minutes > 0 and days == 0:  # Only show minutes if less than a day
        parts.append(f"{minutes} menit")
    
    if not parts:
        return "kurang dari 1 menit"
    
    return ", ".join(parts)

async def send_daily_summary(bot, guild_id: int = None):
    """Kirim ringkasan harian ke channel tertentu (opsional)"""
    try:
        overdue_tasks = get_overdue_tasks()
        pending_tasks = {}
        
        tasks = load_tasks()
        for user_id, user_tasks in tasks.items():
            pending_count = sum(1 for task in user_tasks.values() if task.get('status') == 'pending')
            if pending_count > 0:
                pending_tasks[user_id] = pending_count
        
        if not overdue_tasks and not pending_tasks:
            return  # Tidak ada yang perlu dilaporkan
        
        # Log summary activity dengan display names
        overdue_count = sum(len(user_tasks) for user_tasks in overdue_tasks.values())
        pending_count = sum(pending_tasks.values())
        
        summary_msg = f"Daily summary: {overdue_count} overdue tasks, {pending_count} pending tasks"
        log_activity("System", summary_msg)
        
        print(f"Daily summary: {overdue_count} overdue, {pending_count} pending tasks")
        
    except Exception as e:
        print(f"Error in send_daily_summary: {e}")

async def check_and_notify_managers(bot, guild_id: int = None):
    """Notifikasi ke task manager tentang task yang perlu perhatian"""
    try:
        if not guild_id:
            return
        
        guild = bot.get_guild(guild_id)
        if not guild:
            return
        
        # Load config untuk mendapatkan task manager role
        import json
        try:
            with open("config.json", "r") as f:
                config = json.load(f)
        except:
            return
        
        # Cari task manager role
        task_manager_role = None
        for role in guild.roles:
            if role.name.lower() == "task manager":
                task_manager_role = role
                break
        
        if not task_manager_role:
            return
        
        # Hitung statistik
        overdue_tasks = get_overdue_tasks()
        overdue_count = sum(len(user_tasks) for user_tasks in overdue_tasks.values())
        
        if overdue_count == 0:
            return
        
        # Kirim notifikasi ke semua task manager
        for member in task_manager_role.members:
            try:
                embed = discord.Embed(
                    title="📊 Laporan Task Manager",
                    description=f"Ada {overdue_count} tugas yang sudah melewati deadline!",
                    color=0xe74c3c
                )
                
                # Detail overdue tasks dengan display names
                overdue_details = ""
                for user_id, user_tasks in overdue_tasks.items():
                    user = bot.get_user(int(user_id))
                    display_name = get_user_display_name(user_id, user.display_name if user else f"User {user_id}")
                    overdue_details += f"• **{display_name}**: {len(user_tasks)} tugas\n"
                
                if overdue_details:
                    embed.add_field(name="🚨 Tugas Terlambat", value=overdue_details, inline=False)
                
                embed.add_field(
                    name="💡 Tindakan",
                    value="Gunakan `/listjob` untuk melihat detail tugas dan follow up dengan anggota tim.",
                    inline=False
                )
                
                embed.set_footer(text="Laporan otomatis sistem reminder")
                
                await member.send(embed=embed)
                
            except discord.Forbidden:
                continue  # Skip jika tidak bisa kirim DM
            except Exception as e:
                print(f"Error sending manager notification to {member.id}: {e}")
                continue
        
    except Exception as e:
        print(f"Error in check_and_notify_managers: {e}")

async def cleanup_completed_reminders():
    """Bersihkan reminder untuk task yang sudah selesai"""
    try:
        # Fungsi ini bisa dipanggil secara berkala untuk membersihkan cache
        # reminder yang tidak diperlukan lagi
        pass
    except Exception as e:
        print(f"Error in cleanup_completed_reminders: {e}")

# Fungsi utilitas tambahan
def get_next_reminder_time(task: dict) -> datetime:
    """Hitung kapan reminder berikutnya harus dikirim"""
    try:
        deadline_timestamp = task.get("deadline", 0)
        created_timestamp = task.get("created_at", 0)
        
        if not deadline_timestamp or not created_timestamp:
            return None
        
        deadline_dt = datetime.fromtimestamp(deadline_timestamp)
        created_dt = datetime.fromtimestamp(created_timestamp)
        now = datetime.now()
        
        # Jika sudah overdue
        if now > deadline_dt:
            return now + timedelta(hours=6)  # Reminder overdue setiap 6 jam
        
        # Hitung milestone reminder
        total_duration = deadline_timestamp - created_timestamp
        
        # 50% untuk high priority
        if task.get("priority") == "high":
            fifty_percent_time = created_dt + timedelta(seconds=total_duration * 0.5)
            if now < fifty_percent_time:
                return fifty_percent_time
        
        # 80% untuk semua task
        eighty_percent_time = created_dt + timedelta(seconds=total_duration * 0.8)
        if now < eighty_percent_time:
            return eighty_percent_time
        
        # 24 jam sebelum deadline
        twentyfour_hour_before = deadline_dt - timedelta(hours=24)
        if now < twentyfour_hour_before:
            return twentyfour_hour_before
        
        return deadline_dt
        
    except Exception as e:
        print(f"Error calculating next reminder time: {e}")
        return None

def should_send_urgent_reminder(task: dict) -> bool:
    """Tentukan apakah task memerlukan reminder urgent"""
    try:
        now = datetime.now().timestamp()
        deadline = task.get("deadline", 0)
        progress = task.get("progress", 0)
        priority = task.get("priority", "medium")
        
        # Sudah overdue
        if now > deadline:
            return True
        
        # High priority dengan progress rendah dan deadline dekat
        time_remaining = deadline - now
        if (priority == "high" and 
            progress < 50 and 
            time_remaining < 86400):  # 24 jam
            return True
        
        # Progress sangat rendah dengan deadline sangat dekat
        if progress < 25 and time_remaining < 43200:  # 12 jam
            return True
        
        return False
        
    except Exception as e:
        print(f"Error checking urgent reminder: {e}")
        return False

# Export fungsi utama
__all__ = [
    'check_deadlines',
    'send_daily_summary', 
    'check_and_notify_managers',
    'format_duration',
    'get_next_reminder_time',
    'should_send_urgent_reminder'
]
