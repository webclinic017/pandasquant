import os
import json
import time
import diskcache
import pickle
import random
import hashlib
import requests
import pandas as pd
from functools import wraps
from lxml import etree
from bs4 import BeautifulSoup


class FrameWorkError(Exception):
    def __init__(self, func: str, hint: str) -> None:
        self.func = func
        self.hint = hint
    
    def __str__(self) -> str:
        return f'[-] <{self.func}> {self.hint}'

class Worker(object):
    TS = 1
    CS = 2
    PN = 3
    
    def __init__(self, data: 'pd.DataFrame | pd.Series'):
        self.data = data
        self._validate()
    
    def series2frame(self, data: pd.Series = None, name: str = None):
        if data is None:
            self.data.to_frame(name=name or 'frame')
        else:
            return data.to_frame(name=name or 'frame')
    
    def frame2series(self, data: pd.DataFrame = None, name: str = None):
        if data is None:
            data = self.data
        series = data.iloc[:, 0]
        series.name = name or data.columns[0]
        if data is None:
            self.data = series
        else:
            return series
    
    def ists(self, data: 'pd.DataFrame | pd.Series' = None):
        if data is None:
            data = self.data
        return not isinstance(data.index, pd.MultiIndex) and isinstance(data.index, pd.DatetimeIndex)
    
    def iscs(self, data: 'pd.DataFrame | pd.Series' = None):
        if data is None:
            data = self.data
        return not isinstance(data.index, pd.MultiIndex) and not isinstance(data.index, pd.DatetimeIndex)
    
    def ispanel(self, data: 'pd.DataFrame | pd.Series' = None):
        if data is None:
            data = self.data
        return isinstance(data.index, pd.MultiIndex) and len(data.index.levshape) >= 2 \
                and isinstance(data.index.levels[0], pd.DatetimeIndex)
    
    def isframe(self, data: 'pd.DataFrame | pd.Series' = None):
        if data is None:
            data = self.data
        return True if isinstance(data, pd.DataFrame) else False
    
    def isseries(self, data: 'pd.DataFrame | pd.Series' = None):
        if data is None:
            data = self.data
        return True if isinstance(data, pd.Series) else False

    def _validate(self):

        self.is_frame = self.isframe()
        self.is_series = self.isseries()
        
        if self.is_frame and self.data.columns.size == 1:
            self.is_frame = False
            self.frame2series()
            
        if self.data.empty:
            raise ValueError('[!] Dataframe or Series is empty')

        is_ts = self.ists(self.data)
        is_cs = self.iscs(self.data)
        is_panel = self.ispanel(self.data)
        
        if is_ts:
            self.type_ = Worker.TS
        elif is_cs:
            self.type_ = Worker.CS
        elif is_panel:
            self.type_ = Worker.PN
        else:
            raise ValueError("Your dataframe or series seems not supported in our framework")
 
    def _flat(self, datetime, asset, indicator):
        
        data = self.data.copy()
        
        if self.type_ == Worker.PN:
            check = (not isinstance(datetime, slice), 
                     not isinstance(asset, slice), 
                     not isinstance(indicator, slice))

            # is a panel and is a dataframe
            if check == (False, False, False) and self.is_frame:
                raise ValueError('Must assign at least one of dimension')
            elif check == (False, True, True) and self.is_frame:
                return data.loc[(datetime, asset), indicator].droplevel(1)
            elif check == (True, False, True) and self.is_frame:
                return data.loc[(datetime, asset), indicator].droplevel(0)
            elif check == (True, True, False) and self.is_frame:
                return data.loc[(datetime, asset), indicator]
            elif check == (True, False, False) and self.is_frame:
                return data.loc[(datetime, asset), indicator].droplevel(0)
            elif check == (False, True, False) and self.is_frame:
                return data.loc[(datetime, asset), indicator].droplevel(1)
            elif check == (False, False, True) and self.is_frame:
                return data.loc[(datetime, asset), indicator].unstack(level=1)
            elif check == (True, True, True) and self.is_frame:
                print('[!] single value was selected')
                return data.loc[(datetime, asset), indicator]
                
            # is a panel and is a series
            elif (check[-1] or not any(check)) and not self.is_frame:
                if check[-1]:
                    print("[!] Your data is not a dataframe, indicator will be ignored")
                return data.unstack()
            elif check[1] and not self.is_frame:
                return data.loc[(datetime, asset)].unstack()
            elif check[0] and not self.is_frame:
                return data.loc[(datetime, asset)]
                
        else:
            # not a panel and is a series
            if not self.is_frame:
                if self.type_ == Worker.TS:
                    return data.loc[datetime]
                elif self.type_ == Worker.CS:
                    return data.loc[asset]
            # not a panel and is a dataframe
            else:
                if self.type_ == Worker.TS:
                    return data.loc[(datetime, indicator)]
                elif self.type_ == Worker.CS:
                    return data.loc[(asset, indicator)]

