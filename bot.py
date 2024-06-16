import os
import discord
import subprocess
import random
import string
import asyncio
import socket
import psutil
from datetime import datetime, timedelta
from mcrcon import MCRcon

intents = discord.Intents.default()
intents.messages = True  # Subscribe to message events

client = discord.Client(intents=intents)
project8_exe_path = r'C:\Program Files (x86)\Steam\steamapps\common\Project8Staging\game\bin\win64\project8.exe'
TOKEN = 
SERVER_ADDRESS = 
RCON_PASSWORD = 
PORT_RANGE_START = 
PORT_RANGE_END = 
ADVERTISEMENT_CHANNEL_ID = 

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

async def kill_process(pid, message=None):
    """Kill the process with the given PID if it exists and is a server process."""
    if pid in server_processes:
        if message and server_processes[pid]['creator_id'] != message.author.id:
            await message.author.send("You are not authorized to kill this server.")
            return
        try:
            os.kill(pid, 9)  # Send SIGKILL signal
            print(f'Server with ID {pid} has been killed.')
            del server_processes[pid]
            if pid in zero_player_counts:
                del zero_player_counts[pid]
            if message:
                await message.author.send(f"Server with ID {pid} has been killed.")
        except ProcessLookupError:
            print(f'No process with ID {pid} was found.')
            if message:
                await message.author.send(f"No process with ID {pid} was found.")
    else:
        print(f'No server with ID {pid} found.')
        if message:
            await message.author.send(f"No server with ID {pid} found.")

async def manage_server(pid, port, password):
    """Manage the server behavior after it has been started."""
    try:
        # Allow some time for the server to start
        await asyncio.sleep(20)

        # Connect to RCON
        with MCRcon('localhost', RCON_PASSWORD, port) as mcr:
            print(f"Managing server with ID {pid}")

            # Send initial commands
            print(f"Sending initial command sv_cheats 1 to server with ID {pid}")
            mcr.command("sv_cheats 1")
            await asyncio.sleep(1)

            print(f"Sending command host_timescale to server with ID {pid}")
            mcr.command("host_timescale 0.1")
            
            while True:
                response = mcr.command("status")
                players = 0
                for line in response.splitlines():
                    if "players  :" in line:
                        players = int(line.split(":")[1].strip().split()[0])
                        break

                if players >= 12:
                    print(f"12 or more players detected on server with ID {pid}. Waiting 60s seconds to disable cheats.")
                    await asyncio.sleep(60)  
                    print(f"Sending command sv_cheats 0 to server with ID {pid}")
                    mcr.command("sv_cheats 0")
                    break

                #mcr.command("trooper_kill_all")
                await asyncio.sleep(10)  # Send trooper_kill_all every 10 seconds

    except Exception as e:
        print(f"Failed to manage server with ID {pid}. Error: {e}")

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
        '+map street_test',
        '+sv_password', password  # Add the password as a separate element
    ]
    server_process = subprocess.Popen(command)
    
    # Retrieve the process ID (pid) from the Popen object
    pid = server_process.pid
    
    # Start managing the server behavior asynchronously
    asyncio.create_task(manage_server(pid, port, password))
    
    # Return the process ID
    return pid



async def send_help_message(channel):
    """Send a help message to the specified channel."""
    help_message = (
        "Available commands:\n"
        "1. **SS**: Start a server. Will stay on for 10 minutes if no players joins.\n"
        "2. **kill <ID>**: Kill the server with the specified ID.\n"
        "3. **reset <ID>**: Restart the game on the server with specified ID.\n"
        "4. **RCON <ID> <command>**: Send an RCON command to the server with the specified ID.\n"
        "5. **join <ID>**: Get connection info for the server with the specified ID (if fewer than 12 players).\n"
        "6. **help**: Display this help message.\n"
    )
    help_message += '\nTo receive the connection information for a server, type:\n```@terminal join ID```\n'
    await channel.send(help_message)

