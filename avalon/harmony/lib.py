import subprocess
import threading
import os
import random
import zipfile
import sys
import importlib
import queue
import shutil
import logging
import contextlib
import json
import signal
import time
from uuid import uuid4

from .server import Server
from ..vendor.Qt import QtWidgets
from ..tools import workfiles
from ..toonboom import setup_startup_scripts

self = sys.modules[__name__]
self.server = None
self.pid = None
self.application_path = None
self.callback_queue = None
self.workfile_path = None
self.port = None

# Setup logging.
self.log = logging.getLogger(__name__)
self.log.setLevel(logging.DEBUG)


def signature(postfix="func") -> str:
    """Return random ECMA6 compatible function name.

    Args;
        postfix (str): name to append to random string.

    Returns:
        str: random function name.

    """
    return "f{}_{}".format(str(uuid4()).replace("-", "_"), postfix)


class _ZipFile(zipfile.ZipFile):
    """Extended check for windows invalid characters."""
    # this is extending default zipfile table for few invalid characters
    # that can come from Mac
    _windows_illegal_characters = ":<>|\"?*\r\n\x00"
    _windows_illegal_name_trans_table = str.maketrans(
        _windows_illegal_characters,
        "_" * len(_windows_illegal_characters)
    )


def execute_in_main_thread(func_to_call_from_main_thread):
    self.callback_queue.put(func_to_call_from_main_thread)


def main_thread_listen():
    callback = self.callback_queue.get()
    callback()


def launch(application_path):
    """Setup for Harmony launch.

    Launches Harmony and the server, then starts listening on the main thread
    for callbacks from the server. This is to have Qt applications run in the
    main thread.
    """
    from avalon import api, harmony

    api.install(harmony)

    self.port = random.randrange(5000, 6000)
    os.environ["AVALON_HARMONY_PORT"] = str(self.port)
    self.application_path = application_path

    # Launch Harmony.
    setup_startup_scripts()

    if os.environ.get("AVALON_HARMONY_WORKFILES_ON_LAUNCH", False):
        workfiles.show(save=False)

    # No launch through Workfiles happened.
    if not self.workfile_path:
        zip_file = os.path.join(os.path.dirname(__file__), "temp.zip")
        temp_path = get_local_harmony_path(zip_file)
        if os.path.exists(temp_path):
            self.log.info(f"removing existing {temp_path}")
            try:
                shutil.rmtree(temp_path)
            except Exception as e:
                self.log.critical(f"cannot clear {temp_path}")
                raise Exception(f"cannot clear {temp_path}") from e

        launch_zip_file(zip_file)

    self.callback_queue = queue.Queue()
    while True:
        main_thread_listen()


def get_local_harmony_path(filepath):
    """From the provided path get the equivalent local Harmony path."""
    basename = os.path.splitext(os.path.basename(filepath))[0]
    harmony_path = os.path.join(os.path.expanduser("~"), ".avalon", "harmony")
    return os.path.join(harmony_path, basename)


def launch_zip_file(filepath):
    """Launch a Harmony application instance with the provided zip file."""
    print("Localizing {}".format(filepath))

    temp_path = get_local_harmony_path(filepath)
    scene_path = os.path.join(
        temp_path, os.path.basename(temp_path) + ".xstage"
    )
    unzip = False
    if os.path.exists(scene_path):
        # Check remote scene is newer than local.
        if os.path.getmtime(scene_path) < os.path.getmtime(filepath):
            shutil.rmtree(temp_path)
            unzip = True
    else:
        unzip = True

    if unzip:
        with _ZipFile(filepath, "r") as zip_ref:
            zip_ref.extractall(temp_path)

    # Close existing scene.
    if self.pid:
        os.kill(self.pid, signal.SIGTERM)

    # Stop server.
    if self.server:
        self.server.stop()

    # Launch Avalon server.
    self.server = Server(self.port)
    thread = threading.Thread(target=self.server.start)
    thread.daemon = True
    thread.start()

    # Save workfile path for later.
    self.workfile_path = filepath

    # find any xstage files is directory, prefer the one with the same name
    # as directory (plus extension)
    xstage_files = []
    for _, _, files in os.walk(temp_path):
        for file in files:
            if os.path.splitext(file)[1] == ".xstage":
                xstage_files.append(file)

    if not os.path.basename("temp.zip"):
        if not xstage_files:
            self.server.stop()
            print("no xstage file was found")
            return

    # try to use first available
    scene_path = os.path.join(
        temp_path, xstage_files[0]
    )

    # prefer the one named as zip file
    zip_based_name = "{}.xstage".format(
        os.path.splitext(os.path.basename(filepath))[0])

    if zip_based_name in xstage_files:
        scene_path = os.path.join(
            temp_path, zip_based_name
        )

    if not os.path.exists(scene_path):
        print("error: cannot determine scene file")
        self.server.stop()
        return

    print("Launching {}".format(scene_path))
    process = subprocess.Popen([self.application_path, scene_path])
    self.pid = process.pid


