import os
import sys
import json
import time
import subprocess
import collections
import asyncio
import logging
import socket
import platform
import filecmp
import tempfile
import threading
from queue import Queue
from contextlib import closing

from ..tools import (
    workfiles,
    creator,
    loader,
    publish,
    sceneinventory,
    libraryloader
)
from avalon import api, tvpaint

from aiohttp import web
from aiohttp_json_rpc import JsonRpc
from aiohttp_json_rpc.protocol import (
    encode_request, encode_error, decode_msg, JsonRpcMsgTyp
)
from aiohttp_json_rpc.exceptions import RpcError

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

# Filename of localization file for avalon plugin
# - localization file may be used to modify labels in plugin
LOCALIZATION_FILENAME = "avalon.loc"


class CommunicatorWrapper:
    # TODO add logs and exceptions
    communicator = None
    _connected_client = None

    # Variable which can be modified to register localization file from
    # config
    localization_file = None

    @classmethod
    def create_communicator(cls, *args, **kwargs):
        if not cls.communicator:
            cls.communicator = Communicator(*args, **kwargs)
        return cls.communicator

    @classmethod
    def _client(cls):
        if not cls.communicator:
            log.warning("Communicator object was not created yet.")
            return None

        if not cls.communicator.websocket_rpc:
            log.warning("Communicator's server did not start yet.")
            return None

        for client in cls.communicator.websocket_rpc.clients:
            if not client.ws.closed:
                return client
        log.warning("Client is not yet connected to Communicator.")
        return None

    @classmethod
    def client(cls):
        if not cls._connected_client or cls._connected_client.ws.closed:
            cls._connected_client = cls._client()
        return cls._connected_client

    @classmethod
    def send_request(cls, method, params=[], client=None):
        if client is None:
            client = cls.client()

        if not client:
            return

        return cls.communicator.websocket_rpc.send_request(
            client, method, params
        )

    @classmethod
    def execute_george(cls, george_script):
        """Execute passed goerge script in TVPaint."""
        return CommunicatorWrapper.send_request(
            "execute_george", [george_script]
        )

    @classmethod
    def execute_george_through_file(cls, george_script):
        """Execute george script with temp file.

        Allows to execute multiline george script without stopping websocket
        client.

        On windows make sure script does not contain paths with backwards
        slashes in paths, TVPaint won't execute properly in that case.

        Args:
            george_script (str): George script to execute. May be multilined.
        """
        temporary_file = tempfile.NamedTemporaryFile(
            mode="w", suffix=".grg", delete=False
        )
        temporary_file.write(george_script)
        temporary_file.close()
        CommunicatorWrapper.execute_george(
            "tv_runscript {}".format(
                temporary_file.name.replace("\\", "/")
            )
        )
        os.remove(temporary_file.name)

    @classmethod
    def send_notification(cls, method, params=[], client=None):
        if client is None:
            client = cls.client()

        if not client:
            return

        cls.communicator.websocket_rpc.send_notification(
            client, method, params
        )


def register_localization_file(filepath):
    """Register localization file to be copied with TVPaint plugins.

    This is meant to be called and set from config.

    Args:
        filepath (str): Full path to `.loc` file.
    """
    CommunicatorWrapper.localization_file = filepath


class WebSocketServer:
    def __init__(self):
        self.client = None

        self.loop = asyncio.new_event_loop()
        self.app = web.Application(loop=self.loop)
        self.port = self.find_free_port()
        self.websocket_thread = WebsocketServerThread(
            self, self.port, loop=self.loop
        )

    @property
    def server_is_running(self):
        return self.websocket_thread.server_is_running

    def add_route(self, *args, **kwargs):
        self.app.router.add_route(*args, **kwargs)

    @staticmethod
    def find_free_port():
        with closing(
            socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        ) as sock:
            sock.bind(("", 0))
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            port = sock.getsockname()[1]
        return port

    def start(self):
        self.websocket_thread.start()

    def stop(self):
        try:
            if self.websocket_thread.is_running:
                log.debug("Stopping websocket server")
                self.websocket_thread.is_running = False
                self.websocket_thread.stop()
        except Exception:
            log.warning(
                "Error has happened during Killing websocket server",
                exc_info=True
            )


