import argparse
from html.parser import HTMLParser
import os
import shutil
from progressbar import ProgressBar
import requests
from multiprocessing import pool
import multiprocessing
import math
import signal
import traceback
import sys
import zipfile
from xml.etree import ElementTree
import tempfile


home = os.path.expanduser('~')
hiddenDir = home + '/.target-platform/'
current_dir = hiddenDir + 'current/'
backup_dir = hiddenDir + 'backup/'
tp_name = None
url = None
user = None
password = None
remote_directory = None
local_directory = None
files = None
ignored_files = {'.exe', '.zip', '.gz', '.md5', '.dmg'}


def get_arguments():
    parser = argparse.ArgumentParser(description='Mirror target platform')
    parser.add_argument('operation', type=str, help='update: update the current target platform. restore: restore the '
                                                    'previous target platform. clean: remove restore point.')
    parser.add_argument('targetplatform', type=str, help='The target platform to use.')
    return parser.parse_args()


def load_config(targetplatform):
    global tp_name, url, password, user
    with open(hiddenDir + 'urls', 'r') as file:
        lines = file.readlines()
    for i in range(len(lines)):
        split = lines[i].split(' : ')
        if len(split) != 2:
            continue
        tp_name, url = split
        tp_name = tp_name.strip()
        url = url.strip()
        if tp_name == targetplatform:
            break
    if not url.endswith('/'):
        url += '/'
    if os.path.isfile(hiddenDir + 'account'):
        with open(hiddenDir + 'account', 'r') as file:
            user, password = file.readlines()
        user = user.replace('\n', '')
        password = password.replace('\n', '')


def main():
    signal.signal(signal.SIGINT, handle_sigint)
    arguments = get_arguments()
    operation = arguments.operation
    targetplatform = arguments.targetplatform
    load_config(targetplatform)
    if targetplatform != tp_name:
        print('The target platform ' + targetplatform + ' could not be found in the config file ' + hiddenDir + 'urls')
    elif operation == 'update':
        backup()
        try:
            update()
        except Exception as e:
            print('Error occured: ' + str(e), file=sys.stderr)
            traceback.print_exc()
            restore()
    elif operation == 'restore':
        restore()
    elif operation == 'clean':
        clean()
    else:
        print('Unknown operation: ' + operation)


def backup():
    if os.path.exists(backup_dir + tp_name):
        if os.path.exists(current_dir + tp_name):
            shutil.rmtree(current_dir + tp_name)
    elif os.path.exists(current_dir + tp_name):
        shutil.move(current_dir + tp_name, backup_dir + tp_name)


def restore():
    if os.path.exists(backup_dir + tp_name):
        if os.path.exists(current_dir + tp_name):
            shutil.rmtree(current_dir + tp_name)
        shutil.move(backup_dir + tp_name, current_dir + tp_name)
        print('Restored backup for ' + tp_name)
    else:
        print('No backup available for ' + tp_name)


def clean():
    if os.path.exists(backup_dir):
        shutil.rmtree(backup_dir)
        print('Backup for ' + tp_name + ' removed')
    else:
        print('No backup for ' + tp_name + ' available')


def update():
    global remote_directory, local_directory, files
    files = []
    remote_directory = url
    local_directory = current_dir + tp_name + '/'
    parse_folder(url)
    print('Downloading ' + tp_name + ' from ' + url)
    download_files()


def parse_folder_html(url):
    html = get_html(url)
    folders, file_names = parse_html(html)
    for folder in folders:
        parse_folder(url + folder)
    for file in file_names:
        add_file(url + file)


def parse_folder(url):
    tmp_folder = get_temporary_file_path('target-platform-manager') + os.sep
    composite_content = 'compositeContent.jar'
    composite_artifacts = 'compositeArtifacts.jar'
    content = 'content.jar'
    artifacts = 'artifacts.jar'
    if download_file(url + composite_content, tmp_folder, raise_exception=False):
        add_file(url + composite_content)
        add_file(url + composite_artifacts)
        folders = parse_composite_content(tmp_folder + composite_content)
        for folder in folders:
            parse_folder(url + folder)
    elif download_file(url + content, tmp_folder, raise_exception=False):
        add_file(url + content)
        add_file(url + artifacts)
        file_list = parse_content(tmp_folder + content)
        for file in file_list:
            add_file(url + file)
    shutil.rmtree(tmp_folder)


