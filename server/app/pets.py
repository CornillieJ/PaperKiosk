"""The pet on Home (config "mascot"): its icon, its faces and the few words that only fit a cat.

The pages are written for the cat: its faces (=^.^=), "purring", "Purrfect". kawaii.shell() swaps those for
the chosen pet's with say(). Faces are plain ASCII: the Kindle's fonts have no kaomoji symbols.

To add a pet: one line in PETS (and its key in config.MASCOTS); the icon is an mdi name.
"""

# key: (name on /config, mdi icon, faces (happy, excited, sleepy, sad), "is purring", "Purrfect", "batting at")
PETS = {
    "cat": ("Cat", "cat", ("(=^.^=)", "(=^o^=)", "(=-.-=)", "(=;.;=)"), "is purring", "Purrfect", "is batting at"),
    "dog": ("Dog", "dog", ("U^w^U", "U^o^U", "U-.-U", "U;.;U"), "is wagging its tail", "Pawfect", "is barking at"),
    "bunny": ("Bunny", "rabbit", ("(^x^)", "(^o^)/", "(-x-)", "(;x;)"), "is nibbling a carrot", "Hoppy days",
              "is hopping at"),
    "bear": ("Teddy bear", "teddy-bear", ("(o^.^o)", "(o^o^o)", "(o-.-o)", "(o;.;o)"), "is humming", "Beary nice",
             "is waving at"),
    "panda": ("Panda", "panda", ("(@^.^@)", "(@^o^@)", "(@-.-@)", "(@;.;@)"), "is munching bamboo", "Perfect",
              "is rolling towards"),
    "penguin": ("Penguin", "penguin", ("<(^.^)>", "<(^o^)>", "<(-.-)>", "<(;.;)>"), "is waddling around", "Perfect",
                "is sliding towards"),
    "owl": ("Owl", "owl", ("{^,^}", "{O,O}", "{-,-}", "{;,;}"), "is hooting softly", "Hoot hoot", "is blinking at"),
    "duck": ("Duck", "duck", ("(^v^)", "(^O^)", "(-v-)", "(;v;)"), "is quacking happily", "Perfect",
             "is quacking at"),
    "unicorn": ("Unicorn", "unicorn-variant", ("(*^.^*)", "(*^o^*)", "(*-.-*)", "(*;.;*)"), "is sparkling",
                "Magical", "is prancing under"),
    "koala": ("Koala", "koala", ("@(^.^)@", "@(^o^)@", "@(-.-)@", "@(;.;)@"), "is hugging a branch", "Perfect",
              "is reaching for"),
    "piggy": ("Piggy", "pig-variant", ("(^oo^)", "(^OO^)", "(-oo-)", "(;oo;)"), "is oinking happily", "Perfect",
              "is sniffing at"),
    "robot": ("Robot", "robot-happy", ("[^_^]", "[^o^]", "[-_-]", "[;_;]"), "is beeping happily", "Optimal",
              "is scanning"),
}
CAT_FACES = PETS["cat"][2]


def get(key):
    p = PETS.get(key) or PETS["cat"]
    return {"key": key if key in PETS else "cat", "name": p[0], "icon": p[1], "faces": p[2], "happy": p[3],
            "perfect": p[4], "batting": p[5]}


def say(pet, html):
    """The cat's faces and words in a page, as the chosen pet's."""
    if pet["key"] == "cat":
        return html
    for cat, mine in zip(CAT_FACES, pet["faces"]):
        html = html.replace(cat, mine.replace("<", "&lt;").replace(">", "&gt;"))
    cat = PETS["cat"]
    return html.replace(cat[3], pet["happy"]).replace(cat[4], pet["perfect"]).replace(cat[5], pet["batting"])
