import discord
from discord.ext import commands
from dotenv import load_dotenv
import os
import asyncio
from mcrcon import MCRcon

load_dotenv()

TOKEN = os.getenv("TOKEN")
RCON_IP = os.getenv("RCON_IP")
RCON_PORT = int(os.getenv("RCON_PORT", 25575))
RCON_PASSWORD = os.getenv("RCON_PASSWORD")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)


# ===== КНОПКИ ПРИНЯТЬ / ОТКЛОНИТЬ В ТИКЕТЕ =====
class AdminButtons(discord.ui.View):
    def __init__(self, applicant: discord.Member, nickname: str):
        super().__init__(timeout=None)
        self.applicant = applicant
        self.nickname = nickname

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        is_mod = discord.utils.get(interaction.user.roles, name="Модератор") is not None
        is_admin = discord.utils.get(interaction.user.roles, name="Администратор") is not None
        
        if is_mod or is_admin or interaction.user.guild_permissions.administrator:
            return True
        
        await interaction.response.send_message(
            "❌ У вас нет прав для управления этой заявкой!", 
            ephemeral=True
        )
        return False

    @discord.ui.button(label="Принять", style=discord.ButtonStyle.success, emoji="✅")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        player_role = discord.utils.get(guild.roles, name="Игрок")
        
        await interaction.response.defer()
        log_messages = []

        # 1. Выдача роли
        if player_role:
            try:
                await self.applicant.add_roles(player_role)
                log_messages.append(f"• Выдана роль {player_role.mention}")
            except discord.Forbidden:
                log_messages.append("• ❌ Не удалось выдать роль (проверь иерархию ролей бота)")
        else:
            log_messages.append("• ❌ Роль 'Игрок' не найдена на сервере!")

        # 2. Смена ника
        try:
            await self.applicant.edit(nick=self.nickname)
            log_messages.append(f"• Никнейм изменен на **{self.nickname}**")
        except discord.Forbidden:
            log_messages.append("• ❌ Не удалось изменить ник (у бота нет прав или это владелец)")

        # 3. Вайтлист через RCON
        try:
            with MCRcon(RCON_IP, RCON_PASSWORD, port=RCON_PORT) as mcr:
                response = mcr.command(f"whitelist add {self.nickname}")
                log_messages.append(f"• 🎮 Вайтлист: `{response.strip()}`")
        except Exception as e:
            log_messages.append(f"• ❌ Ошибка RCON: Не удалось добавить в вайтлист (сервер выключен)")

        # 4. Отправка ЛС игроку
        dm_embed = discord.Embed(
            title="🎉 Ваша заявка одобрена!",
            description=f"Добро пожаловать на **Netherium SMP**, **{self.nickname}**! Вы были успешно добавлены в вайтлист. Ниже указаны данные для подключения:",
            color=0x00ff00
        )
        dm_embed.add_field(name="Версия сервера", value="`1.21.11`", inline=False)
        dm_embed.add_field(name="Основной IP-адрес", value="`ru1.mc-serv.ru:27845`", inline=True)
        dm_embed.add_field(name="Дополнительный IP-адрес", value="`217.106.106.181:27845`", inline=True)
        dm_embed.set_footer(text="Приятной игры на Netherium!")

        try:
            await self.applicant.send(embed=dm_embed)
            log_messages.append("• 📥 Уведомление успешно отправлено игроку в ЛС")
        except discord.Forbidden:
            log_messages.append("• ⚠️ Не удалось отправить ЛС игроку (у него закрыты личные сообщения)")

        log_text = "\n".join(log_messages)
        await interaction.channel.send(
            f"🟢 **Заявка одобрена модератором {interaction.user.mention}!**\n{log_text}\n\n*Этот канал будет удален через 5 секунд...*"
        )
        
        await asyncio.sleep(5)
        await interaction.channel.delete()

    @discord.ui.button(label="Отклонить", style=discord.ButtonStyle.danger, emoji="❌")
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        
        dm_embed = discord.Embed(
            title="❌ Ваша заявка отклонена",
            description="Здравствуйте. К сожалению, ваша заявка на сервер **Netherium SMP** была отклонена модерацией сервера.",
            color=0xff0000
        )
        dm_embed.set_footer(text="Netherium SMP")

        dm_status = ""
        try:
            await self.applicant.send(embed=dm_embed)
            dm_status = "\n• 📥 Уведомление об отказе отправлено в ЛС."
        except discord.Forbidden:
            dm_status = "\n• ⚠️ Не удалось отправить ЛС (у игрока закрыты личные сообщения)."

        await interaction.channel.send(
            f"🔴 **Заявка отклонена модератором {interaction.user.mention}.**{dm_status}\n*Этот канал будет удален через 5 секунд...*"
        )
        
        await asyncio.sleep(5)
        await interaction.channel.delete()


