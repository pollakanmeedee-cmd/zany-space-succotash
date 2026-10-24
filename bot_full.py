import os
import json
import asyncio
from typing import Optional

import discord
from discord import app_commands

# ====== ตั้งค่า (environment variables) ======
TOKEN = os.getenv("DISCORD_TOKEN")
DISCORD_GUILD_ID = int(os.getenv("DISCORD_GUILD_ID", "1310186510921764866"))
TICKET_CATEGORY_ID = int(os.getenv("TICKET_CATEGORY_ID", 0))   # หมวดหมู่ที่จะสร้าง ticket (ไม่ใส่ก็ได้)
SUPPORT_ROLE_ID = int(os.getenv("SUPPORT_ROLE_ID", 0))         # ยศทีมงานที่เห็น ticket (ไม่ใส่ก็ได้)

intents = discord.Intents.default()
intents.members = True  # ต้องเปิด Server Members Intent ใน Developer Portal
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)


@client.event
async def on_ready():
    if DISCORD_GUILD_ID:
        guild = discord.Object(id=DISCORD_GUILD_ID)
        tree.copy_global_to(guild=guild)
        tree.clear_commands(guild=None)
        await tree.sync()
        synced = await tree.sync(guild=guild)
        print(f"Sync {len(synced)} คำสั่งเข้าเซิร์ฟเวอร์ {DISCORD_GUILD_ID} แล้ว")
    else:
        synced = await tree.sync()
        print(f"Sync {len(synced)} คำสั่งแบบ global แล้ว")
    print(f"ล็อกอินเป็น {client.user}")


# ====== ปุ่มทั้งหมด (ticket / role) ======
@client.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type != discord.InteractionType.component:
        return
    cid = interaction.data.get("custom_id", "")
    if cid == "ticket:open":
        await open_ticket(interaction)
    elif cid == "ticket:close":
        await close_ticket(interaction)
    elif cid.startswith("role:"):
        await toggle_role(interaction, int(cid[5:]))


# ====== WELCOME ======
CONFIG_FILE = "welcome.json"

DEFAULT_WELCOME = {
    "channel": 0,
    "title": "ยินดีต้อนรับเข้าสู่ {server}",
    "description": (
        "| ยินดีต้อนรับเข้าสู่เซิร์ฟเวอร์ {server}\n"
        "| คุณ {user} คุณเป็นคนที่ {count}\n"
        "| สามารถรับยศได้ที่ห้อง <#ใส่ไอดีห้อง> ✅"
    ),
    "color": "#F58CE8",
    "image": "",
}

DEFAULT_TICKET = {
    "ticket_category": TICKET_CATEGORY_ID,
    "ticket_support_role": SUPPORT_ROLE_ID,
    "ticket_panel_title": "🎫 ติดต่อทีมงาน",
    "ticket_panel_description": "กดปุ่มด้านล่างเพื่อเปิด ticket",
    "ticket_panel_color": "#5865F2",
    "ticket_open_message": "{user} {support} อธิบายปัญหาของคุณได้เลย ทีมงานจะมาตอบเร็วๆ นี้",
}

DEFAULT_ROLE_PANEL = {
    "role_panel_title": "🎭 รับยศ",
    "role_panel_description": "กดปุ่มเพื่อรับยศ / กดซ้ำเพื่อถอดยศ",
    "role_panel_color": "#F1C40F",
    "role_panel_image": "",
    "role_panel_footer": "",
}


