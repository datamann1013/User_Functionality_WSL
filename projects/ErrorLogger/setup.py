from setuptools import setup, find_packages

setup(
    name="ErrorLogger",
    version="1.1.0",
    description="Advanced error logging system for WSL-based development environments",
    author="Auronex",
    packages=find_packages(),
    install_requires=[
        "Flask>=2.3.0",
        "Werkzeug>=2.3.0",
        "requests>=2.31.0",
        "python-dotenv>=1.0.0"
    ],
    include_package_data=True,
    python_requires=">=3.8",
    license="Apache-2.0",
    entry_points={
        'console_scripts': [
            'error-logger=error_server:main'
        ]
    }
)