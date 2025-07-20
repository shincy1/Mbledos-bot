import discord
from discord import app_commands
from discord.ext import commands, tasks
from utils.database import load_tasks, init_database
from utils.reminder import check_deadlines
import os
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Bot version - Semantic Versioning (MAJOR.MINOR.PATCH.BUILD)
BOT_VERSION = "1.4.1.0"
BOT_NAME = "Mbledos Task Manager"
VERSION_CODENAME = "Docker Edition"

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix=".", intents=intents)

@bot.event
async def on_ready():
    print(f'🚀 {BOT_NAME} v{BOT_VERSION} ({VERSION_CODENAME}) is ready!')
    print(f'📊 Bot: {bot.user}')
    print(f'🌐 Servers: {len(bot.guilds)}')
    print(f'👥 Users: {len(set(bot.get_all_members()))}')
    
    # Initialize database
    if not init_database():
        print("❌ Failed to initialize database. Bot may not function properly.")
    else:
        print("✅ Database initialized successfully")
    
    # Load commands setelah bot ready
    commands_loaded = 0
    commands_failed = 0
    
    for filename in os.listdir('./commands'):
        if filename.endswith('.py'):
            try:
                await bot.load_extension(f'commands.{filename[:-3]}')
                print(f'✅ Loaded {filename}')
                commands_loaded += 1
            except Exception as e:
                print(f'❌ Failed to load {filename}: {e}')
                commands_failed += 1
    
    print(f'📋 Commands loaded: {commands_loaded}, Failed: {commands_failed}')
    
    # Sync slash commands
    try:
        synced = await bot.tree.sync()
        print(f'🔄 Synced {len(synced)} slash command(s)')
    except Exception as e:
        print(f'❌ Failed to sync commands: {e}')
    
    # Set bot activity
    activity = discord.Activity(
        type=discord.ActivityType.watching,
        name=f"tasks • v{BOT_VERSION} • MySQL"
    )
    await bot.change_presence(activity=activity)
    
    # Start reminder system
    check_deadlines_loop.start()
    print(f'⏰ Reminder system started (30-minute intervals)')
    print(f'🎉 {BOT_NAME} v{BOT_VERSION} ({VERSION_CODENAME}) fully initialized!')

@bot.event
async def on_guild_join(guild):
    print(f'📥 Joined new server: {guild.name} (ID: {guild.id})')
    print(f'👥 Members: {guild.member_count}')

@bot.event
async def on_guild_remove(guild):
    print(f'📤 Left server: {guild.name} (ID: {guild.id})')

@bot.event
async def on_application_command_error(interaction, error):
    """Handle slash command errors"""
    if isinstance(error, app_commands.MissingRole):
        embed = discord.Embed(
            title="❌ Akses Ditolak",
            description="Anda tidak memiliki role yang diperlukan untuk menggunakan command ini.",
            color=0xe74c3c
        )
        embed.add_field(
            name="Role yang Diperlukan",
            value="**task manager**",
            inline=False
        )
        embed.add_field(
            name="💡 Solusi",
            value="Hubungi administrator server untuk mendapatkan role yang sesuai.",
            inline=False
        )
        
        try:
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except:
            await interaction.followup.send(embed=embed, ephemeral=True)
    else:
        print(f"Command error: {error}")
        
        embed = discord.Embed(
            title="❌ Terjadi Kesalahan",
            description="Maaf, terjadi kesalahan saat menjalankan command.",
            color=0xe74c3c
        )
        embed.add_field(
            name="Error Details",
            value=f"```{str(error)[:1000]}```",
            inline=False
        )
        
        try:
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except:
            await interaction.followup.send(embed=embed, ephemeral=True)

@tasks.loop(minutes=30)
async def check_deadlines_loop():
    """Check deadlines every 30 minutes"""
    try:
        await check_deadlines(bot)
    except Exception as e:
        print(f"Error in deadline check: {e}")

@check_deadlines_loop.before_loop
async def before_deadline_check():
    """Wait until bot is ready before starting deadline checks"""
    await bot.wait_until_ready()

