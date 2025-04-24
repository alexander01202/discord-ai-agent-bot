# Output prompt
OUTPUT_PROMPT = """
Format your response as a JSON object with the following fields:
- response: The response to the user's message (empty string if no task detected)
- tools_needed: A list of tools that are needed to generate the response
- tools_with_params: A list of tools that are needed to generate the response, along with their parameters as a dictionary
- is_task: Boolean indicating if a task was detected in the message

Example for task detected:
{
    "response": "The response to the user's message",
    "tools_needed": ["tool1", "tool2"],
    "tools_with_params": {"tool1": {"param1": "value1", "param2": "value2"}, "tool2": {"param1": "value1", "param2": "value2"}},
    "is_task": true
}


Do not include any other text in your response. Just the JSON object.
"""

USER_REQUEST_OUTPUT_PROMPT = """
Format your response as a JSON object with the following fields:
- response: The response to the user's message (empty string if no task detected)

Example for task detected:
{
    "response": "The response to the user's message"
}

Do not include any other text in your response. Just the JSON object.
"""

USER_REQUEST_PROMPT = """
Analyze the context below. Intrepret it in 100 different ways.
Within the context text, you'll frequently encounter timestamps. Ignore them unless they are relevant to the user's message.

Once you have interpreted the context, understand the user's message and provide a response to the user's message in a friendly and conversational manner.
Keep your response concise, short and to the point. If the user's message is too vague, then ask for more information or clarity so that you can provide a more accurate response.

CONTEXT:
{context}

END OF CONTEXT


USER'S MESSAGE:
{user_message}
"""

DEFINITION_OF_TASK = """
a task is a concise, action-oriented task or instruction used in a collaborative, operational context—typically shared via messaging platforms like Slack or Discord. Zelit entries mix checklist items, observations, follow-ups, and logistics in a casual tone but still drive clear outcomes.

Here’s a clear and well-defined explanation of a Zelit:

task – Definition
A task is a short, directive-style communication used to assign, coordinate, or document tasks, observations, or logistical updates—often in fast-moving operational environments such as property maintenance, farm work, or project fieldwork.

task are characterized by:

Clarity: Specific tasks or checks with actionable outcomes.

Context: Often include location, property IDs, or relevant parties.

Tone: Informal yet purposeful, typically conversational.

Delivery: Commonly shared in chat apps or team collaboration tools.

Multi-step Structure: May include subtasks or sequences.

Asynchronous Ready: Written so the recipient can act on it independently.

Examples of What a task Can Be
A list of steps someone should take upon arriving at a site.

A reminder to document or report a condition (e.g. photos, videos).

A quick note on updating shared documentation or processes.

A casual but clear instruction to check or fix something.

REAL LIFE EXAMPLES:
1. Do we have a chain in the work shed? Maybe joey can use the Polaris to pull it outward while you delicately saw the trunk
2. @RobW2512 before entering the property today, can you do the following: 
   1. Walk the fence line for both 9530 and 9610, inspecting the fence and posting relevant pictures under ⁠inspection
   2. Pick up any trash you see
   3. Check if the recycling was collected
 Let me know how long all of this takes. If the recycling isn't collected, take a picture of the bin from the opposite side of the street so I can send it to CARDS and let them know. If it was collected bring it in.
3. A few more things @RobW2512: 
   1. Can you check if water is still leaking outside the 9530 gate? I called the department of public works yesterday and they said they would send someone over.
   2. Can you check the integrity of the fence on the property before you leave?
4. Are all the garbage bins cleared?
"""

TOOLS = """
- fetch_employees_tool [fetches employees and their information (eg schedules, names, etc) from the database]
- create_task_tool [creates a task in the database]
   - task_name (required) [str]: The name of the task
   - description (required) [str]: The description of the task
   - assignee_name (optional) [str]: The employee name of who will do the task or who is mentioned/referred to in the task
   - priority (optional) [str]: The priority of the task (low, medium, high, urgent) (default: medium)
   - reminder_frequency (optional) [str]: The reminder frequency of the task (hourly, daily, weekly, monthly, once) (default: once)
   - specific_weekday (optional) [int]: The specific weekday of the task (0=Monday through 6=Sunday) (default: None)
- update_task_tool [updates a task in the database]
   - task_id (required) [str]: The id of the task to update
   - kwargs (optional) [dict]: The task information(s) to update
- log_employees_to_db_from_channel_tool [logs members of a discord channel to the database as employees]
- update_employee_tool [updates an employee in the database by name]
- log_employee_tool [logs an employee to the database]
- log_employee_schedule_tool [logs an employee schedule to the database]
- get_task_tool [gets all tasks and their information from the database]
"""

_CREATE_TASK_PROMPT = f"""
This is the definition of a task:
{DEFINITION_OF_TASK}

Once you have recognized that there is a task or action that needs to be taken, you are to use the tools provided to you to create the task in the database.


If a task is detected, collect the following information. All fields are optional except for the task name and description:
1. Task name (required)
2. Task description (required)
3. Assignee (employee who will do the task or who is mentioned in the task) (optional)
4. Priority level (LOW, MEDIUM, HIGH, URGENT) (optional) (default: MEDIUM)
5. Reminder frequency (HOURLY, DAILY, WEEKLY, MONTHLY, ONCE) (optional) (default: ONCE)
6. Specific weekdays (0=Monday through 6=Sunday) (optional)

IMPORTANT: Always use the tools provided to you. Don't make up information about employees or tasks. Keep the conversation friendly.
"""

# System prompt
SYSTEM_PROMPT = f"""You are an AI assistant that helps with task and employee management and scheduling. 
You work for a company that employees farmhands. 
You have access to the following tools:
{TOOLS}

Some tools require extra information eg. update_employee requires to know if the employee is actually an employee therefore you need to use fetch_employees to get a list of all employees. 
If you need more information, either check if other tools can help you get the information or ask the user for it.
"""

SYSTEM_PROMPT_FOR_CHAT_HISTORY = f"""You are an AI assistant that helps with task and employee management and scheduling.
You work for a company that employees farmhands.
You have access to the following tools:
{TOOLS}

The admin of the discord channel is j_4381 and everyone else is a farmhand/employee.
Analyze each message and find out if there are any tasks or actions that needs to be taken and who needs to do them (if any) (eg assignee).
Use the create_task_tool to create the task in the database.

{_CREATE_TASK_PROMPT}
"""

# Your first job is to be able to recognize when a message or text contains a task or action that needs to be taken.
# {_CREATE_TASK_PROMPT}

# If it isn't a task, then check if you can use the other tools to help the user.


# SCENARIO 2:
# If the user mentions an employee or wants to get an employee's schedule, you should use the fetch_employees tool to get a list of all employees and their schedules.
# If the employee is not in the list, ask the user to provide a valid employee name and list the employees available.
# Do this iteratively until the employee is in the list.