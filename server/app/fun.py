"""Things for the Info tab that have nothing to do with the house: a quote of the day, a fun fact that
changes every few hours, countdowns to nice days, the year so far and how long the day is.
Everything is offline (no extra web services). Add quotes/facts freely: they rotate by date.
"""
import math
from datetime import date, timedelta

QUOTES = [
    ("Not all those who wander are lost.", "J.R.R. Tolkien"),
    ("A journey of a thousand miles begins with a single step.", "Lao Tzu"),
    ("Imagination is more important than knowledge.", "Albert Einstein"),
    ("Life is like riding a bicycle. To keep your balance you must keep moving.", "Albert Einstein"),
    ("Happiness can be found even in the darkest of times, if one only remembers to turn on the light.",
     "Albus Dumbledore"),
    ("It does not do to dwell on dreams and forget to live.", "Albus Dumbledore"),
    ("Do or do not. There is no try.", "Yoda"),
    ("May the Force be with you.", "Star Wars"),
    ("Live long and prosper.", "Spock"),
    ("To infinity and beyond!", "Buzz Lightyear"),
    ("Just keep swimming.", "Dory"),
    ("Adventure is out there!", "Up"),
    ("Ohana means family. Family means nobody gets left behind.", "Lilo & Stitch"),
    ("Some people are worth melting for.", "Olaf"),
    ("Even miracles take a little time.", "The Fairy Godmother"),
    ("The flower that blooms in adversity is the most rare and beautiful of all.", "Mulan"),
    ("You're braver than you believe, stronger than you seem, and smarter than you think.", "Christopher Robin"),
    ("We're all mad here.", "The Cheshire Cat"),
    ("Curiouser and curiouser!", "Alice in Wonderland"),
    ("It's no use going back to yesterday, because I was a different person then.", "Alice in Wonderland"),
    ("Second star to the right, and straight on till morning.", "Peter Pan"),
    ("There's no place like home.", "The Wizard of Oz"),
    ("Today you are You, that is truer than true. There is no one alive who is Youer than You.", "Dr. Seuss"),
    ("Oh, the places you'll go!", "Dr. Seuss"),
    ("One cannot think well, love well, sleep well, if one has not dined well.", "Virginia Woolf"),
    ("I am not afraid of storms, for I am learning how to sail my ship.", "Louisa May Alcott"),
    ("Life is what happens when you're busy making other plans.", "John Lennon"),
    ("All you need is love.", "The Beatles"),
    ("Here comes the sun, and I say it's all right.", "The Beatles"),
    ("Don't worry about a thing, 'cause every little thing gonna be all right.", "Bob Marley"),
    ("Stay hungry, stay foolish.", "Steve Jobs"),
    ("The only way to do great work is to love what you do.", "Steve Jobs"),
    ("Well done is better than well said.", "Benjamin Franklin"),
    ("Carpe diem: seize the day.", "Horace"),
    ("I think, therefore I am.", "René Descartes"),
    ("So it goes.", "Kurt Vonnegut"),
    ("Fall seven times, stand up eight.", "Japanese proverb"),
    ("Little by little, one travels far.", "Spanish proverb"),
    ("The best time to plant a tree was 20 years ago. The second best time is now.", "Proverb"),
    ("Hakuna matata: it means no worries.", "The Lion King"),
]

FACTS = [
    "Octopuses have three hearts and blue blood.",
    "Sea otters hold hands while they sleep so they don't drift apart.",
    "A group of flamingos is called a flamboyance.",
    "Bananas are berries, but strawberries are not.",
    "Honey never spoils: pots of it were found in ancient Egyptian tombs.",
    "Wombats make cube-shaped poop.",
    "A day on Venus lasts longer than a whole year on Venus.",
    "Butterflies taste with their feet.",
    "Cats sleep around 12 to 16 hours a day.",
    "A cat's purr vibrates at about 25 to 150 times per second.",
    "Cats can't taste sweet things.",
    "Koalas sleep up to 20 hours a day.",
    "There are more trees on Earth than stars in the Milky Way.",
    "Sloths can hold their breath for up to 40 minutes.",
    "Scotland's national animal is the unicorn.",
    "The Eiffel Tower is about 15 cm taller in summer: the iron expands in the heat.",
    "A blue whale's heart weighs about 180 kg.",
    "Some penguins give pebbles to the penguin they love.",
    "Snails can have thousands of teeth.",
    "Hummingbirds are the only birds that can fly backwards.",
    "An ostrich's eye is bigger than its brain.",
    "Elephants can recognise themselves in a mirror.",
    "Starfish have no brain and no blood.",
    "Pineapples take about two years to grow.",
    "Peanuts aren't nuts: they're legumes, like peas and beans.",
    "A bolt of lightning is about five times hotter than the surface of the Sun.",
    "Light from the Sun takes about 8 minutes to reach us.",
    "On Mars, sunsets are blue.",
    "Saturn would float in a bathtub big enough: it is less dense than water.",
    "There are footprints on the Moon that will stay for millions of years: there's no wind.",
    "Jupiter has more than 90 moons.",
    "A teaspoon of a neutron star would weigh billions of tonnes.",
    "Your nose can tell apart a huge number of different smells.",
    "Babies have more bones than adults: some fuse together as they grow.",
    "The Great Wall of China is not visible from the Moon with the naked eye.",
    "The Atomium in Brussels was built for the 1958 World's Fair.",
    "Cacao beans, the stuff of chocolate, were once used as money by the Aztecs.",
    "Carrots used to be mostly purple before orange ones became popular.",
    "Apples float because a quarter of their volume is air.",
    "Rabbits can't vomit.",
    "Dolphins give each other names: they use signature whistles.",
    "A shrimp's heart is in its head.",
    "Polar bears have black skin under their white fur.",
    "Owls can't move their eyes, so they turn their heads instead.",
    "Rain has a smell: it's called petrichor.",
    "A cloud can weigh more than a million kilograms.",
    "Snowflakes almost always have six sides.",
    "Bamboo can grow almost a metre in a single day.",
    "The longest recorded flight of a chicken is 13 seconds.",
    "Sea otters have a pocket of skin under each arm, handy for their favourite stone.",
    "Red pandas use their fluffy tails as blankets.",
    "Crows remember faces, and can hold a grudge.",
    "A day on Earth was only about 22 hours long 600 million years ago.",
]

