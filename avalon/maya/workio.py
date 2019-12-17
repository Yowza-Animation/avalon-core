"""Host API required Work Files tool"""
import os

from maya import cmds


def file_extensions():
    return [".ma", ".mb"]


def has_unsaved_changes():
    return cmds.file(query=True, modified=True)


def save_file(filepath):
    cmds.file(rename=filepath)
    cmds.file(save=True, type="mayaAscii")


def open_file(filepath):
    return cmds.file(filepath, open=True, force=True)


def current_file():

    current_filepath = cmds.file(query=True, sceneName=True)
    if not current_filepath:
        return None

    return current_filepath


def work_root(session):
    work_dir = session["AVALON_WORKDIR"]
    scene_dir = None

    # Query scene file rule from workspace.mel if it exists in WORKDIR
    workspace_mel = os.path.join(work_dir, "workspace.mel")
    if os.path.exists(workspace_mel):
        scene_rule = 'workspace -fr "scene" '
        # We need to use builtins as `open` is overridden by the workio API
        open_file = __builtins__["open"]
        with open_file(workspace_mel, "r") as f:
            for line in f:
                if line.strip().startswith(scene_rule):
                    remainder = line[len(scene_rule):]      # == "rule";
                    scene_dir = remainder.split('"')[1]     # == rule
    else:
        # We can't query a workspace that does not exist
        # so we return similar to what we do in other hosts.
        scene_dir = session.get("AVALON_SCENEDIR")

    if scene_dir:
        return os.path.join(work_dir, scene_dir)
    else:
        return work_dir