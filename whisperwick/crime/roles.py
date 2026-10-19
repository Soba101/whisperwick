"""Role connections follow the generated victim and killer, as past facts only."""


def adapt(role, role_id, sc):
    role = role.model_copy(deep=True)
    people = {n.id: n for n in sc.npcs}
    victim = people[sc.secrets["victim"]]
    killer = people[sc.secrets["murderer"]]
    if role_id == "cousin":
        role.player.title = f"{victim.name}'s cousin"
        role.items[0].name = f"letter from {victim.name}"
        role.items[
            0
        ].description = (
            f"A letter addressed to Wren: Dear cousin, come visit when you can. {victim.name}."
        )
        # A living relative remembers a connection, never the secret killing.
        role.memory.npc = "npc_hal"
        role.memory.text = f"Wren (player) is {victim.name}'s ({victim.id}) cousin."
    elif role_id == "partner":
        role.player.title = f"{killer.name}'s former business partner"
        role.items[0].description = f"A page listing goods once traded by Wren and {killer.name}."
        role.memory.npc = killer.id
        role.memory.text = "Wren (player) and I used to trade goods together as business partners."
    return role
