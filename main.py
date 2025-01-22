import os
import discord
import random
import asyncio
from discord.ext import commands
from datetime import datetime, timedelta
import pytz  # เพิ่มการนำเข้า pytz

from myserver import server_on

# กำหนดโซนเวลาเป็น GMT+7
tz = pytz.timezone('Asia/Bangkok')

# สร้างบอทพร้อมตั้งค่า intents
intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents)

# ตัวแปรที่ใช้ร่วมกัน
lotto_running = False
players = {}
chosen_numbers = set()
announcement_time = None  # เวลาในการประกาศรางวัล

# ตั้งค่าตัวแปรที่ขาดหายไป
number_range = (000,999)  # ตัวเลขที่สามารถเลือกได้ 000-999
min_players = 2  # จำนวนผู้เล่นขั้นต่ำ
confirm_duration = 15  # ระยะเวลาในการยืนยันตัวตน (วินาที)
num_rounds = 1  # จำนวนรอบในการสุ่มผู้ชนะ

# แปลงวินาทีเป็น วัน/ชั่วโมง/นาที/วินาที
def format_time(seconds):
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    time_parts = []
    if days > 0:
        time_parts.append(f"{days} วัน")
    if hours > 0:
        time_parts.append(f"{hours} ชั่วโมง")
    if minutes > 0:
        time_parts.append(f"{minutes} นาที")
    if seconds > 0:
        time_parts.append(f"{seconds} วินาที")
    return " ".join(time_parts)

# ตรวจสอบว่า user เป็น admin หรือไม่
def is_admin(ctx):    
    return ctx.author.guild_permissions.administrator

# เปิดให้ผู้เล่นพิมพ์เลข และอัปเดตเวลาคงเหลือใน Embed
async def update_embed_time(announcement_message, embed):
    global announcement_time, lotto_running
    while lotto_running:
        now = datetime.now(tz)
        remaining_time = int((announcement_time - now).total_seconds())
        if remaining_time <= 0:
            break
        embed.set_field_at(0, name="⏳ เวลากิจกรรมคงเหลือ:", value=f"{format_time(remaining_time)}", inline=False)
        await announcement_message.edit(embed=embed)
        await asyncio.sleep(30)  # อัปเดตทุก 30 วินาที

    if remaining_time <= 0 and lotto_running:
        await announcement_message.channel.send("⏳ หมดเวลาการเข้าร่วมเกมแล้ว ต่อไปจะเป็นการประกาศรางวัล \n -------------------------")
        lotto_running = False
        await asyncio.sleep(5)


