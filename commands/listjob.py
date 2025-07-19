import discord
from discord import app_commands, Interaction, ButtonStyle
from discord.ui import Button, View
from discord.ext import commands
from utils.database import load_tasks, save_tasks, log_activity
from datetime import datetime

class TaskManagerView(View):
    def __init__(self, tasks, user_id, target_user, current_page=0):
        super().__init__(timeout=300)
        self.tasks = list(tasks.items())
        self.user_id = user_id
        self.target_user = target_user
        self.current_page = current_page
        self.max_pages = len(self.tasks)
        
        # Update button states
        self.update_buttons()
    
    def update_buttons(self):
        # Clear existing items
        
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
            
            # Only show approve button if task is done (100% progress)
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
        
        # Log activity
        log_activity(interaction.user, f"approve task '{task.get('title', 'Untitled')}' for {self.target_user.display_name}")
        
        # Update the view
        self.tasks[self.current_page] = (task_id, tasks[self.user_id][task_id])
        self.update_buttons()
        embed = self.create_embed()
        
        await interaction.response.edit_message(embed=embed, view=self)
        
        # Send notification to user
        try:
            await self.target_user.send(f"🎉 Tugas Anda '{task.get('title', 'Untitled')}' telah disetujui!")
        except:
            pass  # Ignore if can't send DM
    
    def create_embed(self):
        if not self.tasks:
            embed = discord.Embed(
                title=f"📋 Tugas {self.target_user.display_name}", 
                description="Tidak ada tugas.", 
                color=0x3498db
            )
            return embed
        
        task_id, task = self.tasks[self.current_page]
        
        # Status emoji
        status_emoji = {
            "pending": "⏳",
            "done": "✅", 
            "approved": "🎉"
        }
        
        # Priority emoji
        priority_emoji = {
            "low": "🟢",
            "medium": "🟡", 
            "high": "🔴"
        }
        
        # Status color
        status_colors = {
            "pending": 0xf39c12,  # Orange
            "done": 0x2ecc71,     # Green
            "approved": 0x9b59b6  # Purple
        }
        
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
            description=f"**Pengguna:** {self.target_user.mention}",
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
        
        embed.set_footer(text=f"Halaman {self.current_page + 1} dari {self.max_pages}")
        embed.set_thumbnail(url=self.target_user.display_avatar.url)
        
        return embed

@app_commands.command(name="listjob", description="Lihat tugas pengguna")
@app_commands.checks.has_role("task manager")
async def listjob(interaction: Interaction, target_user: discord.Member):
    tasks = load_tasks()
    user_id = str(target_user.id)
    
    if user_id not in tasks or not tasks[user_id]:
        embed = discord.Embed(
            title=f"📋 Tugas {target_user.display_name}", 
            description=f"{target_user.mention} tidak memiliki tugas.", 
            color=0x95a5a6
        )
        embed.set_thumbnail(url=target_user.display_avatar.url)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    view = TaskManagerView(tasks[user_id], user_id, target_user)
    embed = view.create_embed()
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

async def setup(bot):
    bot.tree.add_command(listjob)
