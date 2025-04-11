from setuptools import setup, find_packages

setup(
    name='sshm',
    version='0.1.0',
    description='A modern, user-friendly TUI for managing SSH connections',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    author='lele7663',
    author_email='your.email@example.com',
    url='https://github.com/lele7663/sshm',
    packages=find_packages(),
    py_modules=['sshm'],
    include_package_data=True,
    install_requires=[
        'textual',
        'cryptography',
        'paramiko',
    ],
    extras_require={
        'dev': [
            'pytest',
            'black',
            'flake8',
        ],
    },
    entry_points={
        'console_scripts': [
            'sshm=sshm:main',
        ],
    },
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
    ],
    python_requires='>=3.8',
    keywords='ssh, tui, terminal, manager, sftp',
    project_urls={
        'Bug Reports': 'https://github.com/lele7663/sshm/issues',
        'Source': 'https://github.com/lele7663/sshm',
    },
)
