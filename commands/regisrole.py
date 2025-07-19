import json
import discord
from discord import app_commands, Interaction, ButtonStyle
from discord.ui import Button, View
from discord.ext import commands
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
                # Load config
                with open("config.json", "r") as f:
                    config = json.load(f)
                
                # Remove role from registered_roles
                if role_id in config["registered_roles"]:
                    config["registered_roles"].remove(role_id)
                    
                    # Save config
                    with open("config.json", "w") as f:
                        json.dump(config, f, indent=4)
                    
                    embed = discord.Embed(
                        title="✅ Berhasil",
                        description=f"Role **{role_name}** berhasil dihapus dari daftar.",
                        color=0x2ecc71
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
        # Ensure config file exists
        if not os.path.exists("config.json"):
            default_config = {
                "token": "",
                "registered_roles": []
            }
            with open("config.json", "w") as f:
                json.dump(default_config, f, indent=4)
        
        # Load config
        with open("config.json", "r") as f:
            config = json.load(f)
        
        # Ensure registered_roles key exists
        if "registered_roles" not in config:
            config["registered_roles"] = []
        
        # If no role specified, show management interface
        if role is None:
            view = RoleManagementView(config["registered_roles"], interaction.guild)
            embed = view.create_roles_embed()
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            return
        
        # Check if role is @everyone
        if role.id == interaction.guild.id:
            await interaction.response.send_message("Tidak dapat mendaftarkan role @everyone!", ephemeral=True)
            return
        
        # Check if role is managed by bot/integration
        if role.managed:
            await interaction.response.send_message("Tidak dapat mendaftarkan role yang dikelola oleh bot atau integrasi!", ephemeral=True)
            return
        
        # Check if role is higher than bot's highest role
        bot_member = interaction.guild.get_member(interaction.client.user.id)
        if bot_member and role >= bot_member.top_role:
            await interaction.response.send_message("Tidak dapat mendaftarkan role yang lebih tinggi dari role bot!", ephemeral=True)
            return
        
        # Register or unregister role
        if role.id not in config["registered_roles"]:
            config["registered_roles"].append(role.id)
            
            # Save config
            with open("config.json", "w") as f:
                json.dump(config, f, indent=4)
            
            embed = discord.Embed(
                title="✅ Role Berhasil Didaftarkan",
                description=f"Role {role.mention} berhasil didaftarkan!",
                color=0x2ecc71
            )
            
            embed.add_field(name="📝 Nama Role", value=role.name, inline=True)
            embed.add_field(name="🆔 Role ID", value=str(role.id), inline=True)
            embed.add_field(name="👥 Jumlah Anggota", value=str(len(role.members)), inline=True)
            
            embed.add_field(
                name="ℹ️ Info",
                value="Anggota dengan role ini sekarang dapat diberi tugas menggunakan command `/ask`.",
                inline=False
            )
            
            embed.set_footer(text="Gunakan /regisrole tanpa parameter untuk melihat semua role terdaftar")
            
        else:
            embed = discord.Embed(
                title="⚠️ Role Sudah Terdaftar",
                description=f"Role {role.mention} sudah terdaftar sebelumnya.",
                color=0xf39c12
            )
            
            embed.add_field(
                name="💡 Tips",
                value="Gunakan `/regisrole` tanpa parameter untuk mengelola role terdaftar.",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
    except json.JSONDecodeError:
        embed = discord.Embed(
            title="❌ Error",
            description="File konfigurasi rusak. Silakan hubungi administrator.",
            color=0xe74c3c
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
