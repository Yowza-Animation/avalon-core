// ***************************************************************************
// *                        Avalon Harmony Host                                *
// ***************************************************************************


/**
 * @namespace
 * @classdesc AvalonHarmony encapsulate all Avalon related functions.
 */
var AvalonHarmony = {};


/**
 * Get scene metadata from Harmony.
 * @function
 * @return {object} Scene metadata.
 */
AvalonHarmony.getSceneData = function () {
    var metadata = scene.metadata('avalon');
    if (metadata) {
        return JSON.parse(metadata.value);
    } else {
        return {};
    }
};


/**
 * Set scene metadata to Harmony.
 * @function
 * @param {object} metadata Object containing metadata.
 */
AvalonHarmony.setSceneData = function (metadata) {
    scene.setMetadata({
        'name': 'avalon',
        'type': 'string',
        'creator': 'Avalon',
        'version': '1.0',
        'value': JSON.stringify(metadata)
    });
};

/**
 * Get the current group in Harmony
 * @function
 * @return {String} A string representing the currently open group in the
 * Node View, else "Top" if no Node View is currently open
 */
AvalonHarmony.getCurrentGroup = function () {
    var doc = $.scn;
    nodeView = '';
    for (i = 0; i < 200; i++) {
        nodeView = 'View' + (i);
        if (view.type(nodeView) == 'Node View') {
            break;
        }
    }

    if (!nodeView) {
        $.alert('You must have a Node View open!',
            'No Node View is currently open!\n' +
            'Open a Node View and Try Again.',
            'OK!');
        return;
    }

    var currentGroup;
    if (!nodeView) {
        currentGroup = doc.root;
    } else {
        currentGroup = doc.$node(view.group(nodeView));
    }

    return currentGroup;
};


/**
 * Get selected nodes in Harmony.
 * @function
 * @return {array} Selected nodes paths.
 */
AvalonHarmony.getSelectedNodes = function () {
    var selectionLength = selection.numberOfNodesSelected();
    var selectedNodes = [];
    for (var i = 0; i < selectionLength; i++) {
        selectedNodes.push(selection.selectedNode(i));
    }
    return selectedNodes;
};


/**
 * Set selection of nodes.
 * @function
 * @param {array} nodes Arrya containing node paths to add to selection.
 */
AvalonHarmony.selectNodes = function (nodes) {
    selection.clearSelection();
    for (var i = 0; i < nodes.length; i++) {
        selection.addNodeToSelection(nodes[i]);
    }
};


/**
 * Is node enabled?
 * @function
 * @param {string} node Node path.
 * @return {boolean} state
 */
AvalonHarmony.isEnabled = function (node) {
    return node.getEnable(node);
};


/**
 * Are nodes enabled?
 * @function
 * @param {array} nodes Array of node paths.
 * @return {array} array of boolean states.
 */
AvalonHarmony.areEnabled = function (nodes) {
    var states = [];
    for (var i = 0; i < nodes.length; i++) {
        states.push(node.getEnable(nodes[i]));
    }
    return states;
};


/**
 * Set state on nodes.
 * @function
 * @param {array} args Array of nodes array and states array.
 */
AvalonHarmony.setState = function (args) {
    var nodes = args[0];
    var states = args[1];
    // length of both arrays must be equal.
    if (nodes.length !== states.length) {
        return false;
    }
    for (var i = 0; i < nodes.length; i++) {
        node.setEnable(nodes[i], states[i]);
    }
    return true;
};


/**
 * Disable specified nodes.
 * @function
 * @param {array} nodes Array of nodes.
 */
AvalonHarmony.disableNodes = function (nodes) {
    for (var i = 0; i < nodes.length; i++) {
        node.setEnable(nodes[i], false);
    }
};


/**
 * Save scene in Harmony.
 * @function
 * @return {string} Scene path.
 */
AvalonHarmony.saveScene = function () {
    var app = QCoreApplication.instance();
    app.avalon_on_file_changed = false;
    scene.saveAll();
    return (
        scene.currentProjectPath() + '/' +
        scene.currentVersionName() + '.xstage'
    );
};


/**
 * Enable Harmony file-watcher.
 * @function
 */
AvalonHarmony.enableFileWatcher = function () {
    var app = QCoreApplication.instance();
    app.avalon_on_file_changed = true;
};


/**
 * Add path to file-watcher.
 * @function
 * @param {string} path Path to watch.
 */
AvalonHarmony.addPathToWatcher = function (path) {
    var app = QCoreApplication.instance();
    app.watcher.addPath(path);
};


/**
 * Setup node for Creator.
 * @function
 * @param {string} node Node path.
 */
AvalonHarmony.setupNodeForCreator = function (node) {
    node.setTextAttr(node, 'COMPOSITE_MODE', 1, 'Pass Through');
};


/**
 * Get node names for specified node type.
 * @function
 * @param {string} nodeType Node type.
 * @return {array} Node names.
 */
AvalonHarmony.getNodesNamesByType = function (nodeType) {
    var nodes = node.getNodes(nodeType);
    var nodeNames = [];
    for (var i = 0; i < nodes.length; ++i) {
        nodeNames.push(node.getName(nodes[i]));
    }
    return nodeNames;
};

/**
 * Get get children for specified group node.
 * @function
 * @param {array} args Arguments, see example.
 *
 * @example
 * // arguments are in following order:
 * var args = [
 *  nodeName,
 *  recursive,
 * ];
 */
AvalonHarmony.getChildren = function (args) {
    nodePath = args[0]
    recursive = args[1]
    _node = $.scn.$node(nodePath);
    var children = _node.subNodes(recursive)
    var nodes = [];
    for (n in children){
        nodes.push(children[n].path)
    }
    return nodes
};

/**
 * Get unique column name.
 * @function
 * @param  {string}  columnPrefix Column name.
 * @return {string}  Unique column name.
 */
AvalonHarmony.getUniqueColumnName = function(columnPrefix) {
    var suffix = 0;
    // finds if unique name for a column
    var columnName = columnPrefix;
    while (suffix < 2000) {
        if (!column.type(columnName)) {
            break;
        }

        suffix = suffix + 1;
        columnName = columnPrefix + '_' + suffix;
    }
    return columnName;
};

/**
 * Create container node in Harmony.
 * @function
 * @param {array} args Arguments, see example.
 * @return {string} Resulting node.
 *
 * @example
 * // arguments are in following order:
 * var args = [
 *  nodeName,
 *  nodeType,
 *  groupPath,
 *  x,
 *  y,
 *  z
 * ];
 */
AvalonHarmony.createNode = function (args) {
    nodeName = args[0]
    nodeType = args[1]
    groupPath = args[2]
    x = args[3]
    y = args[4]
    z = args[5]

    var resultNode = node.add(
        groupPath,
        nodeName,
        nodeType,
        x,
        y,
        z
    );
    return resultNode;
};

/**
 * Create container node in Harmony.
 * @function
 * @param {array} args Arguments, see example.
 * @return {string} Resulting node.
 *
 * @example
 * // arguments are in following order:
 * var args = [
 *  nodeName,
 *  nodeType,
 *  selection
 * ];
 */
AvalonHarmony.createContainer = function (args) {
    var resultNode = node.add('Top', args[0], args[1], 0, 0, 0);
    if (args.length > 2) {
        node.link(args[2], 0, resultNode, 0, false, true);
        node.setCoord(resultNode,
            node.coordX(args[2]),
            node.coordY(args[2]) + 70);
    }
    return resultNode;
};
