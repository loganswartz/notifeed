#!/usr/bin/env python3
import setuptools

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="notifeed",
    version="1.0.0",
    author="Logan Swartzendruber",
    author_email="logan.swartzendruber@gmail.com",
    description="Automatically get notifications for new posts on your favorite RSS/Atom feeds.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/loganswartz/notifeed",
    packages=setuptools.find_packages(),
    include_package_data=True,
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.6",
    install_requires=[
        "Click",
    ],
    entry_points="""
        [console_scripts]
        notifeed=notifeed.cli:cli
    """,
)
