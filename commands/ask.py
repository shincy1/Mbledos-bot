import discord
from discord import app_commands, Interaction, ButtonStyle
from discord.ui import Button, View, Modal, TextInput
from discord.ext import commands
from utils.database import load_tasks, save_tasks, log_activity
from datetime import datetime, timedelta

class AskModal(Modal):
    def __init__(self, target_user, *args, **kwargs):
        super().__init__(title="Buat Tugas Baru", *args, **kwargs)
        self.target_user = target_user
        
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
        
        self.add_item(TextInput(
            label="Prioritas (low/medium/high)", 
            placeholder="Pilih: low, medium, atau high",
            max_length=6,
            default="medium"
        ))

    async def on_submit(self, interaction: Interaction):
        try:
            title = self.children[0].value.strip()
            description = self.children[1].value.strip()
            deadline_str = self.children[2].value.strip()
            priority = self.children[3].value.strip().lower()
            
            # Validasi input
            if not title:
                await interaction.response.send_message("Judul tugas tidak boleh kosong!", ephemeral=True)
                return
            
            if not description:
                await interaction.response.send_message("Deskripsi tugas tidak boleh kosong!", ephemeral=True)
                return
            
            # Validasi prioritas
            if priority not in ["low", "medium", "high"]:
                await interaction.response.send_message("Prioritas harus 'low', 'medium', atau 'high'!", ephemeral=True)
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
                "priority": priority,
                "deadline": deadline_timestamp,
                "progress": 0,
                "created_at": created_at,
                "assigned_by": str(interaction.user.id)
            }
            
            # Simpan tasks
            save_tasks(tasks)
            
            # Log activity
            log_activity(interaction.user, f"assigned task '{title}' to {self.target_user.display_name}")
            
            # Buat embed konfirmasi
            priority_emoji = {
                "low": "🟢",
                "medium": "🟡", 
                "high": "🔴"
            }
            
            embed = discord.Embed(
                title="✅ Tugas Berhasil Dibuat",
                description=f"Tugas telah diberikan kepada {self.target_user.mention}",
                color=0x2ecc71
            )
            
            embed.add_field(name="📝 Judul", value=title, inline=False)
            embed.add_field(name="📄 Deskripsi", value=description[:100] + "..." if len(description) > 100 else description, inline=False)
            embed.add_field(name="⚡ Prioritas", value=f"{priority_emoji[priority]} {priority.title()}", inline=True)
            embed.add_field(name="⏰ Deadline", value=deadline_dt.strftime("%d/%m/%Y %H:%M"), inline=True)
            embed.add_field(name="🆔 Task ID", value=f"#{task_id}", inline=True)
            
            embed.set_thumbnail(url=self.target_user.display_avatar.url)
            embed.set_footer(text=f"Dibuat oleh {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
            # Kirim notifikasi ke target user
            try:
                user_embed = discord.Embed(
                    title="📋 Tugas Baru Diterima!",
                    description=f"Anda mendapat tugas baru dari {interaction.user.display_name}",
                    color=0x3498db
                )
                
                user_embed.add_field(name="📝 Judul", value=title, inline=False)
                user_embed.add_field(name="📄 Deskripsi", value=description, inline=False)
                user_embed.add_field(name="⚡ Prioritas", value=f"{priority_emoji[priority]} {priority.title()}", inline=True)
                user_embed.add_field(name="⏰ Deadline", value=deadline_dt.strftime("%d/%m/%Y %H:%M"), inline=True)
                user_embed.add_field(name="🆔 Task ID", value=f"#{task_id}", inline=True)
                
                user_embed.set_footer(text="Gunakan /myjob untuk melihat semua tugas Anda")
                
                await self.target_user.send(embed=user_embed)
            except discord.Forbidden:
                # Jika tidak bisa kirim DM, beri tahu di response
                await interaction.followup.send(
                    f"⚠️ Tidak dapat mengirim notifikasi DM ke {self.target_user.mention}. "
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
    
    modal = AskModal(target_user=target_user)
    await interaction.response.send_modal(modal)

async def setup(bot):
    bot.tree.add_command(ask)
