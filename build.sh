#!/usr/bin/env bash
set -e

PYTHON_VERSION=${PYTHON_VERSION:=python2}

${PYTHON_VERSION} setup.py bdist_wheel

pushd html-to-pdf
npm install
npm run pack
popd
