import os
import re
import threading
import discord
from discord import app_commands
from discord.ext import commands
from flask import Flask

# ================== الإعدادات ==================
OWNERS = {1427993218104168498, 1306034100544737461}
CATEGORY_ID = 1563459146580234341
STAFF_ROLE_ID = 1563610725589590046
EMBED_COLOR = 0x2B2D31  # غير اللون هنا ليطابق الصورة

# ================== سيرفر للابقاء حي (UptimeRobot) ==================
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is alive"

def run_web():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

# ================== البوت ==================
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)


def is_staff(member: discord.Member) -> bool:
    return any(r.id == STAFF_ROLE_ID for r in member.roles)


# ---------- نافذة كتابة السبب ----------
class ReasonModal(discord.ui.Modal):
    def __init__(self, ticket_type: str):
        super().__init__(title=f"فتح تذكرة - {ticket_type}")
        self.ticket_type = ticket_type
        self.reason = discord.ui.TextInput(
            label="سبب فتح التذكرة",
            style=discord.TextStyle.paragraph,
            placeholder="اكتب المشكلة بالتفصيل...",
            required=True,
            min_length=5,
            max_length=1000,
        )
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        category = guild.get_channel(CATEGORY_ID)
        if category is None:
            return await interaction.followup.send("❌ الكاتيجوري غير موجود.", ephemeral=True)

        # رقم التذكرة
        nums = [int(m.group(1)) for c in category.channels
                if (m := re.fullmatch(r"ticket-(\d+)", c.name))]
        number = (max(nums) + 1) if nums else 1

        staff_role = guild.get_role(STAFF_ROLE_ID)
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(
                view_channel=True, send_messages=False, read_message_history=True),
            staff_role: discord.PermissionOverwrite(
                view_channel=True, send_messages=True, read_message_history=True),
            guild.me: discord.PermissionOverwrite(
                view_channel=True, send_messages=True, manage_channels=True,
                embed_links=True, read_message_history=True),
        }
        channel = await guild.create_text_channel(
            name=f"ticket-{number}", category=category, overwrites=overwrites)

        embed = discord.Embed(title=f"🎫 تذكرة رقم {number}", color=EMBED_COLOR)
        embed.add_field(name="صاحب التذكرة", value=interaction.user.mention, inline=True)
        embed.add_field(name="نوع التذكرة", value=self.ticket_type, inline=True)
        embed.add_field(name="السبب", value=self.reason.value, inline=False)
        embed.set_footer(text="بانتظار استلام أحد الإداريين")

        await channel.send(
            content=f"{staff_role.mention} {interaction.user.mention}",
            embed=embed,
            view=TicketControlView(),
        )
        await interaction.followup.send(f"✅ تم فتح تذكرتك: {channel.mention}", ephemeral=True)


# ---------- لوحة الأزرار ----------
class PanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="الإبلاغ", style=discord.ButtonStyle.secondary, custom_id="ticket_report")
    async def report(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ReasonModal("الإبلاغ"))

    @discord.ui.button(label="دعم فني", style=discord.ButtonStyle.secondary, custom_id="ticket_support")
    async def support(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ReasonModal("دعم فني"))

    @discord.ui.button(label="خلل", style=discord.ButtonStyle.secondary, custom_id="ticket_bug")
    async def bug(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ReasonModal("خلل"))


# ---------- ازرار التذكرة ----------
class TicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="استلام", style=discord.ButtonStyle.secondary, custom_id="ticket_claim")
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_staff(interaction.user):
            return await interaction.response.send_message("❌ هذا الزر للإدارة فقط.", ephemeral=True)

        embed = interaction.message.embeds[0]
        if any(f.name == "المستلم" for f in embed.fields):
            return await interaction.response.send_message("❌ التذكرة مستلمة مسبقاً.", ephemeral=True)

        embed.add_field(name="المستلم", value=interaction.user.mention, inline=False)
        embed.set_footer(text="تم استلام التذكرة")

        new_view = TicketControlView()
        new_view.claim.disabled = True
        new_view.claim.label = "تم الاستلام"
        await interaction.response.edit_message(embed=embed, view=new_view)
        await interaction.channel.send(f"✅ {interaction.user.mention} استلم التذكرة.")

    @discord.ui.button(label="حذف التذكرة", style=discord.ButtonStyle.secondary, custom_id="ticket_delete")
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_staff(interaction.user):
            return await interaction.response.send_message("❌ هذا الزر للإدارة فقط.", ephemeral=True)
        await interaction.response.defer()
        await interaction.channel.delete()


# ---------- الأمر ----------
@bot.tree.command(name="تكت", description="إرسال قائمة التذاكر")
async def ticket_cmd(interaction: discord.Interaction):
    if interaction.user.id not in OWNERS:
        return await interaction.response.send_message("❌ ما عندك صلاحية.", ephemeral=True)

    embed = discord.Embed(
        title="🎫 نظام التذاكر",
        description=(
            "**القوانين:**\n"
            "• احترام الإدارة والأعضاء.\n"
            "• اختر نوع التذكرة المناسب لمشكلتك.\n"
            "• اكتب سبب التذكرة بوضوح وبالتفصيل.\n"
            "• ممنوع فتح تذاكر بدون سبب أو للمزاح.\n"
            "• ممنوع تكرار المنشن للإدارة.\n"
            "• التذاكر المخالفة تُحذف بدون إنذار."
        ),
        color=EMBED_COLOR,
    )
    embed.set_footer(text="اضغط على الزر المناسب لفتح تذكرة")
    await interaction.channel.send(embed=embed, view=PanelView())
    await interaction.response.send_message("✅ تم إرسال القائمة.", ephemeral=True)


@bot.event
async def setup_hook():
    bot.add_view(PanelView())
    bot.add_view(TicketControlView())
    await bot.tree.sync()


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")


if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()
    bot.run(os.environ["DISCORD_TOKEN"])
