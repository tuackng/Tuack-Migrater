from setuptools import setup, find_packages

requires = [
    "loguru>=0.7.3",
    "PyYAML>=5.1",
    "questionary>=2.0.0",
    "pydantic>=2.0.0",
    "rich>=15.0.0",
]

setup(
    name='tuack-migrater',
    version='0.1.1',
    packages=find_packages(include=['tuack_migrater', 'tuack_migrater.*']),
    description='Tools for migrating tuack contest projects to tuack-ng format.',
    install_requires=requires,
)
