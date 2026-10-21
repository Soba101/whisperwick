"""Everyday life for generated villagers (week 17, #118): habits, worries and secrets.

These are plain memories, like the grudge and the wish. Nothing tells a villager what
to do with them. They exist so quiet hours have ordinary life in them and so innocents
also have something to hide.

Rules for every line here:
- Only real place names of the village (The Inn, Market, Temple, Town Hall).
- Routines stay in daytime hours (before 21:00), away from every possible murder hour.
- Worries and secrets name no person, no place and no hour, and avoid every word of
  the motive pool, so they never touch any crime. check.py enforces this on each draw.
- Secrets are words only: no item exists for them.
"""

# First person, like the other starting memories. Keyed by scenario occupation.
ROUTINES = {
    "innkeeper": (
        "I usually open The Inn at 07:00 and serve supper there until 20:00.",
        "I usually buy bread at the Market at 08:00 and spend the rest of the day at The Inn.",
        "I usually sweep The Inn at 07:00 and sit by its fire after 19:00.",
        "I usually fetch vegetables from the Market at 09:00 and cook at The Inn from noon.",
        "I usually light a candle at the Temple at 07:00 before opening The Inn.",
        "I usually stay at The Inn all day and walk to the Market at 16:00 for supplies.",
        "I usually count the day's coins at The Inn at 20:00.",
        "I usually air the rooms of The Inn at 10:00 and pour ale from 17:00.",
        "I usually visit the Market at 14:00 to haggle over prices for The Inn.",
        "I usually eat a late breakfast at The Inn at 10:00 after the morning rush.",
    ),
    "blacksmith": (
        "I usually light the forge at the Market at 07:00 and eat at The Inn at 19:00.",
        "I usually work at the Market from 08:00 and rest at The Inn after 18:00.",
        "I usually mend tools at the Market until noon and eat lunch at The Inn.",
        "I usually stoke the forge at the Market at 06:00 before anyone else is up.",
        "I usually stop work at the Market at 17:00 and wash at The Inn.",
        "I usually spend mornings at the Market and visit the Temple at 18:00.",
        "I usually shoe horses at the Market at 09:00 and sharpen blades after 14:00.",
        "I usually take my noon meal at The Inn at 12:00 and return to the Market.",
        "I usually work at the Market all day and walk past the Town Hall at 19:00.",
        "I usually sit at The Inn from 19:00 with a mug of ale.",
    ),
    "priest": (
        "I usually ring the Temple bell at 07:00 and hold prayers at 18:00.",
        "I usually sweep the Temple at 08:00 and walk to the Market at 11:00.",
        "I usually stay at the Temple all morning and eat at The Inn at 13:00.",
        "I usually visit the sick in the morning and return to the Temple at 15:00.",
        "I usually read at the Temple from 09:00 until noon.",
        "I usually tend the Temple candles at 07:00 and again at 20:00.",
        "I usually buy oil at the Market at 10:00 for the Temple lamps.",
        "I usually sit quietly in the Temple from 16:00 until supper.",
        "I usually call at the Town Hall at 10:00 about Temple repairs.",
        "I usually eat supper at The Inn at 19:00 and walk back to the Temple.",
    ),
    "merchant": (
        "I usually set out my stall at the Market at 07:00 and close it at 18:00.",
        "I usually count stock at the Market at 08:00 and eat at The Inn at 19:00.",
        "I usually trade at the Market all day and pay my dues at the Town Hall at 16:00.",
        "I usually meet travellers at The Inn at 12:00 to talk prices.",
        "I usually open my stall at the Market at 08:00 and pack up at 17:00.",
        "I usually write my ledgers at The Inn at 20:00.",
        "I usually unload carts at the Market at 06:00 before the crowds.",
        "I usually spend mornings at the Market and afternoons at The Inn.",
        "I usually visit the Temple at 18:00 after closing my stall.",
        "I usually take tea at The Inn at 15:00 and return to the Market.",
    ),
    "guard": (
        "I usually start my watch at the Town Hall at 08:00 and walk to the Market at 12:00.",
        "I usually patrol from the Town Hall to the Market at 09:00 and 15:00.",
        "I usually keep the Town Hall door from 08:00 and eat at The Inn at 19:00.",
        "I usually check the Market stalls at 10:00 and return to the Town Hall.",
        "I usually walk past the Temple at 14:00 on my rounds.",
        "I usually write the watch book at the Town Hall at 18:00.",
        "I usually stand at the Town Hall all morning and walk the Market after noon.",
        "I usually eat my noon meal at The Inn at 12:00 and return to the Town Hall.",
        "I usually lock the Town Hall at 20:00 after the day's business.",
        "I usually drill alone behind the Town Hall at 07:00.",
    ),
    "mayor": (
        "I usually open the Town Hall at 08:00 and hear complaints until noon.",
        "I usually walk to the Market at 11:00 to greet the traders.",
        "I usually work at the Town Hall all day and dine at The Inn at 19:00.",
        "I usually sign papers at the Town Hall from 09:00.",
        "I usually visit the Temple at 17:00 before supper.",
        "I usually take lunch at The Inn at 13:00 and return to the Town Hall.",
        "I usually meet the traders at the Market at 10:00 about stall fees.",
        "I usually read letters at the Town Hall at 08:00.",
        "I usually stay at the Town Hall until 18:00 and walk home past the Market.",
        "I usually call at The Inn at 20:00 to hear the village news.",
    ),
}

# On their mind, but not the murder.
WORRIES = (
    "My mother has been coughing for weeks and I cannot pay a healer.",
    "My roof leaks and the autumn rains are near.",
    "My eyes are failing and I hide it from everyone.",
    "My apple trees bore little fruit this year.",
    "I have not slept well since the spring.",
    "My brother has not written in three months.",
    "My knees ache more each winter, and my work grows harder.",
    "I fear I am growing forgetful.",
    "I am behind on my rent and the owner is losing patience.",
    "My old dog has stopped eating.",
    "I fear the harvest is poor and bread prices are rising.",
    "My daughter wants to move to the city and I cannot stop her.",
)

# Something an innocent might also lie to hide. Words only, never an item.
SECRETS = (
    "I cannot read, and I have hidden it all my life.",
    "I once spent a night in a city jail under another name.",
    "I was married before, far from here, and no one in the village knows.",
    "I sometimes drink alone until I cannot stand.",
    "I lied when asked where I was born.",
    "I cheat a little at cards with travellers.",
    "I write poems and hide them under my bed.",
    "I have a child in another town whom I have never met.",
    "I faked an illness last winter to avoid a hard job.",
    "I once fell asleep on watch duty and let someone else take the blame.",
    "I am afraid of the dark and keep a lamp lit all night.",
    "I failed my apprentice exam twice and tell everyone I passed.",
)
