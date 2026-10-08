"""ChimeraX entry points. The PLIP/Open Babel engine runs outside ChimeraX."""
from chimerax.core.toolshed import BundleAPI


class _PLIPAPI(BundleAPI):
    api_version = 1

    @staticmethod
    def start_tool(session, bi, ti):
        from .tool import PLIPTool
        return PLIPTool(session, ti.name)

    @staticmethod
    def register_command(bi, ci, logger):
        from .commands import register_command
        register_command(ci.name, logger)


bundle_api = _PLIPAPI()
