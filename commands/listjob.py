import discord
from discord import app_commands, Interaction, ButtonStyle
from discord.ui import Button, View, Select
from discord.ext import commands
from utils.database import load_tasks, save_tasks, log_activity, get_user_display_name, load_registered_roles
from datetime import datetime
import json
import os

class UserSelectDropdown(Select):
    def __init__(self, users_with_tasks, guild):
        self.users_with_tasks = users_with_tasks
        self.guild = guild
        
        options = []
        for user_data in users_with_tasks[:25]:  # Discord limit 25 options
            user = guild.get_member(user_data['user_id'])
            if user:
                task_count = user_data['task_count']
                status_emoji = "📋" if task_count > 0 else "😴"
                
                # Get display name (nickname if available)
                display_name = get_user_display_name(str(user.id), user.display_name)
                
                label = f"{display_name} ({task_count} tugas)" if task_count > 0 else f"{display_name} (nganggur)"
                options.append(discord.SelectOption(
                    label=label[:100],  # Discord limit
                    description=f"Lihat detail tugas {display_name}",
                    value=str(user_data['user_id']),
                    emoji=status_emoji
                ))
        
        super().__init__(
            placeholder="Pilih pengguna untuk melihat detail tugas...",
            options=options,
            min_values=1,
            max_values=1
        )
    
    async def callback(self, interaction: Interaction):
        selected_user_id = int(self.values[0])
        user = self.guild.get_member(selected_user_id)
        
        if not user:
            await interaction.response.send_message("Pengguna tidak ditemukan!", ephemeral=True)
            return
        
        # Load tasks for selected user
        tasks = load_tasks()
        user_tasks = tasks.get(str(selected_user_id), {})
        
        display_name = get_user_display_name(str(user.id), user.display_name)
        
        if not user_tasks:
            embed = discord.Embed(
                title=f"📋 Tugas {display_name}",
                description=f"**{display_name}** tidak memiliki tugas.",
                color=0x95a5a6
            )
            embed.add_field(
                name="ℹ️ Info",
                value=f"Discord: {user.display_name}",
                inline=False
            )
            embed.set_thumbnail(url=user.display_avatar.url)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Create specific user task view
        view = TaskManagerView(user_tasks, str(selected_user_id), user)
        embed = view.create_embed()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

