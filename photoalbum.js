var credentials;
var region;
var bucket;
var s3;
var divIdList = ['folder', 'thumbs', 'main', 'saveOrdering']
var currentFolder = ""
var folderChoice

function logErr(err) {
    if (err) console.log(err, err.stack)
}

function showDiv(divId) {
    for (let i=0; i<divIdList.length; i++) {
        if (divIdList[i] != divId) {
            let div = document.getElementById(divIdList[i])
            if (div) div.style.display = 'none'
        }
    }
    document.getElementById(divId).style.display = 'inline'
}

function setCredentials() {
    showDiv("folder")
    AWS.config.update({ region: region,
                        accessKeyId: credentials.AccessKeyId,
                        secretAccessKey: credentials.SecretAccessKey,
                        sessionToken: credentials.SessionToken
                      });
}

    
function authenticate(regionParam, bucketName) {
    showDiv("folder")
    region = regionParam;
    bucket = bucketName;
    let username = prompt('Username: ')
    let password = prompt('Password: ')
    let apigClient = apigClientFactory.newClient();
    let params = {};
    var body = {
        username: username,
        password: password,
    };
    apigClient.rootPost(params, body)
        .then( function(result) {
            credentials = result.data;
            setCredentials();
             s3 = new AWS.S3({
                apiVersion: '2006-03-01',
                params: { Bucket: bucket }
            });
            listFolders(region, bucketName);
        }).catch( function(result) {
            authenticate(region, bucketName);
        });
}

function stripSlash(folder) {
    if (folder.substr(folder.length-1) == '/')  return folder.slice(0,-1)
    else return folder
}

function listFolders(regionName, bucketName) {
    showDiv("folder")
    region = regionName;
    bucket = bucketName;
    let s3 = new AWS.S3({
        apiVersion: '2006-03-01',
        params: { Bucket: bucket }
    });
    removeElementsByClass('folderList')
    folderChoice = document.getElementById('folderChoice')
    div = document.getElementById("folder-app")
    s3.makeUnauthenticatedRequest(
        'listObjectsV2',
        { Bucket: bucket, Delimiter: '/', Prefix: "" },
        function(err, s3data) {
            if (err) console.log(err, err.stack)
            else {
                let table = document.createElement("table")
                let tr
                let i,len = s3data.CommonPrefixes.length
                for (i=0; i<len; ++i) {
                    if (i%4 == 0) {
                        tr = document.createElement("tr")
                    }
                    table.appendChild(tr)
                    let folder = stripSlash(s3data.CommonPrefixes[i].Prefix)
                    if (folder != 'apiGateway-js-sdk') {
                        if (folderChoice) 
                            addFolder(folderChoice, folder)
                        let text = document.createTextNode(folder)
                        let link = document.createElement("a")
                        link.href='#'
                        link.onclick = function() {
                            showPhotos(folder);
                            return false;
                        }
                        link.appendChild(text)
                        let p = document.createElement("td")
                        p.appendChild(link)
                        tr.appendChild(p)
                    }
                    if (div.childNodes.length > 0) {
                        div.replaceChild(table, div.childNodes[0])
                    } else {
                        div.appendChild(table)
                    }
                }
            }
        }
    )
    showDiv('folder')
}

function showPhotos(folder) {
    resetImages()
    removeElementsByClass('thumb')
    currentFolder = stripSlash(folder)
    showThumbs(region, bucket, currentFolder)
    showDiv('thumbs')
}


function addFolder(parent, folder) {
    let option = document.createElement('option')
    option.value=folder
    option.className="folderChoice"
    let text = document.createTextNode(folder)
    option.appendChild(text)
    parent.appendChild(option)
}


function createFolder() {
    let folderName = prompt("New Folder Name:")
    let indexFile = folderName + "/index.html"
     s3.copyObject(params = {
         Bucket: bucket,
         CopySource:  bucket + "/index-template.html",
         Key: indexFile
    }, function(err,data) {
        if (err) console.log(err, err.stack)
        else {
            s3.waitFor('objectExists', {Bucket: bucket, Key: indexFile})
            showPhotos(folderName)
        }
    })
}

function deleteCurrentFolder() {
    s3.deleteObject(
        { Bucket: bucket, Key: currentFolder + '/index.html' },
        function(err, s3data) {
            if (err) console.log(err, err.stack)
            else listFolders(region, bucket)
        }
    )
    s3.deleteObject(
        { Bucket: bucket, Key: currentFolder + '/metadata.json' }
    )
}


