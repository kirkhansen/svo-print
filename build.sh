#!/usr/bin/env bash

set -e

python setup.py bdist_wheel

pushd html-to-pdf
npm install
npm run pack
popd
