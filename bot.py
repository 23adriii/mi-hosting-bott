# --- IMPORTACIONES NECESARIAS ---
import discord
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput, Select # Añadido Select para tipado
import io
import os  # Para leer el token de forma segura
from flask import Flask  # Para el servidor web
from threading import Thread  # Para que el servidor y el bot funcionen a la vez

# --- SERVIDOR WEB (PARA MANTENERLO ACTIVO 24/7) ---
app = Flask('')

@app.route('/')
def home():
    return "¡El bot está vivo!"

def run_server():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    server_thread = Thread(target=run_server)
    server_thread.start()

# --- CONFIGURACIÓN DEL BOT ---

# ¡¡MUY IMPORTANTE!! Pon aquí el ID del rol que quieres que se asigne a los usuarios verificados.
VERIFIED_ROLE_ID = 1423271361253740574 # <-- ¡CAMBIA ESTE ID!

intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.message_content = True
intents.members = True # <-- Necesario para asignar roles

bot = commands.Bot(command_prefix="!", intents=intents)

# ---------- IDs del Sistema de Tickets ----------
CATEGORIES = {
    "postulación": 1423673954018656346,
    "jefatura": 1423681296961507512,
    "seguridad": 1423674061053104230,
    "soporte": 1423674186005614733
}
LOG_CHANNEL_ID = 1423271363136848005

# ---------- Plantilla de Postulación ----------
POSTULACION_TEMPLATE = """
📋 **Plantilla de Postulación:**

𝐄𝐝𝐚𝐝:
𝐇𝐨𝐫𝐚𝐬 𝐅𝐢𝐯𝐞𝐦 𝐜𝐨𝐧 𝐟𝐨𝐭𝐨 (+𝟖𝟓𝟎 𝐇𝐀𝐘 𝐄𝐗𝐂𝐄𝐏𝐂𝐈𝐎𝐍𝐄𝐒):
¿𝐄𝐧 𝐪𝐮𝐞 𝐛𝐚𝐧𝐝𝐚𝐬 𝐡𝐚𝐬 𝐞𝐬𝐭𝐚𝐝𝐨?:
𝐂𝐥𝐢𝐩𝐬 𝐦𝐢𝐧 𝟓/𝐇𝐠 (𝐡𝐚𝐲 𝐞𝐱𝐂𝐄𝐏𝐂𝐈𝐎𝐍𝐄𝐒):
𝐅𝐨𝐭𝐨 𝐊𝐃:
𝐇𝐨𝐫𝐚𝐬 𝐝𝐢𝐚𝐫𝐢𝐚𝐬 𝐪𝐮𝐞 𝐩𝐮𝐞𝐝𝐞𝐬 𝐣𝐮𝐠𝐚𝐫 𝐚𝐥 𝐝𝐢𝐚:
𝐓𝐢𝐞𝐧𝐞𝐬 𝐛𝐥𝐢𝐧𝐝𝐚𝐝𝐨 𝐨 𝐦𝐨𝐭𝐨:
"""
asumidos = {}

# --------------------------------------------------------------------------------
# --- SISTEMAS PERSISTENTES (VISTAS) ---
# --------------------------------------------------------------------------------

class VerificationView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Verificarte", style=discord.ButtonStyle.secondary, custom_id="verify_button", emoji="✅")
    async def verify_button_callback(self, interaction: discord.Interaction, button: Button):
        role = interaction.guild.get_role(VERIFIED_ROLE_ID)
        if role is None:
            await interaction.response.send_message("❌ Error: El rol de verificación no está configurado. Contacta a un administrador.", ephemeral=True)
            return
        if role in interaction.user.roles:
            await interaction.response.send_message("✅ Ya estás verificado.", ephemeral=True)
        else:
            await interaction.user.add_roles(role)
            await interaction.response.send_message("✅ ¡Has sido verificado correctamente!", ephemeral=True)

