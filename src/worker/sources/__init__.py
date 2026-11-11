"""Clients for the external game catalogues.

Every client returns `schemas.GameCreate` records with genre, platform and tag names
normalized to the names the RAWG snapshot uses, so the same game looks the same
whichever source it came from.
"""
