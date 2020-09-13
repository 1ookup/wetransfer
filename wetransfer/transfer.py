#!/usr/bin/env python
# encoding: utf-8
__time__ = '2020/9/10 2:07 PM'

import re
import os
import sys
import uuid
import requests
# import urllib3
requests.packages.urllib3.disable_warnings()
from loguru import logger
from tqdm import tqdm
config = {
    "handlers": [
        {"sink": sys.stdout, "format": "[<green>{level}</green>] <level>{message}</level>"},
        # {"sink": "file.log", "serialize": True},
    ],
    # "extra": {"user": "someone"}
}
logger.configure(**config)

class upload_in_chunks(object):
    def __init__(self, filename, chunksize=1 << 18):
        self.filename = filename
        self.chunksize = chunksize
        self.totalsize = os.path.getsize(filename)
        self.readsofar = 0
        first_byte = 0
        self.pbar = tqdm(
            total=self.totalsize, initial=first_byte,
            unit='iB', unit_scale=True, desc='')

    def __iter__(self):
        with open(self.filename, 'rb') as file:
            while True:
                data = file.read(self.chunksize)
                if not data:
                    sys.stderr.write("\n")
                    break
                self.readsofar += len(data)
                percent = self.readsofar * 1e2 / self.totalsize
                # sys.stderr.write("\r{percent:3.0f}%".format(percent=percent))
                self.pbar.update(len(data))
                yield data
            self.pbar.close()

    def __len__(self):
        return self.totalsize

