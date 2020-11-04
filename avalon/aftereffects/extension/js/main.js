/*jslint vars: true, plusplus: true, devel: true, nomen: true, regexp: true,
indent: 4, maxerr: 50 */
/*global $, window, location, CSInterface, SystemPath, themeManager*/


var csInterface = new CSInterface();
    
log.warn("script start");

WSRPC.DEBUG = false;
WSRPC.TRACE = false;

// get websocket server url from environment value
async function startUp(url){
    promis = runEvalScript("getEnv('" + url + "')");

    var res = await promis; 
    log.warn("res: " + res);
    // run rest only after resolved promise
    main(res);
}

function main(websocket_url){
    // creates connection to 'websocket_url', registers routes      
    var default_url = 'ws://localhost:8099/ws/';

    if  (websocket_url == ''){
         websocket_url = default_url;
    }
    RPC = new WSRPC(websocket_url, 5000); // spin connection

    RPC.connect();

    log.warn("connected"); 

    RPC.addRoute('AfterEffects.open', function (data) {
        log.warn('Server called client route "open":', data);
        var escapedPath = EscapeStringForJSX(data.path);
        return runEvalScript("fileOpen('" + escapedPath +"')")
            .then(function(result){
                log.warn("open: " + result);
                return result;
            });
    });

    RPC.addRoute('AfterEffects.get_metadata', function (data) {
        log.warn('Server called client route "get_metadata":', data);
        return runEvalScript("getMetadata()")
            .then(function(result){
                log.warn("getMetadata: " + result);
                return result;
            });
    });

    RPC.addRoute('AfterEffects.get_active_document_name', function (data) {
        log.warn('Server called client route ' + 
            '"get_active_document_name":', data);
        return runEvalScript("getActiveDocumentName()")
            .then(function(result){
                log.warn("get_active_document_name: " + result);
                return result;
            });
    });

    RPC.addRoute('AfterEffects.get_active_document_full_name', function (data){
        log.warn('Server called client route ' + 
            '"get_active_document_full_name":', data);
        return runEvalScript("getActiveDocumentFullName()")
            .then(function(result){
                log.warn("get_active_document_full_name: " + result);
                return result;
            });
    });

    RPC.addRoute('AfterEffects.get_items', function (data) {
        log.warn('Server called client route "get_items":', data);
        return runEvalScript("getItems("  + data.comps + "," +
                                            data.folders + "," +
                                            data.footages + ")")
            .then(function(result){
                log.warn("get_items: " + result);
                return result;
            });
    });

    
    RPC.addRoute('AfterEffects.get_selected_items', function (data) {
        log.warn('Server called client route "get_selected_items":', data);
        return runEvalScript("getSelectedItems(" + data.comps + "," +
                                                   data.folders + "," +
                                                   data.footages  + ")")
            .then(function(result){
                log.warn("get_items: " + result);
                return result;
            });
    });

    RPC.addRoute('AfterEffects.import_file', function (data) {
        log.warn('Server called client route "import_file":', data);
        var escapedPath = EscapeStringForJSX(data.path);
        return runEvalScript("importFile('" + escapedPath +"', " +
                                         "'" + data.item_name + "'," +
                                         "'" + JSON.stringify(
                                         data.import_options) + "')")
            .then(function(result){
                log.warn("open: " + result);
                return result;
            });
    });

    RPC.addRoute('AfterEffects.replace_item', function (data) {
        log.warn('Server called client route "replace_item":', data);
        var escapedPath = EscapeStringForJSX(data.path);
        return runEvalScript("replaceItem(" + data.item_id + ", " +
                                     "'" + escapedPath + "', " +
                                     "'" + data.item_name + "')")
            .then(function(result){
                log.warn("replaceItem: " + result);
                return result;
            });
    });

    RPC.addRoute('AfterEffects.delete_item', function (data) {
        log.warn('Server called client route "delete_item":', data);
        return runEvalScript("deleteItem(" + data.item_id + "')")
            .then(function(result){
                log.warn("deleteItem: " + result);
                return result;
            });
    });

    RPC.addRoute('AfterEffects.imprint', function (data) {
        log.warn('Server called client route "imprint":', data);
        var escaped = data.payload.replace(/\n/g, "\\n");
        return runEvalScript("imprint('" + escaped +"')")
            .then(function(result){
                log.warn("imprint: " + result);
                return result;
            });
    });

    RPC.addRoute('AfterEffects.set_label_color', function (data) {
        log.warn('Server called client route "set_label_color":', data);
        return runEvalScript("setLabelColor(" + data.item_id + "," +
                                                data.color_idx + ")")
            .then(function(result){
                log.warn("imprint: " + result);
                return result;
            });
    });

    RPC.addRoute('AfterEffects.saveAs', function (data) {
        log.warn('Server called client route "saveAs":', data);
        var escapedPath = EscapeStringForJSX(data.image_path);
        return runEvalScript("saveAs('" + escapedPath + "', " +
                                     data.as_copy + ")")
            .then(function(result){
                log.warn("saveAs: " + result);
                return result;
            });
    });

    RPC.addRoute('AfterEffects.save', function (data) {
        log.warn('Server called client route "save":', data);
        return runEvalScript("save()")
            .then(function(result){
                log.warn("save: " + result);
                return result;
            });
    });
}

/** main entry point **/
startUp("WEBSOCKET_URL");

(function () {
    'use strict';

    var csInterface = new CSInterface();
    
    
    function init() {
                
        themeManager.init();
                
        $("#btn_test").click(function () {
            csInterface.evalScript('sayHello()');
        });
    }
        
    init();

}());

function EscapeStringForJSX(str){
    // Replaces:
    //  \ with \\
    //  ' with \'
    //  " with \"
    // See: https://stackoverflow.com/a/3967927/5285364
    return str.replace(/\\/g, '\\\\').replace(/'/g, "\\'").replace(/"/g,'\\"');
}

function runEvalScript(script) {
    // because of asynchronous nature of functions in jsx
    // this waits for response
    return new Promise(function(resolve, reject){
        csInterface.evalScript(script, resolve);
    });
}
