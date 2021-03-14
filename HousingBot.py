# Dependencies:
# Discord API for python:
import discord
from discord.ext import commands
from discord.ext import tasks
from discord.ext.tasks import loop

# Asynchronous actions library: 
import asyncio
import threading

# Utilities for database stuff:
import re
import json
import urllib
import pandas
import glob

# Utilities for tracking times:
from datetime import datetime
import pytz

# -------------------------------------------
"""
Information:
This bot was made by Enono Eno to assist with FFXIV housing tracking.
Commands:
    open, list, forsale
        These add the plot following the command to the database and issue a user group alert
        ex: input: ##open mist ward 12 plot 5
            output: mist ward 12 plot 5 is set to Available: 1, and the time of listing is recorded.
            in channel: @SmallMist, a small plot has opened. Mist, Ward 12, Plot 5. Prime time will be at 5pm EST.
    close, unlist, sold, sell
        These remove the plot following the command to the database and mark the original callout as 'sold'
        ex: input: ##unlist mist ward 12 plot 5
            output: mist ward 12 plot 5 is set to Available: 0, and the time of listing is removed. An emoji is added to the original listing.
            in channel: @SmallMist, <st>a small plot has opened. Mist, Ward 12, Plot 5. Prime time will be at 5pm EST.</st> was sold.
    sweep, report
        This scans the database for open plots and returns a report on the currently available plots and their anticipated primetimes.
        ex: input: ##report
        output: scans all plots for openings...
        in channel: [1] Plots available... [1] Goblet, [S] 01-24 <12pm> 
        or whatever...
"""

# -------------------------------------------
# Main:

# Read in your discord bot token (which should be kept secret):
with open ("token.txt", "r") as inFile:
    data = inFile.readlines()
TOKEN = data[0]

# Init the client interface from discord API
client = discord.Client()

# Bot description when quered by user:
description = '''This is a bot made to assist in the management of housing in FFXIV.'''

# Assign a prefix for triggering bot actions:
bot = commands.Bot(command_prefix='##', description=description)

# Where are the DC spreadsheet kept?
DC_LOC = "/DataCenters"

# This is our database of what servers are on what datacenters:
with open('datacenter_dictionary.txt') as f: 
    data = f.read() 
DC_DICT  = json.loads(data) 

# Where are the COOKIES logged?
with open('playerCookies.txt') as f: 
    data = f.read() 
    COOKIES  = json.loads(data) 
    
# This goes into the console on login:
@bot.event
async def on_ready():
    print('Logged in as:')
    print(bot.user.name)
    print(bot.user.id)
    print('------')
    print('Logged in successfully.')
    print('>>')
     
# -------------------------------------------
# Text Commands
@bot.command()
async def exampleFunction(context):
    """An example of how bot functions work for you, the code reader."""
    text = context.message.content 
    await context.send("You said: " + text)
    return
    
# Commands that call for listing properties:
@bot.command(pass_context = True , aliases=['open','Open', 'list', 'List', 'forsale', 'Forsale', 'ForSale'])
async def open_plot(context):
    """List a house as being open for purchase."""
    print("open proxy started...")
    await openInternal(context)    
    return
    
# Commands that call for unlisting properties:
@bot.command(pass_context = True , aliases=['close','Close', 'unlist', 'Unlist', 'sold', 'Sold', 'sell', 'Sell'])  
async def close_plot(context):
    """List a house as being closed to purchases."""
    await closeInternal(context)  
    return

# These ask for a sweep report.    
@bot.command(pass_context = True , aliases=['Sweep','report','Report', ])      
async def sweep(context):
    """Display a readout of current server status in terms of open plots."""
    print("Sweep report being generated...")
    await serverStatus(context) 
    return

@bot.command(pass_context = True , aliases=['wishlist', 'Wishlist', 'Wish',])      
async def wish(context):
    """When used, your name will be written down and pinged when a particular plot is opened."""
    await addWishlist(context) 
    return
    
@bot.command(pass_context = True, aliases=['unwishlist', 'Unwishlist', 'Unwish'])      
async def unwish(context):
    """When used, your name will be written down and pinged when a particular plot is opened."""
    await removeWishlist(context) 
    return

