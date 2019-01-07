import os
import sys
from collections import OrderedDict
import importlib
from .. import api, io
import contextlib
from pyblish import api as pyblish
from ..vendor import toml
import logging
import nuke
from . import lib


log = logging.getLogger(__name__)

AVALON_CONFIG = os.environ["AVALON_CONFIG"]


def reload_pipeline():
    """Attempt to reload pipeline at run-time.

    CAUTION: This is primarily for development and debugging purposes.

    """

    import importlib

    api.uninstall()
    _uninstall_menu()

    for module in ("avalon.io",
                   "avalon.lib",
                   "avalon.pipeline",
                   "avalon.nuke.pipeline",
                   "avalon.nuke.lib",
                   "avalon.tools.loader.app",
                   "avalon.tools.creator.app",
                   "avalon.tools.manager.app",

                   "avalon.api",
                   "avalon.tools",
                   "avalon.nuke",
                   "{}".format(AVALON_CONFIG),
                   "{}.lib".format(AVALON_CONFIG)):
        log.info("Reloading module: {}...".format(module))
        module = importlib.import_module(module)
        reload(module)

    import avalon.nuke
    api.install(avalon.nuke)

    _install_menu()
    _register_events()


def containerise(node,
                 name,
                 namespace,
                 context,
                 loader=None,
                 data=None):
    """Bundle `nodes` into an assembly and imprint it with metadata

    Containerisation enables a tracking of version, author and origin
    for loaded assets.

    Arguments:
        node (object): The node in Nuke to imprint as container,
        usually a Reader.
        name (str): Name of resulting assembly
        namespace (str): Namespace under which to host container
        context (dict): Asset information
        loader (str, optional): Name of node used to produce this container.

    Returns:
        None

    """

    data_imprint = OrderedDict({
        "schema": "avalon-core:container-2.0",
        "id": "pyblish.avalon.container",
        "name": str(name),
        "namespace": str(namespace),
        "loader": str(loader),
        "representation": str(context["representation"]["_id"]),
    })

    if data:
        {data_imprint.update({k: v}) for k, v in data.items()}

    log.info("data: {}".format(data_imprint))

    lib.add_avalon_tab_knob(node)

    node['avalon'].setValue(toml.dumps(data_imprint))


def parse_container(node):
    """Returns containerised data of a node

    This reads the imprinted data from `containerise`.

    """

    raw_text_data = node['avalon'].value()
    data = toml.loads(raw_text_data, _dict=dict)

    if not isinstance(data, dict):
        return

    # If not all required data return the empty container
    required = ['schema', 'id', 'name',
                'namespace', 'loader', 'representation']
    if not all(key in data for key in required):
        return

    container = {key: data[key] for key in required}

    # Store the node's name
    container["objectName"] = node["name"].value()

    # Store reference to the node object
    container["_tool"] = node

    return container


def update_container(node, keys=dict()):
    """Returns node with updateted containder data

    Arguments:
        node (object): The node in Nuke to imprint as container,
        keys (dict): data which should be updated

    Returns:
        node (object): nuke node with updated container data
    """

    raw_text_data = node['avalon'].value()
    data = toml.loads(raw_text_data, _dict=dict)

    if not isinstance(data, dict):
        return

    # If not all required data return the empty container
    required = ['schema', 'id', 'name',
                'namespace', 'node_name', 'representation']
    if not all(key in data for key in required):
        return

    container = {key: data[key] for key in required}

    for key, value in container.items():
        try:
            container[key] = keys[key]
        except KeyError:
            pass

    node['avalon'].setValue('')
    node['avalon'].setValue(toml.dumps(container))

    return node


class Creator(api.Creator):
    def process(self):
        nodes = nuke.allNodes()

        if (self.options or {}).get("useSelection"):
            nodes = nuke.selectedNodes()

        instance = [n for n in nodes
                    if n["name"].value() in self.name] or None

        instance = lib.imprint(instance, self.data)

        return instance


def ls():
    """List available containers.

    This function is used by the Container Manager in Nuke. You'll
    need to implement a for-loop that then *yields* one Container at
    a time.

    See the `container.json` schema for details on how it should look,
    and the Maya equivalent, which is in `avalon.maya.pipeline`
    """
    all_nodes = nuke.allNodes(recurseGroups=True)

    # TODO: add readgeo, readcamera, readimage
    reads = [n for n in all_nodes if n.Class() == 'Read']

    for r in reads:
        container = parse_container(r)
        if container:
            yield container


def install(config):
    """Install Nuke-specific functionality of avalon-core.

    This is where you install menus and register families, data
    and loaders into Nuke.

    It is called automatically when installing via `api.install(nuke)`.

    See the Maya equivalent for inspiration on how to implement this.

    """

    _install_menu()
    _register_events()

    pyblish.register_host("nuke")
    # Trigger install on the config's "nuke" package
    config = find_host_config(config)

    if hasattr(config, "install"):
        config.install()

    log.info("config.nuke installed")


def find_host_config(config):
    try:
        config = importlib.import_module(config.__name__ + ".nuke")
    except ImportError as exc:
        if str(exc) != "No module name {}".format(config.__name__ + ".nuke"):
            raise
        config = None

    return config