def load_config() -> dict:
    try:
        with open(CONFIG_FILE, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def save_config(cfg: dict):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def get_conf(guild_id: int) -> dict:
    return {**DEFAULT_WELCOME, **load_config().get(str(guild_id), {})}


def get_ticket_conf(guild_id: int) -> dict:
    return {**DEFAULT_TICKET, **load_config().get(str(guild_id), {})}


def get_role_panel_conf(guild_id: int) -> dict:
    return {**DEFAULT_ROLE_PANEL, **load_config().get(str(guild_id), {})}


def update_conf(guild_id: int, **values):
    cfg = load_config()
    cfg.setdefault(str(guild_id), {}).update(values)
    save_config(cfg)


def build_welcome_embed(member: discord.Member, conf: dict) -> discord.Embed:
    guild = member.guild

    def fill(text: str) -> str:
        return (text.replace("{user}", member.mention)
                    .replace("{name}", member.display_name)
                    .replace("{server}", guild.name)
                    .replace("{count}", str(guild.member_count)))

    try:
        color = discord.Color(int(conf["color"].lstrip("#"), 16))
    except ValueError:
        color = discord.Color.pink()
    embed = discord.Embed(title=fill(conf["title"]), description=fill(conf["description"]), color=color)
    if conf.get("image"):
        embed.set_image(url=conf["image"])
    return embed


class WelcomeModal(discord.ui.Modal, title="ตกแต่งข้อความ Welcome"):
    def __init__(self, conf: dict):
        super().__init__()
        self.title_in = discord.ui.TextInput(
            label="หัวข้อ", default=conf["title"], max_length=256)
        self.desc_in = discord.ui.TextInput(
            label="ข้อความ", style=discord.TextStyle.paragraph,
            default=conf["description"], max_length=2000)
        self.color_in = discord.ui.TextInput(
            label="สี (hex เช่น #F58CE8)", default=conf["color"], max_length=7)
        self.image_in = discord.ui.TextInput(
            label="ลิงก์รูปภาพ (ไม่ใส่ก็ได้)", default=conf["image"], required=False)
        for item in (self.title_in, self.desc_in, self.color_in, self.image_in):
            self.add_item(item)

    async def on_submit(self, interaction: discord.Interaction):
        update_conf(
            interaction.guild.id,
            title=self.title_in.value,
            description=self.desc_in.value,
            color=self.color_in.value,
            image=self.image_in.value,
        )
        await interaction.response.send_message(
            "บันทึกแล้ว ลอง `/welcometest` เพื่อดูตัวอย่าง", ephemeral=True)


class TicketEditModal(discord.ui.Modal, title="ตกแต่ง Ticket"):
    def __init__(self, conf: dict):
        super().__init__()
        self.panel_title = discord.ui.TextInput(
            label="หัวข้อแผง Ticket", default=conf["ticket_panel_title"], max_length=256)
        self.panel_description = discord.ui.TextInput(
            label="ข้อความบนแผง", style=discord.TextStyle.paragraph,
            default=conf["ticket_panel_description"], max_length=1000)
        self.panel_color = discord.ui.TextInput(
            label="สีแผง (hex เช่น #5865F2)", default=conf["ticket_panel_color"], max_length=7)
        self.open_message = discord.ui.TextInput(
            label="ข้อความในห้อง Ticket", style=discord.TextStyle.paragraph,
            default=conf["ticket_open_message"], max_length=1000)
        for item in (self.panel_title, self.panel_description, self.panel_color, self.open_message):
            self.add_item(item)

    async def on_submit(self, interaction: discord.Interaction):
        color = self.panel_color.value.strip().lstrip("#")
        if len(color) != 6 or any(char not in "0123456789abcdefABCDEF" for char in color):
            return await interaction.response.send_message(
                "กรุณาใส่สี Hex 6 หลัก เช่น #5865F2", ephemeral=True)
        update_conf(
            interaction.guild.id,
            ticket_panel_title=self.panel_title.value,
            ticket_panel_description=self.panel_description.value,
            ticket_panel_color=f"#{color.upper()}",
            ticket_open_message=self.open_message.value,
        )
        await interaction.response.send_message(
            "บันทึกแล้ว ใช้ `/ticketpanel` เพื่อส่งแผงที่อัปเดต", ephemeral=True)


class EmbedCreateModal(discord.ui.Modal, title="สร้าง Embed"):
    def __init__(self, channel: discord.TextChannel, image_url: str = ""):
        super().__init__()
        self.channel = channel
        self.title_in = discord.ui.TextInput(
            label="หัวข้อ", required=False, max_length=256)
        self.description_in = discord.ui.TextInput(
            label="ข้อความ (รองรับ Markdown)", style=discord.TextStyle.paragraph,
            max_length=4000)
        self.color_in = discord.ui.TextInput(
            label="สี Hex เช่น #5865F2", default="#5865F2", max_length=7)
        self.image_in = discord.ui.TextInput(
            label="ลิงก์รูปภาพ (ไม่ใส่ก็ได้)", default=image_url, required=False, max_length=4000)
        self.footer_in = discord.ui.TextInput(
            label="Footer (ไม่ใส่ก็ได้)", required=False, max_length=2048)
        for item in (self.title_in, self.description_in, self.color_in, self.image_in, self.footer_in):
            self.add_item(item)

    async def on_submit(self, interaction: discord.Interaction):
        color = self.color_in.value.strip().lstrip("#")
        if len(color) != 6 or any(char not in "0123456789abcdefABCDEF" for char in color):
            return await interaction.response.send_message(
                "กรุณาใส่สี Hex 6 หลัก เช่น #5865F2", ephemeral=True)

        embed = discord.Embed(
            title=self.title_in.value or None,
            description=self.description_in.value,
            color=discord.Color(int(color, 16)),
        )
        if self.image_in.value:
            embed.set_image(url=self.image_in.value)
        if self.footer_in.value:
            embed.set_footer(text=self.footer_in.value)
        try:
            await self.channel.send(embed=embed)
        except discord.Forbidden:
            return await interaction.response.send_message(
                "บอทไม่มีสิทธิ์ส่งข้อความหรือ Embed ในห้องนี้", ephemeral=True)
        except discord.HTTPException:
            return await interaction.response.send_message(
                "ส่ง Embed ไม่สำเร็จ กรุณาตรวจสอบข้อความและลิงก์รูปภาพ", ephemeral=True)
        await interaction.response.send_message(
            f"ส่ง Embed ไปที่ {self.channel.mention} แล้ว", ephemeral=True)


@tree.command(name="setwelcome", description="เลือกห้องที่จะส่งข้อความ welcome")
@app_commands.default_permissions(manage_guild=True)
async def setwelcome(interaction: discord.Interaction, channel: discord.TextChannel):
    update_conf(interaction.guild.id, channel=channel.id)
    await interaction.response.send_message(f"ตั้งห้อง welcome เป็น {channel.mention} แล้ว", ephemeral=True)


@tree.command(name="welcomeedit", description="ตกแต่งข้อความ welcome")
@app_commands.default_permissions(manage_guild=True)
async def welcomeedit(interaction: discord.Interaction):
    await interaction.response.send_modal(WelcomeModal(get_conf(interaction.guild.id)))


@tree.command(name="welcometest", description="ดูตัวอย่างข้อความ welcome")
@app_commands.default_permissions(manage_guild=True)
async def welcometest(interaction: discord.Interaction):
    embed = build_welcome_embed(interaction.user, get_conf(interaction.guild.id))
    await interaction.response.send_message(embed=embed, ephemeral=True)


@tree.command(name="embed", description="สร้าง Embed แบบกำหนดข้อความและรูปแบบได้")
@app_commands.default_permissions(manage_messages=True)
async def create_embed(
    interaction: discord.Interaction,
    channel: discord.TextChannel,
    image: Optional[discord.Attachment] = None,
):
    if image and image.content_type and not image.content_type.startswith("image/"):
        return await interaction.response.send_message(
            "กรุณาแนบไฟล์รูปภาพเท่านั้น", ephemeral=True)
    await interaction.response.send_modal(EmbedCreateModal(channel, image.url if image else ""))


@client.event
async def on_member_join(member: discord.Member):
    conf = get_conf(member.guild.id)
    ch = member.guild.get_channel(conf["channel"]) or member.guild.system_channel
    if ch:
        await ch.send(embed=build_welcome_embed(member, conf))


# ====== TICKET ======
@tree.command(name="ticketsetup", description="ตั้งหมวดหมู่และยศทีมงานของ ticket")
@app_commands.default_permissions(administrator=True)
async def ticketsetup(
    interaction: discord.Interaction,
    category: discord.CategoryChannel,
    support_role: Optional[discord.Role] = None,
):
    values = {"ticket_category": category.id}
    if support_role:
        values["ticket_support_role"] = support_role.id
    update_conf(interaction.guild.id, **values)
    role_text = f" และตั้งยศทีมงานเป็น {support_role.mention}" if support_role else ""
    await interaction.response.send_message(
        f"ตั้งหมวดหมู่สร้าง ticket เป็น {category.name}{role_text} แล้ว", ephemeral=True)


@tree.command(name="ticketedit", description="แก้ไขข้อความและสีของแผง ticket")
@app_commands.default_permissions(administrator=True)
async def ticketedit(interaction: discord.Interaction):
    await interaction.response.send_modal(TicketEditModal(get_ticket_conf(interaction.guild.id)))


@tree.command(name="ticketpanel", description="ส่งแผงเปิด ticket (แอดมิน)")
@app_commands.default_permissions(administrator=True)
async def ticketpanel(
    interaction: discord.Interaction,
    channel: Optional[discord.TextChannel] = None,
):
    conf = get_ticket_conf(interaction.guild.id)
    try:
        color = discord.Color(int(conf["ticket_panel_color"].lstrip("#"), 16))
    except ValueError:
        color = discord.Color.blurple()
    embed = discord.Embed(
        title=conf["ticket_panel_title"],
        description=conf["ticket_panel_description"],
        color=color,
    )
    view = discord.ui.View(timeout=None)
    view.add_item(discord.ui.Button(
        label="เปิด Ticket", emoji="🎫",
        style=discord.ButtonStyle.primary, custom_id="ticket:open"))
    if channel:
        await channel.send(embed=embed, view=view)
        await interaction.response.send_message(f"ส่งแผง ticket ที่ {channel.mention} แล้ว", ephemeral=True)
    else:
        await interaction.response.send_message(embed=embed, view=view)


async def open_ticket(interaction: discord.Interaction):
    guild, user = interaction.guild, interaction.user
    for ch in guild.text_channels:
        if ch.topic == f"ticket:{user.id}":
            return await interaction.response.send_message(
                f"คุณมี ticket อยู่แล้ว: {ch.mention}", ephemeral=True)

    conf = get_ticket_conf(guild.id)
    support_role_id = conf.get("ticket_support_role") or SUPPORT_ROLE_ID
    support = guild.get_role(support_role_id) if support_role_id else None
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        user: discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True),
        guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True),
    }
    if support:
        overwrites[support] = discord.PermissionOverwrite(view_channel=True, send_messages=True)

    category_id = conf.get("ticket_category") or TICKET_CATEGORY_ID
    category = guild.get_channel(category_id) if category_id else None
    channel = await guild.create_text_channel(
        f"ticket-{user.name}", overwrites=overwrites,
        category=category, topic=f"ticket:{user.id}")

    view = discord.ui.View(timeout=None)
    view.add_item(discord.ui.Button(
        label="ปิด Ticket", emoji="🔒",
        style=discord.ButtonStyle.danger, custom_id="ticket:close"))
    mention = f" {support.mention}" if support else ""
    opening_message = conf["ticket_open_message"].replace(
        "{user}", user.mention).replace("{support}", support.mention if support else "").strip()
    await channel.send(opening_message, view=view)
    await interaction.response.send_message(f"เปิด ticket แล้ว: {channel.mention}", ephemeral=True)