function renameFolder() {
    if (currentFolder == "") {
        console.log("Current Folder is missing")
        return;
    }
    let newFolder = prompt("New Folder Name: ")
    doRenameFolder(currentFolder, newFolder);
}


function doRenameFolder(source, dest) {
    doRenameSubFolder(source+'/', dest)
    doRenameSubFolder(source+'/main/', dest+'/main/')
    doRenameSubFolder(source+'/thumb/', dest+'/thumb/')
    s3.waitFor('objectExists', {Bucket: bucket, Key: dest+'/index.html'}, logErr)
    listFolders(region,bucket)
}


function doRenameSubFolder(source, dest) {
   s3.makeRequest(
        'listObjectsV2',
        { Bucket: bucket, Delimiter: '/', Prefix: source },
        function(err, s3data) {
            if (err) console.log(err, err.stack)
            else renameObjects(source, dest, s3data.Contents);
        })
}

function renameObjects(source, dest, contents) {
    let len = contents.length
    for (let i=0; i<len; ++i) {
        let oldObject = contents[i].Key
        let newObject = oldObject.replace(source, dest)
        renameObject(oldObject, newObject)
    }
}

function renameObject(source, dest) {
    s3.copyObject(params = {
        Bucket: bucket,
        CopySource: bucket + '/' + source,
        Key: dest
    }, function(err,data) {
        if (err) console.log(err, err.stack)
        else {
            deleteObject(source);
        }
    })
}

function deleteObject(obj) {
    s3.deleteObject({
        Bucket: bucket,
        Key: obj,
    }, logErr);
}

function upload() {
    let files = document.getElementById("upload").files
    for (let i=0; i<files.length; ++i) {
        uploadFile(files.item(i))
        images.push(files.item(i).name)
    }
    saveOrdering()
    alert("Photo is uploaded.  Please wait a few seconds and use the Refresh Folder button to see the photo.")
}


function uploadFile(file) {
    if (!file) {
        console.log(file.name + " does not exist")
    } else {
        s3.upload({
            Bucket: bucket,
            ContentType: file.type,
            Key: 'new/' + currentFolder + '/main/' + file.name,
            Body: file
        }, {}, logErr)
    }
}


function deleteCurrentPhoto() {
    let image = currentImage()
    if (confirm("Delete " + image + "? ")) {
        deleteObject(currentFolder + '/main/' + image)
        deleteObject(currentFolder + '/thumb/' + image)
    }
    newImages = images.filter(img => img != image)
    removeElementsByClass('thumb')
    resetImages()
    doShowThumbs(region, bucket, currentFolder, newImages)
    showDiv('thumbs')
    saveOrdering()
}


function refreshFolder() {
    showPhotos(currentFolder)
}


function moveCurrentPhoto() {
    let newFolder = folderChoice.value
    if (newFolder == "") {
        return
    }
    let image = currentImage()
    renameObject(currentFolder +'/main/'+image, newFolder+'/main/'+image)
    renameObject(currentFolder +'/thumb/'+image, newFolder+'/thumb/'+image)
}


function drop(ev) {
    ev.preventDefault();
    let sourceId = ev.dataTransfer.getData("sourceId");
    let targetId = ev.target.id
    ev.target.appendChild(document.getElementById(sourceId));
    let newImages = []
    let i=0,j=0
    while (i<images.length) {
        if (images[i] == sourceId) {
            i++
        } else if (images[i] == targetId) {
            newImages[j++] = sourceId
            newImages[j++] = targetId
            i++
        } else {
            newImages[j++] = images[i++]
        }
    }
    resetImages()
    removeElementsByClass('thumb')
    for (i=0; i<newImages.length; ++i) {
        addThumb(newImages[i], i)
    }
    document.getElementById('saveOrdering').style.display = 'inline'
}


function saveOrdering() {
    let metadata = {images: images, captions: captions}
    s3.putObject({Body: JSON.stringify(metadata),
                  Bucket: bucket,
                  Key: currentFolder + '/metadata.json',
                  ContentType: 'application/json'
                 }, logErr)
    document.getElementById('saveOrdering').style.display = 'none'
}

function setCaption() {
    let newCaption = document.getElementById("captionInput").value
    captions[currentImage()] = newCaption
    document.getElementById(currentImage()).title = newCaption
    saveOrdering()
    showDiv('thumbs')
}
