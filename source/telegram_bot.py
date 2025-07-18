import logging
import os
from functools import reduce
from typing import Dict
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler
from kleinanzeigenbot import KleinanzeigenBot
from chat_client import ChatClient
from persistence import (
    init_db,
    add_bot as db_add_bot,
    remove_bot as db_remove_bot,
    clear_bots as db_clear_bots,
    load_bots as db_load_bots,
    add_filter as db_add_filter,
    clear_filters as db_clear_filters,
    load_filters as db_load_filters,
)

registered_bots_dict: Dict[int, ChatClient] = {}
# filters = []
# fetch_job_started = False

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

# set higher logging level for httpx to avoid all GET and POST requests being logged
logging.getLogger("httpx").setLevel(logging.WARNING)


async def register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Register the current chat with the bot.

    :param update: the current update
    :param context: the current context
    """

    chat = update.effective_chat

    if chat is None:
        print("could not get id for effective_chat!")
        return

    chat_id = chat.id

    if chat_id in registered_bots_dict.keys():
        await bot_respond(update, context, "This chat is already registered.")
        return

    # add the chat id to the registered ids.
    registered_bots_dict[chat_id] = ChatClient(chat_id)
    await bot_respond(update, context, "successfully registered this chat")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    start the program

    :param update: [TODO:description]
    :param context: [TODO:description]
    """

    message = """Welcome. Available commands are:

    /start -- Show this message
    /start_bots  -- start fetching with registered bots
    /stop -- stop fetching
    /add_bot <name> <link> -- add a bot that scans the specified link
    /remove_bot <name> -- stop and remove a bot
    /clear_bots -- stop and clear all registered bots
    /status -- get status information
    /add_filter -- add a filter to filter out unwanted messages
    /show_filters -- show active filters
    /clear_filters -- clear all filters"""
    await bot_respond(update, context, message)