class Request(object):

    def __init__(self, url, headers: dict = None, **kwargs):
        self.url = url
        if headers:
            headers.update(self.header())
            self.headers = headers
        else:
            self.headers = self.header()
        self.kwargs = kwargs
        
    def header(self):
        ua_list = [
            'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/30.0.1599.101',
            'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/38.0.2125.122',
            'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.71',
            'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95',
            'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.1 (KHTML, like Gecko) Chrome/21.0.1180.71',
            'Mozilla/4.0 (compatible; MSIE 6.0; Windows NT 5.1; SV1; QQDownload 732; .NET4.0C; .NET4.0E)',
            'Mozilla/5.0 (Windows NT 5.1; U; en; rv:1.8.1) Gecko/20061208 Firefox/2.0.0 Opera 9.50',
            'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:34.0) Gecko/20100101 Firefox/34.0',
            ]
        base_header = {
            "User-Agent": random.choice(ua_list),
            'Accept': '*/*',
            'Connection': 'keep-alive',
            'Accept-Language': 'zh-CN,zh;q=0.8'
        }
        return base_header

    # @cache()
    def get(self):
        try:
            response = requests.get(self.url, headers=self.headers, **self.kwargs)
            response.raise_for_status()        
            self.response = response
            print(f'[+] {self.url} Get Success!')
            return self
        except Exception as e:
            print(f'[-] Error: {e}')

    def post(self):
        try:
            response = requests.post(self.url, headers=self.headers, **self.kwargs)
            response.raise_for_status()        
            self.response = response
            print(f'[+] {self.url} Post Success!')
            return self
        except Exception as e:
            print(f'[-] Error: {e}')

    @property
    def etree(self):
        return etree.HTML(self.response.text)

    @property
    def json(self):
        return json.loads(self.response.text)
    
    @property
    def soup(self):
        return BeautifulSoup(self.response.text, 'lxml')


class ProxyRequest(Request):
    
    def __init__(self, url, headers: dict = None, 
        proxies: list = None, timeout: int = None, 
        retry: int = None, retry_delay: float = None,**kwargs):
        super().__init__(url, headers, **kwargs)
        self.proxies = [] if proxies is None else proxies
        self.timeout = 2 if timeout is None else timeout
        self.retry = -1 if retry is None else retry
        self.retry_delay = 0 if retry_delay is None else retry_delay
        self.kwargs = kwargs
    
    def get(self):
        if isinstance(self.proxies, dict):
            self.proxies = [self.proxies]
        random.shuffle(self.proxies) 
        if self.retry == -1:
            self.retry = len(self.proxies)
        for try_times, proxy in enumerate(self.proxies):
            if try_times + 1 <= self.retry:
                try:
                    response = requests.get(self.url, headers=self.headers, proxies=proxy, **self.kwargs)
                    response.raise_for_status()
                    self.response = response
                    print(f'[+] {self.url}, try {try_times + 1}/{self.retry}')
                    return self
                except Exception as e:
                    print(f'[-] [{e}] {self.url}, try {try_times + 1}/{self.retry}')
                    time.sleep(self.retry_delay)

    def post(self):
        if isinstance(self.proxies, dict):
            self.proxies = [self.proxies]
        random.shuffle(self.proxies) 
        if self.retry == -1:
            self.retry = len(self.proxies)
        for try_times, proxy in enumerate(self.proxies):
            if try_times + 1 <= self.retry:
                try:
                    response = requests.post(self.url, headers=self.headers, proxies=proxy, **self.kwargs)
                    response.raise_for_status()
                    self.response = response
                    print(f'[+] {self.url}, try {try_times + 1}/{self.retry}')
                    return self
                except Exception as e:
                    print(f'[-] [{e}] {self.url}, try {try_times + 1}/{self.retry}')
                    time.sleep(self.retry_delay)

    def get_async(self, container: dict):
        if isinstance(self.proxies, dict):
            self.proxies = [self.proxies]
        random.shuffle(self.proxies) 
        if self.retry == -1:
            self.retry = len(self.proxies)
        for try_times, proxy in enumerate(self.proxies):
            if try_times + 1 <= self.retry:
                try:
                    response = requests.get(self.url, headers=self.headers, proxies=proxy, **self.kwargs)
                    response.raise_for_status()
                    self.response = response
                    container[self.url] = self.process()
                    print(f'[+] {self.url}, try {try_times + 1}/{self.retry}')
                    break
                except Exception as e:
                    print(f'[-] [{e}] {self.url}, try {try_times + 1}/{self.retry}')
                    time.sleep(self.retry_delay)

    def post_async(self, container: dict):
        if isinstance(self.proxies, dict):
            self.proxies = [self.proxies]
        random.shuffle(self.proxies) 
        if self.retry == -1:
            self.retry = len(self.proxies)
        for try_times, proxy in enumerate(self.proxies):
            if try_times + 1 <= self.retry:
                try:
                    response = requests.post(self.url, headers=self.headers, proxies=proxy, **self.kwargs)
                    response.raise_for_status()
                    self.response = response
                    container[self.url] = self.process()
                    print(f'[+] {self.url}, try {try_times + 1}/{self.retry}')
                    break
                except Exception as e:
                    print(f'[-] [{e}] {self.url}, try {try_times + 1}/{self.retry}')
                    time.sleep(self.retry_delay)

    def process(self):
        raise NotImplementedError