class AllUsersView(View):
    def __init__(self, users_with_tasks, guild, current_page=0, per_page=7):
        super().__init__(timeout=300)
        self.users_with_tasks = users_with_tasks
        self.guild = guild
        self.current_page = current_page
        self.per_page = per_page
        self.max_pages = max(1, (len(users_with_tasks) + per_page - 1) // per_page)
        
        self.update_buttons()
    
    def update_buttons(self):
        self.clear_items()
        
        # Add navigation buttons if multiple pages
        if self.max_pages > 1:
            prev_button = Button(label="◀ Previous", style=ButtonStyle.secondary, disabled=self.current_page == 0)
            prev_button.callback = self.previous_page
            self.add_item(prev_button)
            
            next_button = Button(label="Next ▶", style=ButtonStyle.secondary, disabled=self.current_page >= self.max_pages - 1)
            next_button.callback = self.next_page
            self.add_item(next_button)
        
        # Add user selection dropdown
        start_idx = self.current_page * self.per_page
        end_idx = min(start_idx + self.per_page, len(self.users_with_tasks))
        current_page_users = self.users_with_tasks[start_idx:end_idx]
        
        if current_page_users:
            dropdown = UserSelectDropdown(current_page_users, self.guild)
            self.add_item(dropdown)
        
        # Add refresh button
        refresh_button = Button(label="🔄 Refresh", style=ButtonStyle.primary)
        refresh_button.callback = self.refresh_data
        self.add_item(refresh_button)
    
    async def previous_page(self, interaction: Interaction):
        if self.current_page > 0:
            self.current_page -= 1
            self.update_buttons()
            embed = self.create_embed()
            await interaction.response.edit_message(embed=embed, view=self)
    
    async def next_page(self, interaction: Interaction):
        if self.current_page < self.max_pages - 1:
            self.current_page += 1
            self.update_buttons()
            embed = self.create_embed()
            await interaction.response.edit_message(embed=embed, view=self)
    
    async def refresh_data(self, interaction: Interaction):
        # Reload data
        self.users_with_tasks = get_all_registered_users_with_tasks(self.guild)
        self.max_pages = max(1, (len(self.users_with_tasks) + self.per_page - 1) // self.per_page)
        
        # Reset to first page if current page is out of bounds
        if self.current_page >= self.max_pages:
            self.current_page = 0
        
        self.update_buttons()
        embed = self.create_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    def create_embed(self):
        embed = discord.Embed(
            title="📊 Ringkasan Tugas Semua Pengguna",
            description="Status tugas untuk semua anggota terdaftar hari ini",
            color=0x3498db
        )
        
        if not self.users_with_tasks:
            embed.description = "Tidak ada pengguna terdaftar yang ditemukan."
            embed.color = 0x95a5a6
            return embed
        
        # Calculate current page data
        start_idx = self.current_page * self.per_page
        end_idx = min(start_idx + self.per_page, len(self.users_with_tasks))
        current_page_users = self.users_with_tasks[start_idx:end_idx]
        
        # Create user list
        user_list = ""
        stats = {"total_users": 0, "active_users": 0, "idle_users": 0, "total_tasks": 0}
        
        for user_data in current_page_users:
            user = self.guild.get_member(user_data['user_id'])
            if user:
                task_count = user_data['task_count']
                pending_count = user_data['pending_count']
                done_count = user_data['done_count']
                overdue_count = user_data['overdue_count']
                
                # Get display name
                display_name = get_user_display_name(str(user.id), user.display_name)
                
                stats["total_users"] += 1
                stats["total_tasks"] += task_count
                
                if task_count > 0:
                    stats["active_users"] += 1
                    status_emoji = "📋"
                    
                    # Add warning indicators
                    indicators = []
                    if overdue_count > 0:
                        indicators.append(f"🚨{overdue_count}")
                    if pending_count > 0:
                        indicators.append(f"⏳{pending_count}")
                    if done_count > 0:
                        indicators.append(f"✅{done_count}")
                    
                    indicator_text = f" ({', '.join(indicators)})" if indicators else ""
                    user_list += f"{status_emoji} **{display_name}** **{task_count} tugas**{indicator_text}\n"
                else:
                    stats["idle_users"] += 1
                    user_list += f"😴 **{display_name}** *nganggur*\n"
        
        embed.add_field(name="👥 Daftar Pengguna", value=user_list or "Tidak ada pengguna", inline=False)
        
        # Add statistics
        stats_text = (
            f"👥 Total: **{stats['total_users']}** pengguna\n"
            f"📋 Aktif: **{stats['active_users']}** pengguna\n"
            f"😴 Nganggur: **{stats['idle_users']}** pengguna\n"
            f"📊 Total Tugas: **{stats['total_tasks']}**"
        )
        embed.add_field(name="📈 Statistik", value=stats_text, inline=True)
        
        # Add legend
        legend_text = (
            "🚨 Terlambat\n"
            "⏳ Pending\n"
            "✅ Selesai\n"
            "😴 Tidak ada tugas"
        )
        embed.add_field(name="📝 Keterangan", value=legend_text, inline=True)
        
        embed.set_footer(text=f"Halaman {self.current_page + 1} dari {self.max_pages} • {self.per_page} pengguna per halaman")
        
        return embed

class TaskManagerView(View):
    def __init__(self, tasks, user_id, target_user, current_page=0):
        super().__init__(timeout=300)
        self.tasks = list(tasks.items())
        self.user_id = user_id
        self.target_user = target_user
        self.current_page = current_page
        self.max_pages = len(self.tasks)
        
        self.update_buttons()
    
    def update_buttons(self):
        self.clear_items()
        
        # Add navigation buttons
        if self.max_pages > 1:
            prev_button = Button(label="◀ Previous", style=ButtonStyle.secondary, disabled=self.current_page == 0)
            prev_button.callback = self.previous_page
            self.add_item(prev_button)
            
            next_button = Button(label="Next ▶", style=ButtonStyle.secondary, disabled=self.current_page >= self.max_pages - 1)
            next_button.callback = self.next_page
            self.add_item(next_button)
        
        # Add approve button if task exists
        if self.tasks:
            task_id, task = self.tasks[self.current_page]
            
            if task.get("progress", 0) == 100 and task.get("status") == "done":
                approve_button = Button(label="✅ Approve Task", style=ButtonStyle.green)
                approve_button.callback = self.approve_task
                self.add_item(approve_button)
            elif task.get("status") == "approved":
                approved_button = Button(label="🎉 Already Approved", style=ButtonStyle.gray, disabled=True)
                self.add_item(approved_button)
            else:
                pending_button = Button(label="⏳ Waiting for Completion", style=ButtonStyle.gray, disabled=True)
                self.add_item(pending_button)
        
        # Back to overview button
        back_button = Button(label="🔙 Back to Overview", style=ButtonStyle.secondary)
        back_button.callback = self.back_to_overview
        self.add_item(back_button)
    
    async def previous_page(self, interaction: Interaction):
        if self.current_page > 0:
            self.current_page -= 1
            self.update_buttons()
            embed = self.create_embed()
            await interaction.response.edit_message(embed=embed, view=self)
    
    async def next_page(self, interaction: Interaction):
        if self.current_page < self.max_pages - 1:
            self.current_page += 1
            self.update_buttons()
            embed = self.create_embed()
            await interaction.response.edit_message(embed=embed, view=self)
    
    async def approve_task(self, interaction: Interaction):
        if not self.tasks:
            await interaction.response.send_message("Tidak ada tugas untuk disetujui.", ephemeral=True)
            return
            
        task_id, task = self.tasks[self.current_page]
        
        if task.get("progress", 0) != 100:
            await interaction.response.send_message("Progress harus 100% untuk menyetujui tugas.", ephemeral=True)
            return
        
        if task.get("status") == "approved":
            await interaction.response.send_message("Tugas sudah disetujui sebelumnya.", ephemeral=True)
            return
        
        # Update task status
        tasks = load_tasks()
        tasks[self.user_id][task_id]["status"] = "approved"
        save_tasks(tasks)
        
        # Get display names
        target_display_name = get_user_display_name(str(self.target_user.id), self.target_user.display_name)
        
        # Log activity
        log_activity(interaction.user, f"approved task '{task.get('title', 'Untitled')}' for {target_display_name}")
        
        # Update the view
        self.tasks[self.current_page] = (task_id, tasks[self.user_id][task_id])
        self.update_buttons()
        embed = self.create_embed()
        
        await interaction.response.edit_message(embed=embed, view=self)
        
        # Send notification to user
        try:
            await self.target_user.send(f"🎉 Tugas Anda '{task.get('title', 'Untitled')}' telah disetujui!")
        except:
            pass
    
    async def back_to_overview(self, interaction: Interaction):
        # Return to all users view
        users_with_tasks = get_all_registered_users_with_tasks(interaction.guild)
        view = AllUsersView(users_with_tasks, interaction.guild)
        embed = view.create_embed()
        await interaction.response.edit_message(embed=embed, view=view)
    
    def create_embed(self):
        if not self.tasks:
            display_name = get_user_display_name(str(self.target_user.id), self.target_user.display_name)
            embed = discord.Embed(
                title=f"📋 Tugas {display_name}", 
                description="Tidak ada tugas.", 
                color=0x3498db
            )
            return embed
        
        task_id, task = self.tasks[self.current_page]
        
        # Status emoji and colors
        status_emoji = {"pending": "⏳", "done": "✅", "approved": "🎉"}
        priority_emoji = {"low": "🟢", "medium": "🟡", "high": "🔴"}
        status_colors = {"pending": 0xf39c12, "done": 0x2ecc71, "approved": 0x9b59b6}
        
        # Get display name
        display_name = get_user_display_name(str(self.target_user.id), self.target_user.display_name)
        
        # Format deadline
        deadline_timestamp = task.get("deadline", 0)
        if deadline_timestamp:
            deadline_dt = datetime.fromtimestamp(deadline_timestamp)
            deadline_str = deadline_dt.strftime("%d/%m/%Y %H:%M")
            
            # Check if overdue
            now = datetime.now()
            if deadline_dt < now and task["status"] not in ["done", "approved"]:
                deadline_str += " ⚠️ **TERLAMBAT**"
        else:
            deadline_str = "Tidak ada deadline"
        
        embed = discord.Embed(
            title=f"📋 Tugas #{task_id}: {task.get('title', 'Untitled')}", 
            description=f"**Pengguna:** {display_name}",
            color=status_colors.get(task["status"], 0x3498db)
        )
        
        embed.add_field(
            name="📝 Deskripsi", 
            value=task.get('description', 'Tidak ada deskripsi'), 
            inline=False
        )
        
        embed.add_field(
            name="📊 Status", 
            value=f"{status_emoji.get(task['status'], '❓')} {task['status'].title()}", 
            inline=True
        )
        
        embed.add_field(
            name="⚡ Prioritas", 
            value=f"{priority_emoji.get(task['priority'], '⚪')} {task['priority'].title()}", 
            inline=True
        )
        
        embed.add_field(
            name="📈 Progress", 
            value=f"{task.get('progress', 0)}%", 
            inline=True
        )
        
        embed.add_field(
            name="⏰ Deadline", 
            value=deadline_str, 
            inline=False
        )
        
        # Created at
        created_timestamp = task.get("created_at", 0)
        if created_timestamp:
            created_dt = datetime.fromtimestamp(created_timestamp)
            created_str = created_dt.strftime("%d/%m/%Y %H:%M")
            embed.add_field(name="📅 Dibuat", value=created_str, inline=True)
        
        # Progress bar visualization
        progress = task.get('progress', 0)
        progress_bar = ""
        filled = int(progress / 10)
        for i in range(10):
            if i < filled:
                progress_bar += "█"
            else:
                progress_bar += "░"
        
        embed.add_field(
            name="📊 Progress Bar", 
            value=f"`{progress_bar}` {progress}%", 
            inline=False
        )
        
        # Add user info
        embed.add_field(
            name="👤 Info Pengguna",
            value=f"**Nama:** {display_name}\n**Discord:** {self.target_user.display_name}",
            inline=True
        )
        
        embed.set_footer(text=f"Halaman {self.current_page + 1} dari {self.max_pages}")
        embed.set_thumbnail(url=self.target_user.display_avatar.url)
        
        return embed

def get_all_registered_users_with_tasks(guild):
    """Get all registered users with their task counts"""
    try:
        # Load registered roles from database
        registered_roles = load_registered_roles()
        if not registered_roles:
            return []
        
        # Get all members with registered roles
        registered_users = set()
        for role_id in registered_roles:
            role = guild.get_role(role_id)
            if role:
                for member in role.members:
                    if not member.bot:  # Exclude bots
                        registered_users.add(member.id)
        
        # Load tasks
        tasks = load_tasks()
        current_time = datetime.now().timestamp()
        
        users_with_tasks = []
        for user_id in registered_users:
            user_tasks = tasks.get(str(user_id), {})
            
            # Count different types of tasks
            task_count = len(user_tasks)
            pending_count = 0
            done_count = 0
            approved_count = 0
            overdue_count = 0
            
            for task in user_tasks.values():
                status = task.get("status", "pending")
                deadline = task.get("deadline", 0)
                
                if status == "pending":
                    pending_count += 1
                    # Check if overdue
                    if deadline and current_time > deadline:
                        overdue_count += 1
                elif status == "done":
                    done_count += 1
                elif status == "approved":
                    approved_count += 1
            
            users_with_tasks.append({
                'user_id': user_id,
                'task_count': task_count,
                'pending_count': pending_count,
                'done_count': done_count,
                'approved_count': approved_count,
                'overdue_count': overdue_count
            })
        
        # Sort by task count (descending), then by overdue count (descending)
        users_with_tasks.sort(key=lambda x: (x['task_count'], x['overdue_count']), reverse=True)
        
        return users_with_tasks
        
    except Exception as e:
        print(f"Error getting registered users with tasks: {e}")
        return []
@app_commands.command(name="listjob", description="Lihat tugas pengguna (spesifik atau semua)")
@app_commands.checks.has_role("task manager")
async def listjob(interaction: Interaction, target_user: discord.Member = None):
    if target_user:
        # Specific user mode (original functionality)
        tasks = load_tasks()
        user_id = str(target_user.id)
        
        display_name = get_user_display_name(str(target_user.id), target_user.display_name)
        
        if user_id not in tasks or not tasks[user_id]:
            embed = discord.Embed(
                title=f"📋 Tugas {display_name}", 
                description=f"**{display_name}** tidak memiliki tugas.", 
                color=0x95a5a6
            )
            embed.add_field(
                name="ℹ️ Info",
                value=f"Discord: {target_user.display_name}",
                inline=False
            )
            embed.set_thumbnail(url=target_user.display_avatar.url)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        view = TaskManagerView(tasks[user_id], user_id, target_user)
        embed = view.create_embed()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    else:
        # All users mode (new functionality)
        users_with_tasks = get_all_registered_users_with_tasks(interaction.guild)
        
        if not users_with_tasks:
            embed = discord.Embed(
                title="📊 Ringkasan Tugas Semua Pengguna",
                description="Tidak ada pengguna terdaftar yang ditemukan.\n\nGunakan `/regisrole` untuk mendaftarkan role terlebih dahulu.",
                color=0x95a5a6
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        view = AllUsersView(users_with_tasks, interaction.guild)
        embed = view.create_embed()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

async def setup(bot):
    bot.tree.add_command(listjob)