async def reset_server(pid, message):
    """Reset the server with the given PID by sending the changelevel command."""
    loop = asyncio.get_event_loop()
    print(f"Attempting to reset server with ID: {pid}")
    if pid in server_processes and server_processes[pid]['creator_id'] == message.author.id:
        port = server_processes[pid]['port']
        try:
            print(f"Connecting to RCON on port {port} with password {RCON_PASSWORD}")
            with MCRcon('localhost', RCON_PASSWORD, port) as mcr:
                response = await loop.run_in_executor(None, mcr.command, "changelevel street_test")
                print(f"RCON response: {response}")
                await message.author.send(f"Server with ID {pid} has been reset.\nResponse: {response}")
        except Exception as e:
            print(f"Failed to reset server with ID {pid}. Error: {e}")
            await message.author.send(f"Failed to reset server with ID {pid}. Error: {e}")
    else:
        print(f"Invalid server ID: {pid} or unauthorized user.")
        await message.author.send("Invalid server ID or unauthorized user.")

async def send_rcon_command(pid, command, message):
    """Send an RCON command to the server with the given PID and return the response."""
    if pid in server_processes and server_processes[pid]['creator_id'] == message.author.id:
        port = server_processes[pid]['port']
        try:
            print(f"Connecting to RCON on port {port} with password {RCON_PASSWORD}")
            with MCRcon('localhost', RCON_PASSWORD, port) as mcr:
                response = mcr.command(command)
                print(f"RCON response for server ID {pid}: {response}")
                await message.author.send(f"RCON command response for server ID {pid}:\n{response}")
        except Exception as e:
            print(f"Failed to send RCON command to server with ID {pid}. Error: {e}")
            await message.author.send(f"Failed to send RCON command to server with ID {pid}. Error: {e}")
    else:
        print(f"Invalid server ID: {pid} or unauthorized user.")
        await message.author.send("Invalid server ID or unauthorized user.")

async def check_server_status():
    """Check the status of all active servers and kill any that have no players three times in a row."""
    loop = asyncio.get_event_loop()
    
    while True:
        for pid, info in list(server_processes.items()):
            port = info['port']
            # Check if the process with pid exists
            if not psutil.pid_exists(pid):
                print(f"Server with ID {pid} has been killed externally.")
                del server_processes[pid]
                if pid in zero_player_counts:
                    del zero_player_counts[pid]
                continue

            try:
                print(f"Checking server status for PID {pid} on port {port}")
                with MCRcon('localhost', RCON_PASSWORD, port) as mcr:
                    response = await loop.run_in_executor(None, mcr.command, "status")
                    print(f"RCON status response for server ID {pid}: {response}")
                    if "players  : 0 humans" in response:
                        zero_player_counts[pid] = zero_player_counts.get(pid, 0) + 1
                        print(f"Server with ID {pid} is found to be idle. Zero player count: {zero_player_counts[pid]}")
                    else:
                        zero_player_counts[pid] = 0
                        print(f"Server with ID {pid} is not idle. Players are present.")
                    
                    if zero_player_counts[pid] >= 3:
                        await kill_process(pid)
                        print(f"Server with ID {pid} has been idle for too long and has been killed.")
                    
                    if "Game State: 6" in response:
                        await kill_process(pid)
                        print(f"Server with ID {pid} is in an invalid game state and has been killed.")
            except Exception as e:
                print(f"Failed to check status for server with ID {pid}. Error: {e}")
        await asyncio.sleep(500)  # Wait X



async def handle_ss_command(message):
    """Handle the 'SS' command to start a new server."""
    port = generate_random_port()  # Generate a random port between PORT_RANGE_START and PORT_RANGE_END
    password = generate_random_password()  # Generate a random 10-digit password
    pid = start_server(port, password)
    server_processes[pid] = {'port': port, 'password': password, 'creator_id': message.author.id}
    zero_player_counts[pid] = 0

    print(f'Server started on port {port}. ID: {pid}')

    # Send the connection information to the user
    response = (
        f"!THIS SERVER WILL BE KILLED IF EMPTY FOR 10 MINUTES JOIN NOW!\n"
        f"Server ID: {pid}\n"
        f"{SERVER_ADDRESS}:{port}\n"
        f"{password}\n"
        f"```\nconnect {SERVER_ADDRESS}:{port}; password {password}\n```\n"
        f"```\n/startlobby server:{SERVER_ADDRESS}:{port} password:{password} preset:EU_nodraft\n```"

    )
    await message.author.send(response)

async def handle_message(message):
    """Handle incoming messages and execute the appropriate command."""
    content = message.content
    parts = content.split()

    # Check if the message is empty
    if not parts:
        return

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
            if part.lower() in ["reset", "kill", "join"]:
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
        elif command == "join":
            await handle_join_command(server_id, message)
    else:
        if "SS" in message.content:
            await handle_ss_command(message)
        elif "help" in message.content.lower():
            await send_help_message(message.channel)  # Send help message in the channel where it was requested
        else:
            await message.author.send("No valid command found in the message.")

