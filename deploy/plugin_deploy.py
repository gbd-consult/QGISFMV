import os
import sys
import shutil
import platform
from configparser import ConfigParser

windows = platform.system() == "Windows"

directory = os.path.realpath(__file__)

basePath = os.path.join(directory, os.path.realpath("../code"))
print("basePath : " + basePath)
os.chdir(basePath)

with open("metadata.txt") as mf:
    cp = ConfigParser()
    cp.read_file(mf)
    internal_name = cp.get("general", "internal_name")
    VERSION = cp.get("general", "version")

destPath = os.path.join(
    os.path.expanduser(('~')),
    '.local/share/QGIS/QGIS3/profiles/default/python/plugins',
    internal_name
)
print("destPath : " + destPath)

def copyProjectStructure():
    """ Copy structure project """
    print("Copying structure")
    try:
        if os.path.exists(destPath):
            shutil.rmtree(destPath)

        if windows:
            os.system(
                'robocopy %s %s /E /V /XD ".settings" "sql" "__pycache__" "tests" "ui" ".git" /XF *.bat *.sh *.pro *.ts .gitignore *.docx *.bak *.yml *.pyc *.ps1 *.project *.pydevproject'
                % (basePath, destPath)
            )
        else:
            basePath_linux = os.path.join(directory, os.path.realpath("../code/*"))
            exclude = os.path.join(os.path.dirname(directory), "exclude-file.txt")
            cmd = 'rsync -avi --progress --exclude-from="{}" {} {}'.format(
                exclude, basePath_linux, destPath
            )
            os.system(cmd)

    except Exception as e:
        print("An error occurred when copying the project structure : " + str(e))
        sys.exit(1)


if __name__ == "__main__":
    copyProjectStructure()