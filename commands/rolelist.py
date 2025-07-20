import discord
from discord import app_commands, Interaction, ButtonStyle
from discord.ui import Button, View
from discord.ext import commands
from utils.database import get_user_display_name, load_registered_roles
import os

class RoleListView(View):
    def __init__(self, registered_roles, guild, current_page=0, per_page=5):
        super().__init__(timeout=300)
        self.registered_roles = registered_roles
        self.guild = guild
        self.current_page = current_page
        self.per_page = per_page
        self.max_pages = max(1, (len(registered_roles) + per_page - 1) // per_page)
        
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
        
        # Add refresh button
        refresh_button = Button(label="🔄 Refresh", style=ButtonStyle.primary)
        refresh_button.callback = self.refresh_data
        self.add_item(refresh_button)
        
        # Add manage roles button
        manage_button = Button(label="⚙️ Manage Roles", style=ButtonStyle.secondary)
        manage_button.callback = self.manage_roles
        self.add_item(manage_button)
    
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
        try:
            # Reload registered roles from database
            self.registered_roles = load_registered_roles()
            self.max_pages = max(1, (len(self.registered_roles) + self.per_page - 1) // self.per_page)
            
            # Reset to first page if current page is out of bounds
            if self.current_page >= self.max_pages:
                self.current_page = 0
            
            self.update_buttons()
            embed = self.create_embed()
            await interaction.response.edit_message(embed=embed, view=self)
            
        except Exception as e:
            await interaction.response.send_message(f"Error saat refresh: {str(e)}", ephemeral=True)
    
    async def manage_roles(self, interaction: Interaction):
        await interaction.response.send_message(
            "💡 **Tip Manajemen Role:**\n"
            "• Gunakan `/regisrole <role>` untuk menambah role baru\n"
            "• Gunakan `/regisrole` tanpa parameter untuk mengelola role\n"
            "• Role yang terdaftar dapat diberi tugas menggunakan `/ask`",
            ephemeral=True
        )
    
    def create_embed(self):
        embed = discord.Embed(
            title="🎭 Daftar Role Terdaftar",
            description="Role yang dapat diberi tugas dalam sistem task manager",
            color=0x3498db
        )
        
        if not self.registered_roles:
            embed.description = "Belum ada role yang terdaftar."
            embed.color = 0x95a5a6
            embed.add_field(
                name="💡 Cara Mendaftar Role",
                value="Gunakan command `/regisrole <role>` untuk mendaftarkan role baru.",
                inline=False
            )
            return embed
        
        # Calculate current page data
        start_idx = self.current_page * self.per_page
        end_idx = min(start_idx + self.per_page, len(self.registered_roles))
        current_page_roles = self.registered_roles[start_idx:end_idx]
        
        # Statistics
        total_members = 0
        valid_roles = 0
        invalid_roles = 0
        
        role_info = ""
        for i, role_id in enumerate(current_page_roles, start_idx + 1):
            role = self.guild.get_role(role_id)
            if role:
                member_count = len(role.members)
                total_members += member_count
                valid_roles += 1
                
                # Role color indicator
                color_indicator = "🔵" if role.color == discord.Color.default() else "🎨"
                
                # Permission level indicator
                perm_indicator = "👑" if role.permissions.administrator else "👤"
                
                # Member activity indicator
                if member_count == 0:
                    activity_indicator = "😴"
                elif member_count <= 5:
                    activity_indicator = "👥"
                else:
                    activity_indicator = "👫"
                
                role_info += (
                    f"**{i}.** {color_indicator} **{role.name}** {perm_indicator}\n"
                    f"   └ {role.mention} • {activity_indicator} **{member_count}** anggota\n"
                    f"   └ Posisi: #{role.position} • ID: `{role.id}`\n\n"
                )
            else:
                invalid_roles += 1
                role_info += (
                    f"**{i}.** ❌ **Role Tidak Ditemukan**\n"
                    f"   └ ID: `{role_id}` (mungkin sudah dihapus)\n\n"
                )
        
        embed.add_field(name="📋 Daftar Role", value=role_info or "Tidak ada role", inline=False)
        
        # Add member list for current page roles with nicknames
        if valid_roles > 0:
            member_info = ""
            for role_id in current_page_roles:
                role = self.guild.get_role(role_id)
                if role and role.members:
                    member_info += f"**{role.name}:**\n"
                    member_list = []
                    for member in role.members[:10]:  # Limit to 10 members per role
                        status_emoji = "🟢" if member.status == discord.Status.online else "⚫"
                        # Use nickname if available
                        display_name = get_user_display_name(str(member.id), member.display_name)
                        member_list.append(f"{status_emoji} {display_name}")
                    
                    if len(role.members) > 10:
                        member_list.append(f"... dan {len(role.members) - 10} lainnya")
                    
                    member_info += "   └ " + ", ".join(member_list) + "\n\n"
            
            if member_info:
                # Truncate if too long
                if len(member_info) > 1000:
                    member_info = member_info[:997] + "..."
                
                embed.add_field(name="👥 Anggota Role", value=member_info, inline=False)
        
        # Add statistics
        stats_text = (
            f"🎭 **Role Terdaftar:** {len(self.registered_roles)}\n"
            f"✅ **Valid:** {valid_roles}\n"
            f"❌ **Invalid:** {invalid_roles}\n"
            f"👥 **Total Anggota:** {total_members}"
        )
        embed.add_field(name="📊 Statistik", value=stats_text, inline=True)
        
        # Add legend
        legend_text = (
            "🔵 Default Color\n"
            "🎨 Custom Color\n"
            "👑 Administrator\n"
            "👤 Regular Role\n"
            "🟢 Online\n"
            "⚫ Offline/Away"
        )
        embed.add_field(name="📝 Keterangan", value=legend_text, inline=True)
        
        embed.set_footer(text=f"Halaman {self.current_page + 1} dari {self.max_pages} • {self.per_page} role per halaman")
        
        return embed

@app_commands.command(name="rolelist", description="Lihat daftar role terdaftar dan anggotanya")
@app_commands.checks.has_role("task manager")
async def rolelist(interaction: Interaction):
    try:
        # Load registered roles from database
        registered_roles = load_registered_roles()
        
        if not registered_roles:
            embed = discord.Embed(
                title="🎭 Daftar Role Terdaftar",
                description="Belum ada role yang terdaftar dalam sistem task manager.",
                color=0x95a5a6
            )
            
            embed.add_field(
                name="💡 Cara Mendaftar Role",
                value=(
                    "1. Gunakan `/regisrole <role>` untuk mendaftarkan role\n"
                    "2. Role yang terdaftar dapat diberi tugas dengan `/ask`\n"
                    "3. Anggota role dapat melihat tugas dengan `/myjob`"
                ),
                inline=False
            )
            
            embed.add_field(
                name="📋 Fitur Role System",
                value=(
                    "• **Task Assignment**: Beri tugas ke anggota role\n"
                    "• **Progress Tracking**: Monitor kemajuan tugas\n"
                    "• **Automatic Reminders**: Pengingat deadline otomatis\n"
                    "• **Activity Logging**: Riwayat aktivitas lengkap\n"
                    "• **Nickname Support**: Tampilan nama yang dipersonalisasi"
                ),
                inline=False
            )
            
            embed.set_footer(text="Gunakan /regisrole untuk memulai mendaftarkan role")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Create view with pagination
        view = RoleListView(registered_roles, interaction.guild)
        embed = view.create_embed()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        
    except Exception as e:
        embed = discord.Embed(
            title="❌ Error",
            description=f"Terjadi kesalahan: {str(e)}",
            color=0xe74c3c
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    bot.tree.add_command(rolelist)

