import os
import discord
import subprocess
import random
import string
import asyncio
import socket
from datetime import datetime, timedelta
from mcrcon import MCRcon

intents = discord.Intents.default()
intents.messages = True  # Subscribe to message events

client = discord.Client(intents=intents)
project8_exe_path = 
TOKEN = 
SERVER_ADDRESS = 
RCON_PASSWORD = 
PORT_RANGE_START = 
PORT_RANGE_END = 

# Dictionary to store the process objects with their associated IDs (PIDs), ports, passwords, and creator IDs
server_processes = {}

# Dictionary to track the number of consecutive zero player statuses
zero_player_counts = {}

def generate_random_password(length=10):
    """Generate a random password of given length consisting of digits."""
    return ''.join(random.choices(string.digits, k=length))

def is_port_in_use(port):
    """Check if a given port is currently in use."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0

def generate_random_port(start=PORT_RANGE_START, end=PORT_RANGE_END):
    """Generate a random port number within the specified range and ensure it's not in use."""
    while True:
        port = random.randint(start, end)
        if not is_port_in_use(port):
            return port

async def kill_process(pid, message):
    """Kill the process with the given PID if it exists and is a server process."""
    if pid in server_processes:
        try:
            os.kill(pid, 9)  # Send SIGKILL signal
            print(f'Server with PID {pid} has been killed.')
            del server_processes[pid]
            if pid in zero_player_counts:
                del zero_player_counts[pid]
            await message.channel.send(f"Server with ID {pid} has been killed.")
        except ProcessLookupError:
            print(f'No process with PID {pid} was found.')
            await message.channel.send(f"No process with ID {pid} was found.")
    else:
        print(f'No server with PID {pid} found.')
        await message.channel.send(f"No server with PID {pid} found.")

async def kill_all_processes(message):
    """Kill all running server processes and send a message for each killed server."""
    global server_processes
    for pid in list(server_processes.keys()):
        await kill_process(pid, message)
    server_processes.clear()
    zero_player_counts.clear()
    await message.channel.send("All running server processes have been killed.")

def start_server(port, password):
    """Start the server with the specified port and password."""
    command = [
        project8_exe_path,
        '-dedicated',
        '-insecure',
        '-convars_visible_by_default',
        '-allow_no_lobby_connect',
        '-usercon',
        '-ip', '0.0.0.0',  # Bind to all available IP addresses
        '-port', str(port),  # Convert port to string
        '-strictportbind',
        '+map start',
        '+sv_password', password  # Add the password as a separate element
    ]
    server_process = subprocess.Popen(command)
    return server_process.pid

async def send_help_message(channel):
    """Send a help message to the specified channel."""
    help_message = (
        "Available commands:\n"
        "1. **SS**: Start a server.\n"
        "2. **killall**: Kill all running server processes.\n"
        "3. **kill <ID>**: Kill the server with the specified ID.\n"
        "4. **list**: List all active server IDs.\n"
        "5. **reset <ID>**: Restart the game on the server with specified ID.\n"
        "6. **RCON <ID> <command>**: Send an RCON command to the server with the specified ID.\n"
        "7. **help**: Display this help message.\n"
    )
    await channel.send(help_message)

async def list_active_servers(channel):
    """List all active server IDs."""
    if server_processes:
        active_servers = "\n".join([
            f"ID: {pid}, Port: {info['port']}, Password: {info['password']}, Created by: <@{info['creator_id']}>\n"
            f"Connect Command: \n ```connect {SERVER_ADDRESS}:{info['port']}; password {info['password']}```"
            for pid, info in server_processes.items()
        ])
        await channel.send(f"Active server IDs:\n{active_servers}")
    else:
        await channel.send("No active servers.")

async def reset_server(pid, message):
    """Reset the server with the given PID by sending the changelevel command."""
    print(f"Attempting to reset server with PID: {pid}")
    if pid in server_processes:
        if message.author.id != server_processes[pid]['creator_id']:
            await message.channel.send("You are not authorized to reset this server.")
            return
        port = server_processes[pid]['port']
        try:
            print(f"Connecting to RCON on port {port} with password {RCON_PASSWORD}")
            with MCRcon('localhost', RCON_PASSWORD, port) as mcr:
                response = mcr.command("changelevel street_test")
                print(f"RCON response: {response}")
                await message.channel.send(f"Server with ID {pid} has been reset.\nResponse: {response}")
        except Exception as e:
            print(f"Failed to reset server with ID {pid}. Error: {e}")
            await message.channel.send(f"Failed to reset server with ID {pid}. Error: {e}")
    else:
        print(f"Invalid server ID: {pid}")
        await message.channel.send("Invalid server ID.")