async def close_ticket(interaction: discord.Interaction):
    ch = interaction.channel
    if not (ch.topic or "").startswith("ticket:"):
        return
    owner_id = int(ch.topic.split(":")[1])
    user = interaction.user
    support = interaction.guild.get_role(SUPPORT_ROLE_ID)
    allowed = (
        user.id == owner_id
        or user.guild_permissions.manage_channels
        or (support and support in user.roles)
    )
    if not allowed:
        return await interaction.response.send_message("คุณไม่มีสิทธิ์ปิด ticket นี้", ephemeral=True)
    await interaction.response.send_message("กำลังปิด ticket ใน 5 วินาที...")
    await asyncio.sleep(5)
    await ch.delete()


# ====== ROLE (กดรับยศ) ======
@tree.command(name="rolepanel", description="ส่งแผงกดรับยศ (แอดมิน)")
@app_commands.default_permissions(administrator=True)
async def rolepanel(
    interaction: discord.Interaction,
    role1: discord.Role,
    role2: Optional[discord.Role] = None,
    role3: Optional[discord.Role] = None,
    role4: Optional[discord.Role] = None,
    role5: Optional[discord.Role] = None,
    channel: Optional[discord.TextChannel] = None,
):
    roles = [r for r in (role1, role2, role3, role4, role5) if r]
    conf = get_role_panel_conf(interaction.guild.id)
    color_value = conf["role_panel_color"].strip().lstrip("#")
    try:
        color = discord.Color(int(color_value, 16))
    except ValueError:
        color = discord.Color.gold()
    embed = discord.Embed(
        title=conf["role_panel_title"],
        description=conf["role_panel_description"],
        color=color,
    )
    if conf["role_panel_image"]:
        embed.set_image(url=conf["role_panel_image"])
    if conf["role_panel_footer"]:
        embed.set_footer(text=conf["role_panel_footer"])
    view = discord.ui.View(timeout=None)
    for r in roles:
        view.add_item(discord.ui.Button(
            label=r.name, style=discord.ButtonStyle.secondary, custom_id=f"role:{r.id}"))
    if channel:
        await channel.send(embed=embed, view=view)
        await interaction.response.send_message(
            f"ส่งแผงรับยศที่ {channel.mention} แล้ว", ephemeral=True)
    else:
        await interaction.response.send_message(embed=embed, view=view)


