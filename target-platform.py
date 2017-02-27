import argparse
from html.parser import HTMLParser
import os
import shutil
from progressbar import ProgressBar
import requests

home = os.path.expanduser('~')
hiddenDir = home + '/.target-platform/'
current_dir = hiddenDir + 'current/'
backup_dir = hiddenDir + 'backup/'
urls = []
user = None
password = None
remote_directory = None
local_directory = None
files = None
ignored_files = {'.exe', '.zip', '.gz', '.md5', '.dmg'}


def get_arguments():
    parser = argparse.ArgumentParser(description='Mirror target platform')
    parser.add_argument('option', type=str, help='update: update the current target platform. restore: restore the '
                                                 'previous target platform. clean: remove restore point')
    return parser.parse_args()


def load_config():
    global urls, password, user
    with open(hiddenDir + 'urls', 'r') as file:
        urls = file.readlines()
    for i in range(len(urls)):
        urls[i] = urls[i].replace('\n', '')
        if not urls[i].endswith('/'):
            urls[i] += '/'
    with open(hiddenDir + 'account', 'r') as file:
        user, password = file.readlines()
    user = user.replace('\n', '')
    password = password.replace('\n', '')


def main():
    option = get_arguments().option
    load_config()
    if option == 'update':
        backup()
        try:
            update_from_urls()
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
    if os.path.exists(backup_dir):
        if os.path.exists(current_dir):
            shutil.rmtree(current_dir)
    elif os.path.exists(current_dir):
        shutil.move(current_dir, backup_dir)


def restore():
    if os.path.exists(backup_dir):
        if os.path.exists(current_dir):
            shutil.rmtree(current_dir)
        shutil.move(backup_dir, current_dir)
        print('Restored backup')
    else:
        print('No backup available')


def clean():
    if os.path.exists(backup_dir):
        shutil.rmtree(backup_dir)
        print('Backup removed')
    else:
        print('No backup available')


def update_from_urls():
    global remote_directory, local_directory, files
    for url in urls:
        files = []
        remote_directory = url
        local_directory = current_dir + os.path.basename(url[:len(url) - 1]) + '/'
        parse_folder(url)
        print('Downloading ' + url)
        download_files()
    print()


def parse_folder(url):
    html = get_html(url)
    folders, file_names = parse_html(html)
    for folder in folders:
        parse_folder(url + folder)
        pass
    for file in file_names:
        add_file(url + file)


def download_files():
    global files
    with ProgressBar(max_value=len(files)) as progress:
        for i, file in enumerate(files):
            local_path = file.replace(remote_directory, local_directory)
            folder = os.path.dirname(local_path) + '/'
            download_file(file, folder)
            progress.update(i + 1)


def download_file(url, folder):
    if not os.path.exists(folder):
        os.makedirs(folder)
    auth = requests.auth.HTTPBasicAuth(user, password)
    response = requests.get(url, auth=auth)
    with open(folder + os.path.basename(url), 'wb') as local_file:
        local_file.write(response.content)


def add_file(file):
    global files
    extension = os.path.splitext(file)[1]
    if extension not in ignored_files:
        files.append(file)


def get_html(url):
    auth = requests.auth.HTTPBasicAuth(user, password)
    response = requests.get(url, auth=auth)
    return response.text


class FileLinkHTMLParser(HTMLParser):

    def __init__(self):
        self.folders = set()
        self.files = set()
        self.valid = False
        HTMLParser.__init__(self)

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
            self.valid = False

    def handle_data(self, data):
        pass


def parse_html(html):
    parser = FileLinkHTMLParser()
    parser.reset()
    parser.feed(html)
    return parser.folders, parser.files


if __name__ == '__main__':
    main()
