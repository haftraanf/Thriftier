import os
import discord
from discord.ext import commands, tasks
import json
from datetime import datetime
from decimal import Decimal, InvalidOperation
import calendar

from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
client = discord.Client(intents=intents)# create an instance of client, this is the connection to discord

#helper functions aiding the features
file = "data.json"

def is_decimal (num):
    try:
        Decimal(num)
        return True
    except InvalidOperation:
        return False

def add_expense_to_list(amount, category, date):
    with open(file, "r") as infile:
        dict = json.load(infile)  # extract the dict
        expense_obj = {"amount": amount,
                       "category": category.capitalize(),
                       "date": date
                       }  # create the expense object
        dict["expenses"].append(expense_obj)  # add it to the list
    with open(file, "w") as infile:
        json.dump(dict, infile, indent=2, default=str) #update the json file with new expense
    with open(file, "r") as infile:
        dict = json.load(infile)  # extract the dict
        dict["expenses"] = sorted(dict["expenses"], key=lambda x: x["date"])
    with open(file, "w") as infile:
        json.dump(dict, infile, indent=2, default=str) #update the json file with new expense


def filter_expenses_by_date(start_date, end_date):
    filtered_expenses = []
    with open(file, "r") as infile:
        dict = json.load(infile)  # extract the dict
        for expense in dict["expenses"]: #iterate through each expense in the expenses list
            expense_date = datetime.fromisoformat(expense["date"]).date() #convert the expense date to datetime object for comparision
            if start_date <= expense_date <= end_date: #check if the expense date falls within the specified date range
                filtered_expenses.append(expense) #if yes, then append it to the  returned list
        return filtered_expenses

def construct_start_and_end_dates(date):
    year, month = date.year, date.month
    _, last_day = calendar.monthrange(year, month) #use the built-in function to obtain the number of days in the specified month
    start_date = datetime.fromisoformat(f"{year}-{month:02d}-01").date()
    end_date = datetime.fromisoformat(f"{year}-{month:02d}-{last_day:02d}").date()
    return start_date, end_date

def total_amount_per_category(filtered_expenses):
    amount_by_category = {}
    for expense in filtered_expenses:
        category = expense["category"]
        if category in amount_by_category:
            amount_by_category[category] += expense["amount"]
        else:
            amount_by_category[category] = expense["amount"]
    return amount_by_category

async def removing_expense(message, removed_expense):
    with open(file, "r") as infile:
        dict = json.load(infile)  # extract the dict
        for expense in dict["expenses"]:  # iterate through each expense in the expenses list
            if expense["amount"] == removed_expense["amount"] and expense["category"] == removed_expense["category"] and expense["date"] == removed_expense["date"]:
                dict["expenses"].remove(expense)
    with open(file, "w") as infile:
        json.dump(dict, infile, indent=2, default=str)  # update the json file with new expense
    await message.channel.send("The selected expense have successfully deleted.")

async def print_summary(message, expenses_list, start_date, end_date):
    startdate = start_date.strftime("%Y-%m-%d")
    enddate = end_date.strftime("%Y-%m-%d")
    await message.channel.send("Your expenses list starting from {} to {}:".format(startdate, enddate))
    for numbering, expense in enumerate(expenses_list, start=1):
        await message.channel.send(f"{numbering}. {expense['date']}: {expense['category']} - ${expense['amount']:.2f}")

async def print_total(message, total_expenses_per_category, start_date, end_date):
    startdate = start_date.strftime("%Y-%m-%d")
    enddate = end_date.strftime("%Y-%m-%d")
    await message.channel.send("Your expenses list starting from {} to {}:".format(startdate, enddate))
    for numbering, (category, amount) in enumerate(total_expenses_per_category.items(), start=1):
        await message.channel.send(f"{numbering}. {category} - ${amount:.2f}")

# when the bot is ready to be used
@client.event
async def on_ready():
    print('We have logged in as {0.user}'.format(client))

