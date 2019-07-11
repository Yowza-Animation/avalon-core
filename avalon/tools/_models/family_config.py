from . import qtawesome, io, api
from ...vendor import six


FAMILY_ICON_COLOR = "#0091B2"


class Singleton(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(
                Singleton, cls
            ).__call__(*args, **kwargs)
        return cls._instances[cls]


class FamilyConfig(six.with_metaclass(Singleton, dict)):

    def get(self, name):
        """Get value from config with fallback to default"""
        # We assume the default fallback key in the config is `__default__`
        return super(FamilyConfig, self).get(
            name,
            super(FamilyConfig, self).get(
                "__default__", None
            )
        )


    def refresh(self):
        """Get the family configurations from the database

        The configuration must be stored on the project under `config`.
        For example:

        {
            "config": {
                "families": [
                    {"name": "avalon.camera", label: "Camera", "icon": "photo"},
                    {"name": "avalon.anim", label: "Animation", "icon": "male"},
                ]
            }
        }

        It is possible to override the default behavior and set specific families
        checked. For example we only want the families imagesequence  and camera
        to be visible in the Loader.

        # This will turn every item off
        api.data["familyStateDefault"] = False

        # Only allow the imagesequence and camera
        api.data["familyStateToggled"] = ["imagesequence", "camera"]

        """
        # Update the icons from the project configuration
        project = io.find_one(
            {"type": "project"},
            projection={"config.families": True}
        )

        assert project, "Project not found!"
        families = project['config'].get("families", [])
        families = {family['name']: family for family in families}

        # Check if any family state are being overwritten by the configuration
        default_state = api.data.get("familiesStateDefault", True)
        toggled = set(api.data.get("familiesStateToggled", []))

        # Replace icons with a Qt icon we can use in the user interfaces
        default_icon = qtawesome.icon("fa.folder", color=FAMILY_ICON_COLOR)
        for name, family in families.items():
            # Set family icon
            icon = family.get("icon", None)
            if icon:
                family['icon'] = qtawesome.icon(
                    "fa.{}".format(icon), color=FAMILY_ICON_COLOR
                )
            else:
                family['icon'] = default_icon

            # Update state
            state = not default_state if name in toggled else default_state
            family["state"] = state

        # Default configuration
        families["__default__"] = {"icon": default_icon}

        self.clear()
        self.update(families)