def on_file_changed(path, threaded=True):
    """Threaded zipping and move of the project directory.

    This method is called when the `.xstage` file is changed.
    """

    self.log.debug("File changed: " + path)

    if self.workfile_path is None:
        return

    if threaded:
        thread = threading.Thread(
            target=zip_and_move,
            args=(os.path.dirname(path), self.workfile_path)
        )
        thread.start()
    else:
        zip_and_move(os.path.dirname(path), self.workfile_path)


def zip_and_move(source, destination):
    """Zip a directory and move to `destination`

    Args:
        - source (str): Directory to zip and move to destination.
        - destination (str): Destination file path to zip file.
    """
    os.chdir(os.path.dirname(source))
    shutil.make_archive(os.path.basename(source), "zip", source)
    with _ZipFile(os.path.basename(source) + ".zip") as zr:
        if zr.testzip() is not None:
            raise Exception("File archive is corrupted.")
    shutil.move(os.path.basename(source) + ".zip", destination)
    self.log.debug("Saved \"{}\" to \"{}\"".format(source, destination))


def show(module_name):
    """Call show on "module_name".

    This allows to make a QApplication ahead of time and always "exec_" to
    prevent crashing.

    Args:
        module_name (str): Name of module to call "show" on.
    """

    # Requests often get doubled up when showing tools, so we wait a second for
    # requests to be received properly.
    time.sleep(1)

    # Need to have an existing QApplication.
    app = QtWidgets.QApplication.instance()
    if not app:
        app = QtWidgets.QApplication(sys.argv)

    # Import and show tool.
    module = importlib.import_module(module_name)

    if "loader" in module_name:
        module.show(use_context=True)
    else:
        module.show()

    # QApplication needs to always execute.
    if "publish" in module_name:
        return

    app.exec_()


def get_scene_data():
    sig = signature("get_scene_data")
    func = """function %s(args)
    {
        var metadata = scene.metadata("avalon");
        if (metadata){
            return JSON.parse(metadata.value);
        }else {
            return {};
        }
    }
    %s
    """ % (sig, sig)
    try:
        return self.send({"function": func})["result"]
    except json.decoder.JSONDecodeError:
        # Means no sceen metadata has been made before.
        return {}
    except KeyError:
        # Means no existing scene metadata has been made.
        return {}


def set_scene_data(data):
    # Write scene data.
    sig = signature("set_scene_data")
    func = """function %s(args)
    {
        scene.setMetadata({
          "name"       : "avalon",
          "type"       : "string",
          "creator"    : "Avalon",
          "version"    : "1.0",
          "value"      : JSON.stringify(args[0])
        });
    }
    %s
    """ % (sig, sig)
    self.send({"function": func, "args": [data]})


def read(node_id):
    """Read object metadata in to a dictionary.

    Args:
        node_id (str): Path to node or id of object.

    Returns:
        dict
    """
    scene_data = get_scene_data()
    if node_id in get_scene_data():
        return scene_data[node_id]

    return {}


def remove(node_id):
    data = get_scene_data()
    del data[node_id]
    set_scene_data(data)


def imprint(node_id, data, remove=False):
    """Write `data` to the `node` as json.

    Arguments:
        node_id (str): Path to node or id of object.
        data (dict): Dictionary of key/value pairs.
        remove (bool): Removes the data from the scene.

    Example:
        >>> from avalon.harmony import lib
        >>> node = "Top/Display"
        >>> data = {"str": "someting", "int": 1, "float": 0.32, "bool": True}
        >>> lib.imprint(layer, data)
    """
    scene_data = get_scene_data()

    if remove and (node_id in scene_data):
        scene_data.pop(node_id, None)
    else:
        if node_id in scene_data:
            scene_data[node_id].update(data)
        else:
            scene_data[node_id] = data

    set_scene_data(scene_data)


