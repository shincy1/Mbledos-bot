import discord
from discord import app_commands, Interaction, ButtonStyle
from discord.ui import Button, View
from discord.ext import commands
from utils.database import load_registered_roles, save_registered_roles
import os

class RoleManagementView(View):
    def __init__(self, registered_roles, guild):
        super().__init__(timeout=300)
        self.registered_roles = registered_roles
        self.guild = guild
        self.update_buttons()
    
    def update_buttons(self):
        self.clear_items()
        
        # Add view all roles button
        view_button = Button(label="👁️ Lihat Semua Role", style=ButtonStyle.primary)
        view_button.callback = self.view_all_roles
        self.add_item(view_button)
        
        # Add remove role button if there are registered roles
        if self.registered_roles:
            remove_button = Button(label="🗑️ Hapus Role", style=ButtonStyle.danger)
            remove_button.callback = self.show_remove_options
            self.add_item(remove_button)
    
    async def view_all_roles(self, interaction: Interaction):
        embed = self.create_roles_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def show_remove_options(self, interaction: Interaction):
        if not self.registered_roles:
            await interaction.response.send_message("Tidak ada role yang terdaftar untuk dihapus.", ephemeral=True)
            return
        
        # Create remove view
        remove_view = RemoveRoleView(self.registered_roles, self.guild)
        embed = discord.Embed(
            title="🗑️ Hapus Role Terdaftar",
            description="Pilih role yang ingin dihapus dari daftar:",
            color=0xe74c3c
        )
        
        role_list = ""
        for role_id in self.registered_roles:
            role = self.guild.get_role(role_id)
            if role:
                role_list += f"• {role.name} ({role.mention})\n"
            else:
                role_list += f"• Role tidak ditemukan (ID: {role_id})\n"
        
        embed.add_field(name="Role Terdaftar", value=role_list or "Tidak ada role", inline=False)
        
        await interaction.response.send_message(embed=embed, view=remove_view, ephemeral=True)
    
    def create_roles_embed(self):
        embed = discord.Embed(
            title="📋 Daftar Role Terdaftar",
            description="Role yang dapat diberi tugas:",
            color=0x3498db
        )
        
        if not self.registered_roles:
            embed.description = "Belum ada role yang terdaftar."
            embed.color = 0x95a5a6
            return embed
        
        role_info = ""
        valid_roles = 0
        invalid_roles = 0
        
        for role_id in self.registered_roles:
            role = self.guild.get_role(role_id)
            if role:
                member_count = len(role.members)
                role_info += f"🔹 **{role.name}**\n"
                role_info += f"   └ {role.mention} • {member_count} anggota\n\n"
                valid_roles += 1
            else:
                role_info += f"❌ **Role Tidak Ditemukan**\n"
                role_info += f"   └ ID: {role_id} (mungkin sudah dihapus)\n\n"
                invalid_roles += 1
        
        embed.add_field(name="Role List", value=role_info or "Tidak ada role", inline=False)
        
        # Add statistics
        stats = f"✅ Valid: {valid_roles}\n"
        if invalid_roles > 0:
            stats += f"❌ Invalid: {invalid_roles}\n"
        stats += f"📊 Total: {len(self.registered_roles)}"
        
        embed.add_field(name="Statistik", value=stats, inline=True)
        
        embed.set_footer(text="Gunakan /regisrole <role> untuk menambah role baru")
        
        return embed

class RemoveRoleView(View):
    def __init__(self, registered_roles, guild):
        super().__init__(timeout=60)
        self.registered_roles = registered_roles
        self.guild = guild
        
        # Add buttons for each role (max 25 buttons)
        for i, role_id in enumerate(registered_roles[:25]):
            role = guild.get_role(role_id)
            if role:
                button = Button(
                    label=f"Remove {role.name}"[:80], 
                    style=ButtonStyle.danger,
                    custom_id=f"remove_{role_id}"
                )
                button.callback = self.create_remove_callback(role_id, role.name)
                self.add_item(button)
    
    def create_remove_callback(self, role_id, role_name):
        async def remove_role_callback(interaction: Interaction):
            try:
                # Load registered roles from database
                registered_roles = load_registered_roles()
                
                # Remove role from registered_roles
                if role_id in registered_roles:
                    registered_roles.remove(role_id)
                    
                    # Save updated roles to database
                    if save_registered_roles(registered_roles):
                        embed = discord.Embed(
                            title="✅ Berhasil",
                            description=f"Role **{role_name}** berhasil dihapus dari daftar.",
                            color=0x2ecc71
                        )
                    else:
                        embed = discord.Embed(
                            title="❌ Error",
                            description=f"Gagal menyimpan perubahan untuk role **{role_name}**.",
                            color=0xe74c3c
                        )
                    
                    await interaction.response.edit_message(embed=embed, view=None)
                else:
                    embed = discord.Embed(
                        title="❌ Error",
                        description=f"Role **{role_name}** tidak ditemukan dalam daftar.",
                        color=0xe74c3c
                    )
                    await interaction.response.edit_message(embed=embed, view=None)
                    
            except Exception as e:
                embed = discord.Embed(
                    title="❌ Error",
                    description=f"Gagal menghapus role: {str(e)}",
                    color=0xe74c3c
                )
                await interaction.response.edit_message(embed=embed, view=None)
        
        return remove_role_callback

