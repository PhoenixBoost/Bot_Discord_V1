import os
import discord
from discord.ext import commands, tasks
from discord import ui
from datetime import datetime, timezone, timedelta
import asyncio
from discord import Embed
import json
import re
from discord.ui import Modal, TextInput
from My_Server import server_on

# ✅ กำหนด Intents เพื่อให้บอทเข้าถึงข้อมูลสมาชิกและข้อความ
intents = discord.Intents.default()
intents.members = True  # ติดตามสมาชิกใหม่
intents.message_content = True  # อนุญาตให้บอทเข้าถึงข้อความในช่อง

# ✅ สร้างบอทและตั้งค่า reconnect=True เพื่อให้บอทพยายามเชื่อมต่อใหม่อัตโนมัติ
bot = commands.Bot(command_prefix="!", intents=intents, reconnect=True)

# ช่องและ ID ของบทบาท
WELCOME_CHANNEL_ID = 1309509732695806023  # ช่องต้อนรับ
WELCOME_ROLE_ID = 1306502186783473707  # บทบาทต้อนรับ
ANNOUNCEMENT_CHANNEL_ID = 1349837451220484266  # ช่องสำหรับประกาศ
ADMIN_ROLE_ID = 1294266042993868863  # ID ของบทบาทแอดมิน

# ตัวแปรเก็บ ID ของข้อความประกาศล่าสุด
last_announcement_message_id = None

# อัพเดตข้อมูลลิงก์เชิญเมื่อสมาชิกใหม่เข้าร่วม
@bot.event
async def on_member_join(member):
    guild = member.guild
    channel = guild.get_channel(WELCOME_CHANNEL_ID)

    # ดึงลิงก์เชิญปัจจุบันและเปรียบเทียบกับข้อมูลเชิญที่เก็บไว้
    invites = await guild.invites()
    used_invite = None

    for invite in invites:
        if invite.code in bot.invite_cache and invite.uses > bot.invite_cache[invite.code].uses:
            used_invite = invite
            break

    bot.invite_cache = {invite.code: invite for invite in invites}

    invite_info = f"🔗 ลิงก์เชิญที่ใช้: `{used_invite.url}` โดย `{used_invite.inviter}`" if used_invite else "❌ ไม่พบลิงก์เชิญ"

    # กำหนดบทบาทให้สมาชิกใหม่
    role1 = guild.get_role(WELCOME_ROLE_ID)
    role2 = guild.get_role(1306522538503045172)  # ตัวอย่างบทบาทอื่น
    for role in [role1, role2]:
        if role:
            try:
                await member.add_roles(role)
            except discord.Forbidden:
                print(f"❌ บอทไม่มีสิทธิ์เพิ่มบทบาท {role.name}")

    # ส่งข้อความต้อนรับ
    if channel:
        join_time = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M:%S UTC")
        embed = discord.Embed(
            title="👋 ยินดีต้อนรับสู่เซิร์ฟเวอร์!",
            description=f"**ชื่อผู้ใช้:** {member.name}\n**แท็ก:** {member.mention}\n**เข้าร่วมเมื่อ:** {join_time}\n{invite_info}",
            color=discord.Color.green()
        )
        embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
        await channel.send(embed=embed)

