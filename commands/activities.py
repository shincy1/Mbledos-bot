import discord
from discord import app_commands, Interaction, ButtonStyle
from discord.ui import Button, View
from discord.ext import commands
import json
import os
from datetime import datetime
from utils.database import load_activities, save_activities, ensure_data_directory

class ActivityView(View):
    def __init__(self, logs, current_page=0, per_page=5):
        super().__init__(timeout=300)
        self.logs = logs
        self.current_page = current_page
        self.per_page = per_page
        self.max_pages = max(1, (len(logs) + per_page - 1) // per_page)
        
        # Update button states
        self.update_buttons()
    
    def update_buttons(self):
        # Clear existing items
        self.clear_items()
        
        # Add navigation buttons only if there are multiple pages
        if self.max_pages > 1:
            prev_button = Button(label="◀ Previous", style=ButtonStyle.secondary, disabled=self.current_page == 0)
            prev_button.callback = self.previous_page
            self.add_item(prev_button)
            
            next_button = Button(label="Next ▶", style=ButtonStyle.secondary, disabled=self.current_page >= self.max_pages - 1)
            next_button.callback = self.next_page
            self.add_item(next_button)
        
        # Add refresh button
        refresh_button = Button(label="🔄 Refresh", style=ButtonStyle.primary)
        refresh_button.callback = self.refresh_activities
        self.add_item(refresh_button)
        
        # Add clear logs button (dangerous action)
        clear_button = Button(label="🗑️ Clear All", style=ButtonStyle.danger)
        clear_button.callback = self.clear_logs
        self.add_item(clear_button)
    
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
    
    async def refresh_activities(self, interaction: Interaction):
        try:
            # Reload logs menggunakan fungsi dari database.py
            self.logs = load_activities()
            
            # Recalculate max pages
            self.max_pages = max(1, (len(self.logs) + self.per_page - 1) // self.per_page)
            
            # Reset to first page if current page is out of bounds
            if self.current_page >= self.max_pages:
                self.current_page = 0
            
            self.update_buttons()
            embed = self.create_embed()
            await interaction.response.edit_message(embed=embed, view=self)
            
        except Exception as e:
            print(f"Error in refresh_activities: {e}")
            embed = discord.Embed(
                title="❌ Error",
                description="Terjadi kesalahan saat refresh. File telah diperbaiki.",
                color=0xe74c3c
            )
            
            # Reset activities file
            try:
                from utils.database import reset_activities_file
                reset_activities_file()
                self.logs = []
                embed.description = "File riwayat aktivitas telah diperbaiki."
                embed.color = 0x2ecc71
            except Exception as reset_error:
                print(f"Error resetting activities file: {reset_error}")
                embed.description = f"Gagal memperbaiki file: {str(reset_error)}"
            
            await interaction.response.edit_message(embed=embed, view=None)
    
    async def clear_logs(self, interaction: Interaction):
        # Create confirmation view
        confirm_view = ConfirmClearView()
        embed = discord.Embed(
            title="⚠️ Konfirmasi Hapus",
            description="Apakah Anda yakin ingin menghapus semua riwayat aktivitas?\n\n**Tindakan ini tidak dapat dibatalkan!**",
            color=0xe74c3c
        )
        await interaction.response.send_message(embed=embed, view=confirm_view, ephemeral=True)
    
    def create_embed(self):
        if not self.logs:
            embed = discord.Embed(
                title="📜 Riwayat Aktivitas",
                description="Belum ada aktivitas tercatat.",
                color=0x95a5a6
            )
            return embed
        
        # Calculate start and end indices for current page
        start_idx = self.current_page * self.per_page
        end_idx = min(start_idx + self.per_page, len(self.logs))
        
        # Get logs for current page (reverse order to show newest first)
        current_logs = list(reversed(self.logs))[start_idx:end_idx]
        
        embed = discord.Embed(
            title="📜 Riwayat Aktivitas",
            description=f"Menampilkan aktivitas terbaru",
            color=0x3498db
        )
        
        # Add activity entries
        activity_text = ""
        for i, log in enumerate(current_logs, 1):
            timestamp = log.get('timestamp', 'Unknown time')
            user = log.get('user', 'Unknown user')
            action = log.get('action', 'Unknown action')
            
            # Parse timestamp for better formatting
            try:
                dt = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
                formatted_time = dt.strftime("%d/%m %H:%M")
            except:
                formatted_time = timestamp
            
            # Add emoji based on action type
            action_emoji = "📝"
            if "assign" in action.lower():
                action_emoji = "📋"
            elif "approve" in action.lower():
                action_emoji = "✅"
            elif "complete" in action.lower():
                action_emoji = "🎯"
            elif "update" in action.lower():
                action_emoji = "🔄"
            
            activity_text += f"{action_emoji} **{formatted_time}** - {user}\n└ {action}\n\n"
        
        if activity_text:
            embed.description = activity_text
        else:
            embed.description = "Tidak ada aktivitas pada halaman ini."
        
        # Add statistics
        total_activities = len(self.logs)
        embed.add_field(
            name="📊 Statistik",
            value=f"Total aktivitas: **{total_activities}**",
            inline=False
        )
        
        embed.set_footer(
            text=f"Halaman {self.current_page + 1} dari {self.max_pages} • {self.per_page} aktivitas per halaman"
        )
        
        return embed

class ConfirmClearView(View):
    def __init__(self):
        super().__init__(timeout=60)
    
    @discord.ui.button(label="✅ Ya, Hapus Semua", style=ButtonStyle.danger)
    async def confirm_clear(self, interaction: Interaction, button: Button):
        try:
            # Clear activities menggunakan fungsi dari database.py
            result = save_activities([])
            
            if result:
                embed = discord.Embed(
                    title="✅ Berhasil",
                    description="Semua riwayat aktivitas telah dihapus.",
                    color=0x2ecc71
                )
            else:
                embed = discord.Embed(
                    title="❌ Error",
                    description="Gagal menghapus riwayat aktivitas.",
                    color=0xe74c3c
                )
            
            await interaction.response.edit_message(embed=embed, view=None)
            
        except Exception as e:
            print(f"Error clearing activities: {e}")
            embed = discord.Embed(
                title="❌ Error",
                description=f"Gagal menghapus riwayat aktivitas: {str(e)}",
                color=0xe74c3c
            )
            await interaction.response.edit_message(embed=embed, view=None)
    
    @discord.ui.button(label="❌ Batal", style=ButtonStyle.secondary)
    async def cancel_clear(self, interaction: Interaction, button: Button):
        embed = discord.Embed(
            title="❌ Dibatalkan",
            description="Penghapusan riwayat aktivitas dibatalkan.",
            color=0x95a5a6
        )
        await interaction.response.edit_message(embed=embed, view=None)

@app_commands.command(name="activities", description="Lihat riwayat aktivitas")
@app_commands.checks.has_role("task manager")
async def activities(interaction: Interaction):
    try:
        # Load activities menggunakan fungsi dari database.py
        logs = load_activities()
        
        if not logs:
            embed = discord.Embed(
                title="📜 Riwayat Aktivitas",
                description="Belum ada aktivitas tercatat.",
                color=0x95a5a6
            )
            embed.set_footer(text="Aktivitas akan muncul setelah ada tindakan yang dilakukan.")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Create view with pagination
        view = ActivityView(logs)
        embed = view.create_embed()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        
    except Exception as e:
        print(f"Unexpected error in activities command: {e}")
        
        # Coba reset file activities
        try:
            from utils.database import reset_activities_file
            reset_activities_file()
            
            embed = discord.Embed(
                title="✅ File Diperbaiki",
                description="File riwayat aktivitas telah diperbaiki. Silakan coba lagi.",
                color=0x2ecc71
            )
            embed.add_field(
                name="ℹ️ Info",
                value="File yang rusak telah direset. Aktivitas baru akan mulai tercatat.",
                inline=False
            )
        except:
            embed = discord.Embed(
                title="❌ Error",
                description=f"Terjadi kesalahan: {str(e)}",
                color=0xe74c3c
            )
            embed.add_field(
                name="💡 Solusi",
                value="Hubungi administrator untuk memperbaiki file aktivitas.",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    bot.tree.add_command(activities)
