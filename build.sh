#!/bin/bash
pyinstaller ./src/iMeshBackend.py --onefile
pyinstaller ./src/iMeshDbClean.py --onefile
rm -r build
rm *.spec