# ✅ ประกาศอัตโนมัติทุกๆ 1 ชั่วโมง
@tasks.loop(hours=1)
async def auto_announcement():
    channel = bot.get_channel(ANNOUNCEMENT_CHANNEL_ID)
    announcement_data = load_announcement()

    if channel and announcement_data:
        title = announcement_data.get('title', 'ไม่มีหัวข้อประกาศ')
        description = announcement_data.get('description', 'ไม่มีรายละเอียดประกาศ')
        color_input = announcement_data.get('color', '')
        thumbnail_url = announcement_data.get('thumbnail_url', None)

        # ดึงอิโมจิทั้งหมดจากเซิร์ฟเวอร์
        emojis = channel.guild.emojis
        emoji_dict = {f":{emoji.name}:": str(emoji) for emoji in emojis}

        # แปลง title และ description ด้วยอิโมจิจริง
        for emoji_code, emoji_str in emoji_dict.items():
            title = re.sub(re.escape(emoji_code), emoji_str, title)
            description = re.sub(re.escape(emoji_code), emoji_str, description)

        # ตรวจสอบข้อจำกัดความยาวของ description หลังแปลงอิโมจิ
        if len(description) > 4096:
            description = description[:4093] + "..."  # ตัดข้อความที่เกิน 4096 และเพิ่ม "..."

        # การตั้งค่าสี Embed หากกรอกสี
        color = discord.Color(int(color_input.replace('#', ''), 16)) if color_input else discord.Color.random()

        embed = discord.Embed(title=title, description=description, color=color)
        if thumbnail_url:
            embed.set_thumbnail(url=thumbnail_url)

        try:
            await channel.send(embed=embed)
            print("✅ ประกาศถูกโพสต์!")
        except discord.HTTPException as e:
            print(f"❌ การโพสต์ประกาศล้มเหลว: {e}")
    else:
        print("❌ ไม่พบข้อมูลประกาศหรือช่องประกาศ!")

