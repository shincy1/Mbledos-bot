import discord
from discord.ext import commands, tasks
from utils.database import load_tasks
from utils.reminder import check_deadlines
import os
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix=".", intents=intents)

@bot.event
async def on_ready():
    print(f'Bot is ready as {bot.user}')
    
    # Load commands setelah bot ready
    for filename in os.listdir('./commands'):
        if filename.endswith('.py'):
            try:
                await bot.load_extension(f'commands.{filename[:-3]}')
                print(f'Loaded {filename}')
            except Exception as e:
                print(f'Failed to load {filename}: {e}')
    
    # Sync slash commands
    try:
        synced = await bot.tree.sync()
        print(f'Synced {len(synced)} command(s)')
    except Exception as e:
        print(f'Failed to sync commands: {e}')
    
    check_deadlines_loop.start()

@tasks.loop(minutes=30)
async def check_deadlines_loop():
    await check_deadlines(bot)

# Jalankan bot
bot.run(os.getenv("DISCORD_TOKEN"))