async def handle_join_command(pid, message):
    """Handle the 'join <ID>' command to send connection info to the user if there are fewer than 12 players."""
    if pid in server_processes:
        port = server_processes[pid]['port']
        try:
            with MCRcon('localhost', RCON_PASSWORD, port) as mcr:
                response = mcr.command("status")
                players = 0
                for line in response.splitlines():
                    if "players  :" in line:
                        players = int(line.split(":")[1].strip().split()[0])
                        break
                if players < 12:
                    password = server_processes[pid]['password']
                    response_message = (
                        f"Server ID: {pid}\n"
                        f"{SERVER_ADDRESS}:{port}\n"
                        f"{password}\n"
                        f"```\nconnect {SERVER_ADDRESS}:{port}; password {password}\n```\n"
                    )
                    await message.author.send(response_message)
                    await message.author.send(f'To receive the connection information for this server, type:\n```@terminal join {pid}```')
                else:
                    await message.author.send("Server is full (12 players).")
        except Exception as e:
            print(f"Failed to handle join command for server with ID {pid}. Error: {e}")
            await message.author.send(f"Failed to handle join command for server with ID {pid}. Error: {e}")
    else:
        print(f"Invalid server ID: {pid}")
        await message.author.send("Invalid server ID.")

async def advertise_active_servers(channel):
    """Advertise the list of active servers in the specified channel every minute."""
    last_message = None  # Track the last sent message
    
    while True:
        try:
            if server_processes:
                active_servers = []
                for pid, info in list(server_processes.items()):  # Create a list to iterate over
                    port = info['port']
                    try:
                        with MCRcon('localhost', RCON_PASSWORD, port) as mcr:
                            response = mcr.command("status")
                            # Extract the number of players from the response
                            players = "unknown"
                            for line in response.splitlines():
                                if "players  :" in line:
                                    players = line.split(":")[1].strip().split()[0]
                                    break
                            creator = await client.fetch_user(info['creator_id'])
                            active_servers.append(f"ID: {pid}, Created by: {creator.name}, Players: {players}")
                    except Exception as e:
                        print(f"Failed to get status for server with ID {pid}. Error: {e}")
                        creator = await client.fetch_user(info['creator_id'])
                        active_servers.append(f"ID: {pid}, Created by: {creator.name}, Players: unknown")
                
                advertisement_message = "Active server IDs:\n" + "\n".join(active_servers)
                advertisement_message += '\n\nTo receive the connection information for a server, type:\n```@terminal join ID```\n'

                # Delete previous message if exists
                if last_message:
                    try:
                        await last_message.delete()
                    except discord.NotFound:
                        pass  # Handle case where message was already deleted

                # Send new advertisement
                last_message = await channel.send(advertisement_message)
            else:
                advertisement_message = "No active servers.\nTo start a server, type\n```@terminal SS```"
                
                # Delete previous message if exists
                if last_message:
                    try:
                        await last_message.delete()
                    except discord.NotFound:
                        pass  # Handle case where message was already deleted

                # Send new advertisement
                last_message = await channel.send(advertisement_message)
            
            await asyncio.sleep(60)  # Wait 1 minute

        except RuntimeError as e:
            print(f"Runtime error in advertise_active_servers: {e}")
        except Exception as e:
            print(f"Unexpected error in advertise_active_servers: {e}")





@client.event
async def on_ready():
    print(f'Logged in as {client.user}')
    # Start the server status check loop
    client.loop.create_task(check_server_status())
    # Start the advertisement loop
    advertisement_channel = client.get_channel(ADVERTISEMENT_CHANNEL_ID)
    client.loop.create_task(advertise_active_servers(advertisement_channel))

@client.event
async def on_message(message):
    if isinstance(message.channel, discord.DMChannel):
        print(f'Message from {message.author}: {message.content}')  # Log message in the terminal
    else:
        print(f'Message from {message.author} in #{message.channel.name} ({message.channel.id}): {message.content}')  # Log message in the terminal

    # Ignore messages from the bot itself
    if message.author == client.user:
        return

    # Handle the message if it's in any channel
    await handle_message(message)

client.run(TOKEN)
