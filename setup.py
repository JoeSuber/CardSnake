from distutils.core import setup

setup(
        name='CardSnake',
        version='.1',
        packages=['requests', 'grequests', 'Levenshtein', 'gmpy2', 'numpy', 'cv2'],
        url='https://github.com/Joesuber/CardSnake',
        license='MIT',
        author='Joe Suber',
        author_email='joesuber@gmail.com',
        description='scrape together data & images of Magic: the Gathering cards. Serve them up by similarity measures.'
)