@client.event
async def on_message(message):
    if message.author == client.user: return

    msg = message.content

    if msg.startswith("!add"):
        amount = msg.split()[1]
        category = msg.split()[2]
        try:
            bool(datetime.fromisoformat(msg.split()[-1]).date())
        except ValueError:
            await message.channel.send("You have entered the wrong format for the date. Please try again in the correct format yyyy-mm-dd!")
        else:
            date = datetime.fromisoformat(msg.split()[-1]).date()
            if is_decimal(amount):
                if category.isalpha():
                    add_expense_to_list(float(amount), category, date)
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
            await message.channel.send("You have entered the wrong format for the date. Please try again in the correct format yyyy-mm-dd!")
        except IndexError:
            date_range = construct_start_and_end_dates(datetime.now().date())
            filtered_expenses = filter_expenses_by_date(date_range[0], date_range[1])
            await print_summary(message, filtered_expenses, date_range[0], date_range[1])
        else:
            filtered_expenses = filter_expenses_by_date(start_date, end_date)
            await print_summary(message, filtered_expenses, start_date, end_date)


    if msg.startswith("!total"):
        try:
            start_date = datetime.fromisoformat(msg.split()[1]).date()
            end_date = datetime.fromisoformat(msg.split()[-1]).date()
        except ValueError:
            await message.channel.send("You have entered the wrong format for the date. Please try again in the correct format yyyy-mm-dd!")
        except IndexError:
            date_range = construct_start_and_end_dates(datetime.now().date())
            filtered_expenses = filter_expenses_by_date(date_range[0], date_range[1])
            total_expenses = total_amount_per_category(filtered_expenses)
            await print_total(message, total_expenses, date_range[0], date_range[1])
        else:
            filtered_expenses = filter_expenses_by_date(start_date, end_date)
            total_expenses = total_amount_per_category(filtered_expenses)
            await print_total(message, total_expenses, start_date, end_date)

    if msg.startswith("!remove"):
        try:
            start_date = datetime.fromisoformat(msg.split()[1]).date()
            end_date = datetime.fromisoformat(msg.split()[-1]).date()
        except ValueError:
            await message.channel.send("You have entered the wrong format for the date. Please try again in the correct format yyyy-mm-dd!")
        except IndexError:
            date_range = construct_start_and_end_dates(datetime.now().date())
            filtered_expenses = filter_expenses_by_date(date_range[0], date_range[1])
            await print_summary(message, filtered_expenses, date_range[0], date_range[1])
            await message.channel.send("Which expense do you wish to remove? Please type in the number of the expense.")
            def check(m):
                return is_decimal(m.content) and (1 <= int(m.content) <= len(filtered_expenses))
            msg = await client.wait_for('message', check=check)
            await removing_expense(message, filtered_expenses[int(msg.content) - 1])
        else:
            filtered_expenses = filter_expenses_by_date(start_date, end_date)
            await print_summary(message, filtered_expenses, start_date, end_date)
            await message.channel.send("Which expense do you wish to remove? Please type in the number of the expense.")
            def check(m):
                return is_decimal(m.content) and (1 <= int(m.content) <= len(filtered_expenses))
            msg = await client.wait_for('message', check=check)
            await removing_expense(message, filtered_expenses[int(msg.content) - 1])

    if (msg == "!help"):
        embed = discord.Embed(
            title="List of Available Commands!",
            description="",
            colour=0x88aed0
        )
        embed.add_field(name='Personal Commands (parameters inside < > are optional)', value='`!add amount category date` - add an expense\n`!summary <start date> <end date>`- view a list of every expenses\n`!total <start date> <end date>` - view the total amount spent for each category\n`!remove <start date> <end date>` - remove an expense', inline=False)
        embed.add_field(name='Misc Commands', value="`!help` - display vailable commands", inline=False)

        await message.channel.send(embed=embed)

client.run(TOKEN)