@bot.command(pass_context = True, aliases=['Cookies'])      
async def cookies(context):
    """Checks to see how many cookies you have."""
    author = str(context.author.id)    
    c = 0;
    if author in COOKIES.keys(): 
        c = COOKIES[author]
        await context.send("You have " + str(c) + " cookies. Good job!")
    else: 
        await context.send("You don't have any cookies, report open plots to get some.")
    return   
    
## Only admins can call these commands:
# This commands is meant to save the admins time assigning channels for primetime and sweep announcements in the DC_DICT dictionary. 
@bot.command(pass_context = True) 
@commands.has_role("Admin")  # Only for admin use.
async def assemble_reports(context):    
    # scan channel names:
    await getReportingChannels(context)
    # :thumbsup: when done:
    await context.message.add_reaction('\U0001F44D')
    return

## Events: 
#for message cleanups:
@bot.event
async def on_reaction_add(reaction, user):
    msg = reaction.message
    if msg.author.id == bot.user.id:
        if reaction.emoji == '\U0000274C':
            await msg.delete()
  
## Internal Commands:
async def openInternal(context):
    # Figure out what DC and Server we're in:
    # Imagine the input to be ##open Mist w10 p15. in #Zalera-Plots
    fileLoc, district, callout, wNum, pNum  = await getDatabase(context)
    print("Opening...")
    
    # Make sure this returned a value:
    if "NULL" in fileLoc:
        print("database not found...")
        return
    
    # Read the database spreadsheet:
    wardMatrix = pandas.read_excel(fileLoc, engine='openpyxl')
    # Set up some datatypes that confuse pandas:
    wardMatrix = await pandasSantize(wardMatrix)
    
    # See if the ward is already listed:
    isAvail = wardMatrix.at[pNum-1,'Available']
    print(isAvail)
    if isAvail == 1:
        await context.send("This plot was already listed as open on " + wardMatrix.at[pNum-1,'Listing Time'])
        return
        
    # If it isn't already listed... list it!
    if isAvail == 0:
        # Get time:
        tz = pytz.timezone('US/Eastern')
        now = datetime.now(tz)
        wardMatrix.at[pNum-1,'Listing Time'] = str(now.month) + '/' + str(now.day) + '/' + str(now.hour)
        wardMatrix.at[pNum-1,'Available'] = 1
        # Get the prime time hour:
        ptTime = now.hour + 10
        ptZone = 'am'
        if ptTime > 23:
            ptTime = ptTime - 24
        if ptTime > 11:
            ptZone = 'pm'
        if ptTime > 12:
            ptTime = ptTime - 12
            
        author = str(context.author.id)   
        if author in COOKIES.keys(): 
            COOKIES[author] += 1 
        else: 
            COOKIES[author] = 1
        with open("playerCookies.txt", "w") as outfile:  
            json.dump(COOKIES, outfile) 
        

    # Look up house size:
    hVal = wardMatrix.at[pNum-1,'Size']
    if 'S' in hVal:
        hSize = "Small"
    if 'M' in hVal:
        hSize = "Medium"
    if 'L' in hVal:
        hSize = "Large"
    
    # update the callout string to reflect size:
    callout = hSize + callout
    
    print("Sending Callout...")
    # Post the listing:
    sentMessage = await context.send(discord.utils.get(context.guild.roles, name=callout).mention + ", a " + hSize.lower() + " plot has opened at: " + district + ", Ward " + str(wNum) + ", Plot " + str(pNum) + ". Prime time will be at " + str(ptTime) + ptZone + " EST.")
    
    await checkWish(context,wardMatrix,pNum)
    
    # Save the message ID for when the plot sells:
    message_id = sentMessage.id
    
    # Pandas will destroy this number if we don't edit it a little...
    wardMatrix.at[pNum-1,'ListingID'] = "s" + str(message_id)

    # Save edited database:
    wardMatrix.to_excel(fileLoc, "Sheet1", index = False, header = True, engine='xlsxwriter')
    
    # Write the log entry:
    tz = pytz.timezone('US/Eastern')
    now = datetime.now(tz)
    ptTime = now.hour 
    ptZone = 'am'
    if ptTime > 23:
        ptTime = ptTime - 24
    if ptTime > 11:
        ptZone = 'pm'
    if ptTime > 12:
        ptTime = ptTime - 12
    nhour = now.hour
    if nhour > 12:
        nhour = nhour - 12
    
    logLoc  = await getLogfile(context)
    logfile = open(logLoc,'a+') 
    
    logfile.write("[" + str(now.month) + "-" + str(now.day) + "-" + str(now.year) + " " + str(now.hour) + ":" + str(now.minute)  + "] ")
    logfile.write(district.capitalize() + " Ward " + str(wNum).zfill(2) + " Plot " + str(pNum).zfill(2) + " [" + wardMatrix.at[pNum-1,'Size'] + "] became available at " + str(nhour).zfill(2) + ":" + str(now.minute).zfill(2) + ptZone + "." + '\n')
    
    logfile.close() 
    
    # done!
    return