# Add version command
@bot.tree.command(name="version", description="Lihat versi bot dan informasi sistem")
async def version_command(interaction: discord.Interaction):
    # Parse version components
    version_parts = BOT_VERSION.split('.')
    major, minor, patch, build = version_parts if len(version_parts) == 4 else version_parts + ['0']
    
    embed = discord.Embed(
        title=f"🤖 {BOT_NAME}",
        description=f"**{VERSION_CODENAME}**\nAdvanced Discord Task Management System with MySQL Database",
        color=0x3498db
    )
    
    # Version information
    version_info = (
        f"**Version:** `{BOT_VERSION}`\n"
        f"**Major:** {major} (Core System)\n"
        f"**Minor:** {minor} (New Features)\n"
        f"**Patch:** {patch} (Improvements)\n"
        f"**Build:** {build} (Release Build)"
    )
    embed.add_field(name="📊 Version Details", value=version_info, inline=True)
    
    # System statistics
    system_stats = (
        f"**Servers:** {len(bot.guilds)}\n"
        f"**Users:** {len(set(bot.get_all_members()))}\n"
        f"**Commands:** 8 slash commands\n"
        f"**Database:** MySQL\n"
        f"**Uptime:** Since startup"
    )
    embed.add_field(name="🌐 System Stats", value=system_stats, inline=True)
    
    # Release information
    release_info = (
        f"**Release Date:** December 2024\n"
        f"**License:** MIT License\n"
        f"**Developer:** shincy1\n"
        f"**Framework:** discord.py\n"
        f"**Database:** MySQL 8.0+"
    )
    embed.add_field(name="ℹ️ Release Info", value=release_info, inline=True)
    
    embed.add_field(
        name="🆕 Version 1.3.1 New Features",
        value=(
            "• **Docker**: Robust Docker Compose deployment\n"
            "• **MySQL Database**: Robust database backend\n"
            "• **Connection Pooling**: Optimized database performance\n"
            "• **Data Integrity**: ACID compliance and constraints\n"
            "• **Scalability**: Handle larger datasets efficiently\n"
            "• **Backup & Recovery**: Built-in database reliability\n"
            "• **Environment Variables**: Secure configuration\n"
            "• **Performance Optimization**: Faster data operations"
        ),
        inline=False
    )
    
    embed.add_field(
        name="📋 Available Commands",
        value=(
            "**Task Manager Commands:**\n"
            "`/ask` - Assign tasks to users\n"
            "`/listjob [user]` - View tasks (all users or specific)\n"
            "`/activities` - View activity history\n"
            "`/regisrole [role]` - Manage registered roles\n"
            "`/rolelist` - View role details and members\n\n"
            "**User Commands:**\n"
            "`/myjob` - View personal tasks\n"
            "`/identify` - Manage personal identity & nickname\n"
            "`/version` - View system information"
        ),
        inline=False
    )
    
    # Add what's new
    embed.add_field(
        name="✨ What's New in v1.3.1.0",
        value=(
            "🔥 **NEW:** MySQL database backend\n"
            "🔥 **NEW:** Connection pooling for better performance\n"
            "🔥 **NEW:** Environment-based configuration\n"
            "⚡ **IMPROVED:** Data integrity with database constraints\n"
            "⚡ **IMPROVED:** Faster query performance\n"
            "⚡ **IMPROVED:** Better error handling and recovery\n"
            "🐛 **FIXED:** Data consistency issues\n"
            "📊 **ENHANCED:** Scalable architecture for growth"
        ),
        inline=False
    )
    
    # Database status
    try:
        from utils.database import get_connection
        conn = get_connection()
        conn.close()
        db_status = "🟢 Connected"
    except:
        db_status = "🔴 Disconnected"
    
    embed.add_field(
        name="🗄️ Database Status",
        value=(
            f"**Status:** {db_status}\n"
            f"**Type:** MySQL\n"
            f"**Host:** {os.getenv('DB_HOST', 'localhost')}\n"
            f"**Database:** {os.getenv('DB_NAME', 'mbledos_bot')}"
        ),
        inline=True
    )
    
    embed.set_footer(
        text=f"Mbledos Task Manager v{BOT_VERSION} • MySQL Edition • Developed by shincy1",
        icon_url=bot.user.display_avatar.url
    )
    
    embed.set_thumbnail(url=bot.user.display_avatar.url)
    await interaction.response.send_message(embed=embed, ephemeral=True)

# Jalankan bot
if __name__ == "__main__":
    print(f"🚀 Starting {BOT_NAME} v{BOT_VERSION} ({VERSION_CODENAME})...")
    print(f"📋 Semantic Versioning: MAJOR.MINOR.PATCH.BUILD")
    print(f"   └ MAJOR: {BOT_VERSION.split('.')[0]} (Breaking changes)")
    print(f"   └ MINOR: {BOT_VERSION.split('.')[1]} (New features)")
    print(f"   └ PATCH: {BOT_VERSION.split('.')[2]} (Bug fixes & improvements)")
    print(f"   └ BUILD: {BOT_VERSION.split('.')[3]} (Release build)")
    print(f"🆕 New in v1.3.1: MySQL Database Backend")
    print(f"   └ Robust database with connection pooling")
    print(f"   └ ACID compliance and data integrity")
    print(f"   └ Environment-based secure configuration")
    print(f"   └ Optimized performance for larger datasets")
    
    # Check environment variables
    required_env = ['DISCORD_TOKEN', 'DB_USER']
    missing_env = [var for var in required_env if not os.getenv(var)]
    
    if missing_env:
        print(f"❌ Missing required environment variables: {', '.join(missing_env)}")
        print("Please check your .env file and ensure all required variables are set.")
        exit(1)
    
    print("✅ Environment variables loaded successfully")
    bot.run(os.getenv("DISCORD_TOKEN"))
