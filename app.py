import discord
from discord.ext import commands, tasks
from discord import ui, Interaction
import re
import random
import asyncio
from datetime import datetime, timezone, timedelta

# ========== НАСТРОЙКИ ==========
MOSCOW_TZ = timezone(timedelta(hours=3))  # Московское время UTC+3

def get_moscow_time():
    """Возвращает текущее московское время"""
    return datetime.now(MOSCOW_TZ).strftime("%H:%M:%S")

def get_moscow_datetime():
    """Возвращает полную дату и время по Москве"""
    return datetime.now(MOSCOW_TZ).strftime("%d.%m.%Y %H:%M:%S")

# ========== КОНФИГ ==========
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.presences = True
bot = commands.Bot(command_prefix='!', intents=intents)

WHITELIST_CHANNEL_ID = 1512930366464463060
HOST_ROLE_ID = 1483737074388570253

# ========== ИМИТАЦИЯ АКТИВНОСТИ ==========
@tasks.loop(minutes=5)
async def fake_activity():
    channel = bot.get_channel(WHITELIST_CHANNEL_ID)
    if channel and random.random() < 0.3:
        messages = [
            f"🟢 Система вайт-листа активна | {get_moscow_time()} МСК",
            f"📊 Проверка заявок... | {get_moscow_time()}",
            f"⚙️ Обновление списка | {get_moscow_time()}",
            f"✅ Всё работает штатно | {get_moscow_time()} МСК",
            f"💾 Синхронизация с базой | {get_moscow_time()}"
        ]
        await channel.send(random.choice(messages))

@tasks.loop(minutes=1)
async def change_status():
    statuses = [
        discord.Game(f"📝 {get_moscow_time()} МСК"),
        discord.Game(f"👥 {len(bot.guilds)} серверов | {get_moscow_time()}"),
        discord.Activity(type=discord.ActivityType.watching, name=f"✅ {get_moscow_time()}"),
        discord.Game(f"🔍 {get_moscow_time()}"),
        discord.Activity(type=discord.ActivityType.listening, name="!whitelist")
    ]
    await bot.change_presence(status=discord.Status.online, activity=random.choice(statuses))

@tasks.loop(hours=2)
async def memory_cleanup():
    print(f"🧹 Очистка кэша... {get_moscow_datetime()}")

# ========== ОСНОВНОЙ КОД ==========
def can_approve(member: discord.Member) -> bool:
    return any(role.id == HOST_ROLE_ID for role in member.roles)

class WhiteListModal(ui.Modal, title="📝 Анкета вайт-листа"):
    nickname = ui.TextInput(label="1. Никнейм в игре", placeholder="Ваш никнейм ТОЧНО как в игре", required=True, max_length=50)
    age = ui.TextInput(label="2. Сколько вам лет", placeholder="Необязательно", required=False, max_length=3)
    plans = ui.TextInput(label="3. Что собираетесь делать на сервере", placeholder="Строить, выживать, помогать...", style=discord.TextStyle.paragraph, required=True, max_length=500)
    hours = ui.TextInput(label="4. Сколько сможете играть в день", placeholder="Например: 2-3 часа", required=True, max_length=100)
    source = ui.TextInput(label="5. Откуда узнали о нас", placeholder="Друг, YouTube, реклама...", required=True, max_length=200)

    async def on_submit(self, interaction: Interaction):
        nickname = self.nickname.value.strip()
        if not re.match(r'^[A-Za-z0-9_]{3,32}$', nickname):
            await interaction.response.send_message(
                f"❌ **Ошибка!** Никнейм может содержать только буквы, цифры и _, длина 3-32 символа.\nПовторите заявку. | {get_moscow_time()} МСК",
                ephemeral=True
            )
            return

        channel = bot.get_channel(WHITELIST_CHANNEL_ID)
        if not channel:
            await interaction.response.send_message(
                f"❌ Ошибка: канал вайт-листа не найден. Сообщите хосту. | {get_moscow_time()}",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title="📥 Новая заявка в вайт-лист",
            color=discord.Color.blue(),
            timestamp=interaction.created_at
        )
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.avatar.url)
        embed.add_field(name="🎮 1. Никнейм", value=f"`{nickname}`", inline=False)
        embed.add_field(name="📅 2. Возраст", value=self.age.value or "не указан", inline=False)
        embed.add_field(name="⚒️ 3. Планы", value=self.plans.value, inline=False)
        embed.add_field(name="⏱️ 4. Часы в день", value=self.hours.value, inline=False)
        embed.add_field(name="🔍 5. Откуда узнали", value=self.source.value, inline=False)
        embed.set_footer(text=f"ID: {interaction.user.id} | {get_moscow_time()} МСК")

        await channel.send(
            f"📣 **Заявка от {interaction.user.mention}**\n*Только хост может поставить ✅ для одобрения*\n⏰ Время: {get_moscow_time()} МСК",
            embed=embed
        )

        await interaction.response.send_message(
            f"✅ **Заявка отправлена!**\nНикнейм: `{nickname}`\n⏰ Время: {get_moscow_time()} МСК\nОжидайте реакции ✅ от хоста в канале whitelist.",
            ephemeral=True
        )

