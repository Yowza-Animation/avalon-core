import logging
import os
import subprocess
import sys

from ..models import Item, TreeModel
from ... import style
from ...vendor import qtawesome
from ...vendor.Qt import QtCore

from avalon.api import AvalonMongoDB
from avalon import io

log = logging.getLogger(__name__)


class FilesModel(TreeModel):
    """Model listing files with specified extensions in a root folder"""
    Columns = ["filename", "date", "modified_by"] #, "publish_version"]

    FileNameRole = QtCore.Qt.UserRole + 2
    DateModifiedRole = QtCore.Qt.UserRole + 3
    FilePathRole = QtCore.Qt.UserRole + 4
    IsEnabled = QtCore.Qt.UserRole + 5
    ModifiedByRole = QtCore.Qt.UserRole + 6
    PublishVersionRole = QtCore.Qt.UserRole + 7

    def __init__(self, file_extensions, parent=None):
        super(FilesModel, self).__init__(parent=parent)

        self._root = None
        self._file_extensions = file_extensions
        self._icons = {"file": qtawesome.icon("fa.file-o",
                                              color=style.colors.default)}

        self.dbcon = AvalonMongoDB()

    def set_root(self, root):
        self._root = root
        self.refresh()

    def _add_empty(self):

        item = Item()
        item.update({
            # Put a display message in 'filename'
            "filename": "No files found.",
            # Not-selectable
            "enabled": False,
            "filepath": None
        })

        self.add_child(item)

    def refresh(self):

        self.clear()
        self.beginResetModel()

        root = self._root

        if not root:
            self.endResetModel()
            return

        if not os.path.exists(root):
            # Add Work Area does not exist placeholder
            log.debug("Work Area does not exist: %s", root)
            message = "Work Area does not exist. Use Save As to create it."
            item = Item({
                "filename": message,
                "date": None,
                "modified_by": None,
                "publish_version": None,
                "filepath": None,
                "enabled": False,
                "icon": qtawesome.icon("fa.times",
                                       color=style.colors.mid)
            })
            self.add_child(item)
            self.endResetModel()
            return

        extensions = self._file_extensions

        for f in os.listdir(root):
            path = os.path.join(root, f)
            if os.path.isdir(path):
                continue

            if extensions and os.path.splitext(f)[1] not in extensions:
                continue

            modified = os.path.getmtime(path)
            modified_by = self.get_file_owner(path)
            publish_version = None#self.get_published_version(path)

            item = Item({
                "filename": f,
                "date": modified,
                "modified_by": modified_by,
                "publish_version": publish_version,
                "filepath": path
            })

            self.add_child(item)

        self.endResetModel()

    def get_file_owner(self, path):

        if sys.platform == "win32":
            # import win32security
            # sd = win32security.GetFileSecurity (path, win32security.OWNER_SECURITY_INFORMATION)
            # owner_sid = sd.GetSecurityDescriptorOwner ()
            # name, domain, type = win32security.LookupAccountSid (None, owner_sid)
            # print( "File owned by %s\\%s" % (domain, name))

            dirname, basename = os.path.split(path)

            cmd = ["cmd", "/c", "dir", path, "/q"]
            session = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            result = session.communicate()[0].decode('utf8')
            sys.stdout.write(result)
            lines = result.split('\n')
            for line in lines:
                columns = [x.rstrip("\r") for x in line.split(" ") if x]
                log.info(line+"\n")
                if len(columns) == 6:
                    if basename == columns[5]:
                        return columns[4].split("\\")[-1]

        else:
            from os import stat
            from pwd import getpwuid
            return getpwuid(stat(path).st_uid).pw_name

        return "..."

    def get_published_version(self, path):

        path = os.path.normpath(
            path
            ).replace(
                os.path.splitdrive(path)[0],
                "{root}"
                ).replace("\\", "/")

        version = io.find_one({"data.source": path})
        log.info(version)

        return str(version)

    def data(self, index, role):

        if not index.isValid():
            return

        if role == QtCore.Qt.DecorationRole:
            # Add icon to filename column
            item = index.internalPointer()
            if index.column() == 0:
                if item["filepath"]:
                    return self._icons["file"]
                else:
                    return item.get("icon", None)
        if role == self.FileNameRole:
            item = index.internalPointer()
            return item["filename"]
        if role == self.DateModifiedRole:
            item = index.internalPointer()
            return item["date"]
        if role == self.ModifiedByRole:
            item = index.internalPointer()
            return item["modified_by"]
        if role == self.PublishVersionRole:
            return item["publish_version"]
        if role == self.FilePathRole:
            item = index.internalPointer()
            return item["filepath"]
        if role == self.IsEnabled:
            item = index.internalPointer()
            return item.get("enabled", True)

        return super(FilesModel, self).data(index, role)

    def headerData(self, section, orientation, role):

        # Show nice labels in the header
        if role == QtCore.Qt.DisplayRole and \
                orientation == QtCore.Qt.Horizontal:
            if section == 0:
                return "Name"
            elif section == 1:
                return "Date modified"
            elif section == 2:
                return "User"
            elif section == 3:
                return "Published Version"

        return super(FilesModel, self).headerData(section, orientation, role)