@app_commands.command(name="regisrole", description="Daftarkan role yang bisa diberi tugas")
@app_commands.checks.has_role("task manager")
async def regisrole(interaction: Interaction, role: discord.Role = None):
    try:
        # Load registered roles from database
        registered_roles = load_registered_roles()
        
        # If no role specified, show management interface
        if role is None:
            view = RoleManagementView(registered_roles, interaction.guild)
            embed = view.create_roles_embed()
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            return
        
        # Check if role is @everyone
        if role.id == interaction.guild.id:
            embed = discord.Embed(
                title="❌ Role Tidak Valid",
                description="Tidak dapat mendaftarkan role @everyone!",
                color=0xe74c3c
            )
            embed.add_field(
                name="💡 Alasan",
                value="Role @everyone mencakup semua anggota server dan tidak dapat digunakan untuk sistem tugas.",
                inline=False
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Check if role is managed by bot/integration (optional warning, not blocking)
        if role.managed:
            embed = discord.Embed(
                title="⚠️ Peringatan",
                description=f"Role **{role.name}** dikelola oleh bot atau integrasi.",
                color=0xf39c12
            )
            embed.add_field(
                name="ℹ️ Info",
                value="Role ini mungkin berubah secara otomatis. Apakah Anda yakin ingin mendaftarkannya?",
                inline=False
            )
            # Still allow registration, just show warning
        
        # Register or show already registered message
        if role.id not in registered_roles:
            registered_roles.append(role.id)
            
            # Save to database
            if save_registered_roles(registered_roles):
                embed = discord.Embed(
                    title="✅ Role Berhasil Didaftarkan",
                    description=f"Role {role.mention} berhasil didaftarkan!",
                    color=0x2ecc71
                )
                
                embed.add_field(name="📝 Nama Role", value=role.name, inline=True)
                embed.add_field(name="🆔 Role ID", value=str(role.id), inline=True)
                embed.add_field(name="👥 Jumlah Anggota", value=str(len(role.members)), inline=True)
                
                # Show role position info
                embed.add_field(name="📊 Posisi Role", value=f"#{role.position}", inline=True)
                embed.add_field(name="🎨 Warna Role", value=str(role.color), inline=True)
                embed.add_field(name="🔧 Dikelola Bot", value="Ya" if role.managed else "Tidak", inline=True)
                
                embed.add_field(
                    name="ℹ️ Info",
                    value="Anggota dengan role ini sekarang dapat diberi tugas menggunakan command `/ask`.",
                    inline=False
                )
                
                embed.set_footer(text="Gunakan /regisrole tanpa parameter untuk melihat semua role terdaftar")
            else:
                embed = discord.Embed(
                    title="❌ Error",
                    description="Gagal menyimpan role ke database.",
                    color=0xe74c3c
                )
        else:
            embed = discord.Embed(
                title="⚠️ Role Sudah Terdaftar",
                description=f"Role {role.mention} sudah terdaftar sebelumnya.",
                color=0xf39c12
            )
            
            embed.add_field(name="📝 Nama Role", value=role.name, inline=True)
            embed.add_field(name="👥 Jumlah Anggota", value=str(len(role.members)), inline=True)
            embed.add_field(name="📊 Posisi Role", value=f"#{role.position}", inline=True)
            
            embed.add_field(
                name="💡 Tips",
                value="Gunakan `/regisrole` tanpa parameter untuk mengelola role terdaftar.",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
    except Exception as e:
        embed = discord.Embed(
            title="❌ Error",
            description=f"Terjadi kesalahan: {str(e)}",
            color=0xe74c3c
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    bot.tree.add_command(regisrole)