# ฟังก์ชันโหลดข้อมูลประกาศจากไฟล์ JSON
def load_announcement():
    try:
        with open('announcement.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print("❌ ไม่พบไฟล์ 'announcement.json'")
        return None
    except json.JSONDecodeError:
        print("❌ ข้อผิดพลาดในการอ่านไฟล์ 'announcement.json'")
        return None

# ✅ คำสั่ง /clear เพื่อล้างข้อความในช่อง
@bot.tree.command(name="clear", description="🧹 ล้างข้อความในช่องแชท")
async def clear(interaction: discord.Interaction):
    admin_role = interaction.guild.get_role(ADMIN_ROLE_ID)
    if admin_role and admin_role in interaction.user.roles:
        await interaction.response.defer(ephemeral=True)
        deleted_messages = await interaction.channel.purge()
        await interaction.followup.send(f"✅ ล้างช่องแชทแล้ว ({len(deleted_messages)} ข้อความถูกลบ)", ephemeral=True)
    else:
        await interaction.response.send_message("❌ คุณไม่มีสิทธิ์ใช้คำสั่งนี้", ephemeral=True)

# ✅ คำสั่ง /chat คำสั่งประกาศ
@bot.tree.command(name="chat", description="📢 สร้างประกาศจากทีมงาน")
async def chat(interaction: discord.Interaction):
    # ตรวจสอบว่าผู้ใช้มี role ของ admin หรือไม่
    admin_role = interaction.guild.get_role(ADMIN_ROLE_ID)
    if admin_role and admin_role in interaction.user.roles:
        await interaction.response.send_modal(AnnouncementModal())
    else:
        await interaction.response.send_message("❌ คุณไม่มีสิทธิ์ใช้คำสั่งนี้", ephemeral=True)

class AnnouncementModal(Modal, title="📢 ประกาศจากทีมงาน"):
    # การรับค่าจากผู้ใช้ในการกรอกข้อมูล
    title_input = TextInput(label="หัวข้อ", placeholder="พิมพ์หัวข้อที่นี่")
    description_input = TextInput(label="รายละเอียด", style=discord.TextStyle.paragraph, placeholder="พิมพ์รายละเอียดที่นี่")
    color_input = TextInput(label="สี Embed (Hex Code เช่น #FF0000)", placeholder="#7289DA", required=False)
    image_url_input = TextInput(label="ลิงก์รูปภาพ (ไม่บังคับ)", placeholder="https://...", required=False)

    async def on_submit(self, interaction: discord.Interaction):
        # การตั้งค่าสี Embed หากกรอกสี
        try:
            color = discord.Color(int(self.color_input.value.replace('#', ''), 16)) if self.color_input.value else discord.Color.random()
        except:
            color = discord.Color.random()

        # ดึงอิโมจิทั้งหมดจากเซิร์ฟเวอร์
        emojis = interaction.guild.emojis
        emoji_dict = {f":{emoji.name}:": str(emoji) for emoji in emojis}

        # ใช้ regex แทนที่ :emoji_name: ด้วยอิโมจิจริง
        title_text = self.title_input.value
        description_text = self.description_input.value

        # แปลง title_input และ description_input ด้วยอิโมจิจริง
        for emoji_code, emoji_str in emoji_dict.items():
            title_text = re.sub(re.escape(emoji_code), emoji_str, title_text)
            description_text = re.sub(re.escape(emoji_code), emoji_str, description_text)

        # สร้าง Embed ที่มีข้อความและรายละเอียด
        embed = discord.Embed(
            title=title_text,
            description=description_text,
            color=color
        )

        # หากกรอก URL รูปภาพ, จะเพิ่มรูปภาพเข้าไปใน Embed
        if self.image_url_input.value:
            embed.set_image(url=self.image_url_input.value)

        # ส่ง Embed ที่สร้างเสร็จแล้ว
        await interaction.response.send_message(embed=embed)

# ✅ คำสั่ง /announce เพื่อโพสต์ประกาศทันที
@bot.tree.command(name="announce", description="📢 โพสต์ประกาศทันที")
async def announce(interaction: discord.Interaction):
    admin_role = interaction.guild.get_role(ADMIN_ROLE_ID)
    if admin_role and admin_role in interaction.user.roles:
        announcement_data = load_announcement()

        if announcement_data:
            title = announcement_data.get('title', 'ไม่มีหัวข้อประกาศ')
            description = announcement_data.get('description', 'ไม่มีรายละเอียดประกาศ')
            color_input = announcement_data.get('color', '#FF0000')
            thumbnail_url = announcement_data.get('thumbnail_url', None)

            # ดึงอิโมจิทั้งหมดจากเซิร์ฟเวอร์
            emojis = interaction.guild.emojis
            emoji_dict = {f":{emoji.name}:": str(emoji) for emoji in emojis}

            # แปลง title และ description ด้วยอิโมจิจริง
            for emoji_code, emoji_str in emoji_dict.items():
                title = re.sub(re.escape(emoji_code), emoji_str, title)
                description = re.sub(re.escape(emoji_code), emoji_str, description)

            # ตรวจสอบความยาวของ description
            if len(description) > 4096:
                description = description[:4093] + "..."  # ตัดความยาวให้ไม่เกิน 4096 และเพิ่ม "..." ที่ท้าย

            # การตั้งค่าสี Embed หากกรอกสี
            color = discord.Color(int(color_input.replace('#', ''), 16)) if color_input else discord.Color.random()

            embed = discord.Embed(title=title, description=description, color=color)
            if thumbnail_url:
                embed.set_thumbnail(url=thumbnail_url)

            channel = interaction.guild.get_channel(ANNOUNCEMENT_CHANNEL_ID)
            if channel:
                await channel.send(embed=embed)
                await interaction.response.send_message("✅ ประกาศถูกโพสต์เรียบร้อย!", ephemeral=True)
            else:
                await interaction.response.send_message("❌ ไม่พบช่องประกาศ!", ephemeral=True)
        else:
            await interaction.response.send_message("❌ ไม่พบข้อมูลประกาศในไฟล์ 'announcement.json'", ephemeral=True)
    else:
        await interaction.response.send_message("❌ คุณไม่มีสิทธิ์ใช้คำสั่งนี้", ephemeral=True)

# ✅ คำสั่ง /edit_announce แก้ไขและตั้งเวลาใหม่
class EditAnnouncementModal(Modal, title="✏️ แก้ไขประกาศ"):
    title_input = TextInput(label="หัวข้อประกาศ (สูงสุด 45 ตัว)", placeholder="พิมพ์หัวข้อที่นี่")
    description_input = TextInput(label="รายละเอียดประกาศ", style=discord.TextStyle.paragraph, placeholder="พิมพ์รายละเอียดที่นี่")
    time_input = TextInput(
        label="ระยะเวลา (เช่น '1H', '30M', หรือ '1H30M')", 
        placeholder="เช่น 1H หรือ 30M หรือ 1H30M"
    )

    async def on_submit(self, interaction: discord.Interaction):
        global last_announcement_message_id

        title = self.title_input.value
        description = self.description_input.value
        time_str = self.time_input.value.strip().upper()

        # ตรวจสอบรูปแบบเวลา
        time_pattern = re.match(r"(?:(\d+)H)?(?:(\d+)M)?", time_str)
        if not time_pattern:
            await interaction.response.send_message("❌ รูปแบบเวลาไม่ถูกต้อง กรุณาใช้ '1H', '30M', หรือ '1H30M'.", ephemeral=True)
            return

        hours = int(time_pattern.group(1) or 0)
        minutes = int(time_pattern.group(2) or 0)
        target_time = datetime.now() + timedelta(hours=hours, minutes=minutes)
        remaining_time = target_time - datetime.now()

        if remaining_time.total_seconds() < 0:
            await interaction.response.send_message("❌ เวลาที่ระบุในอดีต กรุณาระบุเวลาในอนาคต", ephemeral=True)
            return

        await interaction.response.send_message(
            f"✅ ประกาศจะถูกโพสต์ในเวลา {target_time.strftime('%H:%M')} ซึ่งเหลือเวลา {remaining_time.seconds // 3600} ชั่วโมง {remaining_time.seconds // 60 % 60} นาที!", 
            ephemeral=True)

        delay = remaining_time.total_seconds()

        # ดึงอิโมจิทั้งหมดจากเซิร์ฟเวอร์
        emojis = interaction.guild.emojis
        emoji_dict = {f":{emoji.name}:": str(emoji) for emoji in emojis}

        # แปลง title และ description ด้วยอิโมจิจริง
        for emoji_code, emoji_str in emoji_dict.items():
            title = re.sub(re.escape(emoji_code), emoji_str, title)
            description = re.sub(re.escape(emoji_code), emoji_str, description)

        # รอจนถึงเวลาที่กำหนด
        await self.wait_for_delay(delay)

        if last_announcement_message_id:
            try:
                channel = interaction.guild.get_channel(ANNOUNCEMENT_CHANNEL_ID)
                message = await channel.fetch_message(last_announcement_message_id)
                await message.delete()
            except discord.NotFound:
                print("❌ ไม่พบข้อความประกาศเดิม!")

        embed = discord.Embed(
            title=title,
            description=description,
            color=discord.Color.red()
        )
        channel = interaction.guild.get_channel(ANNOUNCEMENT_CHANNEL_ID)
        new_message = await channel.send(embed=embed)
        last_announcement_message_id = new_message.id

    async def wait_for_delay(self, delay):
        while delay > 0:
            await asyncio.sleep(1)
            delay -= 1
            await asyncio.sleep(0)

# ✅ คำสั่ง /edit_announce เพื่อแก้ไขและกำหนดเวลาในการประกาศ
@bot.tree.command(name="edit_announce", description="📝 แก้ไขและกำหนดเวลาในการประกาศ")
async def edit_announce(interaction: discord.Interaction):
    admin_role = interaction.guild.get_role(ADMIN_ROLE_ID)
    if admin_role and admin_role in interaction.user.roles:
        await interaction.response.send_modal(EditAnnouncementModal())
    else:
        await interaction.response.send_message("❌ คุณไม่มีสิทธิ์ใช้คำสั่งนี้", ephemeral=True)

# ✅ โหลดข้อมูลลิงก์เชิญเมื่อบอทเริ่มทำงาน
@bot.event
async def on_ready():
    print(f"✅ บอทออนไลน์แล้ว: {bot.user}")

    if not bot.guilds:
        print("❌ ไม่พบเซิร์ฟเวอร์ที่บอทเข้าร่วม")
        return

    for guild in bot.guilds:
        print(f"- {guild.name} (ID: {guild.id})")

    auto_announcement.start()

    # เก็บข้อมูลเชิญในหน่วยความจำ
    guild = bot.get_guild(1293907837977755719)  # แทนที่ด้วย ID เซิร์ฟเวอร์ของคุณ
    invites = await guild.invites()
    bot.invite_cache = {invite.code: invite for invite in invites}

# เริ่มต้นบอทด้วย token ที่กำหนด
server_on()
bot.run(os.getenv('TOKEN'))