class WebsocketServerThread(threading.Thread):
    """ Listener for websocket rpc requests.

        It would be probably better to "attach" this to main thread (as for
        example Harmony needs to run something on main thread), but currently
        it creates separate thread and separate asyncio event loop
    """
    def __init__(self, module, port, loop):
        super(WebsocketServerThread, self).__init__()
        self.is_running = False
        self.server_is_running = False
        self.port = port
        self.module = module
        self.loop = loop
        self.runner = None
        self.site = None
        self.tasks = []

    def run(self):
        self.is_running = True

        try:
            log.debug("Starting websocket server")

            self.loop.run_until_complete(self.start_server())

            log.info(
                "Running Websocket server on URL:"
                " \"ws://localhost:{}\"".format(self.port)
            )

            asyncio.ensure_future(self.check_shutdown(), loop=self.loop)

            self.server_is_running = True
            self.loop.run_forever()

        except Exception:
            log.warning(
                "Websocket Server service has failed", exc_info=True
            )
        finally:
            self.server_is_running = False
            # optional
            self.loop.close()

        self.is_running = False
        log.info("Websocket server stopped")

    async def start_server(self):
        """ Starts runner and TCPsite """
        self.runner = web.AppRunner(self.module.app)
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, "localhost", self.port)
        await self.site.start()

    def stop(self):
        """Sets is_running flag to false, 'check_shutdown' shuts server down"""
        self.is_running = False

    async def check_shutdown(self):
        """ Future that is running and checks if server should be running
            periodically.
        """
        while self.is_running:
            while self.tasks:
                task = self.tasks.pop(0)
                log.debug("waiting for task {}".format(task))
                await task
                log.debug("returned value {}".format(task.result))

            await asyncio.sleep(0.5)

        log.debug("## Server shutdown started")
        await self.site.stop()
        log.debug("# Site stopped")
        await self.runner.cleanup()
        log.debug("# Server runner stopped")
        tasks = [
            task for task in asyncio.all_tasks()
            if task is not asyncio.current_task()
        ]
        list(map(lambda task: task.cancel(), tasks))  # cancel all the tasks
        results = await asyncio.gather(*tasks, return_exceptions=True)
        log.debug(f"Finished awaiting cancelled tasks, results: {results}...")
        await self.loop.shutdown_asyncgens()
        # to really make sure everything else has time to stop
        await asyncio.sleep(0.07)
        self.loop.stop()


