from setuptools import setup, find_packages

setup(
    name='User-Functionality-WSL',
    version='0.2.0',
    packages=find_packages(),
    install_requires=[
        'python-dotenv>=1.0.0',
    ],
    description='A modular collection of quality-of-life tools for WSL2 users',
    author='datamann1013',
    include_package_data=True,
    python_requires=">=3.8",
    extras_require={
        'ai_service': [
            'Flask>=2.3.0',
            'torch>=2.0.0',
            'transformers>=4.30.0',
            'huggingface_hub>=0.16.0',
            'accelerate>=0.20.0',
        ],
        'error_logger': [
            'Flask>=2.3.0',
            'Werkzeug>=2.3.0',
            'requests>=2.31.0',
        ]
    }
)