async def closeInternal(context):
    #Figure out what DC and Server we're in:
    fileLoc, district, callout, wNum, pNum  = await getDatabase(context)
    
    # Make sure this returned a value:
    if "NULL" in fileLoc:
        print("database not found...")
        return
        
    # Read the database spreadsheet:
    wardMatrix = pandas.read_excel(fileLoc, engine='openpyxl')
    wardMatrix = await pandasSantize(wardMatrix)
    
    # Check to make sure this plot is actually up for sale:
    isAvail = wardMatrix.at[pNum-1,'Available']
    # If not, tell the command user:
    if isAvail == 0:
        await context.send("This plot is not currently listed as available.")
        return
    
    # Otherwise, delist the plot:
    wardMatrix.at[pNum-1,'Available'] = 0
    
    # Get the listing post:
    fmID = wardMatrix.at[pNum-1,'ListingID']
    # Remove the 's'
    fmID = fmID[1:]
    # Target the listing post:
    fMessage = await context.fetch_message(fmID)
    formerContent = fMessage.content 
    
    # Timestamp the sale:
    tz = pytz.timezone('US/Eastern')
    now = datetime.now(tz)
    hour = now.hour
    tzStamp = 'am'
    if hour > 11:
        tzStamp = 'pm'
    if hour > 12:
        hour = hour - 12

    # Edit the listing to reflect a sale:
    await fMessage.edit(content = (formerContent + " **This plot was sold at " + str(hour) + tzStamp + " EST.**"))
    # React with the all important sold emoji!
    await fMessage.add_reaction(r":sold:814622054379683890")
    
    # Save edited database:
    wardMatrix.to_excel(fileLoc, "Sheet1", index = False, header = True, engine='xlsxwriter')
    
    # Write the log entry:
    tz = pytz.timezone('US/Eastern')
    now = datetime.now(tz)
    ptTime = now.hour 
    ptZone = 'am'
    if ptTime > 23:
        ptTime = ptTime - 24
    if ptTime > 11:
        ptZone = 'pm'
    if ptTime > 12:
        ptTime = ptTime - 12
    nhour = now.hour
    if nhour > 12:
        nhour = nhour - 12
    
    logLoc  = await getLogfile(context)
    logfile = open(logLoc,'a+') 
    
    logfile.write("[" + str(now.month) + "-" + str(now.day) + "-" + str(now.year) + " " + str(now.hour) + ":" + str(now.minute)  + "] ")
    logfile.write(district.capitalize() + " Ward " + str(wNum).zfill(2) + " Plot " + str(pNum).zfill(2) + " [" + wardMatrix.at[pNum-1,'Size'] + "] was sold at " + str(nhour).zfill(2) + ":" + str(now.minute).zfill(2) + ptZone)
    
    # how long was it up?
    LT = wardMatrix.at[pNum-1,'Listing Time']
    sp = str(LT).split("/")
    lMon = int(sp[0])    
    lDay = int(sp[1])
    lHour = int(sp[2])
    qual = ""
    # this definitely isn't perfect...
    if now.day > lDay:
        lHour = lHour - 24
    if now.month > lMon:
        qual = " or more"
    listHours = now.hour - lHour
    
    logfile.write(" after being listed for " + str(listHours) + qual + " hours." + '\n')
    wardMatrix.at[pNum-1,'Listing Time']
    
    logfile.close() 
    
    # Done!
    return
 
 
