from setuptools import setup, find_packages
from typing import List

def get_requirements() -> List[str]:
    requirement_lst: List[str] = []
    try:
        with open('requirements.txt', 'r') as file:
            lines = file.readlines()
            for line in lines:
                if line.strip() and line.strip() != '-e .':
                    requirement_lst.append(line.strip())

        return requirement_lst

    except FileNotFoundError:
        print("Error: requirements.txt not found")
        return []


setup(
    name="E-Commerce Product Assistance",
    version="0.1",
    author="Atharva Rai",
    author_email="atharvarai07@gmail.com",
    packages=find_packages(),
    install_requires=get_requirements()
)
