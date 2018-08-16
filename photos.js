var images = []
var captions = {}
var bucketName = ""
var prefix = ""
var currentIndex = 0
var currentRotation = 0

function imageUrl(imageType, imageName) {
    return 'http://s3.amazonaws.com/' + bucketName + '/' + prefix + '/' + imageType
    + '/' + imageName
}


function removeElementsByClass(className) {
    let thumbs = document.getElementsByClassName(className);
    let l = thumbs.length;
    for (let i=l-1; i>=0; --i) {
        thumbs[i].remove();
    }
}


function photos(region) {
    let pieces = window.document.documentURI.split("/")
    bucketName = pieces[2]
    prefix = pieces[3]
    showThumbs(region, bucketName, prefix)
}

function arrayContains(array, element) {
    return array.findIndex(el => el == element) != -1
}


function showThumbs(region, bucket, folder) {
    let s3 = new AWS.S3({
        apiVersion: '2006-03-01',
        params: { Bucket: bucket }
    });
    s3.makeUnauthenticatedRequest(
        'getObject',
        {Bucket: bucket, Key: folder + '/metadata.json'},
        function(err, data) {
            if (err) {
                console.log(err)
                doShowThumbs(region, bucket, folder, null)
            }
            else  {
                let metadata = JSON.parse(data.Body)
                let uniqueImages = []
                if (metadata.hasOwnProperty('images')) {
                    let imgList = metadata.images
                    for (let i=0; i<imgList.length; ++i) {
                        if (!arrayContains(uniqueImages, imgList[i]))
                            uniqueImages.push(imgList[i])
                    }
                }
                captions = metadata.captions
                doShowThumbs(region, bucket, folder, uniqueImages)
            }
        })
}


function doShowThumbs(region, bucket, folder, orderedImages) {
    bucketName = bucket
    prefix = folder
    document.getElementById("main").style.display = 'none'
    let title = document.createElement('H1')
    title.className = 'thumb'
    title.innerHTML = prefix
    let thumbDiv = document.getElementById("thumbs")
    thumbDiv.appendChild(title)
    if (orderedImages != null && orderedImages.length > 0) {
        for (let i=0; i<orderedImages.length; ++i) {
            addThumb(orderedImages[i], i)
        }
    } else {
        resetImages()
    }
    showAllThumbs(region, bucket, folder)
}

function showAllThumbs(region, bucket, folder) {
    AWS.config.update({ region: region });
    let s3 = new AWS.S3({
        apiVersion: '2006-03-01',
        params: { Bucket: bucketName }
    });
    s3.makeUnauthenticatedRequest(
        'listObjectsV2',
        {Bucket: bucketName, Prefix: prefix + '/thumb'},
        function(err, s3data) {
            if (err) console.log(err, err.stack)
            else {
                currentIndex = 0
                let contents = s3data.Contents
                let i, len = contents.length
                for (i=0; i<len; ++i) {
                    let parts = contents[i].Key.split('/')
                    addThumb(parts.pop(), i)
                }
            }
        }
    )
}

function toggleDeleteButton() {
    let deleteButton = document.getElementById('delete-button')
    if (deleteButton != null) {
        if (images.length > 0) {
            deleteButton.style.display = 'none'
        } else {
            deleteButton.style.display = 'inline'
        }
    }
}


function addThumb(thumbName, index) {
    let thumbDiv = document.getElementById("thumbs")
    if (!arrayContains(images, thumbName)) {
        images.push(thumbName)
    }
    let img = document.createElement("img")
    let anchor = document.createElement("a")
    anchor.className = "thumb"
    img.id=thumbName
    img.src = imageUrl('thumb', thumbName)
    img.draggable="true"
    img.ondrop=drop
    img.ondragover=allowDrop
    img.ondragstart=drag
    if (captions[thumbName]) img.title = captions[thumbName]
    anchor.onclick = function () { return clickOnThumb(index) }
    anchor.appendChild(img)
    thumbDiv.appendChild(anchor)
}

function displayImage() {
    currentRotation = 0
    let img = document.createElement("img")
    let current = currentImage()
    img.src = imageUrl('main', current)
    img.id = "main-image"
    img.onload = function() {
        let hscale = img.height/parseFloat(window.innerHeight)
        let wscale = img.width/parseFloat(window.innerWidth)
        if (hscale > 1 || wscale > 1) {
            let scale = 1.1*(hscale > wscale ? hscale : wscale)
            img.height = Math.round(img.height/scale)
        }
    }
    let container = document.getElementById("image-container")
    if (container.firstChild) 
        container.replaceChild(img, container.firstChild)
    else
        container.appendChild(img)
    document.getElementById("thumbs").style.display = 'none'
    document.getElementById("main").style.display = 'inline'
    let caption = captions[current]
    let titleElement = document.getElementById("photo-caption")
    let captionInput = document.getElementById("captionInput")
    if (!caption) {
        caption = ""
    }
    if (captionInput) captionInput.value = caption
    titleElement.innerHTML = '<H1>'+caption+'</H1>'
}


function clickOnThumb(index) {
    currentIndex = index % images.length
    displayImage()
    return false
} 

function previous() {
    currentIndex = (images.length + currentIndex -1) % images.length
    displayImage()
    return false
}

function next() {
    currentIndex = (currentIndex +1) % images.length
    displayImage()
    return false
}

function closeImage() {
    document.getElementById("thumbs").style.display = 'inline'
    document.getElementById("main").style.display = 'none'
    return false
}

function rotate(n) {
    currentRotation += n
    let rotation = 'rotate(' + currentRotation + 'deg)'
    document.getElementById("main-image").style.transform = rotation
    return false
}

function currentImage() {
    return images[currentIndex]
}


function allowDrop(ev) {
    ev.preventDefault();
}

function drag(ev) {
    ev.dataTransfer.setData("sourceId", ev.target.id);
}

function resetImages() {
    images = []
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
    let saveButton = document.getElementById('saveOrdering')
    if (saveButton) saveButton.style.display = 'inline'
}