@contextlib.contextmanager
def maintained_selection():
    """Maintain selection during context."""
    sig = signature("get_selection_nodes")
    func = """function %s()
    {
        var selection_length = selection.numberOfNodesSelected();
        var selected_nodes = [];
        for (var i = 0 ; i < selection_length; i++)
        {
            selected_nodes.push(selection.selectedNode(i));
        }
        return selected_nodes
    }
    %s
    """ % (sig, sig)
    selected_nodes = self.send({"function": func})["result"]

    sig = signature("select_nodes")
    func = """function %s(node_paths)
    {
        selection.clearSelection();
        for (var i = 0 ; i < node_paths.length; i++)
        {
            selection.addNodeToSelection(node_paths[i]);
        }
    }
    %s
    """ % (sig, sig)
    try:
        yield selected_nodes
    finally:
        selected_nodes = self.send(
            {"function": func, "args": selected_nodes}
        )


def send(request):
    """Public method for sending requests to Harmony."""
    return self.server.send(request)


@contextlib.contextmanager
def maintained_nodes_state(nodes):
    """Maintain nodes states during context."""
    # Collect current state.
    states = []
    for node in nodes:
        states.append(
            self.send(
                {"function": "node.getEnable", "args": [node]}
            )["result"]
        )

    # Disable all nodes.
    sig = signature("disable_all_nodes")
    func = """function %s(nodes)
    {
        for (var i = 0 ; i < nodes.length; i++)
        {
            node.setEnable(nodes[i], false);
        }
    }
    %s
    """ % (sig, sig)
    self.send({"function": func, "args": [nodes]})
    sig = signature("restore")
    # Restore state after yield.
    func = """function %s(args)
    {
        var nodes = args[0];
        var states = args[1];
        for (var i = 0 ; i < nodes.length; i++)
        {
            node.setEnable(nodes[i], states[i]);
        }
    }
    %s
    """ % (sig, sig)

    try:
        yield
    finally:
        self.send({"function": func, "args": [nodes, states]})


def save_scene():
    """Save the Harmony scene safely.

    The built-in (to Avalon) background zip and moving of the Harmony scene
    folder, interfers with server/client communication by sending two requests
    at the same time. This only happens when sending "scene.saveAll()". This
    method prevents this double request and safely saves the scene.
    """
    # Need to turn off the backgound watcher else the communication with
    # the server gets spammed with two requests at the same time.
    sig = signature("save_scene")
    func = """function %s()
    {
        var app = QCoreApplication.instance();
        app.avalon_on_file_changed = false;
        scene.saveAll();
        return (
            scene.currentProjectPath() + "/" +
            scene.currentVersionName() + ".xstage"
        );
    }
    %s
    """ % (sig, sig)
    scene_path = self.send({"function": func})["result"]

    # Manually update the remote file.
    self.on_file_changed(scene_path, threaded=False)

    # Re-enable the background watcher.
    sig = signature("enable_watcher")
    func = """function %s()
    {
        var app = QCoreApplication.instance();
        app.avalon_on_file_changed = true;
    }
    %s
    """ % (sig, sig)
    self.send({"function": func})


def save_scene_as(filepath):
    """Save Harmony scene as `filepath`."""
    scene_dir = os.path.dirname(filepath)
    destination = os.path.join(
        os.path.dirname(self.workfile_path),
        os.path.splitext(os.path.basename(filepath))[0] + ".zip"
    )

    if os.path.exists(scene_dir):
        shutil.rmtree(scene_dir)

    send(
        {"function": "scene.saveAs", "args": [scene_dir]}
    )["result"]

    zip_and_move(scene_dir, destination)

    self.workfile_path = destination
    sig = signature("add_path")
    func = """function %s(path)
    {
        var app = QCoreApplication.instance();
        app.watcher.addPath(path);
    }
    %s
    """ % (sig, sig)
    send(
        {"function": func, "args": [filepath]}
    )


def find_node_by_name(name, node_type):
    nodes = send(
        {"function": "node.getNodes", "args": [[node_type]]}
    )["result"]
    for node in nodes:
        node_name = node.split("/")[-1]
        if name == node_name:
            return node

    return None