def uninstall(config):
    """Uninstall all tha was installed

    This is where you undo everything that was done in `install()`.
    That means, removing menus, deregistering families and  data
    and everything. It should be as though `install()` was never run,
    because odds are calling this function means the user is interested
    in re-installing shortly afterwards. If, for example, he has been
    modifying the menu or registered families.

    """
    config = find_host_config(config)
    if hasattr(config, "uninstall"):
        config.uninstall()

    _uninstall_menu()

    pyblish.deregister_host("nuke")


def _install_menu():
    from ..tools import (
        creator,
        # publish,
        workfiles,
        cbloader,
        cbsceneinventory,
        contextmanager
    )
    # for now we are using `lite` version
    # TODO: just for now untill qml in Nuke will be fixed (pyblish-qml#301)
    import pyblish_lite as publish

    # Create menu
    menubar = nuke.menu("Nuke")
    menu = menubar.addMenu(api.Session["AVALON_LABEL"])

    label = "{0}, {1}".format(
        api.Session["AVALON_ASSET"], api.Session["AVALON_TASK"]
    )
    context_menu = menu.addMenu(label)
    context_menu.addCommand("Set Context", contextmanager.show)

    menu.addSeparator()
    menu.addCommand("Work Files...",
                    lambda: workfiles.show(
                        os.environ["AVALON_WORKDIR"]
                    )
                    )
    menu.addSeparator()
    menu.addCommand("Create...", creator.show)
    menu.addCommand("Load...", cbloader.show)
    menu.addCommand("Publish...", publish.show)
    menu.addCommand("Manage...", cbsceneinventory.show)

    menu.addSeparator()
    frames_menu = menu.addMenu("Reset Frame Range")
    frames_menu.addCommand("Cut length", reset_frame_range)
    frames_menu.addCommand("Full length(handles)", reset_frame_range_handles)
    menu.addCommand("Reset Resolution", reset_resolution)

    menu.addSeparator()
    menu.addCommand("Reload Pipeline", reload_pipeline)


def _uninstall_menu():
    menubar = nuke.menu("Nuke")
    menubar.removeItem(api.Session["AVALON_LABEL"])


def reset_frame_range():
    """Set frame range to current asset"""

    fps = float(api.Session.get("AVALON_FPS", 25))

    nuke.root()["fps"].setValue(fps)
    asset = api.Session["AVALON_ASSET"]
    asset = io.find_one({"name": asset, "type": "asset"})

    try:
        edit_in = int(asset["data"]["fstart"])
        edit_out = int(asset["data"]["fend"])
    except KeyError:
        log.warning(
            "Frame range not set! No edit information found for "
            "\"{0}\".".format(asset["name"])
        )
        return

    nuke.root()["first_frame"].setValue(edit_in)
    nuke.root()["last_frame"].setValue(edit_out)


def reset_frame_range_handles():
    """Set frame range to current asset"""

    fps = float(api.Session.get("AVALON_FPS", 25))

    nuke.root()["fps"].setValue(fps)
    name = api.Session["AVALON_ASSET"]
    asset = io.find_one({"name": name, "type": "asset"})

    if "data" not in asset:
        msg = "Asset {} don't have set any 'data'".format(name)
        log.warning(msg)
        nuke.message(msg)
        return
    data = asset["data"]

    missing_cols = []
    check_cols = ["fstart", "fend", "handles"]

    for col in check_cols:
        if col not in data:
            missing_cols.append(col)

    if len(missing_cols) > 0:
        missing = ", ".join(missing_cols)
        msg = "'{}' are not set for asset '{}'!".format(missing, name)
        log.warning(msg)
        nuke.message(msg)
        return

    handles = int(asset["data"]["handles"])
    edit_in = int(asset["data"]["fstart"]) - handles
    edit_out = int(asset["data"]["fend"]) + handles

    nuke.root()["first_frame"].setValue(edit_in)
    nuke.root()["last_frame"].setValue(edit_out)


def reset_resolution():
    """Set resolution to project resolution."""
    project = io.find_one({"type": "project"})

    try:
        width = project["data"].get("resolution_width", 1920)
        height = project["data"].get("resolution_height", 1080)
    except KeyError:
        print(
            "No resolution information found for \"{0}\".".format(
                project["name"]
            )
        )
        return

    current_width = nuke.root()["format"].value().width()
    current_height = nuke.root()["format"].value().height()

    if width != current_width or height != current_height:

        fmt = None
        for f in nuke.formats():
            if f.width() == width and f.height() == height:
                fmt = f.name()

        if not fmt:
            nuke.addFormat(
                "{0} {1} {2}".format(int(width), int(height), project["name"])
            )
            fmt = project["name"]

        nuke.root()["format"].setValue(fmt)


def publish():
    """Shorthand to publish from within host"""
    import pyblish.util
    return pyblish.util.publish()


def _register_events():

    api.on("taskChanged", _on_task_changed)
    log.info("Installed event callback for 'taskChanged'..")


def _on_task_changed(*args):

    # Update menu
    _uninstall_menu()
    _install_menu()


@contextlib.contextmanager
def viewer_update_and_undo_stop():
    """Lock viewer from updating and stop recording undo steps"""
    try:
        # nuke = getattr(sys.modules["__main__"], "nuke", None)
        # lock all connections between nodes
        # nuke.Root().knob('lock_connections').setValue(1)

        # stop active viewer to update any change
        nuke.activeViewer().stop()
        nuke.Undo.disable()
        yield
    finally:
        # nuke.Root().knob('lock_connections').setValue(0)
        # nuke.activeViewer().start()
        nuke.Undo.enable()