async def serverStatus(context):
    # This function 'sweeps' the database for available plots:
    
    # Get channel name:
    text = context.channel.name
    text = text.lower()
    print(text)
    
    dc = "none"
    server = "none"
    
    # Start a dictionary search. DC_DICT has each DC as a function of the server name.
    breakout = 1
    for key in DC_DICT:
        if key in text:
            server = key
            dc = DC_DICT[key]['datacenter']
            text.replace(key, '')
            breakout = 0
    
    # Prevent reporting if the message didn't come from a plot reporting channel:
    if breakout == 1:
        print("Exited assignment due to inappropriate reporting location.")
        return
    
    # figure out what DC and server paths are
    fileLoc = r"Datacenters/" + dc.capitalize() + "/" + server.capitalize() + "/"
    print(fileLoc)
    
    # write down total plots for report
    totalPlots = 0
    
    print("Sweep report being generated for Goblet...")
    gFiles = fileLoc + "Goblet/"
    
    # Get list of datasheets:
    gGlob = glob.glob(gFiles + "*.xlsx")
   
    # go through them one by one:
    nGobs = 0
    gString = ""
    for file in gGlob:
        wardMatrix = pandas.read_excel(file, engine='openpyxl')
        wardMatrix = await pandasSantize(wardMatrix)
        file = re.sub('\D', '', file)
        ward = int(file)
        for i in range(0,60):
            if wardMatrix.at[i,'Available'] == 1:
                totalPlots = totalPlots + 1
                nGobs = nGobs + 1
                PT, ampm = await formatPT(wardMatrix.at[i,'Listing Time'])
                gString = gString + " [" + wardMatrix.at[i,'Size'] + "] " + str(ward).zfill(2) + "-" + str(i+1).zfill(2) + " <" + str(PT) + ampm + ">,"
    if nGobs > 0:
        gString = gString[:-1] + "."
    if nGobs == 0:
        gString = "No plots available."
    gString = "[" + str(nGobs) + "] " + '\U00002600' + " Goblet: " + gString + '\n'
    
    print("Sweep report being generated for Lavender Beds...")
    lbFiles = fileLoc + "LavenderBeds/"
    
    # Get list of datasheets:
    lbGlob = glob.glob(lbFiles + "*.xlsx")
    # go through them one by one:    
    nLavs = 0
    lbString = ""
    for file in lbGlob:
        wardMatrix = pandas.read_excel(file, engine='openpyxl')
        file = re.sub('\D', '', file)
        ward = int(file)
        for i in range(0,60):
            if wardMatrix.at[i,'Available'] == 1:
                totalPlots = totalPlots + 1
                nLavs = nLavs + 1
                PT, ampm = await formatPT(wardMatrix.at[i,'Listing Time'])
                lbString = lbString + " [" + wardMatrix.at[i,'Size'] + "] " + str(ward).zfill(2) + "-" + str(i+1).zfill(2) + " <" + str(PT) + ampm + ">,"
    if nLavs > 0:
        lbString = lbString[:-1] + "."
    if nLavs == 0:
        lbString = "No plots available."
    lbString = "[" + str(nLavs) + "] " + '\U0001f490' + " Lavender Beds: " + lbString + '\n'
    
    print("Sweep report being generated for Mist...")
    mFiles = fileLoc + "Mist/"
    
    # Get list of datasheets:
    mGlob = glob.glob(mFiles + "*.xlsx")
    # go through them one by one:    
    nMists = 0
    mString = ""
    for file in mGlob:
        wardMatrix = pandas.read_excel(file, engine='openpyxl')
        file = re.sub('\D', '', file)
        ward = int(file)
        for i in range(0,60):
            if wardMatrix.at[i,'Available'] == 1:
                totalPlots = totalPlots + 1
                nMists = nMists + 1
                PT, ampm = await formatPT(wardMatrix.at[i,'Listing Time'])
                mString = mString + " [" + wardMatrix.at[i,'Size'] + "] " + str(ward).zfill(2) + "-" + str(i+1).zfill(2) + " <" + str(PT) + ampm + ">,"
    if nMists > 0:
        mString = mString[:-1] + "."
    if nMists == 0:
        mString = "No plots available."
    mString = "[" + str(nMists) + "] " + '\U0001F30A' + " Mist: " + mString + '\n'
    
    print("Sweep report being generated for Shirogane...")
    sFiles = fileLoc + "Shirogane/"
    
    # Get list of datasheets:
    sGlob = glob.glob(sFiles + "*.xlsx")
    # go through them one by one:    
    nShiros = 0
    shString = ""
    for file in sGlob:
        wardMatrix = pandas.read_excel(file, engine='openpyxl')
        file = re.sub('\D', '', file)
        ward = int(file)
        for i in range(0,60):
            if wardMatrix.at[i,'Available'] == 1:
                totalPlots = totalPlots + 1
                nShiros = nShiros + 1
                PT, ampm = await formatPT(wardMatrix.at[i,'Listing Time'])
                shString = shString + " [" + wardMatrix.at[i,'Size'] + "] " + str(ward).zfill(2) + "-" + str(i+1).zfill(2) + " <" + str(PT) + ampm + ">,"
    if nShiros > 0:
        shString = shString[:-1] + "."
    if nShiros == 0:
        shString = "No plots available."
    shString = "[" + str(nShiros) + "] " + '\U000026E9' + "Shirogane: " + shString + '\n'
    
    
    
    header = "__Sweep Report: " + str(totalPlots) + " plot(s) available. <all prime times are EST>" + "__" + '\n'
    
    print('Sending report...')
    await context.send(header + gString + lbString + mString + shString)
    return
    
