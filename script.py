import os
import sys
import click
path = os.path.join(os.path.dirname(os.path.dirname(__file__)))
sys.path.append(path)
from wetransfer import Transfer

PROXY = None
ChunkSize = 256

@click.group()
# @click.option('--debug/--no-debug', default=False)
@click.option('--proxy', '-p', default=None, type=click.STRING, help='socks5://127.0.0.1:1080')
@click.option('--chunksize', '-c', default=256, type=click.INT, help='chunksize (kb)')
def cli(proxy, chunksize):
    # click.echo('Debug mode is %s' % ('on' if debug else 'off'))
    global PROXY
    PROXY = proxy
    global ChunkSize
    ChunkSize = chunksize

@cli.command()
@click.option('--file', '-f', type=click.Path(exists=True), help='upload file path')
def upload(file):
    global PROXY
    global ChunkSize
    ts = Transfer(proxy=PROXY, chunksize=ChunkSize)
    ts.upload(file)

@cli.command()
@click.option('--url', '-u', type=click.STRING, help='download url. eg: https://we.tl/t-XXXXXXX')
@click.option('--file', '-f', type=click.Path(exists=False), help='download file path')
def download(url, file):
    global PROXY
    global ChunkSize
    ts = Transfer(proxy=PROXY, chunksize=ChunkSize)
    ts.download(url, file)

if __name__ == '__main__':
    cli()