# name, MM-DD, icon. Easter is added by date (it moves).
HOLIDAYS = [("Christmas", "12-25", "pine-tree"), ("New Year", "01-01", "party-popper"),
            ("Valentine's Day", "02-14", "heart"), ("Halloween", "10-31", "ghost"),
            ("Start of summer", "06-21", "white-balance-sunny"), ("Start of spring", "03-20", "flower-tulip"),
            ("Start of autumn", "09-22", "leaf"), ("Start of winter", "12-21", "snowflake")]


def quote_of(day):
    return QUOTES[(day.toordinal() * 7) % len(QUOTES)]


def fact_of(now):
    """A new fact every 4 hours."""
    return FACTS[(now.date().toordinal() * 6 + now.hour // 4) % len(FACTS)]


def easter(year):
    a, b, c = year % 19, year // 100, year % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    return date(year, month, (h + l - 7 * m + 114) % 31 + 1)


def next_date(mmdd, today):
    month, day = int(mmdd[:2]), int(mmdd[3:])
    for year in (today.year, today.year + 1):
        try:
            d = date(year, month, day)
        except ValueError:   # 29 February
            d = date(year, 3, 1)
        if d >= today:
            return d
    return today


def countdowns(today, mine, n=3):
    """Next n nice days: the user's own (birthdays, ...) and the holidays. [{name, icon, days, date}]"""
    items = [(c["name"], next_date(c["date"], today), "cake-variant") for c in mine]
    items += [(name, next_date(d, today), ic) for name, d, ic in HOLIDAYS]
    e = easter(today.year)
    items.append(("Easter", e if e >= today else easter(today.year + 1), "egg-easter"))
    items.sort(key=lambda x: (x[1], x[2] != "cake-variant"))
    return [{"name": name, "icon": ic, "days": (d - today).days, "date": d.strftime("%-d %b")}
            for name, d, ic in items[:n]]


def day_length(day, lat):
    """Hours of daylight (sunrise to sunset) on a date at a latitude. Accurate to a couple of minutes."""
    n = day.timetuple().tm_yday
    decl = math.asin(math.sin(math.radians(-23.44)) *
                     math.cos(math.radians(360 / 365.24 * (n + 10) + 360 / math.pi * 0.0167 *
                                           math.sin(math.radians(360 / 365.24 * (n - 2))))))
    phi = math.radians(lat)
    x = (math.sin(math.radians(-0.833)) - math.sin(phi) * math.sin(decl)) / (math.cos(phi) * math.cos(decl))
    if x <= -1:
        return 24.0
    if x >= 1:
        return 0.0
    return 24 / math.pi * math.acos(x)


def daylight(today, lat):
    """{"length": "9h 12m", "delta": "3 min less than yesterday"} (None without a latitude)."""
    if lat is None:
        return None
    now, before = day_length(today, lat), day_length(today - timedelta(days=1), lat)
    mins = round(now * 60)
    diff = round((now - before) * 60)
    if diff > 0:
        delta = f"{diff} min more than yesterday"
    elif diff < 0:
        delta = f"{-diff} min less than yesterday"
    else:
        delta = "same as yesterday"
    return {"length": f"{mins // 60}h {mins % 60:02d}m", "delta": delta, "hours": now}


def year_progress(today):
    start = date(today.year, 1, 1)
    total = (date(today.year + 1, 1, 1) - start).days
    n = (today - start).days + 1
    return {"day": n, "of": total, "pct": round(100 * n / total), "week": today.isocalendar()[1],
            "left": total - n}


def season(today):
    md = today.strftime("%m-%d")
    if "03-20" <= md < "06-21":
        return "Spring", "flower-tulip"
    if "06-21" <= md < "09-22":
        return "Summer", "white-balance-sunny"
    if "09-22" <= md < "12-21":
        return "Autumn", "leaf"
    return "Winter", "snowflake"