# คำสั่ง lotto พร้อมตั้งเวลาประกาศรางวัล
@bot.command(name="lotto")
@commands.check(is_admin)
async def lotto(ctx, hour: int, minute: int):
    global lotto_running, players, chosen_numbers, announcement_time

    if lotto_running:
        await ctx.send("❗ กิจกรรมกำลังทำงานอยู่ ไม่สามารถเริ่มกิจกรรมใหม่ได้")
        return

    lotto_running = True
    players.clear()
    chosen_numbers.clear()

    # ตั้งเวลาในการประกาศรางวัล
    now = datetime.now(tz)  # ใช้โซนเวลา GMT+7
    announcement_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if announcement_time <= now:
        announcement_time += timedelta(days=1)  # หากเวลาผ่านไปแล้ว ให้เลื่อนไปวันถัดไป

    remaining_time = int((announcement_time - now).total_seconds())

    # ประกาศเริ่มกิจกรรม
    embed = discord.Embed(
        title="🎉 **กิจกรรม Lotto แจกรางวัล!** 🎉",
        description=(f"@everyone กิจกรรมเริ่มขึ้นแล้ว! \nพิมพ์ตัวเลขในรูปแบบ 3 หลัก เช่น 000-999 เพื่อเข้าร่วมเกม!\n"
                     "ตัวเลขห้ามซ้ำกัน ใครพิมพ์ก่อนจะได้สิทธิ์เลขนั้น\n\nการได้สิทธิ์ในตัวเลขจะต้องมีเครื่องหมาย ✅ จากระบบ \nหลังจากเลือกตัวเลขแล้วเท่านั้น\n\n"
                     f"📌 **จะประกาศรางวัลเวลา {hour:02d}:{minute:02d}** "
                     f"({format_time(remaining_time)})"),
                     
        color=discord.Color.red(),
    )
    embed.set_image(url="https://i.imgur.com/8Ovktmu.png")
    embed.add_field(name="⏳ เวลากิจกรรมคงเหลือ:", value=f"{format_time(remaining_time)}", inline=False)
    announcement_message = await ctx.send(embed=embed)

     # เริ่มงานอัปเดตเวลาแบบ Async
    asyncio.create_task(update_embed_time(announcement_message, embed))

    def get_available_numbers():
        available_numbers = list(set(range(number_range[0], number_range[1] + 1)) - chosen_numbers)
        return random.sample(available_numbers, 10) if len(available_numbers) >= 10 else available_numbers


    # เปิดให้ผู้เล่นพิมพ์เลข
    while lotto_running and remaining_time > 0:
        try:
            msg = await bot.wait_for("message", timeout=2, check=lambda m: m.channel == ctx.channel and not m.author.bot)
            
            # ตรวจสอบรูปแบบตัวเลข
            if not msg.content.isdigit() or len(msg.content) != 3:
                await msg.reply(f"❗ กรุณากรอกตัวเลขในรูปแบบ 3 หลัก เช่น 000, 001 หรือ 123!", delete_after=5)
                continue

            number = int(msg.content)

            # ตรวจสอบว่าหมายเลขอยู่ในช่วงที่อนุญาต
            if number < number_range[0] or number > number_range[1]:
                await msg.reply(f"❗ หมายเลข {msg.content} ไม่อยู่ในช่วงที่อนุญาต (000-999)!", delete_after=5)
            elif msg.author in players:
                await msg.reply("❗ คุณได้เลือกตัวเลขไปแล้วและไม่สามารถเปลี่ยนได้!", delete_after=5)
            elif number in chosen_numbers:
                available_numbers = get_available_numbers()
                await msg.reply(f"❗ ตัวเลข {msg.content} ถูกเลือกไปแล้ว! เราขอแนะนำชุดตัวเลขที่ยังสามารถเลือกได้ ดังนี้: {', '.join(map(str, available_numbers))}", delete_after=10 )
            else:
                players[msg.author] = number
                chosen_numbers.add(number)
                await msg.add_reaction("✅")

        except asyncio.TimeoutError:
            pass   
       
    # ยุติหากผู้เล่นไม่ถึงขั้นต่ำ
    if len(players) < min_players:
        await ctx.send(f"❗ ไม่สามารถเริ่มกิจกรรมได้เนื่องจากมีผู้เข้าร่วมไม่ถึง {min_players} คน! 😢")
        lotto_running = False
        return    

    # สุ่มตัวเลขเป้าหมายและเริ่มออกรางวัล
    winning_number = random.randint(*number_range)
    sorted_players = sorted(players.items(), key=lambda x: abs(x[1] - winning_number))
    confirmed_winners = []
    used_winners = set()

    # นับถอยหลัง 5 วินาที ก่อนประกาศผู้ชนะ
    await ctx.send("⏳ กรุณารอซักครู่ เรากำลังประมวลผลรายชื่อผู้โชคดี \nและผู้ชนะรางวัลได้แก่....")
    await asyncio.sleep(7)

    async def confirm_winner(winner):
        try:
            await winner.send(
                f"🎉 สวัสดี {winner.name}! คุณเป็นผู้โชคดีจากกิจกรรม Lotto! "
                f"กรุณายืนยันตัวตนโดยพิมพ์ 'ยืนยัน' ภายใน {format_time(confirm_duration)}"
            )
        except discord.Forbidden:
            await ctx.send(f"❗ {winner.mention} ไม่สามารถส่ง DM ได้ กรุณายืนยันในแชท")

        await ctx.send(
            f"{winner.mention} กรุณายืนยันตัวตนภายใน {format_time(confirm_duration)} "
            "โดยพิมพ์คำว่า '**ยืนยัน**' ในช่องแชทนี้"
        )

        def check(message):
            return message.author == winner and message.content.lower() == "ยืนยัน"

        try:
            await bot.wait_for("message", check=check, timeout=confirm_duration)
            confirmed_winners.append(winner)
            used_winners.add(winner)
            await ctx.send(f"🎉 {winner.mention} ได้ยืนยันตัวตนแล้ว!")
            await asyncio.sleep(3)
        except asyncio.TimeoutError:
            await ctx.send(f"⏳ เสียใจด้วย {winner.mention} ไม่ได้ยืนยันตัวตนภายในเวลาที่กำหนด.")
            await asyncio.sleep(5)

    # ตัวแปรเก็บผู้ชนะในแต่ละรอบ
    winners_by_round = []

    # ฟังก์ชันแก้ไขการสุ่มผู้ชนะในแต่ละรอบ
    for round_num in range(num_rounds):
        winning_number = random.randint(*number_range)

        # ค้นหาผู้ที่เลือกเลขตรงกับเลขที่ชนะและไม่ได้ยืนยันตัวตนในรอบก่อนหน้า
        winners = [(player, number) for player, number in players.items() if number == winning_number and player not in used_winners]

        if not winners:
            await ctx.send(f"(เลขที่ออก: **{winning_number}** ❗ น่าเสียดายไม่มีผู้ชนะในรอบนี้ เนื่องจากไม่มีใครเลือกตัวเลขที่ชนะ ).\n -------------------------")
            await asyncio.sleep(7)  # หน่วงเวลารอบถัดไป
            winners_by_round.append(f"รอบที่ {round_num + 1}: ไม่มีผู้ชนะ")
            continue

        winner, number = winners[0]  # ผู้ชนะคนแรกที่เลือกเลขถูก
        embed = discord.Embed(
            title=f"🎉 ประกาศผลรอบที่ {round_num + 1}! 🎉",
            description=(f"🎯 ตัวเลขที่ชนะคือ: **{winning_number}**\n"
                        f"🎉 ผู้ชนะรางวัลคือ: {winner.mention} (เลขที่เลือก: {number})\n"
                        f"กรุณายืนยันตัวตนภายใน {format_time(confirm_duration)} เพื่อรับรางวัล!"),
            color=discord.Color.green(),
        )
        embed.set_thumbnail(url=winner.avatar.url if winner.avatar else None)
        await ctx.send(embed=embed)
        await confirm_winner(winner)

        if winner in confirmed_winners:
            used_winners.add(winner)  # เพิ่มผู้ที่ยืนยันตัวตนแล้วใน used_winners
            winners_by_round.append(f"รอบที่ {round_num + 1}: {winner.mention}")
            await ctx.send(f"🎉 ผู้ชนะในรอบที่ {round_num + 1}: {winner.mention} \n -------------------------")
        else:
            winners_by_round.append(f"รอบที่ {round_num + 1}: ไม่มีการยืนยันจาก {winner.mention}")
            await ctx.send(f"⏳ ไม่มีการยืนยันจาก {winner.mention} ในรอบนี้. \n -------------------------")
        
        await asyncio.sleep(7)  # หน่วงเวลารอบถัดไป

    # สรุปผลผู้ชนะทั้งหมดในกิจกรรม
    await ctx.send("🎉 สรุปผลผู้ชนะที่ยืนยันตัวตน:") 
    for result in winners_by_round:
        await ctx.send(result)

    if confirmed_winners:
        winner_mentions = ", ".join(winner.mention for winner in confirmed_winners)
        await ctx.send(f"🎉 ผู้ชนะทั้งหมดที่ยืนยันตัวตนแล้ว: {winner_mentions} \n\nให้ทำการเปิด 🎟️ Ticket ในห้อง https://discord.com/channels/1326774367492898870/1330853563299266601 เพื่อรอรับรางวัลเลยจ้า!. \n -------------------------")
    else:
        await ctx.send("❗ น่าเสียดายที่ไม่มีผู้ชนะที่ยืนยันตัวตนในกิจกรรมนี้ 😢 \n -------------------------")

    await ctx.send("🎉 กิจกรรม Lotto สิ้นสุดลงแล้ว! \n ขอบคุณที่เข้ามาร่วมสนุกกับเรา แล้วพบกันใหม่รอบหน้านะจ๊ะ.")

    # รีเซ็ตสถานะกิจกรรม
    lotto_running = False
    players.clear()
    chosen_numbers.clear()

# รีเซ็ตกิจกรรม
@bot.command(name="reset")
@commands.check(is_admin)
async def reset_all(ctx):
    global lotto_running, players, chosen_numbers

    lotto_running = False
    players.clear()
    chosen_numbers.clear()
    await ctx.send("♻️ กิจกรรมได้ถูกยกเลิกเรียบร้อยแล้ว!")

@bot.event
async def on_ready():
    print(f"บอท {bot.user} พร้อมใช้งานแล้ว!")

server_on()

# รันบอท
bot.run(os.getenv('TOKEN'))
