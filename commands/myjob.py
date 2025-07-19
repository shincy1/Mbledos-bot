import discord
from discord import app_commands, Interaction, ButtonStyle
from discord.ui import Button, View, Modal, TextInput
from discord.ext import commands
from utils.database import load_tasks, save_tasks
from datetime import datetime

class ProgressModal(Modal):
    def __init__(self, task_id, user_id, *args, **kwargs):
        super().__init__(title="Update Progress", *args, **kwargs)
        self.task_id = task_id
        self.user_id = user_id
        self.add_item(TextInput(label="Progress (0-100)", placeholder="Contoh: 80"))

    async def on_submit(self, interaction: Interaction):
        try:
            progress = int(self.children[0].value)
            if progress < 0 or progress > 100:
                await interaction.response.send_message("Progress harus antara 0-100!", ephemeral=True)
                return
                
            tasks = load_tasks()
            tasks[self.user_id][self.task_id]["progress"] = progress
            if progress == 100:
                tasks[self.user_id][self.task_id]["status"] = "done"
            save_tasks(tasks)
            await interaction.response.send_message("Progress diperbarui!", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("Masukkan angka yang valid!", ephemeral=True)

class TaskView(View):
    def __init__(self, tasks, user_id, current_page=0):
        super().__init__(timeout=300)
        self.tasks = list(tasks.items())
        self.user_id = user_id
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
        
        # Add progress update button
        if self.tasks:
            progress_button = Button(label="Update Progress", style=ButtonStyle.primary)
            progress_button.callback = self.update_progress
            self.add_item(progress_button)
    
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
    
    async def update_progress(self, interaction: Interaction):
        if self.tasks:
            task_id, task = self.tasks[self.current_page]
            modal = ProgressModal(task_id=task_id, user_id=self.user_id)
            await interaction.response.send_modal(modal)
    
    def create_embed(self):
        if not self.tasks:
            embed = discord.Embed(title="📋 Tugas Saya", description="Tidak ada tugas.", color=0x3498db)
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
            color=0x3498db
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
        
        embed.set_footer(text=f"Halaman {self.current_page + 1} dari {self.max_pages}")
        
        return embed

@app_commands.command(name="myjob", description="Lihat tugas Anda")
async def myjob(interaction: Interaction):
    tasks = load_tasks()
    user_id = str(interaction.user.id)
    
    if user_id not in tasks or not tasks[user_id]:
        embed = discord.Embed(
            title="📋 Tugas Saya", 
            description="Anda tidak memiliki tugas.", 
            color=0x95a5a6
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    view = TaskView(tasks[user_id], user_id)
    embed = view.create_embed()
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

async def setup(bot):
    bot.tree.add_command(myjob)
