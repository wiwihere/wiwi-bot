# %%
if __name__ == "__main__":
    from scripts.utilities import django_setup

    django_setup.run()

import logging

import discord
import numpy as np
from scripts.log_helpers import (
    EMBED_COLOUR,
)

logger = logging.getLogger(__name__)


def validate_embed_size(embed: discord.Embed) -> bool:
    """Validate that the embed size is within Discord limits.

    Parameters
    ----------
    embed : discord.Embed
        The embed to validate.

    Returns
    -------
    bool
        True if the embed is valid, False otherwise.
    """
    total_length = len(embed.title or "") + len(embed.description or "")
    for field in embed.fields:
        total_length += len(field.name) + len(field.value)

    if len(embed.description) > 4096:
        logger.warning(
            f"Embed description exceeds Discord limit of 4096 characters: {len(embed.description)} characters"
        )
        return False

    if total_length > 6000:
        logger.warning(f"Embed exceeds Discord limit of 6000 characters: {total_length} characters")
        return False
    return True


def create_discord_embeds(titles: dict[dict, str], descriptions: dict[dict, str]) -> dict[str, discord.Embed]:
    """Create discord embed from titles and descriptions."""
    embeds: dict[str, discord.Embed] = {}
    has_title = False
    for instance_type in titles:
        use_fields = True  # max 1024 per field
        field_characters = np.array([len(i) for i in descriptions[instance_type].values()])
        # Check field length. If more than 1024 it cannot go to a field and should instead
        # go to description
        if np.any(field_characters > 1024):
            logger.info("Cannot use fields because one has more than 1024 chars")
            use_fields = False

            # field characters actually change here because the titles are included in
            # the description.
            field_characters += np.array([len(i) for i in titles[instance_type].values()])

        # If we go over 4096 characters, a new embed should be created.
        # Just find per field which embed they should be in:

        embed_ids = np.floor(np.cumsum(field_characters) / 4096).astype(int)

        # Loop over every unique embed for this instance.
        for embed_id in np.unique(embed_ids):
            title = ""
            description = ""
            # The first embed gets a title and title description.
            if int(embed_id) == 0:
                title = titles[instance_type]["main"]
                description = descriptions[instance_type]["main"]
                if ("raid" in titles) and ("strike" in titles):
                    if not has_title:
                        has_title = True
                    else:
                        title = ""
                        description = ""

            if not use_fields:
                # Loop the encounters
                for embed_id_instance, encounter_key in zip(embed_ids, descriptions[instance_type].keys()):
                    if encounter_key == "main":  # Main is already in title.
                        continue
                    if embed_id_instance != embed_id:  # Should go to different embed.
                        continue

                    description += titles[instance_type][encounter_key]
                    description += descriptions[instance_type][encounter_key] + "\n"

            embeds[f"{instance_type}_{embed_id}"] = discord.Embed(
                title=title,
                description=description,
                colour=EMBED_COLOUR[instance_type],
            )

            if use_fields:
                for embed_id_instance, encounter_key in zip(embed_ids, descriptions[instance_type].keys()):
                    if encounter_key == "main":  # Main is already in title.
                        continue
                    if embed_id_instance != embed_id:  # Should go to different embed.
                        continue
                    field_name = titles[instance_type][encounter_key]
                    field_value = descriptions[instance_type][encounter_key]
                    embeds[f"{instance_type}_{embed_id}"].add_field(name=field_name, value=field_value, inline=False)

    for embed_key in embeds:
        if not validate_embed_size(embeds[embed_key]):
            raise ValueError(f"Embed {embed_key} is invalid due to size limits.")

    return embeds
