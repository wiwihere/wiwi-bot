# %%

# %% Updating emoji ids in bulk. The ids can be retrieved by printing the
# emoji like this in discord;   \:emoji_id:

from django.conf import settings

from gw2_logs_archive.gw2_logs.models import Emoji

if __name__ == "__main__":
    from _setup_django import init_django

    init_django(__file__)

# %%

pngs_dir = settings.BASE_DIR.joinpath("img", "raid")


# Copy this into discord
for png in pngs_dir.glob("*.png"):
    png_name = png.stem
    print(rf"\:{png.stem}:")

# %%
# Process discord emoji ids from discord
emote_ids_raw = """paste result from discord here."""
emote_ids = {i.split(":")[1]: i.split(":")[-1].split(">")[0] for i in emote_ids_raw.split("\n")}

for png_name, png_id in emote_ids.items():
    cm = False
    if png_name.endswith("_cm"):
        png_name = png_name[:-3]
        cm = True
    e = Emoji.objects.get(png_name=png_name)

    if png_id:
        if cm:
            e.discord_id_cm = int(png_id)
        else:
            e.discord_id = int(png_id)
        print(f"Update {e.name}. CM:{cm}")

        e.save()