# ===== ФОРМА АНКЕТЫ =====
class ApplyForm(discord.ui.Modal, title="Заявка на Netherium"):
    nickname = discord.ui.TextInput(
        label="Игровой никнейм", 
        placeholder="Введите ваш ник", 
        required=True, 
        max_length=16
    )
    age = discord.ui.TextInput(
        label="Возраст", 
        placeholder="Сколько вам лет?", 
        required=True, 
        max_length=3
    )
    about = discord.ui.TextInput(
        label="Расскажите о себе", 
        style=discord.TextStyle.paragraph, 
        placeholder="Чем вы занимаетесь?", 
        required=True, 
        max_length=400
    )
    source = discord.ui.TextInput(
        label="Откуда вы о нас узнали?", 
        placeholder="TikTok, YouTube, друг, мониторинг...", 
        required=True, 
        max_length=100
    )
    pack_check = discord.ui.TextInput(
        label="Скачали модпак и ресурспак?", 
        placeholder="Да / Нет (всё лежит в канале 🧭・навигатор)", 
        required=True, 
        max_length=50
    )

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        applicant = interaction.user

# КАТЕГОРИЯ ДЛЯ ТИКЕТОВ
        category = discord.utils.get(guild.categories, name="ЗАЯВКИ")

        # НАСТРОЙКА ПРАВ ДОСТУПА НА КАНАЛ
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),  # Скрываем от всех остальных
            applicant: discord.PermissionOverwrite(read_messages=True, send_messages=True)  # Игрок видит и может писать
        }

        # Добавляем права для модераторов и админов (чтобы они видели и могли писать)
        moderator_role = discord.utils.get(guild.roles, name="Модератор")
        admin_role = discord.utils.get(guild.roles, name="Администратор")

        if moderator_role:
            overwrites[moderator_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        if admin_role:
            overwrites[admin_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        # СОЗДАНИЕ КАНАЛА С ПРАВАМИ
        channel = await guild.create_text_channel(
            name=f"заявка-{self.nickname.value}",
            category=category,
            overwrites=overwrites
        )

        embed = discord.Embed(title="📨 Новая заявка", color=0xff8800)
        embed.add_field(name="👤 Никнейм", value=self.nickname.value, inline=False)
        embed.add_field(name="🎂 Возраст", value=self.age.value, inline=False)
        embed.add_field(name="📝 О себе", value=self.about.value, inline=False)
        embed.add_field(name="📢 Откуда узнал", value=self.source.value, inline=False)
        embed.add_field(name="📦 Модпак / Ресурспак", value=self.pack_check.value, inline=False)
        embed.set_footer(text=f"Discord ID: {applicant.id}")

        moderator_role = discord.utils.get(guild.roles, name="Модератор")
        admin_role = discord.utils.get(guild.roles, name="Администратор")

        mentions = ""
        if moderator_role: mentions += f"{moderator_role.mention} "
        if admin_role: mentions += f"{admin_role.mention}"

        view = AdminButtons(applicant=applicant, nickname=self.nickname.value)

        await channel.send(content=mentions if mentions else "Роли для тега не найдены!", embed=embed, view=view)
        await interaction.response.send_message(f"✅ Заявка отправлена: {channel.mention}", ephemeral=True)


# ===== КНОПКА ПОДАЧИ ЗАЯВКИ =====
class ApplyButton(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)

    @discord.ui.button(label="Подать заявку", style=discord.ButtonStyle.primary, emoji="📨")
    async def apply(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ApplyForm())


@bot.event
async def on_ready():
    print(f'Бот запущен как {bot.user}')


# ===== КОМАНДА SETUP =====
@bot.command()
@commands.has_permissions(administrator=True)
async def setup(ctx):
    embed = discord.Embed(
        title="🌑 Заявка на Netherium",
        description="Нажми кнопку ниже, чтобы подать заявку на сервер.",
        color=0xff8800
    )
    embed.set_footer(text="Netherium SMP")
    await ctx.send(embed=embed, view=ApplyButton())

@setup.error
async def setup_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ У вас нет прав Администратора для использования этой команды!", delete_after=5)


bot.run(TOKEN)