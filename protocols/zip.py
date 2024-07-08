# Profile: Hyperspace Labs
# Protocol: zip
#
# A quick-and-dirty script to download packages from the internet for 
# integration with orbit.

import sys
import requests, zipfile, io

if len(sys.argv) < 2:
    print('error: script requires URL as command-line argument')
    exit(101)

# get the url
URL = sys.argv[1]

r = requests.get(URL)
if r.ok == False:
    print('error:', str(r), str(r.reason))
    exit(101)
z = zipfile.ZipFile(io.BytesIO(r.content))
z.extractall()
