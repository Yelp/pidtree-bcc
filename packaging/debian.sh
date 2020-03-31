#!/bin/bash

dpkg-buildpackage -us -uc
mv ../*.deb dist
chmod 777 dist/*.deb
