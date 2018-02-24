#!/usr/bin/env bash

set -e

pyinstaller -y svo-print.spec
pushd dist
zip -FSr svo-print.zip svo-print
popd

pushd html-to-pdf
npm install
npm run pack
popd