# --- SOLUCIÓN: Vista persistente para la creación de tickets ---
class TicketCreationView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.select(
        placeholder="Selecciona una opción para abrir un ticket",
        custom_id="ticket_creation_menu",
        options=[
            discord.SelectOption(label="Postulación", description="📝 Para postular a la mejor banda.", emoji="📝"),
            discord.SelectOption(label="Jefatura", description="🧠 Para hablar con una jefatura.", emoji="🧠"),
            discord.SelectOption(label="Seguridad", description="🛡️ Para temas de alianzas/seguridad.", emoji="🛡️"),
            discord.SelectOption(label="Soporte", description="🛠️ Para hablar con soporte.", emoji="🛠️")
        ]
    )
    async def select_callback(self, interaction: discord.Interaction, select: Select):
        tipo = select.values[0].lower()
        guild = interaction.guild
        category = guild.get_channel(CATEGORIES[tipo])

        # Comprobación por si la categoría ha sido borrada
        if category is None:
            await interaction.response.send_message("❌ Error: La categoría para este ticket no existe. Avisa a un administrador.", ephemeral=True)
            return

        # Evita que se creen tickets duplicados rápidamente
        for channel in category.text_channels:
            if channel.name == f"ticket-{tipo}-{interaction.user.name.lower()}":
                 await interaction.response.send_message(f"❌ Ya tienes un ticket de **{tipo}** abierto: {channel.mention}", ephemeral=True)
                 return

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        channel = await guild.create_text_channel(f"ticket-{tipo}-{interaction.user.name}", category=category, overwrites=overwrites)
        embed_ticket = discord.Embed(
            title=f"📂 Ticket de {tipo.capitalize()}",
            description="Por favor, explica tu caso abajo." if tipo != "postulación" else POSTULACION_TEMPLATE,
            color=0x2f3136
        )
        embed_ticket.set_footer(text=f"Solicitado por: {interaction.user}")
        view = TicketButtons(tipo, interaction.user)
        await channel.send(embed=embed_ticket, view=view)
        await interaction.response.send_message(f"✅ Ticket de **{tipo.capitalize()}** creado: {channel.mention}", ephemeral=True)


# --------------------------------------------------------------------------------
# --- COMANDOS ---
# --------------------------------------------------------------------------------

@bot.command()
@commands.has_permissions(administrator=True)
async def verificacion(ctx):
    embed = discord.Embed(
        title="VERIFICARTE",
        description="Para acceder al servidor, necesitas verificarte haciendo clic en el botón de abajo.",
        color=0x2f3136
    )
    embed.set_footer(text="© JB INFO")
    await ctx.send(embed=embed, view=VerificationView())

@bot.command()
@commands.has_permissions(administrator=True)
async def ticket(ctx):
    embed = discord.Embed(
        title="📩 Sistema de Tickets",
        description=(
            "📌 Para postular a la mejor banda de KRNL PVP, selecciona 📝 **Postulación**.\n"
            "📌 Para hablar con una jefatura selecciona 🧠 **Jefatura**.\n"
            "📌 Para abrir ticket de cualquier tipo de alianza/seguridad selecciona 🛡️ **Seguridad**.\n"
            "📌 Para hablar con soporte selecciona 🛠️ **Soporte**."
        ),
        color=0x2f3136
    )
    embed.set_footer(text="El mejor sistema de tickets putaamaaaas")
    embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1423271362750976091/1423650841503731772/37f183bd-60d8-44dc-8408-b686aaad4791.png?ex=68e115aa&is=68dfc42a&hm=df0387036c717bbb540831913a67e6cddf9ff6489525ceab3b3bf54fd5aa50f6&")
    embed.set_image(url="https://cdn.discordapp.com/attachments/1423271362750976091/1423650841503731772/37f183bd-60d8-44dc-8408-b686aaad4791.png?ex=68e115aa&is=68dfc42a&hm=df0387036c717bbb540831913a67e6cddf9ff6489525ceab3b3bf54fd5aa50f6&")
    
    # Ahora usamos la vista persistente
    await ctx.send(embed=embed, view=TicketCreationView())

# --------------------------------------------------------------------------------
# --- CÓDIGO DE GESTIÓN DE TICKETS (SIN CAMBIOS) ---
# --------------------------------------------------------------------------------

