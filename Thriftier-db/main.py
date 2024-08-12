import os
import discord
import mysql.connector
from datetime import datetime
from decimal import Decimal, InvalidOperation
import calendar
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# MySQL database connection
db = mysql.connector.connect(
    host="localhost",        # Your MySQL server hostname
    user="root",    # Your MySQL username
    password="root",# Your MySQL password
    database="sys"   # The database you created
)
# Establish the connection
cursor = db.cursor()

# Creating tables if they don't exist
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT UNIQUE
)
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS expenses (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT,
    amount DECIMAL(10, 2),
    category VARCHAR(255),
    date DATE,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
)
""")
db.commit()

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
client = discord.Client(intents=intents)  # create an instance of client, this is the connection to discord


# Helper functions aiding the features

def is_decimal(num):
    try:
        Decimal(num)
        return True
    except InvalidOperation:
        return False


def add_expense_to_db(user_id, amount, category, date):
    # Insert user if not exists
    cursor.execute("INSERT IGNORE INTO users (user_id) VALUES (%s)", (user_id,))

    # Insert expense
    sql = "INSERT INTO expenses (user_id, amount, category, date) VALUES (%s, %s, %s, %s)"
    val = (user_id, amount, category.capitalize(), date)
    cursor.execute(sql, val)
    db.commit()


def filter_expenses_by_date(user_id, start_date, end_date):
    sql = "SELECT amount, category, date FROM expenses WHERE user_id = %s AND date BETWEEN %s AND %s ORDER BY date"
    cursor.execute(sql, (user_id, start_date, end_date))
    return cursor.fetchall()


def construct_start_and_end_dates(date):
    year, month = date.year, date.month
    _, last_day = calendar.monthrange(year,
                                      month)  # use the built-in function to obtain the number of days in the specified month
    start_date = datetime.fromisoformat(f"{year}-{month:02d}-01").date()
    end_date = datetime.fromisoformat(f"{year}-{month:02d}-{last_day:02d}").date()
    return start_date, end_date


def total_amount_per_category(filtered_expenses):
    amount_by_category = {}
    for expense in filtered_expenses:
        category = expense[1]  # category is the second field
        amount = expense[0]  # amount is the first field
        if category in amount_by_category:
            amount_by_category[category] += amount
        else:
            amount_by_category[category] = amount
    return amount_by_category


async def removing_expense(message, user_id, removed_expense):
    sql = "DELETE FROM expenses WHERE user_id = %s AND amount = %s AND category = %s AND date = %s"
    val = (user_id, removed_expense[0], removed_expense[1], removed_expense[2])
    cursor.execute(sql, val)
    db.commit()
    await message.channel.send("The selected expense has been successfully deleted.")


async def print_summary(message, expenses_list, start_date, end_date):
    startdate = start_date.strftime("%Y-%m-%d")
    enddate = end_date.strftime("%Y-%m-%d")
    await message.channel.send("Your expenses list starting from {} to {}:".format(startdate, enddate))
    for numbering, expense in enumerate(expenses_list, start=1):
        await message.channel.send(f"{numbering}. {expense[2]}: {expense[1]} - ${expense[0]:.2f}")


async def print_total(message, total_expenses_per_category, start_date, end_date):
    startdate = start_date.strftime("%Y-%m-%d")
    enddate = end_date.strftime("%Y-%m-%d")
    await message.channel.send("Your expenses list starting from {} to {}:".format(startdate, enddate))
    for numbering, (category, amount) in enumerate(total_expenses_per_category.items(), start=1):
        await message.channel.send(f"{numbering}. {category} - ${amount:.2f}")


# When the bot is ready to be used
@client.event
async def on_ready():
    print('We have logged in as {0.user}'.format(client))


@client.event
async def on_message(message):
    if message.author == client.user: return

    msg = message.content
    user_id = message.author.id

    if msg.startswith("!add"):
        amount = msg.split()[1]
        category = msg.split()[2]
        try:
            bool(datetime.fromisoformat(msg.split()[-1]).date())
        except ValueError:
            await message.channel.send(
                "You have entered the wrong format for the date. Please try again in the correct format yyyy-mm-dd!")
        else:
            date = datetime.fromisoformat(msg.split()[-1]).date()
            if is_decimal(amount):
                if category.isalpha():
                    add_expense_to_db(user_id, float(amount), category, date)
                    await message.channel.send("Noted! You spent ${:.2f} on {}.".format(float(amount), category))
                else:
                    await message.channel.send("You have entered an invalid category. Please try again!")
            else:
                await message.channel.send("You have entered an invalid amount. Please try again!")

    if msg.startswith("!summary"):
        try:
            start_date = datetime.fromisoformat(msg.split()[1]).date()
            end_date = datetime.fromisoformat(msg.split()[-1]).date()
        except ValueError:
            await message.channel.send(
                "You have entered the wrong format for the date. Please try again in the correct format yyyy-mm-dd!")
        except IndexError:
            date_range = construct_start_and_end_dates(datetime.now().date())
            filtered_expenses = filter_expenses_by_date(user_id, date_range[0], date_range[1])
            await print_summary(message, filtered_expenses, date_range[0], date_range[1])
        else:
            filtered_expenses = filter_expenses_by_date(user_id, start_date, end_date)
            await print_summary(message, filtered_expenses, start_date, end_date)

    if msg.startswith("!total"):
        try:
            start_date = datetime.fromisoformat(msg.split()[1]).date()
            end_date = datetime.fromisoformat(msg.split()[-1]).date()
        except ValueError:
            await message.channel.send(
                "You have entered the wrong format for the date. Please try again in the correct format yyyy-mm-dd!")
        except IndexError:
            date_range = construct_start_and_end_dates(datetime.now().date())
            filtered_expenses = filter_expenses_by_date(user_id, date_range[0], date_range[1])
            total_expenses = total_amount_per_category(filtered_expenses)
            await print_total(message, total_expenses, date_range[0], date_range[1])
        else:
            filtered_expenses = filter_expenses_by_date(user_id, start_date, end_date)
            total_expenses = total_amount_per_category(filtered_expenses)
            await print_total(message, total_expenses, start_date, end_date)

    if msg.startswith("!remove"):
        try:
            start_date = datetime.fromisoformat(msg.split()[1]).date()
            end_date = datetime.fromisoformat(msg.split()[-1]).date()
        except ValueError:
            await message.channel.send(
                "You have entered the wrong format for the date. Please try again in the correct format yyyy-mm-dd!")
        except IndexError:
            date_range = construct_start_and_end_dates(datetime.now().date())
            filtered_expenses = filter_expenses_by_date(user_id, date_range[0], date_range[1])
            await print_summary(message, filtered_expenses, date_range[0], date_range[1])
            await message.channel.send("Which expense do you wish to remove? Please type in the number of the expense.")

            def check(m):
                return is_decimal(m.content) and (1 <= int(m.content) <= len(filtered_expenses))

            msg = await client.wait_for('message', check=check)
            await removing_expense(message, user_id, filtered_expenses[int(msg.content) - 1])
        else:
            filtered_expenses = filter_expenses_by_date(user_id, start_date, end_date)
            await print_summary(message, filtered_expenses, start_date, end_date)
            await message.channel.send("Which expense do you wish to remove? Please type in the number of the expense.")

            def check(m):
                return is_decimal(m.content) and (1 <= int(m.content) <= len(filtered_expenses))

            msg = await client.wait_for('message', check=check)
            await removing_expense(message, user_id, filtered_expenses[int(msg.content) - 1])

    if msg == "!help":
        embed = discord.Embed(
            title="List of Available Commands!",
            description="",
            colour=0x88aed0
        )
        embed.add_field(name='Personal Commands (parameters inside < > are optional)', value='`!add amount category date` - add an expense\n`!summary <start date> <end date>`- view a list of every expense\n`!total <start date> <end date>` - view the total amount spent for each category\n`!remove <start date> <end date>` - remove an expense', inline=False)
        embed.add_field(name='Misc Commands', value="`!help` - display available commands", inline=False)

        await message.channel.send(embed=embed)

# Run the bot
client.run(TOKEN)

# Close the database connection when the bot shuts down
@client.event
async def on_disconnect():
    cursor.close()
    db.close()