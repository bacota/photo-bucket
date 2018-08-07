A simple javascript program for viewing photos stored in a folder in S3.

Requirements
1. A subfolder called "thumb" with thumbnail images
2. A subfolder called "main" with the real images
3. Cors configuration of the s3 folders

The included index.html pulls the js script from s3 and invokes a
function, passing the aws region and a bucket name.

The javascript function extracts the folder name from the windows document url (and bucket name) and displays all the thumbnail images.  If a thumbnail is clicked, the full image is downloaded and displayed with a height and width calculated to fit the browser window.  Links are shown to go to the next or previous image, or to rotate the image.

To create the thumbnail images and the main directory, I usually a script like prepare.sh (included) on ubuntul.
