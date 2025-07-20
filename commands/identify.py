import discord
from discord import app_commands, Interaction, ButtonStyle
from discord.ui import Button, View, Modal, TextInput, Select
from discord.ext import commands
from utils.database import load_identities, save_identities, log_activity, load_registered_roles
import json
import os

class IdentityModal(Modal):
    def __init__(self, target_user, *args, **kwargs):
        super().__init__(title=f"Identitas untuk {target_user.display_name}", *args, **kwargs)
        self.target_user = target_user
        
        # Load existing identity if any
        identities = load_identities()
        existing_identity = identities.get(str(target_user.id), {})
        
        self.add_item(TextInput(
            label="Nama Lengkap",
            placeholder="Masukkan nama lengkap...",
            max_length=100,
            default=existing_identity.get('full_name', '')
        ))
        
        self.add_item(TextInput(
            label="Nama Panggilan",
            placeholder="Masukkan nama panggilan...",
            max_length=50,
            default=existing_identity.get('nickname', '')
        ))

    async def on_submit(self, interaction: Interaction):
        try:
            full_name = self.children[0].value.strip()
            nickname = self.children[1].value.strip()
            
            # Validasi input
            if not full_name:
                await interaction.response.send_message("Nama lengkap tidak boleh kosong!", ephemeral=True)
                return
            
            if not nickname:
                await interaction.response.send_message("Nama panggilan tidak boleh kosong!", ephemeral=True)
                return
            
            # Load identities
            identities = load_identities()
            
            # Check if nickname already exists for different user
            for user_id, identity in identities.items():
                if (identity.get('nickname', '').lower() == nickname.lower() and 
                    user_id != str(self.target_user.id)):
                    existing_user = interaction.guild.get_member(int(user_id))
                    existing_name = existing_user.display_name if existing_user else f"User {user_id}"
                    await interaction.response.send_message(
                        f"Nama panggilan '{nickname}' sudah digunakan oleh {existing_name}!", 
                        ephemeral=True
                    )
                    return
            
            # Save identity
            identities[str(self.target_user.id)] = {
                'full_name': full_name,
                'nickname': nickname,
                'discord_name': self.target_user.display_name,
                'updated_at': discord.utils.utcnow().isoformat(),
                'updated_by': str(interaction.user.id)
            }
            
            save_identities(identities)
            
            # Log activity
            log_activity(interaction.user, f"updated identity for {self.target_user.display_name}: {full_name} ({nickname})")
            
            # Create confirmation embed
            embed = discord.Embed(
                title="✅ Identitas Berhasil Disimpan",
                description=f"Identitas untuk {self.target_user.mention} telah diperbarui",
                color=0x2ecc71
            )
            
            embed.add_field(name="👤 Discord Name", value=self.target_user.display_name, inline=True)
            embed.add_field(name="📝 Nama Lengkap", value=full_name, inline=True)
            embed.add_field(name="🏷️ Nama Panggilan", value=nickname, inline=True)
            
            embed.set_thumbnail(url=self.target_user.display_avatar.url)
            embed.set_footer(text=f"Diperbarui oleh {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            print(f"Error in IdentityModal.on_submit: {e}")
            await interaction.response.send_message("Terjadi kesalahan saat menyimpan identitas. Silakan coba lagi.", ephemeral=True)

class IdentityListView(View):
    def __init__(self, identities_by_role, guild, current_page=0, per_page=10):
        super().__init__(timeout=300)
        self.identities_by_role = identities_by_role
        self.guild = guild
        self.current_page = current_page
        self.per_page = per_page
        
        # Flatten the role data for pagination
        self.flattened_data = []
        for role_name, members in identities_by_role.items():
            self.flattened_data.append(('role_header', role_name, len(members)))
            for member_data in members:
                self.flattened_data.append(('member', member_data, None))
        
        self.max_pages = max(1, (len(self.flattened_data) + per_page - 1) // per_page)
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
        
        # Add manage button
        manage_button = Button(label="⚙️ Manage Identities", style=ButtonStyle.secondary)
        manage_button.callback = self.manage_identities
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
        # Reload data
        self.identities_by_role = get_identities_by_role(self.guild)
        
        # Rebuild flattened data
        self.flattened_data = []
        for role_name, members in self.identities_by_role.items():
            self.flattened_data.append(('role_header', role_name, len(members)))
            for member_data in members:
                self.flattened_data.append(('member', member_data, None))
        
        self.max_pages = max(1, (len(self.flattened_data) + self.per_page - 1) // self.per_page)
        
        # Reset to first page if current page is out of bounds
        if self.current_page >= self.max_pages:
            self.current_page = 0
        
        self.update_buttons()
        embed = self.create_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def manage_identities(self, interaction: Interaction):
        await interaction.response.send_message(
            "💡 **Tips Manajemen Identitas:**\n"
            "• Gunakan `/identify <user>` untuk menambah/edit identitas\n"
            "• Nama panggilan akan digunakan di semua command\n"
            "• Pastikan nama panggilan unik untuk setiap user\n"
            "• Identitas membantu mengenali anggota tim dengan lebih baik",
            ephemeral=True
        )
    
    def create_embed(self):
        embed = discord.Embed(
            title="👥 Daftar Identitas Anggota",
            description="Identitas anggota berdasarkan role",
            color=0x3498db
        )
        
        if not self.flattened_data:
            embed.description = "Belum ada identitas yang terdaftar."
            embed.color = 0x95a5a6
            embed.add_field(
                name="💡 Cara Mendaftar Identitas",
                value="Gunakan command `/identify <user>` untuk mendaftarkan identitas anggota.",
                inline=False
            )
            return embed
        
        # Calculate current page data
        start_idx = self.current_page * self.per_page
        end_idx = min(start_idx + self.per_page, len(self.flattened_data))
        current_page_data = self.flattened_data[start_idx:end_idx]
        
        content = ""
        stats = {"total_identities": 0, "total_roles": 0}
        
        for item_type, data, extra in current_page_data:
            if item_type == 'role_header':
                role_name = data
                member_count = extra
                stats["total_roles"] += 1
                content += f"\n**🎭 {role_name}** ({member_count} anggota)\n"
                content += "─" * 30 + "\n"
            elif item_type == 'member':
                member_info = data
                stats["total_identities"] += 1
                
                # Status indicator
                status_emoji = "🟢" if member_info['status'] == 'online' else "⚫"
                
                content += f"{status_emoji} **{member_info['full_name']}** ({member_info['nickname']})\n"
                content += f"   └ Discord: {member_info['discord_name']}\n"
        
        if content:
            embed.description = content
        else:
            embed.description = "Tidak ada data pada halaman ini."
        
        # Add statistics
        embed.add_field(
            name="📊 Statistik",
            value=f"👥 Total Identitas: **{stats['total_identities']}**\n🎭 Role Ditampilkan: **{stats['total_roles']}**",
            inline=True
        )
        
        # Add legend
        embed.add_field(
            name="📝 Keterangan",
            value="🟢 Online\n⚫ Offline/Away\n🎭 Role Header",
            inline=True
        )
        
        embed.set_footer(text=f"Halaman {self.current_page + 1} dari {self.max_pages} • {self.per_page} item per halaman")
        
        return embed

def get_identities_by_role(guild):
    """Get identities organized by role"""
    try:
        # Load registered roles from database
        registered_roles = load_registered_roles()
        identities = load_identities()
        
        identities_by_role = {}
        
        for role_id in registered_roles:
            role = guild.get_role(role_id)
            if not role:
                continue
            
            role_members = []
            for member in role.members:
                if member.bot:
                    continue
                
                identity = identities.get(str(member.id))
                if identity:
                    role_members.append({
                        'user_id': member.id,
                        'discord_name': member.display_name,
                        'full_name': identity['full_name'],
                        'nickname': identity['nickname'],
                        'status': str(member.status)
                    })
            
            if role_members:
                # Sort by full name
                role_members.sort(key=lambda x: x['full_name'].lower())
                identities_by_role[role.name] = role_members
        
        return identities_by_role
        
    except Exception as e:
        print(f"Error getting identities by role: {e}")
        return {}

@app_commands.command(name="identify", description="Kelola identitas anggota (nama lengkap dan panggilan)")
@app_commands.checks.has_role("task manager")
async def identify(interaction: Interaction, target_user: discord.Member = None):
    if target_user:
        # Specific user mode - add/edit identity
        if target_user.bot:
            await interaction.response.send_message("Tidak dapat mengatur identitas untuk bot!", ephemeral=True)
            return
        
        # Show modal for identity input
        modal = IdentityModal(target_user)
        await interaction.response.send_modal(modal)
    else:
        # List all identities mode
        identities_by_role = get_identities_by_role(interaction.guild)
        
        if not identities_by_role:
            embed = discord.Embed(
                title="👥 Daftar Identitas Anggota",
                description="Belum ada identitas yang terdaftar dalam sistem.",
                color=0x95a5a6
            )
            
            embed.add_field(
                name="💡 Cara Mendaftar Identitas",
                value=(
                    "1. Gunakan `/identify <user>` untuk mendaftarkan identitas\n"
                    "2. Masukkan nama lengkap dan nama panggilan\n"
                    "3. Nama panggilan akan digunakan di semua command"
                ),
                inline=False
            )
            
            embed.add_field(
                name="📋 Manfaat Sistem Identitas",
                value=(
                    "• **Easy Recognition**: Kenali anggota dengan nama asli\n"
                    "• **Professional Display**: Tampilan nama yang lebih formal\n"
                    "• **Better Organization**: Organisasi berdasarkan role\n"
                    "• **Consistent Naming**: Nama panggilan konsisten di semua fitur"
                ),
                inline=False
            )
            
            embed.set_footer(text="Gunakan /identify <user> untuk memulai mendaftarkan identitas")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Create view with pagination
        view = IdentityListView(identities_by_role, interaction.guild)
        embed = view.create_embed()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

async def setup(bot):
    bot.tree.add_command(identify)
