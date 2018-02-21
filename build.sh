#!/usr/bin/env bash

set -e

pyinstaller -y cli.spec
pushd dist
tar -czf cli.tar.gz cli
popd

pushd html-to-pdf
npm install
npm run pack
popd