class TVPaintRpc(JsonRpc):
    def __init__(self, communication_obj, route_name="", **kwargs):
        super().__init__(**kwargs)
        self.requests_ids = collections.defaultdict(lambda: 0)
        self.waiting_requests = collections.defaultdict(list)
        self.responses = collections.defaultdict(list)

        self.route_name = route_name
        self.communication_obj = communication_obj
        # Register methods
        self.add_methods(
            (route_name, self.workfiles_tool),
            (route_name, self.loader_tool),
            (route_name, self.creator_tool),
            (route_name, self.publish_tool),
            (route_name, self.scene_inventory_tool),
            (route_name, self.library_loader_tool)
        )

    async def _handle_rpc_msg(self, http_request, raw_msg):
        # This is duplicated code from super but there is no way how to do it
        # to be able handle server->client requests
        host = http_request.host
        if host in self.waiting_requests:
            try:
                _raw_message = raw_msg.data
                msg = decode_msg(_raw_message)

            except RpcError as error:
                await self._ws_send_str(http_request, encode_error(error))
                return

            if msg.type in (JsonRpcMsgTyp.RESULT, JsonRpcMsgTyp.ERROR):
                msg_data = json.loads(_raw_message)
                if msg_data.get("id") in self.waiting_requests[host]:
                    self.responses[host].append(msg_data)
                    return

        return await super()._handle_rpc_msg(http_request, raw_msg)

    def client_connected(self):
        # TODO This is poor check. Add check it is client from TVPaint
        if self.clients:
            return True
        return False

    # Panel routes for tools
    async def workfiles_tool(self):
        log.info("Triggering Workfile tool")
        item = MainThreadItem(workfiles.show)
        result = self._execute_in_main_thread(item)
        return result

    async def loader_tool(self):
        log.info("Triggering Loader tool")
        item = MainThreadItem(loader.show)
        result = self._execute_in_main_thread(item)
        return result

    async def creator_tool(self):
        log.info("Triggering Creator tool")
        item = MainThreadItem(creator.show)
        result = self._execute_in_main_thread(item)
        return result

    async def publish_tool(self):
        log.info("Triggering Publish tool")
        item = MainThreadItem(publish.show)
        result = self._execute_in_main_thread(item)
        return result

    async def scene_inventory_tool(self):
        log.info("Triggering Scene inventory tool")
        item = MainThreadItem(sceneinventory.show)
        result = self._execute_in_main_thread(item)
        return result

    async def library_loader_tool(self):
        log.info("Triggering Library loader tool")
        item = MainThreadItem(libraryloader.show)
        result = self._execute_in_main_thread(item)
        return result

    def _execute_in_main_thread(self, item):
        return self.communication_obj.execute_in_main_thread(item)

    def send_notification(self, client, method, params=[]):
        future = asyncio.run_coroutine_threadsafe(
            client.ws.send_str(encode_request(method, params=params)),
            loop=self.loop
        )
        result = future.result()

    def send_request(self, client, method, params=[], timeout=0):
        client_host = client.host

        request_id = self.requests_ids[client_host]
        self.requests_ids[client_host] += 1

        self.waiting_requests[client_host].append(request_id)

        log.debug("Sending request to client {} ({}, {}) id: {}".format(
            client_host, method, params, request_id
        ))
        future = asyncio.run_coroutine_threadsafe(
            client.ws.send_str(encode_request(method, request_id, params)),
            loop=self.loop
        )
        result = future.result()

        not_found = object()
        response = not_found
        start = time.time()
        while True:
            if client.ws.closed:
                return None

            for _response in self.responses[client_host]:
                _id = _response.get("id")
                if _id == request_id:
                    response = _response
                    break

            if response is not not_found:
                break

            if timeout > 0 and (time.time() - start) > timeout:
                raise Exception("Timeout passed")
                return

            time.sleep(0.1)

        if response is not_found:
            raise Exception("Connection closed")

        self.responses[client_host].remove(response)

        error = response.get("error")
        result = response.get("result")
        if error:
            raise Exception("Error happened: {}".format(error))
        return result


class MainThreadItem:
    """Structure to store information about callback in main thread.

    Item should be used to execute callback in main thread which may be needed
    for execution of Qt objects.

    Item store callback (callable variable), arguments and keyword arguments
    for the callback. Item hold information about it's process.
    """
    not_set = object()
    sleep_time = 0.1

    def __init__(self, callback, *args, **kwargs):
        self.done = False
        self.exc_info = self.not_set
        self.result = self.not_set
        self.callback = callback
        self.args = args
        self.kwargs = kwargs

    def execute(self):
        """Execute callback and store it's result.

        Method must be called from main thread. Item is marked as `done`
        when callback execution finished. Store output of callback of exception
        information when callback raise one.
        """
        log.debug("Executing process in main thread")
        if self.done:
            log.warning("- item is already processed")
            return

        callback = self.callback
        args = self.args
        kwargs = self.kwargs
        log.info("Running callback: {}".format(str(callback)))
        try:
            result = callback(*args, **kwargs)
            self.result = result

        except Exception:
            self.exc_info = sys.exc_info()

        finally:
            self.done = True

    def wait(self):
        """Wait for result from main thread.

        This method stops current thread until callback is executed.

        Returns:
            object: Output of callback. May be any type or object.

        Raises:
            Exception: Reraise any exception that happened during callback
                execution.
        """
        while not self.done:
            time.sleep(self.sleep_time)

        if self.exc_info is self.not_set:
            return self.result
        raise self.exc_info


