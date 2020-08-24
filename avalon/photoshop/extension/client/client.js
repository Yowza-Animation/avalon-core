    // client facing part of extension, creates WSRPC client (jsx cannot 
    // do that)
    // consumes RPC calls from server (Pype) calls ./host/index.jsx and 
    // returns values back (in json format)
    
    var logReturn = function(result){ log.warn('Result: ' + result);};
    
    var csInterface = new CSInterface();
    
    log.warn("script start");

    WSRPC.DEBUG = true;
    WSRPC.TRACE = true;
  
    var url = 'ws://localhost:8099/ws/';
    RPC = new WSRPC(url, 5000); // spin connection

    RPC.connect();

    log.warn("connected");
    
    function myCallBack(){
        log.warn("Triggered index.jsx");
    }
    // importing through manifest.xml isn't working because relative paths
    // possibly TODO
    jsx.evalFile('./host/index.jsx', myCallBack); 
    
    function EscapeStringForJSX(str){
    // Replaces:
    //  \ with \\
    //  ' with \'
    //  " with \"
    // See: https://stackoverflow.com/a/3967927/5285364
        return str.replace(/\\/g, '\\\\').replace(/'/g, "\\'").replace(/"/g, '\\"');
    }

    function runEvalScript(script) {
        // because of asynchronous nature of functions in jsx
        // this waits for response
        return new Promise(function(resolve, reject){
            csInterface.evalScript(script, resolve);
        });
    }
    
    RPC.addRoute('Photoshop.open', function (data) {
            log.warn('Server called client route "open":', data);
            var escapedPath = EscapeStringForJSX(data.path);
            return runEvalScript("fileOpen('" + escapedPath +"')")
                .then(function(result){
                    log.warn("open: " + result);
                    return result;
                });
    });
    
    RPC.addRoute('Photoshop.read', function (data) {
            log.warn('Server called client route "read":', data);
            return runEvalScript("getHeadline()")
                .then(function(result){
                    log.warn("getHeadline: " + result);
                    return result;
                });
    });

    RPC.addRoute('Photoshop.get_layers', function (data) {
            log.warn('Server called client route "get_layers":', data);
            return runEvalScript("getLayers()")
                .then(function(result){
                    log.warn("getLayers: " + result);
                    return result;
                });
    });
    
    RPC.addRoute('Photoshop.set_visible', function (data) {
            log.warn('Server called client route "set_visible":', data);
            return runEvalScript("setVisible(" + data.layer_id + ", " 
                                 + data.visibility + ")")
                .then(function(result){
                    log.warn("setVisible: " + result);
                    return result;
                });
    });
    
    RPC.addRoute('Photoshop.get_active_document_name', function (data) {
            log.warn('Server called client route "get_active_document_name":', 
                      data);
            return runEvalScript("getActiveDocumentName()")
                .then(function(result){
                    log.warn("save: " + result);
                    return result;
                });
    });
    
    RPC.addRoute('Photoshop.get_active_document_full_name', function (data) {
            log.warn('Server called client route ' +
                     '"get_active_document_full_name":', data);
            return runEvalScript("getActiveDocumentFullName()")
                .then(function(result){
                    log.warn("save: " + result);
                    return result;
                });
    });
    
    RPC.addRoute('Photoshop.save', function (data) {
            log.warn('Server called client route "save":', data);
            
            return runEvalScript("save()")
                .then(function(result){
                    log.warn("save: " + result);
                    return result;
                });
    });
    
    RPC.addRoute('Photoshop.get_selected_layers', function (data) {
            log.warn('Server called client route "get_selected_layers":', data);
            
            return runEvalScript("getSelectedLayers()")
                .then(function(result){
                    log.warn("get_selected_layers: " + result);
                    return result;
                });
    });
    
    RPC.addRoute('Photoshop.create_group', function (data) {
            log.warn('Server called client route "create_group":', data);
            
            return runEvalScript("createGroup('" + data.name + "')")
                .then(function(result){
                    log.warn("createGroup: " + result);
                    return result;
                });
    });
    
    RPC.addRoute('Photoshop.group_selected_layers', function (data) {
            log.warn('Server called client route "group_selected_layers":', 
                     data);
            
            return runEvalScript("groupSelectedLayers(null, "+
                                 "'" + data.name +"')")
                .then(function(result){
                    log.warn("group_selected_layers: " + result);
                    return result;
                });
    });
    
    RPC.addRoute('Photoshop.import_smart_object', function (data) {
            log.warn('Server called client route "import_smart_object":', data);
            var escapedPath = EscapeStringForJSX(data.path);
            return runEvalScript("importSmartObject('" + escapedPath +"')")
                .then(function(result){
                    log.warn("import_smart_object: " + result);
                    return result;
                });
    });
    
    RPC.addRoute('Photoshop.replace_smart_object', function (data) {
            log.warn('Server called route "replace_smart_object":', data);
            var escapedPath = EscapeStringForJSX(data.path);
            return runEvalScript("replaceSmartObjects('" + data.layer + "'," +
                                                      "'" + escapedPath +"')")
                .then(function(result){
                    log.warn("replaceSmartObjects: " + result);
                    return result;
                });
    });
     
    RPC.addRoute('Photoshop.select_layers', function (data) {
            log.warn('Server called client route "select_layers":', data);
            
            return runEvalScript("selectLayers()")
                .then(function(result){
                    log.warn("select_layers: " + result);
                    return result;
                });
    });
    
    RPC.addRoute('Photoshop.is_saved', function (data) {
            log.warn('Server called client route "is_saved":', data);
            
            return runEvalScript("isSaved()")
                .then(function(result){
                    log.warn("is_saved: " + result);
                    return result;
                });
    });
    
    RPC.addRoute('Photoshop.saveAs', function (data) {
            log.warn('Server called client route "saveAsJPEG":', data);
            var escapedPath = EscapeStringForJSX(data.image_path);
            return runEvalScript("saveAs('" + escapedPath + "', " +
                                         "'" + data.ext + "', " + 
                                         data.as_copy + ")")
                .then(function(result){
                    log.warn("save: " + result);
                    return result;
                });
    });
    
    RPC.addRoute('Photoshop.imprint', function (data) {
            log.warn('Server called client route "imprint":', data);
            var escaped = data.payload.replace(/\n/g, "\\n");
            return runEvalScript("imprint('" + escaped + "')")
                .then(function(result){
                    log.warn("imprint: " + result);
                    return result;
                });
    });
      
    RPC.call('Photoshop.ping').then(function (data) {
        log.warn('Result for calling server route "ping": ', data);
        return runEvalScript("ping()")
                .then(function(result){
                    log.warn("ping: " + result);
                    return result;
                });
              
    }, function (error) {
        log.warn(error);
    });
    
    log.warn("end script");