class Cache(diskcache.Cache):

    def __init__(self, 
        directory: str = None, 
        prefix: str = 'generic', 
        expire_time: float = 3600,
    ):
        if directory is None:
            directory = os.path.join(os.path.split(os.path.abspath(__file__))[0] ,'..', 'cache')
        self.prefix = prefix
        self.expire_time = expire_time
        super().__init__(directory)
    
    @staticmethod
    def md5key(func, *args, **kwargs):
        return hashlib.md5(pickle.dumps(f'{func.__name__};{args};{kwargs}')).hexdigest()
    
    def __call__(self, func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            hash_key = self.md5key(func, *args, **kwargs)
            data = self.get(key=self.prefix + ':' + hash_key)
            if data is not None:
                # get cache successful
                return data
            else:
                # not fund cache,return data will be cache
                result = func(*args, **kwargs)
                self.set(key=self.prefix + ':' + hash_key, value=result, expire=self.expire_time)
                return result
        return wrapper


@Cache(directory=None, prefix='proxy', expire_time=172800)
def get_proxy(page_size: int = 20):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.163 Safari/537.36"
    }
    url_list = [f'https://free.kuaidaili.com/free/inha/{i}/' for i in range(1, page_size + 1)]
    proxies = []
    for url in url_list:
        data = pd.read_html(url)[0][['IP', 'PORT', '类型']].drop_duplicates()
        print(f'[+] {url} Get Success!')
        data['类型'] = data['类型'].str.lower()
        proxy = (data['类型'] + '://' + data['IP'] + ':' + data['PORT'].astype('str')).to_list()
        proxies += list(map(lambda x: {x.split('://')[0]: x}, proxy))
        time.sleep(0.8)
    available_proxies = []
    
    for proxy in proxies:
        try:
            res = Request('https://www.baidu.com', headers=headers,
                proxies=proxy, timeout=1).get().response
            res.raise_for_status()
            available_proxies.append(proxy)
        except Exception as e:
            print(str(e))
    
    print(f'[=] Get {len(proxies)} proxies, while {len(available_proxies)} are available. '
        f'Current available rate is {len(available_proxies) / len(proxies) * 100:.2f}%')
    return proxies


@Cache(directory=None, prefix='holidays', expire_time=31556926)
def chinese_holidays():
    root = 'https://api.apihubs.cn/holiday/get'
    complete = False
    page = 1
    holidays = []
    while not complete:
        params = f'?field=date&holiday_recess=1&cn=1&page={page}&size=366'
        url = root + params
        data = Request(url).get().json['data']
        if data['page'] * data['size'] >= data['total']:
            complete = True
        days = pd.DataFrame(data['list']).date.astype('str')\
            .astype('datetime64[ns]').to_list()
        holidays += days
        page += 1
    return holidays

try:
    CHD = chinese_holidays()
    CBD = pd.offsets.CustomBusinessDay(holidays=CHD)
except:
    print(f'[!] It seems that you have no internet connection, please check your network')
    CBD = pd.offsets.BusinessDay()


if __name__ == "__main__":
    Cache().expire()
