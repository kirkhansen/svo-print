#!/usr/bin/env bash

set -e

pyinstaller -y cli.py
pushd html-to-pdf
npm install
npm run pack
popd
