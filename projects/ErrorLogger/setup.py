from setuptools import setup, find_packages

setup(
    name="ErrorLogger",
    version="0.1.0",
    description="A reusable error logging utility for Flask and other Python projects.",
    author="Your Name",
    packages=find_packages(),
    install_requires=[
        "Flask",
        "Werkzeug"
    ],
    include_package_data=True,
    python_requires=">=3.7",
)
