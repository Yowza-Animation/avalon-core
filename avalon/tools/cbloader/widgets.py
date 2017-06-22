import datetime

from ...vendor.Qt import QtWidgets, QtCore, QtGui
from ... import io
from ... import api

from .model import SubsetsModel
from .delegates import PrettyTimeDelegate, VersionDelegate
from . import lib


def _get_representations(version_id):
    """Return available representations representations for a version"""
    return [representation for representation in
            io.find({"type": "representation", "parent": version_id})
            if representation["name"] not in ("json", "source")]


class SubsetWidget(QtWidgets.QWidget):
    """A widget that lists the published subsets for an asset"""

    active_changed = QtCore.Signal()    # active index changed
    version_changed = QtCore.Signal()   # version state changed for a subset

    def __init__(self, parent=None):
        super(SubsetWidget, self).__init__(parent=parent)
        model = SubsetsModel()
        view = QtWidgets.QTreeView()
        view.setModel(model)

        view.setIndentation(5)
        view.setStyleSheet("""
            QTreeView::item{
                padding: 5px 1px;
                border: 0px;
            }
        """)
        view.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        view.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        view.setSortingEnabled(True)
        view.sortByColumn(0, QtCore.Qt.AscendingOrder)
        view.setAlternatingRowColors(True)

        # Set view delegates
        time_delegate = VersionDelegate()
        column = model.COLUMNS.index("version")
        view.setItemDelegateForColumn(column, time_delegate)

        version_delegate = PrettyTimeDelegate()
        column = model.COLUMNS.index("time")
        view.setItemDelegateForColumn(column, version_delegate)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(view)

        self.data = {
            "delegates": {
                "version": version_delegate,
                "time": time_delegate
            }
        }
        self.model = model
        self.view = view

        view.customContextMenuRequested.connect(self.on_context_menu)

        selection = view.selectionModel()
        selection.selectionChanged.connect(self.active_changed)

    def on_context_menu(self, point):

        point_index = self.view.indexAt(point)
        if not point_index.isValid():
            return

        # Get all representation->loader combinations available for the
        # index under the cursor, so we can list the user the options.
        loaders = list()
        node = point_index.data(self.model.NodeRole)
        version_id = node['version_document']['_id']
        for representation in _get_representations(version_id):
            for loader in lib.iter_loaders(representation["_id"]):
                loaders.append((representation, loader))

        if not loaders:
            # no loaders available
            self.echo("No compatible loaders available for this version.")
            return

        # List the available loaders
        menu = QtWidgets.QMenu(self)
        for representation, loader in loaders:

            # Label
            label = getattr(loader, "label", None)
            if label is None:
                label = loader.__name__

            # Add the representation as suffix
            label = "{0} ({1})".format(label, representation['name'])

            action = QtWidgets.QAction(label, menu)
            action.setData((representation, loader))
            menu.addAction(action)

        # Show the context action menu
        global_point = self.view.mapToGlobal(point)
        action = menu.exec_(global_point)
        if not action:
            return

        # Find the representation name and loader to trigger
        action_representation, loader = action.data()
        representation_name = action_representation['name']  # extension

        # Run the loader for all selected indices, for those that have the
        # same representation available
        selection = self.view.selectionModel()
        rows = selection.selectedRows()

        # Ensure point index is run first.
        try:
            rows.remove(point_index)
        except ValueError:
            pass
        rows.insert(0, point_index)

        # Trigger
        for row in rows:
            node = row.data(self.model.NodeRole)
            version_id = node['version_document']['_id']
            representation = io.find_one({"type": "representation",
                                          "name": representation_name,
                                          "parent": version_id})
            if not representation:
                self.echo("Subset '{}' has no representation '{}'".format(
                        node['subset'],
                        representation_name
                ))
                continue

            # If the representation can be
            context = lib.get_representation_context(representation["_id"])
            if not lib.is_compatible_loader(loader, context):
                self.echo("Loader not compatible with '{}'".format(
                        node['subset']
                ))
                continue

            lib.run_loader(loader, representation['_id'])

    def echo(self, message):
        print(message)


class VersionWidget(QtWidgets.QWidget):
    """A Widget that display information about a specific version"""
    def __init__(self, parent=None):
        super(VersionWidget, self).__init__(parent=parent)

        layout = QtWidgets.QVBoxLayout(self)

        label = QtWidgets.QLabel("Version")
        data = QtWidgets.QTextEdit()
        data.setReadOnly(True)
        layout.addWidget(label)
        layout.addWidget(data)

        self.data = data

        # initialize to empty state
        self.set_version(None)

    def set_version(self, version_id):
        if version_id:
            version = io.find_one({"_id": version_id, "type": "version"})
            assert version, "Not a valid version id"

            subset = io.find_one({"_id": version['parent'], "type": "subset"})
            assert subset, "No valid subset parent for version"

            # Define readable creation timestamp
            created = version["data"]["time"]
            created = datetime.datetime.strptime(created, "%Y%m%dT%H%M%SZ")
            created = datetime.datetime.strftime(created, "%b %d %Y %I:%M%p")

            comment = version['data'].get("comment", None) or "No comment"

            # Format raw source to source with current {root}
            raw_source = version['data'].get("source", "")
            if raw_source:
                source = raw_source.format(root=api.registered_root())
            else:
                source = raw_source

            data = {
                "subset": subset['name'],
                "version": version['name'],
                "comment": comment,
                "created": created,
                "source": source,
                "raw_source": raw_source
            }

            self.data.setHtml("""
<h3>{subset} v{version:03d}</h3>
<b>Comment</b><br>
{comment}<br>
<br>
<b>Created</b><br>
{created}<br>
<br>
<b>Source</b><br>
{source}<br>
<br>
<b>Raw Source</b><br>
{raw_source}<br>""".format(**data))
        else:
            self.data.setText("")