async def addWishlist(context):
    # This function adds a user to the wishlist field in the plot database
    # Figure out what DC and Server we're in:
    # Imagine the input to be ##wish Mist w10 p15. in #Zalera-Plots
    fileLoc, district, callout, wNum, pNum  = await getDatabase(context)
    
    # Make sure this returned a value:
    if "NULL" in fileLoc:
        print("database not found...")
        return
        
    # Read the database spreadsheet:
    wardMatrix = pandas.read_excel(fileLoc, engine='openpyxl')
    wardMatrix = await pandasSantize(wardMatrix)
    
    # Get author's id so we can ping them later:
    author = context.author.id
    
    # Grab the current wishlist and search it for the author:
    wishes = wardMatrix.at[pNum-1,'Wish List']
    
    # If they're already on the wishlist tell them they're in trouble.
    breakout = 0
    if str(author) in wishes:
        breakout = 1;
    if breakout == 1:
        await context.send("You have already wishlisted this plot.")
        await context.message.add_reaction('\U0000274C')
        return
    
    # Else, add them with a delimiter of "**"
    wishes = wishes + "**" + str(author);
    
    # Add that long string to the database
    wardMatrix.at[pNum-1,'Wish List'] = wishes
    
    # Save edited database:
    wardMatrix.to_excel(fileLoc, "Sheet1", index = False, header = True, engine='xlsxwriter')
    
    await context.message.add_reaction('\U0001F320')
    return
    
async def removeWishlist(context):
    # This function adds a user to the wishlist field in the plot database
    # Figure out what DC and Server we're in:
    # Imagine the input to be ##wish Mist w10 p15. in #Zalera-Plots
    fileLoc, district, callout, wNum, pNum  = await getDatabase(context)
    
    # Make sure this returned a value:
    if "NULL" in fileLoc:
        print("database not found...")
        return
        
    # Read the database spreadsheet:
    wardMatrix = pandas.read_excel(fileLoc, engine='openpyxl')
    wardMatrix = await pandasSantize(wardMatrix)
    
    # Get author's id so we can if they're on the list:
    author = context.author.id
    
    # If they're not on the wishlist tell them they're in trouble.
    wishes = wardMatrix.at[pNum-1,"Wish List"]
    breakout = 0
    if not str(author) in wishes:
        breakout = 1;
    if breakout == 1:
        await context.send("You have not wished for this plot.")
        await context.message.add_reaction('\U0000274C')
        return
    # Otherwise, remove them:
    wishes = wishes.replace("**" + str(author),'')
    
    # Edit the existing wishlist.
    wardMatrix.at[pNum-1,"Wish List"] = wishes

    # Save edited database:
    wardMatrix.to_excel(fileLoc, "Sheet1", index = False, header = True, engine='xlsxwriter')
    
    await context.message.add_reaction('\U0001F44D')
    return

