import os
import sys
import logging
import collections
from functools import partial
import re

from ...vendor.Qt import QtWidgets, QtCore
from ...vendor import qtawesome
from ... import io, api, style
from ...lib import MasterVersionType

from .. import lib as tools_lib
from ..delegates import VersionDelegate

from .proxy import FilterProxyModel
from .model import InventoryModel
from .lib import switch_item

DEFAULT_COLOR = "#fb9c15"

module = sys.modules[__name__]
module.window = None


class View(QtWidgets.QTreeView):
    data_changed = QtCore.Signal()
    hierarchy_view = QtCore.Signal(bool)

    def __init__(self, parent=None):
        super(View, self).__init__(parent=parent)

        # view settings
        self.setIndentation(12)
        self.setAlternatingRowColors(True)
        self.setSortingEnabled(True)
        self.setSelectionMode(self.ExtendedSelection)
        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_right_mouse_menu)
        self._hierarchy_view = False
        self._selected = None

    def enter_hierarchy(self, items):
        self._selected = set(i["objectName"] for i in items)
        self._hierarchy_view = True
        self.hierarchy_view.emit(True)
        self.data_changed.emit()
        self.expandToDepth(1)
        self.setStyleSheet("""
        QTreeView {
             border-color: #fb9c15;
        }
        """)

    def leave_hierarchy(self):
        self._hierarchy_view = False
        self.hierarchy_view.emit(False)
        self.data_changed.emit()
        self.setStyleSheet("QTreeView {}")

    def build_item_menu_for_selection(self, items, menu):
        if not items:
            return

        repre_ids = []
        for item in items:
            item_id = io.ObjectId(item["representation"])
            if item_id not in repre_ids:
                repre_ids.append(item_id)

        repre_entities = io.find({
            "type": "representation",
            "_id": {"$in": repre_ids}
        })

        parent_ids = []
        for repre in repre_entities:
            parent_id = repre["parent"]
            if parent_id not in parent_ids:
                parent_ids.append(parent_id)

        loaded_versions = io.find({
            "_id": {"$in": parent_ids},
            "type": {"$in": ["version", "master_version"]}
        })

        loaded_master_versions = []
        versions_by_parent_id = collections.defaultdict(list)
        version_parents = []
        for version in loaded_versions:
            if version["type"] == "master_version":
                loaded_master_versions.append(version)
            else:
                parent_id = version["parent"]
                versions_by_parent_id[parent_id].append(version)
                if parent_id not in version_parents:
                    version_parents.append(parent_id)

        all_versions = io.find({
            "type": {"$in": ["master_version", "version"]},
            "parent": {"$in": version_parents}
        })
        master_versions = []
        versions = []
        for version in all_versions:
            if version["type"] == "master_version":
                master_versions.append(version)
            else:
                versions.append(version)

        has_loaded_master_versions = len(loaded_master_versions) > 0
        has_available_master_version = len(master_versions) > 0
        has_outdated = False

        for version in versions:
            parent_id = version["parent"]
            current_versions = versions_by_parent_id[parent_id]
            for current_version in current_versions:
                if current_version["name"] < version["name"]:
                    has_outdated = True
                    break

            if has_outdated:
                break

        updatetolatest_action = None
        if has_outdated or has_loaded_master_versions:
            # update to latest version
            def _on_update_to_latest(items):
                for item in items:
                    api.update(item, -1)
                self.data_changed.emit()

            update_icon = qtawesome.icon(
                "fa.angle-double-up",
                color=DEFAULT_COLOR
            )
            updatetolatest_action = QtWidgets.QAction(
                update_icon,
                "Update to latest",
                menu
            )
            updatetolatest_action.triggered.connect(
                lambda: _on_update_to_latest(items)
            )

        change_to_master = None
        if has_available_master_version:
            # change to master version
            def _on_update_to_master(items):
                for item in items:
                    api.update(item, MasterVersionType(-1))
                self.data_changed.emit()

            # TODO change icon
            change_icon = qtawesome.icon(
                "fa.asterisk",
                color="#00b359"
            )
            change_to_master = QtWidgets.QAction(
                change_icon,
                "Change to Master",
                menu
            )
            change_to_master.triggered.connect(
                lambda: _on_update_to_master(items)
            )

        # set version
        set_version_icon = qtawesome.icon("fa.hashtag", color=DEFAULT_COLOR)
        set_version_action = QtWidgets.QAction(
            set_version_icon,
            "Set version",
            menu
        )
        set_version_action.triggered.connect(
            lambda: self.show_version_dialog(items))

        # switch asset
        switch_asset_icon = qtawesome.icon("fa.sitemap", color=DEFAULT_COLOR)
        switch_asset_action = QtWidgets.QAction(
            switch_asset_icon,
            "Switch Asset",
            menu
        )
        switch_asset_action.triggered.connect(
            lambda: self.show_switch_dialog(items))

        # remove
        remove_icon = qtawesome.icon("fa.remove", color=DEFAULT_COLOR)
        remove_action = QtWidgets.QAction(remove_icon, "Remove items", menu)
        remove_action.triggered.connect(
            lambda: self.show_remove_warning_dialog(items))

        # add the actions
        if updatetolatest_action:
            menu.addAction(updatetolatest_action)

        if change_to_master:
            menu.addAction(change_to_master)

        menu.addAction(set_version_action)
        menu.addAction(switch_asset_action)

        menu.addSeparator()

        menu.addAction(remove_action)

        menu.addSeparator()

    def build_item_menu(self, items):
        """Create menu for the selected items"""

        menu = QtWidgets.QMenu(self)

        # add the actions
        self.build_item_menu_for_selection(items, menu)

        # These two actions should be able to work without selection
        # expand all items
        expandall_action = QtWidgets.QAction(menu, text="Expand all items")
        expandall_action.triggered.connect(self.expandAll)

        # collapse all items
        collapse_action = QtWidgets.QAction(menu, text="Collapse all items")
        collapse_action.triggered.connect(self.collapseAll)

        menu.addAction(expandall_action)
        menu.addAction(collapse_action)

        custom_actions = self.get_custom_actions(containers=items)
        if custom_actions:
            submenu = QtWidgets.QMenu("Actions", self)
            for action in custom_actions:

                color = action.color or DEFAULT_COLOR
                icon = qtawesome.icon("fa.%s" % action.icon, color=color)
                action_item = QtWidgets.QAction(icon, action.label, submenu)
                action_item.triggered.connect(
                    partial(self.process_custom_action, action, items))

                submenu.addAction(action_item)

            menu.addMenu(submenu)

        # go back to flat view
        if self._hierarchy_view:
            back_to_flat_icon = qtawesome.icon("fa.list", color=DEFAULT_COLOR)
            back_to_flat_action = QtWidgets.QAction(
                back_to_flat_icon,
                "Back to Full-View",
                menu
            )
            back_to_flat_action.triggered.connect(self.leave_hierarchy)

        # send items to hierarchy view
        enter_hierarchy_icon = qtawesome.icon("fa.indent", color="#d8d8d8")
        enter_hierarchy_action = QtWidgets.QAction(
            enter_hierarchy_icon,
            "Cherry-Pick (Hierarchy)",
            menu
        )
        enter_hierarchy_action.triggered.connect(
            lambda: self.enter_hierarchy(items))

        if items:
            menu.addAction(enter_hierarchy_action)

        if self._hierarchy_view:
            menu.addAction(back_to_flat_action)

        return menu

    def get_custom_actions(self, containers):
        """Get the registered Inventory Actions

        Args:
            containers(list): collection of containers

        Returns:
            list: collection of filter and initialized actions
        """

        def sorter(Plugin):
            """Sort based on order attribute of the plugin"""
            return Plugin.order

        # Fedd an empty dict if no selection, this will ensure the compat
        # lookup always work, so plugin can interact with Scene Inventory
        # reversely.
        containers = containers or [dict()]

        # Check which action will be available in the menu
        Plugins = api.discover(api.InventoryAction)
        compatible = [p() for p in Plugins if
                      any(p.is_compatible(c) for c in containers)]

        return sorted(compatible, key=sorter)

    def process_custom_action(self, action, containers):
        """Run action and if results are returned positive update the view

        If the result is list or dict, will select view items by the result.

        Args:
            action (InventoryAction): Inventory Action instance
            containers (list): Data of currently selected items

        Returns:
            None
        """

        result = action.process(containers)
        if result:
            self.data_changed.emit()

            if isinstance(result, (list, set)):
                self.select_items_by_action(result)

            if isinstance(result, dict):
                self.select_items_by_action(result["objectNames"],
                                            result["options"])

    def select_items_by_action(self, object_names, options=None):
        """Select view items by the result of action

        Args:
            object_names (list or set): A list/set of container object name
            options (dict): GUI operation options.

        Returns:
            None

        """
        options = options or dict()

        if options.get("clear", True):
            self.clearSelection()

        object_names = set(object_names)
        if (self._hierarchy_view and
                not self._selected.issuperset(object_names)):
            # If any container not in current cherry-picked view, update
            # view before selecting them.
            self._selected.update(object_names)
            self.data_changed.emit()

        model = self.model()
        selection_model = self.selectionModel()

        select_mode = {
            "select": selection_model.Select,
            "deselect": selection_model.Deselect,
            "toggle": selection_model.Toggle,
        }[options.get("mode", "select")]

        for item in tools_lib.iter_model_rows(model, 0):
            item = item.data(InventoryModel.ItemRole)
            if item.get("isGroupNode"):
                continue

            name = item.get("objectName")
            if name in object_names:
                self.scrollTo(item)  # Ensure item is visible
                selection_model.select(item, select_mode)
                object_names.remove(name)

            if len(object_names) == 0:
                break

    def show_right_mouse_menu(self, pos):
        """Display the menu when at the position of the item clicked"""

        globalpos = self.viewport().mapToGlobal(pos)

        if not self.selectionModel().hasSelection():
            print("No selection")
            # Build menu without selection, feed an empty list
            menu = self.build_item_menu([])
            menu.exec_(globalpos)
            return

        active = self.currentIndex()  # index under mouse
        active = active.sibling(active.row(), 0)  # get first column

        # move index under mouse
        indices = self.get_indices()
        if active in indices:
            indices.remove(active)

        indices.append(active)

        # Extend to the sub-items
        all_indices = self.extend_to_children(indices)
        items = [dict(i.data(InventoryModel.ItemRole)) for i in all_indices
                 if i.parent().isValid()]

        if self._hierarchy_view:
            # Ensure no group item
            items = [n for n in items if not n.get("isGroupNode")]

        menu = self.build_item_menu(items)
        menu.exec_(globalpos)

    def get_indices(self):
        """Get the selected rows"""
        selection_model = self.selectionModel()
        return selection_model.selectedRows()

    def extend_to_children(self, indices):
        """Extend the indices to the children indices.

        Top-level indices are extended to its children indices. Sub-items
        are kept as is.

        Args:
            indices (list): The indices to extend.

        Returns:
            list: The children indices

        """
        def get_children(i):
            model = i.model()
            rows = model.rowCount(parent=i)
            for row in range(rows):
                child = model.index(row, 0, parent=i)
                yield child

        subitems = set()
        for i in indices:
            valid_parent = i.parent().isValid()
            if valid_parent and i not in subitems:
                subitems.add(i)

                if self._hierarchy_view:
                    # Assume this is a group item
                    for child in get_children(i):
                        subitems.add(child)
            else:
                # is top level item
                for child in get_children(i):
                    subitems.add(child)

        return list(subitems)

    def show_version_dialog(self, items):
        """Create a dialog with the available versions for the selected file

        Args:
            items (list): list of items to run the "set_version" for

        Returns:
            None
        """

        active = items[-1]

        # Get available versions for active representation
        representation_id = io.ObjectId(active["representation"])
        representation = io.find_one({"_id": representation_id})
        version = io.find_one({
            "_id": representation["parent"]
        })

        versions = list(io.find(
            {
                "parent": version["parent"],
                "type": "version"
            },
            sort=[("name", 1)]
        ))

        master_version = io.find_one({
            "parent": version["parent"],
            "type": "master_version"
        })
        if master_version:
            _version_id = master_version["version_id"]
            for _version in versions:
                if _version["_id"] != _version_id:
                    continue

                master_version["name"] = MasterVersionType(
                    _version["name"]
                )
                master_version["data"] = _version["data"]
                break

        # Get index among the listed versions
        current_item = None
        current_version = active["version"]
        if isinstance(current_version, MasterVersionType):
            current_item = master_version
        else:
            for version in versions:
                if version["name"] == current_version:
                    current_item = version
                    break

        all_versions = []
        if master_version:
            all_versions.append(master_version)
        all_versions.extend(reversed(versions))

        if current_item:
            index = all_versions.index(current_item)
        else:
            index = 0

        versions_by_label = dict()
        labels = []
        for version in all_versions:
            is_master = version["type"] == "master_version"
            label = tools_lib.format_version(version["name"], is_master)
            labels.append(label)
            versions_by_label[label] = version["name"]

        label, state = QtWidgets.QInputDialog.getItem(
            self,
            "Set version..",
            "Set version number to",
            labels,
            current=index,
            editable=False
        )
        if not state:
            return

        if label:
            version = versions_by_label[label]
            for item in items:
                api.update(item, version)
            # refresh model when done
            self.data_changed.emit()

    def show_switch_dialog(self, items):
        """Display Switch dialog"""
        dialog = SwitchAssetDialog(self, items)
        dialog.switched.connect(self.data_changed.emit)
        dialog.show()

    def show_remove_warning_dialog(self, items):
        """Prompt a dialog to inform the user the action will remove items"""

        accept = QtWidgets.QMessageBox.Ok
        buttons = accept | QtWidgets.QMessageBox.Cancel

        message = ("Are you sure you want to remove "
                   "{} item(s)".format(len(items)))
        state = QtWidgets.QMessageBox.question(self, "Are you sure?",
                                               message,
                                               buttons=buttons,
                                               defaultButton=accept)

        if state != accept:
            return

        for item in items:
            api.remove(item)
        self.data_changed.emit()