class RolePanelEditModal(discord.ui.Modal, title="ตกแต่งแผงรับยศ"):
    def __init__(self, conf: dict, image_url: Optional[str] = None):
        super().__init__()
        self.title_in = discord.ui.TextInput(
            label="หัวข้อ", default=conf["role_panel_title"], max_length=256)
        self.description_in = discord.ui.TextInput(
            label="ข้อความ", style=discord.TextStyle.paragraph,
            default=conf["role_panel_description"], max_length=1000)
        self.color_in = discord.ui.TextInput(
            label="สี Hex เช่น #F1C40F", default=conf["role_panel_color"], max_length=7)
        self.image_in = discord.ui.TextInput(
            label="ลิงก์รูปภาพ (ไม่ใส่ก็ได้)",
            default=image_url if image_url is not None else conf["role_panel_image"],
            required=False, max_length=4000)
        self.footer_in = discord.ui.TextInput(
            label="Footer (ไม่ใส่ก็ได้)", default=conf["role_panel_footer"],
            required=False, max_length=2048)
        for item in (self.title_in, self.description_in, self.color_in, self.image_in, self.footer_in):
            self.add_item(item)

    async def on_submit(self, interaction: discord.Interaction):
        color = self.color_in.value.strip().lstrip("#")
        if len(color) != 6 or any(char not in "0123456789abcdefABCDEF" for char in color):
            return await interaction.response.send_message(
                "กรุณาใส่สี Hex 6 หลัก เช่น #F1C40F", ephemeral=True)
        update_conf(
            interaction.guild.id,
            role_panel_title=self.title_in.value,
            role_panel_description=self.description_in.value,
            role_panel_color=f"#{color.upper()}",
            role_panel_image=self.image_in.value,
            role_panel_footer=self.footer_in.value,
        )
        await interaction.response.send_message(
            "บันทึกแล้ว ใช้ `/rolepanel` เพื่อส่งแผงที่อัปเดต", ephemeral=True)


