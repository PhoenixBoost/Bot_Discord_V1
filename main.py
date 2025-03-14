from My_Server import server_on
import os
import discord
from discord.ext import commands
from discord import app_commands, ui
from datetime import datetime, timezone
from dotenv import load_dotenv
from discord.ext import tasks

# ✅ เปิด Intents เพื่อให้บอทเข้าถึงข้อมูลสมาชิกและข้อความ
intents = discord.Intents.default()
intents.members = True  # เปิดการติดตามสมาชิกใหม่
intents.message_content = True  # เปิดให้บอทเข้าถึงข้อความในเซิร์ฟเวอร์ (สำคัญ!)

# ✅ ใช้ reconnect=True เพื่อให้บอทพยายามเชื่อมต่อใหม่อัตโนมัติ
bot = commands.Bot(command_prefix="!", intents=intents, reconnect=True)

# ตั้งค่า ID ของช่องและบทบาท
WELCOME_CHANNEL_ID = 1309509732695806023  # ช่องต้อนรับ
WELCOME_ROLE_ID = 1306502186783473707  # บทบาทต้อนรับ
ANNOUNCEMENT_CHANNEL_ID = 1349837451220484266  # ช่องสำหรับประกาศ
invite_cache = {}  # แคชเก็บจำนวนการใช้ลิงก์เชิญ

# ✅ โหลดข้อมูลลิงก์เชิญเมื่อบอทเริ่มทำงาน
@bot.event
async def on_ready():
    global invite_cache
    if not auto_announcement.is_running():
        auto_announcement.start()
    for guild in bot.guilds:
        invites = await guild.invites()
        invite_cache[guild.id] = {invite.code: invite.uses for invite in invites}

    print(f"✅ บอทออนไลน์แล้ว: {bot.user}")

# ✅ ตรวจสอบว่าลิงก์เชิญไหนถูกใช้
@bot.event
async def on_member_join(member):
    global invite_cache
    guild = member.guild
    channel = guild.get_channel(WELCOME_CHANNEL_ID)

    # ดึงข้อมูลลิงก์เชิญล่าสุด
    invites = await guild.invites()
    used_invite = None

    # หา invite ที่ถูกใช้ (จำนวน uses เพิ่มขึ้น)
    for invite in invites:
        if invite_cache.get(guild.id, {}).get(invite.code, 0) < invite.uses:
            used_invite = invite
            break

    # อัปเดตแคช
    invite_cache[guild.id] = {invite.code: invite.uses for invite in invites}

    # ตั้งค่าข้อความเชิญ
    invite_info = f"🔗 ลิงก์เชิญที่ใช้: `{used_invite.url}` โดย `{used_invite.inviter}`" if used_invite else "❌ ไม่พบลิงก์เชิญ"

    # แจก Role ต้อนรับ
    role = guild.get_role(WELCOME_ROLE_ID)
    if role:
        try:
            await member.add_roles(role)
        except discord.Forbidden:
            print(f"❌ Bot ไม่มีสิทธิ์เพิ่ม Role {role.name}")
        except discord.HTTPException as e:
            print(f"❌ ไม่สามารถเพิ่ม Role ได้: {e}")

    # ส่งข้อความต้อนรับ
    if channel:
        join_time = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M:%S UTC")
        embed = discord.Embed(
            title="👋 ยินดีต้อนรับสู่เซิร์ฟเวอร์!",
            description=(
                f"**ชื่อผู้ใช้:** {member.name}\n"
                f"**แท็ก:** {member.mention}\n"
                f"**เข้าร่วมเมื่อ:** {join_time}\n"
                f"{invite_info}"
            ),
            color=discord.Color.green()
        )
        embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
        await channel.send(embed=embed)

