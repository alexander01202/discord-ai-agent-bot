import json
import os
import datetime
import discord
from discord import app_commands
from discord.ext import tasks
from dotenv import load_dotenv
from src.discord_bot_handler.bot_handler import BotHandler
from src.discord_bot_handler.paginators.user_log_paginator import UserLogPaginator
from src.discord_bot_handler.paginators.employee_schedule_paginator import EmployeeSchedulePaginator
from langchain_task_handler import TaskManagementAgent
from langchain_user_request_handler import UserRequestAgent
from discord_chat_history_ingestor import DiscordChatHistoryIngestor
import asyncio
from src.db.db_handler import get_employees, log_discord_chat_history, get_tasks, delete_task
from prompts import SYSTEM_PROMPT_FOR_CHAT_HISTORY, SYSTEM_PROMPT
from src.langchain_tools.utils.utils import remove_angle_bracket_content

# Load environment variables
load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")

bot_handler = BotHandler()
bot = bot_handler.bot

agent = TaskManagementAgent(bot=bot)
user_request_agent = UserRequestAgent(bot=bot)
discord_chat_history_ingestor = DiscordChatHistoryIngestor(bot=bot)

@bot.tree.command(name="log-admin", description="Log an admin to database", guild=bot_handler.guild)
@app_commands.describe(name="Admin Full Name")
async def log_admin(interaction: discord.Interaction, name: str):
    if not name:
        await interaction.response.send_message("Error: Admin must have a name.", ephemeral=True)
        return

    admin_paginator_view = UserLogPaginator(user_name=name, user_type='admin')
    admin_paginator_view.update_dropdown()
    await interaction.response.send_message("Please Select Admin Job Type:", view=admin_paginator_view)


@bot.tree.command(name="log-employee", description="Log an employee to database", guild=bot_handler.guild)
@app_commands.describe(name="Employee Full Name")
async def log_admin(interaction: discord.Interaction, name: str):
    if not name:
        await interaction.response.send_message("Error: Employee must have a name.", ephemeral=True)
        return

    admin_paginator_view = UserLogPaginator(user_name=name, user_type='employee')
    admin_paginator_view.update_dropdown()
    await interaction.response.send_message("Please Select Employee Job Type:", view=admin_paginator_view)


@bot.tree.command(name="log-employee-schedule", description="Log an employee schedule to database", guild=bot_handler.guild)
@app_commands.describe()
async def log_admin(interaction: discord.Interaction):
    employee_schedule_paginator = EmployeeSchedulePaginator()
    employee_schedule_paginator.update_dropdown()
    await interaction.response.send_message("Please Select Employee To Update Schedule:", view=employee_schedule_paginator)

@bot.event
async def on_message(message):
    print(f'Message from {message.author} via Channel {message.channel}: {message.content}')
    # Check if the bot or johanson was mentioned

    # Get all members who can view the channel
    # members_with_access = [member for member in channel.guild.members
    #                     if channel.permissions_for(member).view_channel]

    # # Print or do something with the members
    # member_names = [member.name for member in members_with_access]
    # print(f'Members with access: {member_names}')

    # channel = discord.utils.get(message.guild.text_channels, name=message.channel.name)
    # viewers = [member for member in message.guild.members if channel.permissions_for(member).read_messages]
    # print(f'Viewers: {viewers}')
    admin_bot_channel = bot.get_channel(int(os.getenv("ADMIN_BOT_DISCORD_CHANNEL_ID")))

    if admin_bot_channel.name == message.channel.name or (bot.user in message.mentions and message.author.id == '405840051113558026'):
        # Process the message with the AI agent
        channel_id = str(message.channel.id)
        channel_name = str(message.channel.name)
        print(f'Processing message from {message.author} via Channel {message.channel}: {message.content}')
        response = await agent.process_message(message.content, channel_id, channel_name, SYSTEM_PROMPT)
        print(f'Response: {response}')
        # Send the agent's response

        await admin_bot_channel.send(response)

    if bot.user in message.mentions:
        # Process the message with the AI agent
        channel_id = str(message.channel.id)
        channel_name = str(message.channel.name)
        print(f'Processing message from {message.author} via Channel {message.channel}: {message.content}')
        response = await user_request_agent.process_message(message.content, channel_id, channel_name, message.author.id, message.author.name)
        print(f'Response: {response}')
        # Send the agent's response

        target_channel = bot.get_channel(message.channel.id)
        await target_channel.send(response)

    # Process commands
    await bot.process_commands(message)