class SearchComboBox(QtWidgets.QComboBox):
    """Searchable ComboBox with empty placeholder value as first value"""

    def __init__(self, parent=None, placeholder=""):
        super(SearchComboBox, self).__init__(parent)

        self.setEditable(True)
        self.setInsertPolicy(self.NoInsert)
        self.lineEdit().setPlaceholderText(placeholder)

        # Apply completer settings
        completer = self.completer()
        completer.setCompletionMode(completer.PopupCompletion)
        completer.setCaseSensitivity(QtCore.Qt.CaseInsensitive)

        # Force style sheet on popup menu
        # It won't take the parent stylesheet for some reason
        # todo: better fix for completer popup stylesheet
        if module.window:
            popup = completer.popup()
            popup.setStyleSheet(module.window.styleSheet())

    def populate(self, items):
        self.clear()
        self.addItems([""])     # ensure first item is placeholder
        self.addItems(items)

    def get_valid_value(self):
        """Return the current text if it's a valid value else None

        Note: The empty placeholder value is valid and returns as ""

        """

        text = self.currentText()
        lookup = set(self.itemText(i) for i in range(self.count()))
        if text not in lookup:
            return None

        return text


class SwitchAssetDialog(QtWidgets.QDialog):
    """Widget to support asset switching"""

    MIN_WIDTH = 550

    fill_check = False
    initialized = False
    switched = QtCore.Signal()

    is_lod = False
    LOD_REGEX = re.compile(r"_(LOD\d+)")
    LOD_MARK = "(LODs)"
    LOD_SPLITTER = "_"
    LOD_NOT_LOD = "< without LOD >"

    def __init__(self, parent=None, items=None):
        QtWidgets.QDialog.__init__(self, parent)

        self.setModal(True)  # Force and keep focus dialog

        self.log = logging.getLogger(self.__class__.__name__)

        self._items = items

        self._assets_box = SearchComboBox(placeholder="<asset>")
        self._subsets_box = SearchComboBox(placeholder="<subset>")
        self._lods_box = SearchComboBox(placeholder="<lod>")
        self._representations_box = SearchComboBox(
            placeholder="<representation>"
        )

        self._asset_label = QtWidgets.QLabel("")
        self._subset_label = QtWidgets.QLabel("")
        self._lod_label = QtWidgets.QLabel("")
        self._repre_label = QtWidgets.QLabel("")

        main_layout = QtWidgets.QVBoxLayout()
        context_layout = QtWidgets.QHBoxLayout()
        asset_layout = QtWidgets.QVBoxLayout()
        subset_layout = QtWidgets.QVBoxLayout()
        lod_layout = QtWidgets.QVBoxLayout()
        repre_layout = QtWidgets.QVBoxLayout()

        accept_icon = qtawesome.icon("fa.check", color="white")
        accept_btn = QtWidgets.QPushButton()
        accept_btn.setIcon(accept_icon)
        accept_btn.setFixedWidth(24)
        accept_btn.setFixedHeight(24)

        asset_layout.addWidget(self._assets_box)
        asset_layout.addWidget(self._asset_label)
        subset_layout.addWidget(self._subsets_box)
        subset_layout.addWidget(self._subset_label)
        lod_layout.addWidget(self._lods_box)
        lod_layout.addWidget(self._lod_label)
        repre_layout.addWidget(self._representations_box)
        repre_layout.addWidget(self._repre_label)

        context_layout.addLayout(asset_layout)
        context_layout.addLayout(subset_layout)
        context_layout.addLayout(lod_layout)
        context_layout.addLayout(repre_layout)
        context_layout.addWidget(accept_btn)

        self._accept_btn = accept_btn

        self._assets_box.currentIndexChanged.connect(self.on_assets_change)
        self._subsets_box.currentIndexChanged.connect(self.on_subset_change)
        self._lods_box.currentIndexChanged.connect(self.on_lod_change)
        self._representations_box.currentIndexChanged.connect(
            self.on_repre_change
        )

        main_layout.addLayout(context_layout)
        self.setLayout(main_layout)
        self.setWindowTitle("Switch selected items ...")

        self.connections()

        self.refresh(0)

        self.setMinimumWidth(self.MIN_WIDTH)

        # Set default focus to accept button so you don't directly type in
        # first asset field, this also allows to see the placeholder value.
        accept_btn.setFocus()
        self.fill_check = True
        self.initialized = True

    def connections(self):
        self._accept_btn.clicked.connect(self._on_accept)

    def on_assets_change(self):
        self.refresh(1)

    def on_subset_change(self):
        self.refresh(2)

    def on_lod_change(self):
        # if self.fill_check and self.initialized:
        self.refresh(3)

    def on_repre_change(self):
        # if self.fill_check and self.initialized:
        self.refresh(4)

    def refresh(self, refresh_type):
        """Build the need comboboxes with content"""
        if (not self.fill_check or not self.initialized) and refresh_type > 0:
            return

        if refresh_type < 1:
            assets = sorted(self._get_assets())
            self.fill_check = False
            self._assets_box.populate(assets)
            self.fill_check = True

        if refresh_type < 2:
            last_subset = self._subsets_box.currentText()

            self._compute_is_lod()
            subsets, gs = self._group_lods(sorted(self._get_subsets()))
            self.fill_check = False
            self._subsets_box.populate(subsets)
            self.fill_check = True

            if (last_subset != "" and last_subset in list(subsets)):
                index = None
                for i in range(self._subsets_box.count()):
                    if last_subset == str(self._subsets_box.itemText(i)):
                        index = i
                        break
                if index is not None:
                    self._subsets_box.setCurrentIndex(index)

        if refresh_type < 3:
            self._lods_box.setVisible(self.is_lod)
            self._lod_label.setVisible(self.is_lod)
            if self.is_lod:
                self._fill_lod_box()

        if refresh_type < 4:
            self._fill_representations_box()

        self.set_labels()
        self.validate()

    def _compute_is_lod(self):
        is_lod = True
        if self._assets_box.currentText() != "":
            asset = io.find_one({
                "type": "asset",
                "name": self._assets_box.currentText()
            })
            subsets = io.find({"parent": asset["_id"]})
            is_lod = False
            for subset in subsets:
                lod_regex_result = re.search(
                    self.LOD_REGEX, subset["name"]
                )
                # If had at least one LOD subset
                if lod_regex_result:
                    is_lod = True
                    break
        else:
            for item in self._items:
                if is_lod is False:
                    break
                _id = io.ObjectId(item["representation"])
                repre = io.find_one({"_id": _id})
                version = io.find_one({"_id": repre["parent"]})
                subset = io.find_one({"_id": version["parent"]})

                lod_regex_result = re.search(
                    self.LOD_REGEX, subset["name"]
                )
                if lod_regex_result:
                    continue

                if self._assets_box.currentText() == "":
                    parent = subset["parent"]
                else:
                    asset = io.find_one({
                        "type": "asset",
                        "name": self._assets_box.currentText()
                    })
                    parent = asset["_id"]
                # check if exists lod subset with same name
                lod_subsets = []
                for sub in io.find({"parent": parent}):
                    name = sub["name"]
                    lod_regex_result = re.search(self.LOD_REGEX, name)
                    if not lod_regex_result:
                        continue
                    if name.startswith(subset["name"]):
                        lod_subsets.append(name)
                if len(lod_subsets) == 0:
                    is_lod = False

        self.is_lod = is_lod

        return is_lod

    def _fill_representations_box(self):
        last_repre = self._representations_box.currentText()
        representations = sorted(self._get_representations())
        self.fill_check = False
        self._representations_box.populate(representations)

        if (last_repre != "" and last_repre in list(representations)):
            index = None
            for i in range(self._representations_box.count()):
                if last_repre == self._representations_box.itemText(i):
                    index = i
                    break
            if index is not None:
                self._representations_box.setCurrentIndex(index)
        self.fill_check = True

    def _fill_lod_box(self):
        asset_text = self._assets_box.currentText()
        subset_text = self._subsets_box.currentText()
        last_lod = self._lods_box.currentText()

        if subset_text != "":
            is_lod = self.LOD_MARK in subset_text
            # self.is_lod = is_lod
            self._lods_box.setVisible(is_lod)
            self._lod_label.setVisible(is_lod)
            if not is_lod:
                lods = []
                lods.append(self.LOD_NOT_LOD)
                self.fill_check = False
                self._lods_box.populate(list(lods))
                self._lods_box.setCurrentIndex(0)
                self.fill_check = True
                return

        lods = set()
        if asset_text != "" and subset_text != "":
            subset_part = subset_text.replace(self.LOD_MARK, "")
            asset = io.find_one({
                "type": "asset",
                "name": asset_text
            })
            subsets = io.find({
                "type": "subset",
                "parent": asset["_id"]
            })
            for subset in subsets:
                if not subset["name"].startswith(subset_part):
                    continue
                lod_regex_result = re.search(self.LOD_REGEX, subset["name"])
                if lod_regex_result:
                    lod = lod_regex_result.group(0).replace(
                        self.LOD_SPLITTER, ""
                    )
                else:
                    lod = self.LOD_NOT_LOD
                lods.add(lod)

        elif asset_text != "":
            asset = io.find_one({
                "type": "asset",
                "name": asset_text
            })
            subsets = io.find({
                "type": "subset",
                "parent": asset["_id"]
            })
            subset_names, groups = self._group_lods(
                sorted(subsets.distinct("name"))
            )
            is_lod = True
            for name in subset_names:
                if self.LOD_MARK not in name:
                    is_lod = False
                    break

            self._lods_box.setVisible(is_lod)
            self._lod_label.setVisible(is_lod)
            if not is_lod:
                lods = []
                lods.append(self.LOD_NOT_LOD)
                self.fill_check = False
                self._lods_box.populate(lods)
                self._lods_box.setCurrentIndex(0)
                self.fill_check = True
                return
            for _lods in groups.values():
                sub_lods = set()
                for lod in _lods:
                    sub_lods.add(lod)
                if lods:
                    lods = (lods & sub_lods)
                else:
                    lods = sub_lods

        else:
            subset_part = subset_text.replace(self.LOD_MARK, "")
            for item in self._items:
                item_lods = set()
                _id = io.ObjectId(item["representation"])
                representation = io.find_one({
                    "type": "representation",
                    "_id": _id
                })
                version, subset, asset, project = io.parenthood(representation)
                subsets = io.find({
                    "type": "subset",
                    "parent": asset["_id"]
                })
                for subset in subsets:
                    if not subset["name"].startswith(subset_part):
                        continue
                    lod_regex_result = re.search(self.LOD_REGEX, subset["name"])
                    if lod_regex_result:
                        lod = lod_regex_result.group(0).replace(
                            self.LOD_SPLITTER, ""
                        )
                    else:
                        lod = self.LOD_NOT_LOD
                    item_lods.add(lod)
                if lods:
                    lods = (lods & item_lods)
                else:
                    lods = item_lods

        lods = sorted(list(lods))
        self.fill_check = False
        # fill lods into combobox
        self._lods_box.populate(lods)
        # try select last LOD if was selected
        if last_lod != "":
            index = None
            for i in range(self._lods_box.count()):
                if last_lod == self._lods_box.itemText(i):
                    index = i
                    break
            if index is not None:
                self._lods_box.setCurrentIndex(index)
        self.fill_check = True

    def set_labels(self):
        default = "*No changes"
        asset_label = default
        subset_label = default
        lod_label = default
        repre_label = default

        if self._assets_box.currentText() != "":
            asset_label = self._assets_box.currentText()
        if self._subsets_box.currentText() != "":
            subset_label = self._subsets_box.currentText()
        if self._lods_box.currentText() != "":
            lod_label = self._lods_box.currentText()
        if self._representations_box.currentText() != "":
            repre_label = self._representations_box.currentText()

        self._asset_label.setText(asset_label)
        self._subset_label.setText(subset_label)
        self._lod_label.setText(lod_label)
        self._repre_label.setText(repre_label)

    def validate(self):
        _asset_name = self._assets_box.get_valid_value() or None
        _subset_name = self._subsets_box.get_valid_value() or None
        _lod_name = self._lods_box.get_valid_value() or None
        _repre_name = self._representations_box.get_valid_value() or None

        asset_ok = True
        subset_ok = True
        lod_ok = True
        repre_ok = True
        for item in self._items:
            _id = io.ObjectId(item["representation"])
            representation = io.find_one({
                "type": "representation",
                "_id": _id
            })
            ver, subset, asset, proj = io.parenthood(representation)

            asset_name = _asset_name
            subset_name = _subset_name
            lod_name = _lod_name
            repre_name = _repre_name

            if asset_name is None:
                asset_name = asset["name"]

            # asset check
            asset = io.find_one({
                "name": asset_name,
                "type": "asset"
            })

            if asset is None:
                asset_ok = False
                continue

            if repre_name is None:
                repre_name = representation["name"]

            if self.is_lod and self._lods_box.isVisible():
                subsets = io.find({
                    "type": "subset",
                    "parent": asset["_id"]
                })

                if subset_name is None and lod_name is None:
                    subset_name = subset["name"]
                    lod_regex_result = re.search(
                        self.LOD_REGEX, subset_name
                    )
                    subset = io.find_one({
                        "name": subset_name,
                        "type": "subset",
                        "parent": asset["_id"]
                    })
                    if not lod_regex_result:
                        subset_ok = False
                        continue
                    elif subset is None:
                        lod_part = lod_regex_result.group(1)
                        subset_part = subset_name.replace(
                            lod_regex_result.group(0), ""
                        )
                        _sub_ok = False
                        for subset in subsets:
                            if subset["name"].startswith(subset_part):
                                _sub_ok = True
                                break
                        if subset_ok:
                            subset_ok = _sub_ok
                        if lod_ok:
                            lod_ok = not _sub_ok
                        continue

                elif subset_name is None:
                    subset_name = subset["name"]
                    lod_regex_result = re.search(
                        self.LOD_REGEX, subset_name
                    )
                    if not lod_regex_result:
                        subset_ok = False
                        continue
                    subset_name = subset_name.replace(
                        lod_regex_result.group(0),
                        (self.LOD_SPLITTER + lod_name)
                    )
                    subset = io.find_one({
                        "name": subset_name,
                        "type": "subset",
                        "parent": asset["_id"]
                    })
                    if subset is None:
                        subset_ok = False
                        continue

                elif lod_name is None or lod_name == self.LOD_NOT_LOD:
                    orig_subset_name = subset["name"]
                    lod_regex_result = re.search(
                        self.LOD_REGEX, orig_subset_name
                    )
                    if not lod_regex_result:
                        lod_ok = False
                        continue
                    subset_name = subset_name.replace(self.LOD_MARK, "")
                    subset_name += (
                        lod_regex_result.group(0)
                    )
                    subset = io.find_one({
                        "name": subset_name,
                        "type": "subset",
                        "parent": asset["_id"]
                    })
                    if subset is None:
                        lod_ok = False
                        continue
                else:
                    orig_subset_name = subset["name"]
                    subset_name = subset_name.replace(self.LOD_MARK, "")
                    subset_name += self.LOD_SPLITTER + lod_name
                    subset = io.find_one({
                        "name": subset_name,
                        "type": "subset",
                        "parent": asset["_id"]
                    })

                    # This should never happen
                    if subset is None:
                        lod_regex_result = re.search(
                            self.LOD_REGEX, orig_subset_name
                        )
                        lod_part = lod_regex_result.group(1)
                        subset_part = subset_name.replace(
                            lod_regex_result.group(0), ""
                        )
                        _sub_ok = False
                        for subset in subsets:
                            if subset["name"].startswith(subset_part):
                                _sub_ok = True
                                break
                        if _sub_ok and self._lods_box.count() == 0:
                            _sub_ok = False
                        if subset_ok:
                            subset_ok = _sub_ok
                        if lod_ok:
                            lod_ok = not _sub_ok
                        continue

            else:
                if subset_name is None:
                    subset_name = subset["name"]
                    lod_regex_result = re.search(
                        self.LOD_REGEX, subset["name"]
                    )
                    if lod_regex_result and _asset_name is not None:
                        subset_name = subset_name.replace(
                            lod_regex_result.group(0), ""
                        )
                else:
                    lod_regex_result = re.search(
                        self.LOD_REGEX, subset["name"]
                    )
                    if lod_regex_result and _asset_name is None:
                        subset_name += lod_regex_result.group(0)

                subset = io.find_one({
                    "name": subset_name,
                    "type": "subset",
                    "parent": asset["_id"]
                })
                if subset is None:
                    subset_ok = False
                    continue

            version = io.find_one(
                {
                    "type": "version",
                    "parent": subset["_id"]
                },
                sort=[("name", -1)]
            )
            if version is None:
                repre_ok = False
                continue

            repre = io.find_one({
                "name": repre_name,
                "type": "representation",
                "parent": version["_id"]
            })
            if repre is None:
                repre_ok = False
                continue

        error_msg = "*Please select"
        error_sheet = "border: 1px solid red;"
        success_sheet = "border: 1px solid green;"
        asset_sheet = subset_sheet = repre_sheet = lod_sheet = ""
        accept_sheet = ""
        all_ok = asset_ok and subset_ok and lod_ok and repre_ok

        if asset_ok is False:
            asset_sheet = error_sheet
            self._asset_label.setText(error_msg)
        if subset_ok is False:
            subset_sheet = error_sheet
            self._subset_label.setText(error_msg)
        if lod_ok is False:
            lod_sheet = error_sheet
            self._lod_label.setText(error_msg)
        if repre_ok is False:
            repre_sheet = error_sheet
            self._repre_label.setText(error_msg)
        if all_ok:
            accept_sheet = success_sheet

        self._assets_box.setStyleSheet(asset_sheet)
        self._subsets_box.setStyleSheet(subset_sheet)
        self._lods_box.setStyleSheet(lod_sheet)
        self._representations_box.setStyleSheet(repre_sheet)

        self._accept_btn.setEnabled(all_ok)
        self._accept_btn.setStyleSheet(accept_sheet)

    def _get_assets(self):
        filtered_assets = []
        for asset in io.find({"type": "asset"}):
            subsets = io.find({
                "type": "subset",
                "parent": asset["_id"]
            })
            for subs in subsets:
                filtered_assets.append(asset["name"])
                break

        return filtered_assets

    def _get_subsets(self):
        # Filter subsets by asset in dropdown
        if self._assets_box.currentText() != "":
            parents = list()
            parents.append(io.find_one({
                "type": "asset",
                "name": self._assets_box.currentText()
            }))

            return self._get_document_names("subset", parents)
        # If any asset in dropdown is selected
        # - filter subsets by selected assets in scene inventory
        assets = []
        for item in self._items:
            _id = io.ObjectId(item["representation"])
            representation = io.find_one(
                {"type": "representation", "_id": _id}
            )
            version, subset, asset, project = io.parenthood(representation)
            assets.append(asset)

        possible_subsets = set()
        for asset in assets:
            subsets = io.find({
                "type": "subset",
                "parent": asset["_id"]
            })
            asset_subsets = set()
            for subset in subsets:
                subset_name = subset["name"]
                lod_regex_result = re.search(self.LOD_REGEX, subset_name)
                if not self.is_lod and lod_regex_result:
                    subset_name = subset_name.replace(
                        lod_regex_result.group(0), ""
                    )
                asset_subsets.add(subset_name)
            if possible_subsets:
                possible_subsets = (possible_subsets & asset_subsets)
            else:
                possible_subsets = asset_subsets

        return list(possible_subsets)

    def _group_lods(self, subsets):
        """
        Group subset names if they contains ``_LODx`` string in list under
        dict key with the name of group.

        Example::
            ``["A_LOD1", "A_LOD2", "B_LOD1", "B_LOD2", "C"]``
            will became:
            ``
            {
                "A(LODs)": ["LOD1", "LOD2"],
                "B(LODs)": ["LOD1", "LOD2"]
            }

        :param subsets: List of subset names
        :param type: list
        :returns: dict of groups and list of all subset with group names
        :rtype: dict, list
        """
        groups = collections.defaultdict(list)
        subsets_out = []
        for subset in subsets:
            lod_regex_result = re.search(self.LOD_REGEX, subset)
            if lod_regex_result:
                # strip _LOD string from subset name
                grp_name = re.search("(.*){}".format(
                    lod_regex_result.group(0)), subset
                )
                # This formatting can't be changed!!!
                #  - replacing on accept won't work (LOD_MARK is replaced)
                key_name = "{}{}".format(grp_name.group(1), self.LOD_MARK)
                # store only "LOD*number*"
                groups[key_name].append(
                    lod_regex_result.group(1).replace("_", "")
                )
                if key_name not in subsets_out:
                    subsets_out.append(key_name)
            elif subset not in subsets_out:
                subsets_out.append(subset)

        return subsets_out, groups

    def _get_representations(self):
        output_repres = set()
        # If nothing is selected
        if (
            self._assets_box.currentText() == "" and
            self._subsets_box.currentText() == "" and
            (
                self.is_lod is False or
                self._lods_box.currentText() == ""
            )
        ):
            for item in self._items:
                _id = io.ObjectId(item["representation"])
                representation = io.find_one({
                    "type": "representation",
                    "_id": _id
                })
                repres = io.find({
                    "type": "representation",
                    "parent": representation["parent"]
                })
                merge_repres = set()
                for repre in repres:
                    merge_repres.add(repre["name"])
                if output_repres:
                    output_repres = (output_repres & merge_repres)
                else:
                    output_repres = merge_repres

        # If everything is selected
        elif(
            self._assets_box.currentText() != "" and
            self._subsets_box.currentText() != "" and
            (
                self.is_lod is False or
                self._lods_box.currentText() != ""
            )
        ):
            asset = io.find_one({
                "type": "asset",
                "name": self._assets_box.currentText()
            })
            # subset
            subset_name = self._subsets_box.currentText()
            if self.is_lod:
                subset_name = subset_name.replace(self.LOD_MARK, "")
                lod_name = self._lods_box.currentText()
                if lod_name != self.LOD_NOT_LOD:
                    subset_name += (
                        self.LOD_SPLITTER + self._lods_box.currentText()
                    )
            subset = io.find_one({
                "type": "subset",
                "parent": asset["_id"],
                "name": subset_name
            })
            # versions
            versions = io.find({
                "type": "version",
                "parent": subset["_id"]
            }, sort=[("name", 1)])
            versions = [version for version in versions]
            if len(versions) == 0:
                return list(output_repres)
            # representations
            repres = io.find({
                "type": "representation",
                "parent": versions[-1]["_id"]
            })
            output_repres = [repre["name"] for repre in repres]

        # Rest of If asset is selected
        elif(
            self._assets_box.currentText() != ""
        ):
            # if is LOD and (subset or lod) are selected
            asset = io.find_one({
                "type": "asset",
                "name": self._assets_box.currentText()
            })
            subsets = io.find({
                "type": "subset",
                "parent": asset["_id"]
            })

            possible_subsets = []
            if (
                self.is_lod and (
                    self._subsets_box.currentText() != "" or
                    self._lods_box.currentText() != ""
                )
            ):
                if self._subsets_box.currentText() != "":
                    subset_name = self._subsets_box.currentText()
                    subset_name = subset_name.replace(self.LOD_MARK, "")
                    for subset in subsets:
                        if subset["name"].startswith(subset_name):
                            possible_subsets.append(subset)
                else:
                    lod_name = self._lods_box.currentText()
                    if lod_name == self.LOD_NOT_LOD:
                        for subset in subsets:
                            lod_regex_result = re.search(
                                self.LOD_REGEX, subset["name"]
                            )
                            if lod_regex_result:
                                continue
                            possible_subsets.append(subset)
                    else:
                        for subset in subsets:
                            if subset["name"].endswith(lod_name):
                                possible_subsets.append(subset)
            # if only asset is selected
            else:
                possible_subsets = subsets
            # versions
            versions = []
            for subset in possible_subsets:
                _versions = io.find({
                    "type": "version",
                    "parent": subset["_id"]
                }, sort=[("name", 1)])
                _versions = [version for version in _versions]
                if len(_versions) == 0:
                    continue
                versions.append(_versions[-1])
            if len(versions) == 0:
                return list(output_repres)
            # representations
            for version in versions:
                repres = io.find({
                    "type": "representation",
                    "parent": version["_id"]
                }).distinct("name")
                repre_names = set(repres)
                if output_repres:
                    output_repres = (output_repres & repre_names)
                else:
                    output_repres = repre_names

        # if asset is not selected and lod is selected
        elif self.is_lod and self._lods_box.currentText() != "":
            lod_name = self._lods_box.currentText()
            for item in self._items:
                _id = io.ObjectId(item["representation"])
                representation = io.find_one({
                    "type": "representation",
                    "_id": _id
                })
                ver, subs, asset, proj = io.parenthood(representation)
                subset_name = self._strip_lod(subs["name"])
                if lod_name != self.LOD_NOT_LOD:
                    subset_name = self.LOD_SPLITTER.join(
                        [subset_name, lod_name]
                    )

                subsets = io.find({
                    "type": "subset",
                    "parent": asset["_id"],
                    "name": subset_name
                })

                versions = []
                for subset in subsets:
                    _versions = io.find({
                        "type": "version",
                        "parent": subset["_id"]
                    }, sort=[("name", 1)])
                    _versions = [version for version in _versions]
                    if len(_versions) == 0:
                        continue
                    versions.append(_versions[-1])

                if len(versions) == 0:
                    return list(output_repres)

                for version in versions:
                    repres = io.find({
                        "type": "representation",
                        "parent": version["_id"]
                    }).distinct("name")
                    repre_names = set(repres)
                    if output_repres:
                        output_repres = (output_repres & repre_names)
                    else:
                        output_repres = repre_names

        # if asset is not selected
        else:
            subset_text = self._subsets_box.currentText()
            if self.is_lod:
                subset_text = subset_text.replace(self.LOD_MARK, "")

            for item in self._items:
                _id = io.ObjectId(item["representation"])
                representation = io.find_one({
                    "type": "representation",
                    "_id": _id
                })
                ver, subs, asset, proj = io.parenthood(representation)

                subset_name = subset_text
                lod_regex_result = re.search(self.LOD_REGEX, subs["name"])
                if lod_regex_result:
                    subset_name += lod_regex_result.group(0)
                # should find only one subset
                subsets = io.find({
                    "type": "subset",
                    "parent": asset["_id"],
                    "name": subset_name
                })
                versions = []
                for subset in subsets:
                    _versions = io.find({
                        "type": "version",
                        "parent": subset["_id"]
                    }, sort=[("name", 1)])
                    _versions = [version for version in _versions]
                    if len(_versions) == 0:
                        continue
                    versions.append(_versions[-1])

                if len(versions) == 0:
                    return list(output_repres)

                for version in versions:
                    repres = io.find({
                        "type": "representation",
                        "parent": version["_id"]
                    }).distinct("name")
                    repre_names = set(repres)
                    if output_repres:
                        output_repres = (output_repres & repre_names)
                    else:
                        output_repres = repre_names

        return list(output_repres)

    def _get_document_names(self, document_type, parents=[]):

        query = {"type": document_type}

        if len(parents) == 1:
            query["parent"] = parents[0]["_id"]
        elif len(parents) > 1:
            or_exprs = []
            for parent in parents:
                expr = {"parent": parent["_id"]}
                or_exprs.append(expr)

            query["$or"] = or_exprs

        return io.find(query).distinct("name")

    def _on_accept(self):

        # Use None when not a valid value or when placeholder value
        _asset = self._assets_box.get_valid_value() or None
        _subset = self._subsets_box.get_valid_value() or None
        _lod = self._lods_box.get_valid_value() or None
        _representation = self._representations_box.get_valid_value() or None

        if self.is_lod:
            if not any([_asset, _subset, _lod, _representation]):
                self.log.error("Nothing selected")
                return

            for item in self._items:
                _asset_name = _asset
                _subset_name = _subset
                _lod_name = _lod
                _representation_name = _representation

                _id = io.ObjectId(item["representation"])
                representation = io.find_one({
                    "type": "representation",
                    "_id": _id
                })
                version, subset, asset, project = io.parenthood(representation)

                if _subset_name is not None and _lod_name is not None:
                    _subset_name = self.LOD_SPLITTER.join([
                        _subset_name.replace(self.LOD_MARK, ""),
                        _lod_name
                    ])
                elif _subset_name is not None and self._lods_box.isVisible():
                    subset_name = subset["name"]
                    lod_regex_result = re.search(self.LOD_REGEX, subset_name)
                    _lod_name = lod_regex_result.group(0)
                    _subset_name = self.LOD_SPLITTER.join([
                        _subset_name, _lod_name
                    ])

                elif _lod_name is not None:
                    subset_name = subset["name"]
                    lod_regex_result = re.search(self.LOD_REGEX, subset_name)
                    if lod_regex_result:
                        subset_name = subset_name.replace(
                            lod_regex_result.group(0), ""
                        )
                    _subset_name = self.LOD_SPLITTER.join([
                        subset_name, _lod_name
                    ])

                try:
                    switch_item(
                        item,
                        asset_name=_asset_name,
                        subset_name=_subset_name,
                        representation_name=_representation_name
                    )
                except Exception as e:
                    self.log.warning(e)
        else:
            if not any([_asset, _subset, _representation]):
                self.log.error("Nothing selected")
                return

            for item in self._items:
                _asset_name = _asset
                _subset_name = _subset
                _representation_name = _representation

                _id = io.ObjectId(item["representation"])
                representation = io.find_one({
                    "type": "representation",
                    "_id": _id
                })
                version, subset, asset, project = io.parenthood(representation)
                if _subset_name is not None and _asset_name is None:
                    lod_regex_result = re.search(
                        self.LOD_REGEX, subset["name"]
                    )
                    if lod_regex_result:
                        lod = lod_regex_result.group(0)
                        _subset_name += lod

                try:
                    switch_item(
                        item,
                        asset_name=_asset_name,
                        subset_name=_subset_name,
                        representation_name=_representation_name
                    )
                except Exception as e:
                    self.log.warning(e)

        self.switched.emit()

        self.close()

    def _strip_lod(self, subset):
        """
        Strip _LODx string from subset name or return subset name unmodified.
        :param subset: subset name
        :type subset: str
        :returns: subset name
        :rtype: str
        """
        m = re.search(self.LOD_REGEX, subset)
        if m:
            grp_name = re.search("(.*){}".format(m.group(0)), subset)
            return grp_name.group(1)
        else:
            return subset