# ✅ คำสั่ง `/clear` เพื่อล้างข้อความ
@bot.tree.command(name="clear", description="🧹 ล้างข้อความในช่องแชท")
async def clear(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    deleted_messages = await interaction.channel.purge()
    await interaction.followup.send(f"✅ ล้างช่องแชทแล้ว ({len(deleted_messages)} ข้อความถูกลบ)", ephemeral=True)

# ✅ คำสั่ง `/chat` เพื่อสร้างประกาศ
class AnnouncementModal(ui.Modal, title="📢 ประกาศจากทีมงาน"):
    title_input = ui.TextInput(label="หัวข้อ", placeholder="พิมพ์หัวข้อที่นี่")
    description_input = ui.TextInput(label="รายละเอียด", style=discord.TextStyle.paragraph, placeholder="พิมพ์รายละเอียดที่นี่")
    color_input = ui.TextInput(label="สี Embed (Hex Code เช่น #FF0000)", placeholder="#7289DA", required=False)
    image_url_input = ui.TextInput(label="ลิงก์รูปภาพ (ไม่บังคับ)", placeholder="https://...", required=False)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            color = discord.Color(int(self.color_input.value.replace('#', ''), 16)) if self.color_input.value else discord.Color.random()
        except:
            color = discord.Color.random()

        embed = discord.Embed(
            title=self.title_input.value,
            description=self.description_input.value,
            color=color
        )
        if self.image_url_input.value:
            embed.set_image(url=self.image_url_input.value)

        await interaction.response.send_message(embed=embed)

# ✅ ฟังก์ชันโพสต์ข้อความประกาศอัตโนมัติทุก 1 ชั่วโมง
@tasks.loop(hours=1)  # เปลี่ยนเป็น 1 ชั่วโมง
async def auto_announcement():
    channel = bot.get_channel(ANNOUNCEMENT_CHANNEL_ID)
    if channel:
        embed = discord.Embed(
            title="🔥 **จำหน่ายรหัส VALORANT ราคาถูก!** 🔥",
            description=(
                "🔹 **ทั้งเปลี่ยนได้ และ เปลี่ยนไม่ได้**\n"
                "🚀 **รวมถึงบริการรับ Boost Rank**\n"
                "💬 **สนใจติดต่อ** <@&1294266042993868863>"
            ),
            color=discord.Color.red()
        )
        embed.set_thumbnail(url="https://media.discordapp.net/attachments/1349784034242203711/1349949802426667099/Hacker.png?ex=67d4f639&is=67d3a4b9&hm=e95ade2b98076c37e5ae2460a0b1ac6c0e411ce360e99455bd7443f6c2b47dab&=&format=webp&quality=lossless&width=256&height=256")  # เพิ่ม URL รูปภาพที่เกี่ยวข้อง
        await channel.send(embed=embed)
    else:
        print("❌ ไม่พบช่องประกาศ!")

# ✅ คำสั่ง `/announce` ให้แอดมินโพสต์ประกาศทันที
@bot.tree.command(name="announce", description="📢 โพสต์ประกาศทันที")
async def announce(interaction: discord.Interaction):
    admin_role = interaction.guild.get_role(1294266042993868863)  # ID ของ Role แอดมิน
    if admin_role and admin_role in interaction.user.roles:
        channel = interaction.guild.get_channel(ANNOUNCEMENT_CHANNEL_ID)
        if channel:
            embed = discord.Embed(
                title="🔥 **จำหน่ายรหัส VALORANT ราคาถูก!** 🔥",
                description=(
                    "🔹 **ทั้งเปลี่ยนได้ และ เปลี่ยนไม่ได้**\n"
                    "🚀 **รวมถึงบริการรับ Boost Rank**\n"
                    "💬 **สนใจติดต่อ** <@&1294266042993868863>"
                ),
                color=discord.Color.red()
            )
            embed.set_thumbnail(url="https://media.discordapp.net/attachments/1349784034242203711/1349949802426667099/Hacker.png?ex=67d4f639&is=67d3a4b9&hm=e95ade2b98076c37e5ae2460a0b1ac6c0e411ce360e99455bd7443f6c2b47dab&=&format=webp&quality=lossless&width=256&height=256")
            await channel.send(embed=embed)
            await interaction.response.send_message("✅ ประกาศถูกโพสต์เรียบร้อย!", ephemeral=True)
        else:
            await interaction.response.send_message("❌ ไม่พบช่องประกาศ!", ephemeral=True)
    else:
        await interaction.response.send_message("❌ คุณไม่มีสิทธิ์ใช้คำสั่งนี้", ephemeral=True)

@bot.tree.command(name="chat", description="📢 สร้างประกาศใหม่")
async def chat(interaction: discord.Interaction):
    admin_role = interaction.guild.get_role(1294266042993868863)
    if admin_role and admin_role in interaction.user.roles:
        await interaction.response.send_modal(AnnouncementModal())
    else:
        await interaction.response.send_message("❌ คุณไม่มีสิทธิ์ใช้งานคำสั่งนี้", ephemeral=True)

# ✅ คำสั่ง `/test_welcome` เพื่อลองทดสอบข้อความต้อนรับ
@bot.tree.command(name="test_welcome", description="🔍 ทดสอบข้อความต้อนรับ")
async def test_welcome(interaction: discord.Interaction):
    channel = interaction.guild.get_channel(WELCOME_CHANNEL_ID)
    if channel:
        join_time = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M:%S UTC")
        embed = discord.Embed(
            title="👋 ยินดีต้อนรับ!",
            description=f"**ชื่อผู้ใช้:** {interaction.user.name}\n**แท็ก:** {interaction.user.mention}\n**เข้าร่วมเมื่อ:** {join_time}",
            color=discord.Color.green()
        )
        embed.set_thumbnail(url=interaction.user.avatar.url if interaction.user.avatar else interaction.user.default_avatar.url)
        await channel.send(embed=embed)

    await interaction.response.send_message("✅ ทดสอบข้อความต้อนรับสำเร็จ!", ephemeral=True)

# ✅ รันบอท
server_on()
bot.run(os.getenv('TOKEN'))