# Utility functions: 
async def getDatabase(context):
    # This function finds the appropriate database file path:
    fileLoc = "NULL"

    # Get channel name:
    text = context.channel.name
    text = text.lower()
    print(text)
    
    dc = "none"
    server = "none"
    
    # Start a dictionary search. DC_DICT has each DC as a function of the server name.
    breakout = 1
    for key in DC_DICT:
        if key in text:
            server = key
            dc = DC_DICT[key]['datacenter']
            text.replace(key, '')
            breakout = 0
    
    # Prevent reporting if the message didn't come from a plot reporting channel:
    if breakout == 1:
        print("Exited assignment due to inapporopriate reporting location.")
        return fileLoc

    # Now get the , housing district, ward and plot
    # Get channel message:
    text = context.message.content 
    text = text.lower()
    
    # Determine district
    district = "none"
    callout = "none"
    if "lb" in text:
        district = "Lavender Beds"
        callout = "LavenderBeds"
    if "lav" in text:
        district = "Lavender Beds"
        callout = "LavenderBeds"
    if "gob" in text:
        district = "Goblet"
        callout = "Goblet"
    if "shir" in text:
        district = "Shirogane"  
        callout = "Shirogane"
    if "mi" in text:
        district = "Mist"    
        callout = "Mist"        
    
    # Slice off the command leading string
    pSplit = text.split(" ",1)
    text = pSplit[1]

    # Predefs:
    wNum = 0
    pNum = 0
    
    # this input ALWAYS needs to be in 'ward x plot x' order.
    if 'w' in text:
        wSplit = text
        wSplit = re.sub('\D', ' ', wSplit)
        w = [int(s) for s in wSplit.split() if str(s).isdigit()]
        wNum = w[0]
        pNum = w[1]
    
    # Exception for ward and plot numbers that don't exist:
    if wNum > 24 or wNum < 1:
        print("Exited assignment due to inapporopriate ward number.")
        return fileLoc
        
    if pNum > 60 or pNum < 1:
        print("Exited assignment due to inapporopriate ward number.")
        return fileLoc
        
    # Get the file path:
    fileLoc = r"Datacenters/" + dc.capitalize() + "/" + server.capitalize() + "/" + callout + "/" + str(wNum).zfill(2) + ".xlsx"
    # Return all this stuff to the calling function:
    return fileLoc, district, callout, wNum, pNum

    
async def getLogfile(context):
    # This function finds the appropriate database file path:
    fileLoc = "NULL"

    # Get channel name:
    text = context.channel.name
    text = text.lower()

    dc = "none"
    server = "none"
    
    # Start a dictionary search. DC_DICT has each DC as a function of the server name.
    breakout = 1
    for key in DC_DICT:
        if key in text:
            server = key
            dc = DC_DICT[key]['datacenter']
            text.replace(key, '')
            breakout = 0
    
    # Prevent reporting if the message didn't come from a plot reporting channel:
    if breakout == 1:
        print("Exited assignment due to inapporopriate reporting location.")
        return fileLoc
        
    # Get the file path:
    fileLoc = r"Datacenters/" + dc.capitalize() + "/" + server.capitalize() + "/logfile.txt"
    # Return location
    return fileLoc
    
async def formatPT(inStr):
    # This returns pt time and am/pm indicator
    sp = inStr.split("/")
    # Prime time is presumed to be the report time + 10 hours.
    hour = int(sp[2]) + 10
    ptTime = hour
    
    # figure out if this is am or pm, then covert to the twelve hour base for listing.
    ampm = 'am'
    if ptTime > 23:
        ptTime = ptTime - 24
    if ptTime > 11:
        ampm = 'pm'
    if ptTime > 12:
        ptTime = ptTime - 12
    return ptTime, ampm

async def checkWish(context,wardMatrix,pNum):
    # Load the wishlist:
    wishes = wardMatrix.at[pNum-1,"Wish List"]
    # Get all the wishers:
    toCalls = wishes.split("**")
    # call them up:
    for i in toCalls:
        if i.isnumeric():
            # I know that this is going to fail at some point, so...
            try:
                m = await bot.fetch_user(int(i))
                await context.send("This plot is on your wishlist, " + m.mention + ".")
            except:
                print("Ran into a wishlist error.")

    return
    
 