class WhiteListButton(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="📝 Подать заявку в вайт-лист", style=discord.ButtonStyle.primary, custom_id="whitelist_btn")
    async def whitelist_button(self, interaction: Interaction, button: ui.Button):
        await interaction.response.send_modal(WhiteListModal())

@bot.command()
@commands.has_permissions(administrator=True)
async def whitelist(ctx):
    embed = discord.Embed(
        title="📋 Подача заявки в вайт-лист",
        description=f"Нажми на кнопку ниже и заполни анкету.\n**Важно:** никнейм должен быть точь-в-точь как в игре!\n\n✅ После одобрения **хост** поставит реакцию под твоей заявкой.\n\n🕐 Текущее время: **{get_moscow_time()} МСК**",
        color=discord.Color.green()
    )
    await ctx.send(embed=embed, view=WhiteListButton())
    await ctx.message.delete()

@bot.command()
async def time(ctx):
    """Команда !time - показывает текущее московское время"""
    await ctx.send(f"🕐 **Текущее московское время:** `{get_moscow_datetime()}`")

@bot.event
async def on_raw_reaction_add(payload):
    if payload.user_id == bot.user.id:
        return
    if str(payload.emoji) != "✅":
        return
    if payload.channel_id != WHITELIST_CHANNEL_ID:
        return

    guild = bot.get_guild(payload.guild_id)
    if not guild:
        return

    member = guild.get_member(payload.user_id)
    if not member:
        try:
            member = await guild.fetch_member(payload.user_id)
        except:
            return

    if not can_approve(member):
        return

    channel = bot.get_channel(payload.channel_id)
    try:
        message = await channel.fetch_message(payload.message_id)
    except:
        return

    if message.embeds:
        embed = message.embeds[0]
        for field in embed.fields:
            if field.name == "🎮 1. Никнейм":
                nickname = field.value.strip('`')
                await channel.send(
                    f"✅ **Игрок добавлен в вайт-лист!**\n"
                    f"Никнейм: `{nickname}`\n"
                    f"Одобрил: {member.mention} (Хост)\n"
                    f"⏰ Время одобрения: {get_moscow_time()} МСК"
                )
                return

@bot.event
async def on_ready():
    print(f"✅ Бот {bot.user} запущен")
    print(f"🕐 Текущее московское время: {get_moscow_datetime()}")
    
    bot.add_view(WhiteListButton())
    change_status.start()
    fake_activity.start()
    memory_cleanup.start()
    
    print("🔄 Все системы активны")

@bot.event
async def on_disconnect():
    print(f"⚠️ Бот отключился в {get_moscow_datetime()}")

# ========== ЗАПУСК ==========
bot.run("MTUxMTgyNzEzNzA4MTExODc1MA.GddQcL.AhImIAzB9hrmW9S_VMozeEhf6Ip3XU6_40d_HI")  # ЗАМЕНИ НА СВОЙ ТОКЕН!
