import discord
from discord import app_commands, Interaction, ButtonStyle
from discord.ui import Button, View, Modal, TextInput, Select
from discord.ext import commands
from utils.database import load_tasks, save_tasks, log_activity, get_user_display_name
from datetime import datetime, timedelta

class PrioritySelect(Select):
    def __init__(self):
        options = [
            discord.SelectOption(
                label="Low Priority",
                description="Tugas dengan prioritas rendah",
                emoji="🟢",
                value="low"
            ),
            discord.SelectOption(
                label="Medium Priority", 
                description="Tugas dengan prioritas sedang",
                emoji="🟡",
                value="medium"
            ),
            discord.SelectOption(
                label="High Priority",
                description="Tugas dengan prioritas tinggi", 
                emoji="🔴",
                value="high"
            )
        ]
        
        super().__init__(
            placeholder="Pilih prioritas tugas...",
            min_values=1,
            max_values=1,
            options=options
        )
    
    async def callback(self, interaction: Interaction):
        # Update the view's selected priority
        self.view.selected_priority = self.values[0]
        
        # Update the embed to show selected priority
        embed = self.view.create_embed()
        await interaction.response.edit_message(embed=embed, view=self.view)

class AskView(View):
    def __init__(self, target_user):
        super().__init__(timeout=300)
        self.target_user = target_user
        self.selected_priority = None
        self.task_data = {}
        
        # Add priority dropdown
        self.priority_select = PrioritySelect()
        self.add_item(self.priority_select)
        
        # Add form button (initially disabled)
        self.form_button = Button(
            label="📝 Isi Detail Tugas",
            style=ButtonStyle.primary,
            disabled=True
        )
        self.form_button.callback = self.open_form
        self.add_item(self.form_button)
        
        # Add cancel button
        cancel_button = Button(
            label="❌ Batal",
            style=ButtonStyle.secondary
        )
        cancel_button.callback = self.cancel
        self.add_item(cancel_button)
    
    def create_embed(self):
        # Get display name for target user
        target_display_name = get_user_display_name(str(self.target_user.id), self.target_user.display_name)
        
        embed = discord.Embed(
            title="📋 Buat Tugas Baru",
            description=f"Membuat tugas untuk **{target_display_name}**",
            color=0x3498db
        )
        
        embed.add_field(
            name="👤 Target User",
            value=f"**{target_display_name}**\nDiscord: {self.target_user.display_name}",
            inline=True
        )
        
        if self.selected_priority:
            priority_emoji = {"low": "🟢", "medium": "🟡", "high": "🔴"}
            embed.add_field(
                name="⚡ Prioritas Terpilih",
                value=f"{priority_emoji[self.selected_priority]} {self.selected_priority.title()}",
                inline=True
            )
            
            # Enable form button when priority is selected
            self.form_button.disabled = False
            
            embed.add_field(
                name="📝 Langkah Selanjutnya",
                value="Klik tombol **Isi Detail Tugas** untuk melanjutkan",
                inline=False
            )
        else:
            embed.add_field(
                name="📝 Langkah 1",
                value="Pilih prioritas tugas menggunakan dropdown di atas",
                inline=False
            )
        
        embed.set_thumbnail(url=self.target_user.display_avatar.url)
        embed.set_footer(text="Timeout: 5 menit")
        
        return embed
    
    async def open_form(self, interaction: Interaction):
        if not self.selected_priority:
            await interaction.response.send_message("Pilih prioritas terlebih dahulu!", ephemeral=True)
            return
        
        modal = AskModal(self.target_user, self.selected_priority)
        await interaction.response.send_modal(modal)
    
    async def cancel(self, interaction: Interaction):
        embed = discord.Embed(
            title="❌ Dibatalkan",
            description="Pembuatan tugas dibatalkan.",
            color=0x95a5a6
        )
        await interaction.response.edit_message(embed=embed, view=None)