def parse_composite_content(path):
    folders = list()
    xml = read_zipped_file(path, 'compositeContent.xml')
    root = ElementTree.fromstring(xml)
    children = root.findall('./children/child')
    for child in children:
        folder = child.get('location')
        if not folder.endswith('/'):
            folder += '/'
        folders.append(folder)
    return folders


def parse_content(path):
    file_set = set()
    xml = read_zipped_file(path, 'content.xml')
    root = ElementTree.fromstring(xml)
    artifacts = root.findall('./units/unit/artifacts/artifact')
    for artifact in artifacts:
        file_name = artifact.get('id') + '_' + artifact.get('version')
        classifier = artifact.get('classifier')
        if classifier == 'osgi.bundle':
            folder_name = 'plugins'
            file_name += '.jar'
        elif classifier == 'org.eclipse.update.feature':
            folder_name = 'features'
            file_name += '.jar'
        elif classifier == 'binary':
            folder_name = 'binary'
        else:
            raise ValueError('Unknown artifact classifier in content.xml: ' + classifier)
        file_set.add(folder_name + '/' + file_name)
    return file_set


def read_zipped_file(zip_path, file_path):
    with zipfile.ZipFile(zip_path, 'r') as zip_file:
        return zip_file.read(file_path)


def get_temporary_file_path(prefix=None):
    file_path = tempfile.mkstemp(prefix=prefix)[1]
    os.remove(file_path)
    return file_path


def download_files():
    global files
    number_processes = os.cpu_count()
    signal.signal(signal.SIGINT, handle_sigint_worker)
    with pool.Pool(number_processes) as process_pool:
        with ProgressBar(max_value=len(files)) as progress:
            progress.update(0)
            chunks = chunk(len(files), number_processes)
            queue = multiprocessing.Manager().Queue()
            for file_chunk in chunks:
                process_pool.apply_async(download_file_batch, [files[file_chunk['start']:file_chunk['end']], queue])
            signal.signal(signal.SIGINT, handle_sigint)
            workers_done = 0
            done = 0
            while workers_done < number_processes:
                result = queue.get()
                if result is True:
                    workers_done += 1
                elif isinstance(result, int):
                    done += result
                    progress.update(done)
                else:
                    raise result


def download_file_batch(file_batch, queue):
    try:
        for file in file_batch:
            local_path = file.replace(remote_directory, local_directory)
            folder = os.path.dirname(local_path) + '/'
            download_file(file, folder)
            queue.put(1)
        queue.put(True)
    except Exception as e:
        queue.put(e)


def download_file(url, folder, raise_exception=True):
    os.makedirs(folder, exist_ok=True)
    auth = None
    if user is not None and password is not None:
        auth = requests.auth.HTTPBasicAuth(user, password)
    response = requests.get(url, auth=auth)
    if response.status_code != 200:
        if raise_exception:
            raise IOError(str(response.status_code) + ': Could not download \'' + url + '\': ')
        return False
    with open(folder + os.path.basename(url), 'wb') as local_file:
        local_file.write(response.content)
        return True


def handle_sigint(signal_, frame):
    print('\nProcess aborted', file=sys.stderr)
    restore()
    sys.exit(0)


def handle_sigint_worker(signal_, frame):
    sys.exit(0)


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


def chunk(number, number_chunks):
    chunks = []
    chunk_size = math.ceil(number / number_chunks)
    number_chunks = math.ceil(number / chunk_size)
    for i in range(number_chunks):
        start = chunk_size * i
        end = min(start + chunk_size, number)
        size = end - start
        chunks.append({'size': size, 'start': start, 'end': end})
    return chunks


if __name__ == '__main__':
    main()
