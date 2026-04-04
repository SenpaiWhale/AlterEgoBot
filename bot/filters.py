"""NSFW content detection using profanity library and custom blocklist."""

import re

from better_profanity import profanity

profanity.load_censor_words()

NSFW_BLOCKLIST = {
    "pornhub", "xvideos", "xhamster", "xnxx", "redtube", "youporn", "tube8",
    "spankbang", "porntrex", "beeg", "tnaflix", "drtuber", "slutload",
    "motherless", "hentaihaven", "nhentai", "rule34", "gelbooru", "danbooru",
    "onlyfans", "fansly", "manyvids", "clips4sale", "chaturbate", "cam4",
    "bongacams", "stripchat", "myfreecams", "livejasmin", "camsoda",
    "porn", "porno", "pornography", "hentai", "xxx", "nsfw", "nude", "nudes",
    "naked", "nudity", "explicit", "adult content", "18+",
    "sex tape", "sextape", "sex video", "sexvideo", "lewd", "r34",
    "rule 34", "rule34", "cum", "cumshot", "creampie", "gangbang",
    "blowjob", "handjob", "rimjob", "footjob", "titjob", "anal",
    "vagina", "penis", "dick pic", "dickpic", "cock", "pussy", "boobs",
    "tits", "butthole", "anus", "dildo", "vibrator", "masturbat",
    "orgasm", "erotic", "erotica", "fetish", "bdsm", "kink", "kinky",
    "horny", "aroused", "seductive", "stripclub", "strip club",
    "escort", "prostitut", "hooker", "whore", "slut", "thot",
}


def is_nsfw(text: str) -> bool:
    """Return True if *text* contains NSFW language.

    Parameters
    ----------
    text : str
        The string to check.

    Returns
    -------
    bool
        True when profanity or a blocklist term is found.
    """
    if not text:
        return False
    lower = text.lower()
    clean = re.sub(r"[-\d]", " ", lower)
    if profanity.contains_profanity(clean):
        return True
    return any(term in lower for term in NSFW_BLOCKLIST)
