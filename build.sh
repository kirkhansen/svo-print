#!/usr/bin/env bash

pyinstaller -y cli.py
pushd html-to-pdf
npm install
npm run pack
popd