class TicketButtons(View):
    def __init__(self, tipo, autor):
        super().__init__(timeout=None)
        self.tipo = tipo
        self.autor = autor

    @discord.ui.button(label="Cerrar Ticket", style=discord.ButtonStyle.danger)
    async def cerrar(self, interaction: discord.Interaction, button: Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Solo un administrador puede cerrar tickets.", ephemeral=True)
            return

        confirm = discord.Embed(
            title="⚠️ Confirmar cierre",
            description="¿Estás seguro de que quieres cerrar este ticket?",
            color=0xff0000
        )
        view = View()
        async def confirmar_callback(i):
            if i.user.guild_permissions.administrator:
                messages = []
                async for msg in interaction.channel.history(limit=None, oldest_first=True):
                    messages.append(f"{msg.author}: {msg.content}")
                transcript = "\n".join(messages) if messages else "Sin mensajes."

                file = discord.File(io.BytesIO(transcript.encode()), filename=f"transcript-{interaction.channel.name}.txt")
                log_channel = bot.get_channel(LOG_CHANNEL_ID)
                embed_log = discord.Embed(
                    title="📕 Ticket cerrado",
                    description=f"Ticket **{interaction.channel.name}** cerrado por {interaction.user.mention}",
                    color=0xff0000
                )
                await log_channel.send(embed=embed_log, file=file)
                await interaction.channel.delete()
            else:
                await i.response.send_message("❌ No tienes permisos.", ephemeral=True)

        confirm_button = Button(label="Confirmar", style=discord.ButtonStyle.danger)
        confirm_button.callback = confirmar_callback
        view.add_item(confirm_button)
        await interaction.response.send_message(embed=confirm, view=view, ephemeral=True)
    
    @discord.ui.button(label="Asumir", style=discord.ButtonStyle.secondary)
    async def asumir(self, interaction: discord.Interaction, button: Button):
        if interaction.channel.id in asumidos:
            await interaction.response.send_message("⚠️ Este ticket ya fue asumido.", ephemeral=True)
            return
        asumidos[interaction.channel.id] = interaction.user.id
        await interaction.channel.edit(name=f"{self.tipo}-{self.autor.name}")
        await interaction.response.send_message(f"👤 Ticket asumido por {interaction.user.mention}", ephemeral=False)

    @discord.ui.button(label="Añadir miembro", style=discord.ButtonStyle.success)
    async def add_member(self, interaction: discord.Interaction, button: Button):
        modal = AddMemberModal(interaction.channel)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Sacar persona", style=discord.ButtonStyle.secondary)
    async def remove_member(self, interaction: discord.Interaction, button: Button):
        modal = RemoveMemberModal(interaction.channel)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Renombrar Ticket", style=discord.ButtonStyle.primary)
    async def rename_ticket(self, interaction: discord.Interaction, button: Button):
        modal = RenameTicketModal(interaction.channel)
        await interaction.response.send_modal(modal)

class AddMemberModal(Modal, title="Añadir miembro al Ticket"):
    user_id = TextInput(label="ID del usuario", style=discord.TextStyle.short)
    def __init__(self, channel):
        super().__init__()
        self.channel = channel
    async def on_submit(self, interaction: discord.Interaction):
        try:
            member_id = int(self.user_id.value)
            member = await interaction.guild.fetch_member(member_id)
            await self.channel.set_permissions(member, read_messages=True, send_messages=True)
            await interaction.response.send_message(f"✅ {member.mention} añadido al ticket.", ephemeral=True)
        except (ValueError, discord.NotFound):
            await interaction.response.send_message("❌ ID de usuario no válido.", ephemeral=True)

class RemoveMemberModal(Modal, title="Sacar miembro del Ticket"):
    user_id = TextInput(label="ID del usuario", style=discord.TextStyle.short)
    def __init__(self, channel):
        super().__init__()
        self.channel = channel
    async def on_submit(self, interaction: discord.Interaction):
        try:
            member_id = int(self.user_id.value)
            member = await interaction.guild.fetch_member(member_id)
            await self.channel.set_permissions(member, overwrite=None)
            await interaction.response.send_message(f"❌ {member.mention} eliminado del ticket.", ephemeral=True)
        except (ValueError, discord.NotFound):
            await interaction.response.send_message("❌ ID de usuario no válido.", ephemeral=True)

class RenameTicketModal(Modal, title="Renombrar Ticket"):
    new_name = TextInput(label="Nuevo nombre del canal", style=discord.TextStyle.short)
    def __init__(self, channel):
        super().__init__()
        self.channel = channel
    async def on_submit(self, interaction: discord.Interaction):
        await self.channel.edit(name=self.new_name.value)
        await interaction.response.send_message(f"✏️ Ticket renombrado a **{self.new_name.value}**", ephemeral=True)

# --------------------------------------------------------------------------------
# --- EVENTOS Y ARRANQUE ---
# --------------------------------------------------------------------------------

@bot.event
async def on_ready():
    # SOLUCIÓN: Registramos ambas vistas para que sean persistentes.
    bot.add_view(VerificationView())
    bot.add_view(TicketCreationView()) 
    print(f"✅ Bot conectado como {bot.user}")

if __name__ == "__main__":
    keep_alive()
    try:
        token = os.environ.get("DISCORD_TOKEN")
        if token is None:
            print("❌ ERROR: El token no está configurado.")
            print("Asegúrate de crear la variable 'DISCORD_TOKEN' en tu hosting.")
        else:
            bot.run(token)
    except discord.errors.LoginFailure:
        print("❌ ERROR: El token proporcionado es inválido.")