class Window(QtWidgets.QDialog):
    """Scene Inventory window"""

    def __init__(self, parent=None):
        QtWidgets.QDialog.__init__(self, parent)

        self.resize(1100, 480)
        self.setWindowTitle(
            "Scene Inventory 1.0 - {}".format(
                os.getenv("AVALON_PROJECT") or "<Project not set>"
            )
        )
        self.setObjectName("SceneInventory")
        self.setProperty("saveWindowPref", True)  # Maya only property!

        layout = QtWidgets.QVBoxLayout(self)

        # region control
        control_layout = QtWidgets.QHBoxLayout()
        filter_label = QtWidgets.QLabel("Search")
        text_filter = QtWidgets.QLineEdit()

        outdated_only = QtWidgets.QCheckBox("Filter to outdated")
        outdated_only.setToolTip("Show outdated files only")
        outdated_only.setChecked(False)

        icon = qtawesome.icon("fa.refresh", color="white")
        refresh_button = QtWidgets.QPushButton()
        refresh_button.setIcon(icon)

        control_layout.addWidget(filter_label)
        control_layout.addWidget(text_filter)
        control_layout.addWidget(outdated_only)
        control_layout.addWidget(refresh_button)

        # endregion control

        model = InventoryModel()
        proxy = FilterProxyModel()
        view = View()
        view.setModel(proxy)

        # apply delegates
        version_delegate = VersionDelegate(self)
        column = model.Columns.index("version")
        view.setItemDelegateForColumn(column, version_delegate)

        layout.addLayout(control_layout)
        layout.addWidget(view)

        self.filter = text_filter
        self.outdated_only = outdated_only
        self.view = view
        self.refresh_button = refresh_button
        self.model = model
        self.proxy = proxy

        # signals
        text_filter.textChanged.connect(self.proxy.setFilterRegExp)
        outdated_only.stateChanged.connect(self.proxy.set_filter_outdated)
        refresh_button.clicked.connect(self.refresh)
        view.data_changed.connect(self.refresh)
        view.hierarchy_view.connect(self.model.set_hierarchy_view)
        view.hierarchy_view.connect(self.proxy.set_hierarchy_view)

        # proxy settings
        proxy.setSourceModel(self.model)
        proxy.setDynamicSortFilter(True)
        proxy.setFilterCaseSensitivity(QtCore.Qt.CaseInsensitive)

        self.data = {
            "delegates": {
                "version": version_delegate
            }
        }

        # set some nice default widths for the view
        self.view.setColumnWidth(0, 250)  # name
        self.view.setColumnWidth(1, 55)  # version
        self.view.setColumnWidth(2, 55)  # count
        self.view.setColumnWidth(3, 150)  # family
        self.view.setColumnWidth(4, 100)  # namespace

        tools_lib.refresh_family_config_cache()

    def keyPressEvent(self, event):
        """Custom keyPressEvent.

        Override keyPressEvent to do nothing so that Maya's panels won't
        take focus when pressing "SHIFT" whilst mouse is over viewport or
        outliner. This way users don't accidently perform Maya commands
        whilst trying to name an instance.

        """

    def refresh(self):
        with tools_lib.preserve_expanded_rows(tree_view=self.view,
                                              role=self.model.UniqueRole):
            with tools_lib.preserve_selection(tree_view=self.view,
                                              role=self.model.UniqueRole,
                                              current_index=False):
                if self.view._hierarchy_view:
                    self.model.refresh(selected=self.view._selected)
                else:
                    self.model.refresh()


def show(root=None, debug=False, parent=None):
    """Display Scene Inventory GUI

    Arguments:
        debug (bool, optional): Run in debug-mode,
            defaults to False
        parent (QtCore.QObject, optional): When provided parent the interface
            to this QObject.

    """

    try:
        module.window.close()
        del module.window
    except (RuntimeError, AttributeError):
        pass

    if debug is True:
        io.install()

        any_project = next(
            project for project in io.projects()
            if project.get("active", True) is not False
        )

        api.Session["AVALON_PROJECT"] = any_project["name"]

    with tools_lib.application():
        window = Window(parent)
        window.setStyleSheet(style.load_stylesheet())
        window.show()
        window.refresh()

        module.window = window
