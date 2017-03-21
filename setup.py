from setuptools import setup, find_packages


setup(
    name='rigidsearch',
    version='1.0.dev0',
    url='http://github.com/getsentry/rigidsearch',
    description='A simple web search API.',
    license='BSD',
    author='Sentry',
    author_email='hello@getsentry.com',
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    platforms='any',
    install_requires=[
        'click>=6.0',
        'Flask',
        'whoosh',
        'html5lib<=0.9999999',
        'lxml',
        'cssselect',
        'raven',
        'blinker',
    ],
    extras_require={
        'server': ['gunicorn', 'gevent'],
        'test': ['pytest'],
    },
    classifiers=[
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        'Topic :: Software Development :: Libraries :: Python Modules'
    ],
    entry_points='''
        [console_scripts]
        rigidsearch=rigidsearch.cli:main
    '''
)