class Transfer():
    def __init__(self, proxy=None, chunksize = 256):
        self.http = requests.session()
        self.token_header = None
        self.__proxy = proxy
        if self.__proxy:
            logger.info("Proxy: {}".format(proxy))
        self.chunksize = chunksize

    def upload(self, file=None):#, files=None):
        if not file: # and not files:
            return False
        upload_files = []
        # data = open(file, 'rb').read()
        file_path = file
        if file:
            upload_files.append({
                "name": os.path.basename(file),
                "size": os.path.getsize(file),
                "item_type": "file"})
        # if files:
        #     return False

        csrf_token = self.__csrf_token()
        if not csrf_token:
            logger.warning("csrf token 获取错误")
            return False

        self.token_header = {
            "X-CSRF-Token": csrf_token['token']
        }

        if not self.__link(upload_files):
            logger.warning("获取 transfers link 出错")
            return False

        for file in self.files:
            # logger.info(file)
            url = self.__put_url(file)
            if not url:
                logger.warning("获取 AWS put url 出错: {}".format(file))
                return False


            if not self.__put_aws(url, file_path=file_path):
                logger.warning("AWS 上传文件出错: {}".format(file))
                return False

            if not self.__finalize_mpp(file):
                logger.warning("finalize mpp error: {}".format(file))
                return False

        url = self.__finalize()
        return url


    def __headers(self):
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_6) Chrome/83.0.4103.116"
        }
        return headers

    def __options(self):
        options = {
            "verify": False,
            # "proxies": {"https": "socks5://127.0.0.1:7890"},
            "headers": self.__headers()
        }
        if self.__proxy:
            options["proxies"] = {"https": self.__proxy}
        if self.token_header:
            options["headers"].update(self.token_header)
        return options

    def __csrf_token(self):
        pass
        url = "https://wetransfer.com/"
        resp = self.http.get(url, **self.__options())
        # logger.debug(resp.text)
        m = re.search('<meta name="csrf-param" content="([\w_]*)" />', resp.text)
        param = m.group(1)

        m = re.search('<meta name="csrf-token" content="([\w_/+=]*)" />', resp.text)
        token = m.group(1)

        csrf = {
            "param": param,
            "token": token
        }
        logger.debug("csrf token: {}".format(csrf["token"]))
        # self.csrf = csrf
        return csrf

    def __link(self, files):
        payload = {
            "message":"",
            "ui_language":"en",
            "domain_user_id":str(uuid.uuid4()), # "df99c230-57d8-4376-a5d0-28d32ffe5cdd",
            "files":files
        }
        url = "https://wetransfer.com/api/v4/transfers/link"
        try:
            resp = self.http.post(url, json=payload, **self.__options())
            resp = resp.json()
            self.tid = resp["id"]
            self.files = resp["files"]
        except:
            return False
        return True

    def __put_url(self, file):
        url = "https://wetransfer.com/api/v4/transfers/{}/files".format(self.tid)
        payload = {
            "name": file["name"],
            "size": file["size"]
        }
        resp = self.http.post(url, json=payload, **self.__options())
        # logger.info(resp.text)

        payload = {
            "chunk_number": 1,
            "chunk_size": file["size"],
            "chunk_crc": 0
        }
        url = "https://wetransfer.com/api/v4/transfers/{}/files/{}/part-put-url".format(self.tid, file["id"])
        aws_url = None
        try:
            resp = self.http.post(url, json=payload, **self.__options())
            aws_url = resp.json()["url"]
        except Exception as e:
            logger.exception(e)

        return aws_url

    def __put_aws(self, aws_url, data=None, file_path=None):
        # resp = self.http.put(aws_url, data=data)
        resp = self.http.put(aws_url, data=upload_in_chunks(file_path, chunksize=self.chunksize*1024), **self.__options())
        if resp.status_code == 200:
            return True
        else:
            return False

    def __finalize_mpp(self, file):
        url = "https://wetransfer.com/api/v4/transfers/{}/files/{}/finalize-mpp".format(self.tid, file["id"])
        payload = {
            "chunk_count": 1
        }
        resp = self.http.put(url, json=payload, **self.__options())
        if resp.status_code == 200:
            return True
        else:
            return False

    def __finalize(self):
        url = "https://wetransfer.com/api/v4/transfers/{}/finalize".format(self.tid)
        resp = self.http.put(url, **self.__options())
        url = None
        try:
            url = resp.json()["shortened_url"]
        except Exception as e:
            pass
        return url

    def download(self, surl, target_path):
        resp = self.http.get(surl, **self.__options())
        logger.info(resp.url)
        m = re.match(r"https://wetransfer.com/downloads/(\w+)/(\w+)", resp.url)
        if not m:
            logger.warning("url 格式错误")
        tid = m.group(1)
        security_hash = m.group(2)
        m = re.search('<meta name="csrf-token" content="([\w_/+=]*)" />', resp.text)
        self.token_header = {
            "X-CSRF-Token": m.group(1)
        }

        download_url = self.__direct_link(tid, security_hash)
        self.__download_file(download_url, target_path)

    def __direct_link(self, tid, security_hash):
        url = "https://wetransfer.com/api/v4/transfers/{}/download".format(tid)
        payload = {
            "security_hash":security_hash,
            "intent":"entire_transfer",
            "domain_user_id":str(uuid.uuid4())
        }
        resp = self.http.post(url, json=payload, **self.__options())
        download_url = resp.json()["direct_link"]
        return download_url

    def __download_file(self, url, path):
        response = self.http.get(url, **self.__options(), stream=True)
        total_size_in_bytes = int(response.headers.get('content-length', 0))
        block_size = 1024 * self.chunksize  # 1 Kibibyte
        progress_bar = tqdm(total=total_size_in_bytes, unit='iB', unit_scale=True)
        with open(path, 'wb') as file:
            for data in response.iter_content(block_size):
                progress_bar.update(len(data))
                file.write(data)
        progress_bar.close()
        if total_size_in_bytes != 0 and progress_bar.n != total_size_in_bytes:
            print("ERROR, something went wrong")

        # resp = self.http.get(url, **self.__options())
        # logger.info(resp.text)


if __name__ == '__main__':
    t = Transfer(proxy="socks5://127.0.0.1:7890")
    # f = open("/tmp/test.txt")
    # files = f

    # url = t.upload(file="/tmp/Aweme")
    # logger.info("短连接: {}".format(url))

    # t.download("https://we.tl/t-cWlydYMq3S")
    t.download("https://we.tl/t-AxtF5hzkAW", "/tmp/a")