# This function will run in the background
@tasks.loop(reconnect=True, hours=24)
async def scheduled_reminder_check():
    """Check for reminders that need to be sent"""
    print("Checking for reminders that need to be sent")

    try:
        # Get all tasks from the database
        tasks = get_tasks()

        # Check if any tasks need to be sent
        for task in tasks:
            if task['due_date'] <= datetime.datetime.now():
                # Use specified channel
                target_channel = bot.get_channel(task['channel_id'])
                target_channel.send(f"Reminder for {task['name']}. \n Description: {task['description']}")
                
                if task['reminder_frequency'] == 'ONCE':
                    # Delete the task from the database
                    delete_task(task['_id'])
        
    except Exception as e:
        print(f"Error: {e}")


# This function will run in the background
@tasks.loop(reconnect=True, hours=24)
async def scheduled_history_timeframe(days_ago=5, limit=500):
    """Get message history within a specific timeframe"""
    print("Getting message history within a specific timeframe")

    try:
        # Calculate the date for days_ago
        start_date = datetime.datetime.now() - datetime.timedelta(days=days_ago)
        channel_id = 1264079091154423948

        # Use specified channel
        target_channel = bot.get_channel(channel_id)

        messages = []
        async for message in target_channel.history(limit=limit, after=start_date):
            messages.append({
                "channel": target_channel.name,
                "message": message.content,
                "author": message.author.name,
                "created_at": message.created_at,
                "user_mentions": [mention.name for mention in message.mentions]
            })

        if not messages:
            await target_channel.send(f"No messages found in the last {days_ago} days.")
            return
        
        # log_discord_chat_history(messages)

        employees = get_employees()
        employees_string = "\n".join([f"Employee name: {employee['name']} - Discord ID: {employee['discord_id']} - Discord Username: {employee['discord_username']}" for employee in employees])
        # messages_string = "\n".join([f"{message['author']} said: '{' and '.join([mention for mention in message['user_mentions']])}{message['message']}' " for message in messages])
        # messages_string = remove_angle_bracket_content(messages_string)

        iterator = 0
        message_batch = ""
        for message in messages:
            print(f"iterator: {iterator}")
            if iterator < 2:
                message_batch += f"{message['author']} said: '{' and '.join([mention for mention in message['user_mentions']])} {message['message']} \n"
                iterator += 1
                continue
            
            try:
                full_messages = f"EMPLOYEES: {employees_string}\n\n MESSAGES: \n{remove_angle_bracket_content(message_batch)}"
                response = await discord_chat_history_ingestor.process_message(full_messages, channel_id, target_channel.name)
                print(f"Response: {response}")
                task_channel_id = 1361986399259332738
                if not response:
                    continue
                payload = json.loads(response)
                task_name = payload['task_name']
                description = payload['description']
                assignee_name = payload['assignee_name']
                next_reminder = payload['next_reminder']
                await bot.get_channel(task_channel_id).send(f"**Successfully created task**\n\n**Task Name:** {task_name}\n**Description:** {description}\n**Assignee:** {assignee_name}\n**Next Reminder:** {next_reminder}")
            except Exception as e:
                print(f'Error sending task to channel: {e}')
            finally:
                message_batch = message_batch.split('\n')[-1] # Get the last message for overlapping messages
                iterator = 0


        # for message in messages_string.split('\n'):
        #     full_messages = f"Employees: {employees_string}\n\n Messages: {message}"

        #     # print(f'Message: {message}')
        #     response = await discord_chat_history_ingestor.process_message(full_messages, channel_id, target_channel.name)
        #     print(f'Finished Response: {response}')
        #     task_channel_id = 1361986399259332738
        #     if not response:
        #         continue
        #     try:
        #         payload = json.loads(response)
        #         task_name = payload['task_name']
        #         description = payload['description']
        #         assignee_name = payload['assignee_name']
        #         next_reminder = payload['next_reminder']
        #         await bot.get_channel(task_channel_id).send(f"**Successfully created task**\n\n**Task Name:** {task_name}\n**Description:** {description}\n**Assignee:** {assignee_name}\n**Next Reminder:** {next_reminder}")
        #     except Exception as e:
        #         print(f'Error sending task to channel: {e}')

        # bot_task_channel = bot.get_channel(1361986399259332738)
        # await bot_task_channel.send(f"Found {len(messages)} messages in the last {days_ago} days:",
        #             file=discord.File("filtered_history.txt"))
    except Exception as e:
        print(f"Error: {e}")


# Wait for the bot to be ready before starting the task
@scheduled_history_timeframe.before_loop
async def before_scheduled_history():
    await bot.wait_until_ready()
    print("Starting scheduled history capture...")

    
if __name__ == "__main__":
    async def main():
        try:
            # Start the scheduled task
            scheduled_history_timeframe.start()
            # Run the bot
            await bot.start(TOKEN)
        except Exception as e:
            print(f"Error in main loop: {e}")
            # Wait a bit before retrying
            await asyncio.sleep(5)
            await main()  # Retry

    # Run the async main function
    asyncio.run(main())
        
        
