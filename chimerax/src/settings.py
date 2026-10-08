from chimerax.core.settings import Settings


class PLIPSettings(Settings):
    AUTO_SAVE = {'python': '', 'appearance': '', 'language': 'en'}


def get_settings(session):
    # Retain the original preference namespace across the PLIP-Xplorer rename.
    settings = getattr(session, '_plip_settings', None)
    if settings is None:
        settings = session._plip_settings = PLIPSettings(session, 'PLIP')
    return settings
