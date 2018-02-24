#!/usr/bin/env bash

set -e

pyinstaller -y cli.spec
pushd dist
zip -r cli.zip cli
popd

pushd html-to-pdf
npm install
npm run pack
popd
