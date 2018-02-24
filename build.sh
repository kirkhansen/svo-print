#!/usr/bin/env bash

set -e

pyinstaller -y svo-print.spec
pushd dist
zip -r svo-print.zip svo-print
popd

pushd html-to-pdf
npm install
npm run pack
popd