async def send_rcon_command(pid, command, message):
    """Send an RCON command to the server with the given PID and return the response."""
    if pid in server_processes:
        if message.author.id != server_processes[pid]['creator_id']:
            await message.channel.send("You are not authorized to send RCON commands to this server.")
            return
        port = server_processes[pid]['port']
        try:
            print(f"Connecting to RCON on port {port} with password {RCON_PASSWORD}")
            with MCRcon('localhost', RCON_PASSWORD, port) as mcr:
                response = mcr.command(command)
                print(f"RCON response for server ID {pid}: {response}")
                await message.channel.send(f"RCON command response for server ID {pid}:\n{response}")
        except Exception as e:
            print(f"Failed to send RCON command to server with ID {pid}. Error: {e}")
            await message.channel.send(f"Failed to send RCON command to server with ID {pid}. Error: {e}")
    else:
        print(f"Invalid server ID: {pid}")
        await message.channel.send("Invalid server ID.")

async def check_server_status():
    """Check the status of all active servers and kill any that have no players three times in a row."""
    while True:
        for pid, info in list(server_processes.items()):
            port = info['port']
            try:
                print(f"Checking server status for PID {pid} on port {port}")
                with MCRcon('localhost', RCON_PASSWORD, port) as mcr:
                    response = mcr.command("status")
                    print(f"RCON status response for server ID {pid}: {response}")
                    if "players  : 0 humans" in response:
                        zero_player_counts[pid] = zero_player_counts.get(pid, 0) + 1
                    else:
                        zero_player_counts[pid] = 0
                    if zero_player_counts[pid] >= 3:
                        await kill_process(pid)
                    if "Game State: 6" in response:
                        await kill_process(pid)
            except Exception as e:
                print(f"Failed to check status for server with ID {pid}. Error: {e}")
        await asyncio.sleep(500)  # Wait 

async def handle_message(message):
    """Handle the incoming message and start the server if the message contains 'SS'."""
    global server_processes

    # Log the message content
    print(f'Received message: {message.content}')

    # Split the message content into parts, ignoring mentions
    content = message.content
    for user in message.mentions:
        content = content.replace(f'<@{user.id}>', '').strip()
    parts = content.split()

    # Iterate through each part to find the command and ID
    command = None
    server_id = None
    rcon_command = None

    if parts[0].lower() == "rcon" and len(parts) > 2 and parts[1].isdigit():
        command = parts[0].lower()
        server_id = int(parts[1])
        rcon_command = " ".join(parts[2:])
    else:
        for part in parts:
            if part.lower() in ["reset", "kill"]:
                command = part.lower()
            elif part.isdigit():
                server_id = int(part)

    # Process the command and ID
    if command and server_id is not None:
        if command == "reset":
            await reset_server(server_id, message)
        elif command == "kill":
            await kill_process(server_id, message)
        elif command == "rcon":
            await send_rcon_command(server_id, rcon_command, message)
    else:
        if "SS" in message.content:
            port = generate_random_port()  # Generate a random port between PORT_RANGE_START and PORT_RANGE_END
            password = generate_random_password()  # Generate a random 10-digit password
            pid = start_server(port, password)
            server_processes[pid] = {'port': port, 'password': password, 'creator_id': message.author.id}
            zero_player_counts[pid] = 0

            print(f'Server started on port {port}. PID: {pid}')

            # Send the connection information to the channel
            response = (
                f"Server ID: {pid}\n"
                f"{SERVER_ADDRESS}:{port}\n"
                f"{password}\n"
                f"```\nconnect {SERVER_ADDRESS}:{port}; password {password}\n```\n"
            )
            await message.channel.send(response)

        elif "killall" in message.content.lower():
            await kill_all_processes(message)

        elif "list" in message.content.lower():
            await list_active_servers(message.channel)

        elif "help" in message.content.lower():
            await send_help_message(message.channel)

        else:
            print("No valid command found in the message.")

@client.event
async def on_ready():
    print(f'Logged in as {client.user}')
    # Start the server status check loop
    client.loop.create_task(check_server_status())

@client.event
async def on_message(message):
    print(f'Message from {message.author} in #{message.channel.name} ({message.channel.id}): {message.content}')  # Log message in the terminal

    # Ignore messages from the bot itself
    if message.author == client.user:
        return

    # Handle the message if it's in any channel
    await handle_message(message)

client.run(TOKEN)