class AskModal(Modal):
    def __init__(self, target_user, priority, *args, **kwargs):
        super().__init__(title="Detail Tugas", *args, **kwargs)
        self.target_user = target_user
        self.priority = priority
        
        self.add_item(TextInput(
            label="Judul Tugas", 
            placeholder="Masukkan judul tugas...",
            max_length=100
        ))
        
        self.add_item(TextInput(
            label="Deskripsi Tugas", 
            style=discord.TextStyle.paragraph,
            placeholder="Jelaskan detail tugas yang harus dikerjakan...",
            max_length=1000
        ))
        
        self.add_item(TextInput(
            label="Deadline (format: DD/MM/YYYY HH:MM)", 
            placeholder="Contoh: 25/12/2024 15:30",
            max_length=16
        ))

    async def on_submit(self, interaction: Interaction):
        try:
            title = self.children[0].value.strip()
            description = self.children[1].value.strip()
            deadline_str = self.children[2].value.strip()
            
            # Validasi input
            if not title:
                await interaction.response.send_message("Judul tugas tidak boleh kosong!", ephemeral=True)
                return
            
            if not description:
                await interaction.response.send_message("Deskripsi tugas tidak boleh kosong!", ephemeral=True)
                return
            
            # Parse deadline
            try:
                deadline_dt = datetime.strptime(deadline_str, "%d/%m/%Y %H:%M")
                deadline_timestamp = deadline_dt.timestamp()
                
                # Cek apakah deadline sudah lewat
                if deadline_dt <= datetime.now():
                    await interaction.response.send_message("Deadline tidak boleh di masa lalu!", ephemeral=True)
                    return
                    
            except ValueError:
                await interaction.response.send_message("Format deadline salah! Gunakan: DD/MM/YYYY HH:MM\nContoh: 25/12/2024 15:30", ephemeral=True)
                return
            
            # Load tasks dan buat task baru
            created_at = datetime.now().timestamp()
            tasks = load_tasks()
            user_id = str(self.target_user.id)
            
            if user_id not in tasks:
                tasks[user_id] = {}
            
            # Generate task ID
            task_id = str(len(tasks[user_id]) + 1)
            
            # Buat task baru
            tasks[user_id][task_id] = {
                "title": title,
                "description": description,
                "status": "pending",
                "priority": self.priority,
                "deadline": deadline_timestamp,
                "progress": 0,
                "created_at": created_at,
                "assigned_by": str(interaction.user.id)
            }
            
            # Simpan tasks
            save_tasks(tasks)
            
            # Get display names for logging
            target_display_name = get_user_display_name(user_id, self.target_user.display_name)
            assigner_display_name = get_user_display_name(str(interaction.user.id), interaction.user.display_name)
            
            # Log activity
            log_activity(interaction.user, f"assigned task '{title}' to {target_display_name}")
            
            # Buat embed konfirmasi
            priority_emoji = {
                "low": "🟢",
                "medium": "🟡", 
                "high": "🔴"
            }
            
            embed = discord.Embed(
                title="✅ Tugas Berhasil Dibuat",
                description=f"Tugas telah diberikan kepada **{target_display_name}**",
                color=0x2ecc71
            )
            
            embed.add_field(name="📝 Judul", value=title, inline=False)
            embed.add_field(name="📄 Deskripsi", value=description[:100] + "..." if len(description) > 100 else description, inline=False)
            embed.add_field(name="⚡ Prioritas", value=f"{priority_emoji[self.priority]} {self.priority.title()}", inline=True)
            embed.add_field(name="⏰ Deadline", value=deadline_dt.strftime("%d/%m/%Y %H:%M"), inline=True)
            embed.add_field(name="🆔 Task ID", value=f"#{task_id}", inline=True)
            
            embed.add_field(
                name="👤 Penerima Tugas",
                value=f"**{target_display_name}**\nDiscord: {self.target_user.display_name}",
                inline=True
            )
            
            embed.set_thumbnail(url=self.target_user.display_avatar.url)
            embed.set_footer(text=f"Dibuat oleh {assigner_display_name}", icon_url=interaction.user.display_avatar.url)
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
            # Kirim notifikasi ke target user
            try:
                user_embed = discord.Embed(
                    title="📋 Tugas Baru Diterima!",
                    description=f"Anda mendapat tugas baru dari **{assigner_display_name}**",
                    color=0x3498db
                )
                
                user_embed.add_field(name="📝 Judul", value=title, inline=False)
                user_embed.add_field(name="📄 Deskripsi", value=description, inline=False)
                user_embed.add_field(name="⚡ Prioritas", value=f"{priority_emoji[self.priority]} {self.priority.title()}", inline=True)
                user_embed.add_field(name="⏰ Deadline", value=deadline_dt.strftime("%d/%m/%Y %H:%M"), inline=True)
                user_embed.add_field(name="🆔 Task ID", value=f"#{task_id}", inline=True)
                
                user_embed.add_field(
                    name="👤 Pemberi Tugas",
                    value=f"**{assigner_display_name}**\nDiscord: {interaction.user.display_name}",
                    inline=False
                )
                
                user_embed.set_footer(text="Gunakan /myjob untuk melihat semua tugas Anda")
                
                await self.target_user.send(embed=user_embed)
            except discord.Forbidden:
                # Jika tidak bisa kirim DM, beri tahu di response
                await interaction.followup.send(
                    f"⚠️ Tidak dapat mengirim notifikasi DM ke **{target_display_name}**. "
                    f"Pastikan mereka dapat menerima pesan langsung.", 
                    ephemeral=True
                )
            except Exception as e:
                print(f"Error sending DM notification: {e}")
                
        except Exception as e:
            print(f"Error in AskModal.on_submit: {e}")
            await interaction.response.send_message("Terjadi kesalahan saat membuat tugas. Silakan coba lagi.", ephemeral=True)

@app_commands.command(name="ask", description="Beri tugas ke pengguna")
@app_commands.checks.has_role("task manager")
async def ask(interaction: Interaction, target_user: discord.Member):
    # Cek apakah target user adalah bot
    if target_user.bot:
        await interaction.response.send_message("Tidak dapat memberikan tugas kepada bot!", ephemeral=True)
        return
    
    # Cek apakah target user adalah diri sendiri
    if target_user.id == interaction.user.id:
        await interaction.response.send_message("Tidak dapat memberikan tugas kepada diri sendiri!", ephemeral=True)
        return
    
    # Create view with priority selection
    view = AskView(target_user)
    embed = view.create_embed()
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

async def setup(bot):
    bot.tree.add_command(ask)