class Communicator:
    def __init__(self, qt_app):
        self.callback_queue = Queue()
        self.qt_app = qt_app

        self.process = None
        self.websocket_route = None
        self.websocket_server = None
        self.websocket_rpc = None

    def execute_in_main_thread(self, main_thread_item):
        """Add `MainThreadItem` to callback queue and wait for result."""
        self.callback_queue.put(main_thread_item)
        return main_thread_item.wait()

    def main_thread_listen(self):
        """Get last `MainThreadItem` from queue.

        Must be called from main thread.

        Method checks if host process is still running as it may cause
        issues if not.
        """
        # check if host still running
        if self.process.poll() is not None:
            self.websocket_server.stop()
            return self.qt_app.quit()

        if self.callback_queue.empty():
            return None
        return self.callback_queue.get()

    def localization_file(self):
        # TODO: return localization file from config or default.
        return None

    def _windows_copy(self, src_dst_mapping):
        """Windows specific copy process asking for admin permissions.

        It is required to have administration permissions to copy plugin to
        TVPaint installation folder.

        Method requires `pywin32` python module.

        Args:
            src_dst_mapping (list, tuple, set): Mapping of source file to
                destination. Both must be full path. Each item must be iterable
                of size 2 `(C:/src/file.dll, C:/dst/file.dll)`.
        """

        from win32com.shell import shell
        import pythoncom

        dst_folders = collections.defaultdict(list)
        for src, dst in src_dst_mapping:
            src = os.path.normpath(src)
            dst = os.path.normpath(dst)
            dst_filename = os.path.basename(dst)
            dst_folder_path = os.path.dirname(dst)
            dst_folders[dst_folder_path].append((dst_filename, src))

        # create an instance of IFileOperation
        fo = pythoncom.CoCreateInstance(
            shell.CLSID_FileOperation,
            None,
            pythoncom.CLSCTX_ALL,
            shell.IID_IFileOperation
        )

        # here you can use SetOperationFlags, progress Sinks, etc.
        for folder_path, items in dst_folders.items():
            # create an instance of IShellItem for the target folder
            folder_item = shell.SHCreateItemFromParsingName(
                folder_path, None, shell.IID_IShellItem
            )
            for _dst_filename, source_file_path in items:
                # create an instance of IShellItem for the source item
                copy_item = shell.SHCreateItemFromParsingName(
                    source_file_path, None, shell.IID_IShellItem
                )
                # queue the copy operation
                fo.CopyItem(copy_item, folder_item, _dst_filename, None)

        # commit
        fo.PerformOperations()

    def _prepare_windows_plugin(self, launch_args):
        """Copy plugin to TVPaint plugins and set PATH to dependencies.

        Check if plugin in TVPaint's plugins exist and match to plugin
        version to current implementation version. Based on 64-bit or 32-bit
        version of the plugin. Path to libraries required for plugin is added
        to PATH variable.
        """

        host_executable = launch_args[0]
        executable_file = os.path.basename(host_executable)
        if "64bit" in executable_file:
            subfolder = "windows_x64"
        elif "32bit" in executable_file:
            subfolder = "windows_x86"
        else:
            raise ValueError(
                "Can't determine if executable "
                "leads to 32-bit or 64-bit TVPaint!"
            )

        # Folder for right windows plugin files
        source_plugins_dir = os.path.join(
            os.path.dirname(os.path.abspath(tvpaint.__file__)),
            "plugin_files",
            subfolder
        )

        # Path to libraies (.dll) required for plugin library
        # - additional libraries can be copied to TVPaint installation folder
        #   (next to executable) or added to PATH environment variable
        additional_libs_folder = os.path.join(
            source_plugins_dir,
            "additional_libraries"
        )
        additional_libs_folder = additional_libs_folder.replace("\\", "/")
        if additional_libs_folder not in os.environ["PATH"]:
            os.environ["PATH"] += (os.pathsep + additional_libs_folder)

        # Path to TVPaint's plugins folder (where we want to add our plugin)
        host_plugins_path = os.path.join(
            os.path.dirname(host_executable),
            "plugins"
        )

        # Files that must be copied to TVPaint's plugin folder
        plugin_dir = os.path.join(source_plugins_dir, "plugin")

        to_copy = []
        for filename in os.listdir(plugin_dir):
            src_full_path = os.path.join(plugin_dir, filename)
            dst_full_path = os.path.join(host_plugins_path, filename)
            if (
                not os.path.exists(dst_full_path)
                or not filecmp.cmp(src_full_path, dst_full_path)
            ):
                to_copy.append((src_full_path, dst_full_path))

        # Add localization file is there is any
        localization_file_src = CommunicatorWrapper.localization_file
        if localization_file_src and os.path.exists(localization_file_src):
            localization_file_dst = os.path.join(
                host_plugins_path, LOCALIZATION_FILENAME
            )
            if (
                not os.path.exists(localization_file_dst)
                or not filecmp.cmp(
                    localization_file_src, localization_file_dst
                )
            ):
                to_copy.append((localization_file_src, localization_file_dst))

        # Skip copy if everything is done
        if not to_copy:
            return

        # Try to copy
        try:
            self._windows_copy(to_copy)
        except Exception:
            pass

        # Validate copy was done
        invalid = []
        for src, dst in to_copy:
            if not os.path.exists(dst) or not filecmp.cmp(src, dst):
                invalid.append((src, dst))

        if invalid:
            raise RuntimeError("Copying of plugin was not successfull")

    def _launch_tv_paint(self, launch_args):
        if platform.system().lower() == "windows":
            self._prepare_windows_plugin(launch_args)

        kwargs = {
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
            "env": os.environ
        }
        self.process = subprocess.Popen(launch_args, **kwargs)

    def launch(self, launch_args):
        """Prepare all required data and launch host.

        First is prepared websocket server as communication point for host,
        when server is ready to use host is launched as subprocess.
        """
        log.info("Installing TVPaint implementation")
        api.install(tvpaint)

        # Launch TVPaint and the websocket server.
        log.info("Launching TVPaint")
        self.websocket_server = WebSocketServer()
        self.websocket_rpc = TVPaintRpc(self, loop=self.websocket_server.loop)

        os.environ["WEBSOCKET_URL"] = "ws://localhost:{}".format(
            self.websocket_server.port
        )
        self.websocket_server.add_route(
            "*", "/", self.websocket_rpc.handle_request
        )
        log.info("Added request handler for url: {}".format(
            os.environ["WEBSOCKET_URL"]
        ))

        self.websocket_server.start()
        # Make sure RPC is using same loop as websocket server
        while not self.websocket_server.server_is_running:
            time.sleep(0.1)

        # Start TVPaint when server is running
        self._launch_tv_paint(launch_args)

        log.info("Waiting for client connection")
        while True:
            if self.process.poll() is not None:
                log.debug("Host process is not alive. Exiting")
                self.websocket_server.stop()
                self.qt_app.quit()
                return

            if self.websocket_rpc.client_connected():
                log.info("Client has connected")
                break
            time.sleep(0.5)

        api.emit("application.launched")

    def stop(self):
        """Stop communication and currently running python process."""
        log.info("Stopping communication")
        self.websocket_server.stop()
        self.qt_app.quit()
