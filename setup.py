from setuptools import setup

setup(
    name='wetransfer',
    version='0.1',
    py_modules=['script'],
    install_requires=[
        'Click',
        'loguru',
        'PySocks',
        'requests',
        'tqdm'
    ],
    entry_points='''
        [console_scripts]
        wetransfer=script:cli
    ''',
)