async def pandasSantize(wm):
    # This is to make sure that pandas doesn't run into any errors because of old or bad spreadsheets.
    if 'Plot' not in wm:
        wm.insert(0, "Plot", 0) 
        for i in range(0,61):
            wm.at[i,"Plot"] = i + 1
    if 'Available' not in wm:
        wm.insert(3, 'Available', 0) 
        for i in range(0,61):
            wm.at[i,'Available'] = 0  
    if 'Listing Time' not in wm:
        wm.insert(4, 'Listing Time', 'nan')   
    if 'Last Sweep' not in wm:
        wm.insert(5, 'Last Sweep', 'nan')   
    if 'ListingID' not in wm:
        wm.insert(6, 'ListingID', 'nan')     
    if 'Wish List' not in wm:
        wm.insert(7, 'Wish List', 'nan')   
    wm = wm.astype({'Listing Time': str})
    wm = wm.astype({'Last Sweep': str})
    wm = wm.astype({'Wish List': str})
    wm = wm.astype({'ListingID': str})
    return wm

async def getReportingChannels(context):
    # Get the channels in the 'guild' or server:
    listOfChannels = context.guild.channels
    # Go through them one by one:
    for c in listOfChannels:
        # See if they're sweep channels:
        if 'sweep' in c.name:
            # See which key is in their name:
            for key in DC_DICT:
                if key in c.name:
                    # Write down the channel id in the server's dictionary:
                    DC_DICT[key]["reporting channel"] = str(c.id)
    
    # Rewrite the dictionary:
    with open("datacenter_dictionary.txt", "w") as outfile:  
        json.dump(DC_DICT, outfile) 

# Overarching timer function:
@loop(seconds=60)
async def timerFunction():
    now = datetime.now()
    if now.minute == 55: 
        await checkPrimeTimes()
    return

# Triggered at the :55 mark every hour, checks for PTs and sends them.
async def checkPrimeTimes():
    print("Checking prime times...")
    tz = pytz.timezone('US/Eastern')
    now = datetime.now(tz)
    print(now)
    
    for key in DC_DICT:
        reportingStr = ""
        c = DC_DICT[key]['reporting channel']
        if float(c) <= 0:
            continue
        channel = await bot.fetch_channel(c)
        dc = DC_DICT[key]['datacenter']
        server = key
        print(channel)
        for division in ["Goblet", "LavenderBeds", "Mist", "Shirogane"]:
            for wNum in range(1,25):
                fileLoc = r"Datacenters/" + dc.capitalize() + "/" + server.capitalize() + "/" + division + "/" + str(wNum).zfill(2) + ".xlsx"
                wardMatrix = pandas.read_excel(fileLoc, engine='openpyxl')
                for i in range(0,60):
                    if wardMatrix.at[i,'Available'] == 1:
                        sp = wardMatrix.at[i,'Listing Time']
                        # print(division + " " + str(wNum) + " " + str(i))
                        # print(sp)
                        sp = sp.split("/")
                        # Prime time is presumed to be the report time + 10 hours.
                        PT = int(sp[2])
                        if (PT-1) == now.hour:
                            reportingStr = reportingStr + division + ", [" + wardMatrix.at[i,'Size'] + "] Ward " + str(wNum) + " Plot " + str(i+1) + " "
                            # Load the wishlist:
                            
                            wishes = wardMatrix.at[i,"Wish List"]
                            print(wishes)
                            if len(str(wishes))>3:
                                # Get all the wishers:
                                toCalls = wishes.split("**")
                                # call them up:
                                for j in toCalls:
                                    if j.isnumeric():
                                        # I know that this is going to fail at some point, so...
                                        try:
                                            m = await bot.fetch_user(int(j))
                                            reportingStr = reportingStr + ">> " + m.mention + " "
                                        except:
                                            print("Ran into a wishlist error.")
                            reportingStr = reportingStr + '\n'
                            
        if len(reportingStr) > 0:
            reportingStr = "__The following plots will be in prime time in the upcoming hour:__" + '\n' + reportingStr
            await channel.send(reportingStr)
        
    return
  
# start schedule function
timerFunction.start()
  
bot.run(TOKEN)

## TO DO:
"""
> Timer function for hourly PT updates.

> fix PT listings range. You know that report time doesn't always mean PT time -10...

> Manual changing of variables in the spreadsheet, e.g. set the PT to a different value.
> PT ranges?
    > A value in the spreadsheets that reflects the last sweep of the district.

> Auto-assembly for the data structure...
"""