async def get_chat_client(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> ChatClient | None:
    """
    Check if the current chat id already has a registered chatClient.

    :param update: the current update
    :param context: the current context
    :return: the current chat_id or -1
    """
    if update.effective_chat is None:
        print("could not get id for effective_chat!")
        return None
    chat_id = update.effective_chat.id

    if chat_id not in registered_bots_dict.keys():
        await register(update, context)

    return registered_bots_dict[chat_id]


async def start_bots(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Start the Fetch job for the current chat id.

    :param update: the current update.
    :param context: the current context.
    """
    chatClient = await get_chat_client(update, context)
    if chatClient is None:
        return

    await chatClient.start_fetch_job(context)

    await bot_respond(update, context, "Fetch job started")


async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Stop the Fetch job for the current chat id, if it is running.

    :param update: the current update.
    :param context: the current context
    """
    chatClient = await get_chat_client(update, context)
    if chatClient is None:
        return

    if not chatClient.fetch_job_running():
        await bot_respond(
            update,
            context,
            "Fetch job is not running yet. Start Fetch job with /start_bots",
        )

    chatClient.stop_fetch_job()

    await bot_respond(update, context, "Fetch job stopped")


async def bot_respond(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    """
    Send a message based on the current context to the sender given in Update.

    :param update: the current update
    :param context: the current context
    :param text: the message to be sent
    """
    chat = update.effective_chat

    if chat is None:
        print("could not get id for effective_chat!")
        return

    await context.bot.send_message(
        chat_id=chat.id,
        text=text,
    )


async def add_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Add a link to be checked for new items

    :param update: the current update
    :param context: the current context
    """
    chatClient = await get_chat_client(update, context)
    if chatClient is None:
        return

    # add a new bot to the registered bots
    args = context.args

    if args is None:
        return

    # sanitize input
    if len(args) != 2:
        await bot_respond(
            update,
            context,
            "add_bot command requires two arguments. usage:\n/add_bot <name> <link>",
        )
        return

    bot = KleinanzeigenBot(args[1], args[0])

    if bot.invalid_link_flag:
        await bot_respond(update, context, "something went wrong, link is not valid!")
        return

    chatClient.add_bot(bot)
    db_add_bot(bot.name, bot.url)

    await bot_respond(
        update,
        context,
        f"added new bot: {bot.name}, with {bot.num_items()} items registered.",
    )


async def add_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chatClient = await get_chat_client(update, context)
    if chatClient is None:
        return

    args = context.args

    if args is None:
        return

    for filter in args:
        chatClient.add_filter(filter)
        db_add_filter(filter)

    filterList = reduce(lambda a, b: a + "\n- " + b, chatClient.filters, "\n- ")
    await bot_respond(update, context, f"added new filter(s): {filterList}")


async def show_filters(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chatClient = await get_chat_client(update, context)
    if chatClient is None:
        return

    if len(chatClient.filters) <= 0:
        await bot_respond(update, context, "no active filters")
        return

    filterList = reduce(lambda a, b: a + "\n- " + b, chatClient.filters, "\n- ")
    await bot_respond(update, context, f"current filter(s): {filterList}")


async def clear_filters(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Clear all current filters.

    :param update: the current update
    :param context: the current context
    """
    chatClient = await get_chat_client(update, context)
    if chatClient is None:
        return

    chatClient.filters.clear()
    db_clear_filters()

    await bot_respond(update, context, "cleared all filters")


async def clear_bots(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Clears the list of Bots.

    :param update: the current update
    :param context: the current context
    """
    chatClient = await get_chat_client(update, context)
    if chatClient is None:
        return

    # stop running fetch jobs.
    chatClient.stop_fetch_job()

    info = "Cleared registered bots. removed bots:"

    for bot in chatClient.registered_bots:
        info += f"\n- {bot.name} -- {bot.url}"
    chatClient.registered_bots.clear()
    db_clear_bots()

    await bot_respond(update, context, info)


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chatClient = await get_chat_client(update, context)
    if chatClient is None:
        return

    info = "status: " + (
        '<b style="color:#00FF00">running</b>'
        if chatClient.fetch_job_running()
        else '<b style="color:#FF0000">idle</b>'
    )
    info += "\nregistered links:"
    for bot in chatClient.registered_bots:
        info += f"\n{bot.name}: {bot.num_items()} items registered | {bot.url}"

    await context.bot.send_message(chat_id=chatClient.id, text=info, parse_mode="HTML")


async def remove_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args

    if args is None:
        return

    if len(args) != 1:
        await bot_respond(
            update,
            context,
            text="wrong number of arguments. usage:\n/remove_bot <name>",
        )
        return

    chatClient = await get_chat_client(update, context)
    if chatClient is None:
        return

    if not chatClient.remove_bot(args[0]):
        await bot_respond(
            update,
            context,
            "could not remove bot from active list. are you sure it exists?",
        )
        return

    db_remove_bot(args[0])

    message = f"successfully removed {args[0]}."

    if len(chatClient.registered_bots) <= 0:
        message += "\nStopping fetch job, because there are no more active bots."
        chatClient.stop_fetch_job()

    await bot_respond(update, context, message)


if __name__ == "__main__":
    # Initialize DB and load state
    init_db()

    # Get the Telegram API Token from token.txt
    try:
        with open("token.txt") as f:
            lines = f.readlines()
            token = lines[0].replace("\n", "")
    except Exception as e:
        print(
            f"something went wrong while trying to read 'token.txt', please make sure that the file is in located in the working directory: {os.getcwd()}\n {e}"
        )
        raise SystemExit

    logging.info("token read, starting application")

    application = ApplicationBuilder().token(token).build()
    job_queue = application.job_queue

    start_handler = CommandHandler("start", start)
    start_bots_handler = CommandHandler("start_bots", start_bots)
    stop_handler = CommandHandler("stop", stop)
    add_bot_handler = CommandHandler("add_bot", add_bot)
    clear_bots_handler = CommandHandler("clear_bots", clear_bots)
    status_handler = CommandHandler("status", status)
    remove_bot_handler = CommandHandler("remove_bot", remove_bot)
    add_filter_handler = CommandHandler("add_filter", add_filter)
    show_filters_handler = CommandHandler("show_filters", show_filters)
    clear_filter_handler = CommandHandler("clear_filters", clear_filters)

    logging.info("Adding handlers")

    application.add_handler(start_handler)
    application.add_handler(start_bots_handler)
    application.add_handler(stop_handler)
    application.add_handler(add_bot_handler)
    application.add_handler(clear_bots_handler)
    application.add_handler(status_handler)
    application.add_handler(remove_bot_handler)
    application.add_handler(add_filter_handler)
    application.add_handler(show_filters_handler)
    application.add_handler(clear_filter_handler)

    # Load bots from DB and add to the first registered ChatClient (if any)
    bots = db_load_bots()
    filters = db_load_filters()
    if bots or filters:
        # If there is at least one chat registered, populate it
        if registered_bots_dict:
            chatClient = next(iter(registered_bots_dict.values()))
            for name, url in bots:
                chatClient.add_bot(KleinanzeigenBot(url, name))
            chatClient.filters = filters

    # drop_pending_updates discards all updates before startup
    application.run_polling(drop_pending_updates=True)

    logging.info("Application started")
