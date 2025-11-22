from setuptools import find_packages, setup

setup(
    name="shared",
    version="0.1.0",
    packages=find_packages(),
    package_dir={"": "."},
    install_requires=[
        "sqlalchemy>=2.0.0",
        "loguru>=0.7.0",
        "python-dotenv>=1.0.0",
    ],
)