@tree.command(name="roleedit", description="ตกแต่งข้อความและรูปของแผงรับยศ")
@app_commands.default_permissions(administrator=True)
async def roleedit(
    interaction: discord.Interaction,
    image: Optional[discord.Attachment] = None,
):
    if image and image.content_type and not image.content_type.startswith("image/"):
        return await interaction.response.send_message(
            "กรุณาแนบไฟล์รูปภาพเท่านั้น", ephemeral=True)
    await interaction.response.send_modal(
        RolePanelEditModal(
            get_role_panel_conf(interaction.guild.id), image.url if image else None))


async def toggle_role(interaction: discord.Interaction, role_id: int):
    role = interaction.guild.get_role(role_id)
    if not role:
        return await interaction.response.send_message("ไม่พบยศนี้แล้ว", ephemeral=True)
    member = interaction.user
    try:
        if role in member.roles:
            await member.remove_roles(role)
            msg = f"ถอดยศ **{role.name}** แล้ว"
        else:
            await member.add_roles(role)
            msg = f"รับยศ **{role.name}** แล้ว"
    except discord.Forbidden:
        msg = "บอทไม่มีสิทธิ์ให้ยศนี้ (ย้ายยศบอทให้อยู่สูงกว่ายศที่แจก)"
    await interaction.response.send_message(msg, ephemeral=True)


if not TOKEN:
    raise SystemExit("Missing DISCORD_TOKEN environment variable")

client.run(TOKEN)
