import argparse
import urllib2
import base64
import HTMLParser
import os
import shutil
from progressbar import ProgressBar, SimpleProgress, Bar, ETA

home = os.path.expanduser('~')
hiddenDir = home + '/.target-platform/'
currentDir = hiddenDir + 'current/'
backupDir = hiddenDir + 'backup/'
urls = []
user = None
password = None
remoteDirectory = None
localDirectory = None
files = None

def get_arguments():
    parser = argparse.ArgumentParser(description='Mirror target platform')
    parser.add_argument('option', type=str, help='update: update the current target platform. restore: restore the previous target platform. clean: remove restore point')
    return parser.parse_args()

def load_config():
    global urls, password, user
    with open(hiddenDir + 'urls', 'r') as file:
        urls = file.readlines()
    for i in range(len(urls)):
        urls[i] = urls[i].replace('\n', '')
        if not urls[i].endswith('/'):
            urls[i] = urls[i] + '/'
    with open(hiddenDir + 'password', 'r') as file:
        data = file.readlines()[0]
    user = data[0]
    password = data[1]

def main():
    option = get_arguments().option
    load_config()
    if option == 'update':
        backup()
        try:
            updateFromUrls()
        except Exception as e:
            print('Error occured: ' + str(e))
            restore()
    elif option == 'restore':
        restore()
    elif option == 'clean':
        clean()
    else:
        print('Unknown option: ' + option)

def backup():
    if os.path.exists(backupDir):
        shutil.rmtree(currentDir)
    elif os.path.exists(currentDir):
        shutil.move(currentDir, backupDir)

def restore():
    if os.path.exists(backupDir):
        shutil.rmtree(currentDir)
        shutil.move(backupDir, currentDir)
        shutil.rmtree(backupDir)
        print('Restored backup')
    else:
        print('No backup available')

def clean():
    if os.path.exists(backupDir):
        shutil.rmtree(backupDir)
        print('Backup removed')
    else:
        print('No backup available')

def updateFromUrls():
    global remoteDirectory, localDirectory, files
    for url in urls:
        files = []
        remoteDirectory = url
        localDirectory = currentDir + os.path.basename(url[:len(url)-1]) + '/'
        parseFolder(url)
        print('Downloading ' + url)
        downloadFiles()
    print()

def parseFolder(url):
    html = getHtml(url)
    folders, files = parseHtml(html)
    for folder in folders:
        parseFolder(url + folder)
        pass
    for file in files:
        addFile(url + file)

def downloadFiles():
    bar = ProgressBar(widgets=[SimpleProgress(), ' ', Bar(), ' ', ETA()])
    bar.maxval = len(files)
    bar.start()
    for i, file in enumerate(files):
        localPath = file.replace(remoteDirectory, localDirectory)
        folder = os.path.dirname(localPath) + '/'
        downloadFile(file, folder)
        bar.update(i + 1)
    bar.finish()

def downloadFile(url, folder):
    if not os.path.exists(folder):
        os.makedirs(folder)
    try:
        file = urllib2.urlopen(url)
        with open(folder + os.path.basename(url), 'wb') as local_file:
            local_file.write(file.read())
    except urllib2.HTTPError, e:
        print(e)
    except urllib2.URLError, e:
        print(e)

def addFile(file):
    global files
    if not file.endswith('.zip'):
        files.append(file)

def getHtml(url):
    request = urllib2.Request(url)
    base64string = base64.b64encode('%s:%s' % (user, password))
    request.add_header("Authorization", "Basic %s" % base64string)
    return urllib2.urlopen(request).read()

class FileLinkHTMLParser(HTMLParser.HTMLParser):
    def __init__(self):
        self.folders = set()
        self.files = set()
        self.valid = False
    def handle_starttag(self, tag, attrs):
        if tag == 'tr':
            for attr in attrs:
                if attr[0] == 'class' and (attr[1] == 'odd' or attr[1] == 'even'):
                    self.valid = True
        elif tag == 'a' and self.valid:
            for attr in attrs:
                if attr[0] == 'href':
                    if attr[1].startswith('/') or attr[1].startswith('http'):
                        # this is not a link we care about, ignore
                        pass
                    elif attr[1].endswith('/'):
                        self.folders.add(attr[1])
                    else:
                        self.files.add(attr[1])
    def handle_endtag(self, tag):
        if tag == 'tr':
            valid = False
    def handle_data(self, data):
        pass

def parseHtml(html):
    parser = FileLinkHTMLParser()
    parser.reset()
    parser.feed(html)
    return parser.folders, parser.files

if __name__ == '__main__':
    main()