import setuptools
import os

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="pidtree-bcc",
    version="0.2",
    author="Matt Carroll",
    author_email="oholiab@grimmwa.re",
    description="eBPF-based intrusion detection and audit logging",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/oholiab/pidtree-bcc",
    packages=setuptools.find_packages(),
    license='BSD 3-clause "New" or "Revised License"',
    classifiers=[
        "Programming Language :: Python :: 2",
        "License :: OSI Approved :: BSD License",
        "Operating System :: Linux",
    ],
)
