# FFXIV_housing_bot
This is a discord bot that keeps track of housing availability. 
Message me at Eno#6033 with questions.

I don't know how README.md works.

To use this bot you need to create a Discord bot, see: https://www.freecodecamp.org/news/create-a-discord-bot-with-python/

I chose to have this bot react to ## +  a command, you can change this on line 61:
>bot = commands.Bot(command_prefix='##', description=description) 

change the command_prefix setting to change the reactive prefix.

What else do you want to know?

>> How to install this in an independent discord bot for private use:
>> 1. Set up a discord bot: "How to Create a Discord Bot Account" from https://www.freecodecamp.org/news/create-a-discord-bot-with-python/
>> 2. Either install anaconda on your comptuer, or on a VPS, or another remote bot hosting site, like... https://pebblehost.com/bot-hosting for example. Use discord.py / Python hosting.
>> 3. Create a virtual environment "> conda create -n yourenvname "
>> 4. Get into the environment by using "> conda activate yourenvname "
>> 5. Navigate to the location you downloaded this repository to "> cd C:\Users\Sadu\Desktop\HousingBot"
>> 6. Install pip "> conda install pip "
>> 7. Use pip to install the dependencies "> pip install -r requirements.txt "
>> 8. Write down your API token in a file called "token.txt" and save it in the repository folder.
>> 9. Make a folder called "Datacenters", and a subfolder inside that called "Crystal", then add whatever your server's name is, e.g. "Balmung" to that as a folder. That plot templates included here need to go into that. Sorry, this is Github's fault. They should be named 01.xlsx ... 24.xlsx. 
>> 10. Run "> python.exe HousingBot.py "
